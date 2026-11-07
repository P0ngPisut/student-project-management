import { trimAscii } from "@/features/auth/api";

export type Project = { id: string; name: string; description: string | null; team_id: string; created_by: string };
type FieldError = { field: string; code: string };
const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ProjectApiError extends Error {
  constructor(public readonly status: number, public readonly code: string, public readonly fields: FieldError[] = []) {
    super(code); this.name = "ProjectApiError";
  }
}

function object(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
}
function isId(value: unknown): value is string { return typeof value === "string" && /^-?\d+$/.test(value); }

async function request(path: string, init: RequestInit): Promise<Project> {
  const response = await fetch(`${API_BASE}/api/v1/projects${path}`, { ...init, credentials: "include", cache: "no-store" });
  const body = object(await response.json().catch(() => null));
  if (!response.ok) {
    const error = object(body?.error);
    const fields: FieldError[] = [];
    if (Array.isArray(error?.fields)) for (const value of error.fields) {
      const item = object(value);
      if (typeof item?.field === "string" && typeof item?.code === "string") fields.push({ field: item.field, code: item.code });
    }
    throw new ProjectApiError(response.status, typeof error?.code === "string" ? error.code : "REQUEST_FAILED", fields);
  }
  const data = object(body?.data);
  if (!data || !isId(data.id) || !isId(data.team_id) || !isId(data.created_by) || typeof data.name !== "string"
    || !(typeof data.description === "string" || data.description === null)) throw new ProjectApiError(502, "INVALID_RESPONSE");
  return data as Project;
}

export async function currentProject(signal?: AbortSignal): Promise<Project | null> {
  try { return await request("/me", { method: "GET", signal }); }
  catch (cause) {
    if (cause instanceof ProjectApiError && cause.status === 404 && cause.code === "PROJECT_NOT_FOUND") return null;
    throw cause;
  }
}

export function createProject(name: string, description: string, signal?: AbortSignal): Promise<Project> {
  const csrf = document.cookie.split(";").map((part) => part.trim()).find((part) => part.startsWith("spms_csrf="))?.slice("spms_csrf=".length);
  return request("", { method: "POST", signal, headers: { "Content-Type": "application/json", ...(csrf ? { "X-CSRF-Token": csrf } : {}) },
    body: JSON.stringify({ name: trimAscii(name), description: trimAscii(description) || null }) });
}

export function projectErrorMessage(cause: unknown): string {
  if (!(cause instanceof ProjectApiError)) return "ไม่สามารถยืนยันผลการทำรายการได้ กรุณาตรวจสอบโครงงานอีกครั้ง";
  return ({ AUTHENTICATION_REQUIRED: "กรุณาเข้าสู่ระบบอีกครั้ง", PROJECT_ACCESS_FORBIDDEN: "หน้านี้สำหรับโครงงานของทีมนักศึกษาเท่านั้น",
    PROJECT_CREATION_FORBIDDEN: "เฉพาะหัวหน้าทีมเท่านั้นที่สร้างโครงงานได้", TEAM_NOT_FOUND: "คุณยังไม่มีทีม กรุณาไปที่หน้าทีมก่อน",
    PROJECT_ALREADY_EXISTS: "ทีมของคุณมีโครงงานแล้ว กรุณาตรวจสอบโครงงาน", CSRF_INVALID: "ไม่สามารถยืนยันคำขอได้ กรุณาเข้าสู่ระบบอีกครั้ง",
    ORIGIN_NOT_ALLOWED: "ไม่สามารถทำรายการจากหน้านี้ได้ กรุณาติดต่อผู้ดูแลระบบ", VALIDATION_ERROR: "กรุณาตรวจสอบข้อมูลโครงงาน",
    INTERNAL_ERROR: "ระบบยังไม่พร้อมใช้งาน กรุณาลองอีกครั้ง" } as Record<string, string>)[cause.code] ?? "ไม่สามารถทำรายการได้ กรุณาตรวจสอบโครงงานอีกครั้ง";
}

const FIELD_MESSAGES: Record<string, string> = { REQUIRED: "กรุณากรอกชื่อโครงงาน", INVALID_TYPE: "รูปแบบข้อมูลไม่ถูกต้อง",
  PROJECT_NAME_REQUIRED: "กรุณากรอกชื่อโครงงาน", PROJECT_NAME_TOO_LONG: "ชื่อโครงงานต้องยาวไม่เกิน 255 ตัวอักษร",
  PROJECT_TEXT_INVALID: "ข้อความมีอักขระที่ระบบไม่รองรับ กรุณาตรวจสอบอีกครั้ง" };
export function projectFieldMessages(cause: unknown): Record<string, string> {
  if (!(cause instanceof ProjectApiError)) return {};
  return Object.fromEntries(cause.fields.filter((item) => ["name", "description"].includes(item.field))
    .map((item) => [item.field, FIELD_MESSAGES[item.code] ?? "กรุณาตรวจสอบข้อมูลช่องนี้"]));
}
export function validateProjectInput(name: string, description: string): Record<string, string> {
  const fields: Record<string, string> = {};
  if (!trimAscii(name)) fields.name = FIELD_MESSAGES.PROJECT_NAME_REQUIRED;
  else if (Array.from(trimAscii(name)).length > 255) fields.name = FIELD_MESSAGES.PROJECT_NAME_TOO_LONG;
  for (const [key, value] of [["name", name], ["description", description]]) {
    if (value.includes("\x00") || Array.from(value).some((char) => { const point = char.codePointAt(0)!; return point >= 0xd800 && point <= 0xdfff; })) fields[key] = FIELD_MESSAGES.PROJECT_TEXT_INVALID;
  }
  return fields;
}
