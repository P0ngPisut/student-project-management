"""Connection boundary for V1 deployment tools: only the named test database.

DB_NAME from private config is deliberately ignored. No backend engine is
imported, and no fallback connection to postgres/template/main DB is attempted.
Role changes and any DDL remain the individual tool's responsibility.
"""

from pathlib import Path

from dotenv import dotenv_values
import psycopg

BASE = Path(__file__).resolve().parents[2]
TEST_DB = "student_project_management_v1_test"


def connect_test_database(*, autocommit=False, readonly=False):
    config = dotenv_values(BASE / "backend/.env")
    if not config.get("DB_USER") or not config.get("DB_PASSWORD"):
        raise RuntimeError("Private DB fixture/deployment credentials are required")
    options = "-c statement_timeout=15000 -c lock_timeout=3000"
    if readonly:
        options += " -c default_transaction_read_only=on"
    conn = psycopg.connect(
        host=config.get("DB_HOST") or "localhost",
        port=int(config.get("DB_PORT") or 5432),
        dbname=TEST_DB,
        user=config["DB_USER"], password=config["DB_PASSWORD"],
        autocommit=autocommit, connect_timeout=8, options=options,
    )
    try:
        if conn.execute("SELECT current_database()").fetchone() != (TEST_DB,):
            raise RuntimeError("Test-database identity guard failed")
        return conn
    except Exception:
        try:
            conn.rollback()
        finally:
            conn.close()
        raise
