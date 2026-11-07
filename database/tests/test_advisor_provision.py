"""New-advisor CLI/boundary tests and real PostgreSQL rollback-only provisioning."""

from contextlib import redirect_stdout
import getpass
import io
import json
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4
import warnings

from backend.auth_api import CSRF_COOKIE, CSRF_HEADER
from backend.auth_security import hash_password, verify_password
from backend.auth_store import open_auth_connection, assert_auth_connection
from backend.invitation_api import get_invitation_uow
from backend.invitation_store import invitation_transaction_on
from backend.project_api import get_project_uow
from backend.project_store import project_transaction_on
from backend.tests import test_team_api as base
from database.tests.Auth_Regression import switch
from database.tools import Auth_Provision_Advisor as tool

PASSWORD = 'ProvisionFixtureA1'


class AdvisorProvisionBoundaryTests(unittest.TestCase):
    def invoke(self, args):
        out=io.StringIO()
        with redirect_stdout(out):status=tool.main(args)
        return status,json.loads(out.getvalue())

    def test_default_is_dry_run_and_password_is_not_a_command_argument(self):
        with patch.object(tool,'prompt_password',return_value=PASSWORD),patch.object(tool,'provision',return_value={'result':'PASS'}) as provision:
            status,_=self.invoke(['--full-name','Advisor fixture','--email','advisor@example.test'])
            self.assertEqual(status,0)
            provision.assert_called_once_with('Advisor fixture','advisor@example.test',PASSWORD,apply=False)

    def test_explicit_apply_is_only_forwarded_after_database_confirmation_using_mock(self):
        with patch.object(tool,'prompt_password',return_value=PASSWORD),patch.object(tool,'provision',return_value={'result':'PASS'}) as provision:
            status,_=self.invoke(['--apply','--confirm-database',tool.TEST_DB,'--full-name','Advisor fixture','--email','advisor@example.test'])
            self.assertEqual(status,0)
            self.assertTrue(provision.call_args.kwargs['apply'])

    def test_apply_without_confirmation_and_wrong_target_never_connect(self):
        for args in (['--apply'],['--apply','--confirm-database','other_database'],['--confirm-database','other_database']):
            with patch.object(tool,'connect_test_database') as connect,patch.object(tool,'prompt_password') as prompt:
                status,result=self.invoke(args)
                self.assertEqual((status,result['code']),(1,'TEST_DATABASE_CONFIRMATION_REQUIRED'))
                connect.assert_not_called();prompt.assert_not_called()

    def test_unknown_password_option_is_rejected_without_echo(self):
        with patch.object(tool,'connect_test_database') as connect:
            status,result=self.invoke(['--password','DoNotEchoPasswordFixtureA1'])
            self.assertEqual((status,result['code']),(1,'ARGUMENT_ERROR'))
            self.assertNotIn('DoNotEchoPasswordFixtureA1',str(result));connect.assert_not_called()

    def test_check_has_no_account_or_password_prompts(self):
        with patch.object(tool,'check',return_value={'result':'PASS'}),patch.object(tool,'prompt_password') as password,patch('builtins.input') as account:
            status,_=self.invoke(['--check'])
            self.assertEqual(status,0);password.assert_not_called();account.assert_not_called()

    def test_non_tty_secret_input_fails_closed(self):
        with patch.object(tool.sys.stdin,'isatty',return_value=False),patch('getpass.getpass') as password:
            with self.assertRaises(tool.ProvisionError) as caught:tool.prompt_password()
            self.assertEqual(caught.exception.code,'PASSWORD_TTY_REQUIRED');password.assert_not_called()

    def test_getpass_fallback_warning_and_mismatch_do_not_echo_password(self):
        def warn(*args):warnings.warn('Password input may be echoed',getpass.GetPassWarning)
        with patch.object(tool.sys.stdin,'isatty',return_value=True),patch.object(tool.sys.stderr,'isatty',return_value=True):
            for response in (warn,[PASSWORD,'DifferentFixtureA1']):
                with patch('getpass.getpass',side_effect=response):
                    with self.assertRaises(tool.ProvisionError) as caught:tool.prompt_password()
                    self.assertIn(caught.exception.code,('PASSWORD_TTY_REQUIRED','PASSWORD_MISMATCH'))
                    self.assertNotIn(PASSWORD,str(caught.exception))

    def test_invalid_account_or_password_is_rejected_before_connection(self):
        cases=[('','advisor@example.test',PASSWORD),('x'*256,'advisor@example.test',PASSWORD),
               ('Advisor','bad-email',PASSWORD),('bad\x00name','advisor@example.test',PASSWORD),
               ('bad\ud800name','advisor@example.test',PASSWORD),('Advisor','advisor@example.test','short'),
               ('Advisor','advisor@example.test','lowercase1'),('Advisor','advisor@example.test','NoDigitsHere')]
        with patch.object(tool,'connect_test_database') as connect:
            for name,email,password in cases:
                with self.assertRaises(tool.ProvisionError):tool.provision(name,email,password)
            connect.assert_not_called()

    def test_wrong_database_guard_stops_before_role_change_or_writes(self):
        conn=MagicMock();conn.execute.return_value.fetchone.return_value=('other_database',)
        with self.assertRaises(tool.ProvisionError) as caught:tool.guard_owner(conn)
        self.assertEqual(caught.exception.code,'TEST_DATABASE_REQUIRED')
        conn.execute.assert_called_once_with('SELECT current_database()')


class AdvisorProvisionIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):base.TeamAPIIntegrationTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):base.TeamAPIIntegrationTests.tearDownClass.__func__(cls)

    def setUp(self):
        base.TeamAPIIntegrationTests.setUp(self)
        self.email='provision-'+uuid4().hex+'@example.test'
        self.app.dependency_overrides[get_project_uow]=lambda:lambda:project_transaction_on(self.conn)
        self.app.dependency_overrides[get_invitation_uow]=lambda:lambda:invitation_transaction_on(self.conn)

    tearDown=base.TeamAPIIntegrationTests.tearDown
    signed_in=base.TeamAPIIntegrationTests.signed_in
    create_team=base.TeamAPIIntegrationTests.create

    def app_role(self):
        with self.conn.cursor() as cur:switch(cur,'project_app')

    def test_creation_is_atomic_normalized_and_hash_verifies_exact_password(self):
        user=tool.create_advisor_on(self.conn,' \tAdvisor fixture\n',' '+self.email.upper()+'\t',PASSWORD)
        self.assertEqual(user['role'],'advisor');self.assertEqual(user['email'],self.email)
        self.assertEqual(user['full_name'],'Advisor fixture');self.assertIsInstance(user['id'],str)
        encoded=self.conn.execute('SELECT password_hash FROM auth.credentials WHERE user_id=%s',(user['id'],)).fetchone()[0]
        self.assertTrue(encoded.startswith('$argon2id$'));self.assertTrue(verify_password(PASSWORD,encoded))
        self.assertFalse(verify_password(' '+PASSWORD,encoded));self.assertNotIn(encoded,json.dumps(user));self.assertNotIn(PASSWORD,json.dumps(user))
        self.assertEqual(self.conn.execute('SELECT current_user').fetchone(),('project_owner',))

    def test_existing_user_password_role_name_and_credentials_are_unchanged(self):
        with self.conn.cursor() as cur:switch(cur,'project_owner')
        original_hash=hash_password('ExistingFixtureA1')
        user=self.conn.execute("INSERT INTO public.users(full_name,email,role) VALUES ('Existing student',%s,'student') RETURNING id",(self.email,)).fetchone()[0]
        self.conn.execute('INSERT INTO auth.credentials(user_id,password_hash) VALUES (%s,%s)',(user,original_hash))
        with self.assertRaises(tool.ProvisionError) as caught:tool.create_advisor_on(self.conn,'Replacement',self.email.upper(),PASSWORD)
        self.assertEqual(caught.exception.code,'ACCOUNT_ALREADY_EXISTS')
        row=self.conn.execute('SELECT u.full_name,u.role,c.password_hash FROM public.users u JOIN auth.credentials c ON c.user_id=u.id WHERE u.id=%s',(user,)).fetchone()
        self.assertEqual(row,('Existing student','student',original_hash))

    def test_existing_advisor_without_credentials_is_not_automatically_activated(self):
        with self.conn.cursor() as cur:switch(cur,'project_owner')
        user=self.conn.execute("INSERT INTO public.users(full_name,email,role) VALUES ('Existing advisor',%s,'advisor') RETURNING id",(self.email,)).fetchone()[0]
        with self.assertRaises(tool.ProvisionError) as caught:tool.create_advisor_on(self.conn,'Replacement',self.email,PASSWORD)
        self.assertEqual(caught.exception.code,'ACCOUNT_ALREADY_EXISTS')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM auth.credentials WHERE user_id=%s',(user,)).fetchone()[0],0)

    def test_credential_constraint_failure_removes_new_user_in_same_savepoint(self):
        def invalid_hash(conn,user,encoded):
            conn.execute('INSERT INTO auth.credentials(user_id,password_hash) VALUES (%s,%s)',(user,'plaintext-fixture'))
        with patch.object(tool,'insert_credentials',invalid_hash):
            with self.assertRaises(tool.ProvisionError) as caught:tool.create_advisor_on(self.conn,'Advisor',self.email,PASSWORD)
        self.assertEqual(caught.exception.code,'DATABASE_OPERATION_FAILED')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM public.users WHERE email=%s',(self.email,)).fetchone()[0],0)

    def test_helper_never_commits_callers_outer_transaction(self):
        with self.conn.transaction(force_rollback=True):
            tool.create_advisor_on(self.conn,'Advisor',self.email,PASSWORD)
            self.assertEqual(self.conn.execute('SELECT count(*) FROM public.users WHERE email=%s',(self.email,)).fetchone()[0],1)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM public.users WHERE email=%s',(self.email,)).fetchone()[0],0)

    def test_default_service_dry_run_leaves_no_account(self):
        result=tool.provision('Advisor dry run',self.email,PASSWORD)
        self.assertEqual(result['mode'],'DRY_RUN');self.assertFalse(result['persisted'])
        self.assertEqual(self.conn.execute('SELECT count(*) FROM public.users WHERE email=%s',(self.email,)).fetchone()[0],0)

    def test_direct_app_login_cannot_assume_owner_for_provisioning(self):
        conn=open_auth_connection()
        try:
            with conn.transaction(force_rollback=True):
                assert_auth_connection(conn)
                with self.assertRaises(tool.ProvisionError) as caught:tool.create_advisor_on(conn,'Advisor',self.email,PASSWORD)
                self.assertEqual(caught.exception.code,'DATABASE_OPERATION_FAILED')
                assert_auth_connection(conn)
        finally:conn.rollback();conn.close()
        self.assertEqual(self.conn.execute('SELECT count(*) FROM public.users WHERE email=%s',(self.email,)).fetchone()[0],0)

    def test_provisioned_advisor_can_login_receive_invitation_and_accept_as_app(self):
        advisor=tool.create_advisor_on(self.conn,'Provisioned advisor',self.email,PASSWORD)
        self.app_role()
        leader=self.signed_in()
        self.create_team()
        headers={**base.ORIGIN,CSRF_HEADER:self.client.cookies.get(CSRF_COOKIE)}
        self.assertEqual(self.client.post('/api/v1/projects',headers=headers,json={'name':'Provision workflow'}).status_code,201)
        response=self.client.post('/api/v1/projects/me/advisor-invitations',headers=headers,json={'advisor_id':advisor['id']})
        self.assertEqual(response.status_code,201);invitation=response.json()['data']['id']
        response=self.client.post('/api/v1/auth/login',headers=base.ORIGIN,json={'email':self.email,'password':PASSWORD})
        self.assertEqual(response.status_code,200);self.assertEqual(response.json()['data']['role'],'advisor')
        headers={**base.ORIGIN,CSRF_HEADER:self.client.cookies.get(CSRF_COOKIE)}
        response=self.client.post(f'/api/v1/advisor-invitations/{invitation}/respond',headers=headers,json={'decision':'accepted'})
        self.assertEqual(response.status_code,200);self.assertEqual(response.json()['data']['status'],'accepted')
        self.assertNotEqual(leader['id'],advisor['id'])


if __name__=='__main__':unittest.main()
