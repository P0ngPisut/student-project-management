"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { errorMessage, fieldMessages, login, register, trimAscii } from "./api";
import { AuthShell } from "./auth-shell";
import styles from "./auth.module.css";

export function AuthForm({ mode, notice = "" }: { mode: "login" | "register"; notice?: string }) {
  const router = useRouter();
  const signup = mode === "register";
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const invalid: Record<string, string> = {};
    if (signup && !trimAscii(fullName)) invalid.full_name = "กรุณากรอกชื่อและนามสกุล";
    if (signup && Array.from(trimAscii(fullName)).length > 255) invalid.full_name = "ชื่อต้องยาวไม่เกิน 255 ตัวอักษร";
    if (!trimAscii(email)) invalid.email = "กรุณากรอกอีเมล";
    if (!password) invalid.password = "กรุณากรอกรหัสผ่าน";
    else if (signup && Array.from(password).length < 8) invalid.password = "รหัสผ่านต้องมีอย่างน้อย 8 ตัวอักษร";
    else if (signup && !/[A-Z]/.test(password)) invalid.password = "รหัสผ่านต้องมีตัวพิมพ์ใหญ่ A–Z อย่างน้อย 1 ตัว";
    else if (signup && !/[0-9]/.test(password)) invalid.password = "รหัสผ่านต้องมีตัวเลข 0–9 อย่างน้อย 1 ตัว";
    setFields(invalid);
    setError("");
    if (Object.keys(invalid).length) return;
    const controller = new AbortController();
    request.current = controller;
    setBusy(true);
    try {
      if (signup) {
        await register(trimAscii(fullName), trimAscii(email), password, controller.signal);
        setPassword("");
        router.replace("/login?registered=1");
      } else {
        await login(trimAscii(email), password, controller.signal);
        setPassword("");
        router.replace("/");
        router.refresh();
      }
    } catch (cause) {
      if (!controller.signal.aborted) { setError(errorMessage(cause)); setFields(fieldMessages(cause)); setPassword(""); }
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }

  return <AuthShell>
    <div className={styles.heading}>
      <span className={styles.sectionLabel}>{signup ? "สร้างบัญชีนักศึกษา" : "เข้าสู่ระบบ"}</span>
      <h1>{signup ? "สร้างบัญชีของคุณ" : "ยินดีต้อนรับกลับมา"}</h1>
      <p>{signup ? "กรอกข้อมูลเพื่อเริ่มต้นใช้งานระบบ" : "เข้าสู่ระบบด้วยอีเมลและรหัสผ่านของคุณ"}</p>
    </div>
    {notice && <p className={styles.notice} role="status">{notice}</p>}
    {error && <p className={styles.errorBox} role="alert">{error}</p>}
    <form className={styles.form} onSubmit={submit} noValidate aria-busy={busy}>
      {signup && <div className={styles.field}>
        <label htmlFor="full-name">ชื่อและนามสกุล</label>
        <input id="full-name" name="full_name" autoComplete="name" value={fullName} onChange={(event) => setFullName(event.target.value)} disabled={busy} required
          aria-invalid={Boolean(fields.full_name)} aria-describedby={fields.full_name ? "full-name-error" : undefined} placeholder="กรอกชื่อและนามสกุล" />
        {fields.full_name && <p id="full-name-error" className={styles.fieldError}>{fields.full_name}</p>}
      </div>}
      <div className={styles.field}>
        <label htmlFor="email">อีเมล</label>
        <input id="email" name="email" type="email" autoComplete="username" inputMode="email" value={email} onChange={(event) => setEmail(event.target.value)} disabled={busy} required
          autoCapitalize="none" spellCheck={false} placeholder="student@example.test" aria-invalid={Boolean(fields.email)} aria-describedby={fields.email ? "email-error" : undefined} />
        {fields.email && <p id="email-error" className={styles.fieldError}>{fields.email}</p>}
      </div>
      <div className={styles.field}>
        <label htmlFor="password">รหัสผ่าน</label>
        <input id="password" name="password" type="password" autoComplete={signup ? "new-password" : "current-password"} value={password} onChange={(event) => setPassword(event.target.value)} disabled={busy} required
          placeholder="กรอกรหัสผ่านของคุณ" aria-invalid={Boolean(fields.password)} aria-describedby={fields.password ? "password-error" : signup ? "password-hint" : undefined} />
        {fields.password ? <p id="password-error" className={styles.fieldError}>{fields.password}</p>
          : signup && <p id="password-hint" className={styles.hint}>อย่างน้อย 8 ตัวอักษร มีตัวพิมพ์ใหญ่ A–Z และตัวเลขอย่างละ 1 ตัว</p>}
      </div>
      <button className={styles.primaryButton} type="submit" disabled={busy}>
        {busy ? (signup ? "กำลังสร้างบัญชี…" : "กำลังเข้าสู่ระบบ…") : (signup ? "สร้างบัญชี" : "เข้าสู่ระบบ")}{!busy && <span aria-hidden="true">→</span>}
      </button>
    </form>
    <p className={styles.switchLink}>{signup ? "มีบัญชีอยู่แล้ว?" : "ยังไม่มีบัญชี?"}{" "}<Link href={signup ? "/login" : "/register"}>{signup ? "เข้าสู่ระบบ" : "สมัครสมาชิก"}</Link></p>
    {signup && <p className={styles.signupNote}>สมัครด้วยตนเองได้เฉพาะนักศึกษา<br />บัญชีอาจารย์และผู้ประสานงาน กรุณาติดต่อผู้ดูแลระบบ</p>}
  </AuthShell>;
}
