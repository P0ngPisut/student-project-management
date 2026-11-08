-- V1 existing-baseline repair REVIEW. Always ROLLBACK; not an installer.
-- Source is checksum-pinned in V1_Baseline_Prepare.py. No V1 tables/columns/rules change.
-- Replace five legacy function definitions and add the missing parent-lock helper.
-- Only NEW application privilege proposed: EXECUTE on v1_lock_team(bigint).
-- No direct UPDATE/DELETE/TRUNCATE grants; no role/password changes.
-- Permanent installation and the new helper EXECUTE require explicit approval.
BEGIN;
SET LOCAL search_path = pg_catalog, public, pg_temp;
DO $baseline_guard$
DECLARE v_count integer;
BEGIN
    IF current_database() <> 'student_project_management_v1_test'
       OR current_user <> 'project_owner'
       OR (SELECT rolsuper FROM pg_roles WHERE rolname=current_user)
       OR current_setting('session_replication_role') <> 'origin' THEN
        RAISE EXCEPTION 'Wrong test database, effective owner or trigger mode';
    END IF;
    IF (SELECT pg_get_userbyid(datdba) FROM pg_database
        WHERE datname=current_database()) <> 'project_owner' THEN
        RAISE EXCEPTION 'Unexpected database owner';
    END IF;
    IF to_regprocedure('public.v1_lock_team(bigint)') IS NOT NULL THEN
        RAISE EXCEPTION 'Expected legacy baseline without v1_lock_team; do not reapply';
    END IF;
    IF (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname='public' AND left(p.proname,3)='v1_') <> 51 THEN
        RAISE EXCEPTION 'Unexpected V1 function inventory';
    END IF;
    SELECT count(*) INTO v_count
    FROM (VALUES
        ('v1_lock_project','91ef3f77b8f46ec411670b32ba8922280b19fab3e8cd98422eac5df34d538eca'),
        ('v1_team_members_guard','5acda1b9045f1b8cbccfa97774279764e6a1cfabd2d808432c9480a110a6ea2e'),
        ('v1_project_guard','5a131918bee0177809ec6aab89fc6a7ed95198aa906c3bcb9d3e64b2cff2a611'),
        ('v1_team_final_cardinality','1a494e78fdb882ec693ad01aeb652e17034c702d15af1103f79e3032a64ab9c0'),
        ('v1_in_progress_has_assignee','7460b11f6801b408721895dcd019f0206ba7dcc807be181a040cdc724ad6bfa5')
    ) expected(name,body_hash)
    JOIN pg_proc p ON p.proname=expected.name
    JOIN pg_namespace n ON n.oid=p.pronamespace
    WHERE n.nspname='public' AND pg_get_userbyid(p.proowner)='project_owner'
      AND encode(sha256(convert_to(p.prosrc,'UTF8')),'hex')=expected.body_hash
      AND NOT p.prosecdef;
    IF v_count <> 5 THEN
        RAISE EXCEPTION 'Legacy body/security fingerprint mismatch; inspect drift first';
    END IF;
    IF has_schema_privilege('project_app','public','CREATE')
       OR pg_has_role('project_app','project_owner','MEMBER') THEN
        RAISE EXCEPTION 'Application role boundary is not safe';
    END IF;
    IF EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relkind='r'
          AND (has_any_column_privilege('project_app',c.oid,'UPDATE')
               OR has_table_privilege('project_app',c.oid,'DELETE')
               OR has_table_privilege('project_app',c.oid,'TRUNCATE'))) THEN
        RAISE EXCEPTION 'Unexpected application direct-write privileges';
    END IF;
END $baseline_guard$;

CREATE OR REPLACE FUNCTION public.v1_lock_team(p_team BIGINT) RETURNS VOID
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM public.users WHERE id=public.v1_actor_id()) THEN
        RAISE EXCEPTION 'Verified transaction actor must exist' USING ERRCODE='42501';
    END IF;
    PERFORM 1 FROM public.teams WHERE id=p_team FOR UPDATE;
    -- Preserve the caller's existing missing-team checks / foreign-key errors.
END $$;
ALTER FUNCTION public.v1_lock_team(bigint) SET search_path = pg_catalog, public, pg_temp;
REVOKE ALL ON FUNCTION public.v1_lock_team(bigint) FROM PUBLIC;

CREATE OR REPLACE FUNCTION public.v1_lock_project(p_project BIGINT) RETURNS VOID
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM public.users WHERE id=public.v1_actor_id()) THEN
        RAISE EXCEPTION 'Verified transaction actor must exist' USING ERRCODE='42501';
    END IF;
    PERFORM 1 FROM public.projects WHERE id=p_project FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Project not found: %',p_project; END IF;
END $$;
ALTER FUNCTION public.v1_lock_project(bigint) SET search_path = pg_catalog, public, pg_temp;
REVOKE ALL ON FUNCTION public.v1_lock_project(bigint) FROM PUBLIC;

CREATE OR REPLACE FUNCTION public.v1_team_members_guard() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE v_user_role TEXT; v_project BIGINT; v_member_count INTEGER;
BEGIN
    IF TG_OP='DELETE' THEN
        -- During team ON DELETE CASCADE the team row no longer exists.
        IF NOT EXISTS(SELECT 1 FROM teams WHERE id=OLD.team_id) THEN
            RETURN OLD;
        END IF;
        PERFORM public.v1_lock_team(OLD.team_id);
        IF OLD.role='leader' THEN
            RAISE EXCEPTION 'Transfer leadership before leaving the team';
        END IF;
        IF NOT (v1_is_team_leader(OLD.team_id,v1_actor_id())
                OR OLD.user_id=v1_actor_id()) THEN
            RAISE EXCEPTION 'Cannot remove this team member' USING ERRCODE='42501';
        END IF;
        -- Assignee cleanup must occur in same transaction BEFORE team member
        -- delete (ON DELETE RESTRICT on task_assignees.team_member_id).
        RETURN OLD;
    END IF;

    PERFORM public.v1_lock_team(NEW.team_id);
    IF TG_OP='INSERT' THEN
        SELECT role INTO v_user_role FROM users WHERE id=NEW.user_id;
        IF v_user_role IS DISTINCT FROM 'student' THEN
            RAISE EXCEPTION 'Only students may join a team';
        END IF;
        SELECT count(*) INTO v_member_count FROM team_members WHERE team_id=NEW.team_id;
        IF v_member_count=0 AND NEW.role='leader' AND NEW.user_id=v1_actor_id() THEN
            -- Creating the first leader during team-creation transaction.
            RETURN NEW;
        END IF;
        IF NOT v1_is_team_leader(NEW.team_id,v1_actor_id()) THEN
            RAISE EXCEPTION 'Only team leader may add members' USING ERRCODE='42501';
        END IF;
        SELECT id INTO v_project FROM projects WHERE team_id=NEW.team_id;
        IF v_project IS NOT NULL AND NOT v1_topic_metadata_editable(v_project) THEN
            RAISE EXCEPTION 'Member additions are locked in current phase';
        END IF;
        IF NEW.role <> 'member' THEN
            RAISE EXCEPTION 'Additional team member must start as member';
        END IF;
    ELSE
        IF NEW.team_id IS DISTINCT FROM OLD.team_id OR
           NEW.user_id IS DISTINCT FROM OLD.user_id THEN
            RAISE EXCEPTION 'team_id/user_id cannot be changed';
        END IF;
        IF NEW.role IS DISTINCT FROM OLD.role THEN
            -- Only controlled leader-transfer call may set this flag;
            -- the app role must have no direct UPDATE privilege on role.
            IF current_setting('app.v1_leader_transfer',true) IS DISTINCT FROM 'on'
               OR current_setting('app.v1_transfer_initiator',true) IS DISTINCT FROM v1_actor_id()::TEXT THEN
                RAISE EXCEPTION 'Role updates require authorized leader transfer';
            END IF;
        END IF;
    END IF;
    RETURN NEW;
END $$;
ALTER FUNCTION public.v1_team_members_guard() SET search_path = pg_catalog, public, pg_temp;
REVOKE ALL ON FUNCTION public.v1_team_members_guard() FROM PUBLIC;

CREATE OR REPLACE FUNCTION public.v1_project_guard() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    -- R-01 = A (confirmed): Project deletion is forbidden in ALL V1 states,
    -- including before its first submission and when no dependent rows exist.
    -- This trigger protects even when a role accidentally receives DELETE;
    -- the application role must ALSO receive no DELETE privilege on projects.
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'R-01: Project deletion is forbidden in V1'
          USING ERRCODE='42501';
    END IF;
    NEW.name := btrim(NEW.name, E' \t\n\r\f\v');
    NEW.description := nullif(btrim(NEW.description, E' \t\n\r\f\v'),'');
    IF TG_OP='INSERT' THEN
        PERFORM public.v1_lock_team(NEW.team_id);
        IF NOT v1_is_team_leader(NEW.team_id,v1_actor_id())
            OR NEW.created_by<>v1_actor_id() THEN
            RAISE EXCEPTION 'Project creator must be current team leader';
        END IF;
    ELSE
        IF NEW.team_id IS DISTINCT FROM OLD.team_id OR
           NEW.created_by IS DISTINCT FROM OLD.created_by THEN
            RAISE EXCEPTION 'Project team_id/created_by immutable';
        END IF;
        IF NEW.name IS DISTINCT FROM OLD.name OR
           NEW.description IS DISTINCT FROM OLD.description THEN
            IF NOT v1_is_team_leader(OLD.team_id,v1_actor_id()) THEN
                RAISE EXCEPTION 'Only team leader may edit Project' USING ERRCODE='42501';
            END IF;
            IF NOT v1_topic_metadata_editable(OLD.id) THEN
                RAISE EXCEPTION 'Project metadata locked in current phase';
            END IF;
        END IF;
    END IF;
    RETURN NEW;
END $$;
ALTER FUNCTION public.v1_project_guard() SET search_path = pg_catalog, public, pg_temp;
REVOKE ALL ON FUNCTION public.v1_project_guard() FROM PUBLIC;

CREATE OR REPLACE FUNCTION public.v1_team_final_cardinality() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE v_team BIGINT;
BEGIN
    -- Separate statements avoid resolving team_members fields on a teams row.
    IF TG_TABLE_NAME='teams' THEN
        v_team := CASE WHEN TG_OP='DELETE' THEN OLD.id ELSE NEW.id END;
    ELSE
        v_team := CASE WHEN TG_OP='DELETE' THEN OLD.team_id ELSE NEW.team_id END;
    END IF;
    IF EXISTS (SELECT 1 FROM teams WHERE id=v_team) THEN
        IF (SELECT count(*) FROM team_members WHERE team_id=v_team) < 1
           OR (SELECT count(*) FROM team_members WHERE team_id=v_team AND role='leader') <> 1 THEN
            RAISE EXCEPTION 'Team % must have at least one member and exactly one leader at COMMIT',v_team;
        END IF;
    END IF;
    RETURN NULL;
END $$;
ALTER FUNCTION public.v1_team_final_cardinality() SET search_path = pg_catalog, public, pg_temp;
REVOKE ALL ON FUNCTION public.v1_team_final_cardinality() FROM PUBLIC;

CREATE OR REPLACE FUNCTION public.v1_in_progress_has_assignee() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE v_task BIGINT;
BEGIN
    -- Separate statements prevent resolving fields absent from this row type.
    IF TG_TABLE_NAME='tasks' THEN
        v_task:=CASE WHEN TG_OP='DELETE' THEN OLD.id ELSE NEW.id END;
    ELSE
        v_task:=CASE WHEN TG_OP='DELETE' THEN OLD.task_id ELSE NEW.task_id END;
    END IF;
    IF EXISTS(SELECT 1 FROM tasks WHERE id=v_task AND status='in_progress')
       AND NOT EXISTS(SELECT 1 FROM task_assignees WHERE task_id=v_task) THEN
        RAISE EXCEPTION 'In-progress Task % must have an assignee at COMMIT',v_task;
    END IF;
    RETURN NULL;
END $$;
ALTER FUNCTION public.v1_in_progress_has_assignee() SET search_path = pg_catalog, public, pg_temp;
REVOKE ALL ON FUNCTION public.v1_in_progress_has_assignee() FROM PUBLIC;

-- Review-only helper grant, matching the existing V1 RBAC template.
GRANT EXECUTE ON FUNCTION public.v1_lock_team(bigint) TO project_app;
ROLLBACK;
