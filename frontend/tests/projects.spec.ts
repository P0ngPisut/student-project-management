import { expect, test, type Page, type Route } from "@playwright/test";
import { randomUUID } from "node:crypto";

const API = "http://localhost:8001";
const PROJECTS = `${API}/api/v1/projects`;
const PASSWORD = "ProjectBrowserFixtureA1";
const ORIGIN = { Origin: "http://localhost:3000" };
let unsafe = 0;
test.beforeEach(async ({ page }) => {
  unsafe = 0;
  await page.route("**/api/v1/**", async (route) => {
    if (new URL(route.request().url()).origin !== API) { unsafe += 1; return route.abort(); }
    await route.continue();
  });
});
test.afterEach(() => { expect(unsafe).toBe(0); });

async function student(page: Page) {
  const email = `project-browser-${randomUUID()}@example.test`;
  const response = await page.request.post(`${API}/api/v1/auth/register`, { headers: ORIGIN,
    data: { full_name: "นักศึกษาทดสอบโครงงาน", email, password: PASSWORD } });
  expect(response.status()).toBe(201);
  return (await response.json()).data as { id: string; email: string };
}
async function login(page: Page, email: string) {
  expect((await page.request.post(`${API}/api/v1/auth/login`, { headers: ORIGIN, data: { email, password: PASSWORD } })).status()).toBe(200);
}
async function headers(page: Page) {
  const token = (await page.context().cookies(API)).find((cookie) => cookie.name === "spms_csrf")?.value ?? "";
  return { ...ORIGIN, "X-CSRF-Token": token };
}
async function leader(page: Page) {
  const user = await student(page);
  await login(page, user.email);
  const team = await page.request.post(`${API}/api/v1/teams`, { headers: await headers(page), data: { name: "ทีมเตรียมโครงงาน" } });
  expect(team.status()).toBe(201);
  return { user, team: (await team.json()).data as { id: string } };
}
async function form(page: Page) {
  const data = await leader(page);
  await page.goto("/projects");
  await expect(page.getByRole("heading", { name: "สร้างโครงงานของทีม", exact: true })).toBeVisible();
  return data;
}
function region(page: Page) { return page.getByRole("region", { name: "โครงงานของทีม", exact: true }); }

test("team navigation, create and refresh use the real Project API", async ({ page }, info) => {
  const { user, team } = await leader(page);
  await page.goto("/teams");
  await page.getByRole("link", { name: "โครงงานของทีม →", exact: true }).click();
  await expect(page).toHaveURL(/\/projects$/);
  let writes = 0; let body: unknown; let csrf = false;
  page.on("request", (request) => {
    if (request.url() === PROJECTS && request.method() === "POST") {
      writes += 1; body = request.postDataJSON(); csrf = Boolean(request.headers()["x-csrf-token"]);
    }
  });
  await page.getByLabel("ชื่อโครงงาน", { exact: true }).fill("  ระบบโครงงานตัวอย่าง  ");
  await page.getByLabel("คำอธิบายโครงงาน", { exact: false }).fill("  รายละเอียดสำหรับทดสอบ  ");
  await page.getByRole("button", { name: "สร้างโครงงาน", exact: true }).click();
  await expect(page.getByRole("heading", { name: "ระบบโครงงานตัวอย่าง", exact: true })).toBeVisible();
  await expect(region(page).getByRole("status")).toContainText("สร้างโครงงานสำเร็จแล้ว");
  expect(body).toEqual({ name: "ระบบโครงงานตัวอย่าง", description: "รายละเอียดสำหรับทดสอบ" });
  expect(csrf).toBe(true);
  const current = await page.request.get(`${PROJECTS}/me`);
  expect(current.status()).toBe(200);
  const data = (await current.json()).data;
  expect(Object.keys(data).sort()).toEqual(["created_by", "description", "id", "name", "team_id"]);
  expect(data.team_id).toBe(team.id); expect(data.created_by).toBe(user.id);
  await page.reload();
  await expect(page.getByRole("heading", { name: "ระบบโครงงานตัวอย่าง", exact: true })).toBeVisible();
  await expect(page.getByText("รายละเอียดสำหรับทดสอบ", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "สร้างโครงงาน", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /ลบ|แก้ไข|เชิญ|ส่งไฟล์/ })).toHaveCount(0);
  expect(writes).toBe(1);
  expect(await page.evaluate(() => [JSON.stringify(Object.entries(localStorage)), JSON.stringify(Object.entries(sessionStorage))].join().includes("ระบบโครงงานตัวอย่าง"))).toBe(false);
  await page.screenshot({ path: info.outputPath("project-current-desktop.png"), fullPage: true });
});

test("no team and member waiting are distinct from leader creation", async ({ page }) => {
  const member = await student(page);
  await login(page, member.email);
  await page.goto("/projects");
  await expect(page.getByRole("heading", { name: "ต้องมีทีมก่อนสร้างโครงงาน", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "สร้างโครงงาน", exact: true })).toHaveCount(0);
  const { user } = await leader(page);
  expect((await page.request.post(`${API}/api/v1/teams/me/members`, { headers: await headers(page), data: { email: member.email } })).status()).toBe(201);
  await login(page, member.email); await page.reload();
  await expect(page.getByRole("heading", { name: "รอหัวหน้าทีมสร้างโครงงาน", exact: true })).toBeVisible();
  await expect(page.getByLabel("ชื่อโครงงาน", { exact: true })).toHaveCount(0);
  expect((await page.request.post(PROJECTS, { headers: await headers(page), data: { name: "Forbidden" } })).status()).toBe(403);
  await login(page, user.email);
  expect((await page.request.post(PROJECTS, { headers: await headers(page), data: { name: "โครงงานที่สมาชิกอ่านได้" } })).status()).toBe(201);
  await login(page, member.email); await page.reload();
  await expect(page.getByRole("heading", { name: "โครงงานที่สมาชิกอ่านได้", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "สร้างโครงงาน", exact: true })).toHaveCount(0);
});

test("client validates blank and Unicode length with optional description", async ({ page }, info) => {
  await form(page);
  let writes = 0;
  page.on("request", (request) => { if (request.url() === PROJECTS && request.method() === "POST") writes += 1; });
  await page.getByLabel("ชื่อโครงงาน", { exact: true }).fill("   ");
  await page.getByRole("button", { name: "สร้างโครงงาน", exact: true }).click();
  await expect(page.getByText("กรุณากรอกชื่อโครงงาน", { exact: true })).toBeVisible();
  await page.getByLabel("ชื่อโครงงาน", { exact: true }).fill("x".repeat(256));
  await page.getByRole("button", { name: "สร้างโครงงาน", exact: true }).click();
  await expect(page.getByText("ชื่อโครงงานต้องยาวไม่เกิน 255 ตัวอักษร", { exact: true })).toBeVisible();
  expect(writes).toBe(0);
  await page.screenshot({ path: info.outputPath("project-create-desktop.png"), fullPage: true });
  const title = "📚".repeat(255);
  await page.getByLabel("ชื่อโครงงาน", { exact: true }).fill(title);
  await page.getByRole("button", { name: "สร้างโครงงาน", exact: true }).click();
  await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible();
  await expect(page.getByText("ยังไม่มีคำอธิบายโครงงาน", { exact: true })).toBeVisible();
  expect(writes).toBe(1);
});

test("409 offers reading the Project created since the form loaded", async ({ page }) => {
  await form(page);
  expect((await page.request.post(PROJECTS, { headers: await headers(page), data: { name: "โครงงานที่สร้างไว้แล้ว" } })).status()).toBe(201);
  await page.getByLabel("ชื่อโครงงาน", { exact: true }).fill("โครงงานซ้ำ");
  await page.getByRole("button", { name: "สร้างโครงงาน", exact: true }).click();
  await expect(region(page).getByRole("alert")).toContainText("ทีมของคุณมีโครงงานแล้ว");
  await page.getByRole("button", { name: "ตรวจสอบโครงงานอีกครั้ง", exact: true }).click();
  await expect(page.getByRole("heading", { name: "โครงงานที่สร้างไว้แล้ว", exact: true })).toBeVisible();
});

test("lost POST response is recovered with GET rather than automatic retry", async ({ page }) => {
  await form(page);
  let writes = 0;
  await page.route("**/api/v1/projects", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    writes += 1; expect((await route.fetch()).status()).toBe(201); await route.abort("failed");
  });
  await page.getByLabel("ชื่อโครงงาน", { exact: true }).fill("โครงงานตรวจสอบผล");
  await page.getByRole("button", { name: "สร้างโครงงาน", exact: true }).click();
  await expect(region(page).getByRole("alert")).toBeVisible();
  await page.getByRole("button", { name: "ตรวจสอบโครงงานอีกครั้ง", exact: true }).click();
  await expect(page.getByRole("heading", { name: "โครงงานตรวจสอบผล", exact: true })).toBeVisible();
  expect(writes).toBe(1);
});

test("network, generic 404 and malformed success never show a create form", async ({ page }) => {
  await form(page);
  for (const mode of ["network", "404", "null"]) {
    const handler = async (route: Route) => {
      if (mode === "network") return route.abort("failed");
      return route.fulfill({ status: mode === "404" ? 404 : 200, contentType: "application/json",
        body: JSON.stringify(mode === "404" ? { error: { code: "NOT_FOUND", message: "DoNotEchoSQLFixture" } } : { data: null }) });
    };
    await page.route("**/api/v1/projects/me", handler);
    await page.reload();
    await expect(region(page).getByRole("alert")).toBeVisible();
    await expect(page.getByLabel("ชื่อโครงงาน", { exact: true })).toHaveCount(0);
    await expect(region(page)).not.toContainText("DoNotEchoSQLFixture");
    await page.unroute("**/api/v1/projects/me", handler);
    await page.getByRole("button", { name: "ลองอีกครั้ง", exact: true }).click();
    await expect(page.getByLabel("ชื่อโครงงาน", { exact: true })).toBeVisible();
  }
});

test("pending Project form submits once", async ({ page }) => {
  await form(page);
  let release = () => {};
  const hold = new Promise<void>((resolve) => { release = resolve; });
  let writes = 0;
  await page.route("**/api/v1/projects", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    writes += 1; const response = await route.fetch(); await hold; await route.fulfill({ response });
  });
  await page.getByLabel("ชื่อโครงงาน", { exact: true }).fill("โครงงานส่งครั้งเดียว");
  await page.getByRole("button", { name: "สร้างโครงงาน", exact: true }).click();
  try {
    await expect(page.getByRole("button", { name: "กำลังสร้างโครงงาน…", exact: true })).toBeDisabled();
    await page.locator("form").evaluate((form: HTMLFormElement) => form.requestSubmit());
    expect(writes).toBe(1);
  } finally { release(); }
  await expect(page.getByRole("heading", { name: "โครงงานส่งครั้งเดียว", exact: true })).toBeVisible();
  expect(writes).toBe(1);
});

test("CSRF rejection and lost session do not report successful creation", async ({ page }) => {
  await form(page);
  await page.context().clearCookies({ name: "spms_csrf" });
  await page.getByLabel("ชื่อโครงงาน", { exact: true }).fill("ไม่ควรสร้างโครงงาน");
  await page.getByRole("button", { name: "สร้างโครงงาน", exact: true }).click();
  await expect(region(page).getByRole("alert")).toContainText("ไม่สามารถยืนยันคำขอได้");
  await expect(page.getByRole("link", { name: "เข้าสู่ระบบใหม่", exact: true })).toBeVisible();
  expect((await page.request.get(`${PROJECTS}/me`)).status()).toBe(404);
  await page.context().clearCookies(); await page.reload();
  await expect(page).toHaveURL(/\/login\?reason=session$/);
});

test("mobile Project creation and card fit without horizontal overflow", async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await form(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByLabel("ชื่อโครงงาน", { exact: true }).fill("โครงงานบนโทรศัพท์");
  await page.getByLabel("คำอธิบายโครงงาน", { exact: false }).fill("รายละเอียดโครงงานสำหรับแสดงผลบนโทรศัพท์");
  await page.screenshot({ path: info.outputPath("project-create-mobile.png"), fullPage: true });
  await page.getByRole("button", { name: "สร้างโครงงาน", exact: true }).click();
  await expect(page.getByRole("heading", { name: "โครงงานบนโทรศัพท์", exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("project-current-mobile.png"), fullPage: true });
});
