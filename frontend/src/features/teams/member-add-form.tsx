"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { trimAscii } from "@/features/auth/api";
import { addMember, TeamApiError, teamErrorMessage } from "./api";
import styles from "./teams.module.css";

export function MemberAddForm({ onAdded, onCheck, onUnauthenticated, onTeamChanged }: {
  onAdded: () => void; onCheck: () => void; onUnauthenticated: () => void; onTeamChanged: () => void;
}) {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [field, setField] = useState("");
  const [loginNeeded, setLoginNeeded] = useState(false);
  const pending = useRef(false);
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current) return;
    const value = trimAscii(email);
    setError(""); setField(""); setLoginNeeded(false);
    // Backend remains the authority for the approved Auth email syntax.
    if (!value) { setField("กรุณากรอกอีเมลของนักศึกษา"); return; }
    const controller = new AbortController();
    request.current = controller; pending.current = true; setBusy(true);
    try {
      await addMember(value, controller.signal);
      if (!controller.signal.aborted) { setEmail(""); onAdded(); }
    } catch (cause) {
      if (controller.signal.aborted) return;
      if (cause instanceof TeamApiError && cause.status === 401) { onUnauthenticated(); return; }
      if (cause instanceof TeamApiError && ["TEAM_NOT_FOUND", "TEAM_MEMBER_ADDITION_FORBIDDEN", "TEAM_ACCESS_FORBIDDEN"].includes(cause.code)) {
        onTeamChanged(); return;
      }
      setError(teamErrorMessage(cause));
      if (cause instanceof TeamApiError && cause.code === "VALIDATION_ERROR") setField("กรุณากรอกอีเมลให้ถูกต้อง เช่น student@example.test");
      setLoginNeeded(cause instanceof TeamApiError && cause.code === "CSRF_INVALID");
    } finally {
      pending.current = false;
      if (!controller.signal.aborted) setBusy(false);
    }
  }

  return <div className={styles.addMember}>
    <h3>เพิ่มสมาชิกทีม</h3>
    <p className={styles.hint}>ใช้อีเมลของนักศึกษาที่สมัครแล้วและยังไม่มีทีม เมื่อเพิ่มสำเร็จจะเป็นสมาชิกทันที</p>
    {error && <div className={styles.errorBox} role="alert"><p>{error}</p>
      {loginNeeded ? <Link href="/login">เข้าสู่ระบบใหม่</Link> : <button type="button" onClick={onCheck}>ตรวจสอบรายชื่ออีกครั้ง</button>}
    </div>}
    <form className={styles.form} onSubmit={submit} noValidate aria-busy={busy}>
      <div className={styles.field}>
        <label htmlFor="member-email">อีเมลนักศึกษาที่ต้องการเพิ่ม</label>
        <input id="member-email" name="email" type="email" inputMode="email" autoComplete="off" value={email}
          onChange={(event) => setEmail(event.target.value)} disabled={busy} required placeholder="student@example.test"
          aria-invalid={Boolean(field)} aria-describedby={field ? "member-email-error" : undefined} />
        {field && <p id="member-email-error" className={styles.fieldError}>{field}</p>}
      </div>
      <button className={styles.primaryButton} disabled={busy} type="submit">{busy ? "กำลังเพิ่มสมาชิก…" : "เพิ่มสมาชิก"}</button>
    </form>
  </div>;
}
