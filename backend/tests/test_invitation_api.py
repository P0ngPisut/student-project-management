"""Full invitation HTTP/PostgreSQL workflow; owner fixtures, effective app requests, ROLLBACK."""

from contextlib import contextmanager
import unittest
from unittest.mock import patch

import psycopg

from backend.auth_api import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE
from backend.auth_security import session_digest
from backend.auth_store import StorageUnavailable
from backend.invitation_api import get_invitation_uow
from backend.invitation_store import InvitationRepository, invitation_transaction_on
from backend.project_api import get_project_uow
from backend.project_store import project_transaction_on
from backend.tests import test_project_api as project_base, test_team_api as base
from database.tests.Auth_Regression import switch

HISTORY = "/api/v1/projects/me/advisor-invitations"
CANDIDATES = "/api/v1/projects/me/advisor-candidates"
INBOX = "/api/v1/advisor-invitations/me"


class InvitationAPIIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base.TeamAPIIntegrationTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        base.TeamAPIIntegrationTests.tearDownClass.__func__(cls)

    def setUp(self):
        base.TeamAPIIntegrationTests.setUp(self)
        self.app.dependency_overrides[get_project_uow] = lambda: lambda: project_transaction_on(self.conn)
        self.app.dependency_overrides[get_invitation_uow] = lambda: lambda: invitation_transaction_on(self.conn)

    tearDown = base.TeamAPIIntegrationTests.tearDown
    signed_in = base.TeamAPIIntegrationTests.signed_in
    create_team = base.TeamAPIIntegrationTests.create
    assert_error = base.TeamAPIIntegrationTests.assert_error
    login_as = project_base.ProjectAPIIntegrationTests.login_as
    member = project_base.ProjectAPIIntegrationTests.member

    def headers(self):
        return {**base.ORIGIN, CSRF_HEADER:self.client.cookies.get(CSRF_COOKIE) or ""}

    def setup_project(self):
        leader=self.signed_in()
        team=self.create_team().json()["data"]
        response=self.client.post("/api/v1/projects",headers=self.headers(),json={"name":"Invitation private project","description":"Private description"})
        self.assertEqual(response.status_code,201)
        return leader,team,response.json()["data"]

    def send(self, advisor, extra=None):
        return self.client.post(HISTORY,headers=self.headers(),json={"advisor_id":str(advisor),**(extra or {})})

    def resolve(self, invitation, decision):
        path=f"/api/v1/advisor-invitations/{invitation}/"+("cancel" if decision=="cancelled" else "respond")
        return self.client.post(path,headers=self.headers(),json={} if decision=="cancelled" else {"decision":decision})

    def scenario(self):
        leader,team,project=self.setup_project()
        advisor=self.signed_in("advisor")
        self.login_as(leader)
        response=self.send(advisor["id"])
        self.assertEqual(response.status_code,201)
        return leader,team,project,advisor,response.json()["data"]

    def test_candidates_only_advisors_minimal_fields_and_database_sort(self):
        leader,_,_=self.setup_project()
        one=self.signed_in("advisor");two=self.signed_in("advisor");staff=self.signed_in("coordinator")
        self.login_as(leader)
        response=self.client.get(CANDIDATES)
        self.assertEqual(response.status_code,200)
        rows=response.json()["data"]
        self.assertTrue(all(set(row)=={"id","full_name"} for row in rows))
        self.assertTrue({one["id"],two["id"]}.issubset({row["id"] for row in rows}))
        self.assertNotIn(staff["id"],{row["id"] for row in rows})
        expected=self.conn.execute("SELECT id,full_name FROM public.users WHERE role='advisor' ORDER BY full_name,id").fetchall()
        self.assertEqual(rows,[{"id":str(r[0]),"full_name":r[1]} for r in expected])

    def test_empty_history_is_array_and_candidates_match_existing_baseline(self):
        self.setup_project()
        self.assertEqual(self.client.get(HISTORY).json(),{"data":[]})
        expected=self.conn.execute("SELECT count(*) FROM public.users WHERE role='advisor'").fetchone()[0]
        self.assertEqual(len(self.client.get(CANDIDATES).json()["data"]),expected)

    def test_send_pending_and_team_history_have_exact_public_shape(self):
        leader,_,project,advisor,invitation=self.scenario()
        self.assertEqual(set(invitation),{"id","advisor","status","sent_at","resolved_at"})
        self.assertEqual(invitation["advisor"],{"id":advisor["id"],"full_name":advisor["full_name"]})
        self.assertEqual(invitation["status"],"pending")
        self.assertIsNone(invitation["resolved_at"])
        self.assertEqual(self.client.get(HISTORY).json(),{"data":[invitation]})
        row=self.conn.execute("SELECT project_id,advisor_id,sent_by,status,resolved_by,resolved_at FROM public.advisor_invitations WHERE id=%s",(invitation["id"],)).fetchone()
        self.assertEqual(row,(int(project["id"]),int(advisor["id"]),int(leader["id"]),"pending",None,None))
        self.assertNotIn(advisor["email"],str(invitation))

    def test_pending_and_accepted_advisor_projection_only_has_minimal_context(self):
        _,_,_,advisor,invitation=self.scenario()
        self.login_as(advisor)
        response=self.client.get(INBOX)
        self.assertEqual(response.status_code,200)
        item=next(i for i in response.json()["data"] if i["id"]==invitation["id"])
        self.assertEqual(set(item),{"id","status","sent_at","resolved_at","project_context"})
        self.assertEqual(item["project_context"],{"team_name":"Team fixture","project_name":"Invitation private project","project_description":"Private description"})
        response=self.resolve(invitation["id"],"accepted")
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()["data"]["project_context"],item["project_context"])
        row=self.conn.execute("SELECT resolved_by,resolved_at>=sent_at FROM public.advisor_invitations WHERE id=%s",(invitation["id"],)).fetchone()
        self.assertEqual(row,(int(advisor["id"]),True))

    def test_reject_removes_project_context_and_allows_new_invitation(self):
        leader,_,_,advisor,invitation=self.scenario()
        self.login_as(advisor)
        response=self.resolve(invitation["id"],"rejected")
        self.assertEqual(response.status_code,200)
        self.assertIsNone(response.json()["data"]["project_context"])
        self.assertNotIn("Invitation private project",response.text)
        self.assertNotIn("Private description",self.client.get(INBOX).text)
        self.login_as(leader)
        self.assertEqual(self.send(advisor["id"]).status_code,201)
        history=self.client.get(HISTORY).json()["data"]
        self.assertEqual([i["status"] for i in history],["pending","rejected"])
        self.assertGreater(int(history[0]["id"]),int(history[1]["id"]))

    def test_cancel_removes_advisor_context_and_preserves_history(self):
        leader,_,_,advisor,invitation=self.scenario()
        response=self.resolve(invitation["id"],"cancelled")
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()["data"]["status"],"cancelled")
        self.assertEqual(self.conn.execute("SELECT resolved_by,resolved_at>=sent_at FROM public.advisor_invitations WHERE id=%s",(invitation["id"],)).fetchone(),(int(leader["id"]),True))
        self.login_as(advisor)
        self.assertEqual(self.client.get(INBOX).json()["data"],[{**{k:v for k,v in response.json()["data"].items() if k!='advisor'},"project_context":None}])
        self.assert_error(self.resolve(invitation["id"],"accepted"),409,"INVITATION_ALREADY_RESOLVED")

    def test_duplicate_pending_and_accepted_do_not_create_or_replace_advisor(self):
        leader,_,_,advisor,invitation=self.scenario()
        self.assert_error(self.send(advisor["id"]),409,"INVITATION_ALREADY_PENDING")
        self.assert_error(self.send("9223372036854775807"),409,"INVITATION_ALREADY_PENDING")
        self.login_as(advisor)
        self.assertEqual(self.resolve(invitation["id"],"accepted").status_code,200)
        self.assert_error(self.resolve(invitation["id"],"rejected"),409,"INVITATION_ALREADY_RESOLVED")
        self.login_as(leader)
        self.assert_error(self.send(advisor["id"]),409,"ADVISOR_ALREADY_ACCEPTED")
        self.assert_error(self.resolve(invitation["id"],"cancelled"),409,"INVITATION_ALREADY_RESOLVED")
        self.assertEqual(len(self.client.get(HISTORY).json()["data"]),1)

    def test_member_reads_history_but_cannot_send_cancel_or_list_candidates(self):
        leader,team,_,advisor,invitation=self.scenario()
        self.member(leader,team)
        self.assertEqual(self.client.get(HISTORY).status_code,200)
        self.assert_error(self.client.get(CANDIDATES),403,"INVITATION_ACTION_FORBIDDEN")
        self.assert_error(self.send(advisor["id"]),403,"INVITATION_ACTION_FORBIDDEN")
        self.assert_error(self.resolve(invitation["id"],"cancelled"),403,"INVITATION_ACTION_FORBIDDEN")

    def test_current_leader_can_cancel_after_transfer_original_sender_cannot(self):
        leader,team,_,_,invitation=self.scenario()
        member=self.member(leader,team)
        self.conn.execute("SELECT set_config('app.actor_user_id',%s,true)",(leader["id"],))
        self.conn.execute("SET CONSTRAINTS public.c_team_created_has_leader,public.c_team_member_cardinality DEFERRED")
        self.conn.execute("SELECT public.v1_transfer_team_leader(%s,%s)",(team["id"],member["id"]))
        self.conn.execute("SET CONSTRAINTS public.c_team_created_has_leader,public.c_team_member_cardinality IMMEDIATE")
        self.login_as(leader)
        self.assert_error(self.resolve(invitation["id"],"cancelled"),403,"INVITATION_ACTION_FORBIDDEN")
        self.login_as(member)
        self.assertEqual(self.resolve(invitation["id"],"cancelled").status_code,200)
        self.assertEqual(self.conn.execute("SELECT sent_by,resolved_by FROM public.advisor_invitations WHERE id=%s",(invitation["id"],)).fetchone(),(int(leader["id"]),int(member["id"])))

    def test_exited_member_immediately_loses_team_history_and_cancel_access(self):
        leader,team,_,_,invitation=self.scenario()
        member=self.member(leader,team)
        membership=self.conn.execute("SELECT id FROM public.team_members WHERE user_id=%s",(member["id"],)).fetchone()[0]
        self.conn.execute("SELECT set_config('app.actor_user_id',%s,true)",(member["id"],))
        self.conn.execute("SELECT public.v1_exit_team_member(%s)",(membership,))
        self.assert_error(self.client.get(HISTORY),404,"TEAM_NOT_FOUND")
        self.assert_error(self.resolve(invitation["id"],"cancelled"),404,"INVITATION_NOT_FOUND")

    def test_other_advisor_or_team_cannot_read_or_resolve_target_invitation(self):
        _,_,_,_,invitation=self.scenario()
        self.signed_in("advisor")
        self.assertEqual(self.client.get(INBOX).json(),{"data":[]})
        self.assert_error(self.resolve(invitation["id"],"accepted"),404,"INVITATION_NOT_FOUND")
        self.setup_project()
        self.assertEqual(self.client.get(HISTORY+"?invitation_id="+invitation["id"]).json(),{"data":[]})
        self.assert_error(self.resolve(invitation["id"],"cancelled"),404,"INVITATION_NOT_FOUND")

    def test_missing_invitation_and_forged_identity_do_not_disclose_data(self):
        _,_,_,advisor,invitation=self.scenario()
        stranger=self.signed_in("advisor")
        response=self.client.post(f"/api/v1/advisor-invitations/{invitation['id']}/respond?advisor_id={advisor['id']}",
            headers={**self.headers(),"X-User-ID":advisor["id"],"X-Role":"advisor"},json={"decision":"accepted"})
        self.assert_error(response,404,"INVITATION_NOT_FOUND")
        self.assert_error(self.resolve("9223372036854775807","accepted"),404,"INVITATION_NOT_FOUND")
        self.assertNotEqual(stranger["id"],advisor["id"])

    def test_no_team_no_project_and_wrong_roles(self):
        for role in ("student","advisor","coordinator"):
            self.signed_in(role)
            for url in (HISTORY,CANDIDATES):
                self.assert_error(self.client.get(url),404 if role=='student' else 403,"TEAM_NOT_FOUND" if role=='student' else "INVITATION_ACCESS_FORBIDDEN")
            if role!='advisor':self.assert_error(self.client.get(INBOX),403,"INVITATION_ACCESS_FORBIDDEN")
        self.signed_in();self.create_team()
        for url in (HISTORY,CANDIDATES):self.assert_error(self.client.get(url),404,"PROJECT_NOT_FOUND")

    def test_unknown_or_non_advisor_target_is_same_404(self):
        leader,_,_=self.setup_project()
        first=self.send("9223372036854775807")
        self.assert_error(first,404,"ADVISOR_NOT_FOUND")
        self.assert_error(self.send(leader["id"]),404,"ADVISOR_NOT_FOUND")
        self.assertEqual(first.json(),self.send(leader["id"]).json())
        self.assertEqual(self.client.get(HISTORY).json(),{"data":[]})

    def test_all_endpoints_require_authentication(self):
        for token in (None,"bad","A"*43):
            self.client.cookies.clear()
            if token:self.client.cookies.set(SESSION_COOKIE,token)
            for url in (HISTORY,CANDIDATES,INBOX):self.assert_error(self.client.get(url),401,"AUTHENTICATION_REQUIRED")
            self.assert_error(self.send("1"),401,"AUTHENTICATION_REQUIRED")
            for action in ('accepted','cancelled'):self.assert_error(self.resolve("1",action),401,"AUTHENTICATION_REQUIRED")

    def test_expired_and_revoked_sessions_cannot_read_or_resolve(self):
        _,_,_,advisor,invitation=self.scenario()
        for mode in ("expired","revoked"):
            self.login_as(advisor)
            token=self.client.cookies.get(SESSION_COOKIE)
            if mode=='expired':
                with self.conn.cursor() as cur:
                    switch(cur,"project_owner")
                    cur.execute("UPDATE auth.sessions SET created_at=clock_timestamp()-interval '2 hours',expires_at=clock_timestamp()-interval '1 hour' WHERE token_hash=%s",(session_digest(token),))
                    switch(cur,"project_app")
            else:
                self.client.post('/api/v1/auth/logout',headers=self.headers())
                self.client.cookies.set(SESSION_COOKIE,token)
            self.assert_error(self.client.get(INBOX),401,"AUTHENTICATION_REQUIRED")
            self.assert_error(self.resolve(invitation['id'],'accepted'),401,"AUTHENTICATION_REQUIRED")

    def test_gets_need_no_csrf_origin_and_do_not_renew_session(self):
        leader,_,_,advisor,_=self.scenario()
        for user,urls in ((leader,(HISTORY,CANDIDATES)),(advisor,(INBOX,))):
            self.login_as(user)
            digest=session_digest(self.client.cookies.get(SESSION_COOKIE))
            before=self.conn.execute("SELECT expires_at FROM auth.sessions WHERE token_hash=%s",(digest,)).fetchone()
            self.client.cookies.delete(CSRF_COOKIE)
            for url in urls:
                response=self.client.get(url)
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.headers['cache-control'],'no-store')
                self.assertFalse(response.headers.get_list('set-cookie'))
            self.assertEqual(self.conn.execute("SELECT expires_at FROM auth.sessions WHERE token_hash=%s",(digest,)).fetchone(),before)

    def test_writes_require_origin_and_session_csrf(self):
        _,_,_,advisor,invitation=self.scenario()
        for action in ('send','cancel','respond'):
            if action=='respond':self.login_as(advisor)
            url=HISTORY if action=='send' else f"/api/v1/advisor-invitations/{invitation['id']}/"+('cancel' if action=='cancel' else 'respond')
            body={'advisor_id':advisor['id']} if action=='send' else ({} if action=='cancel' else {'decision':'accepted'})
            for headers,code in (({**self.headers(),CSRF_HEADER:'bad'},'CSRF_INVALID'),({**self.headers(),'Origin':'http://untrusted.example.test'},'ORIGIN_NOT_ALLOWED')):
                self.assert_error(self.client.post(url,headers=headers,json=body),403,code)

    def test_strict_input_ids_decisions_and_cancellation_extra_fields(self):
        leader,_,_,advisor,invitation=self.scenario()
        for value in (1,True,None,'','0','-1','1.0','x','9223372036854775808','9'*100):
            self.assert_error(self.client.post(HISTORY,headers=self.headers(),json={'advisor_id':value}),422,'VALIDATION_ERROR')
        for key in ('project_id','team_id','sent_by','status','sent_at','resolved_by'):
            response=self.send(advisor['id'],{key:'DoNotEchoFixture'})
            self.assert_error(response,422,'VALIDATION_ERROR');self.assertNotIn('DoNotEchoFixture',response.text)
        self.assert_error(self.client.post(f"/api/v1/advisor-invitations/{invitation['id']}/cancel",headers=self.headers(),json={'status':'accepted'}),422,'VALIDATION_ERROR')
        self.login_as(advisor)
        for value in ('pending','cancelled',None,1,'DoNotEchoFixture'):
            response=self.client.post(f"/api/v1/advisor-invitations/{invitation['id']}/respond",headers=self.headers(),json={'decision':value})
            self.assert_error(response,422,'VALIDATION_ERROR');self.assertNotIn('DoNotEchoFixture',response.text)
        for value in ('0','-1','bad','9223372036854775808'):
            self.assert_error(self.resolve(value,'accepted'),422,'VALIDATION_ERROR')

    def test_actual_unique_conflict_after_stale_precheck_is_generic_409(self):
        _,_,_,advisor,_=self.scenario()
        with patch.object(InvitationRepository,'active',return_value=None):
            self.assert_error(self.send(advisor['id']),409,'INVITATION_CONFLICT')
        self.assertEqual(len(self.client.get(HISTORY).json()['data']),1)

    def test_authority_and_state_rechecked_after_locks(self):
        leader,_,_,advisor,invitation=self.scenario()
        original=InvitationRepository.authorized
        for mode in ('missing','member','resolved'):
            calls=0
            def changed(store,*args,**kwargs):
                nonlocal calls
                row=original(store,*args,**kwargs);calls+=1
                if calls==2:
                    if mode=='missing':return None
                    row=list(row);row[4 if mode=='member' else 3]='member' if mode=='member' else 'cancelled';return row
                return row
            with patch.object(InvitationRepository,'authorized',changed):
                status,code={'missing':(404,'INVITATION_NOT_FOUND'),'member':(403,'INVITATION_ACTION_FORBIDDEN'),'resolved':(409,'INVITATION_ALREADY_RESOLVED')}[mode]
                self.assert_error(self.resolve(invitation['id'],'cancelled'),status,code)
        self.assertEqual(self.conn.execute("SELECT status FROM public.advisor_invitations WHERE id=%s",(invitation['id'],)).fetchone(),('pending',))

    def test_insert_resolution_and_completion_failures_roll_back(self):
        leader,_,_=self.setup_project();advisor=self.signed_in('advisor');self.login_as(leader)
        original=InvitationRepository.insert
        def fail_insert(store,*args):original(store,*args);raise StorageUnavailable()
        with patch.object(InvitationRepository,'insert',fail_insert):self.assert_error(self.send(advisor['id']),500,'INTERNAL_ERROR')
        self.assertEqual(self.client.get(HISTORY).json(),{'data':[]})
        invitation=self.send(advisor['id']).json()['data']
        self.login_as(advisor)
        resolve=InvitationRepository.resolve_function
        def fail_resolve(store,*args):resolve(store,*args);raise StorageUnavailable()
        with patch.object(InvitationRepository,'resolve_function',fail_resolve):self.assert_error(self.resolve(invitation['id'],'accepted'),500,'INTERNAL_ERROR')
        @contextmanager
        def fail_completion():
            with invitation_transaction_on(self.conn) as store:
                yield store
                raise StorageUnavailable()
        self.app.dependency_overrides[get_invitation_uow]=lambda:fail_completion
        self.assert_error(self.resolve(invitation['id'],'accepted'),500,'INTERNAL_ERROR')
        self.assertEqual(self.conn.execute("SELECT status,resolved_by,resolved_at FROM public.advisor_invitations WHERE id=%s",(invitation['id'],)).fetchone(),('pending',None,None))

    def test_unexpected_pg_errors_are_sanitized_not_misclassified(self):
        leader,_,_=self.setup_project();advisor=self.signed_in('advisor');self.login_as(leader)
        for error in (psycopg.errors.InsufficientPrivilege('DoNotEchoSQL'),psycopg.errors.RaiseException('DoNotEchoSQL'),psycopg.errors.UniqueViolation('DoNotEchoSQL')):
            with patch.object(InvitationRepository,'insert',side_effect=error):
                response=self.send(advisor['id']);self.assert_error(response,500,'INTERNAL_ERROR');self.assertNotIn('DoNotEchoSQL',response.text)

    def test_trigger_identity_and_final_state_protections_remain_active(self):
        _,_,_,advisor,invitation=self.scenario()
        for sql in ("DELETE FROM public.advisor_invitations WHERE id=%s","UPDATE public.advisor_invitations SET sent_by=-1 WHERE id=%s"):
            with self.assertRaises(psycopg.Error),self.conn.transaction():
                self.conn.execute('SET LOCAL ROLE project_owner');self.conn.execute(sql,(invitation['id'],))
        self.login_as(advisor);self.resolve(invitation['id'],'rejected')
        with self.assertRaises(psycopg.errors.RaiseException),self.conn.transaction():
            self.conn.execute("SELECT public.v1_resolve_invitation(%s,'accepted')",(invitation['id'],))


if __name__ == '__main__':
    unittest.main()
