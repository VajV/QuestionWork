const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const { chromium } = require("playwright");

const FRONTEND_URL = process.env.FRONTEND_URL || "http://127.0.0.1:3000";
const API_URL = process.env.API_URL || "http://127.0.0.1:8001/api/v1";
const ADMIN_USERNAME = process.env.ADMIN_USERNAME || "admin";
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || "Admin123!";
const ADMIN_USER_ID = process.env.ADMIN_USER_ID || "admin";
const BACKEND_ENV_PATH = path.resolve(__dirname, "..", "backend", ".env");

const stamp = new Date().toISOString().replace(/[:.]/g, "-");
const artifactDir = path.resolve(__dirname, "..", "playwright-audit-artifacts", stamp);

fs.mkdirSync(artifactDir, { recursive: true });

const results = [];
const diagnostics = [];

function getBackendEnvValue(key, fallback = undefined) {
  if (!fs.existsSync(BACKEND_ENV_PATH)) {
    return fallback;
  }

  const envText = fs.readFileSync(BACKEND_ENV_PATH, "utf8");
  const match = envText.match(new RegExp(`^${key}=(.*)$`, "m"));
  if (!match) {
    return fallback;
  }

  return match[1].trim();
}

function base64UrlEncode(value) {
  return Buffer.from(value)
    .toString("base64")
    .replace(/=/g, "")
    .replace(/\+/g, "-")
    .replace(/\//g, "_");
}

function createHs256Jwt(payload, secret) {
  const header = { alg: "HS256", typ: "JWT" };
  const encodedHeader = base64UrlEncode(JSON.stringify(header));
  const encodedPayload = base64UrlEncode(JSON.stringify(payload));
  const signature = crypto
    .createHmac("sha256", secret)
    .update(`${encodedHeader}.${encodedPayload}`)
    .digest("base64")
    .replace(/=/g, "")
    .replace(/\+/g, "-")
    .replace(/\//g, "_");
  return `${encodedHeader}.${encodedPayload}.${signature}`;
}

function createLocalAdminAccessToken() {
  const nowSeconds = Math.floor(Date.now() / 1000);
  const secret = process.env.SECRET_KEY || getBackendEnvValue("SECRET_KEY");
  if (!secret) {
    throw new Error("SECRET_KEY is required to mint a local admin access token for the audit runner");
  }

  return createHs256Jwt(
    {
      sub: ADMIN_USER_ID,
      exp: nowSeconds + 5 * 60,
      iat: nowSeconds,
      iss: "questionwork",
      aud: "questionwork-api",
    },
    secret,
  );
}

function sanitizeFilePart(value) {
  return String(value).replace(/[^a-zA-Z0-9_-]+/g, "-").slice(0, 80);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function collectPageState(page) {
  return page.evaluate(() => ({
    url: window.location.href,
    localUser: localStorage.getItem("questionwork_user"),
    buttons: Array.from(document.querySelectorAll("button")).map((element) => ({
      text: (element.textContent || "").replace(/\s+/g, " ").trim(),
      disabled: element.hasAttribute("disabled"),
    })),
    bodySnippet: document.body.innerText.slice(0, 2000),
  }));
}

async function waitForEnabledButton(page, textPattern, timeout = 30000) {
  const locator = page.locator("button").filter({ hasText: textPattern }).first();
  await locator.waitFor({ state: "visible", timeout });

  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    const isDisabled = await locator.evaluate((element) => element.hasAttribute("disabled"));
    if (!isDisabled) {
      return locator;
    }
    await sleep(250);
  }

  const state = await collectPageState(page);
  throw new Error(`Timed out waiting for enabled button ${textPattern}. State: ${JSON.stringify(state)}`);
}

function record(role, step, status, details = {}) {
  results.push({
    role,
    step,
    status,
    timestamp: new Date().toISOString(),
    ...details,
  });
}

function logDiagnostic(entry) {
  diagnostics.push({
    timestamp: new Date().toISOString(),
    ...entry,
  });
}

function shouldIgnoreResponse(url, status) {
  if (url.includes("/favicon.ico")) {
    return true;
  }
  if (url.includes("/_next/") && status === 404) {
    return true;
  }
  return false;
}

function attachPageObservers(page, role) {
  page.on("console", (message) => {
    if (message.type() === "error") {
      logDiagnostic({
        role,
        type: "console-error",
        url: page.url(),
        message: message.text(),
      });
    }
  });

  page.on("pageerror", (error) => {
    logDiagnostic({
      role,
      type: "page-error",
      url: page.url(),
      message: error.message,
      stack: error.stack || null,
    });
  });

  page.on("response", (response) => {
    const status = response.status();
    const url = response.url();
    if (status < 400 || shouldIgnoreResponse(url, status)) {
      return;
    }
    if (url.startsWith(FRONTEND_URL) || url.startsWith(API_URL)) {
      logDiagnostic({
        role,
        type: "http-error",
        pageUrl: page.url(),
        url,
        status,
        method: response.request().method(),
      });
    }
  });

  page.on("dialog", async (dialog) => {
    logDiagnostic({
      role,
      type: "dialog",
      url: page.url(),
      dialogType: dialog.type(),
      message: dialog.message(),
    });
    await dialog.accept();
  });
}

async function createObservedPage(context, role) {
  const page = await context.newPage();
  attachPageObservers(page, role);
  page.setDefaultTimeout(20000);
  return page;
}

async function screenshotOnFailure(page, role, step) {
  const fileName = `${sanitizeFilePart(role)}-${sanitizeFilePart(step)}.png`;
  const filePath = path.join(artifactDir, fileName);
  try {
    await page.screenshot({ path: filePath, fullPage: true });
    return filePath;
  } catch {
    return null;
  }
}

async function runStep(role, step, fn, options = {}) {
  const { page = null, critical = false } = options;
  try {
    const value = await fn();
    record(role, step, "passed");
    return value;
  } catch (error) {
    const screenshot = page ? await screenshotOnFailure(page, role, step) : null;
    const errorMessage = error instanceof Error ? error.message : String(error);
    record(role, step, critical ? "failed-critical" : "failed", {
      error: errorMessage,
      screenshot,
    });
    if (critical) {
      throw error;
    }
    return null;
  }
}

async function apiRequest(endpoint, { method = "GET", body, token } = {}) {
  const response = await fetch(`${API_URL}${endpoint}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  const text = await response.text();
  let data = null;

  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }

  if (!response.ok) {
    throw new Error(`API ${method} ${endpoint} failed with ${response.status}: ${typeof data === "string" ? data : JSON.stringify(data)}`);
  }

  return data;
}

async function loginApi(username, password) {
  return apiRequest("/auth/login", {
    method: "POST",
    body: { username, password },
  });
}

async function waitForOneOfUrls(page, patterns, timeout = 30000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    const currentUrl = page.url();
    if (patterns.some((pattern) => pattern.test(currentUrl))) {
      return currentUrl;
    }
    await sleep(250);
  }
  throw new Error(`Timed out waiting for one of URLs: ${patterns.map((pattern) => pattern.toString()).join(", ")}. Current URL: ${page.url()}`);
}

async function navigateAndSettle(page, route, settleMs = 1200) {
  await page.goto(`${FRONTEND_URL}${route}`, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});
  await sleep(settleMs);
}

async function registerUser(page, role, credentials) {
  await navigateAndSettle(page, "/auth/register");

  await page.locator("#username").fill(credentials.username);
  await page.locator("#email").fill(credentials.email);
  await page.locator("#password").fill(credentials.password);
  await page.locator("#confirmPassword").fill(credentials.password);

  if (role === "client") {
    await page.getByRole("button", { name: /Заказчик/i }).click();
  } else {
    await page.getByRole("button", { name: /Наёмник/i }).click();
  }

  await page.getByRole("button", { name: /Подписать Контракт|Призыв/i }).click();

  const finalUrl = await waitForOneOfUrls(page, [/\/profile$/, /\/onboarding$/, /\/quests$/], 30000);

  if (role === "freelancer" && finalUrl.endsWith("/onboarding")) {
    await page.getByRole("button", { name: /Пропустить/i }).click();
    await waitForOneOfUrls(page, [/\/quests$/, /\/profile$/], 30000);
  }
}

async function loginInBrowser(page, username, password) {
  await navigateAndSettle(page, "/auth/login");
  const usernameField = page.locator('input[name="login_username"]');
  const passwordField = page.locator('input[name="login_password"]');

  if (await usernameField.count()) {
    await usernameField.fill(username);
    await passwordField.fill(password);
    await page.getByRole("button", { name: /Войти в Игру|Соединение/i }).click();
  }

  await waitForOneOfUrls(page, [/\/profile$/, /\/admin$/, /\/onboarding$/, /\/quests$/], 30000);
}

async function createQuestViaBrowser(page, title) {
  await navigateAndSettle(page, "/quests/create");

  await page.getByPlaceholder(/Разработать REST API/i).fill(title);
  await page.getByPlaceholder(/Опишите, что нужно сделать/i).fill(
    "Нужно собрать рабочий демо-флоу для фронтенда и бэкенда, проверить жизненный цикл задачи и подготовить результат для клиентской проверки.",
  );
  await page.getByRole("button", { name: /Далее/i }).click();

  const skillInput = page.getByPlaceholder(/Навык \+ Enter/i);
  await skillInput.fill("React");
  await skillInput.press("Enter");
  await skillInput.fill("TypeScript");
  await skillInput.press("Enter");
  await page.getByText(/Требуется портфолио/i).click();
  await page.getByRole("button", { name: /Далее/i }).click();

  await page.getByPlaceholder(/^5000$/).fill("15000");
  await page.getByText(/Срочный квест/i).click();
  await page.getByRole("button", { name: /Далее/i }).click();

  await page.getByRole("button", { name: /Далее/i }).click();

  await page.getByRole("button", { name: /Прибить к Доске|Публикуем/i }).click();

  const deadline = Date.now() + 30000;
  while (Date.now() < deadline) {
    const currentUrl = page.url();
    const pathname = new URL(currentUrl).pathname;
    if (/^\/quests\/[^/]+$/.test(pathname) && pathname !== "/quests/create") {
      break;
    }
    await sleep(250);
  }

  const questUrl = page.url();
  const questPath = new URL(questUrl).pathname;
  const questId = questPath.split("/").filter(Boolean).pop();
  if (!questId || questId === "create") {
    throw new Error(`Could not extract quest id from ${questUrl}`);
  }
  return questId;
}

async function leaveReview(page, comment) {
  await page.getByRole("button", { name: /Оставить отзыв/i }).click();
  const reviewDialog = page.getByRole("dialog", { name: /Оставить отзыв/i });
  await reviewDialog.waitFor({ state: "visible", timeout: 15000 });

  const ratingButton = reviewDialog.getByRole("button", { name: /Оценка 5 из 5/i });
  await ratingButton.click();

  const deadline = Date.now() + 15000;
  while (Date.now() < deadline) {
    if ((await ratingButton.getAttribute("aria-pressed")) === "true") {
      break;
    }
    await sleep(200);
  }

  await reviewDialog.getByPlaceholder(/Расскажите о работе/i).fill(comment);

  const submitReviewButton = reviewDialog.getByRole("button", { name: /^Отправить$/i });
  await submitReviewButton.waitFor({ state: "visible", timeout: 15000 });

  const submitDeadline = Date.now() + 15000;
  while (Date.now() < submitDeadline) {
    const isDisabled = await submitReviewButton.evaluate((element) => element.hasAttribute("disabled"));
    if (!isDisabled) {
      break;
    }
    await sleep(200);
  }
  await submitReviewButton.click();
  await page.getByText(/Отзыв отправлен/i).first().waitFor({ timeout: 15000 });
}

async function auditRolePages(role, page, routes) {
  for (const route of routes) {
    await runStep(role, `route:${route}`, async () => {
      await navigateAndSettle(page, route, 1800);
    }, { page });
  }
}

async function main() {
  const browser = await chromium.launch({ headless: true });

  const clientContext = await browser.newContext({ viewport: { width: 1440, height: 960 } });
  const freelancerContext = await browser.newContext({ viewport: { width: 1440, height: 960 } });
  const adminContext = await browser.newContext({ viewport: { width: 1440, height: 960 } });

  let clientPage = await createObservedPage(clientContext, "client");
  let freelancerPage = await createObservedPage(freelancerContext, "freelancer");
  const adminPage = await createObservedPage(adminContext, "admin");

  const suffix = Date.now().toString(36);
  const commonPassword = "Quest123!";
  const clientCredentials = {
    username: `pw_client_${suffix}`,
    email: `pw_client_${suffix}@example.com`,
    password: commonPassword,
  };
  const freelancerCredentials = {
    username: `pw_freelancer_${suffix}`,
    email: `pw_freelancer_${suffix}@example.com`,
    password: commonPassword,
  };

  let questId = null;
  let clientUser = null;
  let freelancerUser = null;

  try {
    await runStep("client", "register", async () => {
      await registerUser(clientPage, "client", clientCredentials);
    }, { page: clientPage, critical: true });

    await runStep("freelancer", "register-and-onboarding-skip", async () => {
      await registerUser(freelancerPage, "freelancer", freelancerCredentials);
    }, { page: freelancerPage, critical: true });

    clientUser = await runStep("client", "api-login-after-register", async () => {
      const payload = await loginApi(clientCredentials.username, clientCredentials.password);
      return payload.user;
    }, { critical: true });

    freelancerUser = await runStep("freelancer", "api-login-after-register", async () => {
      const payload = await loginApi(freelancerCredentials.username, freelancerCredentials.password);
      return payload.user;
    }, { critical: true });

    await clientPage.close().catch(() => {});
    await freelancerPage.close().catch(() => {});
    clientPage = await createObservedPage(clientContext, "client");
    freelancerPage = await createObservedPage(freelancerContext, "freelancer");

    await runStep("client", "browser-login-after-register", async () => {
      await loginInBrowser(clientPage, clientCredentials.username, clientCredentials.password);
    }, { page: clientPage, critical: true });

    await runStep("freelancer", "browser-login-after-register", async () => {
      await loginInBrowser(freelancerPage, freelancerCredentials.username, freelancerCredentials.password);
    }, { page: freelancerPage, critical: true });

    await runStep("admin", "fund-client-wallet-via-api", async () => {
      const adminAccessToken = createLocalAdminAccessToken();
      await apiRequest(`/admin/users/${clientUser.id}/adjust-wallet`, {
        method: "POST",
        token: adminAccessToken,
        body: {
          amount: 20000,
          currency: "RUB",
          reason: "Playwright lifecycle funding",
        },
      });
    }, { critical: true });

    questId = await runStep("client", "create-quest", async () => {
      const title = `Playwright audit quest ${suffix}`;
      return createQuestViaBrowser(clientPage, title);
    }, { page: clientPage, critical: true });

    await runStep("freelancer", "apply-to-quest", async () => {
      await navigateAndSettle(freelancerPage, `/quests/${questId}`);
      logDiagnostic({
        role: "freelancer",
        type: "apply-page-state",
        state: await collectPageState(freelancerPage),
      });
      const applyButton = await waitForEnabledButton(freelancerPage, /Откликнуться/i, 30000);
      await applyButton.click();
      await freelancerPage.getByPlaceholder(/Расскажите, почему/i).fill(
        "Есть релевантный опыт с Next.js, API и полным пользовательским циклом. Готов быстро пройти happy-path и передать результат на проверку.",
      );
      const submitApplyButton = await waitForEnabledButton(freelancerPage, /Отправить отклик/i, 15000);
      await submitApplyButton.click();
      await freelancerPage.locator("div, button").filter({ hasText: /Отклик успешно отправлен|Отклик отправлен/i }).first().waitFor({ timeout: 15000 });
    }, { page: freelancerPage, critical: true });

    await runStep("client", "assign-freelancer", async () => {
      await navigateAndSettle(clientPage, `/quests/${questId}`);
      await clientPage.getByRole("button", { name: /Назначить Исполнителем/i }).click();
      await clientPage.getByText(/Исполнитель выбран|ожидается старт работы/i).first().waitFor({ timeout: 15000 });
    }, { page: clientPage, critical: true });

    await runStep("freelancer", "start-quest", async () => {
      await navigateAndSettle(freelancerPage, `/quests/${questId}`);
      await freelancerPage.getByRole("button", { name: /Начать работу/i }).click();
      await freelancerPage.getByPlaceholder(/Опишите, что именно выполнено/i).waitFor({ timeout: 15000 });
    }, { page: freelancerPage, critical: true });

    await runStep("freelancer", "submit-completion", async () => {
      await freelancerPage.getByPlaceholder(/Опишите, что именно выполнено/i).fill(
        "Сценарий выполнен: квест создан, исполнитель назначен, подготовлен результат и ссылка для проверки клиентом.",
      );
      await freelancerPage.getByPlaceholder(/https:\/\/github.com/i).fill("https://example.com/playwright-audit-result");
      await freelancerPage.getByRole("button", { name: /Сдать результат|Отправить исправления/i }).click();
      await freelancerPage.getByText(/Ожидает подтверждения клиента|Ожидает подтверждения/i).first().waitFor({ timeout: 15000 });
    }, { page: freelancerPage, critical: true });

    await runStep("client", "confirm-completion", async () => {
      await navigateAndSettle(clientPage, `/quests/${questId}`);
      await clientPage.getByRole("button", { name: /Подтвердить выполнение/i }).click();
      await clientPage.getByRole("button", { name: /Оставить отзыв/i }).waitFor({ timeout: 15000 });
    }, { page: clientPage, critical: true });

    await runStep("client", "leave-review", async () => {
      await leaveReview(clientPage, "Фрилансер быстро прошёл полный сценарий, коммуникация и результат в порядке.");
    }, { page: clientPage });

    await runStep("freelancer", "leave-review", async () => {
      await navigateAndSettle(freelancerPage, `/quests/${questId}`);
      await leaveReview(freelancerPage, "Заказчик подтвердил выполнение без задержек, постановка задачи была понятной.");
    }, { page: freelancerPage });

    await runStep("admin", "browser-login", async () => {
      await loginInBrowser(adminPage, ADMIN_USERNAME, ADMIN_PASSWORD);
    }, { page: adminPage, critical: true });

    await auditRolePages("client", clientPage, [
      "/profile",
      "/quests",
      "/notifications",
      "/messages",
      "/disputes",
      "/marketplace",
      `/quests/${questId}`,
    ]);

    await auditRolePages("freelancer", freelancerPage, [
      "/profile",
      "/quests",
      "/notifications",
      "/messages",
      "/disputes",
      "/profile/class",
      `/quests/${questId}`,
    ]);

    await auditRolePages("admin", adminPage, [
      "/admin",
      "/admin/dashboard",
      "/admin/users",
      "/admin/quests",
      "/admin/logs",
      "/admin/withdrawals",
      "/admin/disputes",
      "/admin/growth",
    ]);
  } finally {
    await clientContext.close().catch(() => {});
    await freelancerContext.close().catch(() => {});
    await adminContext.close().catch(() => {});
    await browser.close().catch(() => {});
  }

  const summary = {
    generated_at: new Date().toISOString(),
    frontend_url: FRONTEND_URL,
    api_url: API_URL,
    artifact_dir: artifactDir,
    quest_id: questId,
    client_username: clientCredentials.username,
    freelancer_username: freelancerCredentials.username,
    result_counts: results.reduce((accumulator, entry) => {
      accumulator[entry.status] = (accumulator[entry.status] || 0) + 1;
      return accumulator;
    }, {}),
    results,
    diagnostics,
  };

  const summaryPath = path.join(artifactDir, "summary.json");
  fs.writeFileSync(summaryPath, JSON.stringify(summary, null, 2), "utf8");

  console.log(JSON.stringify({
    summaryPath,
    artifactDir,
    questId,
    resultCounts: summary.result_counts,
    failedSteps: results.filter((entry) => entry.status !== "passed"),
    diagnosticsCount: diagnostics.length,
  }, null, 2));
}

main().catch((error) => {
  const failure = {
    fatal: true,
    message: error instanceof Error ? error.message : String(error),
    stack: error instanceof Error ? error.stack : null,
    partial_results: results,
    partial_diagnostics: diagnostics,
  };

  const failurePath = path.join(artifactDir, "fatal.json");
  fs.writeFileSync(failurePath, JSON.stringify(failure, null, 2), "utf8");
  console.error(JSON.stringify({ failurePath, ...failure }, null, 2));
  process.exitCode = 1;
});