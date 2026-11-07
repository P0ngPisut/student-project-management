"""Apply the reviewed V1 RBAC template ONLY to the isolated PostgreSQL test DB.

Run from the repository root after a successful RBAC dry run:
    python -B -m database.tools.Database_Schema_V1_RBAC_Test_Apply_Only

This script COMMITS privilege changes in the TEST DATABASE, unlike the dry run.
It never edits FastAPI's .env, creates accounts or changes the main database.
Requires the template in database/schema and the dry-run helper in database/tools.
"""

from __future__ import annotations

from pathlib import Path
import sys
import psycopg
from psycopg import sql

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.tools.Test_Database import connect_test_database
from database.tools.Database_Schema_V1_RBAC_Dry_Run_Only import (
    APP_ROLE, OWNER_ROLE, TEST_DB, TEMPLATE, EXPECTED_TABLES, render_rbacs
)


def main() -> int:
    if not TEMPLATE.is_file():
        print(f"ERROR: Missing reviewed RBAC template: {TEMPLATE.name}")
        return 1
    with connect_test_database(autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), session_user, current_user")
            db, session_user, current_user = cur.fetchone()
            if db != TEST_DB or session_user != 'postgres' or current_user != 'postgres':
                print("ERROR: Wrong database or admin login, refusing to continue")
                return 1
            cur.execute("SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database()")
            (owner,) = cur.fetchone()
            if owner != OWNER_ROLE:
                print("ERROR: Unexpected database owner")
                return 1
            cur.execute("SELECT tablename, tableowner FROM pg_tables WHERE schemaname='public'")
            tables = dict(cur.fetchall())
            if set(tables) != EXPECTED_TABLES or any(owner != OWNER_ROLE for owner in tables.values()):
                print("ERROR: Test database is not the expected 14-table schema")
                return 1
            cur.execute("SELECT rolname, rolcanlogin, rolsuper FROM pg_roles WHERE rolname IN (%s,%s)",
                        (OWNER_ROLE, APP_ROLE))
            roles = {name: (canlogin, superuser) for name, canlogin, superuser in cur.fetchall()}
            if roles.get(OWNER_ROLE) != (False, False) or roles.get(APP_ROLE) != (True, False):
                print("ERROR: Test roles are not the expected non-superuser roles")
                return 1
            cur.execute("SELECT has_table_privilege(%s,'public.users','SELECT')", (APP_ROLE,))
            if cur.fetchone()[0]:
                print("ERROR: RBAC already seems applied (users SELECT granted). No changes made")
                return 1

            template_text = TEMPLATE.read_text(encoding='utf-8-sig')
            rendered = render_rbacs(template_text, conn)
            print('TEST DATABASE:', db)
            print('DATABASE OWNER:', owner)
            print('ADMIN LOGIN:', session_user)
            print('TARGET APP ROLE:', APP_ROLE)
            print('TABLES:', len(tables))
            print('This operation will COMMIT RBAC GRANT/REVOKE to TEST DATABASE only.')
            if input("Type APPLY-TEST-RBAC to confirm: ").strip() != 'APPLY-TEST-RBAC':
                print('Cancelled; no changes made')
                return 0

            cur.execute(sql.SQL('SET ROLE {}').format(sql.Identifier(OWNER_ROLE)))
            cur.execute('BEGIN')
            try:
                cur.execute(rendered)  # Includes preflight and postflight checks
                cur.execute("""
                    SELECT
                        has_table_privilege(%s,'public.users','SELECT'),
                        has_table_privilege(%s,'public.projects','DELETE'),
                        has_function_privilege(%s,'public.v1_transfer_team_leader(bigint,bigint)','EXECUTE')
                """, (APP_ROLE, APP_ROLE, APP_ROLE))
                can_select, can_delete_project, can_execute = cur.fetchone()
                if (can_select, can_delete_project, can_execute) != (True, False, True):
                    raise ValueError('Unexpected RBAC privileges after applying the template')
                cur.execute('COMMIT')
                print('SUCCESS: RBAC privilege changes COMMITTED to TEST DATABASE ONLY')
            except Exception:
                cur.execute('ROLLBACK')
                print('ROLLBACK: RBAC privilege changes NOT committed')
                raise

            cur.execute('RESET ROLE')
            cur.execute("""
                SELECT
                    has_table_privilege(%s,'public.users','SELECT'),
                    has_table_privilege(%s,'public.projects','DELETE'),
                    has_function_privilege(%s,'public.v1_transfer_team_leader(bigint,bigint)','EXECUTE')
            """, (APP_ROLE, APP_ROLE, APP_ROLE))
            flags = cur.fetchone()
            print('Verified after commit:')
            print('  project_app SELECT users:', flags[0])
            print('  project_app DELETE projects:', flags[1])
            print('  project_app EXECUTE leader transfer:', flags[2])
            if flags != (True, False, True):
                print('WARNING: Unexpected grants on post-commit verification; review test database RBAC')
                return 1
            print('Main database was not accessed or modified.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print('ERROR:', type(exc).__name__, str(exc))
        raise SystemExit(1) from None
