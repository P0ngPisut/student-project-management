"use client";

import { useCallback, useEffect, useState } from "react";
import { currentTeam, TeamApiError, teamErrorMessage, type CreatedTeam, type CurrentTeam } from "./api";

type TeamState = { status: "loading" } | { status: "empty" } | { status: "unauthenticated" }
  | { status: "forbidden" } | { status: "ready"; team: CurrentTeam } | { status: "error"; message: string };
type RecordState = { owner?: string; value: TeamState };

export function useCurrentTeam(actorId?: string) {
  const [record, setRecord] = useState<RecordState>({ value: { status: "loading" } });
  const [revision, setRevision] = useState(0);
  const refresh = useCallback(() => {
    setRecord({ owner: actorId, value: { status: "loading" } });
    setRevision((value) => value + 1);
  }, [actorId]);
  const acceptCreated = useCallback((team: CreatedTeam) => {
    setRecord({ owner: actorId, value: { status: "ready", team: {
      id: team.id, name: team.name, description: team.description,
      membership: { id: team.members[0].id, role: team.members[0].role },
    } } });
  }, [actorId]);
  useEffect(() => {
    if (!actorId) return;
    const controller = new AbortController();
    void currentTeam(controller.signal).then((team) => {
      if (!controller.signal.aborted) setRecord({ owner: actorId, value: team ? { status: "ready", team } : { status: "empty" } });
    }).catch((error: unknown) => {
      if (controller.signal.aborted) return;
      const value: TeamState = error instanceof TeamApiError && error.status === 401 ? { status: "unauthenticated" }
        : error instanceof TeamApiError && error.status === 403 ? { status: "forbidden" }
          : { status: "error", message: teamErrorMessage(error) };
      setRecord({ owner: actorId, value });
    });
    return () => controller.abort();
  }, [actorId, revision]);
  const state: TeamState = !actorId || record.owner !== actorId ? { status: "loading" } : record.value;
  return { state, refresh, acceptCreated };
}
