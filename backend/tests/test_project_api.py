"""Project HTTP + installed PostgreSQL V1; every fixture is rolled back."""

from contextlib import contextmanager
import unittest
from unittest.mock import patch

import psycopg
from pydantic import ValidationError

from backend.auth_api import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE
from backend.auth_security import session_digest
from backend.auth_store import StorageUnavailable
from backend.project_api import ProjectCreateInput, get_project_uow
from backend.project_store import ProjectRepository, project_transaction_on
from backend.tests import test_team_api as base
from database.tests.Auth_Regression import switch

URL = "/api/v1/projects"


class ProjectAPIIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base.TeamAPIIntegrationTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        base.TeamAPIIntegrationTests.tearDownClass.__func__(cls)

    def setUp(self):
        base.TeamAPIIntegrationTests.setUp(self)
        self.app.dependency_overrides[get_project_uow] = lambda: lambda: project_transaction_on(self.conn)

    tearDown = base.TeamAPIIntegrationTests.tearDown
    signed_in = base.TeamAPIIntegrationTests.signed_in
    create_team = base.TeamAPIIntegrationTests.create
    assert_error = base.TeamAPIIntegrationTests.assert_error

    def team(self):
        leader = self.signed_in()
        response = self.create_team()
        self.assertEqual(response.status_code,201)
        return leader,response.json()["data"]

    def post(self, payload=None, headers=None):
        return self.client.post(URL, headers={**base.ORIGIN,CSRF_HEADER:self.client.cookies.get(CSRF_COOKIE) or "",**(headers or {})},
            json={"name":"Project fixture"} if payload is None else payload)

    def projects(self, extra=0):
        self.assertEqual(self.conn.execute("SELECT count(*) FROM public.projects").fetchone()[0],self.before[1]["public.projects"]+extra)

    def login_as(self, user):
        self.client.cookies.clear()
        self.assertEqual(self.client.post("/api/v1/auth/login",headers=base.ORIGIN,
            json={"email":user["email"],"password":base.PASSWORD}).status_code,200)

    def member(self, leader, team):
        member=self.signed_in()
        self.conn.execute("SELECT set_config('app.actor_user_id',%s,true)",(leader["id"],))
        self.conn.execute("INSERT INTO public.team_members(team_id,user_id,role) VALUES (%s,%s,'member')",(team["id"],member["id"]))
        self.conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        return member

    def test_leader_creates_normalized_project_for_own_team_and_reads_same_shape(self):
        leader,team=self.team()
        response=self.post({"name":" \tProject's % fixture\n","description":"  Example  "})
        self.assertEqual(response.status_code,201)
        data=response.json()["data"]
        self.assertEqual(set(data),{"id","name","description","team_id","created_by"})
        self.assertEqual(data["name"],"Project's % fixture")
        self.assertEqual(data["description"],"Example")
        self.assertEqual(data["team_id"],team["id"])
        self.assertEqual(data["created_by"],leader["id"])
        self.assertTrue(all(isinstance(data[key],str) for key in ("id","team_id","created_by")))
        self.assertEqual(response.headers["cache-control"],"no-store")
        self.assertFalse(response.headers.get_list("set-cookie"))
        read=self.client.get(URL+"/me")
        self.assertEqual(read.status_code,200)
        self.assertEqual(read.json()["data"],data)
        self.assertEqual(self.conn.execute("SELECT name,description,team_id,created_by FROM public.projects WHERE id=%s",(data["id"],)).fetchone(),
                         (data["name"],data["description"],int(team["id"]),int(leader["id"])))
        self.projects(1)

    def test_description_missing_null_blank_and_no_added_length_limit(self):
        self.team()
        for extra in ({},{"description":None},{"description":""},{"description":" \t\r\n\f\v"},{"description":"x"*4096}):
            with self.subTest(),self.conn.transaction(force_rollback=True):
                response=self.post({"name":"Project",**extra})
                self.assertEqual(response.status_code,201)
                expected=extra.get("description")
                self.assertEqual(response.json()["data"]["description"],expected if expected and expected.startswith("x") else None)

    def test_name_unicode_boundary_and_non_ascii_whitespace_preserved(self):
        self.team()
        for name in ("\U0001f4da"*255,"\u00a0Project\u00a0"):
            with self.conn.transaction(force_rollback=True):
                response=self.post({"name":" "+name+"\t","description":"\u00a0"})
                self.assertEqual(response.status_code,201)
                self.assertEqual(response.json()["data"]["name"],name)
                self.assertEqual(response.json()["data"]["description"],"\u00a0")

    def test_invalid_names_descriptions_and_extra_identity_fields_are_sanitized_422(self):
        self.team()
        payloads=[{}, {"name":None},{"name":True},{"name":12},{"name":[]},{"name":" \t\n"},{"name":"x"*256},
                  {"name":"bad\x00name"},{"name":"Project","description":False},{"name":"Project","description":"bad\x00text"}]
        payloads += [{"name":"Project",field:"DoNotEchoProjectFixture"} for field in ("id","team_id","created_by","user_id","actor_user_id","role","status","members","password")]
        for payload in payloads:
            with self.subTest(fields=list(payload)):
                response=self.post(payload)
                self.assert_error(response,422,"VALIDATION_ERROR")
                self.assertNotIn("DoNotEchoProjectFixture",response.text)
                self.projects()
        for field in ("name","description"):
            with self.assertRaises(ValidationError):
                ProjectCreateInput(**{"name":"Project",field:"bad\ud800text"})

    def test_invalid_json_is_sanitized_422(self):
        self.team()
        response=self.client.post(URL,headers={**base.ORIGIN,CSRF_HEADER:self.client.cookies.get(CSRF_COOKIE),"Content-Type":"application/json"},content="{bad")
        self.assert_error(response,422,"VALIDATION_ERROR")
        self.projects()

    def test_missing_malformed_and_unknown_sessions_are_401(self):
        for token in (None,"bad","A"*43):
            self.client.cookies.clear()
            if token:self.client.cookies.set(SESSION_COOKIE,token)
            self.assert_error(self.client.get(URL+"/me"),401,"AUTHENTICATION_REQUIRED")
            self.assert_error(self.post(),401,"AUTHENTICATION_REQUIRED")
        self.projects()

    def test_expired_and_revoked_sessions_are_401(self):
        for mode in ("expired","revoked"):
            self.signed_in()
            token=self.client.cookies.get(SESSION_COOKIE)
            if mode=="expired":
                with self.conn.cursor() as cur:
                    switch(cur,"project_owner")
                    cur.execute("UPDATE auth.sessions SET created_at=clock_timestamp()-interval '2 hours',expires_at=clock_timestamp()-interval '1 hour' WHERE token_hash=%s",(session_digest(token),))
                    switch(cur,"project_app")
            else:
                self.client.post("/api/v1/auth/logout",headers={**base.ORIGIN,CSRF_HEADER:self.client.cookies.get(CSRF_COOKIE)})
                self.client.cookies.set(SESSION_COOKIE,token)
            self.assert_error(self.client.get(URL+"/me"),401,"AUTHENTICATION_REQUIRED")
            self.assert_error(self.post(),401,"AUTHENTICATION_REQUIRED")

    def test_no_team_is_404_and_staff_are_403(self):
        for role in ("student","advisor","coordinator"):
            self.signed_in(role)
            status,code=(404,"TEAM_NOT_FOUND") if role=="student" else (403,"PROJECT_ACCESS_FORBIDDEN")
            self.assert_error(self.client.get(URL+"/me"),status,code)
            self.assert_error(self.post(),status,code)
        self.projects()

    def test_team_without_project_returns_404(self):
        self.team()
        self.assert_error(self.client.get(URL+"/me"),404,"PROJECT_NOT_FOUND")

    def test_member_can_read_but_cannot_create_even_before_project_exists(self):
        leader,team=self.team()
        member=self.member(leader,team)
        self.assert_error(self.client.get(URL+"/me"),404,"PROJECT_NOT_FOUND")
        self.assert_error(self.post(),403,"PROJECT_CREATION_FORBIDDEN")
        self.login_as(leader)
        created=self.post().json()
        self.login_as(member)
        response=self.client.get(URL+"/me")
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json(),created)
        self.assert_error(self.post(),403,"PROJECT_CREATION_FORBIDDEN")
        self.projects(1)

    def test_get_requires_no_origin_csrf_and_does_not_renew_session(self):
        self.team()
        self.post()
        token=self.client.cookies.get(SESSION_COOKIE)
        before=self.conn.execute("SELECT expires_at FROM auth.sessions WHERE token_hash=%s",(session_digest(token),)).fetchone()
        self.client.cookies.delete(CSRF_COOKIE)
        response=self.client.get(URL+"/me")
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.headers["cache-control"],"no-store")
        self.assertFalse(response.headers.get_list("set-cookie"))
        self.assertEqual(self.conn.execute("SELECT expires_at FROM auth.sessions WHERE token_hash=%s",(session_digest(token),)).fetchone(),before)

    def test_post_requires_origin_and_session_bound_csrf(self):
        self.team()
        for value in ("","wrong"):
            self.assert_error(self.post(headers={CSRF_HEADER:value}),403,"CSRF_INVALID")
        for origin in ("","null","http://untrusted.example.test"):
            self.assert_error(self.post(headers={"Origin":origin}),403,"ORIGIN_NOT_ALLOWED")
        first=self.client.cookies.get(CSRF_COOKIE)
        self.signed_in()
        self.client.cookies.set(CSRF_COOKIE,first,domain="localhost.local",path="/")
        self.assert_error(self.post(headers={CSRF_HEADER:first}),403,"CSRF_INVALID")
        self.projects()

    def test_identity_headers_and_query_cannot_select_other_project_or_team(self):
        first,team=self.team()
        private=self.post({"name":"Other team's private Project"}).json()["data"]
        self.signed_in()
        query="?project_id="+private["id"]+"&team_id="+team["id"]+"&user_id="+first["id"]
        self.assert_error(self.client.get(URL+"/me"+query,headers={"X-User-ID":first["id"]}),404,"TEAM_NOT_FOUND")
        own=self.create_team().json()["data"]
        response=self.client.get(URL+"/me"+query)
        self.assert_error(response,404,"PROJECT_NOT_FOUND")
        self.assertNotIn(private["name"],response.text)
        response=self.client.post(URL+query,headers={**base.ORIGIN,CSRF_HEADER:self.client.cookies.get(CSRF_COOKIE),"X-User-ID":first["id"],"X-Role":"leader"},json={"name":"Own Project"})
        self.assertEqual(response.status_code,201)
        self.assertEqual(response.json()["data"]["team_id"],own["id"])
        self.projects(2)

    def test_duplicate_and_actual_unique_conflict_are_409_without_new_project(self):
        self.team()
        self.assertEqual(self.post().status_code,201)
        self.assert_error(self.post(),409,"PROJECT_ALREADY_EXISTS")
        with patch.object(ProjectRepository,"exists",return_value=False):
            self.assert_error(self.post(),409,"PROJECT_ALREADY_EXISTS")
        self.projects(1)

    def test_two_teams_can_use_same_project_name(self):
        self.team();self.assertEqual(self.post().status_code,201)
        self.team();self.assertEqual(self.post().status_code,201)
        self.projects(2)

    def test_authority_rechecked_after_parent_lock(self):
        self.team()
        original=ProjectRepository.own_team
        for mode in ("member","missing"):
            calls=0
            def changed(store,actor):
                nonlocal calls
                row=original(store,actor);calls+=1
                if calls==2:return (row[0],"member") if mode=="member" else None
                return row
            with patch.object(ProjectRepository,"own_team",changed):
                self.assert_error(self.post(),403 if mode=="member" else 404,"PROJECT_CREATION_FORBIDDEN" if mode=="member" else "TEAM_NOT_FOUND")
        self.projects()

    def test_failure_after_insert_and_transaction_completion_rolls_back(self):
        self.team()
        original=ProjectRepository.insert
        def fail_after_insert(store,*args):
            original(store,*args)
            raise StorageUnavailable()
        with patch.object(ProjectRepository,"insert",fail_after_insert):
            self.assert_error(self.post(),500,"INTERNAL_ERROR")
        @contextmanager
        def fail_completion():
            with project_transaction_on(self.conn) as store:
                yield store
                raise StorageUnavailable()
        self.app.dependency_overrides[get_project_uow]=lambda:fail_completion
        self.assert_error(self.post(),500,"INTERNAL_ERROR")
        self.projects()

    def test_unexpected_pg_errors_are_sanitized_500_not_business_errors(self):
        self.team()
        for error in (psycopg.errors.InsufficientPrivilege("DoNotEchoSQLFixture"),psycopg.errors.RaiseException("DoNotEchoSQLFixture"),psycopg.errors.UniqueViolation("DoNotEchoSQLFixture")):
            with patch.object(ProjectRepository,"insert",side_effect=error):
                response=self.post()
                self.assert_error(response,500,"INTERNAL_ERROR")
                self.assertNotIn("DoNotEchoSQLFixture",response.text)
        with patch.object(ProjectRepository,"current",side_effect=StorageUnavailable()):
            self.assert_error(self.client.get(URL+"/me"),500,"INTERNAL_ERROR")
        self.projects()

    def test_bigint_project_ids_are_strings(self):
        self.team()
        large=9223372036854775804
        def insert(store,name,description,team,actor):
            return store.conn.execute("INSERT INTO public.projects(id,name,description,team_id,created_by) OVERRIDING SYSTEM VALUE VALUES (%s,%s,%s,%s,%s) RETURNING id,name,description,team_id,created_by",(large,name,description,team,actor)).fetchone()
        # App has INSERT on this table; identity override needs no owner role.
        with patch.object(ProjectRepository,"insert",insert):
            response=self.post()
        self.assertEqual(response.status_code,201)
        self.assertEqual(response.json()["data"]["id"],str(large))
        self.assertEqual(self.client.get(URL+"/me").json()["data"]["id"],str(large))

    def test_project_fk_identity_immutability_and_r01_protection_remain_enabled(self):
        leader,team=self.team()
        project=self.post().json()["data"]
        for sql,params,state in (
            ("INSERT INTO public.projects(name,team_id,created_by) VALUES ('FK fixture',%s,%s)",(team["id"],-1),"P0001"),
            ("DELETE FROM public.projects WHERE id=%s",(project["id"],),"42501"),
        ):
            with self.assertRaises(psycopg.Error) as caught,self.conn.transaction():self.conn.execute(sql,params)
            self.assertEqual(caught.exception.sqlstate,state)
        # Prove FK/immutable/R-01 trigger under owner inside savepoints without
        # granting app UPDATE/DELETE or creating the normal Project as owner.
        for sql,params,state in (
            ("UPDATE public.projects SET team_id=-1 WHERE id=%s",(project["id"],),"P0001"),
            ("UPDATE public.projects SET created_by=-1 WHERE id=%s",(project["id"],),"P0001"),
            ("DELETE FROM public.projects WHERE id=%s",(project["id"],),"42501"),
        ):
            with self.assertRaises(psycopg.Error) as caught,self.conn.transaction():
                self.conn.execute("SET LOCAL ROLE project_owner")
                self.conn.execute(sql,params)
            self.assertEqual(caught.exception.sqlstate,state)
        self.assertEqual(self.conn.execute("SELECT team_id,created_by FROM public.projects WHERE id=%s",(project["id"],)).fetchone(),(int(team["id"]),int(leader["id"])))
        self.projects(1)

    def test_no_delete_or_update_http_operations_exist(self):
        self.team()
        self.post()
        paths=self.app.openapi()["paths"]
        self.assertEqual(set(paths[URL]),{"post"})
        self.assertEqual(set(paths[URL+"/me"]),{"get"})
        for method in ("delete","patch","put"):
            response=getattr(self.client,method)(URL+"/me",headers=base.ORIGIN)
            self.assertEqual(response.status_code,405)
            self.assertEqual(response.headers["cache-control"],"no-store")
        self.projects(1)


if __name__ == "__main__":
    unittest.main()
