"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AuthShell } from "@/features/auth/auth-shell";
import { useSession } from "@/features/auth/use-session";
import authStyles from "@/features/auth/auth.module.css";
import { TeamCreateForm } from "./team-create-form";
import { useCurrentTeam } from "./use-current-team";
import { TeamMembers } from "./team-members";
import styles from "./teams.module.css";

export function TeamScreen() {
  const router = useRouter();
  const session = useSession();
  const actorId = session.state.status === "authenticated" && session.state.user.role === "student" ? session.state.user.id : undefined;
  const team = useCurrentTeam(actorId);
  const onUnauthenticated = useCallback(() => router.replace("/login?reason=session"), [router]);
  const [notice, setNotice] = useState<{ owner?: string; teamId: string; text: string } | null>(null);
  useEffect(() => {
    if (session.state.status === "unauthenticated" || team.state.status === "unauthenticated") router.replace("/login?reason=session");
  }, [session.state.status, team.state.status, router]);

  const back = <Link className={styles.backLink} href="/">← กลับหน้าบัญชี</Link>;
  const loading = <div className={authStyles.sessionState} role="status"><span className={authStyles.spinner} aria-hidden="true" /><p>กำลังตรวจสอบทีมของคุณ…</p></div>;
  if (session.state.status === "loading" || session.state.status === "unauthenticated") return <AuthShell>{loading}</AuthShell>;
  if (session.state.status === "error") return <AuthShell>{back}<div className={authStyles.heading}><h1>ยังเชื่อมต่อระบบไม่ได้</h1><p role="alert">{session.state.message}</p></div><button className={styles.primaryButton} onClick={session.retry}>ลองอีกครั้ง</button></AuthShell>;
  if (session.state.user.role !== "student" || team.state.status === "forbidden") return <AuthShell>{back}<div className={authStyles.heading}><span className={authStyles.sectionLabel}>ทีมของฉัน</span><h1>หน้านี้สำหรับนักศึกษา</h1><p>กลับหน้าบัญชีเพื่อใช้งานตามบทบาทของคุณ</p></div></AuthShell>;
  if (team.state.status === "loading" || team.state.status === "unauthenticated") return <AuthShell>{back}{loading}</AuthShell>;
  if (team.state.status === "error") return <AuthShell>{back}<div className={authStyles.heading}><span className={authStyles.sectionLabel}>ทีมของฉัน</span><h1>ยังโหลดข้อมูลทีมไม่ได้</h1><p role="alert">{team.state.message}</p></div><button className={styles.primaryButton} onClick={team.refresh}>ลองอีกครั้ง</button></AuthShell>;
  if (team.state.status === "ready") {
    const data = team.state.team;
    return <AuthShell>{back}
      <div className={authStyles.heading}><span className={authStyles.sectionLabel}>ทีมของฉัน</span><h1>{data.name}</h1><p>ข้อมูลทีมและบทบาทสมาชิกของคุณ</p></div>
      {notice?.owner === actorId && notice?.teamId === data.id && <p className={authStyles.notice} role="status">{notice.text}</p>}
      <section className={styles.teamCard} aria-label="ข้อมูลทีม">
        <div className={styles.cardTop}><span className={styles.teamIcon} aria-hidden="true">◇</span><div><p className={styles.cardLabel}>บทบาทของคุณ</p><strong>{data.membership.role === "leader" ? "หัวหน้าทีม" : "สมาชิกทีม"}</strong></div></div>
        <dl className={styles.teamDetails}><div><dt>ชื่อทีม</dt><dd>{data.name}</dd></div><div><dt>คำอธิบายทีม</dt><dd className={styles.description}>{data.description ?? "ยังไม่มีคำอธิบายทีม"}</dd></div></dl>
      </section>
      <Link className={styles.projectLink} href="/projects">โครงงานของทีม →</Link>
      <TeamMembers key={`${actorId}:${data.id}`} actorId={session.state.user.id}
        onUnauthenticated={onUnauthenticated} onTeamChanged={team.refresh} />
    </AuthShell>;
  }
  return <AuthShell>{back}
    <div className={authStyles.heading}><span className={authStyles.sectionLabel}>เริ่มต้นทีมของคุณ</span><h1>สร้างทีมของคุณ</h1><p>ตั้งชื่อทีมและเพิ่มคำอธิบายเพื่อเริ่มต้นทำงานร่วมกัน</p></div>
    <TeamCreateForm onUnauthenticated={() => router.replace("/login?reason=session")} onCheckTeam={team.refresh}
      onCreated={(created) => {
        if (created.members[0].user_id !== actorId) { session.retry(); return; }
        team.acceptCreated(created);
        setNotice({ owner: actorId, teamId: created.id, text: "สร้างทีมสำเร็จแล้ว คุณเป็นหัวหน้าทีม" });
      }} />
  </AuthShell>;
}
