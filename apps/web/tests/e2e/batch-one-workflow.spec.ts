import { expect, test, type Page } from "@playwright/test";

const email = process.env.ATLAS_E2E_EMAIL ?? "admin@atlasdemo.com";
const password = process.env.ATLAS_E2E_PASSWORD ?? "AtlasDemo2026!";

test.setTimeout(180_000);

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

test.beforeEach(async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("button", { name: "Sign in" })).toBeEnabled();
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard$/, { timeout: 30_000 });
  await expect(page.getByRole("heading", { name: "Recovery Command Center" })).toBeVisible();
});

test("patient, claim, and document workflows are reachable and responsive", async ({ page }) => {
  await page.getByTitle("Patients").click();
  await expect(page).toHaveURL(/\/patients$/, { timeout: 30_000 });
  await expect(page.getByRole("heading", { name: "Patients" })).toBeVisible();
  await expect(page.getByLabel("Search patients")).toBeVisible();
  await expectNoPageOverflow(page);

  await page.getByTitle("Claims").click();
  await expect(page).toHaveURL(/\/claims$/, { timeout: 30_000 });
  await expect(page.getByRole("heading", { name: "Claims" })).toBeVisible();
  await expect(page.getByPlaceholder("Search claim #, patient, or payer…")).toBeVisible();
  await expectNoPageOverflow(page);

  await page.getByTitle("Documents").click();
  await expect(page).toHaveURL(/\/documents$/, { timeout: 30_000 });
  await expect(page.getByRole("heading", { name: "Documents" })).toBeVisible();
  await expect(page.getByLabel("Search claims for documents")).toBeVisible();
  await expectNoPageOverflow(page);
});

test("payer approval and monitoring workflow is reachable and responsive", async ({ page }) => {
  await page.getByTitle("Payers").click();
  await expect(page).toHaveURL(/\/payers$/, { timeout: 30_000 });
  await expect(page.getByRole("heading", { name: "Payer registry" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Add payer" })).toBeVisible();
  await expectNoPageOverflow(page);
});