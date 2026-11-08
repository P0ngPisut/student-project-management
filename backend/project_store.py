"""Current-team Project access using the existing V1 application privileges."""

from contextlib import closing, contextmanager

import psycopg

from backend.auth_store import AuthRepository, StorageUnavailable, assert_auth_connection, open_auth_connection


class ProjectError(Exception):
    def __init__(self, code):
        self.code = code


@contextmanager
def project_transaction_on(conn):
    try:
        with conn.transaction():
            assert_auth_connection(conn)
            yield ProjectRepository(conn)
    except psycopg.Error as exc:
        if (exc.sqlstate == "23505" and exc.diag.schema_name == "public"
                and exc.diag.table_name == "projects"
                and exc.diag.constraint_name == "projects_team_id_key"):
            raise ProjectError("PROJECT_ALREADY_EXISTS") from None
        raise StorageUnavailable() from None


@contextmanager
def project_transaction():
    with closing(open_auth_connection()) as conn:
        with project_transaction_on(conn) as repository:
            yield repository


class ProjectRepository:
    def __init__(self, conn):
        self.conn = conn
        self.auth = AuthRepository(conn)

    @staticmethod
    def public_project(row):
        return {"id": str(row[0]), "name": row[1], "description": row[2],
                "team_id": str(row[3]), "created_by": str(row[4])}

    def own_team(self, actor):
        return self.conn.execute("SELECT team_id,role FROM public.team_members WHERE user_id=%s", (actor,)).fetchone()

    def current(self, actor):
        # One snapshot distinguishes no team from no Project without allowing
        # a request to choose a different team's resource.
        row = self.conn.execute("""SELECT own.team_id,p.id,p.name,p.description,p.created_by
            FROM public.team_members own LEFT JOIN public.projects p ON p.team_id=own.team_id
            WHERE own.user_id=%s""", (actor,)).fetchone()
        if row is None:
            raise ProjectError("TEAM_NOT_FOUND")
        if row[1] is None:
            raise ProjectError("PROJECT_NOT_FOUND")
        return self.public_project((row[1], row[2], row[3], row[0], row[4]))

    def exists(self, team_id):
        return self.conn.execute("SELECT EXISTS(SELECT 1 FROM public.projects WHERE team_id=%s)", (team_id,)).fetchone()[0]

    def insert(self, name, description, team_id, actor):
        return self.conn.execute("""INSERT INTO public.projects(name,description,team_id,created_by)
            VALUES (%s,%s,%s,%s) RETURNING id,name,description,team_id,created_by""",
            (name, description, team_id, actor)).fetchone()

    def create(self, name, description, actor):
        own = self.own_team(actor)
        if own is None:
            raise ProjectError("TEAM_NOT_FOUND")
        team_id = own[0]
        self.conn.execute("SELECT pg_catalog.set_config('app.actor_user_id',%s,true)", (actor,))
        self.conn.execute("SELECT public.v1_lock_team(%s)", (team_id,))
        own = self.own_team(actor)
        if own is None or own[0] != team_id:
            raise ProjectError("TEAM_NOT_FOUND")
        if own[1] != "leader":
            raise ProjectError("PROJECT_CREATION_FORBIDDEN")
        if self.exists(team_id):
            raise ProjectError("PROJECT_ALREADY_EXISTS")
        row = self.insert(name, description, team_id, actor)
        # Project has immediate CHECK/UNIQUE/FK/BEFORE guards. Force the team's
        # existing deferred cardinality checks too before reporting success.
        self.conn.execute("""SET CONSTRAINTS public.c_team_created_has_leader,
            public.c_team_member_cardinality IMMEDIATE""")
        return self.public_project(row)
