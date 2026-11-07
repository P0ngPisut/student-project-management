"""Real app-password connection + Auth/Team HTTP smoke, all fixtures ROLLBACK.

TestClient runs ASGI in process, not live TCP. No schema/grant changes and no
owner role switch in the request connection; metadata snapshots are separate.
"""

import json
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.auth_api import CSRF_COOKIE, CSRF_HEADER, get_auth_uow
from backend.auth_store import TEST_DB, assert_auth_connection, open_auth_connection, transaction_on
from backend.main import create_app
from backend.team_api import get_team_uow
from backend.team_store import team_transaction_on
from backend.project_api import get_project_uow
from backend.project_store import project_transaction_on
from backend.invitation_api import get_invitation_uow
from backend.invitation_store import invitation_transaction_on
from database.tests.Team_Create_Installed_Regression import baseline


def check(condition):
    if not condition:
        raise RuntimeError("Direct app Team HTTP smoke assertion failed")


def emit(case, **details):
    print(json.dumps({"case":case, "result":"PASS", **details}))


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
            check(conn.execute("SELECT current_database(),session_user,current_user").fetchone()
                  == (TEST_DB,"project_app","project_app"))
            emit("TEAM_HTTP_DIRECT_APP_IDENTITY", database=TEST_DB, session_user="project_app", current_user="project_app")
            app = create_app()
            app.dependency_overrides[get_auth_uow] = lambda: lambda: transaction_on(conn)
            app.dependency_overrides[get_team_uow] = lambda: lambda: team_transaction_on(conn)
            app.dependency_overrides[get_project_uow] = lambda: lambda: project_transaction_on(conn)
            app.dependency_overrides[get_invitation_uow] = lambda: lambda: invitation_transaction_on(conn)
            with TestClient(app,base_url="http://localhost:8000") as client:
                origin = {"Origin":"http://localhost:3000"}
                response = client.post("/api/v1/teams",headers=origin,json={"name":"Direct fixture"})
                check(response.status_code == 401)
                emit("TEAM_HTTP_NO_SESSION", status=401)
                email = "team-direct-" + uuid4().hex + "@example.test"
                password = "TeamDirectFixtureA1"  # Synthetic classroom fixture.
                response = client.post("/api/v1/auth/register",headers=origin,
                    json={"full_name":"Team direct fixture","email":email,"password":password})
                check(response.status_code == 201)
                actor = response.json()["data"]["id"]
                emit("TEAM_HTTP_REGISTER", status=201)
                response = client.post("/api/v1/auth/login",headers=origin,json={"email":email,"password":password})
                check(response.status_code == 200)
                emit("TEAM_HTTP_LOGIN", status=200)
                response = client.get("/api/v1/teams/me")
                check(response.status_code == 404 and response.json()["error"]["code"] == "TEAM_NOT_FOUND")
                emit("TEAM_HTTP_CURRENT_TEAM_EMPTY", status=404)
                response = client.post("/api/v1/teams",headers=origin,json={"name":"Direct fixture"})
                check(response.status_code == 403 and response.json()["error"]["code"] == "CSRF_INVALID")
                emit("TEAM_HTTP_MISSING_CSRF", status=403)
                headers = {**origin,CSRF_HEADER:client.cookies.get(CSRF_COOKIE)}
                response = client.post("/api/v1/teams",headers=headers,
                    json={"name":"  Team direct  ","description":"   "})
                check(response.status_code == 201)
                team = response.json()["data"]
                check(team["name"] == "Team direct" and team["description"] is None)
                check(len(team["members"]) == 1 and team["members"][0]["user_id"] == actor
                      and team["members"][0]["role"] == "leader")
                check(response.headers["cache-control"] == "no-store")
                emit("TEAM_HTTP_CREATE_TEAM_AND_LEADER", status=201, ids_are_strings=isinstance(team["id"],str))
                response = client.get("/api/v1/teams/me")
                current = response.json()["data"]
                check(response.status_code == 200 and current["id"] == team["id"]
                      and current["membership"] == {"id":team["members"][0]["id"],"role":"leader"})
                check(set(current) == {"id","name","description","membership"})
                emit("TEAM_HTTP_CURRENT_TEAM_RESTORED", status=200)
                response = client.post("/api/v1/teams",headers=headers,json={"name":"Second team"})
                check(response.status_code == 409 and response.json()["error"]["code"] == "ALREADY_IN_TEAM")
                check(conn.execute("SELECT count(*) FROM public.teams").fetchone()[0] == before[1]["public.teams"] + 1)
                check(conn.execute("SELECT count(*) FROM public.team_members WHERE user_id=%s",(actor,)).fetchone() == (1,))
                conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
                assert_auth_connection(conn)
                emit("TEAM_HTTP_DUPLICATE_REJECTED_WITHOUT_ORPHAN", status=409)
                target_email = "team-member-direct-" + uuid4().hex + "@example.test"
                response = client.post("/api/v1/auth/register", headers=origin,
                    json={"full_name":"Member direct fixture","email":target_email,"password":password})
                check(response.status_code == 201)
                target = response.json()["data"]["id"]
                response = client.post("/api/v1/teams/me/members",headers=headers,json={"email":target_email.upper()})
                check(response.status_code == 201 and response.json()["data"]["user_id"] == target
                      and response.json()["data"]["role"] == "member")
                emit("TEAM_HTTP_ADD_MEMBER", status=201)
                response = client.get("/api/v1/teams/me/members")
                check(response.status_code == 200 and [m["user_id"] for m in response.json()["data"]] == [actor,target])
                check(all(set(m) == {"id","user_id","full_name","role"} for m in response.json()["data"]))
                emit("TEAM_HTTP_LIST_MEMBERS", status=200)
                response = client.post("/api/v1/teams/me/members",headers=headers,json={"email":target_email})
                check(response.status_code == 409 and response.json()["error"]["code"] == "MEMBER_UNAVAILABLE")
                emit("TEAM_HTTP_DUPLICATE_MEMBER", status=409)
                response = client.get("/api/v1/projects/me")
                check(response.status_code == 404 and response.json()["error"]["code"] == "PROJECT_NOT_FOUND")
                emit("PROJECT_HTTP_EMPTY", status=404)
                response = client.post("/api/v1/projects",headers=headers,json={"name":"  Direct Project  ","description":"  "})
                check(response.status_code == 201)
                project = response.json()["data"]
                check(project["name"] == "Direct Project" and project["description"] is None
                      and project["team_id"] == team["id"] and project["created_by"] == actor)
                emit("PROJECT_HTTP_CREATE",status=201)
                response = client.get("/api/v1/projects/me")
                check(response.status_code == 200 and response.json()["data"] == project)
                emit("PROJECT_HTTP_CURRENT",status=200)
                response = client.post("/api/v1/projects",headers=headers,json={"name":"Duplicate Project"})
                check(response.status_code == 409 and response.json()["error"]["code"] == "PROJECT_ALREADY_EXISTS")
                check(conn.execute("SELECT count(*) FROM public.projects").fetchone()[0] == before[1]["public.projects"]+1)
                emit("PROJECT_HTTP_DUPLICATE",status=409)
                response = client.get("/api/v1/projects/me/advisor-candidates")
                check(response.status_code == 200 and all(set(row)=={"id","full_name"} for row in response.json()["data"]))
                emit("INVITATION_HTTP_DIRECT_APP_CANDIDATES",status=200)
                response = client.get("/api/v1/projects/me/advisor-invitations")
                check(response.status_code == 200 and response.json() == {"data":[]})
                response = client.post("/api/v1/projects/me/advisor-invitations",headers=headers,json={"advisor_id":actor})
                check(response.status_code == 404 and response.json()["error"]["code"] == "ADVISOR_NOT_FOUND")
                response = client.get("/api/v1/advisor-invitations/me")
                check(response.status_code == 403 and response.json()["error"]["code"] == "INVITATION_ACCESS_FORBIDDEN")
                emit("INVITATION_HTTP_DIRECT_APP_SCOPED_READ_AND_TARGET_ROLE",history_status=200,non_advisor_target=404,inbox_wrong_role=403)
                passed = True
    except Exception as exc:
        print(json.dumps({"case":"TEAM_HTTP_DIRECT_APP_SMOKE", "result":"FAIL",
            "error_type":type(exc).__name__, "sqlstate":getattr(exc,"sqlstate",None)}))
    finally:
        if conn is not None:
            conn.rollback()
            conn.close()
        if before is not None:
            try:
                cleanup = baseline() == before
                print(json.dumps({"case":"TEAM_HTTP_DIRECT_APP_ROLLBACK", "result":"PASS" if cleanup else "FAIL",
                    "metadata_acl_row_counts_restored":cleanup, "sequence_values_excluded":True}))
            except Exception as exc:
                print(json.dumps({"case":"TEAM_HTTP_DIRECT_APP_CLEANUP", "result":"FAIL", "error_type":type(exc).__name__}))
    return 0 if passed and cleanup else 1


if __name__ == "__main__":
    raise SystemExit(main())
