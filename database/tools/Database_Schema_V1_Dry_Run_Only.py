"""Validate V1 SQL in an isolated test DB and ALWAYS roll back all SQL changes.

Run at repository root: python -B -m database.tools.Database_Schema_V1_Dry_Run_Only
Requires private deployment config and a working test PostgreSQL connection.
Never prints passwords or connection URLs.
"""
from pathlib import Path
import re
import sys

import psycopg

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.tools.Test_Database import connect_test_database

TEST_DB = "student_project_management_v1_test"
OWNER_ROLE = "project_owner"
SQL_FILE = PROJECT_ROOT / "database/schema/Database_Schema_V1_A02_A05_REVIEW_DRAFT.sql"


def main() -> int:
    if not SQL_FILE.is_file():
        print(f"STOP: SQL file not found: {SQL_FILE.name}")
        return 1

    sql = SQL_FILE.read_text(encoding="utf-8-sig")
    # The reviewed draft has its own BEGIN/COMMIT markers. Remove ONLY those
    # two standalone markers and control the transaction in Python instead.
    begin = list(re.finditer(r"(?m)^BEGIN;[ \t]*$", sql))
    commit = list(re.finditer(r"(?m)^COMMIT;[ \t]*$", sql))
    if len(begin) != 1 or len(commit) != 1 or begin[0].start() >= commit[0].start():
        print("STOP: Unexpected transaction markers in SQL; no SQL executed.")
        return 1
    sql_body = re.sub(r"(?m)^BEGIN;[ \t]*$|^COMMIT;[ \t]*$", "", sql)

    connection = None
    try:
        connection = connect_test_database()
        with connection.cursor() as cur:
            cur.execute("SELECT current_database(), current_user")
            db_name, login_role = cur.fetchone()
            if db_name != TEST_DB:
                print("STOP: Connected to an unexpected database. No SQL executed.")
                return 1
            print(f"Database: {db_name}")
            print(f"Login role: {login_role}")

            cur.execute("""
                SELECT count(*) FROM pg_class c
                JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='public'
                  AND c.relkind IN ('r','p','v','m','S','f')
            """)
            public_objects = cur.fetchone()[0]
            cur.execute("""
                SELECT count(*) FROM pg_proc p
                JOIN pg_namespace n ON n.oid=p.pronamespace
                WHERE n.nspname='public' AND p.proname LIKE 'v1\\_%' ESCAPE '\\'
            """)
            v1_functions = cur.fetchone()[0]
            if public_objects or v1_functions:
                print(f"STOP: Test public schema is not empty (objects={public_objects}, V1 functions={v1_functions}).")
                return 1

            cur.execute("SET LOCAL ROLE project_owner")
            cur.execute("SELECT current_user")
            active_role = cur.fetchone()[0]
            if active_role != OWNER_ROLE:
                print("STOP: Could not switch to project_owner. No SQL executed.")
                return 1
            print(f"Execution role: {active_role}")
            print("Checking full SQL draft inside an uncommitted transaction...")
            cur.execute(sql_body, prepare=False)
            print("SQL DRAFT: EXECUTED in transaction (not committed)")
            return 0
    except psycopg.Error as exc:
        print("SQL DRAFT: FAILED during PostgreSQL test")
        if exc.sqlstate:
            print(f"SQLSTATE: {exc.sqlstate}")
        print(str(exc))
        return 1
    except Exception as exc:
        print(f"STOP: {type(exc).__name__}: {exc}")
        return 1
    finally:
        if connection is not None:
            try:
                connection.rollback()
                print("ROLLBACK completed; no schema changes committed.")
            finally:
                connection.close()


if __name__ == "__main__":
    sys.exit(main())
