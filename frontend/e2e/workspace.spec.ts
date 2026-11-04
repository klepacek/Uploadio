import { expect, test } from "@playwright/test";
import path from "node:path";

test("empty workspace and composer use API results", async ({ page }, info) => {
  const payload = Buffer.from(
    JSON.stringify({
      sub: "test-user",
      exp: Math.floor(Date.now() / 1000) + 3600,
    }),
  ).toString("base64url");
  const session = {
    access_token: `e30.${payload}.test`,
    refresh_token: "test-refresh",
    expires_at: Math.floor(Date.now() / 1000) + 3600,
    expires_in: 3600,
    token_type: "bearer",
    user: {
      id: "test-user",
      email: "creator@example.com",
      app_metadata: {},
      user_metadata: {},
      aud: "authenticated",
      created_at: new Date().toISOString(),
    },
  };
  await page.addInitScript(
    (value) =>
      window.localStorage.setItem(
        "sb-uploadio-test-auth-token",
        JSON.stringify(value),
      ),
    session,
  );
  await page.route("http://localhost:8000/api/v1/**", (route) => {
    const pathname = new URL(route.request().url()).pathname;
    const body = pathname.endsWith("/dashboard")
      ? { connected_accounts: 0, targets: {} }
      : pathname.endsWith("/users/me")
        ? {
            id: "test-user",
            email: "creator@example.com",
            display_name: "Creator",
            timezone: "UTC",
            workspace_id: "test-workspace",
          }
        : [];
    return route.fulfill({
      json: body,
      headers: { "Access-Control-Allow-Origin": "*" },
    });
  });
  await page.goto("/dashboard");
  await expect(
    page.getByRole("heading", { name: "A little overview." }),
  ).toBeVisible();
  await expect(page.getByText("Your calendar has room.")).toBeVisible();
  if (process.env.UPLOADIO_SCREENSHOT_DIR)
    await page.screenshot({
      path: path.join(
        process.env.UPLOADIO_SCREENSHOT_DIR,
        `uploadio-workspace-${info.project.name}.png`,
      ),
      fullPage: true,
    });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page
    .getByRole("link", { name: "Create post", exact: true })
    .last()
    .click();
  await expect(
    page.getByRole("heading", { name: "Something worth sharing." }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "Select a validated video" }),
  ).toBeVisible();
  if (info.project.name === "mobile") {
    await page.getByRole("button", { name: "Open navigation" }).click();
    await expect(
      page.getByRole("navigation", { name: "Main navigation" }),
    ).toBeVisible();
    await page
      .getByRole("navigation", { name: "Main navigation" })
      .getByRole("link", { name: "Connected accounts", exact: true })
      .click();
  } else
    await page
      .getByRole("navigation", { name: "Main navigation" })
      .getByRole("link", { name: "Connected accounts", exact: true })
      .click();
  await expect(
    page.getByRole("heading", { name: "Your corners of the internet." }),
  ).toBeVisible();
});
