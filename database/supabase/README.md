# Supabase PostgreSQL bootstrap

This package prepares the project's PostgreSQL tables, workflow functions,
triggers, and least-privilege roles for a **new, empty Supabase database**.
It can be used in an existing Supabase project if its `postgres` database
does not already contain this application's objects.
It does not use Supabase Auth or the Supabase JavaScript client: the FastAPI
backend connects directly to PostgreSQL using `AUTH_DATABASE_URL`.

## Important status and safety

`001_bootstrap.sql` is a Supabase-specific adaptation of the checked-in V1 and
Auth review SQL. It has not been run against a Supabase instance. First apply
it to a disposable Supabase project and verify the backend there. Do not run
it on a project that already contains application tables or valuable data.
The SQL checks for existing target objects and aborts rather than overwriting
them, but it does not migrate or preserve an existing schema.

The source installers under `database/tools/` remain restricted to the local
test database; do not use them against Supabase. This bootstrap does not create
users or seed data. Keep passwords out of this repository, frontend settings,
and chat.

## Install into a disposable Supabase project

1. Select a **test Supabase project**. Its `postgres` database must not already
   contain this application's tables or functions.
2. In **SQL Editor**, run `000_roles.sql` once as the `postgres` administrator.
   It creates:
   - `project_owner`: non-login owner for the application objects.
   - `project_app`: restricted login used by FastAPI.
3. Set a strong password for `project_app` in the Supabase database role
   settings. Do not place it in either checked-in SQL file. The bootstrap
   refuses to continue until the role has a password.
4. Run `001_bootstrap.sql` in the same project's SQL Editor. It requires the
   `postgres` database, the `postgres` administrator, the two roles above, and
   no existing application tables / `v1_*` functions / `spms_auth` schema.
   Schema creation and grants run in one transaction. If a check fails, the
   transaction aborts and does not commit a partial install.
5. In Supabase **Connect**, copy the PostgreSQL **Transaction pooler** string
   with TLS enabled. Its username must identify `project_app`, not `postgres`.
   If the copied pooler username is `postgres.<project-ref>`, replace only
   that username with `project_app.<project-ref>` and use the password set in
   step 3. Keep `sslmode=require`. Do not substitute the HTTPS project URL or
   an `anon` / `service_role` API key.
   The URL has this general shape:

   ```text
   postgresql://project_app.<project-ref>:<password>@<pooler-host>:6543/postgres?sslmode=require
   ```

   Use the host and region shown by **Connect**; do not copy this example
   literally. URL-encode special characters in the password.
6. Copy `backend/.env.supabase.example` to `backend/.env` and set
   `AUTH_DATABASE_URL` to that PostgreSQL connection string. Keep:

   ```dotenv
   AUTH_DB_NAME=postgres
   AUTH_DB_USER=project_app
   AUTH_DB_OWNER_ROLE=project_owner
   AUTH_DB_SCHEMA=spms_auth
   ```

   The URL's login must match `AUTH_DB_USER`. Do not commit `backend/.env`.
7. From the repository root, verify that the backend connects as the expected
   role and that its runtime checks pass:

   ```powershell
   python -c "from backend.auth_store import open_auth_connection, assert_auth_connection; c = open_auth_connection(); assert_auth_connection(c); print(c.execute('SELECT current_database(), current_user').fetchone()); c.close()"
   ```

   Then smoke-test API flows in the disposable project before considering a
   production rollout. Avoid testing account creation with real student data.

## What the schemas contain

- `public`: the 14 V1 system tables and their workflow functions/triggers.
  FastAPI performs request authentication and row-level access filtering;
  the V1 design does not use PostgreSQL RLS.
- `spms_auth`: Auth `credentials` and `sessions` tables, plus the
  `register_student` and `lookup_credentials` functions. It is separate from
  Supabase's own `auth` schema.
- `project_owner` owns the installed application objects. `project_app` gets
  only the reviewed backend grants and must not inherit `project_owner`,
  `pg_read_all_data`, or `pg_write_all_data`.

`AUTH_DATABASE_URL` is a PostgreSQL connection string such as the pooler URL
from **Connect**. A Supabase HTTPS project URL (for example
`https://<project-ref>.supabase.co`) is for Supabase HTTP APIs and is not a
PostgreSQL connection string. The schema name is configured independently in
`AUTH_DB_SCHEMA`; it is not derived from either URL.

## Limitations

This SQL is a deployment draft, not evidence that the live Supabase project is
ready. It has structural checks for expected object counts and ownership, but
has not been validated against Supabase's managed PostgreSQL environment or a
live FastAPI deployment. Review and test it on a disposable project first.
