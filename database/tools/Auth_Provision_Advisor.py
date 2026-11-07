"""Owner-only new-advisor provisioning in the pinned test DB. Default: ROLLBACK.

No password argument, environment password, input file, schema/grant mutation,
existing-account activation, role change or password reset is supported.
"""

import argparse
import getpass
import json
import sys
import warnings

import psycopg

from backend.auth_security import hash_password
from backend.auth_validation import validate_email_format
from database.tools.Test_Database import TEST_DB, connect_test_database

ASCII_SPACE = " \t\n\r\f\v"


class ProvisionError(Exception):
    def __init__(self, code):
        self.code = code


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's normal error includes unknown argument values. Never echo
        # a password accidentally supplied as an unsupported command argument.
        raise ProvisionError("ARGUMENT_ERROR")


def validate_account(full_name, email):
    if not isinstance(full_name, str) or not isinstance(email, str):
        raise ProvisionError("INVALID_ACCOUNT_INPUT")
    name, address = full_name.strip(ASCII_SPACE), email.strip(ASCII_SPACE)
    if not name or len(name) > 255:
        raise ProvisionError("INVALID_FULL_NAME")
    if any("\x00" in value or any(0xD800 <= ord(c) <= 0xDFFF for c in value) for value in (name, address)):
        raise ProvisionError("INVALID_ACCOUNT_TEXT")
    if len(address) > 255:
        raise ProvisionError("INVALID_EMAIL")
    try:
        validate_email_format(address)
    except ValueError:
        raise ProvisionError("INVALID_EMAIL") from None
    return name, address


def guard_owner(conn):
    if conn.execute("SELECT current_database()").fetchone() != (TEST_DB,):
        raise ProvisionError("TEST_DATABASE_REQUIRED")
    # Only after the database guard; this is an administrator tool, not an API
    # fallback. The app login cannot assume this role and is rejected by PG.
    conn.execute("SET LOCAL ROLE project_owner")
    row = conn.execute("""SELECT current_user,r.rolsuper,
            current_setting('session_replication_role'),
            pg_get_userbyid((SELECT relowner FROM pg_class WHERE oid='public.users'::regclass)),
            pg_get_userbyid((SELECT relowner FROM pg_class WHERE oid='auth.credentials'::regclass)),
            EXISTS(SELECT 1 FROM pg_trigger WHERE tgrelid='public.users'::regclass
                AND tgname='tr_users_normalize' AND tgenabled='O'),
            has_any_column_privilege('project_app','public.users','INSERT'),
            has_table_privilege('project_app','auth.credentials','INSERT')
        FROM pg_roles r WHERE r.rolname=current_user""").fetchone()
    if row != ('project_owner', False, 'origin', 'project_owner', 'project_owner', True, False, False):
        raise ProvisionError("OWNER_BASELINE_REQUIRED")


def insert_credentials(conn, user_id, encoded):
    conn.execute("INSERT INTO auth.credentials(user_id,password_hash) VALUES (%s,%s)", (user_id, encoded))


def create_advisor_on(conn, full_name, email, password):
    """Atomic nested-safe operation; caller owns the outer COMMIT/ROLLBACK.

    This function never commits on its own. It may be borrowed by a rollback
    test; CLI wraps it in an explicitly selected outer transaction.
    """
    name, address = validate_account(full_name, email)
    try:
        encoded = hash_password(password)  # Existing Auth policy; never trim.
    except ValueError:
        raise ProvisionError("INVALID_PASSWORD_POLICY") from None
    try:
        with conn.transaction():
            guard_owner(conn)
            if conn.execute("SELECT EXISTS(SELECT 1 FROM public.users WHERE email=lower(%s))", (address,)).fetchone()[0]:
                raise ProvisionError("ACCOUNT_ALREADY_EXISTS")
            row = conn.execute("""INSERT INTO public.users(full_name,email,role)
                VALUES (%s,%s,'advisor') RETURNING id,full_name,email,role""", (name, address)).fetchone()
            insert_credentials(conn, row[0], encoded)
            return {"id": str(row[0]), "full_name": row[1], "email": row[2], "role": row[3]}
    except psycopg.Error as exc:
        if (exc.sqlstate == '23505' and exc.diag.schema_name == 'public'
                and exc.diag.table_name == 'users' and exc.diag.constraint_name == 'users_email_key'):
            raise ProvisionError("ACCOUNT_ALREADY_EXISTS") from None
        raise ProvisionError("DATABASE_OPERATION_FAILED") from None


def provision(full_name, email, password, *, apply=False):
    # Validate before reading private DB configuration or making a connection.
    validate_account(full_name, email)
    from backend.auth_validation import validate_new_password
    try:
        validate_new_password(password)
    except ValueError:
        raise ProvisionError("INVALID_PASSWORD_POLICY") from None
    conn = connect_test_database()
    try:
        # The connector's read-only identity SELECT starts an implicit tx. End
        # only that fresh guard transaction so --apply owns a real root tx.
        conn.rollback()
        with conn.transaction(force_rollback=not apply):
            user = create_advisor_on(conn, full_name, email, password)
        return {"result":"PASS", "mode":"APPLIED" if apply else "DRY_RUN", "database":TEST_DB,
                "effective_role":"project_owner", "persisted":apply, "user":user}
    finally:
        conn.rollback()
        conn.close()


def check():
    conn = connect_test_database(readonly=True)
    try:
        with conn.transaction():
            guard_owner(conn)
        return {"result":"PASS", "mode":"CHECK", "database":TEST_DB, "effective_role":"project_owner", "persisted":False}
    finally:
        conn.rollback()
        conn.close()


def prompt_password():
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        raise ProvisionError("PASSWORD_TTY_REQUIRED")
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        try:
            password = getpass.getpass("Application password (hidden; not the database password): ")
            repeated = getpass.getpass("Repeat application password (hidden): ")
        except getpass.GetPassWarning:
            raise ProvisionError("PASSWORD_TTY_REQUIRED") from None
    if password != repeated:
        raise ProvisionError("PASSWORD_MISMATCH")
    return password


def main(argv=None):
    try:
        parser = SafeParser(description=__doc__)
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument('--check', action='store_true', help='Read-only owner/baseline check, no account prompts')
        mode.add_argument('--dry-run', action='store_true', help='Explicit ROLLBACK mode (the default)')
        mode.add_argument('--apply', action='store_true', help='Persist one NEW advisor; needs approved data-write scope')
        parser.add_argument('--confirm-database', help='Required with --apply; must equal the pinned test DB name')
        parser.add_argument('--full-name')
        parser.add_argument('--email')
        args = parser.parse_args(argv)
        if args.confirm_database not in (None, TEST_DB) or (args.apply and args.confirm_database != TEST_DB):
            raise ProvisionError("TEST_DATABASE_CONFIRMATION_REQUIRED")
        if args.check:
            result = check()
        else:
            if (args.full_name is None or args.email is None) and not sys.stdin.isatty():
                raise ProvisionError("ACCOUNT_INPUT_TTY_REQUIRED")
            name = args.full_name if args.full_name is not None else input('Advisor full name: ')
            email = args.email if args.email is not None else input('Advisor email (a valid .test address is allowed): ')
            validate_account(name, email)
            password = prompt_password()
            try:
                result = provision(name, email, password, apply=args.apply)
            finally:
                del password
        # ASCII JSON also works on Windows terminals whose output encoding
        # cannot represent a valid Unicode name (avoid false failure post-tx).
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except ProvisionError as exc:
        print(json.dumps({'result':'FAIL','code':exc.code}))
    except (KeyboardInterrupt, EOFError):
        print(json.dumps({'result':'FAIL','code':'CANCELLED'}))
    except Exception:
        # No raw psycopg errors, config, DSNs, hashes, passwords or traceback.
        print(json.dumps({'result':'FAIL','code':'INTERNAL_ERROR'}))
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
