"""Read-only PostgreSQL environment check for Student Project Management V1.

Run from the repository root:
    python -B -m database.tools.Database_Schema_V1_Readonly_Preflight

This script performs SELECT only. It never prints DB_PASSWORD or connection URLs.
It uses the backend engine and does NOT pin the test database; see database/README.md.
"""

from __future__ import annotations

import sys
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from backend.database import engine
except ImportError as exc:
    print("Cannot import backend.database. Run from the repository root with the backend venv active.")
    raise SystemExit(1) from exc

EXPECTED_TABLES = (
    "users", "teams", "team_members", "projects", "advisor_invitations",
    "project_submissions", "project_submission_files", "committee_assignments",
    "committee_topic_votes", "committee_evaluations", "milestones", "tasks",
    "task_assignees", "task_assignment_history",
)


def main() -> int:
    try:
        with engine.connect() as connection:
            env = connection.execute(text("""
                SELECT current_database() AS db_name,
                       current_user AS connected_role,
                       current_setting('server_version') AS pg_version,
                       (SELECT pg_get_userbyid(datdba)
                          FROM pg_database WHERE datname = current_database()) AS db_owner
            """)).mappings().one()

            print("=== PostgreSQL V1 READ-ONLY PREFLIGHT ===")
            print("Database:", env["db_name"])
            print("Connected role:", env["connected_role"])
            print("Database owner:", env["db_owner"])
            print("PostgreSQL version:", env["pg_version"])

            roles = connection.execute(text("""
                SELECT rolname, rolcanlogin, rolsuper, rolcreatedb,
                       rolcreaterole, rolbypassrls
                  FROM pg_roles
                 WHERE rolname NOT LIKE 'pg_%'
                 ORDER BY rolname
            """)).mappings().all()
            print("\nExisting user-defined roles:")
            for r in roles:
                flags = [name for name, key in (
                    ("LOGIN", "rolcanlogin"), ("SUPERUSER", "rolsuper"),
                    ("CREATEDB", "rolcreatedb"), ("CREATEROLE", "rolcreaterole"),
                    ("BYPASSRLS", "rolbypassrls"),
                ) if r[key]]
                print(" -", r["rolname"], "[" + ", ".join(flags or ["no elevated flags"]) + "]")

            tables = connection.execute(text("""
                SELECT tablename, tableowner
                  FROM pg_tables
                 WHERE schemaname = 'public'
                 ORDER BY tablename
            """)).mappings().all()
            print("\nPublic tables:", len(tables))
            found = set()
            for row in tables:
                print(" -", row["tablename"], "owner=", row["tableowner"])
                found.add(row["tablename"])
            missing = sorted(set(EXPECTED_TABLES) - found)
            print("V1 expected tables present:", len(EXPECTED_TABLES) - len(missing), "/", len(EXPECTED_TABLES))
            if missing:
                print("V1 tables not yet created:", ", ".join(missing))

            connected = next((r for r in roles if r["rolname"] == env["connected_role"]), None)
            if connected and connected["rolsuper"]:
                print("\nSECURITY NOTE: connected role is SUPERUSER. Do not use it as the production FastAPI role.")
            if not tables:
                print("NEXT: prepare a DIFFERENT test database for V1 SQL experiments; do not execute the draft in the existing database.")
            else:
                print("NEXT: inspect existing objects and take a backup before any future schema changes.")
            print("\nRead-only check completed. No DB changes were made.")
        return 0
    except SQLAlchemyError as exc:
        # Do not leak credential-bearing connection string via exception output.
        print("PostgreSQL connection or read-only query failed:", exc.__class__.__name__)
        print("Check that PostgreSQL is running, the backend venv is active, and backend/.env is configured.")
        return 2


if __name__ == "__main__":
    sys.exit(main())
