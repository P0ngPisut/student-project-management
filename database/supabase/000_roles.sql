-- Run once in the Supabase SQL Editor as postgres, in the postgres database.
-- Set the project_app password separately in the Supabase role settings.
-- This file intentionally contains no password and is not idempotent.

DO $preflight$
BEGIN
    IF current_database() <> 'postgres' OR current_user <> 'postgres' THEN
        RAISE EXCEPTION 'Run in Supabase database postgres as the postgres administrator';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
        WHERE rolname IN ('project_owner', 'project_app')
    ) THEN
        RAISE EXCEPTION 'project_owner or project_app already exists; inspect roles before proceeding';
    END IF;
END
$preflight$;

CREATE ROLE project_owner
    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;

CREATE ROLE project_app
    LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;

GRANT CONNECT ON DATABASE postgres TO project_app;
