"""Install the reviewed V1 draft ONLY into the existing empty V1 test database.

Run in the project root with private backend/.env deployment credentials:
    python -B -m database.tools.Database_Schema_V1_Test_Install_Only

This is a deliberate COMMIT (unlike the earlier dry run). It does not edit
backend/.env, the main database, GitHub, or application source files.
Do not run the RBAC template as part of this step.
"""

from pathlib import Path
import hashlib
import re
import sys

import psycopg

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.tools.Test_Database import connect_test_database

TEST_DATABASE = "student_project_management_v1_test"
MAIN_DATABASE = "student_project_management"
OWNER_ROLE = "project_owner"
APP_ROLE = "project_app"
ADMIN_ROLE = "postgres"
SQL_FILE = PROJECT_ROOT / "database/schema/Database_Schema_V1_A02_A05_REVIEW_DRAFT.sql"
# Pin the revised SQL file; review rollback regression results before installing.
EXPECTED_SHA256 = "770487d56c7ca71887fb91a84e254b59d40cfa949700e8a3b188c69246baa5bc"
EXPECTED = {"tables": 14, "foreign_keys": 28, "functions": 52, "triggers": 24}


def main() -> int:
    if not SQL_FILE.is_file():
        print(f"STOP: Missing {SQL_FILE.name}; nothing changed.")
        return 1

    source = SQL_FILE.read_bytes()
    if hashlib.sha256(source).hexdigest() != EXPECTED_SHA256:
        print("STOP: SQL draft differs from the reviewed version; nothing changed.")
        print("Check the reviewed SQL file and its pinned SHA256 before installation.")
        return 1

    sql = source.decode("utf-8-sig")
    beginnings = list(re.finditer(r"(?m)^BEGIN;[ \t]*$", sql))
    endings = list(re.finditer(r"(?m)^COMMIT;[ \t]*$", sql))
    if len(beginnings) != 1 or len(endings) != 1 or beginnings[0].start() >= endings[0].start():
        print("STOP: Unexpected SQL transaction markers; nothing changed.")
        return 1
    sql_body = re.sub(r"(?m)^BEGIN;[ \t]*$|^COMMIT;[ \t]*$", "", sql)

    conn = None
    committed = False
    try:
        conn = connect_test_database()
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), session_user")
            db, login = cur.fetchone()
            if db != TEST_DATABASE or db == MAIN_DATABASE or login != ADMIN_ROLE:
                print("STOP: Wrong database or admin login. Nothing changed.")
                return 1
            print("Test database:", db)
            print("Admin login:", login)

            cur.execute("""
                SELECT pg_get_userbyid(datdba)
                FROM pg_database WHERE datname = current_database()
            """)
            if cur.fetchone()[0] != OWNER_ROLE:
                print("STOP: Unexpected test DB owner. Nothing changed.")
                return 1

            cur.execute("""
                SELECT rolname, rolcanlogin, rolsuper
                FROM pg_roles WHERE rolname IN (%s, %s)
            """, (OWNER_ROLE, APP_ROLE))
            roles = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
            if roles.get(OWNER_ROLE) != (False, False) or roles.get(APP_ROLE) != (True, False):
                print("STOP: Expected owner/app role properties were not found.")
                return 1

            cur.execute("""
                SELECT count(*) FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                  AND c.relkind IN ('r','p','v','m','S','f','i','I')
            """)
            public_objects = cur.fetchone()[0]
            cur.execute("""
                SELECT count(*) FROM pg_proc p
                JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = 'public'
            """)
            public_functions = cur.fetchone()[0]
            if public_objects != 0 or public_functions != 0:
                print(f"STOP: Test public schema not empty: objects={public_objects}, functions={public_functions}.")
                print("No changes made. Do not rerun a schema installation on existing objects.")
                return 1

            cur.execute("SET LOCAL ROLE project_owner")
            cur.execute("SELECT current_user")
            if cur.fetchone()[0] != OWNER_ROLE:
                print("STOP: Unable to switch to owner role. Nothing changed.")
                return 1
            print("Execution role:", OWNER_ROLE)
            print("Installing reviewed schema inside one transaction...")
            cur.execute(sql_body, prepare=False)

            cur.execute("""
                SELECT count(*) FROM pg_class c
                JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='public' AND c.relkind='r'
            """)
            tables = cur.fetchone()[0]
            cur.execute("""
                SELECT count(*) FROM pg_constraint con
                JOIN pg_class c ON c.oid = con.conrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname='public' AND con.contype='f'
            """)
            foreign_keys = cur.fetchone()[0]
            cur.execute("""
                SELECT count(*) FROM pg_proc p
                JOIN pg_namespace n ON n.oid=p.pronamespace
                WHERE n.nspname='public' AND left(p.proname, 3)='v1_'
            """)
            functions = cur.fetchone()[0]
            cur.execute("""
                SELECT count(*) FROM pg_trigger t
                JOIN pg_class c ON c.oid=t.tgrelid
                JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='public' AND NOT t.tgisinternal
            """)
            triggers = cur.fetchone()[0]

            actual = {"tables": tables, "foreign_keys": foreign_keys,
                      "functions": functions, "triggers": triggers}
            for key, expected in EXPECTED.items():
                print(f"{key}: {actual[key]} / {expected}")
            if actual != EXPECTED:
                raise RuntimeError("Object counts differ from expected; installation will ROLLBACK.")

            cur.execute("""
                SELECT count(*) FROM pg_class c
                JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='public' AND c.relkind='r'
                  AND pg_get_userbyid(c.relowner) <> %s
            """, (OWNER_ROLE,))
            if cur.fetchone()[0]:
                raise RuntimeError("Not all V1 tables belong to project_owner; ROLLBACK.")

            cur.execute("""
                SELECT count(*) FROM pg_proc p
                JOIN pg_namespace n ON n.oid=p.pronamespace
                WHERE n.nspname='public' AND left(p.proname,3)='v1_'
                  AND pg_get_userbyid(p.proowner) <> %s
            """, (OWNER_ROLE,))
            if cur.fetchone()[0]:
                raise RuntimeError("Not all V1 functions belong to project_owner; ROLLBACK.")

            print("Validation passed. COMMITTING into TEST DATABASE ONLY...")
            conn.commit()
            committed = True
            print("SUCCESS: 14 test tables and supporting objects COMMITTED.")
            print("Main database not modified. RBAC template has NOT been run.")
            return 0
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 1
    finally:
        if conn is not None:
            try:
                if not committed:
                    conn.rollback()
                    print("ROLLBACK completed; no installation committed.")
            finally:
                conn.close()


if __name__ == "__main__":
    sys.exit(main())
