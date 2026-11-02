import { expect, test, type Page } from "@playwright/test";

async function expectNoPageOverflow(page: Page) {
  await expect
    .poll(() =>
      page.evaluate(() => ({
        body: document.body.scrollWidth <= window.innerWidth,
        document: document.documentElement.scrollWidth <= window.innerWidth,
      })),
    )
    .toEqual({ body: true, document: true });
}

async function fillRegistration(page: Page) {
  await page.getByLabel("Organization name").fill("Test General Hospital");
  await page.getByLabel("Organization type").selectOption("hospital");
  await page.getByLabel("Country").fill("Kenya");
  await page.getByLabel("First name").fill("Sarah");
  await page.getByLabel("Last name").fill("Wanjiku");
  await page.getByLabel("Work email").fill("sarah@test-hospital.example");
  await page.getByLabel("Password").fill("SecurePassword123!");
}

test("homepage actions have explicit destinations and responsive behavior", async ({ page }) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: "Recover revenue. Preserve trust." }),
  ).toBeVisible();
  await expect(page.locator('nav[aria-label="Primary navigation"]')).toHaveCount(1);
  await expect(page.getByRole("link", { name: "Sign in" }).first()).toHaveAttribute(
    "href",
    "/login",
  );
  await expect(page.getByRole("link", { name: "Build your recovery practice" })).toHaveAttribute(
    "href",
    "/register?intent=recovery-practice",
  );
  await expect(page.getByRole("link", { name: "Request access" }).last()).toHaveAttribute(
    "href",
    "/register?intent=request-access",
  );

  const footer = page.locator("footer");
  for (const [name, href] of [
    ["Method", "#method"],
    ["Platform", "#platform"],
    ["Governance", "#governance"],
    ["Standards", "#standards"],
  ]) {
    await expect(footer.getByRole("link", { name })).toHaveAttribute("href", href);
  }

  await page.getByRole("link", { name: "Explore the method" }).click();
  await expect(page).toHaveURL(/#method$/);
  await expect(
    page.getByRole("heading", {
      name: "A recovery practice built on clarity, judgement, and proof.",
    }),
  ).toBeVisible();
  await expectNoPageOverflow(page);
});

test("homepage registration calls to action explain their distinct intent", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Build your recovery practice" }).click();

  await expect(page).toHaveURL(/\/register\/?\?intent=recovery-practice$/, {
    timeout: 30_000,
  });
  await expect(
    page.getByRole("heading", { name: "Build your recovery practice" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Create recovery workspace" })).toBeVisible();

  await page.goto("/");
  await page.getByRole("link", { name: "Request access" }).last().click();

  await expect(page).toHaveURL(/\/register\/?\?intent=request-access$/, {
    timeout: 30_000,
  });
  await expect(page.getByRole("heading", { name: "Request Atlas access" })).toBeVisible();
  await expect(page.getByText("Access activates only after work email verification.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Request access" })).toBeVisible();
  await expectNoPageOverflow(page);
});

test("registration validates input and explains successful activation", async ({ page }) => {
  let submitted: Record<string, unknown> | undefined;
  await page.route("**/api/v1/auth/register", async (route) => {
    submitted = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 200,
      json: {
        organization_id: 41,
        user_id: 82,
        message: "Verification email sent",
      },
    });
  });

  await page.goto("/register?intent=request-access");
  await page.getByRole("button", { name: "Request access" }).click();

  await expect(page.getByText("Organization name is required")).toBeVisible();
  await expect(page.getByText("First name is required")).toBeVisible();
  await expect(page.getByText("Last name is required")).toBeVisible();
  await expect(page.getByText("Enter a valid work email address")).toBeVisible();
  await expect(page.getByText("Password must be at least 10 characters")).toBeVisible();

  await fillRegistration(page);
  await page.getByRole("button", { name: "Request access" }).click();

  await expect(page.getByRole("heading", { name: "Verification email sent" })).toBeVisible();
  await expect(page.getByText("sarah@test-hospital.example")).toBeVisible();
  await expect(page.getByRole("link", { name: "Continue to sign in" })).toHaveAttribute(
    "href",
    "/login",
  );
  expect(submitted).toMatchObject({
    organization_name: "Test General Hospital",
    organization_type: "hospital",
    country: "Kenya",
    first_name: "Sarah",
    last_name: "Wanjiku",
    email: "sarah@test-hospital.example",
  });
});

test("registration exposes email delivery failures without creating success UI", async ({ page }) => {
  await page.route("**/api/v1/auth/register", async (route) => {
    await route.fulfill({
      status: 503,
      json: { detail: "Verification email delivery is temporarily unavailable" },
    });
  });

  await page.goto("/register?intent=recovery-practice");
  await fillRegistration(page);
  await page.getByRole("button", { name: "Create recovery workspace" }).click();

  await expect(
    page
      .getByRole("alert")
      .filter({ hasText: "Verification email delivery is temporarily unavailable" }),
  ).toHaveText("Verification email delivery is temporarily unavailable");
  await expect(page.getByRole("heading", { name: "Verification email sent" })).toHaveCount(0);
});

test("public sign-in path and return-home control are reachable", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Sign in" }).first().click();

  await expect(page).toHaveURL(/\/login\/?$/);
  await expect(page.getByRole("button", { name: "Sign in" })).toBeEnabled();
  await expect(page.getByRole("link", { name: "Forgot password?" })).toHaveAttribute(
    "href",
    "/forgot-password",
  );
  await expect(page.getByRole("link", { name: "Create an organization" })).toHaveAttribute(
    "href",
    "/register",
  );

  await page.getByRole("link", { name: "Return to Atlas home" }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(
    page.getByRole("heading", { name: "Recover revenue. Preserve trust." }),
  ).toBeVisible();
});
