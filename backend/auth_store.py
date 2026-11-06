"""Test-database-only Auth storage with an explicit transaction per operation.

Runtime connections authenticate as project_app; there is no owner/admin
fallback. Test fixtures can borrow a connection through transaction_on(), which
uses a savepoint when an outer rollback-only transaction is already active.
"""

from contextlib import closing, contextmanager
import os
from pathlib import Path

from dotenv import dotenv_values
import psycopg

TEST_DB = "student_project_management_v1_test"
APP_ROLE = "project_app"


class StorageUnavailable(Exception):
    pass


class EmailConflict(Exception):
    pass


def assert_auth_connection(conn):
    with conn.cursor() as cur:
        cur.execute("""SELECT current_database(), current_user, r.rolsuper,
            r.rolcreatedb, r.rolcreaterole, r.rolbypassrls, r.rolreplication,
            current_setting('session_replication_role'),
            pg_catalog.pg_has_role(current_user,'project_owner','MEMBER'),
            pg_catalog.pg_has_role(current_user,'pg_read_all_data','MEMBER'),
            pg_catalog.pg_has_role(current_user,'pg_write_all_data','MEMBER')
            FROM pg_catalog.pg_roles r WHERE r.rolname=current_user""")
        if cur.fetchone() != (TEST_DB, APP_ROLE, False, False, False, False, False, "origin", False, False, False):
            raise StorageUnavailable()


def open_auth_connection():
    # Do not import backend.database: its DB_NAME may be the protected main DB.
    # Existing admin DB_USER/DB_PASSWORD/DB_NAME are deliberately not reused.
    config = dotenv_values(Path(__file__).with_name(".env"))
    password = os.environ.get("AUTH_DB_PASSWORD", config.get("AUTH_DB_PASSWORD"))
    if not password:
        raise StorageUnavailable()
    try:
        return psycopg.connect(
            host=os.environ.get("AUTH_DB_HOST", config.get("AUTH_DB_HOST") or "localhost"),
            port=int(os.environ.get("AUTH_DB_PORT", config.get("AUTH_DB_PORT") or "5432")),
            dbname=TEST_DB, user=APP_ROLE, password=password, autocommit=False,
            connect_timeout=8,
            options="-c statement_timeout=15000 -c lock_timeout=3000",
        )
    except (psycopg.Error, ValueError):
        raise StorageUnavailable() from None


@contextmanager
def transaction_on(conn):
    try:
        with conn.transaction():
            assert_auth_connection(conn)
            yield AuthRepository(conn)
    except psycopg.Error as exc:
        if exc.sqlstate == "23505" and exc.diag.constraint_name == "users_email_key":
            raise EmailConflict() from None
        raise StorageUnavailable() from None


@contextmanager
def auth_transaction():
    with closing(open_auth_connection()) as conn:
        with transaction_on(conn) as repository:
            yield repository
    # Successful runtime transactions finish here before the route responds.
    # Integration tests wrap transaction_on() in an outer transaction/ROLLBACK.


class AuthRepository:
    def __init__(self, conn):
        self.conn = conn

    def register(self, full_name, email, encoded_hash):
        with self.conn.cursor() as cur:
            cur.execute("SELECT auth.register_student(%s,%s,%s)", (full_name, email, encoded_hash))
            user_id = cur.fetchone()[0]
        return self.user(user_id)

    @staticmethod
    def public_user(row):
        if row is None:
            return None
        return {"id": str(row[0]), "full_name": row[1], "email": row[2], "role": row[3]}

    def user(self, user_id):
        with self.conn.cursor() as cur:
            cur.execute("SELECT id,full_name,email,role FROM public.users WHERE id=%s", (user_id,))
            user = self.public_user(cur.fetchone())
        if user is None:
            raise StorageUnavailable()
        return user

    def credentials(self, email):
        with self.conn.cursor() as cur:
            cur.execute("SELECT user_id,password_hash FROM auth.lookup_credentials(%s)", (email,))
            return cur.fetchone()

    def create_session(self, user_id, digest, ttl_seconds):
        with self.conn.cursor() as cur:
            cur.execute("""INSERT INTO auth.sessions(token_hash,user_id,expires_at)
                VALUES (%s,%s,clock_timestamp()+(%s * interval '1 second'))""",
                        (digest, user_id, ttl_seconds))

    def active_user(self, digest):
        with self.conn.cursor() as cur:
            # FK/cascade maintains credential existence. Do not directly SELECT
            # credentials here: project_app has no such table privilege.
            cur.execute("""SELECT u.id,u.full_name,u.email,u.role
                FROM auth.sessions s JOIN public.users u ON u.id=s.user_id
                WHERE s.token_hash=%s AND s.expires_at>clock_timestamp()""", (digest,))
            return self.public_user(cur.fetchone())

    def delete_session(self, digest):
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM auth.sessions WHERE token_hash=%s", (digest,))
