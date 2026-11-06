-- =========================================================================
-- PostgreSQL V1 A-02/A-05 RBAC REVIEW TEMPLATE.  DO NOT RUN UNTIL APPROVED.
-- Used AFTER Database_Schema_V1_A02_A05_REVIEW_DRAFT.sql in isolated DB.
-- IMPORTANT: use psql with owner/app roles REVIEWED; role names are NOT guessed.
-- Requires: -v v1_owner_role=<schema_object_owner> -v v1_app_role=<fastapi_login>
-- No CREATE/ALTER ROLE here; no database connection or DML is performed.
-- Security boundary: trusted FastAPI only; custom GUC is NOT authentication.
-- ===========================================================================
\set ON_ERROR_STOP on
\if :{?v1_app_role}
\else
\echo 'Missing reviewed v1_app_role; refusing to proceed'
\quit 3
\endif
\if :{?v1_owner_role}
\else
\echo 'Missing reviewed v1_owner_role; refusing to proceed'
\quit 3
\endif
BEGIN;
SELECT pg_catalog.set_config('v1.deploy.app_role', :'v1_app_role', true);
SELECT pg_catalog.set_config('v1.deploy.owner_role', :'v1_owner_role', true);
DO $preflight$
DECLARE v_app NAME := current_setting('v1.deploy.app_role')::NAME;
        v_owner NAME := current_setting('v1.deploy.owner_role')::NAME;
        v_bad_count INTEGER;
BEGIN
    IF v_app = v_owner OR current_user::name <> v_owner THEN
       RAISE EXCEPTION 'Run as the reviewed owner role; app and owner must differ';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=v_app) OR
       NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=v_owner) THEN
       RAISE EXCEPTION 'Deployment roles must already exist and be reviewed';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=v_app AND
        (rolsuper OR rolcreatedb OR rolcreaterole OR rolbypassrls OR rolreplication)) THEN
       RAISE EXCEPTION 'App role has elevated cluster/database privileges';
    END IF;
    IF pg_has_role(v_app,v_owner,'MEMBER') THEN
       RAISE EXCEPTION 'App role must not be member of owner role';
    END IF;
    SELECT count(*) INTO v_bad_count FROM pg_class c
      JOIN pg_namespace n ON n.oid=c.relnamespace
     WHERE n.nspname='public'
       AND c.relname IN ('users','teams','team_members','projects','advisor_invitations','project_submissions','project_submission_files','committee_assignments','committee_topic_votes','committee_evaluations','milestones','tasks','task_assignees','task_assignment_history')
       AND c.relkind='r' AND pg_get_userbyid(c.relowner) <> v_owner;
    IF v_bad_count > 0 THEN
       RAISE EXCEPTION 'Owner role does not own all V1 base tables';
    END IF;
    SELECT count(*) INTO v_bad_count FROM pg_proc f
      JOIN pg_namespace n ON n.oid=f.pronamespace
     WHERE n.nspname='public' AND f.proname LIKE 'v1\_%' ESCAPE '\'
       AND pg_get_userbyid(f.proowner) <> v_owner;
    IF v_bad_count > 0 THEN
       RAISE EXCEPTION 'Owner role does not own all v1_* functions';
    END IF;
END $preflight$;

-- Only in a new isolated DB: deny untrusted CREATE in the shared public schema.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM :"v1_app_role";
GRANT USAGE ON SCHEMA public TO :"v1_app_role";

-- No DML reaches an existing child row except via controlled entrypoints.
REVOKE ALL ON TABLE
    public.users,
    public.teams,
    public.team_members,
    public.projects,
    public.advisor_invitations,
    public.project_submissions,
    public.project_submission_files,
    public.committee_assignments,
    public.committee_topic_votes,
    public.committee_evaluations,
    public.milestones,
    public.tasks,
    public.task_assignees,
    public.task_assignment_history
FROM PUBLIC;
REVOKE ALL ON TABLE
    public.users,
    public.teams,
    public.team_members,
    public.projects,
    public.advisor_invitations,
    public.project_submissions,
    public.project_submission_files,
    public.committee_assignments,
    public.committee_topic_votes,
    public.committee_evaluations,
    public.milestones,
    public.tasks,
    public.task_assignees,
    public.task_assignment_history
FROM :"v1_app_role";

-- G-12.1: FastAPI enforces read filtering; PostgreSQL RLS is not used.
GRANT SELECT ON TABLE
    public.users,
    public.teams,
    public.team_members,
    public.projects,
    public.advisor_invitations,
    public.project_submissions,
    public.project_submission_files,
    public.committee_assignments,
    public.committee_topic_votes,
    public.committee_evaluations,
    public.milestones,
    public.tasks,
    public.task_assignees,
    public.task_assignment_history
TO :"v1_app_role";

-- INSERT of new root/new append-only rows: guards lock parents before INSERT.
GRANT INSERT ON TABLE
    public.teams, public.team_members, public.projects,
    public.advisor_invitations, public.project_submissions, public.project_submission_files
TO :"v1_app_role";
-- NOT GRANTED: direct UPDATE/DELETE existing teams, projects, invitations,
-- submissions, committee assignments, milestones, tasks or assignees.
-- NOT GRANTED: committee vote/evaluation INSERT (controlled functions only).
-- NOT GRANTED: any direct modification of task_assignment_history/users.
-- R-01=A: NEVER direct DELETE on projects (even when childless).
REVOKE DELETE ON TABLE public.projects FROM PUBLIC;
REVOKE DELETE ON TABLE public.projects FROM :"v1_app_role";

-- Helpers used by SECURITY INVOKER triggers; not a substitute for auth.
-- Parent-lock helpers are narrow SECURITY DEFINER functions: no direct UPDATE
-- privilege is granted to app; business authorization remains in their callers.
GRANT EXECUTE ON FUNCTION
    public.v1_actor_id(),
    public.v1_actor_has_role(TEXT),
    public.v1_is_team_leader(BIGINT,BIGINT),
    public.v1_is_current_member(BIGINT,BIGINT),
    public.v1_advisor_for_project(BIGINT),
    public.v1_has_first_evaluation(BIGINT),
    public.v1_topic_decision(BIGINT),
    public.v1_topic_metadata_editable(BIGINT),
    public.v1_lock_team(BIGINT),
    public.v1_lock_project(BIGINT)
TO :"v1_app_role";

-- Whitelisted operations. Each reuses existing business guards and acquires
-- parent locks before changing locked child rows.
GRANT EXECUTE ON FUNCTION
    public.v1_transfer_team_leader(BIGINT,BIGINT),
    public.v1_assign_task(BIGINT,BIGINT),
    public.v1_unassign_task(BIGINT,BIGINT),
    public.v1_exit_team_member(BIGINT),
    public.v1_update_team_metadata(BIGINT,TEXT,TEXT),
    public.v1_delete_team(BIGINT),
    public.v1_update_project_metadata(BIGINT,TEXT,TEXT),
    public.v1_resolve_invitation(BIGINT,TEXT),
    public.v1_review_submission(BIGINT,TEXT,TEXT),
    public.v1_create_milestone(BIGINT,TEXT,TEXT,DATE),
    public.v1_update_milestone(BIGINT,TEXT,TEXT,DATE),
    public.v1_delete_milestone(BIGINT),
    public.v1_create_task(BIGINT,TEXT,TEXT,DATE),
    public.v1_update_task_metadata(BIGINT,TEXT,TEXT,DATE),
    public.v1_set_task_status(BIGINT,TEXT),
    public.v1_delete_task(BIGINT),
    public.v1_appoint_committee(BIGINT,BIGINT),
    public.v1_replace_committee(BIGINT,BIGINT),
    public.v1_remove_committee(BIGINT),
    public.v1_cast_vote(BIGINT,BIGINT,TEXT,TEXT),
    public.v1_record_evaluation(BIGINT,INTEGER,TEXT)
TO :"v1_app_role";

-- No direct EXECUTE grants to v1_refresh_milestone / any definer trigger.
-- No PUBLIC EXECUTE grants: the Schema DDL revokes them for v1_* functions.

DO $postflight$
DECLARE v_app NAME := current_setting('v1.deploy.app_role')::NAME;
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_proc p
         WHERE p.oid IN ('public.v1_lock_team(bigint)'::regprocedure,
                         'public.v1_lock_project(bigint)'::regprocedure)
           AND (NOT p.prosecdef
                OR NOT coalesce(p.proconfig @> ARRAY['search_path=pg_catalog, public, pg_temp'],false))
    ) OR NOT has_function_privilege(v_app,'public.v1_lock_team(bigint)','EXECUTE')
      OR NOT has_function_privilege(v_app,'public.v1_lock_project(bigint)','EXECUTE') THEN
       RAISE EXCEPTION 'Parent-lock helpers must be trusted definers executable by app';
    END IF;
    IF has_schema_privilege(v_app,'public','CREATE') THEN
       RAISE EXCEPTION 'App still has CREATE on public schema (inherited?)';
    END IF;
    IF has_table_privilege(v_app,'public.projects','DELETE') THEN
       RAISE EXCEPTION 'R-01 violated: app has effective DELETE on projects';
    END IF;
    IF has_any_column_privilege(v_app,'public.projects','UPDATE')
       OR has_any_column_privilege(v_app,'public.teams','UPDATE')
       OR has_any_column_privilege(v_app,'public.tasks','UPDATE')
       OR has_any_column_privilege(v_app,'public.milestones','UPDATE')
       OR has_any_column_privilege(v_app,'public.project_submissions','UPDATE')
       OR has_any_column_privilege(v_app,'public.committee_assignments','UPDATE') THEN
       RAISE EXCEPTION 'App still has direct UPDATE on locked workflow tables';
    END IF;
    IF has_table_privilege(v_app,'public.tasks','DELETE')
       OR has_table_privilege(v_app,'public.milestones','DELETE')
       OR has_table_privilege(v_app,'public.task_assignees','DELETE')
       OR has_table_privilege(v_app,'public.committee_assignments','DELETE')
       OR has_table_privilege(v_app,'public.task_assignment_history','INSERT')
       OR has_table_privilege(v_app,'public.committee_topic_votes','INSERT')
       OR has_table_privilege(v_app,'public.committee_evaluations','INSERT') THEN
       RAISE EXCEPTION 'App still has forbidden direct DML from inherited grants';
    END IF;
    IF has_function_privilege(v_app,'public.v1_refresh_milestone(bigint)','EXECUTE')
       OR has_function_privilege(v_app,'public.v1_task_refresh_parent()','EXECUTE')
       OR has_function_privilege(v_app,'public.v1_record_unassignment()','EXECUTE') THEN
       RAISE EXCEPTION 'Internal reconciliation/trigger functions are callable by app';
    END IF;
END $postflight$;
COMMIT;
-- PostgreSQL has_* privilege predicates see PG documentation (current).
-- After approval, test with SET ROLE app, negative DML cases and concurrency.
