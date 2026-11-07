"""Read-only PostgreSQL preflight pinned to the V1 test database.

Run: python -B -m database.tools.Database_Schema_V1_Readonly_Preflight
Never imports backend.database, reads DB_NAME as a target, or writes to DB.
"""

from pathlib import Path
import sys

from psycopg.rows import dict_row

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.tools.Test_Database import connect_test_database, TEST_DB

EXPECTED_TABLES = (
    "users", "teams", "team_members", "projects", "advisor_invitations",
    "project_submissions", "project_submission_files", "committee_assignments",
    "committee_topic_votes", "committee_evaluations", "milestones", "tasks",
    "task_assignees", "task_assignment_history",
)


def main():
    conn = None
    try:
        conn = connect_test_database(readonly=True)
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""SELECT current_database() AS db_name,
                current_user AS connected_role,
                current_setting('server_version') AS pg_version,
                (SELECT pg_get_userbyid(datdba) FROM pg_database
                 WHERE datname=current_database()) AS db_owner,
                current_setting('transaction_read_only') AS readonly""")
            env = cur.fetchone()
            if env["db_name"] != TEST_DB or env["readonly"] != "on":
                raise RuntimeError("Read-only test-database guard failed")
            print("=== TEST DATABASE READ-ONLY PREFLIGHT ===")
            for name in ("db_name", "connected_role", "db_owner", "pg_version", "readonly"):
                print(name + ":", env[name])
            cur.execute("""SELECT rolname,rolcanlogin,rolsuper,rolcreatedb,
                rolcreaterole,rolbypassrls FROM pg_roles
                WHERE rolname IN ('postgres','project_owner','project_app')
                ORDER BY rolname""")
            print("Roles (login/superuser/createdb/createrole/bypassrls):")
            for row in cur.fetchall():
                print(" -", row["rolname"], *(row[key] for key in (
                    "rolcanlogin","rolsuper","rolcreatedb","rolcreaterole","rolbypassrls")))
                if row["rolname"] == env["connected_role"] and row["rolsuper"]:
                    print("   Inventory login only; never use this superuser for application workflows.")
            cur.execute("""SELECT tablename,tableowner FROM pg_tables
                WHERE schemaname='public' ORDER BY tablename""")
            tables = cur.fetchall()
            found = {row["tablename"] for row in tables}
            print("Public tables:", len(tables))
            for row in tables:
                print(" -", row["tablename"], "owner=", row["tableowner"])
            print("V1 expected tables:", len(set(EXPECTED_TABLES) & found), "/", len(EXPECTED_TABLES))
            print("Missing tables:", sorted(set(EXPECTED_TABLES) - found))
            print("Read-only inventory only; not proof that all V1 workflows pass.")
        return 0
    except Exception as exc:
        print("Preflight failed:", type(exc).__name__, "sqlstate=", getattr(exc, "sqlstate", None))
        return 2
    finally:
        if conn is not None:
            conn.rollback()
            conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
