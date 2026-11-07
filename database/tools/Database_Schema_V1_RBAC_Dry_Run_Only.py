"""Dry-run ONLY: validate V1 RBAC grants in the isolated PostgreSQL test DB.

Run from the repository root; the template is in database/schema:
    python -B -m database.tools.Database_Schema_V1_RBAC_Dry_Run_Only

The script reads an existing SQL template, applies it inside ONE explicit transaction,
inspects the effective grants, and ROLLBACKs. It never commits, creates roles, or
changes the application's .env file. Do not use it with a production database.
"""

from __future__ import annotations

import re
from pathlib import Path
import sys

import psycopg
from psycopg import sql

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.tools.Test_Database import connect_test_database

TEST_DB = "student_project_management_v1_test"
OWNER_ROLE = "project_owner"
APP_ROLE = "project_app"
TEMPLATE = PROJECT_ROOT / "database/schema/Database_Schema_V1_A02_A05_RBAC_REVIEW_TEMPLATE.sql"
EXPECTED_TABLES = {
    "users", "teams", "team_members", "projects", "advisor_invitations",
    "project_submissions", "project_submission_files", "committee_assignments",
    "committee_topic_votes", "committee_evaluations", "milestones", "tasks",
    "task_assignees", "task_assignment_history",
}


def render_rbacs(template: str, conn: psycopg.Connection) -> str:
    """Convert only the audited template's psql syntax for psycopg execution."""
    required_markers = (
        "RBAC REVIEW TEMPLATE", "No CREATE/ALTER ROLE here",
        "DO $preflight$", "DO $postflight$",
        "REVOKE DELETE ON TABLE public.projects",
    )
    for marker in required_markers:
        if marker not in template:
            raise ValueError(f"Template is not the expected V1 review version: {marker!r}")

    lines = []
    allowed_psql = {"\\set", "\\if", "\\else", "\\endif", "\\echo", "\\quit"}
    for line in template.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("\\"):
            if stripped.split(maxsplit=1)[0] not in allowed_psql:
                raise ValueError("Unexpected psql command in RBAC template")
            continue
        lines.append(line)
    body = "\n".join(lines)

    # The template has its own BEGIN/COMMIT for an eventual *approved* install.
    # Remove these; the dry-run exclusively controls an outer ROLLBACK transaction.
    body, begins = re.subn(r"(?im)^\s*BEGIN\s*;\s*$", "", body)
    body, commits = re.subn(r"(?im)^\s*COMMIT\s*;\s*$", "", body)
    if begins != 1 or commits != 1:
        raise ValueError("Expected exactly one standalone BEGIN and COMMIT in template")
    if re.search(r"(?im)^\s*(?:COMMIT|END\s+TRANSACTION)\s*;", body):
        raise ValueError("A transaction commit would invalidate the dry-run safeguard")

    # The names below are fixed by this test-only script; never accept user input.
    for var, value in (("v1_app_role", APP_ROLE), ("v1_owner_role", OWNER_ROLE)):
        body = body.replace(':"' + var + '"', sql.Identifier(value).as_string(conn))
        body = body.replace(":'" + var + "'", sql.Literal(value).as_string(conn))
    if re.search(r":(?:'v1_\w+'|\"v1_\w+\")", body):
        raise ValueError("Unresolved psql placeholder; refusing to execute")
    return body


def main() -> int:
    if not TEMPLATE.is_file():
        print(f"ERROR: RBAC template file is missing: {TEMPLATE.name}")
        return 1

    with connect_test_database(autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), current_user")
            db_name, login = cur.fetchone()
            if db_name != TEST_DB:
                print("ERROR: Wrong database; refusing to continue")
                return 1
            if login != "postgres":
                print("ERROR: Unexpected admin login; refusing to continue")
                return 1
            cur.execute("SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = current_database()")
            (db_owner,) = cur.fetchone()
            if db_owner != OWNER_ROLE:
                print("ERROR: Test database owner is not project_owner")
                return 1
            cur.execute("""
                SELECT tablename, tableowner FROM pg_tables WHERE schemaname='public'
            """)
            owned_tables = dict(cur.fetchall())
            if set(owned_tables) != EXPECTED_TABLES or any(v != OWNER_ROLE for v in owned_tables.values()):
                print("ERROR: Test schema doesn't contain exactly the 14 expected owner-owned tables")
                return 1
            cur.execute("SELECT rolname, rolcanlogin, rolsuper FROM pg_roles WHERE rolname IN (%s,%s)", (OWNER_ROLE, APP_ROLE))
            roles = {name: (can_login, superuser) for name, can_login, superuser in cur.fetchall()}
            if roles.get(OWNER_ROLE) != (False, False) or roles.get(APP_ROLE) != (True, False):
                print("ERROR: Role properties differ from the previously agreed test setup")
                return 1
            cur.execute("SELECT has_table_privilege(%s,'public.users','SELECT')", (APP_ROLE,))
            (app_before,) = cur.fetchone()
            if app_before:
                print("ERROR: App already has SELECT; refusing to assume a clean RBAC baseline")
                return 1

            rendered = render_rbacs(TEMPLATE.read_text(encoding="utf-8-sig"), conn)
            print("Database:", db_name)
            print("Database owner:", db_owner)
            print("Login role:", login)
            print("RBAC execution role:", OWNER_ROLE)
            print("Checking RBAC template inside an explicit transaction...")

            # SET ROLE changes only the current connection. It is never stored.
            cur.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(OWNER_ROLE)))
            cur.execute("BEGIN")
            try:
                cur.execute(rendered)
                cur.execute("""
                    SELECT
                      has_table_privilege(%s,'public.users','SELECT'),
                      has_table_privilege(%s,'public.projects','DELETE'),
                      has_function_privilege(%s,'public.v1_transfer_team_leader(bigint,bigint)','EXECUTE')
                """, (APP_ROLE, APP_ROLE, APP_ROLE))
                can_read, can_delete_project, can_transfer = cur.fetchone()
                print("Inside transaction: project_app SELECT users:", can_read)
                print("Inside transaction: project_app DELETE projects:", can_delete_project)
                print("Inside transaction: project_app EXECUTE leader transfer:", can_transfer)
                if (can_read, can_delete_project, can_transfer) != (True, False, True):
                    raise ValueError("Unexpected effective app grants inside the dry-run transaction")
                print("RBAC SQL: executed and postflight checks passed (NOT COMMITTED)")
            finally:
                # Even if any query errors, ROLLBACK works in an aborted transaction.
                cur.execute("ROLLBACK")
                print("ROLLBACK completed: RBAC grants were NOT saved")

            cur.execute("SELECT has_table_privilege(%s,'public.users','SELECT')", (APP_ROLE,))
            (after,) = cur.fetchone()
            if after:
                print("ERROR: Unexpected persisted SELECT privilege after rollback")
                return 1
            print("Verified: project_app still has no SELECT on public.users")
            print("Main database was not accessed or modified")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("RBAC dry-run FAILED:", type(exc).__name__, str(exc))
        print("No RBAC grants should have been committed; review the error before continuing")
        raise SystemExit(1) from None
