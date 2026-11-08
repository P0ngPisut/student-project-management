-- Auth RBAC REVIEW DRAFT. Included by 001_auth_storage_review.sql only.
-- No transaction boundary here: the entry point owns BEGIN and ROLLBACK.
-- These proposed grants are NOT installed merely by preparing this file.
\set ON_ERROR_STOP on

DO $preflight$
BEGIN
    IF current_database() <> 'student_project_management_v1_test'
       OR current_user <> 'project_owner' THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
            MESSAGE = 'Auth RBAC requires the test database and reviewed owner';
    END IF;
    IF pg_catalog.current_setting('auth_review.storage_ready', true)
       IS DISTINCT FROM '001_auth_storage_review' THEN
        RAISE EXCEPTION 'Run Auth RBAC through the rollback-only storage entry point';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_namespace n
        WHERE n.nspname = 'auth'
          AND pg_catalog.pg_get_userbyid(n.nspowner) = 'project_owner'
    ) OR (
        SELECT pg_catalog.count(*) FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'auth' AND c.relname IN ('credentials', 'sessions')
          AND c.relkind = 'r'
          AND pg_catalog.pg_get_userbyid(c.relowner) = 'project_owner'
    ) <> 2 THEN
        RAISE EXCEPTION 'Auth storage ownership does not match the reviewed owner';
    END IF;
END
$preflight$;

-- Trusted backend calls this only AFTER validating the registration request and
-- hashing the password. A client must never supply password_hash or a role.
-- Hardcoded student role; duplicate email raises an error, never takes over or
-- attaches credentials to an existing user. Both INSERTs succeed or roll back.
CREATE FUNCTION auth.register_student(
    p_full_name TEXT,
    p_email TEXT,
    p_password_hash TEXT
) RETURNS BIGINT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $function$
DECLARE
    v_user_id BIGINT;
BEGIN
    INSERT INTO public.users(full_name, email, role)
    VALUES (p_full_name, p_email, 'student')
    RETURNING id INTO v_user_id;

    INSERT INTO auth.credentials(user_id, password_hash)
    VALUES (v_user_id, p_password_hash);

    RETURN v_user_id;
END
$function$;

-- Credential hash is available only through this lookup to the trusted backend.
-- It is private internal data, never an HTTP response. The backend must verify
-- the hash and return the same login failure for unknown email/wrong password.
CREATE FUNCTION auth.lookup_credentials(p_email TEXT)
RETURNS TABLE(user_id BIGINT, password_hash TEXT)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $function$
    SELECT c.user_id, c.password_hash
    FROM auth.credentials AS c
    JOIN public.users AS u ON u.id = c.user_id
    WHERE u.email = pg_catalog.lower(
        pg_catalog.btrim(p_email, E' \t\n\r\f\v')
    );
$function$;

REVOKE ALL ON FUNCTION auth.register_student(TEXT, TEXT, TEXT)
    FROM PUBLIC, project_app;
REVOKE ALL ON FUNCTION auth.lookup_credentials(TEXT)
    FROM PUBLIC, project_app;
REVOKE ALL ON TABLE auth.credentials, auth.sessions FROM PUBLIC, project_app;
REVOKE ALL ON SCHEMA auth FROM PUBLIC, project_app;

GRANT USAGE ON SCHEMA auth TO project_app;
GRANT EXECUTE ON FUNCTION auth.register_student(TEXT, TEXT, TEXT),
    auth.lookup_credentials(TEXT) TO project_app;

-- Backend generates raw session tokens, stores their digest only, and scopes
-- SELECT/DELETE by the session being authenticated. G-12 filtering is still in
-- the backend, as in V1; these grants do not provide row-level authorization.
GRANT SELECT, DELETE ON TABLE auth.sessions TO project_app;
GRANT INSERT (token_hash, user_id, expires_at) ON TABLE auth.sessions TO project_app;

-- No direct credentials SELECT/INSERT/UPDATE/DELETE, no users write grants,
-- no schema CREATE, no session UPDATE/TRUNCATE, no role creation/membership.
DO $postflight$
BEGIN
    IF pg_catalog.has_any_column_privilege('project_app', 'auth.credentials', 'SELECT')
       OR pg_catalog.has_any_column_privilege('project_app', 'auth.credentials', 'INSERT')
       OR pg_catalog.has_any_column_privilege('project_app', 'auth.credentials', 'UPDATE')
       OR pg_catalog.has_table_privilege('project_app', 'auth.credentials', 'DELETE')
       OR pg_catalog.has_schema_privilege('project_app', 'auth', 'CREATE')
       OR pg_catalog.has_any_column_privilege('project_app', 'public.users', 'INSERT')
       OR pg_catalog.has_any_column_privilege('project_app', 'public.users', 'UPDATE')
       OR pg_catalog.has_table_privilege('project_app', 'public.users', 'DELETE')
       OR pg_catalog.has_column_privilege('project_app', 'auth.sessions', 'created_at', 'INSERT')
       OR pg_catalog.has_any_column_privilege('project_app', 'auth.sessions', 'UPDATE')
       OR pg_catalog.has_table_privilege('project_app', 'auth.sessions', 'TRUNCATE') THEN
        RAISE EXCEPTION 'Auth privilege review found unexpected effective access';
    END IF;
    IF NOT pg_catalog.has_schema_privilege('project_app', 'auth', 'USAGE')
       OR NOT pg_catalog.has_function_privilege(
           'project_app', 'auth.register_student(text,text,text)', 'EXECUTE')
       OR NOT pg_catalog.has_function_privilege(
           'project_app', 'auth.lookup_credentials(text)', 'EXECUTE')
       OR NOT pg_catalog.has_table_privilege('project_app', 'auth.sessions', 'SELECT')
       OR NOT pg_catalog.has_table_privilege('project_app', 'auth.sessions', 'DELETE')
       OR NOT pg_catalog.has_column_privilege('project_app', 'auth.sessions', 'token_hash', 'INSERT')
       OR NOT pg_catalog.has_column_privilege('project_app', 'auth.sessions', 'user_id', 'INSERT')
       OR NOT pg_catalog.has_column_privilege('project_app', 'auth.sessions', 'expires_at', 'INSERT') THEN
        RAISE EXCEPTION 'Auth privilege review found missing intended access';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_proc p
        JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(p.proacl, pg_catalog.acldefault('f', p.proowner))
        ) AS a
        WHERE n.nspname = 'auth' AND a.grantee = 0
          AND a.privilege_type = 'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'PUBLIC must not execute Auth functions';
    END IF;
END
$postflight$;
