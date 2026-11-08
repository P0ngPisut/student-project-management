"""Offline connection-boundary tests. No real connection or .env read."""

import unittest
from unittest.mock import MagicMock, patch

from database.tools.Test_Database import connect_test_database, TEST_DB


class TestDatabaseBoundary(unittest.TestCase):
    def setUp(self):
        self.config = {"DB_HOST": "localhost", "DB_PORT": "5432", "DB_USER": "fixture_deployer",
                       "DB_PASSWORD": "SyntheticConfigOnly", "DB_NAME": "student_project_management"}
        self.conn = MagicMock()
        self.conn.execute.return_value.fetchone.return_value = (TEST_DB,)
        self.config_patch = patch("database.tools.Test_Database.dotenv_values", return_value=self.config)
        self.connect_patch = patch("database.tools.Test_Database.psycopg.connect", return_value=self.conn)
        self.config_patch.start()
        self.connect = self.connect_patch.start()
        self.addCleanup(self.config_patch.stop)
        self.addCleanup(self.connect_patch.stop)

    def test_main_db_name_is_ignored_and_test_db_is_pinned(self):
        self.assertIs(connect_test_database(), self.conn)
        self.assertEqual(self.connect.call_args.kwargs["dbname"], TEST_DB)

    def test_missing_db_name_does_not_change_target(self):
        del self.config["DB_NAME"]
        connect_test_database()
        self.assertEqual(self.connect.call_args.kwargs["dbname"], TEST_DB)

    def test_bad_target_is_rolled_back_and_closed(self):
        self.conn.execute.return_value.fetchone.return_value = ("wrong_database",)
        with self.assertRaises(RuntimeError):
            connect_test_database()
        self.conn.rollback.assert_called_once()
        self.conn.close.assert_called_once()

    def test_identity_query_failure_closes_connection(self):
        self.conn.execute.side_effect = RuntimeError("synthetic query failure")
        with self.assertRaises(RuntimeError):
            connect_test_database()
        self.conn.close.assert_called_once()

    def test_failed_rollback_still_closes_wrong_target_connection(self):
        self.conn.execute.return_value.fetchone.return_value = ("wrong_database",)
        self.conn.rollback.side_effect = RuntimeError("synthetic closed connection")
        with self.assertRaises(RuntimeError):
            connect_test_database()
        self.conn.close.assert_called_once()

    def test_missing_deployment_password_does_not_fall_back_to_app(self):
        del self.config["DB_PASSWORD"]
        self.config["AUTH_DB_PASSWORD"] = "SyntheticAppOnly"
        with self.assertRaises(RuntimeError):
            connect_test_database()
        self.connect.assert_not_called()

    def test_readonly_is_set_before_first_query(self):
        connect_test_database(readonly=True)
        self.assertIn("default_transaction_read_only=on", self.connect.call_args.kwargs["options"])

    def test_autocommit_mode_is_explicit_and_target_is_checked(self):
        connect_test_database(autocommit=True)
        self.assertTrue(self.connect.call_args.kwargs["autocommit"])
        self.conn.execute.assert_called_once_with("SELECT current_database()")

    def test_transactional_mode_is_default(self):
        connect_test_database()
        self.assertFalse(self.connect.call_args.kwargs["autocommit"])


if __name__ == "__main__":
    unittest.main()
