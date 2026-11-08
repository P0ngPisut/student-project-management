"""V1 project submission operations using the existing app role and DB guards."""

from contextlib import closing, contextmanager

import psycopg

from backend.auth_store import AuthRepository, StorageUnavailable, assert_auth_connection, open_auth_connection


class SubmissionError(Exception):
    def __init__(self, code: str):
        self.code = code


@contextmanager
def submission_transaction_on(conn):
    try:
        with conn.transaction():
            assert_auth_connection(conn)
            yield SubmissionRepository(conn)
    except psycopg.Error as exc:
        if (exc.sqlstate == "23505" and exc.diag.schema_name == "public"
                and exc.diag.table_name == "project_submissions"
                and exc.diag.constraint_name == "uq_submissions_one_pending"):
            raise SubmissionError("SUBMISSION_PENDING") from None
        raise StorageUnavailable() from None


@contextmanager
def submission_transaction():
    with closing(open_auth_connection()) as conn:
        with submission_transaction_on(conn) as repository:
            yield repository


class SubmissionRepository:
    def __init__(self, conn):
        self.conn = conn
        self.auth = AuthRepository(conn)

    @staticmethod
    def dto(row):
        return {
            "id": str(row[0]),
            "project_id": str(row[1]),
            "submitted_by": str(row[2]),
            "submitted_at": row[3],
            "snapshot_name": row[4],
            "snapshot_description": row[5],
            "status": row[6],
            "reviewed_by": str(row[7]) if row[7] is not None else None,
            "reviewed_at": row[8],
            "review_comment": row[9],
            "original_filename": row[10],
            "mime_type": row[11],
            "team_name": row[12],
        }

    @staticmethod
    def _row_query():
        return """SELECT s.id,s.project_id,s.submitted_by,s.submitted_at,s.snapshot_name,
                s.snapshot_description,s.status,s.reviewed_by,s.reviewed_at,s.review_comment,
                f.original_filename,f.mime_type,
                (SELECT t.name FROM public.projects p JOIN public.teams t ON t.id=p.team_id WHERE p.id=s.project_id)
            FROM public.project_submissions s
            JOIN public.project_submission_files f ON f.submission_id=s.id"""

    def set_actor(self, actor):
        self.conn.execute("SELECT pg_catalog.set_config('app.actor_user_id',%s,true)", (actor,))

    def _access(self, actor, role, submission):
        row = self.conn.execute("""SELECT s.project_id,s.status,
                EXISTS(SELECT 1 FROM public.team_members m JOIN public.projects p ON p.team_id=m.team_id
                    WHERE p.id=s.project_id AND m.user_id=%s),
                EXISTS(SELECT 1 FROM public.advisor_invitations i
                    WHERE i.project_id=s.project_id AND i.advisor_id=%s AND i.status='accepted'),
                EXISTS(SELECT 1 FROM public.committee_assignments a
                    WHERE a.project_id=s.project_id AND a.advisor_id=%s)
            FROM public.project_submissions s WHERE s.id=%s""",
            (actor, actor, actor, submission)).fetchone()
        if row is None:
            raise SubmissionError("SUBMISSION_NOT_FOUND")
        if role == "student" and row[2]:
            return row[0], row[1]
        if role == "advisor" and row[3]:
            return row[0], row[1]
        if role == "advisor" and row[4]:
            return row[0], row[1]
        if role == "coordinator" and row[1] == "approved":
            return row[0], row[1]
        raise SubmissionError("SUBMISSION_NOT_FOUND")

    def team_history(self, actor):
        context = self.conn.execute("""SELECT m.team_id,p.id FROM public.team_members m
            LEFT JOIN public.projects p ON p.team_id=m.team_id WHERE m.user_id=%s""", (actor,)).fetchone()
        if context is None:
            raise SubmissionError("TEAM_NOT_FOUND")
        if context[1] is None:
            raise SubmissionError("PROJECT_NOT_FOUND")
        rows = self.conn.execute(self._row_query() + """ JOIN public.projects p ON p.id=s.project_id
            JOIN public.team_members m ON m.team_id=p.team_id
            WHERE m.user_id=%s ORDER BY s.id DESC""", (actor,)).fetchall()
        return [self.dto(row) for row in rows]

    def advisor_inbox(self, actor):
        rows = self.conn.execute(self._row_query() + """ JOIN public.advisor_invitations i ON i.project_id=s.project_id
            WHERE i.advisor_id=%s AND i.status='accepted' ORDER BY s.id DESC""", (actor,)).fetchall()
        return [self.dto(row) for row in rows]

    def eligibility(self, actor):
        context = self.conn.execute("""SELECT m.team_id,m.role,p.id FROM public.team_members m
            LEFT JOIN public.projects p ON p.team_id=m.team_id WHERE m.user_id=%s""", (actor,)).fetchone()
        if context is None:
            raise SubmissionError("TEAM_NOT_FOUND")
        if context[2] is None:
            raise SubmissionError("PROJECT_NOT_FOUND")
        if context[1] != "leader":
            return False
        if not self.conn.execute("""SELECT EXISTS(SELECT 1 FROM public.advisor_invitations
            WHERE project_id=%s AND status='accepted')""", (context[2],)).fetchone()[0]:
            return False
        latest = self.conn.execute("""SELECT id,status FROM public.project_submissions
            WHERE project_id=%s ORDER BY id DESC LIMIT 1""", (context[2],)).fetchone()
        if latest is None or latest[1] == "revision_requested":
            return True
        if latest[1] == "pending_review":
            return False
        return self.conn.execute("SELECT public.v1_topic_decision(%s)", (latest[0],)).fetchone()[0] == "revision_requested"

    def detail(self, actor, role, submission):
        self._access(actor, role, submission)
        row = self.conn.execute(self._row_query() + " WHERE s.id=%s", (submission,)).fetchone()
        if row is None:
            raise SubmissionError("SUBMISSION_NOT_FOUND")
        return self.dto(row)

    def file(self, actor, role, submission):
        self._access(actor, role, submission)
        row = self.conn.execute("""SELECT f.file_data,f.original_filename,f.mime_type
            FROM public.project_submission_files f WHERE f.submission_id=%s""", (submission,)).fetchone()
        if row is None:
            raise StorageUnavailable()
        return row

    def _team_context(self, actor):
        return self.conn.execute("""SELECT m.team_id,m.role,p.id
            FROM public.team_members m LEFT JOIN public.projects p ON p.team_id=m.team_id
            WHERE m.user_id=%s""", (actor,)).fetchone()

    @staticmethod
    def _require_leader(context):
        if context is None:
            raise SubmissionError("TEAM_NOT_FOUND")
        if context[2] is None:
            raise SubmissionError("PROJECT_NOT_FOUND")
        if context[1] != "leader":
            raise SubmissionError("SUBMISSION_ACTION_FORBIDDEN")

    def submit(self, actor, filename, mime_type, data):
        context = self._team_context(actor)
        self._require_leader(context)
        team_id, _, project_id = context
        self.set_actor(actor)
        self.conn.execute("SELECT public.v1_lock_team(%s)", (team_id,))
        self.conn.execute("SELECT public.v1_lock_project(%s)", (project_id,))
        context = self._team_context(actor)
        self._require_leader(context)
        if context[0] != team_id or context[2] != project_id:
            raise SubmissionError("PROJECT_NOT_FOUND")
        if not self.conn.execute("""SELECT EXISTS(SELECT 1 FROM public.advisor_invitations
            WHERE project_id=%s AND status='accepted')""", (project_id,)).fetchone()[0]:
            raise SubmissionError("ACCEPTED_ADVISOR_REQUIRED")

        latest = self.conn.execute("""SELECT id,status FROM public.project_submissions
            WHERE project_id=%s ORDER BY id DESC LIMIT 1""", (project_id,)).fetchone()
        if latest is not None:
            if latest[1] == "pending_review":
                raise SubmissionError("SUBMISSION_PENDING")
            if latest[1] == "approved":
                decision = self.conn.execute("SELECT public.v1_topic_decision(%s)", (latest[0],)).fetchone()[0]
                if decision != "revision_requested":
                    raise SubmissionError("SUBMISSION_PHASE_CLOSED")

        self.conn.execute("SET CONSTRAINTS public.c_submission_requires_file DEFERRED")
        submission_id = self.conn.execute("""INSERT INTO public.project_submissions(project_id,submitted_by)
            VALUES (%s,%s) RETURNING id""", (project_id, actor)).fetchone()[0]
        self.conn.execute("""INSERT INTO public.project_submission_files
            (submission_id,file_data,original_filename,mime_type) VALUES (%s,%s,%s,%s)""",
            (submission_id, data, filename, mime_type))
        self.conn.execute("SET CONSTRAINTS public.c_submission_requires_file IMMEDIATE")
        row = self.conn.execute(self._row_query() + " WHERE s.id=%s", (submission_id,)).fetchone()
        if row is None:
            raise StorageUnavailable()
        return self.dto(row)

    def review(self, actor, submission, decision, comment):
        row = self.conn.execute("""SELECT s.project_id,s.status,
                EXISTS(SELECT 1 FROM public.advisor_invitations i
                    WHERE i.project_id=s.project_id AND i.advisor_id=%s AND i.status='accepted')
            FROM public.project_submissions s WHERE s.id=%s""", (actor, submission)).fetchone()
        if row is None or not row[2]:
            raise SubmissionError("SUBMISSION_NOT_FOUND")
        self.set_actor(actor)
        self.conn.execute("SELECT public.v1_lock_project(%s)", (row[0],))
        current = self.conn.execute("""SELECT s.project_id,s.status,
                EXISTS(SELECT 1 FROM public.advisor_invitations i
                    WHERE i.project_id=s.project_id AND i.advisor_id=%s AND i.status='accepted')
            FROM public.project_submissions s WHERE s.id=%s""", (actor, submission)).fetchone()
        if current is None or not current[2]:
            raise SubmissionError("SUBMISSION_NOT_FOUND")
        if current[1] != "pending_review":
            raise SubmissionError("SUBMISSION_ALREADY_REVIEWED")
        self.conn.execute("SELECT public.v1_review_submission(%s,%s,%s)", (submission, decision, comment))
        result = self.conn.execute(self._row_query() + " WHERE s.id=%s", (submission,)).fetchone()
        if result is None:
            raise StorageUnavailable()
        return self.dto(result)
