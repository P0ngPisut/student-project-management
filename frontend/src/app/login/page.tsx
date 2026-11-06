import { AuthForm } from "@/features/auth/auth-form";

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ registered?: string; reason?: string; logged_out?: string }> }) {
  const params = await searchParams;
  const notice = params.registered === "1" ? "สร้างบัญชีสำเร็จแล้ว กรุณาเข้าสู่ระบบ" : params.logged_out === "1" ? "ออกจากระบบเรียบร้อยแล้ว"
    : params.reason === "session" ? "กรุณาเข้าสู่ระบบเพื่อใช้งาน หรือเข้าสู่ระบบอีกครั้งหากเซสชันหมดอายุ" : "";
  return <AuthForm mode="login" notice={notice} />;
}
