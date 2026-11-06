import { expect, test, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";

const PASSWORD = "BrowserDemoA1"; // Synthetic classroom test fixture only.
let unsafeRequests = 0;

test.beforeEach(async ({ page }) => {
  unsafeRequests = 0;
  await page.route("**/api/v1/auth/**", async (route) => {
    if (new URL(route.request().url()).origin !== "http://localhost:8001") {
      unsafeRequests += 1;
      await route.abort(); // Never allow a successful test POST on normal 8000.
      return;
    }
    await route.continue();
  });
});
test.afterEach(() => { expect(unsafeRequests).toBe(0); });

async function createAccount(page: Page) {
  const email = `auth-browser-${randomUUID()}@example.test`;
  await page.goto("/register");
  await page.getByLabel("ชื่อและนามสกุล", { exact: true }).fill("นักศึกษาทดสอบ");
  await page.getByLabel("อีเมล", { exact: true }).fill(email);
  await page.getByLabel("รหัสผ่าน", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "สร้างบัญชี", exact: true }).click();
  await expect(page).toHaveURL(/\/login\?registered=1$/);
  await expect(page.getByRole("status")).toContainText("สร้างบัญชีสำเร็จแล้ว");
  return email;
}

async function signIn(page: Page, email: string, password = PASSWORD) {
  await page.getByLabel("อีเมล", { exact: true }).fill(email);
  await page.getByLabel("รหัสผ่าน", { exact: true }).fill(password);
  await page.getByRole("button", { name: "เข้าสู่ระบบ", exact: true }).click();
}

test("register, login, refresh, logout and protected navigation", async ({ page, context }, testInfo) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login\?reason=session$/);
  await expect(page.getByRole("heading", { name: "ยินดีต้อนรับกลับมา" })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("login-desktop.png"), fullPage: true });
  const email = await createAccount(page);
  await signIn(page, email, "wrong");
  await expect(page.getByRole("alert").filter({ hasText: "อีเมลหรือรหัสผ่านไม่ถูกต้อง" })).toBeVisible();
  await signIn(page, email);
  await expect(page).toHaveURL("http://localhost:3000/");
  await expect(page.getByRole("heading", { name: "สวัสดี, นักศึกษาทดสอบ" })).toBeVisible();
  await expect(page.getByText(email, { exact: true })).toBeVisible();
  const cookies = await context.cookies();
  expect(cookies.some((cookie) => cookie.name === "spms_session" && cookie.httpOnly && cookie.sameSite === "Lax")).toBe(true);
  expect(cookies.some((cookie) => cookie.name === "spms_csrf" && !cookie.httpOnly)).toBe(true);
  expect(await page.evaluate(() => !document.cookie.split(";").some((part) => part.trim().startsWith("spms_session=")))).toBe(true);
  expect(await page.evaluate((address) => JSON.stringify([Object.entries(localStorage), Object.entries(sessionStorage)]).includes(address), email)).toBe(false);
  await page.reload();
  await expect(page.getByRole("heading", { name: "สวัสดี, นักศึกษาทดสอบ" })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("account-desktop.png"), fullPage: true });
  await page.getByRole("button", { name: "ออกจากระบบ", exact: true }).click();
  await expect(page).toHaveURL(/\/login\?logged_out=1$/);
  expect((await context.cookies()).some((cookie) => ["spms_session", "spms_csrf"].includes(cookie.name))).toBe(false);
  await page.goto("/");
  await expect(page).toHaveURL(/\/login\?reason=session$/);
});

test("client policy, server validation and duplicate-email feedback", async ({ page }) => {
  const email = await createAccount(page);
  await page.goto("/register");
  await page.getByLabel("ชื่อและนามสกุล", { exact: true }).fill("นักศึกษาทดสอบ");
  await page.getByLabel("อีเมล", { exact: true }).fill(email);
  await page.getByLabel("รหัสผ่าน", { exact: true }).fill("demo1234");
  let registrations = 0;
  page.on("request", (request) => { if (request.url().endsWith("/auth/register") && request.method() === "POST") registrations += 1; });
  await page.getByRole("button", { name: "สร้างบัญชี", exact: true }).click();
  await expect(page.getByText("รหัสผ่านต้องมีตัวพิมพ์ใหญ่ A–Z อย่างน้อย 1 ตัว", { exact: true })).toBeVisible();
  expect(registrations).toBe(0);
  await page.getByLabel("อีเมล", { exact: true }).fill("bad@@example.test");
  await page.getByLabel("รหัสผ่าน", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "สร้างบัญชี", exact: true }).click();
  await expect(page.getByText("กรุณากรอกอีเมลให้ถูกต้อง เช่น student@example.test", { exact: true })).toBeVisible();
  await page.getByLabel("อีเมล", { exact: true }).fill(email.toUpperCase());
  await page.getByLabel("รหัสผ่าน", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "สร้างบัญชี", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "อีเมลนี้มีบัญชีอยู่แล้ว" })).toBeVisible();
});

test("missing cookie redirects protected page to login", async ({ page, context }) => {
  const email = await createAccount(page);
  await signIn(page, email);
  await expect(page.getByRole("heading", { name: "สวัสดี, นักศึกษาทดสอบ" })).toBeVisible();
  await context.clearCookies();
  await page.reload();
  await expect(page).toHaveURL(/\/login\?reason=session$/);
});

test("network failure offers retry and does not pretend the user logged out", async ({ page }) => {
  const email = await createAccount(page);
  await signIn(page, email);
  await expect(page.getByRole("heading", { name: "สวัสดี, นักศึกษาทดสอบ" })).toBeVisible();
  await page.route("**/api/v1/auth/me", (route) => route.abort());
  await page.reload();
  await expect(page.getByRole("heading", { name: "ยังเชื่อมต่อระบบไม่ได้" })).toBeVisible();
  await expect(page).toHaveURL("http://localhost:3000/");
  await page.unroute("**/api/v1/auth/me");
  await page.getByRole("button", { name: "ลองอีกครั้ง" }).click();
  await expect(page.getByRole("heading", { name: "สวัสดี, นักศึกษาทดสอบ" })).toBeVisible();
});

test("mobile login and register remain readable without horizontal overflow", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "ยินดีต้อนรับกลับมา" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("login-mobile.png"), fullPage: true });
  await page.getByRole("link", { name: "สมัครสมาชิก", exact: true }).click();
  await expect(page.getByRole("heading", { name: "สร้างบัญชีของคุณ" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await expect(page.getByRole("button", { name: "สร้างบัญชี", exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("register-mobile.png"), fullPage: true });
});
