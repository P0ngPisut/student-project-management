"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AuthApiError, errorMessage, logout } from "./api";
import { AuthShell } from "./auth-shell";
import { useSession } from "./use-session";
import styles from "./auth.module.css";

const ROLES = { student: "นักศึกษา", advisor: "อาจารย์ที่ปรึกษา", coordinator: "ผู้ประสานงาน" };
export function AccountScreen() {
  const router = useRouter();
  const { state, retry } = useSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { if (state.status === "unauthenticated") router.replace("/login?reason=session"); }, [state.status, router]);
  async function signOut() {
    if (busy) return;
    setBusy(true);
    setError("");
    try { await logout(); router.replace("/login?logged_out=1"); router.refresh(); }
    catch (cause) {
      if (cause instanceof AuthApiError && cause.status === 401) router.replace("/login?reason=session");
      else { setError(errorMessage(cause)); setBusy(false); }
    }
  }
  if (state.status === "loading" || state.status === "unauthenticated") {
    return <AuthShell><div className={styles.sessionState} role="status"><span className={styles.spinner} aria-hidden="true" /><p>กำลังตรวจสอบการเข้าสู่ระบบ…</p></div></AuthShell>;
  }
  if (state.status === "error") {
    return <AuthShell><div className={styles.heading}><span className={styles.sectionLabel}>บัญชีผู้ใช้งาน</span><h1>ยังเชื่อมต่อระบบไม่ได้</h1><p role="alert">{state.message}</p></div><button className={styles.primaryButton} onClick={retry}>ลองอีกครั้ง</button></AuthShell>;
  }
  const user = state.user;
  return <AuthShell>
    <div className={styles.heading}><span className={styles.sectionLabel}>บัญชีผู้ใช้งาน</span><h1>สวัสดี, {user.full_name}</h1><p>คุณเข้าสู่ระบบเรียบร้อยแล้ว</p></div>
    <div className={styles.accountCard}>
      <div className={styles.accountTop}><span className={styles.avatar} aria-hidden="true">{Array.from(user.full_name)[0]}</span><div><p className={styles.accountName}>{user.full_name}</p><span className={styles.roleBadge}>{ROLES[user.role]}</span></div></div>
      <dl className={styles.accountDetails}><div><dt>อีเมล</dt><dd>{user.email}</dd></div><div><dt>บทบาท</dt><dd>{ROLES[user.role]}</dd></div></dl>
    </div>
    {error && <div className={styles.errorBox} role="alert"><p>{error}</p><Link href="/login">เข้าสู่ระบบใหม่</Link></div>}
    <button className={styles.secondaryButton} onClick={signOut} disabled={busy}>{busy ? "กำลังออกจากระบบ…" : "ออกจากระบบ"}</button>
  </AuthShell>;
}
