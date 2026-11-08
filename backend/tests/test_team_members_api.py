"""Installed-V1 member API integration; owner fixtures and all app writes ROLLBACK."""

import unittest
from unittest.mock import patch
from uuid import uuid4

import psycopg

from backend.auth_api import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE
from backend.auth_security import session_digest
from backend.auth_store import StorageUnavailable
from backend.team_store import TeamRepository
from backend.tests import test_team_api as base
from database.tests.Auth_Regression import switch


URL = "/api/v1/teams/me/members"


class TeamMembersIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base.TeamAPIIntegrationTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        base.TeamAPIIntegrationTests.tearDownClass.__func__(cls)

    setUp = base.TeamAPIIntegrationTests.setUp
    tearDown = base.TeamAPIIntegrationTests.tearDown
    signed_in = base.TeamAPIIntegrationTests.signed_in
    create = base.TeamAPIIntegrationTests.create
    assert_error = base.TeamAPIIntegrationTests.assert_error
    assert_counts = base.TeamAPIIntegrationTests.assert_counts

    def fixture(self, name="Member fixture", role="student"):
        email = "member-" + uuid4().hex + "@example.test"
        with self.conn.cursor() as cur:
            switch(cur, "project_owner")
            cur.execute("INSERT INTO public.users(full_name,email,role) VALUES (%s,%s,%s) RETURNING id", (name,email,role))
            user_id = cur.fetchone()[0]
            switch(cur, "project_app")
        return user_id,email

    def actor(self, user_id):
        self.conn.execute("SELECT set_config('app.actor_user_id',%s,true)", (str(user_id),))

    def post(self, email, *, headers=None, extra=None):
        return self.client.post(URL,headers={**base.ORIGIN,CSRF_HEADER:self.client.cookies.get(CSRF_COOKIE) or "",**(headers or {})},
                                json={"email":email,**(extra or {})})

    def team(self):
        leader = self.signed_in()
        team = self.create().json()["data"]
        return leader,team

    def project_submission(self, leader, team):
        advisor,_ = self.fixture("Advisor fixture", "advisor")
        self.actor(leader["id"])
        project = self.conn.execute("INSERT INTO public.projects(name,team_id,created_by) VALUES ('Member phase fixture',%s,%s) RETURNING id", (team["id"],leader["id"])).fetchone()[0]
        invite = self.conn.execute("INSERT INTO public.advisor_invitations(project_id,advisor_id,sent_by) VALUES (%s,%s,%s) RETURNING id", (project,advisor,leader["id"])).fetchone()[0]
        self.actor(advisor)
        self.conn.execute("SELECT public.v1_resolve_invitation(%s,'accepted')", (invite,))
        self.actor(leader["id"])
        submission = self.conn.execute("INSERT INTO public.project_submissions(project_id,submitted_by) VALUES (%s,%s) RETURNING id", (project,leader["id"])).fetchone()[0]
        self.conn.execute("INSERT INTO public.project_submission_files(submission_id,file_data,original_filename,mime_type) VALUES (%s,%s,'fixture.pdf','application/pdf')", (submission,b'%PDF-fixture'))
        self.conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        return project,submission,advisor

    def test_add_normalized_email_returns_only_public_member_and_refresh_list(self):
        leader,_ = self.team()
        target,email = self.fixture()
        response = self.post(" \t"+email.upper()+"\n")
        self.assertEqual(response.status_code,201)
        row = response.json()["data"]
        self.assertEqual(set(row),{"id","user_id","full_name","role"})
        self.assertEqual(row["user_id"],str(target))
        self.assertEqual(row["role"],"member")
        self.assertIsInstance(row["id"],str)
        self.assertNotIn(email,response.text)
        self.assertEqual(response.headers["cache-control"],"no-store")
        self.assertFalse(response.headers.get_list("set-cookie"))
        listed = self.client.get(URL).json()["data"]
        self.assertEqual([m["user_id"] for m in listed],[leader["id"],str(target)])
        self.assertEqual(listed[1],row)
        self.assert_counts(1,2)

    def test_list_order_is_leader_then_database_name_then_membership_id(self):
        self.team()
        added=[]
        for name in ("Zeta","Alpha","Alpha"):
            _,email=self.fixture(name)
            response=self.post(email)
            self.assertEqual(response.status_code,201)
            added.append(response.json()["data"])
        response=self.client.get(URL)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()["data"][1:],[added[1],added[2],added[0]])

    def test_member_reads_own_team_but_cannot_add(self):
        member=self.signed_in()
        leader,_=self.team()
        self.assertEqual(self.post(member["email"]).status_code,201)
        self.client.cookies.clear()
        self.assertEqual(self.client.post("/api/v1/auth/login",headers=base.ORIGIN,json={"email":member["email"],"password":base.PASSWORD}).status_code,200)
        data=self.client.get(URL).json()["data"]
        self.assertEqual([m["user_id"] for m in data],[leader["id"],member["id"]])
        _,email=self.fixture()
        self.assert_error(self.post(email),403,"TEAM_MEMBER_ADDITION_FORBIDDEN")
        self.assert_counts(1,2)

    def test_queries_and_headers_cannot_select_or_modify_other_team(self):
        first,first_team=self.team()
        self.team()
        query="?team_id="+first_team["id"]+"&user_id="+first["id"]
        response=self.client.get(URL+query,headers={"X-User-ID":first["id"],"X-Role":"leader"})
        self.assertNotIn(first["id"],[m["user_id"] for m in response.json()["data"]])
        target,email=self.fixture()
        response=self.client.post(URL+query,headers={**base.ORIGIN,CSRF_HEADER:self.client.cookies.get(CSRF_COOKIE),"X-User-ID":first["id"]},json={"email":email})
        self.assertEqual(response.status_code,201)
        self.assertNotEqual(str(self.conn.execute("SELECT team_id FROM public.team_members WHERE user_id=%s",(target,)).fetchone()[0]),first_team["id"])

    def test_missing_and_invalid_sessions_cannot_read_or_write(self):
        for token in (None,"bad","A"*43):
            self.client.cookies.clear()
            if token:self.client.cookies.set(SESSION_COOKIE,token)
            self.assert_error(self.client.get(URL),401,"AUTHENTICATION_REQUIRED")
            self.assert_error(self.post("missing@example.test"),401,"AUTHENTICATION_REQUIRED")
        self.assert_counts()

    def test_expired_and_revoked_sessions_cannot_read_or_write(self):
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
            self.assert_error(self.client.get(URL),401,"AUTHENTICATION_REQUIRED")
            self.assert_error(self.post("missing@example.test"),401,"AUTHENTICATION_REQUIRED")

    def test_staff_and_no_team_cannot_read_or_write(self):
        for role in ("student","advisor","coordinator"):
            self.signed_in(role)
            status,code=(404,"TEAM_NOT_FOUND") if role=="student" else (403,"TEAM_ACCESS_FORBIDDEN")
            self.assert_error(self.client.get(URL),status,code)
            self.assert_error(self.post("missing@example.test"),status,code)
        self.assert_counts()

    def test_get_does_not_require_csrf_origin_or_renew_session(self):
        self.team()
        token=self.client.cookies.get(SESSION_COOKIE)
        before=self.conn.execute("SELECT expires_at FROM auth.sessions WHERE token_hash=%s",(session_digest(token),)).fetchone()
        self.client.cookies.delete(CSRF_COOKIE)
        response=self.client.get(URL)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.headers["cache-control"],"no-store")
        self.assertFalse(response.headers.get_list("set-cookie"))
        self.assertEqual(self.conn.execute("SELECT expires_at FROM auth.sessions WHERE token_hash=%s",(session_digest(token),)).fetchone(),before)

    def test_post_requires_origin_and_session_bound_csrf(self):
        self.team()
        _,email=self.fixture()
        for value in ("","wrong"):
            self.assert_error(self.post(email,headers={CSRF_HEADER:value}),403,"CSRF_INVALID")
        for origin in ("","null","http://untrusted.example.test"):
            self.assert_error(self.post(email,headers={"Origin":origin}),403,"ORIGIN_NOT_ALLOWED")
        self.assert_counts(1,1)

    def test_invalid_email_extra_fields_and_json_do_not_echo_input(self):
        self.team()
        for email in (None,False,12,[],"","bad","DoNotEchoFixture@","x"*256+"@example.test","bad\x00@example.test"):
            response=self.post(email)
            self.assert_error(response,422,"VALIDATION_ERROR")
            self.assertNotIn("DoNotEchoFixture",response.text)
        for field in ("team_id","actor_user_id","user_id","role","members"):
            self.assert_error(self.post("student@example.test",extra={field:"DoNotEchoFixture"}),422,"VALIDATION_ERROR")
        response=self.client.post(URL,headers={**base.ORIGIN,CSRF_HEADER:self.client.cookies.get(CSRF_COOKIE),"Content-Type":"application/json"},content="{bad")
        self.assert_error(response,422,"VALIDATION_ERROR")
        self.assert_counts(1,1)

    def test_missing_or_non_student_target_is_same_private_404(self):
        self.team()
        missing=self.post("missing-"+uuid4().hex+"@example.test")
        self.assert_error(missing,404,"MEMBER_NOT_FOUND")
        for role in ("advisor","coordinator"):
            _,email=self.fixture(role=role)
            response=self.post(email)
            self.assert_error(response,404,"MEMBER_NOT_FOUND")
            self.assertEqual(response.json(),missing.json())
        self.assert_counts(1,1)

    def test_self_duplicate_and_other_team_are_generic_409(self):
        first,private_team=self.team()
        other,_=self.team()
        self.assert_error(self.post(first["email"]),409,"MEMBER_UNAVAILABLE")
        self.assert_error(self.post(other["email"]),409,"MEMBER_UNAVAILABLE")
        _,email=self.fixture()
        self.assertEqual(self.post(email).status_code,201)
        self.assert_error(self.post(email),409,"MEMBER_UNAVAILABLE")
        self.assert_counts(2,3)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM public.team_members WHERE team_id=%s",(private_team["id"],)).fetchone()[0],1)

    def test_unique_constraint_after_stale_precheck_maps_only_membership_conflict(self):
        leader,_=self.team()
        with patch.object(TeamRepository,"membership_exists",return_value=False):
            self.assert_error(self.post(leader["email"]),409,"MEMBER_UNAVAILABLE")
        self.assert_counts(1,1)

    def test_authority_is_rechecked_after_team_lock(self):
        self.team()
        _,email=self.fixture()
        original=TeamRepository.current_team
        calls=0
        def changed(store,actor):
            nonlocal calls
            row=original(store,actor);calls+=1
            if calls==2:return (*row[:4],"member")
            return row
        with patch.object(TeamRepository,"current_team",changed):
            self.assert_error(self.post(email),403,"TEAM_MEMBER_ADDITION_FORBIDDEN")
        self.assert_counts(1,1)

    def test_storage_and_failure_after_insert_roll_back_member(self):
        self.team()
        _,email=self.fixture()
        original=TeamRepository.insert_member
        def fail_after_insert(store,team_id,target):
            original(store,team_id,target)
            raise StorageUnavailable()
        with patch.object(TeamRepository,"insert_member",fail_after_insert):
            self.assert_error(self.post(email),500,"INTERNAL_ERROR")
        with patch.object(TeamRepository,"current_members",side_effect=StorageUnavailable()):
            self.assert_error(self.client.get(URL),500,"INTERNAL_ERROR")
        self.assert_counts(1,1)

    def test_project_before_first_submission_allows_member(self):
        leader,team=self.team()
        self.actor(leader["id"])
        self.conn.execute("INSERT INTO public.projects(name,team_id,created_by) VALUES ('Before submission',%s,%s)",(team["id"],leader["id"]))
        _,email=self.fixture()
        self.assertEqual(self.post(email).status_code,201)

    def test_advisor_pending_revision_and_approved_phases(self):
        leader,team=self.team()
        _,submission,advisor=self.project_submission(leader,team)
        _,email=self.fixture()
        self.assert_error(self.post(email),409,"MEMBER_ADDITION_LOCKED")
        # Direct app DML still reaches the authoritative V1 guard.
        self.actor(leader["id"])
        target=self.conn.execute("SELECT id FROM public.users WHERE email=%s",(email,)).fetchone()[0]
        with self.assertRaises(psycopg.errors.RaiseException),self.conn.transaction():
            TeamRepository(self.conn).insert_member(team["id"],target)
        for status in ("revision_requested","approved"):
            with self.conn.transaction(force_rollback=True):
                self.actor(advisor)
                self.conn.execute("SELECT public.v1_review_submission(%s,%s,%s)",(submission,status,"Fixture revision" if status=="revision_requested" else None))
                response=self.post(email)
                if status=="revision_requested":self.assertEqual(response.status_code,201)
                else:self.assert_error(response,409,"MEMBER_ADDITION_LOCKED")

    def test_committee_partial_revision_approved_and_resubmission_phases(self):
        leader,team=self.team()
        project,submission,advisor=self.project_submission(leader,team)
        self.actor(advisor)
        self.conn.execute("SELECT public.v1_review_submission(%s,'approved',NULL)",(submission,))
        coordinator,_=self.fixture(role="coordinator")
        committee=[self.fixture(role="advisor")[0] for _ in range(3)]
        self.actor(coordinator)
        assignments=[self.conn.execute("SELECT public.v1_appoint_committee(%s,%s)",(project,user_id)).fetchone()[0] for user_id in committee]
        _,email=self.fixture()
        for decision in ("revision_requested","approved"):
            with self.conn.transaction(force_rollback=True):
                for i,user_id in enumerate(committee):
                    self.actor(user_id)
                    self.conn.execute("SELECT public.v1_cast_vote(%s,%s,%s,%s)",(submission,assignments[i],decision,"Fixture vote"))
                    if i<2:self.assert_error(self.post(email),409,"MEMBER_ADDITION_LOCKED")
                if decision=="approved":
                    self.assert_error(self.post(email),409,"MEMBER_ADDITION_LOCKED")
                else:
                    with self.conn.transaction(force_rollback=True):
                        self.assertEqual(self.post(email).status_code,201)
                    self.actor(leader["id"])
                    self.conn.execute("SET CONSTRAINTS public.c_submission_requires_file DEFERRED")
                    new=self.conn.execute("INSERT INTO public.project_submissions(project_id,submitted_by) VALUES (%s,%s) RETURNING id",(project,leader["id"])).fetchone()[0]
                    self.conn.execute("INSERT INTO public.project_submission_files(submission_id,file_data,original_filename,mime_type) VALUES (%s,%s,'fixture.pdf','application/pdf')",(new,b'%PDF-fixture'))
                    self.conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
                    self.assert_error(self.post(email),409,"MEMBER_ADDITION_LOCKED")


if __name__ == "__main__":
    unittest.main()
