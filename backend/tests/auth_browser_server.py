"""Browser-test fixture only: direct app connection, all writes rolled back.

Port 8001 is isolated from the normal Backend on 8000. Never use this fixture
as the normal application server: successful responses do not persist records.
The runner verifies metadata/row counts and that this connection has closed.
"""

import argparse
from contextlib import contextmanager
import json
import os
from threading import RLock

from dotenv import dotenv_values
import psycopg
from psycopg.pq import TransactionStatus
import uvicorn

from backend.auth_api import get_auth_uow
from backend.auth_store import StorageUnavailable, assert_auth_connection, open_auth_connection, transaction_on
from backend.main import create_app
from database.tests.Auth_Regression import BASE, OWNER, TEST_DB, snapshot, switch

APPLICATION_NAME = "spms_auth_browser_rollback"


def baseline_snapshot():
    cfg = dotenv_values(BASE / "backend/.env")
    conn = None
    try:
        conn = psycopg.connect(
            host=cfg.get("DB_HOST"), port=int(cfg.get("DB_PORT") or 5432),
            dbname=TEST_DB, user=cfg.get("DB_USER"), password=cfg.get("DB_PASSWORD"),
            connect_timeout=8, autocommit=False,
            options="-c statement_timeout=15000 -c lock_timeout=3000",
        )
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SELECT current_database()")
            if cur.fetchone()[0] != TEST_DB:
                raise RuntimeError("Database guard failed")
            switch(cur, OWNER)
            digest, counts = snapshot(cur)
            cur.execute("""SELECT count(*) FROM pg_catalog.pg_stat_activity
                WHERE datname=current_database() AND application_name=%s""", (APPLICATION_NAME,))
            connections = cur.fetchone()[0]
            return {"metadata_sha256": digest, "row_counts": counts, "fixture_connections": connections}
    finally:
        if conn is not None:
            conn.rollback()
            conn.close()


def run_fixture():
    if os.environ.get("SPMS_AUTH_BROWSER_ROLLBACK") != "1":
        raise RuntimeError("Explicit browser rollback-test mode is required")
    conn = open_auth_connection()
    lock = RLock()
    try:
        with conn.transaction(force_rollback=True):
            assert_auth_connection(conn)
            conn.execute("SELECT set_config('application_name',%s,true)", (APPLICATION_NAME,))

            @contextmanager
            def borrowed_uow():
                with lock:
                    # If the outer transaction ever disappears, fail closed
                    # rather than allowing a request to commit a top-level tx.
                    if conn.info.transaction_status != TransactionStatus.INTRANS:
                        raise StorageUnavailable()
                    with transaction_on(conn) as repository:
                        yield repository

            app = create_app()
            app.dependency_overrides[get_auth_uow] = lambda: borrowed_uow
            uvicorn.run(app, host="127.0.0.1", port=8001, log_level="warning")
    finally:
        conn.rollback()
        conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", action="store_true")
    args = parser.parse_args()
    try:
        if args.snapshot:
            print(json.dumps(baseline_snapshot()))
        else:
            run_fixture()
        return 0
    except Exception as exc:
        print(json.dumps({"result": "FAIL", "error_type": type(exc).__name__, "sqlstate": getattr(exc, "sqlstate", None)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
