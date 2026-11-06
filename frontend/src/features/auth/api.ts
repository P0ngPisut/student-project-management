export type AuthUser = { id: string; full_name: string; email: string; role: "student" | "advisor" | "coordinator" };
type FieldError = { field: string; code: string };
const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class AuthApiError extends Error {
  constructor(public readonly status: number, public readonly code: string, public readonly fields: FieldError[] = []) {
    super(code);
    this.name = "AuthApiError";
  }
}

function isUser(value: unknown): value is AuthUser {
  if (!value || typeof value !== "object") return false;
  const user = value as Record<string, unknown>;
  return typeof user.id === "string" && typeof user.full_name === "string" && typeof user.email === "string"
    && ["student", "advisor", "coordinator"].includes(String(user.role));
}

async function request(path: string, init: RequestInit = {}): Promise<AuthUser | undefined> {
  const response = await fetch(`${API_BASE}/api/v1/auth${path}`, { ...init, credentials: "include", cache: "no-store" });
  if (response.status === 204) return;
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const fields: FieldError[] = Array.isArray(body?.error?.fields)
      ? body.error.fields.filter((item: FieldError) => item && typeof item.field === "string" && typeof item.code === "string") : [];
    throw new AuthApiError(response.status, typeof body?.error?.code === "string" ? body.error.code : "REQUEST_FAILED", fields);
  }
  if (!isUser(body?.data)) throw new AuthApiError(502, "INVALID_RESPONSE");
  return body.data;
}

export async function currentUser(signal?: AbortSignal): Promise<AuthUser> {
  const user = await request("/me", { signal });
  if (!user) throw new AuthApiError(502, "INVALID_RESPONSE");
  return user;
}

export function login(email: string, password: string, signal?: AbortSignal) {
  return request("/login", { method: "POST", signal, headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password }) });
}

export function register(fullName: string, email: string, password: string, signal?: AbortSignal) {
  return request("/register", { method: "POST", signal, headers: { "Content-Type": "application/json" }, body: JSON.stringify({ full_name: fullName, email, password }) });
}

export function logout() {
  const csrf = document.cookie.split(";").map((part) => part.trim()).find((part) => part.startsWith("spms_csrf="))?.slice("spms_csrf=".length);
  return request("/logout", { method: "POST", headers: csrf ? { "X-CSRF-Token": csrf } : {} });
}

const MESSAGES: Record<string, string> = {
  INVALID_CREDENTIALS: "อีเมลหรือรหัสผ่านไม่ถูกต้อง กรุณาลองอีกครั้ง",
  EMAIL_ALREADY_REGISTERED: "อีเมลนี้มีบัญชีอยู่แล้ว กรุณาเข้าสู่ระบบ",
  AUTHENTICATION_REQUIRED: "กรุณาเข้าสู่ระบบอีกครั้ง",
  CSRF_INVALID: "ไม่สามารถยืนยันคำขอได้ กรุณาเข้าสู่ระบบอีกครั้ง",
  ORIGIN_NOT_ALLOWED: "ไม่สามารถทำรายการจากหน้านี้ได้ กรุณาติดต่อผู้ดูแลระบบ",
  INTERNAL_ERROR: "ระบบยังไม่พร้อมใช้งาน กรุณาลองอีกครั้ง",
  VALIDATION_ERROR: "กรุณาตรวจสอบข้อมูลในแบบฟอร์ม",
};
export function errorMessage(error: unknown): string {
  return error instanceof AuthApiError ? MESSAGES[error.code] ?? "ไม่สามารถทำรายการได้ กรุณาลองอีกครั้ง" : "ไม่สามารถเชื่อมต่อระบบได้ กรุณาลองอีกครั้ง";
}

const FIELD_MESSAGES: Record<string, string> = {
  REQUIRED: "กรุณากรอกข้อมูลช่องนี้", INVALID_TYPE: "รูปแบบข้อมูลไม่ถูกต้อง",
  EMAIL_FORMAT_INVALID: "กรุณากรอกอีเมลให้ถูกต้อง เช่น student@example.test", EMAIL_TOO_LONG: "อีเมลต้องยาวไม่เกิน 255 ตัวอักษร",
  FULL_NAME_REQUIRED: "กรุณากรอกชื่อและนามสกุล", FULL_NAME_TOO_LONG: "ชื่อต้องยาวไม่เกิน 255 ตัวอักษร",
  PASSWORD_REQUIRED: "กรุณากรอกรหัสผ่าน", PASSWORD_TOO_SHORT: "รหัสผ่านต้องมีอย่างน้อย 8 ตัวอักษร",
  PASSWORD_UPPERCASE_REQUIRED: "รหัสผ่านต้องมีตัวพิมพ์ใหญ่ A–Z อย่างน้อย 1 ตัว", PASSWORD_DIGIT_REQUIRED: "รหัสผ่านต้องมีตัวเลข 0–9 อย่างน้อย 1 ตัว",
};
export function fieldMessages(error: unknown): Record<string, string> {
  if (!(error instanceof AuthApiError)) return {};
  return Object.fromEntries(error.fields.filter((item) => ["full_name", "email", "password"].includes(item.field))
    .map((item) => [item.field, FIELD_MESSAGES[item.code] ?? "กรุณาตรวจสอบข้อมูลช่องนี้"]));
}
export function trimAscii(value: string): string { return value.replace(/^[ \t\n\r\f\v]+|[ \t\n\r\f\v]+$/g, ""); }
