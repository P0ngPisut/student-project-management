import { expect, test, type Page, type Route } from "@playwright/test";
import { randomUUID } from "node:crypto";

const API = "http://localhost:8001";
const TEAM_API = `${API}/api/v1/projects/me/advisor-invitations`;
const INBOX = `${API}/api/v1/advisor-invitations/me`;
const TEAM_PAGE = "/projects/advisor-invitations";
const ADVISOR_PAGE = "/advisor/invitations";
const ORIGIN = { Origin: "http://localhost:3000" };
const STUDENT_PASSWORD = "InvitationBrowserFixtureA1";
const ADVISOR_PASSWORD = "AdvisorBrowserFixtureA1";
const tag = process.env.SPMS_ADVISOR_FIXTURE_TAG;
if (!tag || !/^[a-f0-9]{32}$/.test(tag)) throw new Error("Run invitation browser tests through npm run test:e2e for rollback-only staff fixtures");
const staffEmail = (label: string) => `advisor-browser-${tag}-${label}@example.test`;
const advisorName = (label: string) => `อาจารย์ทดสอบ ${label} ${tag!.slice(0, 6)}`;
let unsafe = 0;

test.beforeEach(async ({ page }) => {
  unsafe = 0;
  await page.route("**/api/v1/**", async (route) => {
    if (new URL(route.request().url()).origin !== API) { unsafe += 1; return route.abort(); }
    await route.continue();
  });
});
test.afterEach(() => { expect(unsafe).toBe(0); });
async function login(page: Page, email: string, password = STUDENT_PASSWORD) {
  expect((await page.request.post(`${API}/api/v1/auth/login`, { headers: ORIGIN, data: { email, password } })).status()).toBe(200);
}
async function headers(page: Page) {
  const csrf = (await page.context().cookies(API)).find((cookie) => cookie.name === "spms_csrf")?.value ?? "";
  return { ...ORIGIN, "X-CSRF-Token": csrf };
}
async function register(page: Page) {
  const email = `invitation-browser-${randomUUID()}@example.test`;
  const response = await page.request.post(`${API}/api/v1/auth/register`, { headers: ORIGIN,
    data: { full_name: "นักศึกษาทดสอบคำเชิญ", email, password: STUDENT_PASSWORD } });
  expect(response.status()).toBe(201);
  return email;
}
async function setup(page: Page) {
  const email = await register(page);
  await login(page, email);
  expect((await page.request.post(`${API}/api/v1/teams`, { headers: await headers(page), data: { name: "ทีมคำเชิญทดสอบ" } })).status()).toBe(201);
  const name = `โครงงานคำเชิญ ${randomUUID().slice(0, 8)}`;
  expect((await page.request.post(`${API}/api/v1/projects`, { headers: await headers(page), data: { name, description: "รายละเอียดที่ต้องซ่อนหลังสิ้นสุดคำเชิญ" } })).status()).toBe(201);
  await page.goto(TEAM_PAGE);
  await expect(page.getByLabel("เลือกอาจารย์ที่ปรึกษา", { exact: true })).toBeVisible();
  return { email, name };
}
async function send(page: Page, label = "A") {
  await page.getByLabel("เลือกอาจารย์ที่ปรึกษา", { exact: true }).selectOption({ label: advisorName(label) });
  await page.getByRole("button", { name: "ส่งคำเชิญ", exact: true }).click();
  await expect(page.getByRole("button", { name: "ยกเลิกคำเชิญ", exact: true })).toBeVisible();
  const response = await page.request.get(TEAM_API);
  expect(response.status()).toBe(200);
  return (await response.json()).data[0] as { id: string; status: string };
}
function teamRegion(page: Page) { return page.getByRole("region", { name: "คำเชิญอาจารย์ของทีม", exact: true }); }
function advisorRegion(page: Page) { return page.getByRole("region", { name: "คำเชิญของอาจารย์", exact: true }); }
function card(page: Page, id: string) { return page.getByTestId(`invitation-${id}`); }

test("leader selects advisor, advisor accepts, team refresh keeps accepted and cannot replace", async ({ page }, info) => {
  const owner = await setup(page);
  await page.goto("/projects");
  await page.getByRole("link", { name: "คำเชิญอาจารย์ที่ปรึกษา →", exact: true }).click();
  await expect(page).toHaveURL(/\/projects\/advisor-invitations$/);
  let sent: unknown; let csrfSent = false;
  page.on("request", (request) => {
    if (request.url() === TEAM_API && request.method() === "POST") { sent = request.postDataJSON(); csrfSent = Boolean(request.headers()["x-csrf-token"]); }
  });
  const invitation = await send(page);
  expect(Object.keys(sent as object)).toEqual(["advisor_id"]); expect(csrfSent).toBe(true);
  await page.reload(); await expect(card(page, invitation.id)).toContainText("รอตอบรับ");
  await login(page, staffEmail("a"), ADVISOR_PASSWORD);
  await page.goto("/");
  await page.getByRole("link", { name: "คำเชิญของฉัน →", exact: true }).click();
  const target = card(page, invitation.id);
  await expect(target).toContainText(owner.name);
  await expect(target).toContainText("ทีมคำเชิญทดสอบ");
  await target.getByRole("button", { name: "ตอบรับ", exact: true }).click();
  await expect(target).toContainText("ตอบรับแล้ว");
  await expect(target.getByRole("button")).toHaveCount(0);
  await login(page, owner.email); await page.goto(TEAM_PAGE);
  await expect(card(page, invitation.id)).toContainText("ตอบรับแล้ว");
  await expect(page.getByLabel("เลือกอาจารย์ที่ปรึกษา", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "ยกเลิกคำเชิญ", exact: true })).toHaveCount(0);
  await page.screenshot({ path: info.outputPath("invitation-team-accepted-desktop.png"), fullPage: true });
});

test("rejection removes all live Project context and leader can invite a different advisor", async ({ page }) => {
  const owner = await setup(page); const invitation = await send(page);
  await login(page, staffEmail("a"), ADVISOR_PASSWORD); await page.goto(ADVISOR_PAGE);
  await card(page, invitation.id).getByRole("button", { name: "ปฏิเสธ", exact: true }).click();
  await expect(card(page, invitation.id)).toContainText("ปฏิเสธแล้ว");
  await expect(card(page, invitation.id)).not.toContainText(owner.name);
  await expect(card(page, invitation.id)).not.toContainText("รายละเอียดที่ต้องซ่อน");
  await page.reload(); await expect(card(page, invitation.id)).not.toContainText(owner.name);
  const inbox = (await (await page.request.get(INBOX)).json()).data;
  expect(inbox.find((item: { id: string }) => item.id === invitation.id).project_context).toBeNull();
  await login(page, owner.email); await page.goto(TEAM_PAGE);
  await expect(card(page, invitation.id)).toContainText("ปฏิเสธแล้ว");
  const second = await send(page, "B");
  expect(second.id).not.toBe(invitation.id);
  await expect(teamRegion(page).getByRole("listitem")).toHaveCount(2);
});

test("leader cancellation removes advisor Project context and keeps history", async ({ page }) => {
  const owner = await setup(page); const invitation = await send(page);
  await card(page, invitation.id).getByRole("button", { name: "ยกเลิกคำเชิญ", exact: true }).click();
  await expect(card(page, invitation.id)).toContainText("ยกเลิกแล้ว");
  await expect(page.getByLabel("เลือกอาจารย์ที่ปรึกษา", { exact: true })).toBeVisible();
  await login(page, staffEmail("a"), ADVISOR_PASSWORD); await page.goto(ADVISOR_PAGE);
  await expect(card(page, invitation.id)).toContainText("ยกเลิกแล้ว");
  await expect(card(page, invitation.id)).not.toContainText(owner.name);
  await expect(card(page, invitation.id).getByRole("button")).toHaveCount(0);
});

test("member reads history without send cancel or candidate access", async ({ page }) => {
  await setup(page); const invitation = await send(page);
  const member = await register(page);
  expect((await page.request.post(`${API}/api/v1/teams/me/members`, { headers: await headers(page), data: { email: member } })).status()).toBe(201);
  await login(page, member); await page.goto(TEAM_PAGE);
  await expect(card(page, invitation.id)).toContainText("รอตอบรับ");
  await expect(page.getByRole("button", { name: "ยกเลิกคำเชิญ", exact: true })).toHaveCount(0);
  await expect(page.getByLabel("เลือกอาจารย์ที่ปรึกษา", { exact: true })).toHaveCount(0);
  expect((await page.request.get(`${API}/api/v1/projects/me/advisor-candidates`)).status()).toBe(403);
});

test("other advisor cannot see or resolve the invitation and roles stay separated", async ({ page }) => {
  await setup(page); const invitation = await send(page);
  await login(page, staffEmail("b"), ADVISOR_PASSWORD); await page.goto(ADVISOR_PAGE);
  await expect(advisorRegion(page).getByRole("heading", { name: "คำเชิญของคุณ", exact: true })).toBeVisible();
  await expect(card(page, invitation.id)).toHaveCount(0);
  const response = await page.request.post(`${API}/api/v1/advisor-invitations/${invitation.id}/respond`, { headers: await headers(page), data: { decision: "accepted" } });
  expect(response.status()).toBe(404);
  await page.goto(TEAM_PAGE);
  await expect(page.getByRole("heading", { name: "บทบาทของคุณไม่สามารถใช้หน้านี้ได้", exact: true })).toBeVisible();
  await login(page, staffEmail("coordinator"), ADVISOR_PASSWORD); await page.goto("/");
  await expect(page.getByRole("link", { name: "คำเชิญของฉัน →", exact: true })).toHaveCount(0);
  await page.goto(ADVISOR_PAGE);
  await expect(page.getByRole("heading", { name: "บทบาทของคุณไม่สามารถใช้หน้านี้ได้", exact: true })).toBeVisible();
});

test("empty advisor candidates and candidate network failures never fabricate a list", async ({ page }) => {
  await setup(page);
  const empty = async (route: Route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ data: [] }) });
  await page.route("**/api/v1/projects/me/advisor-candidates", empty); await page.reload();
  await expect(page.getByText("ยังไม่มีบัญชีอาจารย์ให้เลือก กรุณาให้ผู้ดูแลเตรียมบัญชีก่อน", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "ส่งคำเชิญ", exact: true })).toHaveCount(0);
  await page.unroute("**/api/v1/projects/me/advisor-candidates", empty);
  const failure = async (route: Route) => route.abort("failed");
  await page.route("**/api/v1/projects/me/advisor-candidates", failure); await page.reload();
  await expect(teamRegion(page).getByRole("alert")).toBeVisible();
  await expect(page.getByLabel("เลือกอาจารย์ที่ปรึกษา", { exact: true })).toHaveCount(0);
  await page.unroute("**/api/v1/projects/me/advisor-candidates", failure);
  await page.getByRole("button", { name: "ลองอีกครั้ง", exact: true }).click();
  await expect(page.getByLabel("เลือกอาจารย์ที่ปรึกษา", { exact: true })).toBeVisible();
});

test("failed history and malformed success are errors rather than empty history", async ({ page }) => {
  await setup(page);
  for (const malformed of [false, true]) {
    const handler = async (route: Route) => route.request().method() === "GET"
      ? malformed ? route.fulfill({ status: 200, contentType: "application/json", body: '{"data":null}' }) : route.abort("failed") : route.fallback();
    await page.route("**/api/v1/projects/me/advisor-invitations", handler); await page.reload();
    await expect(teamRegion(page).getByRole("alert")).toBeVisible();
    await expect(page.getByText("ยังไม่มีคำเชิญ", { exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "ส่งคำเชิญ", exact: true })).toHaveCount(0);
    await page.unroute("**/api/v1/projects/me/advisor-invitations", handler);
    await page.getByRole("button", { name: "ลองอีกครั้ง", exact: true }).click();
    await expect(page.getByLabel("เลือกอาจารย์ที่ปรึกษา", { exact: true })).toBeVisible();
  }
});

test("lost send response recovers through history with no automatic POST retry", async ({ page }) => {
  await setup(page); let writes = 0;
  await page.route("**/api/v1/projects/me/advisor-invitations", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    writes += 1; expect((await route.fetch()).status()).toBe(201); await route.abort("failed");
  });
  await page.getByLabel("เลือกอาจารย์ที่ปรึกษา", { exact: true }).selectOption({ label: advisorName("A") });
  await page.getByRole("button", { name: "ส่งคำเชิญ", exact: true }).click();
  await expect(teamRegion(page).getByRole("alert")).toBeVisible();
  await page.getByRole("button", { name: "ตรวจประวัติอีกครั้ง", exact: true }).click();
  await expect(page.getByRole("button", { name: "ยกเลิกคำเชิญ", exact: true })).toBeVisible();
  expect(writes).toBe(1);
});

test("pending send and pending response are each submitted only once", async ({ page }) => {
  const owner = await setup(page); let sendWrites = 0;
  let release = () => {}; let hold = new Promise<void>((resolve) => { release = resolve; });
  await page.route("**/api/v1/projects/me/advisor-invitations", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    sendWrites += 1; const response = await route.fetch(); await hold; await route.fulfill({ response });
  });
  await page.getByLabel("เลือกอาจารย์ที่ปรึกษา", { exact: true }).selectOption({ label: advisorName("A") });
  await page.getByRole("button", { name: "ส่งคำเชิญ", exact: true }).click();
  try {
    await expect(page.getByRole("button", { name: "กำลังส่งคำเชิญ…", exact: true })).toBeDisabled();
    await page.locator("form").evaluate((form: HTMLFormElement) => form.requestSubmit()); expect(sendWrites).toBe(1);
  } finally { release(); }
  await expect(page.getByRole("button", { name: "ยกเลิกคำเชิญ", exact: true })).toBeVisible();
  const invitation = (await (await page.request.get(TEAM_API)).json()).data[0];
  await login(page, staffEmail("a"), ADVISOR_PASSWORD); await page.goto(ADVISOR_PAGE);
  let respondWrites = 0; hold = new Promise<void>((resolve) => { release = resolve; });
  await page.route(`**/api/v1/advisor-invitations/${invitation.id}/respond`, async (route) => {
    respondWrites += 1; const response = await route.fetch(); await hold; await route.fulfill({ response });
  });
  await card(page, invitation.id).getByRole("button", { name: "ตอบรับ", exact: true }).click();
  try {
    await expect(card(page, invitation.id).getByRole("button", { name: "ตอบรับ", exact: true })).toBeDisabled();
    await expect(card(page, invitation.id).getByRole("button", { name: "ปฏิเสธ", exact: true })).toBeDisabled();
    expect(respondWrites).toBe(1);
  } finally { release(); }
  await expect(card(page, invitation.id)).toContainText("ตอบรับแล้ว");
  expect(sendWrites).toBe(1); expect(respondWrites).toBe(1); expect(owner.email).toContain("@example.test");
});

test("stale cancellation shows resolved conflict then loads accepted state", async ({ page }) => {
  const owner = await setup(page); const invitation = await send(page);
  await login(page, staffEmail("a"), ADVISOR_PASSWORD);
  expect((await page.request.post(`${API}/api/v1/advisor-invitations/${invitation.id}/respond`, { headers: await headers(page), data: { decision: "accepted" } })).status()).toBe(200);
  await login(page, owner.email);
  await page.getByRole("button", { name: "ยกเลิกคำเชิญ", exact: true }).click();
  await expect(teamRegion(page).getByRole("alert")).toContainText("คำเชิญนี้สิ้นสุดแล้ว");
  await page.getByRole("button", { name: "ตรวจประวัติอีกครั้ง", exact: true }).click();
  await expect(card(page, invitation.id)).toContainText("ตอบรับแล้ว");
});

test("CSRF rejection and lost session never report a successful invitation", async ({ page }) => {
  await setup(page); await page.context().clearCookies({ name: "spms_csrf" });
  await page.getByLabel("เลือกอาจารย์ที่ปรึกษา", { exact: true }).selectOption({ label: advisorName("A") });
  await page.getByRole("button", { name: "ส่งคำเชิญ", exact: true }).click();
  await expect(teamRegion(page).getByRole("alert")).toContainText("ไม่สามารถยืนยันคำขอได้");
  await expect(page.getByRole("link", { name: "เข้าสู่ระบบใหม่", exact: true })).toBeVisible();
  expect((await (await page.request.get(TEAM_API)).json()).data).toEqual([]);
  await page.context().clearCookies(); await page.reload(); await expect(page).toHaveURL(/\/login\?reason=session$/);
});

test("mobile advisor response and team history fit without horizontal overflow", async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const owner = await setup(page); const invitation = await send(page);
  await page.screenshot({ path: info.outputPath("invitation-team-mobile.png"), fullPage: true });
  await login(page, staffEmail("a"), ADVISOR_PASSWORD); await page.goto(ADVISOR_PAGE);
  await expect(card(page, invitation.id)).toContainText(owner.name);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("invitation-advisor-mobile.png"), fullPage: true });
  await card(page, invitation.id).getByRole("button", { name: "ปฏิเสธ", exact: true }).click();
  await expect(card(page, invitation.id)).toContainText("ปฏิเสธแล้ว");
});
