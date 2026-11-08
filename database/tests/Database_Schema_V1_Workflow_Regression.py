"""Exercise V1 workflows only in the TEST database, then always ROLLBACK.

Apply only the six approved function fixes and existing RBAC inside
the transaction. Create synthetic users as project_owner; exercise operations
as project_app. No business triggers are disabled. A final forced deferred check
must pass before the workflow can be considered valid. Sequences may advance.

Run from the repository root:
    python -B -m database.tests.Database_Schema_V1_Workflow_Regression
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
import re
import sys
from uuid import uuid4

import psycopg
from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.tests.Database_Schema_V1_RBAC_Lock_Regression import (
    APP_ROLE, BASE, OWNER_ROLE, PATCH_FUNCTIONS as LOCK_PATCH_FUNCTIONS, SCHEMA, TEST_DB,
    guard, render_rbac, report, snapshot, switch_role,
)

PATCH_FUNCTIONS = LOCK_PATCH_FUNCTIONS | {"v1_in_progress_has_assignee"}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


class Cases:
    def __init__(self, cur):
        self.cur = cur
        self.current = "SETUP"
        self.passed = 0

    def begin(self, name):
        self.current = name
        guard(self.cur, APP_ROLE)

    def ok(self, **details):
        self.passed += 1
        report(self.current, "PASS", **details)

    def scalar(self, query, params=None):
        self.cur.execute(query, params)
        return self.cur.fetchone()[0]

    def actor(self, user_id):
        self.scalar("SELECT pg_catalog.set_config('app.actor_user_id',%s,true)", (str(user_id),))

    @contextmanager
    def isolated(self):
        # Nested SAVEPOINTs use different names from negative test cases.
        self.cur.execute("SAVEPOINT workflow_isolated")
        try:
            yield
        finally:
            self.cur.execute("ROLLBACK TO SAVEPOINT workflow_isolated")
            self.cur.execute("RELEASE SAVEPOINT workflow_isolated")

    def error(self, name, query, params, state, *, constraint=None, message=None, column=None):
        self.begin(name)
        self.cur.execute("SAVEPOINT workflow_expected_error")
        caught = None
        matched = False
        try:
            self.cur.execute(query, params)
        except psycopg.Error as exc:
            caught = exc
            matched = (exc.sqlstate == state
                       and (constraint is None or exc.diag.constraint_name == constraint)
                       and (message is None or message in (exc.diag.message_primary or ""))
                       and (column is None or exc.diag.column_name == column))
        finally:
            self.cur.execute("ROLLBACK TO SAVEPOINT workflow_expected_error")
            self.cur.execute("RELEASE SAVEPOINT workflow_expected_error")
        if not matched:
            if caught is not None:
                raise caught
            raise RuntimeError("Expected rejection did not occur: " + name)
        self.ok(sqlstate=caught.sqlstate, constraint=caught.diag.constraint_name,
                column=caught.diag.column_name)


def run_workflow(cur):
    checks = Cases(cur)
    token = uuid4().hex
    users = {}
    for label, role in (("leader", "student"), ("member", "student"),
                        ("advisor", "advisor"), ("committee_a", "advisor"),
                        ("committee_b", "advisor"), ("committee_c", "advisor"),
                        ("coordinator", "coordinator")):
        guard(cur, OWNER_ROLE)
        users[label] = checks.scalar("""INSERT INTO public.users(full_name,email,role)
            VALUES (%s,%s,%s) RETURNING id""",
            ("V1 Workflow " + label, "v1-workflow-" + token + "-" + label + "@example.invalid", role))
    report("SYNTHETIC_USERS_AS_OWNER", "PASS", count=len(users), committed=False)
    switch_role(cur, APP_ROLE)
    try:
        checks.begin("APP_TEAM_PROJECT_AND_DEFERRED_TEAM_CHECKS")
        checks.actor(users["leader"])
        team = checks.scalar("INSERT INTO public.teams(name) VALUES (%s) RETURNING id", ("V1 Workflow " + token,))
        leader_member = checks.scalar("""INSERT INTO public.team_members(team_id,user_id,role)
            VALUES (%s,%s,'leader') RETURNING id""", (team, users["leader"]))
        member = checks.scalar("""INSERT INTO public.team_members(team_id,user_id,role)
            VALUES (%s,%s,'member') RETURNING id""", (team, users["member"]))
        project = checks.scalar("""INSERT INTO public.projects(name,team_id,created_by)
            VALUES ('V1 Workflow Project',%s,%s) RETURNING id""", (team, users["leader"]))
        cur.execute("SET CONSTRAINTS ALL IMMEDIATE")
        cur.execute("SET CONSTRAINTS ALL DEFERRED")
        checks.ok()

        checks.begin("LEADER_INVITES_ADVISOR")
        invitation = checks.scalar("""INSERT INTO public.advisor_invitations(project_id,advisor_id,sent_by)
            VALUES (%s,%s,%s) RETURNING id""", (project, users["advisor"], users["leader"]))
        checks.ok()
        checks.error("DUPLICATE_ACTIVE_INVITATION", """INSERT INTO public.advisor_invitations(project_id,advisor_id,sent_by)
            VALUES (%s,%s,%s)""", (project, users["committee_a"], users["leader"]),
            "23505", constraint="uq_invitations_active_project")
        checks.error("LEADER_CANNOT_ACCEPT_AS_ADVISOR", "SELECT public.v1_resolve_invitation(%s,'accepted')",
                     (invitation,), "P0001", message="Only invited advisor may respond")
        checks.begin("INVITED_ADVISOR_ACCEPTS")
        checks.actor(users["advisor"])
        cur.execute("SELECT public.v1_resolve_invitation(%s,'accepted')", (invitation,))
        require(checks.scalar("SELECT status FROM public.advisor_invitations WHERE id=%s", (invitation,)) == "accepted", "Invitation status")
        checks.ok()

        checks.begin("LEADER_SUBMITS_SNAPSHOT")
        checks.actor(users["leader"])
        submission = checks.scalar("""INSERT INTO public.project_submissions(project_id,submitted_by)
            VALUES (%s,%s) RETURNING id""", (project, users["leader"]))
        require(checks.scalar("SELECT snapshot_name FROM public.project_submissions WHERE id=%s", (submission,)) == "V1 Workflow Project", "Submission snapshot")
        checks.ok(deferred_checks_pending=True)
        checks.error("MISSING_FILE_DEFERRED_REJECTION", "SET CONSTRAINTS c_submission_requires_file IMMEDIATE", None,
                     "P0001", message="must have exactly one file at COMMIT")
        upload = """INSERT INTO public.project_submission_files(submission_id,file_data,original_filename,mime_type)
            VALUES (%s,%s,'fixture.pdf','application/pdf') RETURNING id"""
        for size in (0, 4_000_001):
            checks.error("FILE_SIZE_REJECT_" + str(size), upload, (submission, b"x" * size),
                         "23514", constraint="ck_submission_file_size")
        for size in (1, 4_000_000):
            checks.begin("FILE_SIZE_ACCEPT_" + str(size))
            with checks.isolated():
                checks.scalar(upload, (submission, b"x" * size))
                cur.execute("SET CONSTRAINTS c_submission_requires_file IMMEDIATE")
                checks.ok(scope="database byte length, not file authenticity")
        checks.begin("FILE_AND_SUBMISSION_DEFERRED_VALID")
        checks.scalar(upload, (submission, b"%PDF-database-test-fixture"))
        cur.execute("SET CONSTRAINTS ALL IMMEDIATE")
        cur.execute("SET CONSTRAINTS ALL DEFERRED")
        checks.ok()
        checks.error("SECOND_FILE_UNIQUE", upload, (submission, b"x"), "23505",
                     constraint="project_submission_files_submission_id_key")
        checks.error("LEADER_CANNOT_REVIEW", "SELECT public.v1_review_submission(%s,'approved',NULL)",
                     (submission,), "P0001", message="Only accepted project advisor may review")
        checks.actor(users["advisor"])
        checks.error("REVISION_REQUIRES_COMMENT", "SELECT public.v1_review_submission(%s,'revision_requested','  ')",
                     (submission,), "P0001", message="Revision request must include real comment")
        checks.begin("ADVISOR_APPROVES_SUBMISSION")
        cur.execute("SELECT public.v1_review_submission(%s,'approved',NULL)", (submission,))
        checks.ok()

        checks.error("NONCOORDINATOR_CANNOT_APPOINT", "SELECT public.v1_appoint_committee(%s,%s)",
                     (project, users["committee_a"]), "42501", message="Coordinator role required")
        checks.actor(users["coordinator"])
        checks.error("PROJECT_ADVISOR_CANNOT_JOIN_COMMITTEE", "SELECT public.v1_appoint_committee(%s,%s)",
                     (project, users["advisor"]), "P0001", message="cannot serve on own committee")
        checks.begin("COORDINATOR_APPOINTS_THREE_ADVISORS")
        labels = ("committee_a", "committee_b", "committee_c")
        assignments = [checks.scalar("SELECT public.v1_appoint_committee(%s,%s)", (project, users[label])) for label in labels]
        checks.ok()
        checks.error("COORDINATOR_CANNOT_VOTE_AS_ADVISOR", "SELECT public.v1_cast_vote(%s,%s,'approved',NULL)",
                     (submission, assignments[0]), "P0001", message="Only appointed committee member may vote")
        checks.actor(users["committee_a"])
        checks.begin("FIRST_COMMITTEE_VOTE")
        checks.scalar("SELECT public.v1_cast_vote(%s,%s,'approved',NULL)", (submission, assignments[0]))
        checks.ok()
        checks.error("DUPLICATE_VOTE", "SELECT public.v1_cast_vote(%s,%s,'approved',NULL)",
                     (submission, assignments[0]), "23505", constraint="uq_committee_vote_submission_member")
        checks.actor(users["coordinator"])
        checks.error("ROSTER_LOCKED_AFTER_FIRST_VOTE", "SELECT public.v1_remove_committee(%s)",
                     (assignments[2],), "P0001", message="locked permanently after first vote")
        checks.begin("DECISION_WAITS_FOR_ALL_VOTES")
        checks.actor(users["committee_b"])
        checks.scalar("SELECT public.v1_cast_vote(%s,%s,'approved',NULL)", (submission, assignments[1]))
        require(checks.scalar("SELECT public.v1_topic_decision(%s)", (submission,)) is None, "Decision prematurely final")
        checks.ok()
        checks.actor(users["committee_c"])
        checks.error("REVISION_VOTE_REQUIRES_COMMENT", "SELECT public.v1_cast_vote(%s,%s,'revision_requested','  ')",
                     (submission, assignments[2]), "P0001", message="Revision vote requires real comment")
        checks.begin("TWO_OF_THREE_APPROVE_AFTER_ALL_VOTES")
        checks.scalar("SELECT public.v1_cast_vote(%s,%s,'revision_requested','Please revise')", (submission, assignments[2]))
        require(checks.scalar("SELECT public.v1_topic_decision(%s)", (submission,)) == "approved", "Majority decision")
        cur.execute("SET CONSTRAINTS ALL IMMEDIATE")
        cur.execute("SET CONSTRAINTS ALL DEFERRED")
        checks.ok()

        checks.actor(users["committee_a"])
        evaluate = "SELECT public.v1_record_evaluation(%s,%s,%s)"
        checks.error("EVALUATION_REQUIRES_COMPLETED_MILESTONE", evaluate,
                     (assignments[0], 50, "Test"), "P0001", message="At least one completed milestone required")
        checks.begin("LEADER_CREATES_MILESTONE_TASK")
        checks.actor(users["leader"])
        today = checks.scalar("SELECT (now() AT TIME ZONE 'Asia/Bangkok')::date")
        due = today + timedelta(days=14)
        task_due = today + timedelta(days=7)
        milestone = checks.scalar("SELECT public.v1_create_milestone(%s,'Workflow milestone',NULL,%s)", (project, due))
        task = checks.scalar("SELECT public.v1_create_task(%s,'Workflow task',NULL,%s)", (milestone, task_due))
        checks.ok(deferred_checks_pending=True)
        checks.begin("DEFERRED_TASK_INSERT_NOT_STARTED_WITHOUT_ASSIGNEE")
        cur.execute("SET CONSTRAINTS ALL IMMEDIATE")
        cur.execute("SET CONSTRAINTS ALL DEFERRED")
        checks.ok()
        checks.begin("DEFERRED_TASK_DELETE_CASCADE")
        with checks.isolated():
            checks.scalar("SELECT public.v1_assign_task(%s,%s)", (task, member))
            cur.execute("SELECT public.v1_delete_task(%s)", (task,))
            cur.execute("SET CONSTRAINTS ALL IMMEDIATE")
            require(checks.scalar("SELECT count(*) FROM public.tasks WHERE id=%s", (task,)) == 0, "Task deletion")
            require(checks.scalar("SELECT count(*) FROM public.task_assignees WHERE task_id=%s", (task,)) == 0, "Task cascade")
            checks.ok()
        for date, label in ((today - timedelta(days=1), "PAST"), (due + timedelta(days=1), "AFTER_MILESTONE")):
            checks.error("TASK_DATE_REJECT_" + label, "SELECT public.v1_create_task(%s,'Invalid date task',NULL,%s)",
                         (milestone, date), "P0001", message="Invalid Task due_date")
        checks.error("MILESTONE_SHORTEN_D01", "SELECT public.v1_update_milestone(%s,'Workflow milestone',NULL,%s)",
                     (milestone, today), "P0001", message="D-01:")
        for status, phrase in (("in_progress", "In-progress Task requires"), ("completed", "Task completion requires")):
            checks.error("TASK_REQUIRES_ASSIGNEE_" + status.upper(), "SELECT public.v1_set_task_status(%s,%s)",
                         (task, status), "P0001", message=phrase)
        checks.begin("ASSIGN_AND_START_TASK_UPDATES_MILESTONE")
        checks.scalar("SELECT public.v1_assign_task(%s,%s)", (task, member))
        checks.actor(users["member"])
        cur.execute("SELECT public.v1_set_task_status(%s,'in_progress')", (task,))
        require(checks.scalar("SELECT status FROM public.milestones WHERE id=%s", (milestone,)) == "in_progress", "Milestone status sync")
        cur.execute("SET CONSTRAINTS ALL IMMEDIATE")
        cur.execute("SET CONSTRAINTS ALL DEFERRED")
        checks.ok(deferred_checks_forced=True)
        # All task events were checked above. Only the assignee DELETE event
        # remains pending here, so this exercises the other trigger row type.
        checks.begin("DEFERRED_REMOVE_AND_REASSIGN_LAST_ASSIGNEE")
        with checks.isolated():
            checks.actor(users["leader"])
            cur.execute("SELECT public.v1_unassign_task(%s,%s)", (task, member))
            require(checks.scalar("SELECT count(*) FROM public.task_assignees WHERE task_id=%s", (task,)) == 0, "Last assignee removal")
            checks.error("DEFERRED_LAST_ASSIGNEE_REMOVAL_REJECTED", "SET CONSTRAINTS ALL IMMEDIATE", None,
                         "P0001", message="must have an assignee at COMMIT")
            checks.begin("DEFERRED_REASSIGN_BEFORE_VALIDATION_ACCEPTED")
            checks.scalar("SELECT public.v1_assign_task(%s,%s)", (task, member))
            cur.execute("SET CONSTRAINTS ALL IMMEDIATE")
            checks.ok()
        checks.begin("DEFERRED_REMOVE_ONE_OF_TWO_ASSIGNEES")
        with checks.isolated():
            checks.actor(users["leader"])
            checks.scalar("SELECT public.v1_assign_task(%s,%s)", (task, leader_member))
            cur.execute("SELECT public.v1_unassign_task(%s,%s)", (task, member))
            cur.execute("SET CONSTRAINTS ALL IMMEDIATE")
            require(checks.scalar("SELECT count(*) FROM public.task_assignees WHERE task_id=%s", (task,)) == 1, "Remaining assignee")
            checks.ok()
        checks.error("LAST_ASSIGNEE_CANNOT_EXIT_IN_PROGRESS", "SELECT public.v1_exit_team_member(%s)",
                     (member,), "P0001", message="would leave in-progress Task")
        checks.begin("COMPLETE_TASK_UPDATES_MILESTONE")
        cur.execute("SELECT public.v1_set_task_status(%s,'completed')", (task,))
        cur.execute("""SELECT t.status,t.completed_at IS NOT NULL,m.status,m.completed_at IS NOT NULL
            FROM public.tasks t JOIN public.milestones m ON m.id=t.milestone_id WHERE t.id=%s""", (task,))
        require(cur.fetchone() == ("completed", True, "completed", True), "Completion sync")
        checks.ok(deferred_checks_pending=True)
        checks.error("MEMBER_CANNOT_REOPEN_COMPLETED_TASK", "SELECT public.v1_set_task_status(%s,'in_progress')",
                     (task,), "P0001", message="Only leader may reopen")

        checks.actor(users["advisor"])
        checks.error("OTHER_ADVISOR_CANNOT_SCORE", evaluate, (assignments[0], 50, "Test"),
                     "P0001", message="Only assigned advisor may submit own evaluation")
        checks.actor(users["committee_a"])
        for score in (-1, 101):
            checks.error("SCORE_REJECT_" + str(score), evaluate, (assignments[0], score, "Test"),
                         "23514", constraint="ck_evaluations_score")
        checks.error("SCORE_REJECT_NULL", evaluate, (assignments[0], None, "Test"), "23502", column="score")
        checks.error("SCORE_COMMENT_REJECT_BLANK", evaluate, (assignments[0], 50, " \t\n"),
                     "23514", constraint="ck_evaluations_comment")
        checks.error("SCORE_COMMENT_REJECT_NULL", evaluate, (assignments[0], 50, None), "23502", column="comment")
        for score in (0, 50, 100):
            checks.begin("SCORE_ACCEPT_" + str(score))
            with checks.isolated():
                evaluation = checks.scalar(evaluate, (assignments[0], score, "  Test evaluation  "))
                cur.execute("SELECT score,comment FROM public.committee_evaluations WHERE id=%s", (evaluation,))
                require(cur.fetchone() == (score, "Test evaluation"), "Stored score/comment")
                cur.execute("SET CONSTRAINTS ALL IMMEDIATE")
                cur.execute("SET CONSTRAINTS ALL DEFERRED")
                checks.ok(deferred_checks_forced=True)
                if score != 50:
                    continue
                checks.error("DUPLICATE_EVALUATION", evaluate, (assignments[0], 75, "Second"),
                             "23505", constraint="committee_evaluations_committee_assignment_id_key")
                checks.actor(users["leader"])
                checks.error("FIRST_EVALUATION_LOCKS_MILESTONE", "SELECT public.v1_update_milestone(%s,'Changed',NULL,%s)",
                             (milestone, due), "P0001", message="Milestones locked after first committee evaluation")
                checks.error("FIRST_EVALUATION_LOCKS_TASK", "SELECT public.v1_set_task_status(%s,'in_progress')",
                             (task,), "P0001", message="Tasks locked after first committee evaluation")
                checks.error("FIRST_EVALUATION_LOCKS_UNASSIGNMENT", "SELECT public.v1_unassign_task(%s,%s)",
                             (task, member), "P0001", message="Unassignment locked")
                checks.begin("COMPLETED_MEMBER_EXIT_AFTER_EVALUATION_RECORDS_HISTORY")
                checks.actor(users["member"])
                cur.execute("SELECT public.v1_exit_team_member(%s)", (member,))
                require(checks.scalar("SELECT count(*) FROM public.team_members WHERE id=%s", (member,)) == 0, "Member exit")
                require(checks.scalar("SELECT count(*) FROM public.task_assignees WHERE task_id=%s", (task,)) == 0, "Assignment cleanup")
                require(checks.scalar("SELECT count(*) FROM public.task_assignment_history WHERE task_id=%s AND user_id=%s",
                                     (task, users["member"])) == 1, "Unassignment history")
                cur.execute("SET CONSTRAINTS ALL IMMEDIATE")
                checks.ok(deferred_checks_forced=True)

        checks.begin("FINAL_ALL_DEFERRED_CONSTRAINTS")
        cur.execute("SET CONSTRAINTS ALL IMMEDIATE")
        checks.ok()
        return checks.passed
    except Exception as exc:
        details = {"type": type(exc).__name__, "statement_cases_passed": checks.passed}
        if isinstance(exc, psycopg.Error):
            details.update(sqlstate=exc.sqlstate, message=exc.diag.message_primary,
                           constraint=exc.diag.constraint_name, context=exc.diag.context)
        report(checks.current, "FAIL", **details)
        raise


def main():
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
            require(cur.fetchone()[0] == TEST_DB, "Unexpected database")
            switch_role(cur, OWNER_ROLE)
            baseline = snapshot(cur)
            report("DATABASE_BASELINE", "PASS", database=TEST_DB, row_counts=baseline[1])
            source = SCHEMA.read_text(encoding="utf-8-sig")
            definitions = {match[1]: match[0] for match in re.finditer(
                r"(?ms)^CREATE FUNCTION (v1_\w+)\b.*?\$\$;", source)
                if match[1] in PATCH_FUNCTIONS}
            require(set(definitions) == PATCH_FUNCTIONS, "Missing approved function definitions")
            for name in ("v1_lock_team", "v1_lock_project", "v1_team_members_guard",
                         "v1_project_guard", "v1_team_final_cardinality",
                         "v1_in_progress_has_assignee"):
                cur.execute(definitions[name].replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1))
            block = re.search(r"(?ms)^DO \$v1_privileges\$.*?^END \$v1_privileges\$;", source)
            require(block is not None, "Missing function security block")
            cur.execute(block[0])
            cur.execute(render_rbac(conn), prepare=False)
            report("APPROVED_PATCH_AND_RBAC_POSTFLIGHT", "PASS", committed=False)
            count = run_workflow(cur)
            passed = True
            report("WORKFLOW_WITH_FORCED_DEFERRED_CHECKS", "PASS", cases=count)
    except Exception as exc:
        # Never print connection strings, configuration values, or raw traceback.
        report("WORKFLOW_SUITE", "FAIL", type=type(exc).__name__, sqlstate=getattr(exc, "sqlstate", None))
    finally:
        if conn is not None:
            try:
                conn.rollback()
                if baseline is not None:
                    with conn.cursor() as cur:
                        cur.execute("SET TRANSACTION READ ONLY")
                        cur.execute("SELECT current_database()")
                        require(cur.fetchone()[0] == TEST_DB, "Unexpected cleanup database")
                        switch_role(cur, OWNER_ROLE)
                        restored = snapshot(cur)
                        cleanup_ok = restored == baseline
                        report("ROLLBACK_RESTORED_BASELINE", "PASS" if cleanup_ok else "FAIL",
                               definitions_acl_owners_triggers_unchanged=restored[0] == baseline[0],
                               row_counts=restored[1], sequence_values_may_advance=True)
                        conn.rollback()
            except Exception as exc:
                report("ROLLBACK_VERIFICATION", "FAIL", type=type(exc).__name__, sqlstate=getattr(exc, "sqlstate", None))
            finally:
                conn.close()
    report("CONCURRENCY", "NOT_RUN", reason="This suite covers single-session rollback regression only")
    return 0 if passed and cleanup_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
