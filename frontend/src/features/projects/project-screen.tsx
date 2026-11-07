"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AuthShell } from "@/features/auth/auth-shell";
import { useSession } from "@/features/auth/use-session";
import authStyles from "@/features/auth/auth.module.css";
import { ProjectCreateForm } from "./project-create-form";
import { useCurrentProject } from "./use-current-project";
import styles from "./projects.module.css";

export function ProjectScreen() {
  const router = useRouter();
  const session = useSession();
  const actorId = session.state.status === "authenticated" && session.state.user.role === "student" ? session.state.user.id : undefined;
  const project = useCurrentProject(actorId);
  const [notice, setNotice] = useState<{ owner?: string; projectId: string } | null>(null);
  useEffect(() => {
    if (session.state.status === "unauthenticated" || project.state.status === "unauthenticated") router.replace("/login?reason=session");
  }, [session.state.status, project.state.status, router]);
  const loading = <div className={authStyles.sessionState} role="status"><span className={authStyles.spinner} aria-hidden="true" /><p>กำลังตรวจสอบโครงงานของทีม…</p></div>;
  const back = <Link className={styles.backLink} href="/teams">← กลับหน้าทีม</Link>;
  const frame = (content: React.ReactNode) => <AuthShell><section aria-label="โครงงานของทีม">{content}</section></AuthShell>;
  if (session.state.status === "loading" || session.state.status === "unauthenticated") return frame(loading);
  if (session.state.status === "error") return frame(<>{back}<div className={authStyles.heading}><h1>ยังเชื่อมต่อระบบไม่ได้</h1><p role="alert">{session.state.message}</p></div><button className={styles.primaryButton} onClick={session.retry}>ลองอีกครั้ง</button></>);
  if (session.state.user.role !== "student" || project.state.status === "forbidden") return frame(<><Link className={styles.backLink} href="/">← กลับหน้าบัญชี</Link><div className={authStyles.heading}><h1>หน้านี้สำหรับนักศึกษา</h1><p>กลับหน้าบัญชีเพื่อใช้งานตามบทบาทของคุณ</p></div></>);
  if (project.state.status === "loading" || project.state.status === "unauthenticated") return frame(<>{back}{loading}</>);
  if (project.state.status === "error") return frame(<>{back}<div className={authStyles.heading}><h1>ยังโหลดข้อมูลโครงงานไม่ได้</h1><p role="alert">{project.state.message}</p></div><button className={styles.primaryButton} onClick={project.refresh}>ลองอีกครั้ง</button></>);
  if (project.state.status === "no-team") return frame(<>{back}<div className={authStyles.heading}><h1>ต้องมีทีมก่อนสร้างโครงงาน</h1><p>สร้างทีมหรือให้หัวหน้าเพิ่มคุณเข้าทีมก่อนเริ่มโครงงาน</p></div><Link className={styles.primaryButton} href="/teams">ไปหน้าทีม</Link></>);
  const team = project.state.team;
  if (project.state.status === "ready") {
    const data = project.state.project;
    return frame(<>{back}<div className={authStyles.heading}><span className={authStyles.sectionLabel}>โครงงานของทีม</span><h1>{data.name}</h1><p>ข้อมูลโครงงานของ {team.name}</p></div>
      {notice?.owner === actorId && notice?.projectId === data.id && <p className={authStyles.notice} role="status">สร้างโครงงานสำเร็จแล้ว</p>}
      <section className={styles.projectCard} aria-label="ข้อมูลโครงงาน"><dl>
        <div><dt>ชื่อโครงงาน</dt><dd>{data.name}</dd></div><div><dt>คำอธิบายโครงงาน</dt><dd className={styles.description}>{data.description ?? "ยังไม่มีคำอธิบายโครงงาน"}</dd></div>
        <div><dt>ทีมเจ้าของโครงงาน</dt><dd>{team.name}</dd></div>
      </dl></section>
      <Link className={styles.invitationLink} href="/projects/advisor-invitations">คำเชิญอาจารย์ที่ปรึกษา →</Link>
    </>);
  }
  if (team.membership.role !== "leader") return frame(<>{back}<div className={authStyles.heading}><span className={authStyles.sectionLabel}>{team.name}</span><h1>รอหัวหน้าทีมสร้างโครงงาน</h1><p>เมื่อหัวหน้าสร้างโครงงานแล้ว สมาชิกในทีมจะอ่านข้อมูลได้จากหน้านี้</p></div><button className={styles.primaryButton} onClick={project.refresh}>ตรวจสอบโครงงานอีกครั้ง</button></>);
  return frame(<>{back}<div className={authStyles.heading}><span className={authStyles.sectionLabel}>{team.name}</span><h1>สร้างโครงงานของทีม</h1><p>ตั้งชื่อและอธิบายแนวคิดโครงงานสำหรับทีมของคุณ</p></div>
    <ProjectCreateForm key={`${actorId}:${team.id}`} onCheck={project.refresh} onUnauthenticated={() => router.replace("/login?reason=session")}
      onCreated={(created) => {
        if (created.team_id !== team.id || created.created_by !== actorId) { session.retry(); project.refresh(); return; }
        project.acceptCreated(team, created); setNotice({ owner: actorId, projectId: created.id });
      }} />
  </>);
}
