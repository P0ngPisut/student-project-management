import { expect, test, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";

const API = "http://localhost:8001";
const PASSWORD = "TeamBrowserFixtureA1";
let unsafeRequests = 0;

test.beforeEach(async ({ page }) => {
  unsafeRequests = 0;
  await page.route("**/api/v1/**", async (route) => {
    if (new URL(route.request().url()).origin !== API) {
      unsafeRequests += 1;
      await route.abort();
      return;
    }
    await route.continue();
  });
});
test.afterEach(() => { expect(unsafeRequests).toBe(0); });

async function student(page: Page) {
  const email = `team-browser-${randomUUID()}@example.test`;
  await page.goto("/register");
  await page.getByLabel("ชื่อและนามสกุล", { exact: true }).fill("นักศึกษาทดสอบทีม");
  await page.getByLabel("อีเมล", { exact: true }).fill(email);
  await page.getByLabel("รหัสผ่าน", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "สร้างบัญชี", exact: true }).click();
  await expect(page).toHaveURL(/\/login\?registered=1$/);
  await page.getByLabel("อีเมล", { exact: true }).fill(email);
  await page.getByLabel("รหัสผ่าน", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "เข้าสู่ระบบ", exact: true }).click();
  await expect(page.getByRole("heading", { name: "สวัสดี, นักศึกษาทดสอบทีม" })).toBeVisible();
  await page.getByRole("link", { name: "ทีมของฉัน →", exact: true }).click();
  await expect(page.getByRole("heading", { name: "สร้างทีมของคุณ", exact: true })).toBeVisible();
  return email;
}

test("create with session actor, normalize and restore on refresh without client storage", async ({ page }, testInfo) => {
  await student(page);
  await page.screenshot({ path: testInfo.outputPath("team-create-desktop.png"), fullPage: true });
  let writes = 0;
  let body: Record<string, unknown> | null = null;
  let csrfSent = false;
  page.on("request", (request) => {
    if (request.url() === `${API}/api/v1/teams` && request.method() === "POST") {
      writes += 1;
      body = request.postDataJSON();
      csrfSent = Boolean(request.headers()["x-csrf-token"]);
    }
  });
  await page.getByLabel("ชื่อทีม", { exact: true }).fill("  ทีมโครงงานตัวอย่าง  ");
  await page.getByLabel("คำอธิบายทีม", { exact: false }).fill("  คำอธิบายสำหรับทดสอบ  ");
  await page.getByRole("button", { name: "สร้างทีม", exact: true }).click();
  await expect(page.getByRole("heading", { name: "ทีมโครงงานตัวอย่าง", exact: true })).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: "สร้างทีมสำเร็จแล้ว" })).toBeVisible();
  await expect(page.getByText("หัวหน้าทีม", { exact: true })).toBeVisible();
  expect(writes).toBe(1);
  expect(csrfSent).toBe(true);
  expect(body).toEqual({ name: "ทีมโครงงานตัวอย่าง", description: "คำอธิบายสำหรับทดสอบ" });
  await page.reload();
  await expect(page.getByRole("heading", { name: "ทีมโครงงานตัวอย่าง", exact: true })).toBeVisible();
  await expect(page.getByText("คำอธิบายสำหรับทดสอบ", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "สร้างทีม", exact: true })).toHaveCount(0);
  expect(writes).toBe(1);
  expect(await page.evaluate(() => JSON.stringify([Object.entries(localStorage), Object.entries(sessionStorage)]).includes("ทีมโครงงานตัวอย่าง"))).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("team-current-desktop.png"), fullPage: true });
});

test("client name validation, unicode length and optional description", async ({ page }) => {
  await student(page);
  let writes = 0;
  page.on("request", (request) => { if (request.url() === `${API}/api/v1/teams` && request.method() === "POST") writes += 1; });
  await page.getByLabel("ชื่อทีม", { exact: true }).fill("   ");
  await page.getByRole("button", { name: "สร้างทีม", exact: true }).click();
  await expect(page.getByText("กรุณากรอกชื่อทีม", { exact: true })).toBeVisible();
  await page.getByLabel("ชื่อทีม", { exact: true }).fill("x".repeat(256));
  await page.getByRole("button", { name: "สร้างทีม", exact: true }).click();
  await expect(page.getByText("ชื่อทีมต้องยาวไม่เกิน 255 ตัวอักษร", { exact: true })).toBeVisible();
  expect(writes).toBe(0);
  const title = "📚".repeat(255);
  await page.getByLabel("ชื่อทีม", { exact: true }).fill(title);
  await page.getByRole("button", { name: "สร้างทีม", exact: true }).click();
  await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible();
  await expect(page.getByText("ยังไม่มีคำอธิบายทีม", { exact: true })).toBeVisible();
  expect(writes).toBe(1);
});

test("pending form submits only once", async ({ page }) => {
  await student(page);
  let release: () => void = () => {};
  const hold = new Promise<void>((resolve) => { release = resolve; });
  let writes = 0;
  await page.route("**/api/v1/teams", async (route) => {
    if (new URL(route.request().url()).origin !== API || route.request().method() !== "POST") return route.fallback();
    writes += 1;
    const response = await route.fetch();
    await hold;
    await route.fulfill({ response });
  });
  await page.getByLabel("ชื่อทีม", { exact: true }).fill("ทีมส่งครั้งเดียว");
  await page.getByRole("button", { name: "สร้างทีม", exact: true }).click();
  await expect(page.getByRole("button", { name: "กำลังสร้างทีม…", exact: true })).toBeDisabled();
  await page.locator("form").evaluate((form) => (form as HTMLFormElement).requestSubmit());
  release();
  await expect(page.getByRole("heading", { name: "ทีมส่งครั้งเดียว", exact: true })).toBeVisible();
  expect(writes).toBe(1);
});

test("409 offers checking the existing team without creating another one", async ({ page }) => {
  await student(page);
  const status = await page.evaluate(async () => {
    const csrf = document.cookie.split(";").map((part) => part.trim()).find((part) => part.startsWith("spms_csrf="))!.slice("spms_csrf=".length);
    const response = await fetch("http://localhost:8001/api/v1/teams", { method: "POST", credentials: "include",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf }, body: JSON.stringify({ name: "ทีมที่มีอยู่แล้ว" }) });
    return response.status;
  });
  expect(status).toBe(201);
  await page.getByLabel("ชื่อทีม", { exact: true }).fill("ทีมที่ไม่ควรสร้างซ้ำ");
  await page.getByRole("button", { name: "สร้างทีม", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "คุณมีทีมอยู่แล้ว" })).toBeVisible();
  await page.getByRole("button", { name: "ตรวจสอบทีมอีกครั้ง", exact: true }).click();
  await expect(page.getByRole("heading", { name: "ทีมที่มีอยู่แล้ว", exact: true })).toBeVisible();
});

test("lost POST response is recovered by GET rather than automatically posting again", async ({ page }) => {
  await student(page);
  let writes = 0;
  await page.route("**/api/v1/teams", async (route) => {
    if (new URL(route.request().url()).origin !== API || route.request().method() !== "POST") return route.fallback();
    writes += 1;
    await route.fetch();
    await route.abort("connectionreset");
  });
  await page.getByLabel("ชื่อทีม", { exact: true }).fill("ทีมที่บันทึกแล้ว");
  await page.getByRole("button", { name: "สร้างทีม", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "ไม่สามารถยืนยันผล" })).toBeVisible();
  await page.getByRole("button", { name: "ตรวจสอบทีมอีกครั้ง", exact: true }).click();
  await expect(page.getByRole("heading", { name: "ทีมที่บันทึกแล้ว", exact: true })).toBeVisible();
  expect(writes).toBe(1);
});

test("GET network or generic 404 failure never masquerades as no team", async ({ page }) => {
  await student(page);
  await page.route("**/api/v1/teams/me", (route) => route.abort());
  await page.reload();
  await expect(page.getByRole("heading", { name: "ยังโหลดข้อมูลทีมไม่ได้", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "สร้างทีม", exact: true })).toHaveCount(0);
  await page.unroute("**/api/v1/teams/me");
  await page.getByRole("button", { name: "ลองอีกครั้ง", exact: true }).click();
  await expect(page.getByRole("heading", { name: "สร้างทีมของคุณ", exact: true })).toBeVisible();
  await page.route("**/api/v1/teams/me", (route) => route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "Not Found" }) }));
  await page.reload();
  await expect(page.getByRole("heading", { name: "ยังโหลดข้อมูลทีมไม่ได้", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "สร้างทีม", exact: true })).toHaveCount(0);
});

test("session loss redirects and missing CSRF never pretends creation succeeded", async ({ page, context }) => {
  await page.goto("/teams");
  await expect(page).toHaveURL(/\/login\?reason=session$/);
  await student(page);
  await context.clearCookies({ name: "spms_csrf" });
  await page.getByLabel("ชื่อทีม", { exact: true }).fill("ทีมที่ยังสร้างไม่ได้");
  await page.getByRole("button", { name: "สร้างทีม", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "ไม่สามารถยืนยันคำขอ" })).toBeVisible();
  await expect(page.getByRole("link", { name: "เข้าสู่ระบบใหม่", exact: true })).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: "สร้างทีมสำเร็จแล้ว" })).toHaveCount(0);
  await context.clearCookies();
  await page.reload();
  await expect(page).toHaveURL(/\/login\?reason=session$/);
});

test("mobile creation and current team are readable without horizontal overflow", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await student(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("team-create-mobile.png"), fullPage: true });
  await page.getByLabel("ชื่อทีม", { exact: true }).fill("ทีมทดสอบบนมือถือ");
  await page.getByLabel("คำอธิบายทีม", { exact: false }).fill("รายละเอียดทีม\nสำหรับโครงงานของเรา");
  await page.getByRole("button", { name: "สร้างทีม", exact: true }).click();
  await expect(page.getByRole("heading", { name: "ทีมทดสอบบนมือถือ", exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("team-current-mobile.png"), fullPage: true });
});
