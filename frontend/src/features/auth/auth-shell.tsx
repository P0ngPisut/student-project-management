import type { ReactNode } from "react";
import styles from "./auth.module.css";

export function AuthShell({ children }: { children: ReactNode }) {
  return <main className={styles.shell}>
    <aside className={styles.brand} aria-label="Student Project Management System">
      <div className={styles.wordmark}>
        <svg className={styles.logo} viewBox="0 0 40 40" fill="none" aria-hidden="true">
          <path d="M6 11.5 20 5l14 6.5L20 18 6 11.5Z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
          <path d="m6 19 14 6.5L34 19M6 26.5 20 33l14-6.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span>SPMS<span className={styles.wordmarkSub}>Student Project Management</span></span>
      </div>
      <div className={styles.brandContent}>
        <span className={styles.eyebrow}>STUDENT PROJECT MANAGEMENT SYSTEM</span>
        <h2>พื้นที่สำหรับ<br />โครงงานของคุณ</h2>
        <p>เริ่มต้นด้วยบัญชีของคุณ<br />เพื่อก้าวต่อไปกับทีมและโครงงาน</p>
        <div className={styles.brandLine} aria-hidden="true"><span /><span /><span /></div>
      </div>
      <p className={styles.brandFoot}>เชื่อมการเรียนรู้ สู่การทำงานร่วมกัน</p>
    </aside>
    <section className={styles.content} aria-label="บัญชีผู้ใช้งาน">
      <div className={styles.contentInner}>{children}</div>
      <footer className={styles.footer}>Student Project Management System</footer>
    </section>
  </main>;
}
