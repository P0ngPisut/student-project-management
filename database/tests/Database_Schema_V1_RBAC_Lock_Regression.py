"""Test the parent-lock fix in the V1 TEST database, then ALWAYS ROLLBACK.

Temporarily replaces only the five affected functions and applies the RBAC
template as project_owner. One student fixture is created as project_owner;
application workflows run as project_app, without direct UPDATE privileges.
No schema, grants, or fixture rows are committed. Identity sequences may advance.
Run from the repository root:
    backend/.venv/Scripts/python.exe -B -m database.tests.Database_Schema_V1_RBAC_Lock_Regression
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from uuid import uuid4

import psycopg
from psycopg import sql
from dotenv import dotenv_values

BASE = Path(__file__).resolve().parents[2]
TEST_DB = "student_project_management_v1_test"
OWNER_ROLE = "project_owner"
APP_ROLE = "project_app"
SCHEMA = BASE / "database/schema/Database_Schema_V1_A02_A05_REVIEW_DRAFT.sql"
RBAC = BASE / "database/schema/Database_Schema_V1_A02_A05_RBAC_REVIEW_TEMPLATE.sql"
PATCH_FUNCTIONS = {"v1_lock_team", "v1_lock_project",
                   "v1_team_members_guard", "v1_project_guard",
                   "v1_team_final_cardinality"}
TABLES = ("users", "teams", "team_members", "projects", "advisor_invitations",
          "project_submissions", "project_submission_files", "committee_assignments",
          "committee_topic_votes", "committee_evaluations", "milestones", "tasks",
          "task_assignees", "task_assignment_history")


def report(case: str, result: str, **details) -> None:
    print(json.dumps({"case": case, "result": result, **details}, default=str))


def guard(cur, role: str) -> None:
    cur.execute("""SELECT current_database(), current_user,
        (SELECT rolsuper FROM pg_roles WHERE rolname=current_user),
        current_setting('session_replication_role')""")
    if cur.fetchone() != (TEST_DB, role, False, "origin"):
        raise RuntimeError("Database, role, or trigger guard failed")


def switch_role(cur, role: str) -> None:
    cur.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
    guard(cur, role)


def snapshot(cur) -> tuple[str, dict[str, int]]:
    """Compare definitions/ACLs/owners and row counts; exclude sequence values."""
    cur.execute("""SELECT p.oid::regprocedure::text, pg_get_userbyid(p.proowner),
        pg_get_functiondef(p.oid), p.proacl::text
        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname='public' AND left(p.proname,3)='v1_'
        ORDER BY 1""")
    functions = cur.fetchall()
    cur.execute("""SELECT c.relname, pg_get_userbyid(c.relowner), c.relacl::text
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relkind IN ('r','p') ORDER BY 1""")
    tables = cur.fetchall()
    cur.execute("""SELECT nspacl::text FROM pg_namespace WHERE nspname='public'""")
    schema_acl = cur.fetchall()
    cur.execute("""SELECT c.relname, t.tgname, pg_get_triggerdef(t.oid), t.tgenabled
        FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND NOT t.tgisinternal ORDER BY 1,2""")
    triggers = cur.fetchall()
    counts = {}
    for table in TABLES:
        cur.execute(sql.SQL("SELECT count(*) FROM public.{}").format(sql.Identifier(table)))
        counts[table] = cur.fetchone()[0]
    data = json.dumps([functions, tables, schema_acl, triggers], default=str)
    return hashlib.sha256(data.encode()).hexdigest(), counts


def render_rbac(conn) -> str:
    """Remove only the template's psql directives and outer transaction."""
    template = RBAC.read_text(encoding="utf-8-sig")
    allowed = {"\\set", "\\if", "\\else", "\\endif", "\\echo", "\\quit"}
    lines = []
    for line in template.splitlines():
        if line.lstrip().startswith("\\"):
            if line.split(maxsplit=1)[0] not in allowed:
                raise ValueError("Unexpected psql directive")
        else:
            lines.append(line)
    body = "\n".join(lines)
    for marker in ("BEGIN", "COMMIT"):
        body, count = re.subn(rf"(?m)^{marker};[ \t]*$", "", body)
        if count != 1:
            raise ValueError("Unexpected RBAC transaction markers")
    for name, value in (("v1_owner_role", OWNER_ROLE), ("v1_app_role", APP_ROLE)):
        body = body.replace(':"' + name + '"', sql.Identifier(value).as_string(conn))
        body = body.replace(":'" + name + "'", sql.Literal(value).as_string(conn))
    if re.search(r":(?:'v1_\w+'|\"v1_\w+\")", body):
        raise ValueError("Unresolved RBAC placeholder")
    return body


def expect_error(cur, case, action, state, *, constraint=None, message=None):
    guard(cur, OWNER_ROLE if case.startswith("OWNER_") else APP_ROLE)
    cur.execute("SAVEPOINT lock_regression_case")
    matched = False
    try:
        action()
        report(case, "FAIL", reason="Expected error was not raised")
    except psycopg.Error as exc:
        matched = (exc.sqlstate == state
                   and (constraint is None or exc.diag.constraint_name == constraint)
                   and (message is None or message in exc.diag.message_primary))
        report(case, "PASS" if matched else "FAIL", sqlstate=exc.sqlstate,
               constraint=exc.diag.constraint_name, message=exc.diag.message_primary,
               context=exc.diag.context)
    finally:
        cur.execute("ROLLBACK TO SAVEPOINT lock_regression_case")
        cur.execute("RELEASE SAVEPOINT lock_regression_case")
    if not matched:
        raise RuntimeError("Regression case failed: " + case)


def main() -> int:
    conn = None
    baseline = None
    passed = False
    cleanup_ok = False
    try:
        config = dotenv_values(BASE / "backend/.env")
        conn = psycopg.connect(
            host=config.get("DB_HOST"), port=int(config.get("DB_PORT") or 5432),
            dbname=TEST_DB, user=config.get("DB_USER"), password=config.get("DB_PASSWORD"),
            connect_timeout=8, autocommit=False,
            options="-c statement_timeout=15000 -c lock_timeout=3000",
        )
        with conn.cursor() as cur:
            cur.execute("SELECT current_database()")
            if cur.fetchone()[0] != TEST_DB:
                raise RuntimeError("Unexpected database")
            switch_role(cur, OWNER_ROLE)
            baseline = snapshot(cur)
            report("DATABASE_GUARD", "PASS", database=TEST_DB)
            source = SCHEMA.read_text(encoding="utf-8-sig")
            definitions = {
                match[1]: match[0] for match in re.finditer(
                    r"(?ms)^CREATE FUNCTION (v1_\w+)\b.*?\$\$;", source)
                if match[1] in PATCH_FUNCTIONS
            }
            if set(definitions) != PATCH_FUNCTIONS:
                raise ValueError("Missing or unexpected patch definitions")
            for name in ("v1_lock_team", "v1_lock_project",
                         "v1_team_members_guard", "v1_project_guard",
                         "v1_team_final_cardinality"):
                cur.execute(definitions[name].replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1))
            # Reapply the source's security block, including the pinned search_path
            # that CREATE OR REPLACE would otherwise clear on invoker functions.
            privilege_block = re.search(
                r"(?ms)^DO \$v1_privileges\$.*?^END \$v1_privileges\$;", source)
            if privilege_block is None:
                raise ValueError("Missing V1 function privilege block")
            cur.execute(privilege_block[0])
            cur.execute(render_rbac(conn), prepare=False)
            report("PATCH_AND_RBAC_POSTFLIGHT", "PASS", committed=False)
            cur.execute("""SELECT count(*), bool_and(prosecdef),
                bool_and(pg_get_userbyid(proowner)='project_owner'),
                bool_and(proconfig @> ARRAY['search_path=pg_catalog, public, pg_temp'])
                FROM pg_proc WHERE oid IN ('public.v1_lock_team(bigint)'::regprocedure,
                                          'public.v1_lock_project(bigint)'::regprocedure)""")
            if cur.fetchone() != (2, True, True, True):
                raise RuntimeError("Parent-lock helper security properties failed")
            cur.execute("""SELECT count(*) FROM pg_proc p
                JOIN pg_namespace n ON n.oid=p.pronamespace,
                LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) acl
                WHERE n.nspname='public' AND left(p.proname,3)='v1_'
                  AND acl.grantee=0 AND acl.privilege_type='EXECUTE'""")
            if cur.fetchone()[0] != 0:
                raise RuntimeError("PUBLIC can execute V1 functions")
            report("HELPER_OWNER_SEARCH_PATH_AND_PUBLIC_ACL", "PASS")
            token = uuid4().hex
            cur.execute("""INSERT INTO public.users(full_name,email,role)
                VALUES ('V1 Lock Regression Student',%s,'student') RETURNING id""",
                ("v1-lock-" + token + "@example.invalid",))
            actor = cur.fetchone()[0]
            report("ONE_STUDENT_FIXTURE_AS_OWNER", "PASS", committed=False)
            switch_role(cur, APP_ROLE)

            def set_actor(value):
                cur.execute("SELECT pg_catalog.set_config('app.actor_user_id',%s,true)", (str(value),))

            set_actor(actor)
            # Exercise both table row types and the member DELETE/CASCADE path.
            # Reuse the one student before creating the main Team/Project fixture.
            cur.execute("SAVEPOINT team_cascade_case")
            cur.execute("INSERT INTO public.teams(name) VALUES (%s) RETURNING id",
                        ("V1 Cardinality Cascade " + token,))
            cascade_team = cur.fetchone()[0]
            cur.execute("""INSERT INTO public.team_members(team_id,user_id,role)
                VALUES (%s,%s,'leader')""", (cascade_team, actor))
            cur.execute("SET CONSTRAINTS ALL IMMEDIATE")
            report("VALID_TEAM_AND_MEMBER_DEFERRED_ROW_TYPES", "PASS")
            cur.execute("SELECT public.v1_delete_team(%s)", (cascade_team,))
            cur.execute("SET CONSTRAINTS ALL IMMEDIATE")
            cur.execute("""SELECT NOT EXISTS(SELECT 1 FROM public.teams WHERE id=%s),
                NOT EXISTS(SELECT 1 FROM public.team_members WHERE team_id=%s)""",
                (cascade_team, cascade_team))
            if cur.fetchone() != (True, True):
                raise RuntimeError("Team deletion did not cascade cleanly")
            guard(cur, APP_ROLE)
            cur.execute("ROLLBACK TO SAVEPOINT team_cascade_case")
            cur.execute("RELEASE SAVEPOINT team_cascade_case")
            report("TEAM_DELETE_CASCADE_DEFERRED_CHECKS", "PASS")

            cur.execute("INSERT INTO public.teams(name) VALUES (%s) RETURNING id", ("V1 Lock Regression " + token,))
            team = cur.fetchone()[0]
            report("APP_INSERT_TEAM", "PASS", deferred_checks_pending=True)
            guard(cur, APP_ROLE)
            cur.execute("""INSERT INTO public.team_members(team_id,user_id,role)
                VALUES (%s,%s,'leader') RETURNING id""", (team, actor))
            cur.fetchone()
            report("APP_ADD_FIRST_LEADER", "PASS")
            guard(cur, APP_ROLE)
            cur.execute("""INSERT INTO public.projects(name,team_id,created_by)
                VALUES (%s,%s,%s) RETURNING id""", ("V1 Lock Project " + token, team, actor))
            project = cur.fetchone()[0]
            report("APP_CREATE_PROJECT", "PASS")
            cur.execute("SELECT public.v1_update_team_metadata(%s,%s,NULL)",
                        (team, "V1 Updated Team " + token))
            guard(cur, APP_ROLE)
            report("APP_TEAM_UPDATE_CONSTRAINT_TRIGGER", "PASS", deferred_checks_pending=True)
            for helper, parent in (("v1_lock_team", team), ("v1_lock_project", project)):
                cur.execute(sql.SQL("SELECT public.{}(%s)").format(sql.Identifier(helper)), (parent,))
                guard(cur, APP_ROLE)
                report("APP_CALL_" + helper, "PASS", caller_role_restored=True)
                for label, value, text in (("MISSING_ACTOR", "", "Verified transaction actor"),
                                           ("MALFORMED_ACTOR", "not-an-id", "Invalid actor context"),
                                           ("NONEXISTENT_ACTOR", -1, "Verified transaction actor must exist")):
                    set_actor(value)
                    expect_error(cur, helper + "_" + label,
                                 lambda: cur.execute(sql.SQL("SELECT public.{}(%s)").format(sql.Identifier(helper)), (parent,)),
                                 "42501", message=text)
                set_actor(actor)

            cur.execute("""SELECT bool_and(NOT has_any_column_privilege('project_app',c.oid,'UPDATE')
                AND NOT has_table_privilege('project_app',c.oid,'DELETE')
                AND NOT has_table_privilege('project_app',c.oid,'TRUNCATE'))
                FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='public' AND c.relkind='r'""")
            if cur.fetchone() != (True,):
                raise RuntimeError("App has forbidden direct DML privileges")
            report("APP_DIRECT_UPDATE_DELETE_TRUNCATE_REMAIN_DENIED", "PASS")
            for table, row_id in (("teams", team), ("projects", project)):
                expect_error(cur, "APP_RAW_LOCK_" + table,
                             lambda: cur.execute(sql.SQL("SELECT 1 FROM public.{} WHERE id=%s FOR UPDATE").format(sql.Identifier(table)), (row_id,)), "42501")
                expect_error(cur, "APP_RAW_UPDATE_" + table,
                             lambda: cur.execute(sql.SQL("UPDATE public.{} SET name=name WHERE id=%s").format(sql.Identifier(table)), (row_id,)), "42501")
            expect_error(cur, "APP_DELETE_PROJECT",
                         lambda: cur.execute("DELETE FROM public.projects WHERE id=%s", (project,)), "42501")
            expect_error(cur, "APP_CHECK_TEAM_NAME",
                         lambda: cur.execute("INSERT INTO public.teams(name) VALUES (' ' )"),
                         "23514", constraint="ck_teams_name")
            expect_error(cur, "APP_UNIQUE_PROJECT_PER_TEAM",
                         lambda: cur.execute("INSERT INTO public.projects(name,team_id,created_by) VALUES ('Duplicate',%s,%s)", (team, actor)),
                         "23505", constraint="projects_team_id_key")
            expect_error(cur, "APP_CREATED_BY_AUTHORIZATION_PRESERVED",
                         lambda: cur.execute("INSERT INTO public.projects(name,team_id,created_by) VALUES ('Wrong creator',%s,-1)", (team,)),
                         "P0001", message="Project creator must be current team leader")
            expect_error(cur, "APP_INVITATION_ADVISOR_RULE_PRESERVED",
                         lambda: cur.execute("INSERT INTO public.advisor_invitations(project_id,advisor_id,sent_by) VALUES (%s,%s,%s)", (project, actor, actor)),
                         "P0001", message="Invitation target must be advisor")
            expect_error(cur, "APP_SUBMISSION_ADVISOR_RULE_PRESERVED",
                         lambda: cur.execute("INSERT INTO public.project_submissions(project_id,submitted_by) VALUES (%s,%s)", (project, actor)),
                         "P0001", message="Accepted advisor required")

            def orphan_team():
                cur.execute("INSERT INTO public.teams(name) VALUES ('Deferred orphan fixture')")
                cur.execute("SET CONSTRAINTS ALL IMMEDIATE")

            expect_error(cur, "APP_DEFERRED_ORPHAN_TEAM_REJECTED", orphan_team,
                         "P0001", message="exactly one leader")
            switch_role(cur, OWNER_ROLE)
            expect_error(cur, "OWNER_PROJECT_DELETE_TRIGGER_R01",
                         lambda: cur.execute("DELETE FROM public.projects WHERE id=%s", (project,)),
                         "42501", message="R-01: Project deletion is forbidden")
            expect_error(cur, "OWNER_FOREIGN_KEY_USER_IN_USE",
                         lambda: cur.execute("DELETE FROM public.users WHERE id=%s", (actor,)),
                         "23001", constraint="team_members_user_id_fkey")
            switch_role(cur, APP_ROLE)
            cur.execute("SET CONSTRAINTS ALL IMMEDIATE")
            report("VALID_TEAM_PROJECT_DEFERRED_CHECKS", "PASS")
            passed = True
    except Exception as exc:
        # Never print connection errors, URLs, config values, or raw tracebacks.
        report("REGRESSION", "FAIL", error_type=type(exc).__name__,
               sqlstate=getattr(exc, "sqlstate", None))
    finally:
        if conn is not None:
            try:
                conn.rollback()
                report("ROLLBACK", "PASS", committed=False)
                if baseline is not None:
                    with conn.cursor() as cur:
                        cur.execute("SELECT current_database()")
                        if cur.fetchone()[0] != TEST_DB:
                            raise RuntimeError("Cleanup database guard failed")
                        cur.execute("SET TRANSACTION READ ONLY")
                        switch_role(cur, OWNER_ROLE)
                        after = snapshot(cur)
                        cleanup_ok = after == baseline
                        report("CATALOG_ACLS_AND_ALL_ROW_COUNTS_RESTORED",
                               "PASS" if cleanup_ok else "FAIL", row_counts=after[1],
                               identity_sequence_values_excluded=True)
            except Exception as exc:
                report("CLEANUP_VERIFICATION", "FAIL", error_type=type(exc).__name__)
            finally:
                conn.rollback()
                conn.close()
    report("RESULT", "PASS" if passed and cleanup_ok else "FAIL")
    return 0 if passed and cleanup_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
