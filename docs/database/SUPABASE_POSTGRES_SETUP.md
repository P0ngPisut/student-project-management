# Supabase PostgreSQL connection

The backend can connect to Supabase PostgreSQL using `AUTH_DATABASE_URL`.
Keep the URL in the ignored local `backend/.env` file or a deployment secret
store; never put it in frontend variables. Start from
[`backend/.env.supabase.example`](../../backend/.env.supabase.example), then
copy the transaction-pooler URL from the Supabase dashboard and retain
`sslmode=require`.

The runtime checks the connected database, application role, and elevated role
attributes before serving database-backed requests. The configured runtime
role must be a non-superuser login, must not inherit the owner role or broad
data roles, and must have only the reviewed application grants. `AUTH_DB_SCHEMA`
defaults to `auth` for the existing local test database; Supabase should use a
separate application schema such as `spms_auth`, since Supabase owns its `auth`
schema.

For the Supabase-specific fresh-project bootstrap and setup sequence, see
[`database/supabase/README.md`](../../database/supabase/README.md).

## Database initialization status

Connection settings alone do not initialize the application. The checked-in
database installers and regression suites are guarded to the local
`student_project_management_v1_test` database. The repository now includes a
Supabase-specific bootstrap draft under `database/supabase/`, but it has not
been validated against Supabase or applied to a project. Do not run the
test-only installers against Supabase or use the Supabase `postgres` role as
the application runtime. Until the bootstrap is reviewed, tested, and applied,
a connection may succeed while application requests correctly fail their
database/schema checks.

Preparing the bootstrap does not run SQL, create roles, or write to the
Supabase project.
