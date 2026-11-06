"""Offline security/model/config tests using synthetic fixtures only."""

import unittest
from unittest.mock import MagicMock, patch

from backend.auth_api import PublicUser, RegisterInput
from backend.auth_security import (
    csrf_token, decode_session_token, hash_password, new_session_token,
    session_digest, valid_csrf, verify_password,
)
from backend.auth_store import (
    APP_ROLE, TEST_DB, AuthRepository, StorageUnavailable,
    assert_auth_connection, open_auth_connection,
)
from backend.main import create_app


class PasswordSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.encoded = hash_password("ReviewPassA1")

    def test_hash_is_argon2id_and_password_verifies(self):
        self.assertTrue(self.encoded.startswith("$argon2id$"))
        self.assertTrue(verify_password("ReviewPassA1", self.encoded))

    def test_same_password_uses_different_salt(self):
        other = hash_password("ReviewPassA1")
        self.assertTrue(other != self.encoded)
        self.assertTrue(verify_password("ReviewPassA1", other))

    def test_wrong_password_is_rejected(self):
        self.assertFalse(verify_password("WrongPassA1", self.encoded))

    def test_malformed_hashes_fail_closed(self):
        for encoded in ("", "plaintext-fixture", "$argon2id$broken", "$argon2id$v=19$invalid"):
            with self.subTest():
                self.assertFalse(verify_password("ReviewPassA1", encoded))

    def test_hashing_enforces_confirmed_new_password_policy(self):
        for password in ("Demo123", "demo1234", "DemoTest"):
            with self.subTest():
                with self.assertRaises(ValueError):
                    hash_password(password)

    def test_spaces_and_case_are_part_of_password(self):
        encoded = hash_password(" ReviewPassA1 ")
        self.assertTrue(verify_password(" ReviewPassA1 ", encoded))
        self.assertFalse(verify_password("ReviewPassA1", encoded))
        self.assertFalse(verify_password(" reviewpassa1 ", encoded))

    def test_password_model_repr_masks_secret(self):
        model = RegisterInput(email="student@example.test", full_name="Student", password="ReviewPassA1")
        self.assertTrue("ReviewPassA1" not in repr(model))
        self.assertTrue("ReviewPassA1" not in model.model_dump_json())


class SessionSecurityTests(unittest.TestCase):
    def test_random_tokens_and_stored_digest_lengths(self):
        first, second = new_session_token(), new_session_token()
        self.assertTrue(first != second)
        self.assertEqual(len(first), 43)
        self.assertEqual(len(decode_session_token(first)), 32)
        self.assertEqual(len(session_digest(first)), 32)

    def test_invalid_tokens_fail_closed(self):
        for value in (None, "", "bad", "x" * 44, "!" * 43, "x" * 42 + "B"):
            with self.subTest():
                self.assertIsNone(session_digest(value))

    def test_csrf_is_bound_to_session(self):
        first, second = new_session_token(), new_session_token()
        csrf = csrf_token(first)
        self.assertTrue(valid_csrf(first, csrf, csrf))
        self.assertFalse(valid_csrf(second, csrf, csrf))

    def test_csrf_missing_malformed_and_mismatch_rejected(self):
        token = new_session_token()
        csrf = csrf_token(token)
        for cookie, header in ((None, csrf), (csrf, None), (csrf, "wrong"), ("x" * 64, csrf), (csrf, "\u0e01" * 64)):
            with self.subTest():
                self.assertFalse(valid_csrf(token, cookie, header))


class AuthBoundaryTests(unittest.TestCase):
    def test_import_and_openapi_do_not_connect_to_database(self):
        with patch("psycopg.connect", side_effect=AssertionError("Unexpected DB connection")):
            app = create_app()
            self.assertEqual(set(app.openapi()["paths"]), {
                "/", "/api/v1/auth/register", "/api/v1/auth/login", "/api/v1/auth/logout", "/api/v1/auth/me",
            })

    def test_user_ids_preserve_bigint_precision_as_strings(self):
        row = (9223372036854775807, "Student", "student@example.test", "student")
        user = PublicUser(**AuthRepository.public_user(row))
        self.assertEqual(user.id, "9223372036854775807")

    def test_missing_auth_password_never_falls_back_to_admin_config(self):
        with patch.dict("os.environ", {}, clear=True), patch("backend.auth_store.dotenv_values", return_value={
            "DB_USER": "postgres", "DB_PASSWORD": "unused-admin-fixture", "DB_NAME": "unused_database",
        }), patch("backend.auth_store.psycopg.connect") as connect:
            with self.assertRaises(StorageUnavailable):
                open_auth_connection()
            connect.assert_not_called()

    def test_runtime_connection_is_pinned_to_app_and_test_database(self):
        with patch.dict("os.environ", {"AUTH_DB_PASSWORD": "synthetic-config-fixture"}, clear=True), patch(
            "backend.auth_store.dotenv_values", return_value={"DB_USER": "postgres", "DB_NAME": "unused_database"}
        ), patch("backend.auth_store.psycopg.connect") as connect:
            open_auth_connection()
            self.assertEqual(connect.call_args.kwargs["dbname"], TEST_DB)
            self.assertEqual(connect.call_args.kwargs["user"], APP_ROLE)
            self.assertFalse(connect.call_args.kwargs["autocommit"])

    def test_guard_rejects_wrong_database_owner_and_superuser_without_writes(self):
        good = (TEST_DB, APP_ROLE, False, False, False, False, False, "origin", False, False, False)
        rows = [good[:1] + ("project_owner",) + good[2:], ("other_database",) + good[1:],
                good[:2] + (True,) + good[3:],
                good[:8] + (True, False, False), good[:8] + (False, True, False),
                good[:8] + (False, False, True)]
        for row in rows:
            with self.subTest():
                conn = MagicMock()
                conn.cursor.return_value.__enter__.return_value.fetchone.return_value = row
                with self.assertRaises(StorageUnavailable):
                    assert_auth_connection(conn)


if __name__ == "__main__":
    unittest.main()
