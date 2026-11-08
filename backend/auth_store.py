"""PostgreSQL Auth storage with an explicit transaction per operation.

Runtime connections use the configured application identity; there is no
owner/admin fallback. Test fixtures can borrow a connection through
transaction_on(), which uses a savepoint when an outer rollback-only
transaction is already active.
"""

from contextlib import closing, contextmanager
import os
from pathlib import Path
import re

from dotenv import dotenv_values
import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

TEST_DB = "student_project_management_v1_test"
APP_ROLE = "project_app"


class StorageUnavailable(Exception):
    pass


class EmailConflict(Exception):
    pass


def _settings():
    config = dotenv_values(Path(__file__).with_name(".env"))

    def value(name, default=None):
        return os.environ.get(name, config.get(name, default))

    database_url = value("AUTH_DATABASE_URL")
    if database_url:
        try:
            connection = conninfo_to_dict(database_url)
        except psycopg.Error:
            raise StorageUnavailable() from None
        if connection.get("sslmode") not in {"require", "verify-ca", "verify-full"}:
            raise StorageUnavailable()
        database = value("AUTH_DB_NAME", connection.get("dbname"))
        user = value("AUTH_DB_USER", connection.get("user"))
    else:
        database = value("AUTH_DB_NAME", TEST_DB)
        user = value("AUTH_DB_USER", APP_ROLE)

    schema = value("AUTH_DB_SCHEMA", "auth")
    if not database or not user or not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", schema):
        raise StorageUnavailable()

    return {
        "database_url": database_url,
        "database": database,
        "user": user,
        "owner": value("AUTH_DB_OWNER_ROLE", "project_owner"),
        "schema": schema,
        "host": value("AUTH_DB_HOST", "localhost"),
        "port": value("AUTH_DB_PORT", "5432"),
        "password": value("AUTH_DB_PASSWORD"),
    }


def _auth_schema():
    return _settings()["schema"]


def assert_auth_connection(conn):
    settings = _settings()
    with conn.cursor() as cur:
        cur.execute("""SELECT current_database(), current_user, r.rolsuper,
            r.rolcreatedb, r.rolcreaterole, r.rolbypassrls, r.rolreplication,
            current_setting('session_replication_role'),
            pg_catalog.pg_has_role(current_user,%s,'MEMBER'),
            pg_catalog.pg_has_role(current_user,'pg_read_all_data','MEMBER'),
            pg_catalog.pg_has_role(current_user,'pg_write_all_data','MEMBER')
            FROM pg_catalog.pg_roles r WHERE r.rolname=current_user""", (settings["owner"],))
        if cur.fetchone() != (
            settings["database"], settings["user"], False, False, False, False,
            False, "origin", False, False, False,
        ):
            raise StorageUnavailable()


def open_auth_connection():
    try:
        settings = _settings()
        if settings["database_url"]:
            return psycopg.connect(
                settings["database_url"], autocommit=False, connect_timeout=8,
            )
        if not settings["password"]:
            raise StorageUnavailable()
        return psycopg.connect(
            host=settings["host"], port=int(settings["port"]),
            dbname=settings["database"], user=settings["user"],
            password=settings["password"], autocommit=False,
            connect_timeout=8,
        )
    except (psycopg.Error, ValueError, TypeError):
        raise StorageUnavailable() from None


@contextmanager
def transaction_on(conn):
    try:
        with conn.transaction():
            conn.execute("SET LOCAL statement_timeout = '15s'")
            conn.execute("SET LOCAL lock_timeout = '3s'")
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
            query = sql.SQL("SELECT {}.register_student(%s,%s,%s)").format(
                sql.Identifier(_auth_schema())
            )
            cur.execute(query, (full_name, email, encoded_hash))
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
            query = sql.SQL("SELECT user_id,password_hash FROM {}.lookup_credentials(%s)").format(
                sql.Identifier(_auth_schema())
            )
            cur.execute(query, (email,))
            return cur.fetchone()

    def create_session(self, user_id, digest, ttl_seconds):
        with self.conn.cursor() as cur:
            query = sql.SQL("""INSERT INTO {}.sessions(token_hash,user_id,expires_at)
                VALUES (%s,%s,clock_timestamp()+(%s * interval '1 second'))""").format(
                sql.Identifier(_auth_schema())
            )
            cur.execute(query,
                        (digest, user_id, ttl_seconds))

    def active_user(self, digest):
        with self.conn.cursor() as cur:
            # FK/cascade maintains credential existence. Do not directly SELECT
            # credentials here: project_app has no such table privilege.
            query = sql.SQL("""SELECT u.id,u.full_name,u.email,u.role
                FROM {}.sessions s JOIN public.users u ON u.id=s.user_id
                WHERE s.token_hash=%s AND s.expires_at>clock_timestamp()""").format(
                sql.Identifier(_auth_schema())
            )
            cur.execute(query, (digest,))
            return self.public_user(cur.fetchone())

    def delete_session(self, digest):
        with self.conn.cursor() as cur:
            query = sql.SQL("DELETE FROM {}.sessions WHERE token_hash=%s").format(
                sql.Identifier(_auth_schema())
            )
            cur.execute(query, (digest,))
