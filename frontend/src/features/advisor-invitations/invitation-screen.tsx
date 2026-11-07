"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { AuthShell } from "@/features/auth/auth-shell";
import { useSession } from "@/features/auth/use-session";
import authStyles from "@/features/auth/auth.module.css";
import { currentTeam, TeamApiError, type CurrentTeam } from "@/features/teams/api";
import { currentProject, ProjectApiError, type Project } from "@/features/projects/api";
import { advisorHistory, candidates, cancelInvitation, InvitationApiError, invitationErrorMessage, respondInvitation, sendInvitation, STATUS_TEXT,
  teamHistory, type AdvisorInvitation, type Candidate, type TeamInvitation } from "./api";
import styles from "./invitations.module.css";

type Mode = "team" | "advisor";
type Ready = { kind: "team"; team: CurrentTeam; project: Project; history: TeamInvitation[]; candidates: Candidate[] }
  | { kind: "advisor"; history: AdvisorInvitation[] };
type State = { status: "loading" } | { status: "missing"; resource: "team" | "project" }
  | { status: "error"; message: string } | { status: "ready"; data: Ready };
const timestamp = (value: string) => new Intl.DateTimeFormat("th-TH", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Bangkok" }).format(new Date(value));

export function InvitationScreen({ mode }: { mode: Mode }) {
  const router = useRouter();
  const session = useSession();
  const onUnauthenticated = useCallback(() => router.replace("/login?reason=session"), [router]);
  useEffect(() => { if (session.state.status === "unauthenticated") onUnauthenticated(); }, [session.state.status, onUnauthenticated]);
  const frame = (content: React.ReactNode) => <AuthShell><section aria-label={mode === "team" ? "คำเชิญอาจารย์ของทีม" : "คำเชิญของอาจารย์"}>{content}</section></AuthShell>;
  if (session.state.status === "loading" || session.state.status === "unauthenticated") return frame(<p role="status" className={styles.hint}>กำลังตรวจสอบการเข้าสู่ระบบ…</p>);
  if (session.state.status === "error") return frame(<><h1>ยังเชื่อมต่อระบบไม่ได้</h1><p role="alert">{session.state.message}</p><button className={styles.primaryButton} onClick={session.retry}>ลองอีกครั้ง</button></>);
  if (session.state.user.role !== (mode === "team" ? "student" : "advisor")) return frame(<><Link className={styles.backLink} href="/">← กลับหน้าบัญชี</Link><div className={authStyles.heading}><h1>บทบาทของคุณไม่สามารถใช้หน้านี้ได้</h1><p>กลับหน้าบัญชีเพื่อใช้งานตามบทบาทของคุณ</p></div></>);
  return frame(<Workspace key={`${mode}:${session.state.user.id}`} mode={mode} onUnauthenticated={onUnauthenticated} />);
}

function Workspace({ mode, onUnauthenticated }: { mode: Mode; onUnauthenticated: () => void }) {
  const [state, setState] = useState<State>({ status: "loading" });
  const [revision, setRevision] = useState(0);
  const [selected, setSelected] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loginNeeded, setLoginNeeded] = useState(false);
  const pending = useRef(false);
  const actionRequest = useRef<AbortController | null>(null);
  const refresh = useCallback(() => { setState({ status: "loading" }); setSelected(""); setRevision((value) => value + 1); }, []);
  useEffect(() => () => actionRequest.current?.abort(), []);
  useEffect(() => {
    const controller = new AbortController();
    async function load(): Promise<State> {
      if (mode === "advisor") return { status: "ready", data: { kind: "advisor", history: await advisorHistory(controller.signal) } };
      const team = await currentTeam(controller.signal);
      if (!team) return { status: "missing", resource: "team" };
      const project = await currentProject(controller.signal);
      if (!project) return { status: "missing", resource: "project" };
      if (project.team_id !== team.id) throw new InvitationApiError(502, "INVALID_RESPONSE");
      const history = await teamHistory(controller.signal);
      const active = history.some((row) => row.status === "pending" || row.status === "accepted");
      const options = team.membership.role === "leader" && !active ? await candidates(controller.signal) : [];
      return { status: "ready", data: { kind: "team", team, project, history, candidates: options } };
    }
    void load().then((value) => { if (!controller.signal.aborted) setState(value); }).catch((cause: unknown) => {
      if (controller.signal.aborted) return;
      const known = cause instanceof InvitationApiError || cause instanceof ProjectApiError || cause instanceof TeamApiError;
      if (known && cause.status === 401) { onUnauthenticated(); return; }
      if (known && cause.status === 404 && ["TEAM_NOT_FOUND", "PROJECT_NOT_FOUND"].includes(cause.code)) {
        setState({ status: "missing", resource: cause.code === "TEAM_NOT_FOUND" ? "team" : "project" }); return;
      }
      setState({ status: "error", message: invitationErrorMessage(cause) });
    });
    return () => controller.abort();
  }, [mode, revision, onUnauthenticated]);

  async function action(operation: (signal: AbortSignal) => Promise<unknown>, message: string) {
    if (pending.current) return;
    pending.current = true; setBusy(true); setError(""); setNotice(""); setLoginNeeded(false);
    const controller = new AbortController(); actionRequest.current = controller;
    try {
      await operation(controller.signal);
      if (!controller.signal.aborted) { setNotice(message); refresh(); }
    } catch (cause) {
      if (controller.signal.aborted) return;
      if (cause instanceof InvitationApiError && cause.status === 401) { onUnauthenticated(); return; }
      setError(invitationErrorMessage(cause)); setLoginNeeded(cause instanceof InvitationApiError && cause.code === "CSRF_INVALID");
      if (cause instanceof InvitationApiError && ["INVITATION_ACTION_FORBIDDEN", "INVITATION_ACCESS_FORBIDDEN", "INVITATION_NOT_FOUND"].includes(cause.code)) refresh();
    } finally { pending.current = false; if (!controller.signal.aborted) setBusy(false); }
  }
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current) return;
    if (state.status !== "ready" || state.data.kind !== "team" || !state.data.candidates.some((item) => item.id === selected)) { setError("กรุณาเลือกอาจารย์ที่ปรึกษา"); return; }
    void action((signal) => sendInvitation(selected, signal), "ส่งคำเชิญแล้ว");
  }

  const back = <Link className={styles.backLink} href={mode === "team" ? "/projects" : "/"}>{mode === "team" ? "← กลับหน้าโครงงาน" : "← กลับหน้าบัญชี"}</Link>;
  if (state.status === "loading") return <>{back}<p role="status" className={styles.hint}>กำลังโหลดคำเชิญ…</p></>;
  if (state.status === "missing") return <>{back}<div className={authStyles.heading}><h1>{state.resource === "team" ? "ต้องมีทีมก่อนเชิญอาจารย์" : "ต้องมีโครงงานก่อนเชิญอาจารย์"}</h1><p>กลับไปเตรียมข้อมูลก่อนส่งคำเชิญ</p></div><Link className={styles.primaryButton} href={state.resource === "team" ? "/teams" : "/projects"}>ไปหน้าที่เกี่ยวข้อง</Link></>;
  if (state.status === "error") return <>{back}<div className={authStyles.heading}><h1>ยังโหลดคำเชิญไม่ได้</h1><p role="alert">{state.message}</p></div><button className={styles.primaryButton} onClick={refresh}>ลองอีกครั้ง</button></>;
  const data = state.data;
  const leader = data.kind === "team" && data.team.membership.role === "leader";
  const active = data.history.find((row) => row.status === "pending" || row.status === "accepted");
  return <>{back}<div className={authStyles.heading}><span className={authStyles.sectionLabel}>{mode === "team" ? "อาจารย์ที่ปรึกษา" : "สำหรับอาจารย์"}</span>
    <h1>{mode === "team" ? "คำเชิญอาจารย์ที่ปรึกษา" : "คำเชิญของคุณ"}</h1>
    <p>{data.kind === "team" ? data.project.name : "ตอบรับหรือปฏิเสธคำเชิญที่ส่งถึงคุณ"}</p></div>
    {notice && <p className={styles.notice} role="status">{notice}</p>}
    {error && <div className={styles.errorBox} role="alert"><p>{error}</p>{loginNeeded ? <Link href="/login">เข้าสู่ระบบใหม่</Link> : <button disabled={busy} onClick={refresh}>ตรวจประวัติอีกครั้ง</button>}</div>}
    <div className={styles.historyHeading}><h2>ประวัติคำเชิญ</h2><button className={styles.textButton} disabled={busy} onClick={refresh}>โหลดประวัติใหม่</button></div>
    {data.history.length === 0 ? <p className={styles.empty}>ยังไม่มีคำเชิญ</p> : <ul className={styles.history} aria-label="ประวัติคำเชิญ">
      {data.history.map((row) => <li key={row.id} className={styles.card} data-testid={`invitation-${row.id}`}>
        <div className={styles.cardTop}><h3>{"advisor" in row ? row.advisor.full_name : row.project_context?.project_name ?? "คำเชิญที่สิ้นสุดแล้ว"}</h3><span className={styles.badge}>{STATUS_TEXT[row.status]}</span></div>
        {"project_context" in row && row.project_context && <div className={styles.context}><p>{row.project_context.team_name}</p><p>{row.project_context.project_description ?? "ยังไม่มีคำอธิบายโครงงาน"}</p></div>}
        <p className={styles.time}>ส่งเมื่อ {timestamp(row.sent_at)}</p>{row.resolved_at && <p className={styles.time}>สิ้นสุดเมื่อ {timestamp(row.resolved_at)}</p>}
        {row.status === "pending" && (data.kind === "advisor" ? <div className={styles.actions}>
          <button className={styles.primaryButton} disabled={busy} onClick={() => void action((signal) => respondInvitation(row.id, "accepted", signal), "ตอบรับคำเชิญแล้ว")}>ตอบรับ</button>
          <button className={styles.secondaryButton} disabled={busy} onClick={() => void action((signal) => respondInvitation(row.id, "rejected", signal), "ปฏิเสธคำเชิญแล้ว")}>ปฏิเสธ</button>
        </div> : leader && <button className={styles.secondaryButton} disabled={busy} onClick={() => void action((signal) => cancelInvitation(row.id, signal), "ยกเลิกคำเชิญแล้ว")}>ยกเลิกคำเชิญ</button>)}
      </li>)}
    </ul>}
    {data.kind === "team" && (leader ? active ? <p className={styles.hint}>{active.status === "accepted" ? "อาจารย์ตอบรับแล้ว ไม่สามารถเปลี่ยนอาจารย์ได้" : "มีคำเชิญที่รอตอบรับอยู่แล้ว"}</p>
      : data.candidates.length === 0 ? <p className={styles.empty}>ยังไม่มีบัญชีอาจารย์ให้เลือก กรุณาให้ผู้ดูแลเตรียมบัญชีก่อน</p>
        : <form className={styles.form} onSubmit={submit} aria-busy={busy} noValidate><div className={styles.field}>
          <label htmlFor="advisor-select">เลือกอาจารย์ที่ปรึกษา</label><select id="advisor-select" value={selected} onChange={(event) => setSelected(event.target.value)} disabled={busy} required>
            <option value="">เลือกอาจารย์</option>{data.candidates.map((item) => <option key={item.id} value={item.id}>{item.full_name}</option>)}
          </select></div><button className={styles.primaryButton} disabled={busy} type="submit">{busy ? "กำลังส่งคำเชิญ…" : "ส่งคำเชิญ"}</button></form>
      : <p className={styles.hint}>เฉพาะหัวหน้าทีมเท่านั้นที่ส่งหรือยกเลิกคำเชิญได้</p>)}
  </>;
}
