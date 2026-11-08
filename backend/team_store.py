"""Atomic Team creation using only the existing V1 application privileges."""

from contextlib import closing, contextmanager

import psycopg

from backend.auth_store import AuthRepository, StorageUnavailable, assert_auth_connection, open_auth_connection


class AlreadyInTeam(Exception):
    pass


class TeamMemberError(Exception):
    def __init__(self, code):
        self.code = code


@contextmanager
def team_transaction_on(conn):
    try:
        with conn.transaction():
            assert_auth_connection(conn)
            yield TeamRepository(conn)
    except psycopg.Error as exc:
        if (exc.sqlstate == "23505" and exc.diag.schema_name == "public"
                and exc.diag.table_name == "team_members"
                and exc.diag.constraint_name == "team_members_user_id_key"):
            raise AlreadyInTeam() from None
        raise StorageUnavailable() from None


@contextmanager
def team_transaction():
    with closing(open_auth_connection()) as conn:
        with team_transaction_on(conn) as repository:
            yield repository


class TeamRepository:
    def __init__(self, conn):
        self.conn = conn
        self.auth = AuthRepository(conn)

    def membership_exists(self, actor):
        return self.conn.execute("SELECT EXISTS(SELECT 1 FROM public.team_members WHERE user_id=%s)",
                                 (actor,)).fetchone()[0]

    def current_team(self, actor):
        # One statement scopes the result to the verified actor's membership.
        # HTTP status/response mapping belongs to the read endpoint contract.
        return self.conn.execute("""SELECT t.id,t.name,t.description,m.id,m.role
            FROM public.team_members m JOIN public.teams t ON t.id=m.team_id
            WHERE m.user_id=%s""", (actor,)).fetchone()

    @staticmethod
    def public_member(row):
        return {"id": str(row[0]), "user_id": str(row[1]), "full_name": row[2], "role": row[3]}

    def current_members(self, actor):
        # Membership authorization and list projection share one snapshot.
        rows = self.conn.execute("""SELECT m.id,m.user_id,u.full_name,m.role
            FROM public.team_members own
            JOIN public.team_members m ON m.team_id=own.team_id
            JOIN public.users u ON u.id=m.user_id
            WHERE own.user_id=%s
            ORDER BY CASE m.role WHEN 'leader' THEN 0 ELSE 1 END,u.full_name ASC,m.id ASC""",
            (actor,)).fetchall()
        return [self.public_member(row) for row in rows]

    def insert_member(self, team_id, target):
        return self.conn.execute("""INSERT INTO public.team_members(team_id,user_id,role)
            VALUES (%s,%s,'member') RETURNING id,user_id,role""", (team_id, target)).fetchone()

    def add_member(self, actor, email):
        own = self.current_team(actor)
        if own is None:
            raise TeamMemberError("TEAM_NOT_FOUND")
        team_id = own[0]
        self.conn.execute("SELECT pg_catalog.set_config('app.actor_user_id',%s,true)", (actor,))
        # Same order as V1 transfer/exit/metadata operations: team -> project.
        # Recheck authority after any lock wait before inspecting the target.
        self.lock_parent(team_id)
        own = self.current_team(actor)
        if own is None or own[0] != team_id:
            raise TeamMemberError("TEAM_NOT_FOUND")
        if own[4] != "leader":
            raise TeamMemberError("TEAM_MEMBER_ADDITION_FORBIDDEN")
        project = self.conn.execute("SELECT id FROM public.projects WHERE team_id=%s", (team_id,)).fetchone()
        if project is not None:
            self.conn.execute("SELECT public.v1_lock_project(%s)", (project[0],))
            if not self.conn.execute("SELECT public.v1_topic_metadata_editable(%s)", (project[0],)).fetchone()[0]:
                raise TeamMemberError("MEMBER_ADDITION_LOCKED")
        target = self.conn.execute("SELECT id,full_name FROM public.users WHERE email=lower(%s) AND role='student'", (email,)).fetchone()
        if target is None:
            raise TeamMemberError("MEMBER_NOT_FOUND")
        if self.membership_exists(target[0]):
            raise TeamMemberError("MEMBER_UNAVAILABLE")
        member = self.insert_member(team_id, target[0])
        self.conn.execute("""SET CONSTRAINTS public.c_team_created_has_leader,
            public.c_team_member_cardinality IMMEDIATE""")
        return self.public_member((member[0], member[1], target[1], member[2]))

    def insert_team(self, name, description):
        return self.conn.execute("""INSERT INTO public.teams(name,description)
            VALUES (%s,%s) RETURNING id,name,description""", (name, description)).fetchone()

    def lock_parent(self, team_id):
        self.conn.execute("SELECT public.v1_lock_team(%s)", (team_id,))

    def insert_leader(self, team_id, actor):
        return self.conn.execute("""INSERT INTO public.team_members(team_id,user_id,role)
            VALUES (%s,%s,'leader') RETURNING id,user_id,role""", (team_id, actor)).fetchone()

    def create(self, name, description, actor):
        if self.membership_exists(actor):
            raise AlreadyInTeam()
        # Own the timing of these two deferred checks even when the caller's
        # transaction previously forced them IMMEDIATE. Validate below before
        # returning; BEFORE guards/CHECK/UNIQUE/FK remain enabled throughout.
        self.conn.execute("""SET CONSTRAINTS public.c_team_created_has_leader,
            public.c_team_member_cardinality DEFERRED""")
        self.conn.execute("SELECT pg_catalog.set_config('app.actor_user_id',%s,true)", (actor,))
        team = self.insert_team(name, description)
        self.lock_parent(team[0])
        member = self.insert_leader(team[0], actor)
        self.conn.execute("""SET CONSTRAINTS public.c_team_created_has_leader,
            public.c_team_member_cardinality IMMEDIATE""")
        return {"id": str(team[0]), "name": team[1], "description": team[2],
                "members": [{"id": str(member[0]), "user_id": str(member[1]), "role": member[2]}]}
