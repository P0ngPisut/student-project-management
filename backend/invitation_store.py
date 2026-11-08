"""V1 advisor invitations: scoped reads and controlled resolution, no new grants."""

from contextlib import closing, contextmanager

import psycopg

from backend.auth_store import AuthRepository, StorageUnavailable, assert_auth_connection, open_auth_connection


class InvitationError(Exception):
    def __init__(self, code):
        self.code = code


@contextmanager
def invitation_transaction_on(conn):
    try:
        with conn.transaction():
            assert_auth_connection(conn)
            yield InvitationRepository(conn)
    except psycopg.Error as exc:
        if (exc.sqlstate == "23505" and exc.diag.schema_name == "public"
                and exc.diag.table_name == "advisor_invitations"
                and exc.diag.constraint_name == "uq_invitations_active_project"):
            raise InvitationError("INVITATION_CONFLICT") from None
        raise StorageUnavailable() from None


@contextmanager
def invitation_transaction():
    with closing(open_auth_connection()) as conn:
        with invitation_transaction_on(conn) as repository:
            yield repository


class InvitationRepository:
    def __init__(self, conn):
        self.conn = conn
        self.auth = AuthRepository(conn)

    @staticmethod
    def context_check(row, *, leader=False):
        if row is None:
            raise InvitationError("TEAM_NOT_FOUND")
        if row[2] is None:
            raise InvitationError("PROJECT_NOT_FOUND")
        if leader and row[1] != "leader":
            raise InvitationError("INVITATION_ACTION_FORBIDDEN")

    def context(self, actor):
        return self.conn.execute("""SELECT m.team_id,m.role,p.id FROM public.team_members m
            LEFT JOIN public.projects p ON p.team_id=m.team_id WHERE m.user_id=%s""", (actor,)).fetchone()

    def candidates(self, actor):
        # Authorization and candidate projection share one statement snapshot.
        rows = self.conn.execute("""SELECT m.team_id,m.role,p.id,a.id,a.full_name
            FROM public.team_members m LEFT JOIN public.projects p ON p.team_id=m.team_id
            LEFT JOIN public.users a ON a.role='advisor'
            WHERE m.user_id=%s ORDER BY a.full_name ASC,a.id ASC""", (actor,)).fetchall()
        self.context_check(rows[0] if rows else None, leader=True)
        return [{"id": str(row[3]), "full_name": row[4]} for row in rows if row[3] is not None]

    @staticmethod
    def team_dto(row):
        return {"id": str(row[0]), "advisor": {"id": str(row[1]), "full_name": row[2]},
                "status": row[3], "sent_at": row[4], "resolved_at": row[5]}

    @staticmethod
    def advisor_dto(row):
        return {"id": str(row[0]), "status": row[1], "sent_at": row[2], "resolved_at": row[3],
                "project_context": {"team_name": row[4], "project_name": row[5], "project_description": row[6]}
                if row[1] in ("pending", "accepted") else None}

    def team_history(self, actor):
        rows = self.conn.execute("""SELECT m.team_id,m.role,p.id,i.id,i.advisor_id,a.full_name,
                i.status,i.sent_at,i.resolved_at
            FROM public.team_members m LEFT JOIN public.projects p ON p.team_id=m.team_id
            LEFT JOIN public.advisor_invitations i ON i.project_id=p.id
            LEFT JOIN public.users a ON a.id=i.advisor_id
            WHERE m.user_id=%s ORDER BY i.sent_at DESC,i.id DESC""", (actor,)).fetchall()
        self.context_check(rows[0] if rows else None)
        return [self.team_dto(row[3:]) for row in rows if row[3] is not None]

    def advisor_history(self, actor):
        # Do not even select live Project values after rejection/cancellation.
        rows = self.conn.execute("""SELECT i.id,i.status,i.sent_at,i.resolved_at,
                CASE WHEN i.status IN ('pending','accepted') THEN t.name END,
                CASE WHEN i.status IN ('pending','accepted') THEN p.name END,
                CASE WHEN i.status IN ('pending','accepted') THEN p.description END
            FROM public.advisor_invitations i JOIN public.projects p ON p.id=i.project_id
            JOIN public.teams t ON t.id=p.team_id WHERE i.advisor_id=%s
            ORDER BY i.sent_at DESC,i.id DESC""", (actor,)).fetchall()
        return [self.advisor_dto(row) for row in rows]

    def set_actor(self, actor):
        self.conn.execute("SELECT pg_catalog.set_config('app.actor_user_id',%s,true)", (actor,))

    def lock_parents(self, team, project):
        self.conn.execute("SELECT public.v1_lock_team(%s)", (team,))
        self.conn.execute("SELECT public.v1_lock_project(%s)", (project,))

    def active(self, project):
        return self.conn.execute("""SELECT status FROM public.advisor_invitations
            WHERE project_id=%s AND status IN ('pending','accepted')""", (project,)).fetchone()

    def insert(self, project, advisor, actor):
        return self.conn.execute("""INSERT INTO public.advisor_invitations(project_id,advisor_id,sent_by)
            VALUES (%s,%s,%s) RETURNING id,advisor_id,status,sent_at,resolved_at""", (project,advisor,actor)).fetchone()

    def send(self, actor, advisor):
        original = self.context(actor)
        self.context_check(original, leader=True)
        self.set_actor(actor)
        self.lock_parents(original[0], original[2])
        current = self.context(actor)
        self.context_check(current, leader=True)
        if current[0] != original[0] or current[2] != original[2]:
            raise InvitationError("PROJECT_NOT_FOUND")
        active = self.active(current[2])
        if active:
            raise InvitationError("INVITATION_ALREADY_PENDING" if active[0] == "pending" else "ADVISOR_ALREADY_ACCEPTED")
        target = self.conn.execute("SELECT id,full_name FROM public.users WHERE id=%s AND role='advisor'", (advisor,)).fetchone()
        if target is None:
            raise InvitationError("ADVISOR_NOT_FOUND")
        row = self.insert(current[2], advisor, actor)
        return self.team_dto((row[0], row[1], target[1], row[2], row[3], row[4]))

    def authorized(self, actor, invitation, *, advisor):
        if advisor:
            return self.conn.execute("""SELECT i.id,p.team_id,p.id,i.status,NULL
                FROM public.advisor_invitations i JOIN public.projects p ON p.id=i.project_id
                WHERE i.id=%s AND i.advisor_id=%s""", (invitation,actor)).fetchone()
        return self.conn.execute("""SELECT i.id,p.team_id,p.id,i.status,m.role
            FROM public.advisor_invitations i JOIN public.projects p ON p.id=i.project_id
            JOIN public.team_members m ON m.team_id=p.team_id
            WHERE i.id=%s AND m.user_id=%s""", (invitation,actor)).fetchone()

    def resolve_function(self, invitation, decision):
        # This definer locks the invitation row and applies the original guard.
        # App never receives direct UPDATE/DELETE or row-lock UPDATE privileges.
        self.conn.execute("SELECT public.v1_resolve_invitation(%s,%s)", (invitation,decision))

    def resolve(self, actor, invitation, decision, *, advisor):
        row = self.authorized(actor, invitation, advisor=advisor)
        if row is None:
            raise InvitationError("INVITATION_NOT_FOUND")
        self.set_actor(actor)
        self.lock_parents(row[1], row[2])
        row = self.authorized(actor, invitation, advisor=advisor)
        if row is None:
            raise InvitationError("INVITATION_NOT_FOUND")
        if not advisor and row[4] != "leader":
            raise InvitationError("INVITATION_ACTION_FORBIDDEN")
        if row[3] != "pending":
            raise InvitationError("INVITATION_ALREADY_RESOLVED")
        self.resolve_function(invitation, decision)
        # Both projections re-authorize in their statement. The parent locks
        # prevent this workflow's membership/status changing before completion.
        history = self.advisor_history(actor) if advisor else self.team_history(actor)
        return next(item for item in history if item["id"] == str(invitation))
