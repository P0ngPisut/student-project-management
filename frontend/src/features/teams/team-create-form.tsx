"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { createTeam, TeamApiError, teamErrorMessage, teamFieldMessages, validateTeamInput, type CreatedTeam } from "./api";
import styles from "./teams.module.css";

export function TeamCreateForm({ onCreated, onCheckTeam, onUnauthenticated }: {
  onCreated: (team: CreatedTeam) => void;
  onCheckTeam: () => void;
  onUnauthenticated: () => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [loginNeeded, setLoginNeeded] = useState(false);
  const pending = useRef(false);
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current) return;
    const invalid = validateTeamInput(name, description);
    setFields(invalid);
    setError("");
    setLoginNeeded(false);
    if (Object.keys(invalid).length) return;
    const controller = new AbortController();
    request.current = controller;
    pending.current = true;
    setBusy(true);
    try {
      const team = await createTeam(name, description, controller.signal);
      if (!controller.signal.aborted) onCreated(team);
    } catch (cause) {
      if (controller.signal.aborted) return;
      if (cause instanceof TeamApiError && cause.status === 401) { onUnauthenticated(); return; }
      setError(teamErrorMessage(cause));
      setFields(teamFieldMessages(cause));
      setLoginNeeded(cause instanceof TeamApiError && cause.code === "CSRF_INVALID");
    } finally {
      pending.current = false;
      if (!controller.signal.aborted) setBusy(false);
    }
  }

  return <>
    {error && <div className={styles.errorBox} role="alert"><p>{error}</p>
      {loginNeeded ? <Link href="/login">เข้าสู่ระบบใหม่</Link> : <button type="button" onClick={onCheckTeam}>ตรวจสอบทีมอีกครั้ง</button>}
    </div>}
    <form className={styles.form} onSubmit={submit} noValidate aria-busy={busy}>
      <div className={styles.field}>
        <label htmlFor="team-name">ชื่อทีม</label>
        <input id="team-name" name="name" value={name} onChange={(event) => setName(event.target.value)} disabled={busy} required
          placeholder="กรอกชื่อทีมของคุณ" autoComplete="off" aria-invalid={Boolean(fields.name)} aria-describedby={fields.name ? "team-name-error" : "team-name-hint"} />
        {fields.name ? <p id="team-name-error" className={styles.fieldError}>{fields.name}</p> : <p id="team-name-hint" className={styles.hint}>ไม่เกิน 255 ตัวอักษร</p>}
      </div>
      <div className={styles.field}>
        <label htmlFor="team-description">คำอธิบายทีม <span className={styles.optional}>(ไม่บังคับ)</span></label>
        <textarea id="team-description" name="description" value={description} onChange={(event) => setDescription(event.target.value)} disabled={busy}
          placeholder="อธิบายแนวทางหรือความสนใจของทีม" rows={4} aria-invalid={Boolean(fields.description)} aria-describedby={fields.description ? "team-description-error" : undefined} />
        {fields.description && <p id="team-description-error" className={styles.fieldError}>{fields.description}</p>}
      </div>
      <p className={styles.hint}>คุณจะเป็นหัวหน้าทีมโดยอัตโนมัติเมื่อสร้างทีมสำเร็จ</p>
      <button className={styles.primaryButton} type="submit" disabled={busy}>{busy ? "กำลังสร้างทีม…" : "สร้างทีม"}{!busy && <span aria-hidden="true">→</span>}</button>
    </form>
  </>;
}
