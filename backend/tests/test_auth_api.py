"""HTTP + actual PostgreSQL Auth integration; all DB writes are rolled back.

An installed Auth baseline is verified, or created temporarily if absent. Each test
has a rollback-only savepoint; each API request uses another savepoint through
the same repository transaction guard. This never tests a persistent install.
"""

from contextlib import contextmanager
from pathlib import Path
import unittest
from uuid import uuid4

from dotenv import dotenv_values
from fastapi.testclient import TestClient
import psycopg

from backend.auth_api import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE, get_auth_uow
from backend.auth_security import session_digest, verify_password
from backend.auth_store import StorageUnavailable, transaction_on
from backend.main import create_app
from database.tests.Auth_Regression import APP, OWNER, TEST_DB, prepare_auth_for_tests, snapshot, switch

ORIGIN = {"Origin": "http://localhost:3000"}
PASSWORD = "ReviewPassA1"


class AuthAPIIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = None
        try:
            cfg = dotenv_values(Path(__file__).resolve().parents[1] / ".env")
            cls.conn = psycopg.connect(
                host=cfg.get("DB_HOST"), port=int(cfg.get("DB_PORT") or 5432), dbname=TEST_DB,
                user=cfg.get("DB_USER"), password=cfg.get("DB_PASSWORD"), autocommit=False,
                connect_timeout=8, options="-c statement_timeout=15000 -c lock_timeout=3000",
            )
            with cls.conn.cursor() as cur:
                cur.execute("SELECT current_database()")
                if cur.fetchone()[0] != TEST_DB:
                    raise RuntimeError("Database guard failed")
                switch(cur, OWNER)
                cls.before = snapshot(cur)
                cls.baseline_mode = prepare_auth_for_tests(cur)
                switch(cur, APP)
        except Exception as exc:
            if cls.conn is not None:
                cls.conn.rollback()
                cls.conn.close()
            raise RuntimeError("Test database setup failed; SQLSTATE=" + str(getattr(exc, "sqlstate", None))) from None

    @classmethod
    def tearDownClass(cls):
        try:
            cls.conn.rollback()
            with cls.conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SELECT current_database()")
                if cur.fetchone()[0] != TEST_DB:
                    raise AssertionError("Cleanup database guard failed")
                switch(cur, OWNER)
                if snapshot(cur) != cls.before:
                    raise AssertionError("Database baseline was not restored")
            print("Auth HTTP integration: ROLLBACK and baseline verification PASS (sequence values excluded)")
        finally:
            cls.conn.rollback()
            cls.conn.close()

    def setUp(self):
        self.fixture_tag = uuid4().hex
        self.email = "auth-http-" + self.fixture_tag + "@example.test"
        self.case_transaction = self.conn.transaction(force_rollback=True)
        self.case_transaction.__enter__()
        self.app = create_app()
        self.app.dependency_overrides[get_auth_uow] = lambda: lambda: transaction_on(self.conn)
        self.client = TestClient(self.app, base_url="http://localhost:8000")

    def tearDown(self):
        try:
            self.client.close()
        finally:
            self.case_transaction.__exit__(None, None, None)

    def register(self, email=None, password=PASSWORD, **extra):
        email = self.email if email is None else email
        return self.client.post("/api/v1/auth/register", headers=ORIGIN,
                                json={"full_name": "  Auth Student  ", "email": email, "password": password, **extra})

    def login(self, email=None, password=PASSWORD):
        email = self.email if email is None else email
        return self.client.post("/api/v1/auth/login", headers=ORIGIN, json={"email": email, "password": password})

    def logout(self, csrf=None):
        headers = dict(ORIGIN)
        if csrf is not None:
            headers[CSRF_HEADER] = csrf
        return self.client.post("/api/v1/auth/logout", headers=headers)

    def signed_in(self):
        self.assertEqual(self.register().status_code, 201)
        self.assertEqual(self.login().status_code, 200)
        return self.client.cookies.get(SESSION_COOKIE), self.client.cookies.get(CSRF_COOKIE)

    def active_user(self, token):
        with transaction_on(self.conn) as store:
            return store.active_user(session_digest(token))

    def test_existing_root_still_returns_200(self):
        self.assertEqual(self.client.get("/").json(), {"message": "Backend is running"})

    def test_me_returns_current_user_without_requiring_origin(self):
        token, _ = self.signed_in()
        response = self.client.get("/api/v1/auth/me")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"], self.active_user(token))
        self.assertEqual(set(response.json()["data"]), {"id", "full_name", "email", "role"})
        self.assertTrue(token not in response.text and PASSWORD not in response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertFalse(response.headers.get_list("set-cookie"))

    def test_me_missing_malformed_unknown_sessions_are_401(self):
        for value in (None, "bad-token", "A" * 43):
            self.client.cookies.clear()
            if value is not None:
                self.client.cookies.set(SESSION_COOKIE, value)
            self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)

    def test_me_expired_session_is_401(self):
        token, _ = self.signed_in()
        with self.conn.cursor() as cur:
            switch(cur, OWNER)
            cur.execute("""UPDATE auth.sessions SET created_at=clock_timestamp()-interval '2 hours',
                expires_at=clock_timestamp()-interval '1 hour' WHERE token_hash=%s""", (session_digest(token),))
            switch(cur, APP)
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)

    def test_me_rejects_revoked_session_token(self):
        token, csrf = self.signed_in()
        self.assertEqual(self.logout(csrf).status_code, 204)
        self.client.cookies.set(SESSION_COOKIE, token)
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)

    def test_me_reads_current_profile_from_database(self):
        token, _ = self.signed_in()
        user_id = self.active_user(token)["id"]
        with self.conn.cursor() as cur:
            switch(cur, OWNER)
            cur.execute("UPDATE public.users SET full_name=%s WHERE id=%s", ("Updated Fixture Name", user_id))
            switch(cur, APP)
        response = self.client.get("/api/v1/auth/me")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["full_name"], "Updated Fixture Name")

    def test_me_does_not_extend_expiry_or_rotate_cookies(self):
        token, _ = self.signed_in()
        with self.conn.cursor() as cur:
            cur.execute("SELECT expires_at FROM auth.sessions WHERE token_hash=%s", (session_digest(token),))
            before = cur.fetchone()[0]
        response = self.client.get("/api/v1/auth/me")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.headers.get_list("set-cookie"))
        with self.conn.cursor() as cur:
            cur.execute("SELECT expires_at FROM auth.sessions WHERE token_hash=%s", (session_digest(token),))
            self.assertEqual(cur.fetchone()[0], before)

    def test_me_does_not_trust_supplied_identity(self):
        token, _ = self.signed_in()
        response = self.client.get("/api/v1/auth/me?user_id=999&role=coordinator",
                                   headers={"X-User-Id": "999", "X-Role": "coordinator"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"], self.active_user(token))

    def test_me_database_error_is_sanitized(self):
        self.signed_in()
        @contextmanager
        def unavailable():
            raise StorageUnavailable()
            yield  # pragma: no cover
        self.app.dependency_overrides[get_auth_uow] = lambda: unavailable
        response = self.client.get("/api/v1/auth/me")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["error"]["code"], "INTERNAL_ERROR")
        self.assertTrue(PASSWORD not in response.text and "traceback" not in response.text.lower())

    def test_register_student_normalizes_and_hashes_without_autologin(self):
        response = self.register(email="  " + self.email.upper() + "  ")
        self.assertEqual(response.status_code, 201)
        user = response.json()["data"]
        self.assertEqual(set(user), {"id", "full_name", "email", "role"})
        self.assertIsInstance(user["id"], str)
        self.assertEqual((user["email"], user["role"], user["full_name"]),
                         (self.email, "student", "Auth Student"))
        self.assertFalse(response.headers.get_list("set-cookie"))
        with transaction_on(self.conn) as store:
            credential = store.credentials(user["email"])
        self.assertTrue(credential[1].startswith("$argon2id$"))
        self.assertTrue(verify_password(PASSWORD, credential[1]))
        self.assertTrue(PASSWORD not in response.text and credential[1] not in response.text)

    def test_duplicate_email_returns_409_without_overwriting_password(self):
        self.assertEqual(self.register().status_code, 201)
        response = self.register(email=self.email.upper(), password="DifferentPassA1")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "EMAIL_ALREADY_REGISTERED")
        self.assertEqual(self.login().status_code, 200)
        self.assertEqual(self.login(password="DifferentPassA1").status_code, 401)

    def test_registration_rejects_role_user_id_and_hash_spoofing(self):
        for field, value in (("role", "advisor"), ("user_id", "123"), ("password_hash", "private-fixture-marker")):
            with self.subTest(field=field):
                response = self.register(**{field: value})
                self.assertEqual(response.status_code, 422)
                self.assertTrue("private-fixture-marker" not in response.text)

    def test_confirmed_password_policy_is_enforced(self):
        for password in ("Demo123", "demo1234", "DemoTest"):
            with self.subTest():
                response = self.register(password=password)
                self.assertEqual(response.status_code, 422)
                self.assertTrue(password not in response.text)

    def test_exact_eight_character_password_is_accepted(self):
        self.assertEqual(self.register(password="Demo1234").status_code, 201)

    def test_validation_rejects_blank_long_name_and_bad_email(self):
        for values in ({"full_name": " \t "}, {"full_name": "x" * 256}, {"email": "bad@@example.test"}):
            payload = {"full_name": "Student", "email": self.email, "password": PASSWORD, **values}
            response = self.client.post("/api/v1/auth/register", headers=ORIGIN, json=payload)
            self.assertEqual(response.status_code, 422)

    def test_password_nonstring_null_and_malformed_json_are_redacted(self):
        for value in (None, 12345, {"secret": "private-fixture-marker"}):
            response = self.register(password=value)
            self.assertEqual(response.status_code, 422)
            self.assertTrue("private-fixture-marker" not in response.text)
        response = self.client.post("/api/v1/auth/register", headers={**ORIGIN, "Content-Type": "application/json"},
                                    content='{"password":"private-fixture-marker",')
        self.assertEqual(response.status_code, 422)
        self.assertTrue("private-fixture-marker" not in response.text)

    def test_login_sets_bound_cookies_and_eight_hour_db_expiry(self):
        self.assertEqual(self.register().status_code, 201)
        response = self.login(email=" " + self.email.upper() + " ")
        self.assertEqual(response.status_code, 200)
        cookies = response.headers.get_list("set-cookie")
        session = next(value for value in cookies if value.startswith(SESSION_COOKIE + "="))
        csrf = next(value for value in cookies if value.startswith(CSRF_COOKIE + "="))
        self.assertIn("HttpOnly", session)
        self.assertNotIn("HttpOnly", csrf)
        self.assertIn("Max-Age=28800", session)
        self.assertIn("SameSite=lax", session)
        self.assertNotIn("Secure", session)  # Approved HTTP localhost mode.
        token = self.client.cookies.get(SESSION_COOKIE)
        with self.conn.cursor() as cur:
            cur.execute("SELECT expires_at-created_at FROM auth.sessions WHERE token_hash=%s", (session_digest(token),))
            lifetime = cur.fetchone()[0].total_seconds()
        self.assertTrue(28798 < lifetime < 28802)
        self.assertTrue(token not in response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_unknown_user_and_wrong_password_have_identical_errors(self):
        self.assertEqual(self.register().status_code, 201)
        wrong = self.login(password="wrong")  # No new-password policy at login.
        unknown = self.login(email="missing-" + self.email)
        self.assertEqual((wrong.status_code, unknown.status_code), (401, 401))
        self.assertEqual(wrong.json(), unknown.json())
        self.assertFalse(wrong.headers.get_list("set-cookie"))

    def test_password_is_not_trimmed_on_login(self):
        self.assertEqual(self.register(password=" ReviewPassA1 ").status_code, 201)
        self.assertEqual(self.login().status_code, 401)
        self.assertEqual(self.login(password=" ReviewPassA1 ").status_code, 200)

    def test_advisor_and_coordinator_login_use_current_v1_role(self):
        from backend.auth_security import hash_password
        for role in ("advisor", "coordinator"):
            email = role + "-" + self.fixture_tag + "@example.test"
            with self.conn.cursor() as cur:
                switch(cur, OWNER)
                cur.execute("INSERT INTO public.users(full_name,email,role) VALUES (%s,%s,%s) RETURNING id",
                            ("Auth " + role, email, role))
                user_id = cur.fetchone()[0]
                cur.execute("INSERT INTO auth.credentials(user_id,password_hash) VALUES (%s,%s)", (user_id, hash_password(PASSWORD)))
                switch(cur, APP)
            response = self.login(email=email)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["data"]["role"], role)

    def test_relogin_rotates_token_and_revokes_old_session(self):
        token, csrf = self.signed_in()
        self.assertEqual(self.login().status_code, 200)
        other = self.client.cookies.get(SESSION_COOKIE)
        self.assertTrue(other != token)
        self.assertTrue(self.client.cookies.get(CSRF_COOKIE) != csrf)
        self.assertIsNone(self.active_user(token))
        self.assertIsNotNone(self.active_user(other))

    def test_logout_revokes_session_and_clears_cookies(self):
        token, csrf = self.signed_in()
        response = self.logout(csrf)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.assertIsNone(self.active_user(token))
        self.assertIsNone(self.client.cookies.get(SESSION_COOKIE))
        self.assertIsNone(self.client.cookies.get(CSRF_COOKIE))

    def test_logout_requires_header_and_matching_session_csrf(self):
        token, csrf = self.signed_in()
        self.assertEqual(self.logout().status_code, 403)
        self.assertEqual(self.logout("f" * 64).status_code, 403)
        self.assertIsNotNone(self.active_user(token))
        self.assertEqual(self.logout(csrf).status_code, 204)

    def test_csrf_from_another_session_is_rejected(self):
        token, old_csrf = self.signed_in()
        self.assertEqual(self.login().status_code, 200)
        self.client.cookies.set(CSRF_COOKIE, old_csrf, domain="localhost.local", path="/")
        self.assertEqual(self.logout(old_csrf).status_code, 403)

    def test_missing_malformed_and_unknown_session_are_unauthenticated(self):
        for value in (None, "bad-token", "A" * 43):
            self.client.cookies.clear()
            if value is not None:
                self.client.cookies.set(SESSION_COOKIE, value)
            self.assertEqual(self.logout().status_code, 401)

    def test_expired_session_is_not_authenticated(self):
        token, csrf = self.signed_in()
        with self.conn.cursor() as cur:
            switch(cur, OWNER)
            cur.execute("""UPDATE auth.sessions SET created_at=clock_timestamp()-interval '2 hours',
                expires_at=clock_timestamp()-interval '1 hour' WHERE token_hash=%s""", (session_digest(token),))
            switch(cur, APP)
        self.assertIsNone(self.active_user(token))
        self.assertEqual(self.logout(csrf).status_code, 401)

    def test_origin_is_required_and_untrusted_origins_are_denied(self):
        payload = {"email": self.email, "password": PASSWORD, "full_name": "Student"}
        for headers in ({}, {"Origin": "null"}, {"Origin": "http://untrusted.example.test"}):
            response = self.client.post("/api/v1/auth/register", headers=headers, json=payload)
            self.assertEqual(response.status_code, 403)
        with self.conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM public.users WHERE email=%s", (self.email,))
            self.assertEqual(cur.fetchone()[0], 0)

    def test_cors_allows_only_approved_localhost_origin(self):
        headers = {**ORIGIN, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type,x-csrf-token"}
        response = self.client.options("/api/v1/auth/logout", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], ORIGIN["Origin"])
        self.assertEqual(response.headers["access-control-allow-credentials"], "true")
        response = self.client.options("/api/v1/auth/logout", headers={**headers, "Origin": "http://untrusted.example.test"})
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_backend_origin_is_allowed_for_local_api_tools(self):
        response = self.client.post("/api/v1/auth/register", headers={"Origin": "http://localhost:8000"},
                                    json={"full_name": "Student", "email": self.email, "password": PASSWORD})
        self.assertEqual(response.status_code, 201)

    def test_database_errors_are_sanitized_without_cookie(self):
        @contextmanager
        def unavailable():
            raise StorageUnavailable()
            yield  # pragma: no cover
        self.app.dependency_overrides[get_auth_uow] = lambda: unavailable
        response = self.register()
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["error"]["code"], "INTERNAL_ERROR")
        self.assertFalse(response.headers.get_list("set-cookie"))
        self.assertTrue(PASSWORD not in response.text and "traceback" not in response.text.lower())

    def test_registration_transaction_failure_does_not_report_success(self):
        @contextmanager
        def fail_completion():
            with transaction_on(self.conn) as store:
                yield store
                raise StorageUnavailable()
        self.app.dependency_overrides[get_auth_uow] = lambda: fail_completion
        self.assertEqual(self.register().status_code, 500)
        with self.conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM public.users WHERE email=%s", (self.email,))
            self.assertEqual(cur.fetchone()[0], 0)

    def test_login_transaction_failure_preserves_existing_session_without_new_cookie(self):
        token, csrf = self.signed_in()
        @contextmanager
        def fail_completion():
            with transaction_on(self.conn) as store:
                yield store
                raise StorageUnavailable()
        self.app.dependency_overrides[get_auth_uow] = lambda: fail_completion
        response = self.login()
        self.assertEqual(response.status_code, 500)
        self.assertFalse(response.headers.get_list("set-cookie"))
        self.assertIsNotNone(self.active_user(token))
        with self.conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM auth.sessions")
            self.assertEqual(cur.fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
