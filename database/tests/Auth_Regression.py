"""Rehearse reviewed Auth storage/RBAC only in the test DB, then ROLLBACK.

Run from the repository root with backend/.venv/Scripts/python.exe -B -m
database.tests.Auth_Regression. No main DB connection, COMMIT, role creation,
V1 patches, or additional privilege grants are performed. Existing installed
Auth is verified before testing; otherwise it is created temporarily. Sequence values may
advance despite ROLLBACK. SQL storage fixtures do not test password hashing,
HTTP login, cookies, or backend session authorization.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import secrets
from uuid import uuid4

from dotenv import dotenv_values
import psycopg
from psycopg import sql

BASE = Path(__file__).resolve().parents[2]
TEST_DB = "student_project_management_v1_test"
OWNER = "project_owner"
APP = "project_app"
REVIEW_HASHES = {
    "001_auth_storage_review.sql": "6a3589160160dd73f6a0c6532e39594ecbd9324caf5190e28d9840985039fe9e",
    "002_auth_rbac_review.sql": "818f6e78d26ae78a538cd5440d35fd6ebe8e3b0addcedf5dd02c65d5036ae8f7",
}
# Synthetic encoded storage fixture, never a user's password or a login proof.
HASH_FIXTURE = (
    "$argon2id$v=19$m=19456,t=2,p=1$c3Btcy1hdXRoLXJldmlldw$"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
)


def report(case, result, **details):
    print(json.dumps({"case": case, "result": result, **details}, default=str))


def require(condition):
    if not condition:
        raise RuntimeError("Auth regression assertion failed")


def guard(cur, role):
    cur.execute("""SELECT current_database(), current_user,
        (SELECT rolsuper FROM pg_catalog.pg_roles WHERE rolname=current_user),
        current_setting('session_replication_role')""")
    require(cur.fetchone() == (TEST_DB, role, False, "origin"))


def switch(cur, role):
    cur.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
    guard(cur, role)


def snapshot(cur):
    """Definitions, owners, ACLs, structure and row counts; no sequence values."""
    guard(cur, OWNER)
    queries = (
        """SELECT nspname, pg_get_userbyid(nspowner), nspacl::text
           FROM pg_catalog.pg_namespace WHERE nspname IN ('public','auth')
           ORDER BY 1""",
        """SELECT n.nspname, c.relname, c.relkind, pg_get_userbyid(c.relowner),
                  c.relacl::text FROM pg_catalog.pg_class c
           JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
           WHERE n.nspname IN ('public','auth') ORDER BY 1,2""",
        """SELECT p.oid::regprocedure::text, pg_get_userbyid(p.proowner),
                  pg_get_functiondef(p.oid), p.proacl::text
           FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
           WHERE n.nspname IN ('public','auth') AND p.prokind='f' ORDER BY 1""",
        """SELECT n.nspname, c.relname, a.attnum, a.attname,
                  format_type(a.atttypid,a.atttypmod), a.attnotnull, a.attacl::text,
                  pg_get_expr(d.adbin,d.adrelid)
           FROM pg_catalog.pg_attribute a JOIN pg_catalog.pg_class c ON c.oid=a.attrelid
           JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
           LEFT JOIN pg_catalog.pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
           WHERE n.nspname IN ('public','auth') AND c.relkind='r'
             AND a.attnum>0 AND NOT a.attisdropped ORDER BY 1,2,3""",
        """SELECT n.nspname, c.relname, x.conname, pg_get_constraintdef(x.oid)
           FROM pg_catalog.pg_constraint x JOIN pg_catalog.pg_class c ON c.oid=x.conrelid
           JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
           WHERE n.nspname IN ('public','auth') ORDER BY 1,2,3""",
        """SELECT n.nspname, c.relname, t.tgname, pg_get_triggerdef(t.oid), t.tgenabled
           FROM pg_catalog.pg_trigger t JOIN pg_catalog.pg_class c ON c.oid=t.tgrelid
           JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
           WHERE n.nspname IN ('public','auth') ORDER BY 1,2,3""",
        """SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolbypassrls, rolcanlogin
           FROM pg_catalog.pg_roles WHERE rolname IN ('project_owner','project_app')
           ORDER BY 1""",
        "SELECT datacl::text FROM pg_catalog.pg_database WHERE datname=current_database()",
    )
    metadata = []
    for query in queries:
        cur.execute(query)
        metadata.append(cur.fetchall())
    cur.execute("""SELECT n.nspname,c.relname FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname IN ('public','auth') AND c.relkind='r' ORDER BY 1,2""")
    counts = {}
    for schema, table in cur.fetchall():
        cur.execute(sql.SQL("SELECT count(*) FROM {}.{}").format(
            sql.Identifier(schema), sql.Identifier(table)))
        counts[schema + "." + table] = cur.fetchone()[0]
    digest = hashlib.sha256(json.dumps(metadata, default=str).encode()).hexdigest()
    return digest, counts


def render_review():
    """Expand the single approved include; outer transaction belongs to harness."""
    bodies = {}
    for name, expected in REVIEW_HASHES.items():
        data = (BASE / "database/auth" / name).read_bytes()
        require(hashlib.sha256(data).hexdigest() == expected)
        kept = []
        for line in data.decode("utf-8-sig").splitlines():
            if line.lstrip().startswith("\\"):
                require(line in ("\\set ON_ERROR_STOP on", "\\ir 002_auth_rbac_review.sql"))
                if line.startswith("\\ir"):
                    kept.append("-- AUTH_REVIEW_INCLUDE")
            else:
                kept.append(line)
        bodies[name] = "\n".join(kept)
    storage = bodies["001_auth_storage_review.sql"]
    for boundary in ("BEGIN", "ROLLBACK"):
        storage, count = re.subn(rf"(?m)^{boundary};[ \t]*$", "", storage)
        require(count == 1)
    require(storage.count("-- AUTH_REVIEW_INCLUDE") == 1)
    combined = storage.replace("-- AUTH_REVIEW_INCLUDE", bodies["002_auth_rbac_review.sql"])
    require(re.search(r"\bCOMMIT\b", combined, re.IGNORECASE) is None)
    return combined


def validate_installed_auth(cur):
    """Reject an unexpected Auth baseline instead of replacing/dropping it."""
    guard(cur, OWNER)
    render_review()  # Check reviewed source pins even when no DDL is needed.
    cur.execute("SELECT pg_get_userbyid(nspowner) FROM pg_catalog.pg_namespace WHERE nspname='auth'")
    require(cur.fetchone() == (OWNER,))
    cur.execute("""SELECT c.relname, pg_get_userbyid(c.relowner)
        FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='auth' AND c.relkind='r' ORDER BY 1""")
    require(cur.fetchall() == [("credentials", OWNER), ("sessions", OWNER)])
    cur.execute("""SELECT c.relname,a.attname,format_type(a.atttypid,a.atttypmod),a.attnotnull
        FROM pg_catalog.pg_attribute a JOIN pg_catalog.pg_class c ON c.oid=a.attrelid
        JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='auth' AND c.relkind='r' AND a.attnum>0 AND NOT a.attisdropped
        ORDER BY c.relname,a.attnum""")
    require(cur.fetchall() == [
        ("credentials", "user_id", "bigint", True),
        ("credentials", "password_hash", "text", True),
        ("sessions", "token_hash", "bytea", True),
        ("sessions", "user_id", "bigint", True),
        ("sessions", "created_at", "timestamp with time zone", True),
        ("sessions", "expires_at", "timestamp with time zone", True),
    ])
    source = (BASE / "database/auth/002_auth_rbac_review.sql").read_text(encoding="utf-8-sig")
    expected_bodies = dict(re.findall(
        r"(?s)CREATE FUNCTION auth\.(\w+)\(.*?AS \$function\$(.*?)\$function\$;", source))
    cur.execute("""SELECT p.proname,p.prosrc,p.prosecdef,p.proconfig,
        pg_get_userbyid(p.proowner) FROM pg_catalog.pg_proc p
        JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='auth'""")
    functions = cur.fetchall()
    require(len(functions) == 2 and set(expected_bodies) == {row[0] for row in functions})
    for name, body, definer, settings, owner in functions:
        require(body.strip() == expected_bodies[name].strip() and definer
                and settings == ["search_path=pg_catalog, pg_temp"] and owner == OWNER)
    cur.execute("""SELECT count(*) FROM pg_catalog.pg_trigger t
        JOIN pg_catalog.pg_class c ON c.oid=t.tgrelid
        JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='auth' AND NOT t.tgisinternal""")
    require(cur.fetchone()[0] == 0)
    # PostgreSQL 18 also exposes NOT NULL constraints (contype='n'). Those are
    # verified through attnotnull above, independently of generated names.
    cur.execute("""SELECT conname,contype::text FROM pg_catalog.pg_constraint
        WHERE conrelid IN ('auth.credentials'::regclass,'auth.sessions'::regclass)
          AND contype<>'n'
        ORDER BY conname""")
    require(cur.fetchall() == sorted([
        ("credentials_pkey", "p"), ("credentials_user_id_fkey", "f"),
        ("ck_auth_password_hash", "c"), ("sessions_pkey", "p"),
        ("sessions_user_id_fkey", "f"), ("ck_auth_session_token_hash", "c"),
        ("ck_auth_session_lifetime", "c"),
    ]))
    postflight = re.search(r"(?s)DO \$postflight\$.*?\$postflight\$;", source)
    require(postflight is not None)
    cur.execute(postflight[0], prepare=False)


def prepare_auth_for_tests(cur):
    """Return baseline mode. Neither mode commits or repairs existing objects."""
    guard(cur, OWNER)
    cur.execute("SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_namespace WHERE nspname='auth')")
    if cur.fetchone()[0]:
        validate_installed_auth(cur)
        return "installed"
    cur.execute(render_review(), prepare=False)
    validate_installed_auth(cur)
    return "temporary"


class Checks:
    def __init__(self, cur):
        self.cur = cur
        self.passed = 0
        self.case = "START"

    def begin(self, case, role=APP):
        self.case = case
        guard(self.cur, role)

    def ok(self, **details):
        self.passed += 1
        report(self.case, "PASS", **details)

    def scalar(self, query, params=None):
        self.cur.execute(query, params)
        return self.cur.fetchone()[0]

    def error(self, case, query, params, state, *, constraint=None, column=None, role=APP):
        self.begin(case, role)
        self.cur.execute("SAVEPOINT auth_expected_error")
        actual = None
        try:
            self.cur.execute(query, params)
        except psycopg.Error as exc:
            actual = (exc.sqlstate, exc.diag.constraint_name, exc.diag.column_name)
        finally:
            self.cur.execute("ROLLBACK TO SAVEPOINT auth_expected_error")
            self.cur.execute("RELEASE SAVEPOINT auth_expected_error")
        matched = (actual is not None and actual[0] == state
                   and (constraint is None or actual[1] == constraint)
                   and (column is None or actual[2] == column))
        if not matched:
            report(case, "MISMATCH", expected_sqlstate=state,
                   expected_constraint=constraint, expected_column=column,
                   actual_sqlstate=actual[0] if actual else None,
                   actual_constraint=actual[1] if actual else None,
                   actual_column=actual[2] if actual else None)
        require(matched)
        self.ok(sqlstate=actual[0], constraint=actual[1])


def run_cases(checks):
    cur = checks.cur
    checks.begin("AUTH_STRUCTURE_AND_FUNCTION_SECURITY", OWNER)
    require(checks.scalar("SELECT count(*) FROM information_schema.columns WHERE table_schema='auth'") == 6)
    require(checks.scalar("""SELECT count(*) FROM pg_catalog.pg_proc p
        JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname='auth' AND p.prosecdef
          AND pg_get_userbyid(p.proowner)='project_owner'
          AND p.proconfig @> ARRAY['search_path=pg_catalog, pg_temp']""") == 2)
    require(checks.scalar("""SELECT count(*) FROM pg_catalog.pg_proc p
        JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace,
        LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a
        WHERE n.nspname='auth' AND a.grantee=0 AND a.privilege_type='EXECUTE'""") == 0)
    checks.ok()

    token = uuid4().hex
    fixture_emails = {}
    for role in ("advisor", "coordinator"):
        fixture_emails[role] = "auth-" + token + "-" + role + "@example.test"
        cur.execute("INSERT INTO public.users(full_name,email,role) VALUES (%s,%s,%s)",
                    ("Auth Review " + role, fixture_emails[role], role))
    switch(cur, APP)
    checks.begin("REGISTER_STUDENT_NORMALIZATION_AND_ROLE")
    email = "auth-" + token + "-student@example.test"
    user_id = checks.scalar("SELECT auth.register_student(%s,%s,%s)",
                           ("  Auth Review Student  ", "  " + email.upper() + "  ", HASH_FIXTURE))
    cur.execute("SELECT full_name,email,role FROM public.users WHERE id=%s", (user_id,))
    require(cur.fetchone() == ("Auth Review Student", email, "student"))
    checks.ok()

    checks.begin("LOOKUP_CREDENTIALS_NORMALIZED_EMAIL")
    cur.execute("SELECT * FROM auth.lookup_credentials(%s)", ("  " + email.upper() + "  ",))
    require(cur.fetchone() == (user_id, HASH_FIXTURE))
    checks.ok()
    checks.begin("LOOKUP_UNKNOWN_EMAIL_EMPTY_RESULT")
    cur.execute("SELECT * FROM auth.lookup_credentials(%s)", ("missing-" + email,))
    require(cur.fetchall() == [])
    checks.ok()

    checks.error("DUPLICATE_EMAIL_NO_ACCOUNT_TAKEOVER", "SELECT auth.register_student(%s,%s,%s)",
                 ("Duplicate", email.upper(), HASH_FIXTURE), "23505", constraint="users_email_key")
    for role, existing_email in fixture_emails.items():
        checks.error("EXISTING_" + role.upper() + "_EMAIL_NOT_LINKED", "SELECT auth.register_student(%s,%s,%s)",
                     ("Existing Account", existing_email, HASH_FIXTURE), "23505", constraint="users_email_key")
    checks.error("REGISTER_CANNOT_ACCEPT_ROLE_ARGUMENT", "SELECT auth.register_student(%s,%s,%s,%s)",
                 ("Role Spoof", "role-" + email, HASH_FIXTURE, "advisor"), "42883")
    checks.error("EMPTY_NAME_REJECTED", "SELECT auth.register_student(%s,%s,%s)",
                 (" \t ", "blank-" + email, HASH_FIXTURE), "23514", constraint="ck_users_full_name")
    invalid_email = "invalid-hash-" + email
    checks.error("PLAINTEXT_HASH_REJECTED", "SELECT auth.register_student(%s,%s,%s)",
                 ("Invalid Hash", invalid_email, "synthetic-plaintext-fixture"), "23514", constraint="ck_auth_password_hash")
    checks.begin("REGISTRATION_HASH_FAILURE_ROLLS_BACK_USER")
    require(checks.scalar("SELECT count(*) FROM public.users WHERE email=%s", (invalid_email,)) == 0)
    checks.ok()
    null_email = "null-hash-" + email
    checks.error("NULL_HASH_REJECTED", "SELECT auth.register_student(%s,%s,%s)",
                 ("Null Hash", null_email, None), "23502", column="password_hash")
    checks.begin("REGISTRATION_NULL_HASH_ROLLS_BACK_USER")
    require(checks.scalar("SELECT count(*) FROM public.users WHERE email=%s", (null_email,)) == 0)
    checks.ok()

    denied = (
        ("DIRECT_USERS_INSERT_DENIED", "INSERT INTO public.users(full_name,email,role) VALUES ('Denied',%s,'student')", ("direct-" + email,)),
        ("DIRECT_USERS_UPDATE_DENIED", "UPDATE public.users SET full_name='Denied' WHERE id=%s", (user_id,)),
        ("DIRECT_USERS_DELETE_DENIED", "DELETE FROM public.users WHERE id=%s", (user_id,)),
        ("DIRECT_CREDENTIALS_SELECT_DENIED", "SELECT password_hash FROM auth.credentials WHERE user_id=%s", (user_id,)),
        ("DIRECT_CREDENTIALS_INSERT_DENIED", "INSERT INTO auth.credentials VALUES (%s,%s)", (user_id, HASH_FIXTURE)),
        ("DIRECT_CREDENTIALS_UPDATE_DENIED", "UPDATE auth.credentials SET password_hash=%s WHERE user_id=%s", (HASH_FIXTURE, user_id)),
        ("DIRECT_CREDENTIALS_DELETE_DENIED", "DELETE FROM auth.credentials WHERE user_id=%s", (user_id,)),
        ("AUTH_SCHEMA_CREATE_DENIED", "CREATE TABLE auth.unauthorized_table(id bigint)", None),
        ("SESSION_UPDATE_DENIED", "UPDATE auth.sessions SET expires_at=clock_timestamp()+interval '1 hour'", None),
        ("SESSION_TRUNCATE_DENIED", "TRUNCATE auth.sessions", None),
        ("SESSION_CREATED_AT_OVERRIDE_DENIED", "INSERT INTO auth.sessions(token_hash,user_id,created_at,expires_at) VALUES (%s,%s,clock_timestamp(),clock_timestamp()+interval '1 hour')", (b'c' * 32, user_id)),
    )
    for case, query, params in denied:
        checks.error(case, query, params, "42501")

    digest = hashlib.sha256(secrets.token_bytes(32)).digest()
    checks.begin("SESSION_INSERT_AND_SERVER_TIMESTAMP")
    cur.execute("""INSERT INTO auth.sessions(token_hash,user_id,expires_at)
        VALUES (%s,%s,clock_timestamp()+interval '5 minutes')
        RETURNING created_at,expires_at,clock_timestamp()""", (digest, user_id))
    created, expires, server_now = cur.fetchone()
    require(created <= server_now < expires)
    require(checks.scalar("SELECT count(*) FROM auth.sessions WHERE token_hash=%s AND expires_at>clock_timestamp()", (digest,)) == 1)
    checks.ok()
    insert_session = "INSERT INTO auth.sessions(token_hash,user_id,expires_at) VALUES (%s,%s,clock_timestamp()+interval '5 minutes')"
    checks.error("SESSION_DUPLICATE_TOKEN_HASH", insert_session, (digest, user_id), "23505", constraint="sessions_pkey")
    for length in (31, 33):
        checks.error("SESSION_HASH_LENGTH_" + str(length), insert_session, (b'x' * length, user_id), "23514", constraint="ck_auth_session_token_hash")
    checks.error("SESSION_UNKNOWN_USER", insert_session, (b'u' * 32, -1), "23503", constraint="sessions_user_id_fkey")
    checks.error("SESSION_NULL_TOKEN_HASH", insert_session, (None, user_id), "23502", column="token_hash")
    checks.error("SESSION_NULL_USER", insert_session, (b'n' * 32, None), "23502", column="user_id")
    checks.error("SESSION_NULL_EXPIRY", "INSERT INTO auth.sessions(token_hash,user_id,expires_at) VALUES (%s,%s,NULL)",
                 (b'e' * 32, user_id), "23502", column="expires_at")
    checks.error("SESSION_EXPIRY_BEFORE_CREATION", "INSERT INTO auth.sessions(token_hash,user_id,expires_at) VALUES (%s,%s,clock_timestamp()-interval '1 minute')",
                 (b'p' * 32, user_id), "23514", constraint="ck_auth_session_lifetime")

    checks.begin("SESSION_DELETE_DATABASE_ONLY")
    cur.execute("DELETE FROM auth.sessions WHERE token_hash=%s", (digest,))
    require(cur.rowcount == 1)
    require(checks.scalar("SELECT count(*) FROM auth.sessions WHERE token_hash=%s", (digest,)) == 0)
    checks.ok()

    switch(cur, OWNER)
    # PostgreSQL 18.6 reports restrict_violation for this ON DELETE RESTRICT.
    checks.error("CREDENTIALS_RESTRICT_USER_DELETE", "DELETE FROM public.users WHERE id=%s", (user_id,),
                 "23001", constraint="credentials_user_id_fkey", role=OWNER)
    checks.begin("EXPIRED_SESSION_REQUIRES_BACKEND_FILTER", OWNER)
    cur.execute("""INSERT INTO auth.sessions(token_hash,user_id,created_at,expires_at)
        VALUES (%s,%s,clock_timestamp()-interval '2 hours',clock_timestamp()-interval '1 hour')""", (digest, user_id))
    switch(cur, APP)
    require(checks.scalar("SELECT count(*) FROM auth.sessions WHERE token_hash=%s", (digest,)) == 1)
    require(checks.scalar("SELECT count(*) FROM auth.sessions WHERE token_hash=%s AND expires_at>clock_timestamp()", (digest,)) == 0)
    checks.ok(backend_expiry_filter_still_required=True)
    switch(cur, OWNER)
    checks.begin("OWNER_CREDENTIAL_DELETE_CASCADES_SESSIONS", OWNER)
    cur.execute("DELETE FROM auth.credentials WHERE user_id=%s", (user_id,))
    require(checks.scalar("SELECT count(*) FROM auth.sessions WHERE user_id=%s", (user_id,)) == 0)
    require(checks.scalar("SELECT count(*) FROM public.users WHERE id=%s", (user_id,)) == 1)
    checks.ok()
    checks.begin("FORCE_CONSTRAINT_CHECKS_BEFORE_ROLLBACK", OWNER)
    cur.execute("SET CONSTRAINTS ALL IMMEDIATE")
    checks.ok()


def main():
    conn = None
    baseline = None
    checks = None
    passed = cleanup_ok = False
    phase = "CONNECT_TEST_DB"
    try:
        render_review()
        config = dotenv_values(BASE / "backend/.env")
        conn = psycopg.connect(
            host=config.get("DB_HOST"), port=int(config.get("DB_PORT") or 5432),
            dbname=TEST_DB, user=config.get("DB_USER"), password=config.get("DB_PASSWORD"),
            connect_timeout=8, autocommit=False,
            options="-c statement_timeout=15000 -c lock_timeout=3000",
        )
        with conn.cursor() as cur:
            cur.execute("SELECT current_database()")
            require(cur.fetchone()[0] == TEST_DB)
            switch(cur, OWNER)
            baseline = snapshot(cur)
            checks = Checks(cur)
            checks.begin("DATABASE_GUARD_AND_BASELINE", OWNER)
            require(sum(name.startswith("public.") for name in baseline[1]) == 14)
            checks.ok(database=TEST_DB, effective_role=OWNER)
            phase = "AUTH_STORAGE_RBAC_REHEARSAL"
            mode = prepare_auth_for_tests(cur)
            checks.begin(phase, OWNER)
            checks.ok(committed=False, baseline_mode=mode)
            phase = "AUTH_DATABASE_CASES"
            run_cases(checks)
            passed = True
    except Exception as exc:
        # Never print config, connection URLs, params, hashes, or raw tracebacks.
        details = {"error_type": type(exc).__name__, "sqlstate": getattr(exc, "sqlstate", None)}
        if isinstance(exc, psycopg.Error) and exc.sqlstate == "42501":
            details["permission_error"] = exc.diag.message_primary
        report(phase if phase != "AUTH_DATABASE_CASES" else checks.case, "FAIL", **details)
    finally:
        if conn is not None:
            try:
                conn.rollback()
                report("ROLLBACK", "PASS", committed=False)
                if baseline is not None:
                    with conn.cursor() as cur:
                        cur.execute("SET TRANSACTION READ ONLY")
                        cur.execute("SELECT current_database()")
                        require(cur.fetchone()[0] == TEST_DB)
                        switch(cur, OWNER)
                        after = snapshot(cur)
                        cleanup_ok = after == baseline
                        report("BASELINE_RESTORED", "PASS" if cleanup_ok else "FAIL",
                               public_tables=sum(name.startswith("public.") for name in after[1]),
                               auth_tables=sum(name.startswith("auth.") for name in after[1]),
                               total_rows=sum(after[1].values()),
                               identity_sequence_values_excluded=True)
            except Exception as exc:
                report("CLEANUP_VERIFICATION", "FAIL", error_type=type(exc).__name__,
                       sqlstate=getattr(exc, "sqlstate", None))
            finally:
                conn.rollback()
                conn.close()
    report("RESULT", "PASS" if passed and cleanup_ok else "FAIL",
           cases_passed=checks.passed if checks else 0,
           password_hashing_and_http_auth_tested=False)
    return 0 if passed and cleanup_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
