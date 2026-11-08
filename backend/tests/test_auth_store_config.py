import unittest
from unittest.mock import patch

from backend.auth_store import StorageUnavailable, _settings


class AuthStoreConfigTests(unittest.TestCase):
    @patch("backend.auth_store.dotenv_values", return_value={})
    @patch.dict("os.environ", {
        "AUTH_DATABASE_URL": "postgresql://project_app:placeholder@db.example.test:5432/postgres?sslmode=require",
        "AUTH_DB_SCHEMA": "spms_auth",
    }, clear=True)
    def test_supabase_url_selects_database_identity_and_custom_auth_schema(self, _dotenv):
        settings = _settings()
        self.assertEqual(settings["database"], "postgres")
        self.assertEqual(settings["user"], "project_app")
        self.assertEqual(settings["schema"], "spms_auth")
        self.assertEqual(settings["database_url"].split("@", 1)[1],
                         "db.example.test:5432/postgres?sslmode=require")

    @patch("backend.auth_store.dotenv_values", return_value={})
    @patch.dict("os.environ", {"AUTH_DB_SCHEMA": "spms_auth; DROP SCHEMA public"}, clear=True)
    def test_invalid_auth_schema_is_rejected(self, _dotenv):
        with self.assertRaises(StorageUnavailable):
            _settings()

    @patch("backend.auth_store.dotenv_values", return_value={})
    @patch.dict("os.environ", {
        "AUTH_DATABASE_URL": "postgresql://project_app:placeholder@db.example.test:5432/postgres?sslmode=disable",
    }, clear=True)
    def test_supabase_url_without_tls_is_rejected(self, _dotenv):
        with self.assertRaises(StorageUnavailable):
            _settings()


if __name__ == "__main__":
    unittest.main()
