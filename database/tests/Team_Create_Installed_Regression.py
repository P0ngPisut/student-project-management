"""Direct project_app connection, installed V1 only, fixtures always ROLLBACK.

No patch/GRANT/SET ROLE/owner fixture path is used by the application connection.
Owner-level R-01 proof is separate in V1_Baseline_Prepare --test-installed.
"""

import json

from backend.auth_store import TEST_DB, assert_auth_connection, open_auth_connection
from database.tests.Auth_Regression import snapshot, switch
from database.tools.Test_Database import connect_test_database
from database.tools.V1_Baseline_Prepare import inventory, require, team_cases


def baseline():
    conn = connect_test_database(readonly=True)
    try:
        with conn.cursor() as cur:
            switch(cur, "project_owner")
            require(inventory(cur) == (52, []))
            return snapshot(cur)
    finally:
        conn.rollback()
        conn.close()


def main():
    before = None
    conn = None
    passed = False
    cleanup = False
    try:
        before = baseline()
        conn = open_auth_connection()
        with conn.transaction(force_rollback=True):
            assert_auth_connection(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT current_database(),session_user,current_user")
                require(cur.fetchone() == (TEST_DB,"project_app","project_app"))
                print(json.dumps({"case":"DIRECT_APP_CONNECTION", "result":"PASS",
                    "database":TEST_DB, "session_user":"project_app", "current_user":"project_app",
                    "no_owner_role_switch":True}))
                team_cases(cur, owner_check=False)
                assert_auth_connection(conn)
                passed = True
    except Exception as exc:
        print(json.dumps({"case":"DIRECT_APP_TEAM_REGRESSION", "result":"FAIL",
            "error_type":type(exc).__name__, "sqlstate":getattr(exc,"sqlstate",None)}))
    finally:
        if conn is not None:
            conn.rollback()
            conn.close()
        if before is not None:
            try:
                cleanup = baseline() == before
                print(json.dumps({"case":"DIRECT_APP_FIXTURES_ROLLED_BACK",
                    "result":"PASS" if cleanup else "FAIL", "metadata_acl_row_counts_restored":cleanup,
                    "installed_functions_preserved":52, "sequence_values_excluded":True}))
            except Exception as exc:
                print(json.dumps({"case":"DIRECT_APP_CLEANUP", "result":"FAIL",
                    "error_type":type(exc).__name__}))
    return 0 if passed and cleanup else 1


if __name__ == "__main__":
    raise SystemExit(main())
