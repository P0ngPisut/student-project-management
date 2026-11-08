"""Browser fixture: effective app requests, every fixture write rolled back.

Port 8001 is isolated from the normal Backend on 8000. Never use this fixture
as the normal application server: successful responses do not persist records.
Default mode connects directly as app. Explicit invitation-fixture mode seeds
staff as non-superuser owner before switching to app for all HTTP requests.
The runner verifies metadata/row counts and that this connection has closed.
"""

import argparse
from contextlib import contextmanager
import json
import os
import re
from threading import RLock

from dotenv import dotenv_values
import psycopg
from psycopg.pq import TransactionStatus
import uvicorn

from backend.auth_api import get_auth_uow
from backend.auth_store import StorageUnavailable, assert_auth_connection, open_auth_connection, transaction_on
from backend.auth_security import hash_password
from backend.main import create_app
from backend.team_api import get_team_uow
from backend.team_store import team_transaction_on
from backend.project_api import get_project_uow
from backend.project_store import project_transaction_on
from backend.invitation_api import get_invitation_uow
from backend.invitation_store import invitation_transaction_on
from backend.submission_api import get_submission_uow
from backend.submission_store import submission_transaction_on
from database.tests.Auth_Regression import BASE, OWNER, TEST_DB, snapshot, switch
from database.tools.Test_Database import connect_test_database

APPLICATION_NAME = "spms_auth_browser_rollback"


def seed_invitation_accounts(conn, tag):
    # Explicit browser-fixture mode only, never the normal API. The connection
    # remains in one outer rollback transaction; role changes happen BEFORE
    # serving requests. No test-only HTTP provisioning endpoint is exposed.
    if not re.fullmatch(r"[a-f0-9]{32}", tag or ""):
        raise RuntimeError("A unique browser fixture tag is required")
    with conn.cursor() as cur:
        switch(cur, OWNER)
        cur.execute("SELECT current_user,r.rolsuper FROM pg_roles r WHERE r.rolname=current_user")
        if cur.fetchone() != (OWNER, False):
            raise RuntimeError("Non-superuser fixture owner required")
        encoded = hash_password("AdvisorBrowserFixtureA1")
        for label,role in (("a","advisor"),("b","advisor"),("coordinator","coordinator")):
            cur.execute("INSERT INTO public.users(full_name,email,role) VALUES (%s,%s,%s) RETURNING id",
                ("อาจารย์ทดสอบ "+label.upper()+" "+tag[:6] if role=='advisor' else 'ผู้ประสานงานทดสอบ',
                 f"advisor-browser-{tag}-{label}@example.test",role))
            user = cur.fetchone()[0]
            cur.execute("INSERT INTO auth.credentials(user_id,password_hash) VALUES (%s,%s)", (user,encoded))
        switch(cur,"project_app")


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
    owner_fixtures = os.environ.get("SPMS_INVITATION_BROWSER_FIXTURES") == "1"
    conn = connect_test_database() if owner_fixtures else open_auth_connection()
    lock = RLock()
    try:
        with conn.transaction(force_rollback=True):
            if owner_fixtures:
                seed_invitation_accounts(conn, os.environ.get("SPMS_ADVISOR_FIXTURE_TAG"))
            assert_auth_connection(conn)
            conn.execute("SELECT set_config('application_name',%s,true)", (APPLICATION_NAME,))

            @contextmanager
            def borrowed_uow(factory):
                with lock:
                    # If the outer transaction ever disappears, fail closed
                    # rather than allowing a request to commit a top-level tx.
                    if conn.info.transaction_status != TransactionStatus.INTRANS:
                        raise StorageUnavailable()
                    with factory(conn) as repository:
                        yield repository

            app = create_app()
            app.dependency_overrides[get_auth_uow] = lambda: lambda: borrowed_uow(transaction_on)
            app.dependency_overrides[get_team_uow] = lambda: lambda: borrowed_uow(team_transaction_on)
            app.dependency_overrides[get_project_uow] = lambda: lambda: borrowed_uow(project_transaction_on)
            app.dependency_overrides[get_invitation_uow] = lambda: lambda: borrowed_uow(invitation_transaction_on)
            app.dependency_overrides[get_submission_uow] = lambda: lambda: borrowed_uow(submission_transaction_on)
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
