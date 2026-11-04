import { expect, test } from "@playwright/test";
import path from "node:path";

test.beforeEach(async ({ page }) => {
  page.on("pageerror", (error) => console.log("Browser error:", error.message));
});

test("landing page links to registration and fits the viewport", async ({
  page,
}, info) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Your content.",
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  if (process.env.UPLOADIO_SCREENSHOT_DIR)
    await page.screenshot({
      path: path.join(
        process.env.UPLOADIO_SCREENSHOT_DIR,
        `uploadio-${info.project.name}.png`,
      ),
      fullPage: true,
    });
  await page.getByRole("link", { name: "Create your workspace" }).click();
  await expect(page).toHaveURL(/\/register$/);
  await expect(page.getByLabel("Email address")).toBeVisible();
});

test("registration validates a short password before contacting auth", async ({
  page,
}) => {
  await page.goto("/register");
  await page.getByLabel("Email address").fill("creator@example.com");
  await page.getByLabel("Password", { exact: true }).fill("short");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "at least 12 characters" }),
  ).toContainText("at least 12 characters");
});

test("protected workspace redirects a signed-out visitor", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login$/);
  await expect(
    page.getByRole("heading", { name: "Welcome back." }),
  ).toBeVisible();
});
