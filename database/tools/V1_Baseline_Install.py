"""Install the explicitly approved six-function repair in the TEST DB only.

Default: read-only readiness check. --apply: one atomic DDL/one helper grant
transaction, as project_owner, with no fixtures. A correct installed baseline
is verified rather than overwritten. No table/role/password changes allowed.
"""

import argparse
import hashlib
import json

from database.tests.Auth_Regression import snapshot, switch, validate_installed_auth
from database.tools.Test_Database import TEST_DB, connect_test_database
from database.tools.V1_Baseline_Prepare import (
    PATCH_NAMES, REVIEW_SHA, SOURCE_SHA, app_permissions, inventory, require, review_body,
)


def protected_fingerprint(cur):
    """All protected catalog state and row counts, excluding approved definitions.

Existing function ACLs are independently included even for the five replaced
functions. Only the new helper has no old ACL and is checked by postflight.
"""
    queries = [
        ("""SELECT nspname,pg_get_userbyid(nspowner),nspacl::text FROM pg_namespace
            WHERE nspname IN ('public','auth') ORDER BY 1""", None),
        ("""SELECT n.nspname,c.relname,c.relkind,pg_get_userbyid(c.relowner),c.relacl::text,
            c.relrowsecurity,c.relforcerowsecurity FROM pg_class c
            JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname IN ('public','auth') ORDER BY 1,2""", None),
        ("""SELECT n.nspname,c.relname,a.attnum,a.attname,format_type(a.atttypid,a.atttypmod),
            a.attnotnull,a.attacl::text,pg_get_expr(d.adbin,d.adrelid)
            FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
            LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
            WHERE n.nspname IN ('public','auth') AND c.relkind='r'
              AND a.attnum>0 AND NOT a.attisdropped ORDER BY 1,2,3""", None),
        ("""SELECT n.nspname,c.relname,x.conname,pg_get_constraintdef(x.oid)
            FROM pg_constraint x JOIN pg_class c ON c.oid=x.conrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname IN ('public','auth') ORDER BY 1,2,3""", None),
        ("""SELECT n.nspname,c.relname,t.tgname,pg_get_triggerdef(t.oid),t.tgenabled
            FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname IN ('public','auth') ORDER BY 1,2,3""", None),
        ("""SELECT p.oid::regprocedure::text,pg_get_functiondef(p.oid),
            pg_get_userbyid(p.proowner),p.proacl::text FROM pg_proc p
            JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname IN ('public','auth') AND p.prokind='f'
              AND NOT (n.nspname='public' AND p.proname=ANY(%s)) ORDER BY 1""", (sorted(PATCH_NAMES),)),
        ("""SELECT p.oid::regprocedure::text,pg_get_userbyid(p.proowner),p.proacl::text
            FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname IN ('public','auth') AND p.prokind='f'
              AND NOT (n.nspname='public' AND p.proname='v1_lock_team') ORDER BY 1""", None),
        ("""SELECT rolname,rolcanlogin,rolsuper,rolcreatedb,rolcreaterole,rolbypassrls,rolreplication
            FROM pg_roles WHERE rolname IN ('project_owner','project_app') ORDER BY 1""", None),
        ("""SELECT r.rolname,m.rolname,a.admin_option,a.inherit_option,a.set_option
            FROM pg_auth_members a JOIN pg_roles r ON r.oid=a.roleid
            JOIN pg_roles m ON m.oid=a.member
            WHERE r.rolname IN ('project_owner','project_app')
               OR m.rolname IN ('project_owner','project_app') ORDER BY 1,2""", None),
        ("SELECT pg_get_userbyid(datdba),datacl::text FROM pg_database WHERE datname=current_database()", None),
    ]
    records = []
    for query, params in queries:
        cur.execute(query, params)
        records.append(cur.fetchall())
    counts = snapshot(cur)[1]
    records.append(counts)
    return hashlib.sha256(json.dumps(records, default=str).encode()).hexdigest(), counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Commit ONLY the separately approved repair")
    args = parser.parse_args()
    if not args.apply:
        from database.tools.V1_Baseline_Prepare import main as inspect_main
        return inspect_main()
    conn = None
    committed = False
    try:
        # Verify pins even when the database is already repaired.
        reviewed = review_body()
        conn = connect_test_database()
        conn.rollback()
        with conn.transaction():
            with conn.cursor() as cur:
                switch(cur, "project_owner")
                cur.execute("SELECT pg_advisory_xact_lock(736701,1)")
                validate_installed_auth(cur)
                count, differences = inventory(cur)
                if not differences:
                    app_permissions(cur)
                    # No DDL or commit is necessary for an already-correct DB.
                    raise AlreadyInstalled()
                require(count == 51 and {row['function'] for row in differences} == PATCH_NAMES)
                before = protected_fingerprint(cur)
                cur.execute(reviewed, prepare=False)
                require(inventory(cur) == (52, []))
                app_permissions(cur)
                validate_installed_auth(cur)
                after = protected_fingerprint(cur)
                require(before == after)
                print(json.dumps({"case":"INSTALL_POSTFLIGHT", "result":"PASS",
                    "database":TEST_DB, "protected_metadata_acl_rows_unchanged":True,
                    "row_counts":after[1], "fixture_rows_created":False}))
        committed = True
        print(json.dumps({"case":"V1_BASELINE_INSTALL", "result":"PASS", "status":"INSTALLED",
            "database":TEST_DB, "effective_ddl_role":"project_owner", "committed":True,
            "functions":52, "app_grant_added":"EXECUTE public.v1_lock_team(bigint)",
            "source_sha256":SOURCE_SHA, "review_sha256":REVIEW_SHA}))
        return 0
    except AlreadyInstalled:
        print(json.dumps({"case":"V1_BASELINE_INSTALL", "result":"PASS",
            "status":"ALREADY_INSTALLED_VERIFIED", "database":TEST_DB, "committed":False}))
        return 0
    except Exception as exc:
        print(json.dumps({"case":"V1_BASELINE_INSTALL", "result":"FAIL",
            "error_type":type(exc).__name__, "sqlstate":getattr(exc,"sqlstate",None),
            "committed":committed}))
        return 1
    finally:
        if conn is not None:
            try:
                conn.rollback()
            finally:
                conn.close()


class AlreadyInstalled(Exception):
    """Exit a transaction with ROLLBACK after verifying an installed baseline."""


if __name__ == "__main__":
    raise SystemExit(main())
