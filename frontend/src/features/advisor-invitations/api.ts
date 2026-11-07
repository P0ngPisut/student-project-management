export type InvitationStatus = "pending" | "accepted" | "rejected" | "cancelled";
export type Candidate = { id: string; full_name: string };
type BaseInvitation = { id: string; status: InvitationStatus; sent_at: string; resolved_at: string | null };
export type TeamInvitation = BaseInvitation & { advisor: Candidate };
export type AdvisorInvitation = BaseInvitation & { project_context: { team_name: string; project_name: string; project_description: string | null } | null };
const BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
const TEAM = "/api/v1/projects/me/advisor-invitations";

export class InvitationApiError extends Error {
  constructor(public readonly status: number, public readonly code: string) { super(code); this.name = "InvitationApiError"; }
}
function object(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
}
function id(value: unknown): value is string {
  return typeof value === "string" && /^[1-9]\d{0,18}$/.test(value) && (value.length < 19 || value <= "9223372036854775807");
}
function time(value: unknown): value is string {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}T/.test(value) && /(Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value));
}
function candidate(value: unknown): value is Candidate {
  const row = object(value); return Boolean(row && id(row.id) && typeof row.full_name === "string");
}
function baseInvitation(value: unknown): value is BaseInvitation {
  const row = object(value);
  return Boolean(row && id(row.id) && ["pending", "accepted", "rejected", "cancelled"].includes(String(row.status))
    && time(row.sent_at) && (row.status === "pending" ? row.resolved_at === null : time(row.resolved_at)));
}
function teamInvitation(value: unknown): value is TeamInvitation {
  return baseInvitation(value) && candidate(object(value)?.advisor);
}
function advisorInvitation(value: unknown): value is AdvisorInvitation {
  if (!baseInvitation(value)) return false;
  const row = object(value)!;
  if (row.status === "rejected" || row.status === "cancelled") return row.project_context === null;
  const context = object(row.project_context);
  return Boolean(context && typeof context.team_name === "string" && typeof context.project_name === "string"
    && (context.project_description === null || typeof context.project_description === "string"));
}
function invalid(): never { throw new InvitationApiError(502, "INVALID_RESPONSE"); }
function array<T>(value: unknown, check: (item: unknown) => item is T): T[] {
  if (!Array.isArray(value) || !value.every(check)) return invalid();
  return value;
}
async function request(path: string, signal?: AbortSignal, body?: object): Promise<unknown> {
  const csrf = typeof document === "undefined" ? undefined : document.cookie.split(";").map((part) => part.trim()).find((part) => part.startsWith("spms_csrf="))?.slice("spms_csrf=".length);
  const response = await fetch(`${BASE}${path}`, { method: body ? "POST" : "GET", signal, credentials: "include", cache: "no-store",
    ...(body ? { headers: { "Content-Type": "application/json", ...(csrf ? { "X-CSRF-Token": csrf } : {}) }, body: JSON.stringify(body) } : {}) });
  const json = object(await response.json().catch(() => null));
  if (!response.ok) {
    const error = object(json?.error);
    throw new InvitationApiError(response.status, typeof error?.code === "string" ? error.code : "REQUEST_FAILED");
  }
  if (!json || !("data" in json)) return invalid();
  return json.data;
}
export async function candidates(signal?: AbortSignal): Promise<Candidate[]> {
  return array(await request("/api/v1/projects/me/advisor-candidates", signal), candidate);
}
export async function teamHistory(signal?: AbortSignal): Promise<TeamInvitation[]> {
  return array(await request(TEAM, signal), teamInvitation);
}
export async function advisorHistory(signal?: AbortSignal): Promise<AdvisorInvitation[]> {
  return array(await request("/api/v1/advisor-invitations/me", signal), advisorInvitation);
}
export async function sendInvitation(advisor: string, signal?: AbortSignal): Promise<TeamInvitation> {
  if (!id(advisor)) return invalid();
  const data = await request(TEAM, signal, { advisor_id: advisor });
  if (!teamInvitation(data) || data.status !== "pending") return invalid();
  return data;
}
export async function cancelInvitation(invitation: string, signal?: AbortSignal): Promise<TeamInvitation> {
  if (!id(invitation)) return invalid();
  const data = await request(`/api/v1/advisor-invitations/${invitation}/cancel`, signal, {});
  if (!teamInvitation(data) || data.status !== "cancelled") return invalid();
  return data;
}
export async function respondInvitation(invitation: string, decision: "accepted" | "rejected", signal?: AbortSignal): Promise<AdvisorInvitation> {
  if (!id(invitation)) return invalid();
  const data = await request(`/api/v1/advisor-invitations/${invitation}/respond`, signal, { decision });
  if (!advisorInvitation(data) || data.status !== decision) return invalid();
  return data;
}
export const STATUS_TEXT = { pending: "รอตอบรับ", accepted: "ตอบรับแล้ว", rejected: "ปฏิเสธแล้ว", cancelled: "ยกเลิกแล้ว" };
export function invitationErrorMessage(cause: unknown): string {
  if (!(cause instanceof InvitationApiError)) return "ไม่สามารถยืนยันผลการทำรายการได้ กรุณาตรวจประวัติอีกครั้ง";
  return ({ AUTHENTICATION_REQUIRED: "กรุณาเข้าสู่ระบบอีกครั้ง", INVITATION_ACCESS_FORBIDDEN: "บทบาทของคุณไม่สามารถใช้หน้านี้ได้",
    INVITATION_ACTION_FORBIDDEN: "เฉพาะหัวหน้าทีมปัจจุบันเท่านั้นที่ทำรายการนี้ได้", ADVISOR_NOT_FOUND: "ไม่พบอาจารย์ที่เชิญได้",
    INVITATION_NOT_FOUND: "ไม่พบคำเชิญที่คุณเข้าถึงได้", INVITATION_ALREADY_PENDING: "โครงงานมีคำเชิญที่รอตอบรับอยู่แล้ว",
    ADVISOR_ALREADY_ACCEPTED: "โครงงานมีอาจารย์ตอบรับแล้ว ไม่สามารถเปลี่ยนอาจารย์ได้", INVITATION_ALREADY_RESOLVED: "คำเชิญนี้สิ้นสุดแล้ว กรุณาโหลดประวัติใหม่",
    INVITATION_CONFLICT: "ข้อมูลคำเชิญเปลี่ยนแปลง กรุณาโหลดประวัติใหม่", CSRF_INVALID: "ไม่สามารถยืนยันคำขอได้ กรุณาเข้าสู่ระบบอีกครั้ง",
    ORIGIN_NOT_ALLOWED: "ไม่สามารถทำรายการจากหน้านี้ได้ กรุณาติดต่อผู้ดูแลระบบ", VALIDATION_ERROR: "กรุณาตรวจสอบข้อมูลคำเชิญ",
    INTERNAL_ERROR: "ระบบยังไม่พร้อมใช้งาน กรุณาลองอีกครั้ง" } as Record<string, string>)[cause.code] ?? "ไม่สามารถทำรายการได้ กรุณาตรวจประวัติอีกครั้ง";
}
