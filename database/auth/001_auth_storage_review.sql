-- Auth extension REVIEW DRAFT. Prepared for review only; not executed.
-- Entry point for a future approved rollback-only rehearsal using psql.
-- Database: student_project_management_v1_test. Effective role: project_owner.
-- Includes 002_auth_rbac_review.sql in this transaction and always ROLLBACKs.
-- Does not alter V1 tables/functions/triggers or create/alter database roles.
\set ON_ERROR_STOP on

BEGIN;
SET LOCAL search_path = pg_catalog, pg_temp;

DO $preflight$
BEGIN
    IF current_database() <> 'student_project_management_v1_test' THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
            MESSAGE = 'Auth review is restricted to the approved test database';
    END IF;
    IF current_user <> 'project_owner' THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
            MESSAGE = 'Auth review requires the reviewed project_owner role';
    END IF;
    IF NOT pg_catalog.has_database_privilege(current_user, current_database(), 'CREATE') THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
            MESSAGE = 'Owner needs reviewed CREATE privilege on the test database to create auth schema';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles
                   WHERE rolname = 'project_owner' AND NOT rolsuper)
       OR NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles
                      WHERE rolname = 'project_app' AND NOT rolsuper
                        AND NOT rolcreatedb AND NOT rolcreaterole
                        AND NOT rolbypassrls AND NOT rolreplication) THEN
        RAISE EXCEPTION 'Reviewed non-superuser owner/app roles are required';
    END IF;
    IF pg_catalog.pg_has_role('project_app', 'project_owner', 'MEMBER')
       OR pg_catalog.pg_has_role('project_app', 'pg_read_all_data', 'MEMBER')
       OR pg_catalog.pg_has_role('project_app', 'pg_write_all_data', 'MEMBER')
       OR EXISTS (SELECT 1 FROM pg_catalog.pg_database d
                  JOIN pg_catalog.pg_roles r ON r.oid = d.datdba
                  WHERE d.datname = current_database()
                    AND r.rolname = 'project_app') THEN
        RAISE EXCEPTION 'App role must not inherit owner or broad data access';
    END IF;
    IF pg_catalog.to_regclass('public.users') IS NULL THEN
        RAISE EXCEPTION 'Existing V1 users table is required';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_class c
        WHERE c.oid = 'public.users'::pg_catalog.regclass
          AND c.relkind = 'r'
          AND pg_catalog.pg_get_userbyid(c.relowner) = 'project_owner'
    ) THEN
        RAISE EXCEPTION 'V1 users ownership does not match the reviewed owner';
    END IF;
    IF pg_catalog.has_any_column_privilege('project_app', 'public.users', 'INSERT')
       OR pg_catalog.has_any_column_privilege('project_app', 'public.users', 'UPDATE')
       OR pg_catalog.has_table_privilege('project_app', 'public.users', 'DELETE') THEN
        RAISE EXCEPTION 'App has unexpected direct users write privileges';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_namespace WHERE nspname = 'auth') THEN
        RAISE EXCEPTION 'Auth schema already exists; review a separate migration';
    END IF;
END
$preflight$;

CREATE SCHEMA auth AUTHORIZATION project_owner;
REVOKE ALL ON SCHEMA auth FROM PUBLIC, project_app;

CREATE TABLE auth.credentials (
    user_id BIGINT PRIMARY KEY
        REFERENCES public.users(id) ON DELETE RESTRICT,
    password_hash TEXT NOT NULL,
    CONSTRAINT ck_auth_password_hash CHECK (
        pg_catalog.left(password_hash, 10) = '$argon2id$'
        AND pg_catalog.length(password_hash) > 10
        AND password_hash = pg_catalog.btrim(password_hash)
    )
);

-- The prefix CHECK rejects plaintext; the backend hashing library must produce
-- and verify a valid encoded Argon2id hash. SQL does not verify hash parameters
-- or the original password's length/character policy from an encoded hash.
CREATE TABLE auth.sessions (
    token_hash BYTEA PRIMARY KEY,
    user_id BIGINT NOT NULL
        REFERENCES auth.credentials(user_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    expires_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_auth_session_token_hash CHECK (
        pg_catalog.octet_length(token_hash) = 32
    ),
    CONSTRAINT ck_auth_session_lifetime CHECK (expires_at > created_at)
);

CREATE INDEX ix_auth_sessions_user_id ON auth.sessions(user_id);
CREATE INDEX ix_auth_sessions_expires_at ON auth.sessions(expires_at);

REVOKE ALL ON TABLE auth.credentials, auth.sessions FROM PUBLIC, project_app;
SET LOCAL auth_review.storage_ready = '001_auth_storage_review';

\ir 002_auth_rbac_review.sql

-- This draft never persists objects, permissions, accounts or sessions.
ROLLBACK;
