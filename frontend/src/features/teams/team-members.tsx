"use client";

import { useCallback, useEffect, useState } from "react";
import { currentMembers, TeamApiError, teamErrorMessage, type TeamMember } from "./api";
import { MemberAddForm } from "./member-add-form";
import styles from "./teams.module.css";

type State = { status: "loading" } | { status: "error"; message: string } | { status: "ready"; members: TeamMember[] };

export function TeamMembers({ actorId, onUnauthenticated, onTeamChanged }: {
  actorId: string; onUnauthenticated: () => void; onTeamChanged: () => void;
}) {
  const [state, setState] = useState<State>({ status: "loading" });
  const [revision, setRevision] = useState(0);
  const [notice, setNotice] = useState("");
  const refresh = useCallback(() => {
    setState({ status: "loading" }); setRevision((value) => value + 1);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    void currentMembers(controller.signal).then((members) => {
      if (controller.signal.aborted) return;
      if (!members.some((member) => member.user_id === actorId)) throw new TeamApiError(502, "INVALID_RESPONSE");
      setState({ status: "ready", members });
    }).catch((cause: unknown) => {
      if (controller.signal.aborted) return;
      if (cause instanceof TeamApiError && cause.status === 401) { onUnauthenticated(); return; }
      if (cause instanceof TeamApiError && [403, 404].includes(cause.status)
        && ["TEAM_NOT_FOUND", "TEAM_ACCESS_FORBIDDEN"].includes(cause.code)) { onTeamChanged(); return; }
      setState({ status: "error", message: teamErrorMessage(cause) });
    });
    return () => controller.abort();
  }, [actorId, revision, onUnauthenticated, onTeamChanged]);

  return <section className={styles.membersSection} aria-labelledby="team-members-title">
    <div className={styles.membersHeading}><h2 id="team-members-title">สมาชิกในทีม</h2>
      <button type="button" className={styles.textButton} onClick={refresh} disabled={state.status === "loading"}>โหลดรายชื่อใหม่</button>
    </div>
    {notice && <p className={styles.memberNotice} role="status">{notice}</p>}
    {state.status === "loading" && <p className={styles.hint} role="status">กำลังโหลดรายชื่อสมาชิก…</p>}
    {state.status === "error" && <div className={styles.errorBox} role="alert"><p>{state.message}</p><button type="button" onClick={refresh}>ลองโหลดรายชื่ออีกครั้ง</button></div>}
    {state.status === "ready" && <>
      <ul className={styles.memberList} aria-label="รายชื่อสมาชิกทีม">
        {state.members.map((member) => <li key={member.id}><span className={styles.memberName}>{member.full_name}
          {member.user_id === actorId && <span className={styles.selfLabel}> (คุณ)</span>}</span>
          <span className={member.role === "leader" ? styles.leaderBadge : styles.memberBadge}>{member.role === "leader" ? "หัวหน้า" : "สมาชิก"}</span>
        </li>)}
      </ul>
      {state.members.find((member) => member.user_id === actorId)?.role === "leader" && <MemberAddForm
        onUnauthenticated={onUnauthenticated} onTeamChanged={onTeamChanged} onCheck={refresh}
        onAdded={() => { setNotice("เพิ่มสมาชิกสำเร็จแล้ว"); refresh(); }} />}
    </>}
  </section>;
}
