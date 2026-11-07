"use client";

import { useCallback, useEffect, useState } from "react";
import { currentTeam, TeamApiError, type CurrentTeam } from "@/features/teams/api";
import { currentProject, ProjectApiError, projectErrorMessage, type Project } from "./api";

type State = { status: "loading" } | { status: "unauthenticated" } | { status: "forbidden" } | { status: "no-team" }
  | { status: "empty"; team: CurrentTeam } | { status: "ready"; team: CurrentTeam; project: Project }
  | { status: "error"; message: string };

export function useCurrentProject(actorId?: string) {
  const [record, setRecord] = useState<{ owner?: string; value: State }>({ value: { status: "loading" } });
  const [revision, setRevision] = useState(0);
  const refresh = useCallback(() => {
    setRecord({ owner: actorId, value: { status: "loading" } }); setRevision((value) => value + 1);
  }, [actorId]);
  const acceptCreated = useCallback((team: CurrentTeam, project: Project) => {
    setRecord({ owner: actorId, value: { status: "ready", team, project } });
  }, [actorId]);
  useEffect(() => {
    if (!actorId) return;
    const controller = new AbortController();
    async function load(): Promise<State> {
      const team = await currentTeam(controller.signal);
      if (!team) return { status: "no-team" };
      const project = await currentProject(controller.signal);
      if (!project) return { status: "empty", team };
      if (project.team_id !== team.id) throw new ProjectApiError(502, "INVALID_RESPONSE");
      return { status: "ready", team, project };
    }
    void load().then((value) => {
      if (!controller.signal.aborted) setRecord({ owner: actorId, value });
    }).catch((cause: unknown) => {
      if (controller.signal.aborted) return;
      const known = cause instanceof ProjectApiError || cause instanceof TeamApiError;
      const value: State = known && cause.status === 401 ? { status: "unauthenticated" }
        : known && cause.status === 403 ? { status: "forbidden" }
          : known && cause.status === 404 && cause.code === "TEAM_NOT_FOUND" ? { status: "no-team" }
            : { status: "error", message: projectErrorMessage(cause) };
      setRecord({ owner: actorId, value });
    });
    return () => controller.abort();
  }, [actorId, revision]);
  const state: State = !actorId || record.owner !== actorId ? { status: "loading" } : record.value;
  return { state, refresh, acceptCreated };
}
