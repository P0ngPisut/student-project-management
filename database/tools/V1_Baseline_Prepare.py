"""Inspect/rehearse the existing V1 baseline repair. There is NO apply mode.

Default/--check is read-only. --rehearse runs reviewed DDL + test fixtures as
non-superuser effective roles and always restores the complete baseline.
--test-installed tests an already-correct baseline without patching functions.
An optional --workflow runs the existing 57-case suite inside the same rollback.
The separately approved installer is V1_Baseline_Install; this tool never commits.
"""

import argparse
import hashlib
import json
import re
from uuid import uuid4

import psycopg

from backend.auth_security import hash_password
from backend.auth_store import assert_auth_connection
from database.tests.Auth_Regression import snapshot, switch, validate_installed_auth
from database.tools.Test_Database import BASE, TEST_DB, connect_test_database

SOURCE = BASE / "database/schema/Database_Schema_V1_A02_A05_REVIEW_DRAFT.sql"
REVIEW = BASE / "database/migrations/001_v1_baseline_repair_review.sql"
SOURCE_SHA = "770487d56c7ca71887fb91a84e254b59d40cfa949700e8a3b188c69246baa5bc"
REVIEW_SHA = "773cc7f7cd7f7c8d2e368cbd3ba6bdf87fd74b4a8b11f0efaa24b7987898fa70"
PATCH_NAMES = {"v1_lock_team", "v1_lock_project", "v1_team_members_guard",
               "v1_project_guard", "v1_team_final_cardinality", "v1_in_progress_has_assignee"}


def emit(case, result="PASS", **details):
    print(json.dumps({"case": case, "result": result, **details}))


def require(condition):
    if not condition:
        raise RuntimeError("V1 readiness assertion failed")


def sources():
    raw = SOURCE.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == SOURCE_SHA)
    definitions = {m[1]: m[0] for m in re.finditer(
        r"(?ms)^CREATE FUNCTION (v1_\w+)\b.*?\$\$;", raw.decode("utf-8-sig"))}
    require(len(definitions) == 52)
    return definitions


def inventory(cur):
    expected = sources()
    cur.execute("""SELECT p.proname,p.prosrc,p.prosecdef,p.provolatile,
        pg_get_userbyid(p.proowner),p.proconfig FROM pg_proc p
        JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname='public' AND left(p.proname,3)='v1_' ORDER BY 1""")
    rows = cur.fetchall()
    require(len({row[0] for row in rows}) == len(rows))
    live = {row[0]: row for row in rows}
    differences = []
    for name, definition in expected.items():
        if name not in live:
            differences.append({"function": name, "difference": "missing"})
            continue
        row = live[name]
        body = re.search(r"AS \$\$(.*)\$\$;", definition, re.S)[1]
        header = definition[:definition.index("$$")]
        volatility = "i" if "IMMUTABLE" in header else "s" if "STABLE" in header else "v"
        for field, actual, wanted in (
            ("body", row[1].strip(), body.strip()),
            ("security_definer", row[2], "SECURITY DEFINER" in header),
            ("volatility", row[3], volatility),
            ("owner", row[4], "project_owner"),
            ("search_path", row[5], ["search_path=pg_catalog, public, pg_temp"]),
        ):
            if actual != wanted:
                differences.append({"function": name, "difference": field})
    for name in sorted(set(live) - set(expected)):
        differences.append({"function": name, "difference": "unexpected"})
    return len(rows), differences


def review_body():
    raw = REVIEW.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == REVIEW_SHA)
    body = raw.decode("utf-8")
    for boundary in ("BEGIN", "ROLLBACK"):
        body, count = re.subn(rf"(?m)^{boundary};[ \t]*$", "", body)
        require(count == 1)
    require(re.search(r"(?im)^\s*COMMIT\b", body) is None)
    return body


def app_permissions(cur):
    switch(cur, "project_app")
    assert_auth_connection(cur.connection)
    cur.execute("""SELECT has_schema_privilege(current_user,'public','USAGE'),
        has_schema_privilege(current_user,'public','CREATE'),
        has_function_privilege(current_user,'public.v1_lock_team(bigint)','EXECUTE'),
        has_function_privilege(current_user,'public.v1_lock_project(bigint)','EXECUTE')""")
    require(cur.fetchone() == (True, False, True, True))
    cur.execute("""SELECT c.relname,has_table_privilege(current_user,c.oid,'SELECT'),
        has_any_column_privilege(current_user,c.oid,'INSERT')
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relname IN ('users','teams','team_members','projects')
        ORDER BY 1""")
    require(cur.fetchall() == [("projects", True, True), ("team_members", True, True),
                               ("teams", True, True), ("users", True, False)])
    cur.execute("""SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relkind='r'
          AND (has_any_column_privilege(current_user,c.oid,'UPDATE')
               OR has_table_privilege(current_user,c.oid,'DELETE')
               OR has_table_privilege(current_user,c.oid,'TRUNCATE'))""")
    require(cur.fetchone() == (0,))
    switch(cur, "project_owner")
    cur.execute("""SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace,
        LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) acl
        WHERE n.nspname='public' AND left(p.proname,3)='v1_'
          AND acl.grantee=0 AND acl.privilege_type='EXECUTE'""")
    require(cur.fetchone() == (0,))
    emit("EFFECTIVE_APP_PRIVILEGES_AND_PUBLIC_ACL")


def expected_error(cur, name, operation, state, constraint=None):
    cur.execute("SAVEPOINT team_expected_error")
    caught = None
    try:
        operation()
    except psycopg.Error as exc:
        caught = (exc.sqlstate, exc.diag.constraint_name)
    finally:
        cur.execute("ROLLBACK TO SAVEPOINT team_expected_error")
        cur.execute("RELEASE SAVEPOINT team_expected_error")
    require(caught is not None and caught[0] == state
            and (constraint is None or caught[1] == constraint))
    emit(name, sqlstate=state, constraint=constraint)


def team_cases(cur, *, owner_check=True):
    if owner_check:
        switch(cur, "project_app")
    assert_auth_connection(cur.connection)
    token = uuid4().hex
    cur.execute("SELECT auth.register_student(%s,%s,%s)", (
        "Team readiness fixture", "team-ready-" + token + "@example.test",
        hash_password("TeamFixtureA1")))
    actor = cur.fetchone()[0]
    cur.execute("SELECT set_config('app.actor_user_id',%s,true)", (str(actor),))
    cur.execute("INSERT INTO public.teams(name,description) VALUES (%s,%s) RETURNING id,name,description",
                ("  Team " + token + "  ", "   "))
    team, name, description = cur.fetchone()
    require(name == "Team " + token and description is None)
    emit("TEAM_INSERT_AND_NORMALIZATION")

    def missing_actor():
        cur.execute("SELECT set_config('app.actor_user_id','',true)")
        cur.execute("INSERT INTO public.team_members(team_id,user_id,role) VALUES (%s,%s,'leader')", (team, actor))
    expected_error(cur, "FIRST_LEADER_WITHOUT_ACTOR_REJECTED", missing_actor, "42501")
    cur.execute("INSERT INTO public.team_members(team_id,user_id,role) VALUES (%s,%s,'leader')", (team, actor))
    cur.execute("SET CONSTRAINTS ALL IMMEDIATE")
    emit("FIRST_LEADER_AND_FORCED_DEFERRED_CHECKS")
    expected_error(cur, "RAW_PARENT_ROW_LOCK_STILL_DENIED",
                   lambda: cur.execute("SELECT 1 FROM public.teams WHERE id=%s FOR UPDATE", (team,)), "42501")

    def duplicate_membership():
        cur.execute("SET CONSTRAINTS ALL DEFERRED")
        cur.execute("INSERT INTO public.teams(name) VALUES ('Duplicate fixture') RETURNING id")
        other = cur.fetchone()[0]
        cur.execute("INSERT INTO public.team_members(team_id,user_id,role) VALUES (%s,%s,'leader')", (other, actor))
    expected_error(cur, "SECOND_TEAM_MEMBERSHIP_REJECTED", duplicate_membership,
                   "23505", "team_members_user_id_key")

    def orphan_team():
        cur.execute("SET CONSTRAINTS ALL DEFERRED")
        cur.execute("INSERT INTO public.teams(name) VALUES ('Orphan fixture')")
        cur.execute("SET CONSTRAINTS ALL IMMEDIATE")
    expected_error(cur, "ORPHAN_TEAM_REJECTED_WHEN_DEFERRED_FORCED", orphan_team, "P0001")
    cur.execute("INSERT INTO public.projects(name,team_id,created_by) VALUES ('Team readiness Project',%s,%s) RETURNING id", (team, actor))
    project = cur.fetchone()[0]
    cur.execute("SET CONSTRAINTS ALL IMMEDIATE")
    emit("LEADER_CREATES_PROJECT")
    expected_error(cur, "APP_PROJECT_DELETE_DENIED",
                   lambda: cur.execute("DELETE FROM public.projects WHERE id=%s", (project,)), "42501")
    if owner_check:
        switch(cur, "project_owner")
        expected_error(cur, "OWNER_PROJECT_DELETE_REJECTED_BY_R01",
                       lambda: cur.execute("DELETE FROM public.projects WHERE id=%s", (project,)), "42501")
    emit("TEAM_READINESS_CASES", cases=9 if owner_check else 8,
         effective_app_role_not_superuser=True, owner_trigger_case_included=owner_check)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true")
    group.add_argument("--rehearse", action="store_true")
    group.add_argument("--test-installed", action="store_true")
    parser.add_argument("--workflow", action="store_true")
    args = parser.parse_args()
    if args.workflow and not (args.rehearse or args.test_installed):
        parser.error("--workflow requires --rehearse or --test-installed")
    writing = args.rehearse or args.test_installed
    conn = None
    baseline = None
    passed = False
    cleanup = False
    try:
        conn = connect_test_database(readonly=not writing)
        conn.rollback()
        with conn.transaction(force_rollback=True):
            with conn.cursor() as cur:
                switch(cur, "project_owner")
                baseline = snapshot(cur)
                validate_installed_auth(cur)
                count, differences = inventory(cur)
                emit("V1_SOURCE_COMPARISON", "NOT_READY" if differences else "PASS",
                     database=TEST_DB, functions=count, differences=differences, readonly=not writing)
                if args.rehearse:
                    require({row["function"] for row in differences} == PATCH_NAMES)
                    cur.execute(review_body(), prepare=False)
                    require(inventory(cur) == (52, []))
                    emit("SIX_SOURCE_FUNCTIONS_REHEARSED", functions=52, committed=False)
                if writing:
                    require(inventory(cur) == (52, []))
                    app_permissions(cur)
                    prepared = snapshot(cur)
                    cur.execute("SAVEPOINT team_fixtures")
                    team_cases(cur)
                    cur.execute("ROLLBACK TO SAVEPOINT team_fixtures")
                    cur.execute("RELEASE SAVEPOINT team_fixtures")
                    switch(cur, "project_owner")
                    require(snapshot(cur) == prepared)
                    emit("TEAM_FIXTURES_ROLLED_BACK")
                    if args.workflow:
                        from database.tests.Database_Schema_V1_Workflow_Regression import run_workflow
                        switch(cur, "project_owner")
                        cur.execute("SET CONSTRAINTS ALL DEFERRED")
                        count = run_workflow(cur)
                        require(count == 57)
                        emit("EXISTING_WORKFLOW_REGRESSION", cases=count)
                    passed = True
                else:
                    if not differences:
                        app_permissions(cur)
                    passed = not differences
    except Exception as exc:
        emit("V1_PREPARATION", "FAIL", error_type=type(exc).__name__, sqlstate=getattr(exc, "sqlstate", None))
    finally:
        if conn is not None:
            try:
                conn.rollback()
                if baseline is not None:
                    conn.execute("SET TRANSACTION READ ONLY")
                    with conn.cursor() as cur:
                        switch(cur, "project_owner")
                        cleanup = snapshot(cur) == baseline
                    emit("FULL_BASELINE_RESTORED", "PASS" if cleanup else "FAIL",
                         metadata_owners_acl_row_counts_restored=cleanup,
                         sequence_values_excluded=True, committed=False)
            except Exception as exc:
                cleanup = False
                emit("ROLLBACK_VERIFICATION", "FAIL", error_type=type(exc).__name__,
                     sqlstate=getattr(exc, "sqlstate", None))
            finally:
                conn.rollback()
                conn.close()
    return 0 if passed and cleanup else 1


if __name__ == "__main__":
    raise SystemExit(main())
