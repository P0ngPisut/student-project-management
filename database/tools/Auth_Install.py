"""Install only reviewed Auth objects in the test DB; dry-run by default.

--apply commits empty Auth storage and reviewed Auth grants, never fixtures.
--check-runtime verifies direct project_app authentication in a read-only transaction.
No role/password changes, V1 patches, or main database connections are allowed.
The existing rollback-only SQL files are unchanged and checksum pinned.
"""

import argparse
import hashlib
import json

from dotenv import dotenv_values
import psycopg

from database.tests.Auth_Regression import (
    BASE, OWNER, TEST_DB, guard, render_review, require, snapshot, switch,
    validate_installed_auth,
)


def public_fingerprint(cur):
    """Keep V1 objects/ACL/data unchanged; Auth adds its own incoming FK triggers."""
    guard(cur, OWNER)
    cur.execute("SET LOCAL search_path=pg_catalog,pg_temp")
    queries = (
        """SELECT c.relname,c.relkind,pg_get_userbyid(c.relowner),c.relacl::text
           FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
           WHERE n.nspname='public' ORDER BY 1""",
        """SELECT p.oid::regprocedure::text,pg_get_functiondef(p.oid),p.proacl::text,
                  pg_get_userbyid(p.proowner)
           FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
           WHERE n.nspname='public' AND p.prokind='f' ORDER BY 1""",
        """SELECT c.relname,a.attname,a.attnum,format_type(a.atttypid,a.atttypmod),
                  a.attnotnull,a.attacl::text,pg_get_expr(d.adbin,d.adrelid)
           FROM pg_catalog.pg_attribute a JOIN pg_catalog.pg_class c ON c.oid=a.attrelid
           JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
           LEFT JOIN pg_catalog.pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
           WHERE n.nspname='public' AND c.relkind='r' AND a.attnum>0 AND NOT a.attisdropped
           ORDER BY c.relname,a.attnum""",
        """SELECT c.relname,x.conname,pg_get_constraintdef(x.oid)
           FROM pg_catalog.pg_constraint x JOIN pg_catalog.pg_class c ON c.oid=x.conrelid
           JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
           WHERE n.nspname='public' ORDER BY 1,2""",
        """SELECT c.relname,t.tgname,pg_get_triggerdef(t.oid),t.tgenabled
           FROM pg_catalog.pg_trigger t JOIN pg_catalog.pg_class c ON c.oid=t.tgrelid
           JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
           WHERE n.nspname='public' AND NOT t.tgisinternal ORDER BY 1,2""",
        """SELECT nspacl::text FROM pg_catalog.pg_namespace WHERE nspname='public'""",
        """SELECT datacl::text FROM pg_catalog.pg_database WHERE datname=current_database()""",
        """SELECT rolname,rolsuper,rolcreatedb,rolcreaterole,rolbypassrls,rolcanlogin
           FROM pg_catalog.pg_roles WHERE rolname IN ('project_owner','project_app') ORDER BY 1""",
    )
    records = []
    for query in queries:
        cur.execute(query)
        records.append(cur.fetchall())
    public_counts = {name:count for name,count in snapshot(cur)[1].items() if name.startswith("public.")}
    records.append(public_counts)
    return hashlib.sha256(json.dumps(records, default=str, sort_keys=True).encode()).hexdigest()


def check_runtime():
    from backend.auth_store import assert_auth_connection, open_auth_connection
    conn = None
    try:
        conn = open_auth_connection()
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            assert_auth_connection(conn)
            cur.execute("""SELECT has_schema_privilege(current_user,'auth','USAGE'),
                has_function_privilege(current_user,'auth.register_student(text,text,text)','EXECUTE'),
                has_function_privilege(current_user,'auth.lookup_credentials(text)','EXECUTE'),
                has_table_privilege(current_user,'auth.sessions','SELECT'),
                has_any_column_privilege(current_user,'auth.credentials','SELECT'),
                has_any_column_privilege(current_user,'public.users','INSERT')""")
            require(cur.fetchone() == (True, True, True, True, False, False))
            print(json.dumps({"result":"PASS", "status":"RUNTIME_APP_READONLY_VERIFIED",
                              "database":TEST_DB, "role":"project_app", "committed":False}))
        return 0
    except Exception as exc:
        print(json.dumps({"result":"NOT_READY", "status":"CHECK_LOCAL_AUTH_CONFIG_AND_CONNECTION",
                          "error_type":type(exc).__name__, "sqlstate":getattr(exc,"sqlstate",None),
                          "committed":False, "credentials_printed":False}))
        return 1
    finally:
        if conn is not None:
            conn.rollback()
            conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--apply", action="store_true", help="Commit reviewed empty Auth storage/grants in TEST DB only")
    action.add_argument("--check-runtime", action="store_true", help="Read-only direct app credential/privilege check")
    args = parser.parse_args()
    if args.check_runtime:
        return check_runtime()
    conn = None
    committed = False
    try:
        reviewed = render_review()
        cfg = dotenv_values(BASE / "backend/.env")
        conn = psycopg.connect(
            host=cfg.get("DB_HOST"), port=int(cfg.get("DB_PORT") or 5432),
            dbname=TEST_DB, user=cfg.get("DB_USER"), password=cfg.get("DB_PASSWORD"),
            connect_timeout=8, autocommit=False,
            options="-c statement_timeout=15000 -c lock_timeout=3000",
        )
        with conn.cursor() as cur:
            cur.execute("SELECT current_database()")
            require(cur.fetchone()[0] == TEST_DB)
            switch(cur, OWNER)
            cur.execute("SET LOCAL search_path=pg_catalog,pg_temp")
            before = snapshot(cur)
            original_public = public_fingerprint(cur)
            cur.execute("SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_namespace WHERE nspname='auth')")
            existing = cur.fetchone()[0]
            if not existing:
                cur.execute(reviewed, prepare=False)
            validate_installed_auth(cur)
            require(public_fingerprint(cur) == original_public)
            if not existing:
                cur.execute("SELECT (SELECT count(*) FROM auth.credentials)+(SELECT count(*) FROM auth.sessions)")
                require(cur.fetchone()[0] == 0)
            if args.apply and not existing:
                guard(cur, OWNER)
                conn.commit()
                committed = True
            else:
                conn.rollback()
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SELECT current_database()")
            require(cur.fetchone()[0] == TEST_DB)
            switch(cur, OWNER)
            require(public_fingerprint(cur) == original_public)
            if committed or existing:
                validate_installed_auth(cur)
                after = snapshot(cur)
                require(sum(name.startswith('public.') for name in after[1]) == 14)
                require(sum(name.startswith('auth.') for name in after[1]) == 2)
                status = "INSTALLED" if committed else "ALREADY_INSTALLED_VERIFIED"
            else:
                require(snapshot(cur) == before)
                after = before
                status = "DRY_RUN_ROLLED_BACK"
            print(json.dumps({"result":"PASS", "status":status, "database":TEST_DB,
                              "committed":committed, "v1_objects_roles_acls_rows_unchanged":True,
                              "public_tables":sum(name.startswith('public.') for name in after[1]),
                              "auth_tables":sum(name.startswith('auth.') for name in after[1]),
                              "total_rows":sum(after[1].values())}))
        return 0
    except Exception as exc:
        # Never emit credentials, connection strings, parameters or raw traceback.
        print(json.dumps({"result":"FAIL", "error_type":type(exc).__name__,
                          "sqlstate":getattr(exc,"sqlstate",None), "committed":committed}))
        return 1
    finally:
        if conn is not None:
            conn.rollback()
            conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
