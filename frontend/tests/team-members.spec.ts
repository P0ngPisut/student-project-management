import { expect, test, type Page, type Route } from "@playwright/test";
import { randomUUID } from "node:crypto";

const API = "http://localhost:8001";
const MEMBERS_URL = `${API}/api/v1/teams/me/members`;
const PASSWORD = "MembersBrowserFixtureA1";
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

async function register(page: Page, name: string) {
  const email = `members-browser-${randomUUID()}@example.test`;
  const response = await page.request.post(`${API}/api/v1/auth/register`, {
    headers: ORIGIN, data: { full_name: name, email, password: PASSWORD },
  });
  expect(response.status()).toBe(201);
  return (await response.json()).data as { id: string; email: string; full_name: string };
}
async function login(page: Page, email: string) {
  expect((await page.request.post(`${API}/api/v1/auth/login`, { headers: ORIGIN, data: { email, password: PASSWORD } })).status()).toBe(200);
}
async function csrf(page: Page) {
  return (await page.context().cookies(API)).find((cookie) => cookie.name === "spms_csrf")?.value ?? "";
}
async function leader(page: Page) {
  const user = await register(page, "หัวหน้าทดสอบสมาชิก");
  await login(page, user.email);
  expect((await page.request.post(`${API}/api/v1/teams`, { headers: { ...ORIGIN, "X-CSRF-Token": await csrf(page) }, data: { name: "ทีมทดสอบสมาชิก" } })).status()).toBe(201);
  await page.goto("/teams");
  await expect(page.getByRole("button", { name: "เพิ่มสมาชิก", exact: true })).toBeVisible();
  return user;
}

test("leader adds by email, list survives refresh and exposes no email", async ({ page }, info) => {
  await leader(page);
  const target = await register(page, "นักศึกษาสมาชิกใหม่");
  let writes = 0;
  let payload: unknown;
  let csrfSent = false;
  page.on("request", (request) => {
    if (request.url() === MEMBERS_URL && request.method() === "POST") {
      writes += 1; payload = request.postDataJSON(); csrfSent = Boolean(request.headers()["x-csrf-token"]);
    }
  });
  await page.getByLabel("อีเมลนักศึกษาที่ต้องการเพิ่ม").fill(`  ${target.email.toUpperCase()}  `);
  await page.getByRole("button", { name: "เพิ่มสมาชิก", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "เพิ่มสมาชิกสำเร็จแล้ว" })).toBeVisible();
  const list = page.getByRole("list", { name: "รายชื่อสมาชิกทีม" });
  await expect(list.getByRole("listitem")).toHaveCount(2);
  await expect(list.getByText(target.full_name, { exact: true })).toBeVisible();
  expect(payload).toEqual({ email: target.email.toUpperCase() });
  expect(csrfSent).toBe(true);
  const response = await page.request.get(MEMBERS_URL);
  const data = (await response.json()).data;
  expect(data.every((member: object) => Object.keys(member).sort().join() === "full_name,id,role,user_id")).toBe(true);
  expect(data[1].user_id).toBe(target.id);
  await page.reload();
  await expect(list.getByRole("listitem")).toHaveCount(2);
  await expect(list).not.toContainText(target.email);
  expect(writes).toBe(1);
  expect(await page.evaluate(() => [JSON.stringify(Object.entries(localStorage)), JSON.stringify(Object.entries(sessionStorage))].join().includes("นักศึกษาสมาชิกใหม่"))).toBe(false);
  await page.screenshot({ path: info.outputPath("members-desktop.png"), fullPage: true });
});

test("member can read team but has no add form and forged write is forbidden", async ({ page }) => {
  await leader(page);
  const target = await register(page, "สมาชิกอ่านอย่างเดียว");
  expect((await page.request.post(MEMBERS_URL, { headers: { ...ORIGIN, "X-CSRF-Token": await csrf(page) }, data: { email: target.email } })).status()).toBe(201);
  await login(page, target.email);
  await page.reload();
  const list = page.getByRole("list", { name: "รายชื่อสมาชิกทีม" });
  await expect(list.getByRole("listitem")).toHaveCount(2);
  await expect(list).toContainText("สมาชิกอ่านอย่างเดียว");
  await expect(page.getByLabel("อีเมลนักศึกษาที่ต้องการเพิ่ม")).toHaveCount(0);
  const response = await page.request.post(MEMBERS_URL, { headers: { ...ORIGIN, "X-CSRF-Token": await csrf(page), "X-Role": "leader" }, data: { email: "missing@example.test" } });
  expect(response.status()).toBe(403);
  expect((await response.json()).error.code).toBe("TEAM_MEMBER_ADDITION_FORBIDDEN");
});

test("missing account, unavailable member and invalid email show fixed errors", async ({ page }) => {
  const user = await leader(page);
  const input = page.getByLabel("อีเมลนักศึกษาที่ต้องการเพิ่ม");
  const submit = page.getByRole("button", { name: "เพิ่มสมาชิก", exact: true });
  await input.fill("   "); await submit.click();
  await expect(page.getByText("กรุณากรอกอีเมลของนักศึกษา", { exact: true })).toBeVisible();
  await input.fill("bad-email"); await submit.click();
  await expect(page.getByText("กรุณากรอกอีเมลให้ถูกต้อง เช่น student@example.test", { exact: true })).toBeVisible();
  await input.fill(`missing-${randomUUID()}@example.test`); await submit.click();
  await expect(page.getByRole("region", { name: "สมาชิกในทีม" }).getByRole("alert")).toContainText("ไม่พบนักศึกษาที่เพิ่มได้ด้วยอีเมลนี้");
  await input.fill(user.email); await submit.click();
  await expect(page.getByRole("region", { name: "สมาชิกในทีม" }).getByRole("alert")).toContainText("มีทีมอยู่แล้ว");
  await expect(page.getByRole("list", { name: "รายชื่อสมาชิกทีม" }).getByRole("listitem")).toHaveCount(1);
});

test("pending member form sends only one POST", async ({ page }) => {
  await leader(page);
  const target = await register(page, "สมาชิกส่งครั้งเดียว");
  let release = () => {};
  const hold = new Promise<void>((resolve) => { release = resolve; });
  let writes = 0;
  await page.route("**/api/v1/teams/me/members", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    writes += 1;
    const response = await route.fetch();
    await hold; await route.fulfill({ response });
  });
  await page.getByLabel("อีเมลนักศึกษาที่ต้องการเพิ่ม").fill(target.email);
  await page.getByRole("button", { name: "เพิ่มสมาชิก", exact: true }).click();
  try {
    await expect(page.getByRole("button", { name: "กำลังเพิ่มสมาชิก…", exact: true })).toBeDisabled();
    await page.locator('form').evaluate((form: HTMLFormElement) => form.requestSubmit());
    expect(writes).toBe(1);
  } finally { release(); }
  await expect(page.getByText(target.full_name, { exact: true })).toBeVisible();
  expect(writes).toBe(1);
});

test("lost add response recovers through GET without automatic POST retry", async ({ page }) => {
  await leader(page);
  const target = await register(page, "สมาชิกตรวจสอบผล");
  let writes = 0;
  await page.route("**/api/v1/teams/me/members", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    writes += 1;
    expect((await route.fetch()).status()).toBe(201);
    await route.abort("failed");
  });
  await page.getByLabel("อีเมลนักศึกษาที่ต้องการเพิ่ม").fill(target.email);
  await page.getByRole("button", { name: "เพิ่มสมาชิก", exact: true }).click();
  await expect(page.getByRole("region", { name: "สมาชิกในทีม" }).getByRole("alert")).toBeVisible();
  await page.getByRole("button", { name: "ตรวจสอบรายชื่ออีกครั้ง", exact: true }).click();
  await expect(page.getByRole("list", { name: "รายชื่อสมาชิกทีม" })).toContainText(target.full_name);
  expect(writes).toBe(1);
});

test("failed member GET does not show an empty list or an add form", async ({ page }) => {
  await leader(page);
  const handler = async (route: Route) => {
    if (route.request().method() === "GET") return route.abort("failed");
    return route.fallback();
  };
  await page.route("**/api/v1/teams/me/members", handler);
  await page.reload();
  await expect(page.getByRole("region", { name: "สมาชิกในทีม" }).getByRole("alert")).toBeVisible();
  await expect(page.getByRole("list", { name: "รายชื่อสมาชิกทีม" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "เพิ่มสมาชิก", exact: true })).toHaveCount(0);
  await page.unroute("**/api/v1/teams/me/members", handler);
  await page.getByRole("button", { name: "ลองโหลดรายชื่ออีกครั้ง", exact: true }).click();
  await expect(page.getByRole("list", { name: "รายชื่อสมาชิกทีม" }).getByRole("listitem")).toHaveCount(1);
});

test("missing CSRF blocks add and lost session redirects to login", async ({ page }) => {
  await leader(page);
  const target = await register(page, "สมาชิกCSRF");
  await page.context().clearCookies({ name: "spms_csrf" });
  await page.getByLabel("อีเมลนักศึกษาที่ต้องการเพิ่ม").fill(target.email);
  await page.getByRole("button", { name: "เพิ่มสมาชิก", exact: true }).click();
  await expect(page.getByRole("region", { name: "สมาชิกในทีม" }).getByRole("alert")).toContainText("ไม่สามารถยืนยันคำขอได้");
  await expect(page.getByRole("link", { name: "เข้าสู่ระบบใหม่" })).toBeVisible();
  await page.context().clearCookies();
  await page.reload();
  await expect(page).toHaveURL(/\/login\?reason=session$/);
});

test("mobile member list and form fit without horizontal overflow", async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await leader(page);
  const target = await register(page, "สมาชิกทดสอบบนโทรศัพท์");
  await page.getByLabel("อีเมลนักศึกษาที่ต้องการเพิ่ม").fill(target.email);
  await page.getByRole("button", { name: "เพิ่มสมาชิก", exact: true }).click();
  await expect(page.getByText(target.full_name, { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("members-mobile.png"), fullPage: true });
});
