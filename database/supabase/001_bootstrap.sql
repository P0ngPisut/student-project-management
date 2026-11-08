-- Supabase bootstrap for a NEW, EMPTY project database only.
-- Generated from the reviewed V1/Auth SQL sources; do not run on an existing
-- application database. This script commits schema and grants in one transaction.
-- It does not create database roles or set passwords; see README.md.
-- A successful SQL Editor run does not by itself prove the runtime URL works.

BEGIN;
SET LOCAL statement_timeout = '30s';
SET LOCAL lock_timeout = '5s';

DO $supabase_preflight$
DECLARE
    v_names TEXT[] := ARRAY[
        'users', 'teams', 'team_members', 'projects', 'advisor_invitations',
        'project_submissions', 'project_submission_files', 'committee_assignments',
        'committee_topic_votes', 'committee_evaluations', 'milestones', 'tasks',
        'task_assignees', 'task_assignment_history'
    ];
    v_name TEXT;
BEGIN
    IF current_database() <> 'postgres' OR current_user <> 'postgres' THEN
        RAISE EXCEPTION 'Run in Supabase database postgres as the postgres administrator';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
        WHERE rolname = 'project_owner' AND NOT rolsuper AND NOT rolcanlogin
          AND NOT rolinherit
          AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolbypassrls
          AND NOT rolreplication
    ) THEN
        RAISE EXCEPTION 'Create project_owner as a non-login, non-privileged role first';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
        WHERE rolname = 'project_app' AND rolcanlogin AND NOT rolsuper
          AND NOT rolinherit
          AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolbypassrls
          AND NOT rolreplication AND rolpassword IS NOT NULL
    ) THEN
        RAISE EXCEPTION 'Create project_app as a restricted login role and set its password first';
    END IF;
    IF pg_catalog.pg_has_role('project_app', 'project_owner', 'MEMBER')
       OR pg_catalog.pg_has_role('project_app', 'pg_read_all_data', 'MEMBER')
       OR pg_catalog.pg_has_role('project_app', 'pg_write_all_data', 'MEMBER')
       OR EXISTS (
           SELECT 1 FROM pg_catalog.pg_auth_members m
           JOIN pg_catalog.pg_roles r ON r.oid = m.member
           WHERE r.rolname = 'project_app'
       )
       OR EXISTS (
           SELECT 1 FROM pg_catalog.pg_database d
           JOIN pg_catalog.pg_roles r ON r.oid = d.datdba
           WHERE d.datname = current_database() AND r.rolname = 'project_app'
       ) THEN
        RAISE EXCEPTION 'project_app must not inherit owner/broad-data roles or own the database';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_namespace WHERE nspname = 'spms_auth') THEN
        RAISE EXCEPTION 'spms_auth already exists; refusing to overwrite an existing schema';
    END IF;
    FOREACH v_name IN ARRAY v_names LOOP
        IF pg_catalog.to_regclass(pg_catalog.format('public.%I', v_name)) IS NOT NULL THEN
            RAISE EXCEPTION 'public.% already exists; refusing to overwrite existing objects', v_name;
        END IF;
    END LOOP;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_proc p
        JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public' AND p.proname LIKE 'v1\_%' ESCAPE '\'
    ) THEN
        RAISE EXCEPTION 'public already contains v1_* functions; refusing to overwrite';
    END IF;
END
$supabase_preflight$;

GRANT CREATE ON DATABASE postgres TO project_owner;
GRANT USAGE, CREATE ON SCHEMA public TO project_owner;
SET LOCAL ROLE project_owner;
SET LOCAL search_path = public, pg_catalog;

-- V1 public tables, constraints, workflow functions and triggers.
-- ============================================================================
-- Student Project Management System | Database Schema V1 | REVISED DRAFT (DESIGN ONLY)
-- Source: Database_Schema_V1_Data_Dictionary.md, confirmed G-01..G-12,
--         C-01..C-07, D-01.  No new tables or columns.
-- REVISION: A-01..A-06 plus A-02/A-05 controlled write-entrypoint review; originals preserved.
-- A-05: seven DB-state helpers are VOLATILE to avoid a stale statement snapshot after row locks.
-- R-01 = A: projects are NEVER deletable in V1; database DELETE guard + no app DELETE grant.
-- Source draft; copied into this guarded Supabase bootstrap for review.
-- This file is a reviewable SQL DRAFT, NOT a production-ready migration.
-- Privileged operations, API authorization, lock-order guarantees, concurrency
-- tests and access-control deployment are documented in companion review file.
-- Target: PostgreSQL (test in a disposable database after approval).
-- ============================================================================


-- This file targets a NEW, empty database/schema only.  It must not be
-- executed until privileges and trusted schema ownership are approved.
SET LOCAL search_path = public, pg_catalog;

-- 01 / USERS -----------------------------------------------------------------
CREATE TABLE users (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    role VARCHAR(30) NOT NULL,
    CONSTRAINT ck_users_full_name CHECK (full_name = btrim(full_name, E' \t\n\r\f\v') AND full_name <> ''),
    CONSTRAINT ck_users_email_normalized CHECK (email = lower(btrim(email, E' \t\n\r\f\v')) AND email <> ''),
    CONSTRAINT ck_users_role CHECK (role IN ('student','advisor','coordinator'))
);

-- 02 / TEAMS -----------------------------------------------------------------
CREATE TABLE teams (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT NULL,
    CONSTRAINT ck_teams_name CHECK (name = btrim(name, E' \t\n\r\f\v') AND name <> ''),
    CONSTRAINT ck_teams_description CHECK (description IS NULL OR (description = btrim(description, E' \t\n\r\f\v') AND description <> ''))
);

-- 03 / TEAM MEMBERS ----------------------------------------------------------
CREATE TABLE team_members (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    team_id BIGINT NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL UNIQUE REFERENCES users(id) ON DELETE RESTRICT,
    role VARCHAR(20) NOT NULL,
    CONSTRAINT ck_team_members_role CHECK (role IN ('leader','member'))
);

-- 04 / PROJECTS --------------------------------------------------------------
CREATE TABLE projects (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT NULL,
    team_id BIGINT NOT NULL UNIQUE REFERENCES teams(id) ON DELETE RESTRICT,
    created_by BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT ck_projects_name CHECK (name = btrim(name, E' \t\n\r\f\v') AND name <> ''),
    CONSTRAINT ck_projects_description CHECK (description IS NULL OR (description = btrim(description, E' \t\n\r\f\v') AND description <> ''))
);

-- 05 / ADVISOR INVITATIONS ---------------------------------------------------
CREATE TABLE advisor_invitations (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    advisor_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    sent_by BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ NULL,
    resolved_by BIGINT NULL REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT ck_invitations_status CHECK (status IN ('pending','accepted','rejected','cancelled')),
    CONSTRAINT ck_invitations_resolution CHECK (
        (status = 'pending' AND resolved_at IS NULL AND resolved_by IS NULL)
        OR (status <> 'pending' AND resolved_at IS NOT NULL AND resolved_by IS NOT NULL)
    ),
    CONSTRAINT ck_invitations_resolution_time CHECK (resolved_at IS NULL OR resolved_at >= sent_at)
);

-- 06 / PROJECT SUBMISSIONS ---------------------------------------------------
CREATE TABLE project_submissions (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    submitted_by BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    snapshot_name VARCHAR(255) NOT NULL,
    snapshot_description TEXT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'pending_review',
    reviewed_by BIGINT NULL REFERENCES users(id) ON DELETE RESTRICT,
    reviewed_at TIMESTAMPTZ NULL,
    review_comment TEXT NULL,
    CONSTRAINT ck_submissions_status CHECK (status IN ('pending_review','approved','revision_requested')),
    CONSTRAINT ck_submissions_snapshot_name CHECK (snapshot_name = btrim(snapshot_name, E' \t\n\r\f\v') AND snapshot_name <> ''),
    CONSTRAINT ck_submissions_review_fields CHECK (
        (status = 'pending_review' AND reviewed_by IS NULL AND reviewed_at IS NULL AND review_comment IS NULL)
        OR (status IN ('approved','revision_requested') AND reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)
    ),
    CONSTRAINT ck_submissions_review_comment CHECK (
        review_comment IS NULL OR (review_comment = btrim(review_comment, E' \t\n\r\f\v') AND review_comment <> '')
    ),
    CONSTRAINT ck_submissions_revision_comment CHECK (
        status <> 'revision_requested' OR (review_comment IS NOT NULL AND review_comment <> '')
    ),
    CONSTRAINT ck_submissions_review_time CHECK (reviewed_at IS NULL OR reviewed_at >= submitted_at)
);

-- 07 / PROJECT SUBMISSION FILES ---------------------------------------------
CREATE TABLE project_submission_files (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    submission_id BIGINT NOT NULL UNIQUE REFERENCES project_submissions(id) ON DELETE RESTRICT,
    file_data BYTEA NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    CONSTRAINT ck_submission_file_size CHECK (octet_length(file_data) BETWEEN 1 AND 4000000),
    CONSTRAINT ck_submission_filename CHECK (
        original_filename = btrim(original_filename, E' \t\n\r\f\v') AND original_filename <> ''
    ),
    CONSTRAINT ck_submission_filename_mime CHECK (
        (lower(right(original_filename,4)) = '.pdf'
            AND mime_type = 'application/pdf')
        OR (lower(right(original_filename,5)) = '.pptx'
            AND mime_type = 'application/vnd.openxmlformats-officedocument.presentationml.presentation')
    )
);

-- 08 / COMMITTEE ASSIGNMENTS -------------------------------------------------
CREATE TABLE committee_assignments (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    advisor_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    assigned_by BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_committee_project_advisor UNIQUE (project_id,advisor_id)
);

-- 09 / COMMITTEE TOPIC VOTES -------------------------------------------------
CREATE TABLE committee_topic_votes (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    submission_id BIGINT NOT NULL REFERENCES project_submissions(id) ON DELETE RESTRICT,
    committee_assignment_id BIGINT NOT NULL REFERENCES committee_assignments(id) ON DELETE RESTRICT,
    vote VARCHAR(30) NOT NULL,
    comment TEXT NULL,
    voted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_committee_vote_submission_member UNIQUE (submission_id,committee_assignment_id),
    CONSTRAINT ck_committee_vote_value CHECK (vote IN ('approved','revision_requested')),
    CONSTRAINT ck_committee_vote_comment CHECK (
        comment IS NULL OR (comment = btrim(comment, E' \t\n\r\f\v') AND comment <> '')
    ),
    CONSTRAINT ck_committee_vote_revision_comment CHECK (
        vote <> 'revision_requested' OR (comment IS NOT NULL AND comment <> '')
    )
);

-- 10 / COMMITTEE EVALUATIONS -------------------------------------------------
CREATE TABLE committee_evaluations (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    committee_assignment_id BIGINT NOT NULL UNIQUE REFERENCES committee_assignments(id) ON DELETE RESTRICT,
    score INTEGER NOT NULL,
    comment TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_evaluations_score CHECK (score BETWEEN 0 AND 100),
    CONSTRAINT ck_evaluations_comment CHECK (comment = btrim(comment, E' \t\n\r\f\v') AND comment <> '')
);

-- 11 / MILESTONES ------------------------------------------------------------
CREATE TABLE milestones (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    name VARCHAR(255) NOT NULL,
    description TEXT NULL,
    due_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'not_started',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    updated_by BIGINT NULL REFERENCES users(id) ON DELETE RESTRICT,
    completed_at TIMESTAMPTZ NULL,
    CONSTRAINT ck_milestones_name CHECK (name = btrim(name, E' \t\n\r\f\v') AND name <> ''),
    CONSTRAINT ck_milestones_description CHECK (description IS NULL OR (description = btrim(description, E' \t\n\r\f\v') AND description <> '')),
    CONSTRAINT ck_milestones_status CHECK (status IN ('not_started','in_progress','completed')),
    CONSTRAINT ck_milestones_completion CHECK ((status = 'completed') = (completed_at IS NOT NULL))
);

-- 12 / TASKS -----------------------------------------------------------------
CREATE TABLE tasks (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    milestone_id BIGINT NOT NULL REFERENCES milestones(id) ON DELETE RESTRICT,
    name VARCHAR(255) NOT NULL,
    description TEXT NULL,
    due_date DATE NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'not_started',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    updated_by BIGINT NULL REFERENCES users(id) ON DELETE RESTRICT,
    completed_at TIMESTAMPTZ NULL,
    CONSTRAINT ck_tasks_name CHECK (name = btrim(name, E' \t\n\r\f\v') AND name <> ''),
    CONSTRAINT ck_tasks_description CHECK (description IS NULL OR (description = btrim(description, E' \t\n\r\f\v') AND description <> '')),
    CONSTRAINT ck_tasks_status CHECK (status IN ('not_started','in_progress','completed')),
    CONSTRAINT ck_tasks_completion CHECK ((status = 'completed') = (completed_at IS NOT NULL))
);

-- 13 / TASK ASSIGNEES --------------------------------------------------------
CREATE TABLE task_assignees (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    task_id BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    team_member_id BIGINT NOT NULL REFERENCES team_members(id) ON DELETE RESTRICT,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_task_assignees_task_member UNIQUE (task_id,team_member_id)
);

-- 14 / TASK ASSIGNMENT HISTORY ----------------------------------------------
CREATE TABLE task_assignment_history (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    task_id BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    assigned_at TIMESTAMPTZ NOT NULL,
    unassigned_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_assignment_history_time CHECK (unassigned_at >= assigned_at)
);

-- UNIQUE / PARTIAL UNIQUE / EXPRESSION INDEXES ------------------------------
CREATE UNIQUE INDEX uq_team_members_one_leader
    ON team_members(team_id) WHERE role = 'leader';
CREATE UNIQUE INDEX uq_invitations_active_project
    ON advisor_invitations(project_id) WHERE status IN ('pending','accepted');
CREATE UNIQUE INDEX uq_submissions_one_pending
    ON project_submissions(project_id) WHERE status = 'pending_review';
CREATE UNIQUE INDEX uq_milestones_project_name_ci
    ON milestones(project_id,lower(name));
CREATE UNIQUE INDEX uq_tasks_milestone_name_ci
    ON tasks(milestone_id,lower(name));

-- FK lookup indexes (optimization only; no additional business rules) -------
CREATE INDEX ix_invitations_advisor ON advisor_invitations(advisor_id);
CREATE INDEX ix_invitations_sent_by ON advisor_invitations(sent_by);
CREATE INDEX ix_submissions_project_latest ON project_submissions(project_id,id DESC);
CREATE INDEX ix_submissions_submitted_by ON project_submissions(submitted_by);
CREATE INDEX ix_submissions_reviewed_by ON project_submissions(reviewed_by);
CREATE INDEX ix_committee_assignments_advisor ON committee_assignments(advisor_id);
CREATE INDEX ix_committee_assignments_assigned_by ON committee_assignments(assigned_by);
CREATE INDEX ix_votes_assignment ON committee_topic_votes(committee_assignment_id);
CREATE INDEX ix_evaluations_created_at ON committee_evaluations(created_at,id);
CREATE INDEX ix_milestones_created_by ON milestones(created_by);
CREATE INDEX ix_milestones_updated_by ON milestones(updated_by);
CREATE INDEX ix_tasks_milestone ON tasks(milestone_id);
CREATE INDEX ix_tasks_created_by ON tasks(created_by);
CREATE INDEX ix_tasks_updated_by ON tasks(updated_by);
CREATE INDEX ix_task_assignees_member ON task_assignees(team_member_id);
CREATE INDEX ix_assignment_history_task ON task_assignment_history(task_id);
CREATE INDEX ix_assignment_history_user ON task_assignment_history(user_id);

-- ============================================================================
-- TRIGGER FUNCTIONS: supporting invariants.  All user/API authorization
-- depends on a VERIFIED actor provided by FastAPI within its transaction.
-- The application database role MUST NOT have unrestricted direct table DML.
-- These functions are not a substitute for a secure privilege design.
-- ============================================================================

CREATE FUNCTION v1_actor_id() RETURNS BIGINT
LANGUAGE plpgsql STABLE AS $$
DECLARE v TEXT;
BEGIN
    v := nullif(current_setting('app.actor_user_id',true),'');
    IF v IS NULL THEN
        RAISE EXCEPTION 'Verified transaction actor is required' USING ERRCODE='42501';
    END IF;
    RETURN v::BIGINT;
EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range THEN
    RAISE EXCEPTION 'Invalid actor context' USING ERRCODE='42501';
END $$;

CREATE FUNCTION v1_actor_has_role(p_role TEXT) RETURNS BOOLEAN
LANGUAGE sql VOLATILE AS $$
    SELECT EXISTS (SELECT 1 FROM users WHERE id = v1_actor_id() AND role = p_role);
$$;

CREATE FUNCTION v1_is_team_leader(p_team_id BIGINT, p_actor BIGINT) RETURNS BOOLEAN
LANGUAGE sql VOLATILE AS $$
    SELECT EXISTS (SELECT 1 FROM team_members
        WHERE team_id=p_team_id AND user_id=p_actor AND role='leader');
$$;

CREATE FUNCTION v1_is_current_member(p_team_id BIGINT, p_actor BIGINT) RETURNS BOOLEAN
LANGUAGE sql VOLATILE AS $$
    SELECT EXISTS (SELECT 1 FROM team_members
        WHERE team_id=p_team_id AND user_id=p_actor);
$$;

CREATE FUNCTION v1_advisor_for_project(p_project BIGINT) RETURNS BIGINT
LANGUAGE sql VOLATILE AS $$
    SELECT advisor_id FROM advisor_invitations
    WHERE project_id=p_project AND status='accepted'
    ORDER BY id DESC LIMIT 1;
$$;

CREATE FUNCTION v1_has_first_evaluation(p_project BIGINT) RETURNS BOOLEAN
LANGUAGE sql VOLATILE AS $$
    SELECT EXISTS (
        SELECT 1 FROM committee_evaluations e
        JOIN committee_assignments a ON a.id=e.committee_assignment_id
        WHERE a.project_id=p_project
    );
$$;

-- Returns NULL if no completed committee decision; 'approved' or
-- 'revision_requested' only after ALL assigned committee members have voted.
CREATE FUNCTION v1_topic_decision(p_submission BIGINT) RETURNS TEXT
LANGUAGE plpgsql VOLATILE AS $$
DECLARE v_project BIGINT; v_total INTEGER; v_cast INTEGER; v_approved INTEGER;
BEGIN
    SELECT project_id INTO v_project FROM project_submissions WHERE id=p_submission;
    IF NOT FOUND THEN RETURN NULL; END IF;
    SELECT count(*) INTO v_total FROM committee_assignments WHERE project_id=v_project;
    IF v_total < 3 THEN RETURN NULL; END IF;
    SELECT count(*), count(*) FILTER (WHERE v.vote='approved')
      INTO v_cast,v_approved
      FROM committee_topic_votes v
      JOIN committee_assignments a ON a.id=v.committee_assignment_id
     WHERE v.submission_id=p_submission AND a.project_id=v_project;
    IF v_cast <> v_total THEN RETURN NULL; END IF;
    RETURN CASE WHEN v_approved*2 > v_total THEN 'approved'
                ELSE 'revision_requested' END;
END $$;

-- Topic metadata editable: before first submission, during advisor revision,
-- or when the committee has FINISHED voting and requested revision.
CREATE FUNCTION v1_topic_metadata_editable(p_project BIGINT) RETURNS BOOLEAN
LANGUAGE plpgsql VOLATILE AS $$
DECLARE v_sub BIGINT; v_status TEXT;
BEGIN
    SELECT id,status INTO v_sub,v_status FROM project_submissions
    WHERE project_id=p_project ORDER BY id DESC LIMIT 1;
    IF NOT FOUND THEN RETURN TRUE; END IF;
    IF v_status='revision_requested' THEN RETURN TRUE; END IF;
    IF v_status='approved'
       AND v1_topic_decision(v_sub)='revision_requested' THEN RETURN TRUE; END IF;
    RETURN FALSE;
END $$;

-- Shared row lock must be acquired by the calling API/controlled operation
-- BEFORE changing child rows. Trigger checks are a second line of defense.
-- These narrowly scoped definers only lock parent rows. The calling trigger
-- or controlled operation retains all relationship/phase authorization checks.
-- Require a valid transaction actor; custom GUCs still rely on trusted FastAPI.
CREATE FUNCTION v1_lock_team(p_team BIGINT) RETURNS VOID
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM public.users WHERE id=public.v1_actor_id()) THEN
        RAISE EXCEPTION 'Verified transaction actor must exist' USING ERRCODE='42501';
    END IF;
    PERFORM 1 FROM public.teams WHERE id=p_team FOR UPDATE;
    -- Preserve the caller's existing missing-team checks / foreign-key errors.
END $$;

CREATE FUNCTION v1_lock_project(p_project BIGINT) RETURNS VOID
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM public.users WHERE id=public.v1_actor_id()) THEN
        RAISE EXCEPTION 'Verified transaction actor must exist' USING ERRCODE='42501';
    END IF;
    PERFORM 1 FROM public.projects WHERE id=p_project FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Project not found: %',p_project; END IF;
END $$;

CREATE FUNCTION v1_normalize_user() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='UPDATE' AND NEW.role IS DISTINCT FROM OLD.role THEN
        RAISE EXCEPTION 'users.role cannot change';
    END IF;
    NEW.full_name := btrim(NEW.full_name, E' \t\n\r\f\v');
    NEW.email := lower(btrim(NEW.email, E' \t\n\r\f\v'));
    RETURN NEW;
END $$;
CREATE TRIGGER tr_users_normalize BEFORE INSERT OR UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION v1_normalize_user();

CREATE FUNCTION v1_team_guard() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE v_project BIGINT;
BEGIN
    IF TG_OP = 'DELETE' THEN
        -- A team with a project is protected by projects.team_id RESTRICT.
        -- Deleting a team without a project cascades its team_members.
        IF NOT v1_is_team_leader(OLD.id,v1_actor_id()) THEN
            RAISE EXCEPTION 'Only current leader may delete a team' USING ERRCODE='42501';
        END IF;
        RETURN OLD;
    END IF;
    NEW.name := btrim(NEW.name, E' \t\n\r\f\v');
    NEW.description := nullif(btrim(NEW.description, E' \t\n\r\f\v'),'');
    IF TG_OP = 'UPDATE' THEN
        IF NEW.name IS DISTINCT FROM OLD.name OR
           NEW.description IS DISTINCT FROM OLD.description THEN
            IF NOT v1_is_team_leader(OLD.id,v1_actor_id()) THEN
                RAISE EXCEPTION 'Only leader may edit team' USING ERRCODE='42501';
            END IF;
            SELECT id INTO v_project FROM projects WHERE team_id=OLD.id;
            IF v_project IS NOT NULL AND NOT v1_topic_metadata_editable(v_project) THEN
                RAISE EXCEPTION 'Team metadata locked in current project phase';
            END IF;
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER tr_teams_guard BEFORE INSERT OR UPDATE OR DELETE ON teams
FOR EACH ROW EXECUTE FUNCTION v1_team_guard();

CREATE FUNCTION v1_team_members_guard() RETURNS TRIGGER LANGUAGE plpgsql AS $$
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
CREATE TRIGGER tr_team_members_guard BEFORE INSERT OR UPDATE OR DELETE ON team_members
FOR EACH ROW EXECUTE FUNCTION v1_team_members_guard();

-- Deferred validation: team must have exactly one leader at COMMIT.  The
-- partial UNIQUE index immediately enforces *at most* one leader.
CREATE FUNCTION v1_team_final_cardinality() RETURNS TRIGGER LANGUAGE plpgsql AS $$
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
CREATE CONSTRAINT TRIGGER c_team_created_has_leader
AFTER INSERT OR UPDATE ON teams DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION v1_team_final_cardinality();
CREATE CONSTRAINT TRIGGER c_team_member_cardinality
AFTER INSERT OR UPDATE OR DELETE ON team_members DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION v1_team_final_cardinality();

CREATE FUNCTION v1_project_guard() RETURNS TRIGGER LANGUAGE plpgsql AS $$
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
CREATE TRIGGER tr_projects_guard BEFORE INSERT OR UPDATE OR DELETE ON projects
FOR EACH ROW EXECUTE FUNCTION v1_project_guard();

-- The following generic immutable trigger is used for append-only records.
CREATE FUNCTION v1_no_update_or_delete() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '% is immutable; % forbidden',TG_TABLE_NAME,TG_OP
      USING ERRCODE='55000';
END $$;
CREATE TRIGGER tr_submission_files_immutable BEFORE UPDATE OR DELETE
ON project_submission_files FOR EACH ROW EXECUTE FUNCTION v1_no_update_or_delete();
CREATE TRIGGER tr_votes_immutable BEFORE UPDATE OR DELETE
ON committee_topic_votes FOR EACH ROW EXECUTE FUNCTION v1_no_update_or_delete();
CREATE TRIGGER tr_evaluations_immutable BEFORE UPDATE OR DELETE
ON committee_evaluations FOR EACH ROW EXECUTE FUNCTION v1_no_update_or_delete();

CREATE FUNCTION v1_invitation_guard() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE v_team BIGINT;
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'Invitation history cannot be deleted';
    END IF;
    IF TG_OP='INSERT' THEN
        PERFORM v1_lock_project(NEW.project_id);
        SELECT team_id INTO v_team FROM projects WHERE id=NEW.project_id;
        IF NEW.sent_by<>v1_actor_id() OR NOT v1_is_team_leader(v_team,v1_actor_id()) THEN
            RAISE EXCEPTION 'Only leader may send invitation';
        END IF;
        IF NOT EXISTS(SELECT 1 FROM users WHERE id=NEW.advisor_id AND role='advisor') THEN
            RAISE EXCEPTION 'Invitation target must be advisor';
        END IF;
        IF EXISTS(SELECT 1 FROM advisor_invitations
                  WHERE project_id=NEW.project_id AND status='accepted') THEN
            RAISE EXCEPTION 'Accepted advisor cannot be replaced';
        END IF;
        NEW.status:='pending';
        NEW.sent_at:=NOW();
        NEW.resolved_at:=NULL;
        NEW.resolved_by:=NULL;
    ELSE
        PERFORM v1_lock_project(OLD.project_id);
        IF NEW.project_id IS DISTINCT FROM OLD.project_id OR
           NEW.advisor_id IS DISTINCT FROM OLD.advisor_id OR
           NEW.sent_by IS DISTINCT FROM OLD.sent_by OR
           NEW.sent_at IS DISTINCT FROM OLD.sent_at THEN
            RAISE EXCEPTION 'Invitation identity/timestamp immutable';
        END IF;
        IF OLD.status<>'pending' THEN
            RAISE EXCEPTION 'Final invitation cannot be edited';
        END IF;
        IF NEW.status NOT IN ('accepted','rejected','cancelled') THEN
            RAISE EXCEPTION 'Invitation may transition only from pending to final';
        END IF;
        IF NEW.status IN ('accepted','rejected') THEN
            IF v1_actor_id()<>OLD.advisor_id THEN
                RAISE EXCEPTION 'Only invited advisor may respond';
            END IF;
        ELSE
            SELECT team_id INTO v_team FROM projects WHERE id=OLD.project_id;
            IF NOT v1_is_team_leader(v_team,v1_actor_id()) THEN
                RAISE EXCEPTION 'Only team leader may cancel invitation';
            END IF;
        END IF;
        NEW.resolved_by:=v1_actor_id();
        NEW.resolved_at:=NOW();
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER tr_invitations_guard BEFORE INSERT OR UPDATE OR DELETE
ON advisor_invitations FOR EACH ROW EXECUTE FUNCTION v1_invitation_guard();

CREATE FUNCTION v1_submission_guard() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE v_team BIGINT; v_last_id BIGINT; v_last_status TEXT;
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'Submission history cannot be deleted';
    END IF;
    IF TG_OP='INSERT' THEN
        PERFORM v1_lock_project(NEW.project_id);
        SELECT team_id INTO v_team FROM projects WHERE id=NEW.project_id;
        IF NEW.submitted_by<>v1_actor_id()
           OR NOT v1_is_team_leader(v_team,v1_actor_id()) THEN
            RAISE EXCEPTION 'Only current team leader may submit';
        END IF;
        IF v1_advisor_for_project(NEW.project_id) IS NULL THEN
            RAISE EXCEPTION 'Accepted advisor required before submission';
        END IF;
        SELECT id,status INTO v_last_id,v_last_status
          FROM project_submissions WHERE project_id=NEW.project_id
          ORDER BY id DESC LIMIT 1;
        IF v_last_id IS NOT NULL THEN
            IF v_last_status='revision_requested' THEN
                NULL;  -- Advisor requested revision.
            ELSIF v_last_status='approved'
                  AND v1_topic_decision(v_last_id)='revision_requested' THEN
                NULL;  -- Committee completed its votes and requested revision.
            ELSE
                RAISE EXCEPTION 'New submission not permitted in current phase';
            END IF;
        END IF;
        SELECT name,description INTO NEW.snapshot_name,NEW.snapshot_description
          FROM projects WHERE id=NEW.project_id;
        NEW.status:='pending_review';
        NEW.submitted_at:=NOW();
        NEW.reviewed_by:=NULL;
        NEW.reviewed_at:=NULL;
        NEW.review_comment:=NULL;
    ELSE
        PERFORM v1_lock_project(OLD.project_id);
        IF NEW.project_id IS DISTINCT FROM OLD.project_id
           OR NEW.submitted_by IS DISTINCT FROM OLD.submitted_by
           OR NEW.submitted_at IS DISTINCT FROM OLD.submitted_at
           OR NEW.snapshot_name IS DISTINCT FROM OLD.snapshot_name
           OR NEW.snapshot_description IS DISTINCT FROM OLD.snapshot_description THEN
            RAISE EXCEPTION 'Submission identity/snapshot immutable';
        END IF;
        IF OLD.status<>'pending_review'
           OR NEW.status NOT IN ('approved','revision_requested') THEN
            RAISE EXCEPTION 'Advisor can review pending submission exactly once';
        END IF;
        IF v1_actor_id() IS DISTINCT FROM v1_advisor_for_project(OLD.project_id) THEN
            RAISE EXCEPTION 'Only accepted project advisor may review';
        END IF;
        NEW.reviewed_by:=v1_actor_id();
        NEW.reviewed_at:=NOW();
        NEW.review_comment:=nullif(btrim(NEW.review_comment, E' \t\n\r\f\v'),'');
        IF NEW.status='revision_requested' AND NEW.review_comment IS NULL THEN
            RAISE EXCEPTION 'Revision request must include real comment';
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER tr_submissions_guard BEFORE INSERT OR UPDATE OR DELETE
ON project_submissions FOR EACH ROW EXECUTE FUNCTION v1_submission_guard();

CREATE FUNCTION v1_submission_file_guard() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE v_project BIGINT; v_team BIGINT;
BEGIN
    -- Immutable UPDATE/DELETE is blocked by separate trigger.
    SELECT project_id INTO v_project FROM project_submissions WHERE id=NEW.submission_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'Missing submission for file'; END IF;
    PERFORM v1_lock_project(v_project);
    SELECT team_id INTO v_team FROM projects WHERE id=v_project;
    IF NOT v1_is_team_leader(v_team,v1_actor_id()) THEN
        RAISE EXCEPTION 'Only team leader may upload submission file';
    END IF;
    NEW.original_filename:=btrim(NEW.original_filename, E' \t\n\r\f\v');
    -- Actual PDF/PPTX byte structure validated in FastAPI; CHECK validates
    -- extension/MIME agreement and byte length, not file-content authenticity.
    RETURN NEW;
END $$;
CREATE TRIGGER tr_submission_files_guard BEFORE INSERT
ON project_submission_files FOR EACH ROW EXECUTE FUNCTION v1_submission_file_guard();

-- UNIQUE(file.submission_id) gives at most one file.  This deferred trigger
-- gives at least one file for each newly inserted Submission at COMMIT.
CREATE FUNCTION v1_submission_file_required() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM project_submission_files WHERE submission_id=NEW.id) THEN
        RAISE EXCEPTION 'Submission % must have exactly one file at COMMIT',NEW.id;
    END IF;
    RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER c_submission_requires_file
AFTER INSERT ON project_submissions DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION v1_submission_file_required();

CREATE FUNCTION v1_committee_assignment_guard() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE v_project BIGINT;
BEGIN
    v_project := CASE WHEN TG_OP='DELETE' THEN OLD.project_id ELSE NEW.project_id END;
    PERFORM v1_lock_project(v_project);
    IF NOT v1_actor_has_role('coordinator') THEN
        RAISE EXCEPTION 'Coordinator role required for committee assignment' USING ERRCODE='42501';
    END IF;
    IF EXISTS (
        SELECT 1 FROM committee_topic_votes v
        JOIN committee_assignments a ON a.id=v.committee_assignment_id
        WHERE a.project_id=v_project
    ) THEN
        RAISE EXCEPTION 'Committee roster locked permanently after first vote';
    END IF;
    IF TG_OP='DELETE' THEN RETURN OLD; END IF;
    IF TG_OP='UPDATE' THEN
        IF NEW.project_id IS DISTINCT FROM OLD.project_id OR
           NEW.assigned_by IS DISTINCT FROM OLD.assigned_by OR
           NEW.assigned_at IS DISTINCT FROM OLD.assigned_at THEN
            RAISE EXCEPTION 'Committee project/assigner/time immutable';
        END IF;
    ELSE
        IF NEW.assigned_by<>v1_actor_id() THEN
            RAISE EXCEPTION 'assigned_by must be actual coordinator';
        END IF;
        NEW.assigned_at:=NOW();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM users WHERE id=NEW.advisor_id AND role='advisor') THEN
        RAISE EXCEPTION 'Committee appointee must have advisor role';
    END IF;
    IF NEW.advisor_id = v1_advisor_for_project(v_project) THEN
        RAISE EXCEPTION 'Project accepted advisor cannot serve on own committee';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM project_submissions
                   WHERE project_id=v_project AND status='approved') THEN
        RAISE EXCEPTION 'Advisor-approved submission required before committee appointment';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER tr_committee_assignments_guard BEFORE INSERT OR UPDATE OR DELETE
ON committee_assignments FOR EACH ROW EXECUTE FUNCTION v1_committee_assignment_guard();

CREATE FUNCTION v1_committee_vote_guard() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE v_project BIGINT; v_sub_status TEXT; v_committee_project BIGINT;
        v_committee_advisor BIGINT; v_newest BIGINT; v_count INTEGER;
BEGIN
    SELECT project_id,status INTO v_project,v_sub_status
      FROM project_submissions WHERE id=NEW.submission_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'Missing submission'; END IF;
    PERFORM v1_lock_project(v_project);
    SELECT project_id,advisor_id INTO v_committee_project,v_committee_advisor
      FROM committee_assignments WHERE id=NEW.committee_assignment_id;
    IF v_committee_project IS DISTINCT FROM v_project THEN
        RAISE EXCEPTION 'Vote committee assignment must belong to same project';
    END IF;
    IF v_committee_advisor<>v1_actor_id() THEN
        RAISE EXCEPTION 'Only appointed committee member may vote';
    END IF;
    SELECT id INTO v_newest FROM project_submissions
      WHERE project_id=v_project ORDER BY id DESC LIMIT 1;
    IF NEW.submission_id<>v_newest OR v_sub_status<>'approved' THEN
        RAISE EXCEPTION 'Vote requires latest advisor-approved submission';
    END IF;
    SELECT count(*) INTO v_count FROM committee_assignments WHERE project_id=v_project;
    IF v_count<3 THEN RAISE EXCEPTION 'At least 3 committee members required'; END IF;
    NEW.comment:=nullif(btrim(NEW.comment, E' \t\n\r\f\v'),'');
    IF NEW.vote='revision_requested' AND NEW.comment IS NULL THEN
        RAISE EXCEPTION 'Revision vote requires real comment';
    END IF;
    NEW.voted_at:=NOW();
    RETURN NEW;
END $$;
CREATE TRIGGER tr_committee_votes_insert BEFORE INSERT ON committee_topic_votes
FOR EACH ROW EXECUTE FUNCTION v1_committee_vote_guard();

CREATE FUNCTION v1_committee_evaluation_guard() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE v_project BIGINT; v_advisor BIGINT; v_latest BIGINT;
BEGIN
    SELECT project_id,advisor_id INTO v_project,v_advisor
      FROM committee_assignments WHERE id=NEW.committee_assignment_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'Missing committee assignment'; END IF;
    PERFORM v1_lock_project(v_project);
    IF v_advisor<>v1_actor_id() THEN
        RAISE EXCEPTION 'Only assigned advisor may submit own evaluation';
    END IF;
    SELECT id INTO v_latest FROM project_submissions
      WHERE project_id=v_project ORDER BY id DESC LIMIT 1;
    IF v_latest IS NULL OR v1_topic_decision(v_latest) IS DISTINCT FROM 'approved' THEN
        RAISE EXCEPTION 'Committee topic approval required before evaluation';
    END IF;
    IF NOT EXISTS(SELECT 1 FROM milestones WHERE project_id=v_project AND status='completed') THEN
        RAISE EXCEPTION 'At least one completed milestone required for evaluation';
    END IF;
    NEW.comment:=btrim(NEW.comment, E' \t\n\r\f\v');
    NEW.created_at:=NOW();
    RETURN NEW;
END $$;
CREATE TRIGGER tr_evaluations_insert BEFORE INSERT ON committee_evaluations
FOR EACH ROW EXECUTE FUNCTION v1_committee_evaluation_guard();

-- Controlled transfer helper.  On deployment revoke direct UPDATE of
-- team_members.role from the application role; grant EXECUTE on this function
-- only to that role after separately securing the actor context.
CREATE FUNCTION v1_transfer_team_leader(p_team BIGINT,p_next_user BIGINT)
RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE v_old_user BIGINT; v_previous TEXT;
BEGIN
    PERFORM 1 FROM public.teams WHERE id=p_team FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Team not found'; END IF;
    SELECT user_id INTO v_old_user FROM public.team_members
     WHERE team_id=p_team AND role='leader' FOR UPDATE;
    IF v_old_user IS NULL OR v_old_user<>public.v1_actor_id() THEN
        RAISE EXCEPTION 'Only current leader may transfer leadership';
    END IF;
    IF p_next_user=v_old_user OR NOT EXISTS (
        SELECT 1 FROM public.team_members
        WHERE team_id=p_team AND user_id=p_next_user AND role='member'
    ) THEN RAISE EXCEPTION 'New leader must be another current member'; END IF;
    v_previous:=current_setting('app.v1_leader_transfer',true);
    PERFORM set_config('app.v1_leader_transfer','on',true);
    PERFORM set_config('app.v1_transfer_initiator',v_old_user::TEXT,true);
    UPDATE public.team_members SET role='member'
      WHERE team_id=p_team AND user_id=v_old_user;
    UPDATE public.team_members SET role='leader'
      WHERE team_id=p_team AND user_id=p_next_user;
    PERFORM set_config('app.v1_leader_transfer',coalesce(v_previous,''),true);
    PERFORM set_config('app.v1_transfer_initiator','',true);
END $$;

CREATE FUNCTION v1_milestone_guard() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE v_project BIGINT; v_team BIGINT; v_auto BOOLEAN; v_changed BOOLEAN;
BEGIN
    v_project:=CASE WHEN TG_OP='DELETE' THEN OLD.project_id ELSE NEW.project_id END;
    PERFORM v1_lock_project(v_project);
    SELECT team_id INTO v_team FROM projects WHERE id=v_project;
    IF v1_has_first_evaluation(v_project) THEN
        RAISE EXCEPTION 'Milestones locked after first committee evaluation';
    END IF;
    IF TG_OP='DELETE' THEN
        IF NOT v1_is_team_leader(v_team,v1_actor_id()) THEN
            RAISE EXCEPTION 'Only leader may delete milestone';
        END IF;
        RETURN OLD;
    END IF;
    NEW.name:=btrim(NEW.name, E' \t\n\r\f\v');
    NEW.description:=nullif(btrim(NEW.description, E' \t\n\r\f\v'),'');
    v_auto:=(coalesce(current_setting('app.v1_milestone_sync',true),'')='on'); -- A-01: NULL must mean false
    IF TG_OP='INSERT' THEN
        IF NOT v1_is_team_leader(v_team,v1_actor_id()) OR
           NEW.created_by<>v1_actor_id() THEN
            RAISE EXCEPTION 'Only current leader may create milestone';
        END IF;
        IF NEW.due_date < (NOW() AT TIME ZONE 'Asia/Bangkok')::DATE THEN
            RAISE EXCEPTION 'Milestone due_date is before current Bangkok date';
        END IF;
        NEW.status:='not_started';
        NEW.completed_at:=NULL;
        NEW.created_at:=NOW();
        NEW.updated_at:=NEW.created_at;
        NEW.updated_by:=NULL;
    ELSE
        IF NEW.project_id IS DISTINCT FROM OLD.project_id OR
           NEW.created_by IS DISTINCT FROM OLD.created_by OR
           NEW.created_at IS DISTINCT FROM OLD.created_at THEN
            RAISE EXCEPTION 'Milestone project/creator/created_at immutable';
        END IF;
        IF NEW.due_date IS DISTINCT FROM OLD.due_date THEN
            IF NEW.due_date < (NOW() AT TIME ZONE 'Asia/Bangkok')::DATE THEN
                RAISE EXCEPTION 'Milestone due_date is before current Bangkok date';
            END IF;
            IF EXISTS(SELECT 1 FROM tasks
                      WHERE milestone_id=OLD.id AND due_date>NEW.due_date) THEN
                RAISE EXCEPTION 'D-01: adjust task due dates before shortening milestone due date';
            END IF;
        END IF;
        IF NEW.status IS DISTINCT FROM OLD.status AND NOT v_auto THEN
            RAISE EXCEPTION 'Milestone status is derived from tasks';
        END IF;
        IF (NEW.name,NEW.description,NEW.due_date) IS DISTINCT FROM
           (OLD.name,OLD.description,OLD.due_date) THEN
            IF NOT v1_is_team_leader(v_team,v1_actor_id()) THEN
                RAISE EXCEPTION 'Only leader may edit milestone metadata';
            END IF;
        END IF;
        v_changed := (NEW.name,NEW.description,NEW.due_date,NEW.status)
                   IS DISTINCT FROM
                     (OLD.name,OLD.description,OLD.due_date,OLD.status);
        IF v_changed THEN
            NEW.updated_at:=NOW();
            NEW.updated_by:=v1_actor_id();
        ELSE
            NEW.updated_at:=OLD.updated_at;
            NEW.updated_by:=OLD.updated_by;
        END IF;
        IF NEW.status='completed' AND OLD.status<>'completed' THEN
            NEW.completed_at:=NOW();
        ELSIF NEW.status<>'completed' THEN
            NEW.completed_at:=NULL;
        ELSE
            NEW.completed_at:=OLD.completed_at;
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER tr_milestones_guard BEFORE INSERT OR UPDATE OR DELETE ON milestones
FOR EACH ROW EXECUTE FUNCTION v1_milestone_guard();

CREATE FUNCTION v1_task_guard() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE v_project BIGINT; v_team BIGINT; v_parent_date DATE;
        v_changed BOOLEAN; v_metadata_changed BOOLEAN; v_count BIGINT;
BEGIN
    SELECT project_id,due_date INTO v_project,v_parent_date
    FROM milestones WHERE id=CASE WHEN TG_OP='DELETE' THEN OLD.milestone_id ELSE NEW.milestone_id END;
    IF NOT FOUND THEN RAISE EXCEPTION 'Task milestone not found'; END IF;
    PERFORM v1_lock_project(v_project);
    -- Controlled operations MUST acquire project and milestone locks BEFORE
    -- editing task rows; see companion review for raw-SQL lock-order caveat.
    PERFORM 1 FROM milestones
      WHERE id=CASE WHEN TG_OP='DELETE' THEN OLD.milestone_id ELSE NEW.milestone_id END
      FOR UPDATE;
    -- Re-read due_date after lock; the earlier read was only a locator.
    SELECT due_date INTO v_parent_date FROM milestones
      WHERE id=CASE WHEN TG_OP='DELETE' THEN OLD.milestone_id ELSE NEW.milestone_id END;
    SELECT team_id INTO v_team FROM projects WHERE id=v_project;
    IF v1_has_first_evaluation(v_project) THEN
        RAISE EXCEPTION 'Tasks locked after first committee evaluation';
    END IF;
    IF TG_OP='DELETE' THEN
        IF NOT v1_is_team_leader(v_team,v1_actor_id()) THEN
            RAISE EXCEPTION 'Only leader may delete Task';
        END IF;
        IF OLD.status='completed' THEN
            RAISE EXCEPTION 'Reopen completed Task before deleting';
        END IF;
        RETURN OLD;
    END IF;
    NEW.name:=btrim(NEW.name, E' \t\n\r\f\v');
    NEW.description:=nullif(btrim(NEW.description, E' \t\n\r\f\v'),'');
    IF TG_OP='INSERT' THEN
        IF NOT v1_is_team_leader(v_team,v1_actor_id()) OR
           NEW.created_by<>v1_actor_id() THEN
            RAISE EXCEPTION 'Only leader may create Task';
        END IF;
        NEW.status:='not_started';
        NEW.completed_at:=NULL;
        NEW.created_at:=NOW();
        NEW.updated_at:=NEW.created_at;
        NEW.updated_by:=NULL;
    ELSE
        IF NEW.milestone_id IS DISTINCT FROM OLD.milestone_id OR
           NEW.created_at IS DISTINCT FROM OLD.created_at OR
           NEW.created_by IS DISTINCT FROM OLD.created_by THEN
            RAISE EXCEPTION 'Task milestone/creator/created_at immutable';
        END IF;
        v_metadata_changed := (NEW.name,NEW.description,NEW.due_date)
                    IS DISTINCT FROM (OLD.name,OLD.description,OLD.due_date);
        IF v_metadata_changed THEN
            IF OLD.status='completed' THEN
                RAISE EXCEPTION 'Reopen completed Task before editing metadata';
            END IF;
            IF NOT v1_is_team_leader(v_team,v1_actor_id()) THEN
                RAISE EXCEPTION 'Only leader may edit Task metadata';
            END IF;
        END IF;
        IF NEW.status IS DISTINCT FROM OLD.status THEN
            IF NOT v1_is_current_member(v_team,v1_actor_id()) THEN
                RAISE EXCEPTION 'Current team membership required to change Task status';
            END IF;
            IF OLD.status='completed' AND (
                NEW.status<>'in_progress' OR
                NOT v1_is_team_leader(v_team,v1_actor_id())) THEN
                RAISE EXCEPTION 'Only leader may reopen completed Task to in_progress';
            END IF;
        END IF;
        v_changed := (NEW.name,NEW.description,NEW.due_date,NEW.status)
                   IS DISTINCT FROM (OLD.name,OLD.description,OLD.due_date,OLD.status);
        IF v_changed THEN
            NEW.updated_at:=NOW();
            NEW.updated_by:=v1_actor_id();
        ELSE
            NEW.updated_at:=OLD.updated_at;
            NEW.updated_by:=OLD.updated_by;
        END IF;
    END IF;
    IF TG_OP='INSERT' THEN
        IF NEW.due_date IS NOT NULL AND (
           NEW.due_date < (NOW() AT TIME ZONE 'Asia/Bangkok')::DATE OR
           NEW.due_date > v_parent_date) THEN
            RAISE EXCEPTION 'Invalid Task due_date';
        END IF;
    ELSIF NEW.due_date IS DISTINCT FROM OLD.due_date THEN
        IF NEW.due_date IS NOT NULL AND (
           NEW.due_date < (NOW() AT TIME ZONE 'Asia/Bangkok')::DATE OR
           NEW.due_date > v_parent_date) THEN
            RAISE EXCEPTION 'Invalid Task due_date';
        END IF;
    END IF;
    IF TG_OP='UPDATE' AND NEW.status='completed' AND OLD.status<>'completed' THEN
        SELECT count(*) INTO v_count FROM task_assignees WHERE task_id=OLD.id;
        IF v_count<1 THEN RAISE EXCEPTION 'Task completion requires >=1 assignee'; END IF;
    END IF;
    IF TG_OP='UPDATE' AND NEW.status='in_progress' AND OLD.status<>'in_progress' THEN
        SELECT count(*) INTO v_count FROM task_assignees WHERE task_id=OLD.id;
        IF v_count<1 THEN RAISE EXCEPTION 'In-progress Task requires >=1 assignee'; END IF;
    END IF;
    IF TG_OP='UPDATE' THEN
        IF NEW.status='completed' AND OLD.status<>'completed' THEN
            NEW.completed_at:=NOW();
        ELSIF NEW.status<>'completed' THEN
            NEW.completed_at:=NULL;
        ELSE
            NEW.completed_at:=OLD.completed_at;
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER tr_tasks_guard BEFORE INSERT OR UPDATE OR DELETE ON tasks
FOR EACH ROW EXECUTE FUNCTION v1_task_guard();

-- Shared Task -> Milestone status reconciliation, called by AFTER trigger.
-- Internal reconciler: only the Task AFTER trigger should invoke this.
-- SECURITY DEFINER is required if the app DB role cannot UPDATE
-- milestones.status directly (per G-09.1).  REVOKE EXECUTE from PUBLIC.
CREATE FUNCTION v1_refresh_milestone(p_milestone BIGINT) RETURNS VOID
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE v_all INTEGER; v_done INTEGER; v_not_started INTEGER;
        v_next TEXT; v_previous TEXT;
BEGIN
    IF NOT EXISTS(SELECT 1 FROM milestones WHERE id=p_milestone) THEN RETURN; END IF;
    SELECT count(*),count(*) FILTER(WHERE status='completed'),
           count(*) FILTER(WHERE status='not_started')
      INTO v_all,v_done,v_not_started
      FROM tasks WHERE milestone_id=p_milestone;
    IF v_all=0 OR v_not_started=v_all THEN v_next:='not_started';
    ELSIF v_done=v_all THEN v_next:='completed';
    ELSE v_next:='in_progress'; END IF;
    v_previous:=current_setting('app.v1_milestone_sync',true);
    PERFORM set_config('app.v1_milestone_sync','on',true);
    UPDATE milestones SET status=v_next
      WHERE id=p_milestone AND status IS DISTINCT FROM v_next;
    PERFORM set_config('app.v1_milestone_sync',coalesce(v_previous,''),true);
END $$;

-- Definer trigger makes internal Milestone reconciliation possible without
-- granting the app role direct milestones.status UPDATE or v1_refresh_milestone EXECUTE.
CREATE FUNCTION v1_task_refresh_parent() RETURNS TRIGGER
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN
    IF TG_OP='UPDATE' THEN
        IF NEW.status IS NOT DISTINCT FROM OLD.status THEN RETURN NULL; END IF;
    END IF;
    PERFORM v1_refresh_milestone(
        CASE WHEN TG_OP='DELETE' THEN OLD.milestone_id ELSE NEW.milestone_id END
    );
    RETURN NULL;
END $$;
CREATE TRIGGER tr_tasks_refresh_milestone
AFTER INSERT OR UPDATE OF status OR DELETE ON tasks
FOR EACH ROW EXECUTE FUNCTION v1_task_refresh_parent();

CREATE FUNCTION v1_task_assignee_guard() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE v_task BIGINT; v_status TEXT; v_project BIGINT; v_team BIGINT;
        v_milestone BIGINT; v_member_user BIGINT; v_member_team BIGINT; v_exit BOOLEAN;
BEGIN
    v_task:=CASE WHEN TG_OP='DELETE' THEN OLD.task_id ELSE NEW.task_id END;
    -- Initial read locates the parent only; do NOT trust status until after
    -- project/milestone/task locks have been acquired (A-05).
    SELECT t.milestone_id,m.project_id INTO v_milestone,v_project
      FROM tasks t JOIN milestones m ON m.id=t.milestone_id WHERE t.id=v_task;
    IF NOT FOUND THEN
        -- A Task DELETE cascades to assignees; no synthetic unassignment.
        IF TG_OP='DELETE' THEN RETURN OLD; END IF;
        RAISE EXCEPTION 'Missing Task for assignment';
    END IF;
    PERFORM v1_lock_project(v_project);
    PERFORM 1 FROM milestones WHERE id=v_milestone FOR UPDATE;
    SELECT status INTO v_status FROM tasks WHERE id=v_task FOR UPDATE;
    IF NOT FOUND THEN
        IF TG_OP='DELETE' THEN RETURN OLD; END IF;
        RAISE EXCEPTION 'Missing Task for assignment';
    END IF;
    SELECT team_id INTO v_team FROM projects WHERE id=v_project;
    v_exit:=(coalesce(current_setting('app.v1_member_exit',true),'')='on');
    IF TG_OP='UPDATE' THEN
        RAISE EXCEPTION 'Task assignment rows are immutable; delete/reinsert';
    END IF;
    IF TG_OP='INSERT' THEN
        IF NOT v1_is_team_leader(v_team,v1_actor_id()) THEN
            RAISE EXCEPTION 'Only leader may assign Task';
        END IF;
        IF v_status='completed' OR v1_has_first_evaluation(v_project) THEN
            RAISE EXCEPTION 'Task assignments locked';
        END IF;
        SELECT tm.team_id,tm.user_id INTO v_member_team,v_member_user
          FROM team_members tm WHERE tm.id=NEW.team_member_id;
        IF v_member_team IS DISTINCT FROM v_team THEN
            RAISE EXCEPTION 'Assignee must be current member of same team';
        END IF;
        NEW.assigned_at:=NOW();
        RETURN NEW;
    END IF;
    IF v_exit THEN
        -- Only the controlled EXIT operation may legitimately use this path.
        -- Raw DELETE must be denied to app DB role (A-02).
        -- A verified exit/expulsion workflow must remove assignees before
        -- deleting the member; this context must not be set by raw table DML.
        IF NOT (v1_is_team_leader(v_team,v1_actor_id()) OR
            EXISTS (SELECT 1 FROM team_members tm
                     WHERE tm.id=OLD.team_member_id AND tm.user_id=v1_actor_id())) THEN
            RAISE EXCEPTION 'Unauthorized member-exit cleanup';
        END IF;
    ELSE
        IF NOT v1_is_team_leader(v_team,v1_actor_id()) THEN
            RAISE EXCEPTION 'Only leader may unassign Task';
        END IF;
        IF v_status='completed' OR v1_has_first_evaluation(v_project) THEN
            RAISE EXCEPTION 'Unassignment locked';
        END IF;
    END IF;
    RETURN OLD;
END $$;
CREATE TRIGGER tr_task_assignee_guard BEFORE INSERT OR UPDATE OR DELETE
ON task_assignees FOR EACH ROW EXECUTE FUNCTION v1_task_assignee_guard();

-- Writes history only when an assignee row is actually removed while its
-- Task still exists. The function owner needs INSERT privilege on history.
CREATE FUNCTION v1_record_unassignment() RETURNS TRIGGER
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE v_user BIGINT;
BEGIN
    IF NOT EXISTS(SELECT 1 FROM public.tasks WHERE id=OLD.task_id) THEN
        RETURN NULL;  -- Task deletion cascade, not a user unassignment.
    END IF;
    SELECT user_id INTO v_user FROM public.team_members WHERE id=OLD.team_member_id;
    IF v_user IS NULL THEN RAISE EXCEPTION 'Assignee member missing at removal'; END IF;
    INSERT INTO public.task_assignment_history
        (task_id,user_id,assigned_at,unassigned_at)
    VALUES (OLD.task_id,v_user,OLD.assigned_at,NOW());
    RETURN NULL;
END $$;
CREATE TRIGGER tr_task_assignee_removed_history
AFTER DELETE ON task_assignees FOR EACH ROW
EXECUTE FUNCTION v1_record_unassignment();

-- A-04/A-05: controlled operations.  These enforce parent-row locks BEFORE
-- modifying assignee/member rows.  The app DB role must not receive raw DELETE
-- on task_assignees; grant EXECUTE on these entrypoints only after validating
-- the FastAPI -> PostgreSQL actor and deployment privileges (A-02).
CREATE FUNCTION v1_assign_task(p_task BIGINT,p_member BIGINT) RETURNS BIGINT
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE v_project BIGINT; v_milestone BIGINT; v_id BIGINT;
BEGIN
    SELECT t.milestone_id,m.project_id INTO v_milestone,v_project
      FROM public.tasks t JOIN public.milestones m ON m.id=t.milestone_id
     WHERE t.id=p_task;
    IF NOT FOUND THEN RAISE EXCEPTION 'Task not found'; END IF;
    PERFORM public.v1_lock_project(v_project);
    PERFORM 1 FROM public.milestones WHERE id=v_milestone FOR UPDATE;
    PERFORM 1 FROM public.tasks WHERE id=p_task FOR UPDATE;
    INSERT INTO public.task_assignees(task_id,team_member_id)
    VALUES(p_task,p_member) RETURNING id INTO v_id;
    RETURN v_id;
END $$;

CREATE FUNCTION v1_unassign_task(p_task BIGINT,p_member BIGINT) RETURNS VOID
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE v_project BIGINT; v_milestone BIGINT;
BEGIN
    SELECT t.milestone_id,m.project_id INTO v_milestone,v_project
      FROM public.tasks t JOIN public.milestones m ON m.id=t.milestone_id
     WHERE t.id=p_task;
    IF NOT FOUND THEN RAISE EXCEPTION 'Task not found'; END IF;
    PERFORM public.v1_lock_project(v_project);
    PERFORM 1 FROM public.milestones WHERE id=v_milestone FOR UPDATE;
    PERFORM 1 FROM public.tasks WHERE id=p_task FOR UPDATE;
    DELETE FROM public.task_assignees
     WHERE task_id=p_task AND team_member_id=p_member;
    IF NOT FOUND THEN RAISE EXCEPTION 'Current task assignment not found'; END IF;
END $$;

-- Atomic membership exit / expulsion for existing nonleader members.
-- C-02: no in-progress Task may lose its last assignee.  Completed and
-- not-started Tasks may become unassigned due to this workflow.
-- G-11.6: this is the ONLY permitted assignee-cleanup exception after scoring.
CREATE FUNCTION v1_exit_team_member(p_team_member BIGINT) RETURNS VOID
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE v_team BIGINT; v_project BIGINT; v_user BIGINT; v_role TEXT;
        v_actor BIGINT; v_milestone BIGINT; v_task BIGINT;
        v_previous TEXT;
BEGIN
    SELECT team_id INTO v_team FROM public.team_members WHERE id=p_team_member;
    IF NOT FOUND THEN RAISE EXCEPTION 'Team membership not found'; END IF;
    PERFORM 1 FROM public.teams WHERE id=v_team FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Team not found'; END IF;
    SELECT id INTO v_project FROM public.projects WHERE team_id=v_team;
    IF v_project IS NOT NULL THEN PERFORM public.v1_lock_project(v_project); END IF;
    SELECT user_id,role INTO v_user,v_role
      FROM public.team_members WHERE id=p_team_member AND team_id=v_team FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Membership changed concurrently'; END IF;
    v_actor:=public.v1_actor_id();
    IF v_role='leader' THEN RAISE EXCEPTION 'Transfer leadership before leaving'; END IF;
    IF v_actor<>v_user AND NOT public.v1_is_team_leader(v_team,v_actor) THEN
        RAISE EXCEPTION 'Only member or current leader may remove membership'
          USING ERRCODE='42501';
    END IF;
    -- Parent lock order is project -> milestones ascending -> tasks ascending.
    FOR v_milestone IN
        SELECT DISTINCT t.milestone_id
          FROM public.task_assignees a
          JOIN public.tasks t ON t.id=a.task_id
         WHERE a.team_member_id=p_team_member ORDER BY t.milestone_id
    LOOP
        PERFORM 1 FROM public.milestones WHERE id=v_milestone FOR UPDATE;
    END LOOP;
    FOR v_task IN
        SELECT t.id FROM public.task_assignees a
        JOIN public.tasks t ON t.id=a.task_id
        WHERE a.team_member_id=p_team_member ORDER BY t.id
    LOOP
        PERFORM 1 FROM public.tasks WHERE id=v_task FOR UPDATE;
        IF (SELECT status FROM public.tasks WHERE id=v_task)='in_progress'
           AND NOT EXISTS (
               SELECT 1 FROM public.task_assignees a
               WHERE a.task_id=v_task AND a.team_member_id<>p_team_member
           ) THEN
            RAISE EXCEPTION 'Member exit would leave in-progress Task % unassigned',v_task;
        END IF;
    END LOOP;
    v_previous:=current_setting('app.v1_member_exit',true);
    PERFORM set_config('app.v1_member_exit','on',true);
    DELETE FROM public.task_assignees WHERE team_member_id=p_team_member;
    DELETE FROM public.team_members WHERE id=p_team_member;
    PERFORM set_config('app.v1_member_exit',coalesce(v_previous,''),true);
END $$;



-- ==========================================================================
-- A-05: Parent-first controlled write entrypoints (DRAFT; NOT EXECUTED).
-- Only the trusted FastAPI database role may EXECUTE these.  The app role
-- must NOT receive the underlying direct UPDATE/DELETE/INSERT DML grants.
-- These functions reuse existing business triggers; they do NOT add rules.
-- Lookup queries below are locators only; the parent is locked before write.
-- All operations run in the caller's current transaction.  They do not COMMIT.
-- ==========================================================================
CREATE FUNCTION v1_update_team_metadata(p_team BIGINT,p_name TEXT,p_description TEXT)
RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE v_project BIGINT;
BEGIN
    PERFORM 1 FROM public.teams WHERE id=p_team FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Team not found'; END IF;
    SELECT id INTO v_project FROM public.projects WHERE team_id=p_team;
    IF v_project IS NOT NULL THEN PERFORM public.v1_lock_project(v_project); END IF;
    UPDATE public.teams SET name=p_name, description=p_description WHERE id=p_team;
END $$;

CREATE FUNCTION v1_delete_team(p_team BIGINT)
RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN
    PERFORM 1 FROM public.teams WHERE id=p_team FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Team not found'; END IF;
    -- The existing team guard and projects.team_id RESTRICT are authoritative.
    DELETE FROM public.teams WHERE id=p_team;
END $$;

CREATE FUNCTION v1_update_project_metadata(p_project BIGINT,p_name TEXT,p_description TEXT)
RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE v_team BIGINT;
BEGIN
    SELECT team_id INTO v_team FROM public.projects WHERE id=p_project;
    IF NOT FOUND THEN RAISE EXCEPTION 'Project not found'; END IF;
    PERFORM 1 FROM public.teams WHERE id=v_team FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Team not found'; END IF;
    PERFORM public.v1_lock_project(p_project);
    UPDATE public.projects SET name=p_name, description=p_description WHERE id=p_project;
END $$;

CREATE FUNCTION v1_resolve_invitation(p_invitation BIGINT,p_status TEXT)
RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE v_project BIGINT;
BEGIN
    SELECT project_id INTO v_project FROM public.advisor_invitations WHERE id=p_invitation;
    IF NOT FOUND THEN RAISE EXCEPTION 'Invitation not found'; END IF;
    PERFORM public.v1_lock_project(v_project);
    PERFORM 1 FROM public.advisor_invitations WHERE id=p_invitation FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Invitation no longer exists'; END IF;
    UPDATE public.advisor_invitations SET status=p_status WHERE id=p_invitation;
END $$;

CREATE FUNCTION v1_review_submission(p_submission BIGINT,p_status TEXT,p_comment TEXT)
RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE v_project BIGINT;
BEGIN
    SELECT project_id INTO v_project FROM public.project_submissions WHERE id=p_submission;
    IF NOT FOUND THEN RAISE EXCEPTION 'Submission not found'; END IF;
    PERFORM public.v1_lock_project(v_project);
    PERFORM 1 FROM public.project_submissions WHERE id=p_submission FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Submission no longer exists'; END IF;
    UPDATE public.project_submissions SET status=p_status,review_comment=p_comment
    WHERE id=p_submission;
END $$;

CREATE FUNCTION v1_create_milestone(p_project BIGINT,p_name TEXT,p_description TEXT,p_due DATE)
RETURNS BIGINT LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE v_id BIGINT;
BEGIN
    PERFORM public.v1_lock_project(p_project);
    INSERT INTO public.milestones(project_id,name,description,due_date,created_by)
    VALUES(p_project,p_name,p_description,p_due,public.v1_actor_id()) RETURNING id INTO v_id;
    RETURN v_id;
END $$;

CREATE FUNCTION v1_update_milestone(p_milestone BIGINT,p_name TEXT,p_description TEXT,p_due DATE)
RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE v_project BIGINT;
BEGIN
    SELECT project_id INTO v_project FROM public.milestones WHERE id=p_milestone;
    IF NOT FOUND THEN RAISE EXCEPTION 'Milestone not found'; END IF;
    PERFORM public.v1_lock_project(v_project);
    PERFORM 1 FROM public.milestones WHERE id=p_milestone FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Milestone no longer exists'; END IF;
    UPDATE public.milestones
       SET name=p_name,description=p_description,due_date=p_due WHERE id=p_milestone;
END $$;

CREATE FUNCTION v1_delete_milestone(p_milestone BIGINT)
RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE v_project BIGINT;
BEGIN
    SELECT project_id INTO v_project FROM public.milestones WHERE id=p_milestone;
    IF NOT FOUND THEN RAISE EXCEPTION 'Milestone not found'; END IF;
    PERFORM public.v1_lock_project(v_project);
    PERFORM 1 FROM public.milestones WHERE id=p_milestone FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Milestone no longer exists'; END IF;
    DELETE FROM public.milestones WHERE id=p_milestone;
END $$;

CREATE FUNCTION v1_create_task(p_milestone BIGINT,p_name TEXT,p_description TEXT,p_due DATE)
RETURNS BIGINT LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE v_project BIGINT; v_id BIGINT;
BEGIN
    SELECT project_id INTO v_project FROM public.milestones WHERE id=p_milestone;
    IF NOT FOUND THEN RAISE EXCEPTION 'Milestone not found'; END IF;
    PERFORM public.v1_lock_project(v_project);
    PERFORM 1 FROM public.milestones WHERE id=p_milestone FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Milestone no longer exists'; END IF;
    INSERT INTO public.tasks(milestone_id,name,description,due_date,created_by)
    VALUES(p_milestone,p_name,p_description,p_due,public.v1_actor_id()) RETURNING id INTO v_id;
    RETURN v_id;
END $$;

CREATE FUNCTION v1_update_task_metadata(p_task BIGINT,p_name TEXT,p_description TEXT,p_due DATE)
RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE v_project BIGINT; v_milestone BIGINT;
BEGIN
    SELECT t.milestone_id,m.project_id INTO v_milestone,v_project
      FROM public.tasks t JOIN public.milestones m ON m.id=t.milestone_id
      WHERE t.id=p_task;
    IF NOT FOUND THEN RAISE EXCEPTION 'Task not found'; END IF;
    PERFORM public.v1_lock_project(v_project);
    PERFORM 1 FROM public.milestones WHERE id=v_milestone FOR UPDATE;
    PERFORM 1 FROM public.tasks WHERE id=p_task FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Task no longer exists'; END IF;
    UPDATE public.tasks SET name=p_name,description=p_description,due_date=p_due
    WHERE id=p_task;
END $$;

CREATE FUNCTION v1_set_task_status(p_task BIGINT,p_status TEXT)
RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE v_project BIGINT; v_milestone BIGINT;
BEGIN
    SELECT t.milestone_id,m.project_id INTO v_milestone,v_project
      FROM public.tasks t JOIN public.milestones m ON m.id=t.milestone_id
      WHERE t.id=p_task;
    IF NOT FOUND THEN RAISE EXCEPTION 'Task not found'; END IF;
    PERFORM public.v1_lock_project(v_project);
    PERFORM 1 FROM public.milestones WHERE id=v_milestone FOR UPDATE;
    PERFORM 1 FROM public.tasks WHERE id=p_task FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Task no longer exists'; END IF;
    UPDATE public.tasks SET status=p_status WHERE id=p_task;
END $$;

CREATE FUNCTION v1_delete_task(p_task BIGINT)
RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE v_project BIGINT; v_milestone BIGINT;
BEGIN
    SELECT t.milestone_id,m.project_id INTO v_milestone,v_project
      FROM public.tasks t JOIN public.milestones m ON m.id=t.milestone_id
      WHERE t.id=p_task;
    IF NOT FOUND THEN RAISE EXCEPTION 'Task not found'; END IF;
    PERFORM public.v1_lock_project(v_project);
    PERFORM 1 FROM public.milestones WHERE id=v_milestone FOR UPDATE;
    PERFORM 1 FROM public.tasks WHERE id=p_task FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Task no longer exists'; END IF;
    DELETE FROM public.tasks WHERE id=p_task;
END $$;

CREATE FUNCTION v1_appoint_committee(p_project BIGINT,p_advisor BIGINT)
RETURNS BIGINT LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE v_id BIGINT;
BEGIN
    PERFORM public.v1_lock_project(p_project);
    INSERT INTO public.committee_assignments(project_id,advisor_id,assigned_by)
    VALUES(p_project,p_advisor,public.v1_actor_id()) RETURNING id INTO v_id;
    RETURN v_id;
END $$;

CREATE FUNCTION v1_replace_committee(p_assignment BIGINT,p_advisor BIGINT)
RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE v_project BIGINT;
BEGIN
    SELECT project_id INTO v_project FROM public.committee_assignments WHERE id=p_assignment;
    IF NOT FOUND THEN RAISE EXCEPTION 'Committee assignment not found'; END IF;
    PERFORM public.v1_lock_project(v_project);
    PERFORM 1 FROM public.committee_assignments WHERE id=p_assignment FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Committee assignment no longer exists'; END IF;
    UPDATE public.committee_assignments SET advisor_id=p_advisor WHERE id=p_assignment;
END $$;

CREATE FUNCTION v1_remove_committee(p_assignment BIGINT)
RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE v_project BIGINT;
BEGIN
    SELECT project_id INTO v_project FROM public.committee_assignments WHERE id=p_assignment;
    IF NOT FOUND THEN RAISE EXCEPTION 'Committee assignment not found'; END IF;
    PERFORM public.v1_lock_project(v_project);
    PERFORM 1 FROM public.committee_assignments WHERE id=p_assignment FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Committee assignment no longer exists'; END IF;
    DELETE FROM public.committee_assignments WHERE id=p_assignment;
END $$;

CREATE FUNCTION v1_cast_vote(p_submission BIGINT,p_assignment BIGINT,p_vote TEXT,p_comment TEXT)
RETURNS BIGINT LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE v_project BIGINT; v_id BIGINT;
BEGIN
    SELECT project_id INTO v_project FROM public.project_submissions WHERE id=p_submission;
    IF NOT FOUND THEN RAISE EXCEPTION 'Submission not found'; END IF;
    PERFORM public.v1_lock_project(v_project);
    INSERT INTO public.committee_topic_votes(submission_id,committee_assignment_id,vote,comment)
    VALUES(p_submission,p_assignment,p_vote,p_comment) RETURNING id INTO v_id;
    RETURN v_id;
END $$;

CREATE FUNCTION v1_record_evaluation(p_assignment BIGINT,p_score INTEGER,p_comment TEXT)
RETURNS BIGINT LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE v_project BIGINT; v_id BIGINT;
BEGIN
    SELECT project_id INTO v_project FROM public.committee_assignments WHERE id=p_assignment;
    IF NOT FOUND THEN RAISE EXCEPTION 'Committee assignment not found'; END IF;
    PERFORM public.v1_lock_project(v_project);
    INSERT INTO public.committee_evaluations(committee_assignment_id,score,comment)
    VALUES(p_assignment,p_score,p_comment) RETURNING id INTO v_id;
    RETURN v_id;
END $$;

-- In-progress Tasks must never have zero assignees at COMMIT.  Completed
-- Tasks may reach zero after team-member exit (C-02), but not at transition
-- into completed (enforced by v1_task_guard above).
CREATE FUNCTION v1_in_progress_has_assignee() RETURNS TRIGGER LANGUAGE plpgsql AS $$
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
CREATE CONSTRAINT TRIGGER c_task_active_assignee_from_task
AFTER INSERT OR UPDATE ON tasks DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION v1_in_progress_has_assignee();
CREATE CONSTRAINT TRIGGER c_task_active_assignee_on_remove
AFTER DELETE ON task_assignees DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION v1_in_progress_has_assignee();

-- History is append-only. On Task deletion it is removed by FK CASCADE.
-- Do not install unconditional DELETE-blocking triggers on history because
-- that would interfere with the approved ON DELETE CASCADE policy.
CREATE FUNCTION v1_history_update_forbidden() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Assignment history must not be updated directly';
END $$;
CREATE TRIGGER tr_history_no_update BEFORE UPDATE ON task_assignment_history
FOR EACH ROW EXECUTE FUNCTION v1_history_update_forbidden();

-- Restrict default PUBLIC EXECUTE for these V1 functions in this same
-- transaction.  Pin all V1 functions to a trusted, consistent search_path;
-- public must NOT be writable by untrusted roles before deploying this draft.
-- Explicit EXECUTE grants to the approved app role are part of the separate
-- deployment privilege plan; no app role name was assumed in this draft.
DO $v1_privileges$
DECLARE r RECORD;
BEGIN
    FOR r IN
        SELECT p.oid::regprocedure AS signature
          FROM pg_proc p
          JOIN pg_namespace n ON n.oid=p.pronamespace
         WHERE n.nspname='public'
           AND p.proname LIKE 'v1\_%' ESCAPE '\'
    LOOP
        EXECUTE format('ALTER FUNCTION %s SET search_path = pg_catalog, public, pg_temp', r.signature);
        EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC', r.signature);
    END LOOP;
END $v1_privileges$;

-- Deployment/security notes (mandatory for correctness, not extra schema):
-- 1. Assign distinct DB owner/app roles, deny direct INSERT/UPDATE/DELETE on
--    task_assignment_history; owner of SECURITY DEFINER trigger inserts.
-- 2. DENY direct role UPDATE, milestones.status UPDATE, and direct
--    task_assignees DELETE to the app role. Grant EXECUTE only to approved
--    controlled operations; internal v1_refresh_milestone must not be callable.
--    Trust FastAPI authentication, not client-provided custom GUC values.
-- 3. SET LOCAL app.actor_user_id is NOT an authentication token: FastAPI
--    verifies identity; DB functions validate current role/relationships.
-- 4. G-12 read authorization and API response filtering are enforced at
--    FastAPI, not by PostgreSQL RLS in V1.
-- 5. R-01 (confirmed): no Project DELETE API, no app DELETE privilege on
--    projects, and BEFORE DELETE guard blocks deletes even for childless projects.
-- 6. This draft's business triggers require integration/security/concurrency
--    validation BEFORE deployment; see review companion file.


-- V1 least-privilege application grants.

SELECT pg_catalog.set_config('v1.deploy.app_role', 'project_app', true);
SELECT pg_catalog.set_config('v1.deploy.owner_role', 'project_owner', true);
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
REVOKE CREATE ON SCHEMA public FROM project_app;
GRANT USAGE ON SCHEMA public TO project_app;

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
FROM project_app;

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
TO project_app;

-- INSERT of new root/new append-only rows: guards lock parents before INSERT.
GRANT INSERT ON TABLE
    public.teams, public.team_members, public.projects,
    public.advisor_invitations, public.project_submissions, public.project_submission_files
TO project_app;
-- NOT GRANTED: direct UPDATE/DELETE existing teams, projects, invitations,
-- submissions, committee assignments, milestones, tasks or assignees.
-- NOT GRANTED: committee vote/evaluation INSERT (controlled functions only).
-- NOT GRANTED: any direct modification of task_assignment_history/users.
-- R-01=A: NEVER direct DELETE on projects (even when childless).
REVOKE DELETE ON TABLE public.projects FROM PUBLIC;
REVOKE DELETE ON TABLE public.projects FROM project_app;

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
TO project_app;

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
TO project_app;

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

-- Isolated Auth storage and grants.
SET LOCAL search_path = pg_catalog, pg_temp;
-- Auth extension REVIEW DRAFT. Prepared for review only; not executed.
-- Entry point for a future approved rollback-only rehearsal using psql.
-- Database: postgres. Effective role: project_owner.
-- Includes 002_auth_rbac_review.sql in this transaction and always ROLLBACKs.
-- Does not alter V1 tables/functions/triggers or create/alter database roles.



DO $preflight$
BEGIN
    IF current_database() <> 'postgres' THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
            MESSAGE = 'Auth review is restricted to the approved test database';
    END IF;
    IF current_user <> 'project_owner' THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
            MESSAGE = 'Auth review requires the reviewed project_owner role';
    END IF;
    IF NOT pg_catalog.has_database_privilege(current_user, current_database(), 'CREATE') THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
            MESSAGE = 'Owner needs reviewed CREATE privilege on the test database to create spms_auth schema';
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
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_namespace WHERE nspname = 'spms_auth') THEN
        RAISE EXCEPTION 'Auth schema already exists; review a separate migration';
    END IF;
END
$preflight$;

CREATE SCHEMA spms_auth AUTHORIZATION project_owner;
REVOKE ALL ON SCHEMA spms_auth FROM PUBLIC, project_app;

CREATE TABLE spms_auth.credentials (
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
CREATE TABLE spms_auth.sessions (
    token_hash BYTEA PRIMARY KEY,
    user_id BIGINT NOT NULL
        REFERENCES spms_auth.credentials(user_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    expires_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_auth_session_token_hash CHECK (
        pg_catalog.octet_length(token_hash) = 32
    ),
    CONSTRAINT ck_auth_session_lifetime CHECK (expires_at > created_at)
);

CREATE INDEX ix_auth_sessions_user_id ON spms_auth.sessions(user_id);
CREATE INDEX ix_auth_sessions_expires_at ON spms_auth.sessions(expires_at);

REVOKE ALL ON TABLE spms_auth.credentials, spms_auth.sessions FROM PUBLIC, project_app;
SET LOCAL auth_review.storage_ready = '001_auth_storage_review';





-- Auth RBAC REVIEW DRAFT. Included by 001_auth_storage_review.sql only.
-- No transaction boundary here: the entry point owns BEGIN and ROLLBACK.
-- These proposed grants are NOT installed merely by preparing this file.


DO $preflight$
BEGIN
    IF current_database() <> 'postgres'
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
        WHERE n.nspname = 'spms_auth'
          AND pg_catalog.pg_get_userbyid(n.nspowner) = 'project_owner'
    ) OR (
        SELECT pg_catalog.count(*) FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'spms_auth' AND c.relname IN ('credentials', 'sessions')
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
CREATE FUNCTION spms_auth.register_student(
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

    INSERT INTO spms_auth.credentials(user_id, password_hash)
    VALUES (v_user_id, p_password_hash);

    RETURN v_user_id;
END
$function$;

-- Credential hash is available only through this lookup to the trusted backend.
-- It is private internal data, never an HTTP response. The backend must verify
-- the hash and return the same login failure for unknown email/wrong password.
CREATE FUNCTION spms_auth.lookup_credentials(p_email TEXT)
RETURNS TABLE(user_id BIGINT, password_hash TEXT)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $function$
    SELECT c.user_id, c.password_hash
    FROM spms_auth.credentials AS c
    JOIN public.users AS u ON u.id = c.user_id
    WHERE u.email = pg_catalog.lower(
        pg_catalog.btrim(p_email, E' \t\n\r\f\v')
    );
$function$;

REVOKE ALL ON FUNCTION spms_auth.register_student(TEXT, TEXT, TEXT)
    FROM PUBLIC, project_app;
REVOKE ALL ON FUNCTION spms_auth.lookup_credentials(TEXT)
    FROM PUBLIC, project_app;
REVOKE ALL ON TABLE spms_auth.credentials, spms_auth.sessions FROM PUBLIC, project_app;
REVOKE ALL ON SCHEMA spms_auth FROM PUBLIC, project_app;

GRANT USAGE ON SCHEMA spms_auth TO project_app;
GRANT EXECUTE ON FUNCTION spms_auth.register_student(TEXT, TEXT, TEXT),
    spms_auth.lookup_credentials(TEXT) TO project_app;

-- Backend generates raw session tokens, stores their digest only, and scopes
-- SELECT/DELETE by the session being authenticated. G-12 filtering is still in
-- the backend, as in V1; these grants do not provide row-level authorization.
GRANT SELECT, DELETE ON TABLE spms_auth.sessions TO project_app;
GRANT INSERT (token_hash, user_id, expires_at) ON TABLE spms_auth.sessions TO project_app;

-- No direct credentials SELECT/INSERT/UPDATE/DELETE, no users write grants,
-- no schema CREATE, no session UPDATE/TRUNCATE, no role creation/membership.
DO $postflight$
BEGIN
    IF pg_catalog.has_any_column_privilege('project_app', 'spms_auth.credentials', 'SELECT')
       OR pg_catalog.has_any_column_privilege('project_app', 'spms_auth.credentials', 'INSERT')
       OR pg_catalog.has_any_column_privilege('project_app', 'spms_auth.credentials', 'UPDATE')
       OR pg_catalog.has_table_privilege('project_app', 'spms_auth.credentials', 'DELETE')
       OR pg_catalog.has_schema_privilege('project_app', 'spms_auth', 'CREATE')
       OR pg_catalog.has_any_column_privilege('project_app', 'public.users', 'INSERT')
       OR pg_catalog.has_any_column_privilege('project_app', 'public.users', 'UPDATE')
       OR pg_catalog.has_table_privilege('project_app', 'public.users', 'DELETE')
       OR pg_catalog.has_column_privilege('project_app', 'spms_auth.sessions', 'created_at', 'INSERT')
       OR pg_catalog.has_any_column_privilege('project_app', 'spms_auth.sessions', 'UPDATE')
       OR pg_catalog.has_table_privilege('project_app', 'spms_auth.sessions', 'TRUNCATE') THEN
        RAISE EXCEPTION 'Auth privilege review found unexpected effective access';
    END IF;
    IF NOT pg_catalog.has_schema_privilege('project_app', 'spms_auth', 'USAGE')
       OR NOT pg_catalog.has_function_privilege(
           'project_app', 'spms_auth.register_student(text,text,text)', 'EXECUTE')
       OR NOT pg_catalog.has_function_privilege(
           'project_app', 'spms_auth.lookup_credentials(text)', 'EXECUTE')
       OR NOT pg_catalog.has_table_privilege('project_app', 'spms_auth.sessions', 'SELECT')
       OR NOT pg_catalog.has_table_privilege('project_app', 'spms_auth.sessions', 'DELETE')
       OR NOT pg_catalog.has_column_privilege('project_app', 'spms_auth.sessions', 'token_hash', 'INSERT')
       OR NOT pg_catalog.has_column_privilege('project_app', 'spms_auth.sessions', 'user_id', 'INSERT')
       OR NOT pg_catalog.has_column_privilege('project_app', 'spms_auth.sessions', 'expires_at', 'INSERT') THEN
        RAISE EXCEPTION 'Auth privilege review found missing intended access';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_proc p
        JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(p.proacl, pg_catalog.acldefault('f', p.proowner))
        ) AS a
        WHERE n.nspname = 'spms_auth' AND a.grantee = 0
          AND a.privilege_type = 'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'PUBLIC must not execute Auth functions';
    END IF;
END
$postflight$;


RESET ROLE;
REVOKE CREATE ON DATABASE postgres FROM project_owner;

DO $supabase_postflight$
DECLARE
    v_tables INTEGER;
    v_fks INTEGER;
    v_functions INTEGER;
    v_triggers INTEGER;
    v_auth_tables INTEGER;
BEGIN
    SELECT count(*) INTO v_tables
      FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public' AND c.relkind = 'r'
       AND c.relname IN ('users','teams','team_members','projects','advisor_invitations',
          'project_submissions','project_submission_files','committee_assignments',
          'committee_topic_votes','committee_evaluations','milestones','tasks',
          'task_assignees','task_assignment_history');
    SELECT count(*) INTO v_fks
      FROM pg_catalog.pg_constraint x JOIN pg_catalog.pg_class c ON c.oid = x.conrelid
      JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public' AND x.contype = 'f'
       AND c.relname IN ('users','teams','team_members','projects','advisor_invitations',
          'project_submissions','project_submission_files','committee_assignments',
          'committee_topic_votes','committee_evaluations','milestones','tasks',
          'task_assignees','task_assignment_history');
    SELECT count(*) INTO v_functions
      FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
     WHERE n.nspname = 'public' AND p.proname LIKE 'v1\_%' ESCAPE '\';
    SELECT count(*) INTO v_triggers
      FROM pg_catalog.pg_trigger t JOIN pg_catalog.pg_class c ON c.oid = t.tgrelid
      JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public' AND NOT t.tgisinternal
       AND c.relname IN ('users','teams','team_members','projects','advisor_invitations',
          'project_submissions','project_submission_files','committee_assignments',
          'committee_topic_votes','committee_evaluations','milestones','tasks',
          'task_assignees','task_assignment_history');
    SELECT count(*) INTO v_auth_tables
      FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'spms_auth' AND c.relkind = 'r'
       AND c.relname IN ('credentials','sessions');
    IF (v_tables, v_fks, v_functions, v_triggers, v_auth_tables)
       IS DISTINCT FROM (14, 28, 52, 24, 2) THEN
        RAISE EXCEPTION 'Bootstrap object-count check failed: tables %, FKs %, functions %, triggers %, auth tables %',
            v_tables, v_fks, v_functions, v_triggers, v_auth_tables;
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname IN ('public','spms_auth')
          AND c.relname IN ('users','teams','team_members','projects','advisor_invitations',
            'project_submissions','project_submission_files','committee_assignments',
            'committee_topic_votes','committee_evaluations','milestones','tasks',
            'task_assignees','task_assignment_history','credentials','sessions')
          AND pg_catalog.pg_get_userbyid(c.relowner) <> 'project_owner'
    ) THEN
        RAISE EXCEPTION 'Bootstrap ownership check failed; expected project_owner';
    END IF;
END
$supabase_postflight$;

SELECT 'PASS: fresh Supabase schema installed' AS status,
       14 AS public_tables, 28 AS foreign_keys, 52 AS workflow_functions,
       24 AS triggers, 2 AS auth_tables;
COMMIT;
