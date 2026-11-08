"""Team HTTP + PostgreSQL tests against installed V1; all fixtures ROLLBACK.

Fixtures for advisor/coordinator use effective owner, then all requests use
effective project_app. No schema/patch/grant changes or trigger disabling.
The separate team_api_direct_smoke verifies a direct app-password connection.
"""

from contextlib import contextmanager
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.auth_api import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE, get_auth_uow
from backend.auth_security import hash_password, session_digest
from backend.auth_store import StorageUnavailable, transaction_on
from backend.main import create_app
from backend.team_api import get_team_uow
from backend.team_store import TeamRepository, team_transaction_on
from database.tests.Auth_Regression import snapshot, switch, validate_installed_auth
from database.tools.Test_Database import TEST_DB, connect_test_database
from database.tools.V1_Baseline_Prepare import inventory

ORIGIN = {"Origin": "http://localhost:3000"}
PASSWORD = "TeamHttpFixtureA1"  # Synthetic fixture, never a DB password.


class TeamAPIIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = None
        try:
            cls.conn = connect_test_database()
            with cls.conn.cursor() as cur:
                switch(cur, "project_owner")
                if inventory(cur) != (52, []):
                    raise RuntimeError("Installed V1 baseline is required")
                validate_installed_auth(cur)
                cls.before = snapshot(cur)
                switch(cur, "project_app")
        except Exception as exc:
            if cls.conn is not None:
                cls.conn.rollback()
                cls.conn.close()
            raise RuntimeError("Team HTTP test setup failed; SQLSTATE=" + str(getattr(exc, "sqlstate", None))) from None

    @classmethod
    def tearDownClass(cls):
        try:
            cls.conn.rollback()
            cls.conn.execute("SET TRANSACTION READ ONLY")
            with cls.conn.cursor() as cur:
                switch(cur, "project_owner")
                if snapshot(cur) != cls.before:
                    raise AssertionError("Installed baseline was not restored")
            print("Team HTTP integration: ROLLBACK/baseline PASS; installed V1 preserved (sequences excluded)")
        finally:
            cls.conn.rollback()
            cls.conn.close()

    def setUp(self):
        self.case = self.conn.transaction(force_rollback=True)
        self.case.__enter__()
        self.app = create_app()
        self.app.dependency_overrides[get_auth_uow] = lambda: lambda: transaction_on(self.conn)
        self.app.dependency_overrides[get_team_uow] = lambda: lambda: team_transaction_on(self.conn)
        self.client = TestClient(self.app, base_url="http://localhost:8000")

    def tearDown(self):
        try:
            self.client.close()
        finally:
            self.case.__exit__(None, None, None)

    def signed_in(self, role="student"):
        email = "team-http-" + uuid4().hex + "@example.test"
        if role == "student":
            response = self.client.post("/api/v1/auth/register", headers=ORIGIN,
                json={"full_name":"Team fixture", "email":email, "password":PASSWORD})
            self.assertEqual(response.status_code, 201)
        else:
            with self.conn.cursor() as cur:
                switch(cur, "project_owner")
                cur.execute("INSERT INTO public.users(full_name,email,role) VALUES ('Staff fixture',%s,%s) RETURNING id", (email, role))
                actor = cur.fetchone()[0]
                cur.execute("INSERT INTO auth.credentials(user_id,password_hash) VALUES (%s,%s)", (actor, hash_password(PASSWORD)))
                switch(cur, "project_app")
        response = self.client.post("/api/v1/auth/login", headers=ORIGIN, json={"email":email,"password":PASSWORD})
        self.assertEqual(response.status_code, 200)
        return response.json()["data"]

    def create(self, payload=None, *, headers=None):
        request_headers = {**ORIGIN, CSRF_HEADER:self.client.cookies.get(CSRF_COOKIE) or ""}
        if headers:
            request_headers.update(headers)
        return self.client.post("/api/v1/teams", headers=request_headers,
                                json={"name":"Team fixture"} if payload is None else payload)

    def assert_counts(self, teams=0, members=0):
        self.assertEqual(self.conn.execute("SELECT count(*) FROM public.teams").fetchone()[0], self.before[1]["public.teams"] + teams)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM public.team_members").fetchone()[0], self.before[1]["public.team_members"] + members)

    def assert_error(self, response, status, code):
        self.assertEqual(response.status_code, status)
        self.assertEqual(response.json()["error"]["code"], code)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertFalse(response.headers.get_list("set-cookie"))
        for secret in (PASSWORD, self.client.cookies.get(SESSION_COOKIE), self.client.cookies.get(CSRF_COOKIE)):
            if secret:
                self.assertNotIn(secret, response.text)

    def test_student_creates_normalized_team_and_only_self_as_leader(self):
        user = self.signed_in()
        response = self.create({"name":" \tTeam's % name\n", "description":"  Example  "})
        self.assertEqual(response.status_code, 201)
        data = response.json()["data"]
        self.assertEqual(set(data), {"id","name","description","members"})
        self.assertEqual(data["name"], "Team's % name")
        self.assertEqual(data["description"], "Example")
        self.assertIsInstance(data["id"], str)
        self.assertEqual(len(data["members"]), 1)
        leader = data["members"][0]
        self.assertEqual(set(leader), {"id","user_id","role"})
        self.assertEqual(leader["user_id"], user["id"])
        self.assertEqual(leader["role"], "leader")
        self.assertIsInstance(leader["id"], str)
        self.assert_counts(1, 1)
        self.assertEqual(self.conn.execute("SELECT name,description FROM public.teams WHERE id=%s", (data["id"],)).fetchone(), (data["name"],data["description"]))
        self.assertEqual(self.conn.execute("SELECT count(*) FROM public.projects").fetchone()[0], self.before[1]["public.projects"])
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertFalse(response.headers.get_list("set-cookie"))

    def test_description_missing_null_and_ascii_blank_are_null(self):
        self.signed_in()
        for extra in ({}, {"description":None}, {"description":""}, {"description":" \t\r\n\f\v"}):
            with self.subTest(extra=extra), self.conn.transaction(force_rollback=True):
                response = self.create({"name":"Team", **extra})
                self.assertEqual(response.status_code, 201)
                self.assertIsNone(response.json()["data"]["description"])

    def test_creation_explicitly_handles_previously_immediate_team_checks(self):
        self.signed_in()
        self.conn.execute("SET CONSTRAINTS public.c_team_created_has_leader, public.c_team_member_cardinality IMMEDIATE")
        self.assertEqual(self.create().status_code, 201)
        self.assert_counts(1, 1)

    def test_invalid_name_is_422_and_no_partial_team(self):
        self.signed_in()
        for payload in ({}, {"name":None}, {"name":" \t\n\r\f\v"}, {"name":123}, {"name":True}, {"name":[]}, {"name":{}}, {"name":"x"*256}):
            with self.subTest(shape=list(payload)):
                self.assert_error(self.create(payload), 422, "VALIDATION_ERROR")
                self.assert_counts()

    def test_name_limit_is_after_trim_and_uses_unicode_characters(self):
        self.signed_in()
        name = "\U0001f4da" * 255
        response = self.create({"name":" " + name + "\t"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["data"]["name"], name)

    def test_non_ascii_whitespace_is_not_silently_trimmed(self):
        self.signed_in()
        response = self.create({"name":"\u00a0Team\u00a0", "description":"\u00a0"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["data"]["name"], "\u00a0Team\u00a0")
        self.assertEqual(response.json()["data"]["description"], "\u00a0")

    def test_description_has_no_added_length_limit(self):
        self.signed_in()
        text = "x" * 4096
        response = self.create({"name":"Team", "description":text})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["data"]["description"], text)

    def test_bad_description_types_and_database_invalid_text_are_422(self):
        self.signed_in()
        for payload in ({"name":"Team","description":123}, {"name":"Team","description":False},
                        {"name":"bad\x00name"}, {"name":"Team","description":"bad\x00text"}):
            with self.subTest():
                self.assert_error(self.create(payload), 422, "VALIDATION_ERROR")
                self.assert_counts()
        from backend.team_api import TeamCreateInput
        from pydantic import ValidationError
        for field in ("name","description"):
            with self.assertRaises(ValidationError):
                TeamCreateInput(**{"name":"Team", field:"bad\ud800text"})

    def test_client_identity_extra_fields_are_rejected_without_reflection(self):
        self.signed_in()
        for key in ("id","leader_id","user_id","role","actor_user_id","members","member_ids","project","password"):
            with self.subTest(field=key):
                response = self.create({"name":"Team",key:"DoNotEchoThisFixture"})
                self.assert_error(response, 422, "VALIDATION_ERROR")
                self.assertNotIn("DoNotEchoThisFixture", response.text)
                self.assert_counts()

    def test_forged_identity_headers_and_query_cannot_choose_actor(self):
        user = self.signed_in()
        headers = {**ORIGIN,CSRF_HEADER:self.client.cookies.get(CSRF_COOKIE),"X-User-ID":"-1","X-Role":"coordinator","app.actor_user_id":"-1"}
        response = self.client.post("/api/v1/teams?user_id=-1&role=coordinator", headers=headers,json={"name":"Team"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["data"]["members"][0]["user_id"], user["id"])

    def test_missing_malformed_unknown_sessions_are_401(self):
        for token in (None,"bad","A"*43):
            self.client.cookies.clear()
            if token:
                self.client.cookies.set(SESSION_COOKIE, token)
            self.assert_error(self.create(), 401, "AUTHENTICATION_REQUIRED")
            self.assert_counts()

    def test_expired_session_is_401(self):
        self.signed_in()
        token = self.client.cookies.get(SESSION_COOKIE)
        with self.conn.cursor() as cur:
            switch(cur, "project_owner")
            cur.execute("UPDATE auth.sessions SET created_at=clock_timestamp()-interval '2 hours', expires_at=clock_timestamp()-interval '1 hour' WHERE token_hash=%s", (session_digest(token),))
            switch(cur, "project_app")
        self.assert_error(self.create(), 401, "AUTHENTICATION_REQUIRED")
        self.assert_counts()

    def test_revoked_session_is_401(self):
        self.signed_in()
        token,csrf = self.client.cookies.get(SESSION_COOKIE),self.client.cookies.get(CSRF_COOKIE)
        response = self.client.post("/api/v1/auth/logout", headers={**ORIGIN,CSRF_HEADER:csrf})
        self.assertEqual(response.status_code, 204)
        self.client.cookies.set(SESSION_COOKIE, token)
        self.client.cookies.set(CSRF_COOKIE, csrf)
        self.assert_error(self.create(), 401, "AUTHENTICATION_REQUIRED")
        self.assert_counts()

    def test_csrf_missing_mismatched_and_from_other_session_are_403(self):
        self.signed_in()
        self.assert_error(self.create(headers={CSRF_HEADER:""}), 403, "CSRF_INVALID")
        self.assert_error(self.create(headers={CSRF_HEADER:"wrong"}), 403, "CSRF_INVALID")
        first_csrf = self.client.cookies.get(CSRF_COOKIE)
        self.signed_in()
        self.client.cookies.set(CSRF_COOKIE, first_csrf, domain="localhost.local", path="/")
        self.assert_error(self.create(headers={CSRF_HEADER:first_csrf}), 403, "CSRF_INVALID")
        self.assert_counts()

    def test_wrong_or_missing_origin_is_403(self):
        self.signed_in()
        for origin in ("http://untrusted.example.test","null",""):
            self.assert_error(self.create(headers={"Origin":origin}), 403, "ORIGIN_NOT_ALLOWED")
        self.assert_counts()

    def test_staff_roles_cannot_create_team(self):
        for role in ("advisor","coordinator"):
            self.signed_in(role)
            self.assert_error(self.create(), 403, "TEAM_CREATION_FORBIDDEN")
            self.assert_counts()

    def test_existing_member_gets_409_without_orphan_team(self):
        self.signed_in()
        self.assertEqual(self.create().status_code, 201)
        self.assert_error(self.create({"name":"Second Team"}), 409, "ALREADY_IN_TEAM")
        self.assert_counts(1, 1)

    def test_two_students_can_use_same_team_name(self):
        first = self.signed_in()
        one = self.create()
        second = self.signed_in()
        two = self.create()
        self.assertEqual((one.status_code,two.status_code), (201,201))
        self.assertNotEqual(first["id"], second["id"])
        self.assertNotEqual(one.json()["data"]["id"],two.json()["data"]["id"])
        self.assert_counts(2, 2)

    def test_current_team_repository_is_empty_without_membership(self):
        user = self.signed_in()
        self.assertIsNone(TeamRepository(self.conn).current_team(user["id"]))
        self.assert_counts()

    def test_current_team_repository_only_returns_the_requested_membership(self):
        first = self.signed_in()
        one = self.create().json()["data"]
        second = self.signed_in()
        store = TeamRepository(self.conn)
        self.assertIsNone(store.current_team(second["id"]))
        two = self.create({"name":"Second student's team"}).json()["data"]
        self.assertEqual(str(store.current_team(first["id"])[0]), one["id"])
        self.assertEqual(str(store.current_team(second["id"])[0]), two["id"])
        self.assert_counts(2, 2)

    def test_current_team_no_membership_is_404(self):
        self.signed_in()
        self.assert_error(self.client.get("/api/v1/teams/me"), 404, "TEAM_NOT_FOUND")
        self.assert_counts()

    def test_current_team_returns_only_own_membership_without_origin_or_csrf(self):
        user = self.signed_in()
        created = self.create({"name":"Own team", "description":"Own description"}).json()["data"]
        token = self.client.cookies.get(SESSION_COOKIE)
        expires_before = self.conn.execute("SELECT expires_at FROM auth.sessions WHERE token_hash=%s", (session_digest(token),)).fetchone()
        self.client.cookies.delete(CSRF_COOKIE)
        response = self.client.get("/api/v1/teams/me")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(set(data), {"id","name","description","membership"})
        self.assertEqual(data, {"id":created["id"],"name":"Own team","description":"Own description",
                               "membership":{"id":created["members"][0]["id"],"role":"leader"}})
        self.assertNotIn("user_id", data["membership"])
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertFalse(response.headers.get_list("set-cookie"))
        self.assertEqual(self.conn.execute("SELECT expires_at FROM auth.sessions WHERE token_hash=%s", (session_digest(token),)).fetchone(), expires_before)
        self.assert_counts(1, 1)

    def test_current_team_member_gets_member_role_and_no_other_member_data(self):
        leader = self.signed_in()
        team = self.create().json()["data"]
        member = self.signed_in()
        self.conn.execute("SELECT set_config('app.actor_user_id',%s,true)", (leader["id"],))
        membership = self.conn.execute("INSERT INTO public.team_members(team_id,user_id,role) VALUES (%s,%s,'member') RETURNING id", (team["id"],member["id"])).fetchone()[0]
        self.conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        response = self.client.get("/api/v1/teams/me")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["membership"], {"id":str(membership),"role":"member"})
        self.assertNotIn("members", response.json()["data"])
        self.assert_counts(1, 2)

    def test_current_team_missing_malformed_unknown_sessions_are_401(self):
        for token in (None,"bad","A"*43):
            self.client.cookies.clear()
            if token:
                self.client.cookies.set(SESSION_COOKIE, token)
            self.assert_error(self.client.get("/api/v1/teams/me"), 401, "AUTHENTICATION_REQUIRED")
        self.assert_counts()

    def test_current_team_expired_and_revoked_sessions_are_401(self):
        self.signed_in()
        token = self.client.cookies.get(SESSION_COOKIE)
        with self.conn.cursor() as cur:
            switch(cur, "project_owner")
            cur.execute("UPDATE auth.sessions SET created_at=clock_timestamp()-interval '2 hours', expires_at=clock_timestamp()-interval '1 hour' WHERE token_hash=%s", (session_digest(token),))
            switch(cur, "project_app")
        self.assert_error(self.client.get("/api/v1/teams/me"), 401, "AUTHENTICATION_REQUIRED")
        self.signed_in()
        token,csrf = self.client.cookies.get(SESSION_COOKIE),self.client.cookies.get(CSRF_COOKIE)
        self.assertEqual(self.client.post("/api/v1/auth/logout",headers={**ORIGIN,CSRF_HEADER:csrf}).status_code,204)
        self.client.cookies.set(SESSION_COOKIE,token)
        self.assert_error(self.client.get("/api/v1/teams/me"), 401, "AUTHENTICATION_REQUIRED")

    def test_current_team_staff_roles_are_403(self):
        for role in ("advisor","coordinator"):
            self.signed_in(role)
            self.assert_error(self.client.get("/api/v1/teams/me"), 403, "TEAM_ACCESS_FORBIDDEN")
        self.assert_counts()

    def test_current_team_ignores_forged_identity_and_does_not_disclose_other_team(self):
        first = self.signed_in()
        team = self.create({"name":"Private team name"}).json()["data"]
        self.signed_in()
        response = self.client.get("/api/v1/teams/me?user_id="+first["id"]+"&team_id="+team["id"],headers={"X-User-ID":first["id"],"X-Role":"student"})
        self.assert_error(response,404,"TEAM_NOT_FOUND")
        self.assertNotIn("Private team name",response.text)
        own = self.create({"name":"My own team"}).json()["data"]
        response = self.client.get("/api/v1/teams/me?team_id="+team["id"])
        self.assertEqual(response.json()["data"]["id"],own["id"])
        self.assert_counts(2, 2)

    def test_current_team_storage_error_is_sanitized_500(self):
        self.signed_in()
        with patch.object(TeamRepository,"current_team",side_effect=StorageUnavailable()):
            self.assert_error(self.client.get("/api/v1/teams/me"),500,"INTERNAL_ERROR")
        self.assert_counts()

    def test_membership_unique_constraint_race_path_maps_only_expected_409(self):
        self.signed_in()
        self.assertEqual(self.create().status_code, 201)
        # Simulate a stale precheck; the real UNIQUE constraint still rejects.
        with patch.object(TeamRepository,"membership_exists",return_value=False):
            self.assert_error(self.create(), 409, "ALREADY_IN_TEAM")
        self.assert_counts(1, 1)

    def test_missing_leader_is_caught_by_forced_deferred_constraint(self):
        user = self.signed_in()
        with patch.object(TeamRepository,"insert_leader",return_value=(0,user["id"],"leader")):
            self.assert_error(self.create(), 500, "INTERNAL_ERROR")
        self.assert_counts()

    def test_leader_insert_failure_rolls_back_team(self):
        self.signed_in()
        with patch.object(TeamRepository,"insert_leader",side_effect=StorageUnavailable()):
            self.assert_error(self.create(), 500, "INTERNAL_ERROR")
        self.assert_counts()

    def test_transaction_completion_failure_does_not_return_201(self):
        self.signed_in()
        @contextmanager
        def fail_completion():
            with team_transaction_on(self.conn) as store:
                yield store
                raise StorageUnavailable()
        self.app.dependency_overrides[get_team_uow] = lambda: fail_completion
        self.assert_error(self.create(), 500, "INTERNAL_ERROR")
        self.assert_counts()

    def test_database_permission_error_is_500_without_admin_fallback(self):
        self.signed_in()
        def forbidden_lock(store, team):
            store.conn.execute("SELECT 1 FROM public.teams WHERE id=%s FOR UPDATE", (team,))
        with patch.object(TeamRepository,"lock_parent",forbidden_lock):
            self.assert_error(self.create(), 500, "INTERNAL_ERROR")
        self.assert_counts()

    def test_unrelated_unique_violation_is_not_membership_409(self):
        self.signed_in()
        digest = session_digest(self.client.cookies.get(SESSION_COOKIE))
        def duplicate_session(store, team, actor):
            return store.conn.execute("""INSERT INTO auth.sessions(token_hash,user_id,expires_at)
                SELECT token_hash,user_id,clock_timestamp()+interval '8 hours'
                FROM auth.sessions WHERE token_hash=%s""", (digest,)).fetchone()
        with patch.object(TeamRepository,"insert_leader",duplicate_session):
            self.assert_error(self.create(), 500, "INTERNAL_ERROR")
        self.assert_counts()

    def test_bigint_team_and_member_ids_are_decimal_strings(self):
        user = self.signed_in()
        team_id,member_id = 9_007_199_254_740_993,9_007_199_254_740_995
        def large_team(store, name, description):
            return store.conn.execute("""INSERT INTO public.teams(id,name,description)
                OVERRIDING SYSTEM VALUE VALUES (%s,%s,%s) RETURNING id,name,description""", (team_id,name,description)).fetchone()
        def large_member(store, team, actor):
            return store.conn.execute("""INSERT INTO public.team_members(id,team_id,user_id,role)
                OVERRIDING SYSTEM VALUE VALUES (%s,%s,%s,'leader') RETURNING id,user_id,role""", (member_id,team,actor)).fetchone()
        with patch.object(TeamRepository,"insert_team",large_team),patch.object(TeamRepository,"insert_leader",large_member):
            response = self.create()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["data"]["id"], str(team_id))
        self.assertEqual(response.json()["data"]["members"][0], {"id":str(member_id),"user_id":user["id"],"role":"leader"})
        current = self.client.get("/api/v1/teams/me").json()["data"]
        self.assertEqual(current["id"],str(team_id))
        self.assertEqual(current["membership"]["id"],str(member_id))

    def test_json_type_and_parse_errors_are_sanitized(self):
        self.signed_in()
        headers={**ORIGIN,CSRF_HEADER:self.client.cookies.get(CSRF_COOKIE),"Content-Type":"application/json"}
        for body in ('{"name":', '[]', 'null', '"DoNotEchoBodyFixture"'):
            response=self.client.post("/api/v1/teams",headers=headers,content=body)
            self.assert_error(response,422,"VALIDATION_ERROR")
            self.assertNotIn("DoNotEchoBodyFixture",response.text)
        self.assert_counts()

    def test_cors_preflight_and_local_backend_origin(self):
        headers={**ORIGIN,"Access-Control-Request-Method":"POST","Access-Control-Request-Headers":"content-type,x-csrf-token"}
        response=self.client.options("/api/v1/teams",headers=headers)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.headers["access-control-allow-origin"],ORIGIN["Origin"])
        self.assertEqual(response.headers["access-control-allow-credentials"],"true")
        self.signed_in()
        self.assertEqual(self.create(headers={"Origin":"http://localhost:8000"}).status_code,201)


if __name__ == "__main__":
    unittest.main()
