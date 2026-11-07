"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { createProject, ProjectApiError, projectErrorMessage, projectFieldMessages, validateProjectInput, type Project } from "./api";
import styles from "./projects.module.css";

export function ProjectCreateForm({ onCreated, onCheck, onUnauthenticated }: {
  onCreated: (project: Project) => void; onCheck: () => void; onUnauthenticated: () => void;
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
    event.preventDefault(); if (pending.current) return;
    const invalid = validateProjectInput(name, description);
    setFields(invalid); setError(""); setLoginNeeded(false);
    if (Object.keys(invalid).length) return;
    const controller = new AbortController(); request.current = controller; pending.current = true; setBusy(true);
    try {
      const project = await createProject(name, description, controller.signal);
      if (!controller.signal.aborted) onCreated(project);
    } catch (cause) {
      if (controller.signal.aborted) return;
      if (cause instanceof ProjectApiError && cause.status === 401) { onUnauthenticated(); return; }
      if (cause instanceof ProjectApiError && ["PROJECT_CREATION_FORBIDDEN", "TEAM_NOT_FOUND", "PROJECT_ACCESS_FORBIDDEN"].includes(cause.code)) { onCheck(); return; }
      setError(projectErrorMessage(cause)); setFields(projectFieldMessages(cause));
      setLoginNeeded(cause instanceof ProjectApiError && cause.code === "CSRF_INVALID");
    } finally { pending.current = false; if (!controller.signal.aborted) setBusy(false); }
  }
  return <>
    {error && <div className={styles.errorBox} role="alert"><p>{error}</p>
      {loginNeeded ? <Link href="/login">เข้าสู่ระบบใหม่</Link> : <button type="button" onClick={onCheck}>ตรวจสอบโครงงานอีกครั้ง</button>}
    </div>}
    <form className={styles.form} onSubmit={submit} noValidate aria-busy={busy}>
      <div className={styles.field}><label htmlFor="project-name">ชื่อโครงงาน</label>
        <input id="project-name" name="name" value={name} onChange={(event) => setName(event.target.value)} disabled={busy} required
          autoComplete="off" placeholder="กรอกชื่อโครงงานของทีม" aria-invalid={Boolean(fields.name)} aria-describedby={fields.name ? "project-name-error" : "project-name-hint"} />
        {fields.name ? <p id="project-name-error" className={styles.fieldError}>{fields.name}</p> : <p id="project-name-hint" className={styles.hint}>ไม่เกิน 255 ตัวอักษร</p>}
      </div>
      <div className={styles.field}><label htmlFor="project-description">คำอธิบายโครงงาน <span className={styles.optional}>(ไม่บังคับ)</span></label>
        <textarea id="project-description" name="description" value={description} onChange={(event) => setDescription(event.target.value)} disabled={busy}
          placeholder="อธิบายแนวคิดหรือเป้าหมายของโครงงาน" rows={4} aria-invalid={Boolean(fields.description)} aria-describedby={fields.description ? "project-description-error" : undefined} />
        {fields.description && <p id="project-description-error" className={styles.fieldError}>{fields.description}</p>}
      </div>
      <p className={styles.hint}>หนึ่งทีมสร้างได้หนึ่งโครงงาน และไม่สามารถลบโครงงานได้</p>
      <button className={styles.primaryButton} type="submit" disabled={busy}>{busy ? "กำลังสร้างโครงงาน…" : "สร้างโครงงาน"}</button>
    </form>
  </>;
}
