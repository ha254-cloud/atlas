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

test.beforeEach(async ({ page }, testInfo) => {
  if (testInfo.title.includes("payment settlement")) {
    await page.route("**/api/v1/**", async (route) => {
      await route.fulfill({ json: {} });
    });
    await page.route("**/api/v1/auth/login", async (route) => {
      await route.fulfill({ json: { access_token: "payments-e2e-token" } });
    });
    await page.route("**/api/v1/auth/me", async (route) => {
      await route.fulfill({
        json: {
          id: 17,
          email: "finance@atlas.test",
          first_name: "Finance",
          last_name: "Owner",
          role: "owner",
          organization_id: 1,
          is_active: true,
          is_superuser: false,
          email_verified: true,
        },
      });
    });
    await page.addInitScript(() => {
      window.localStorage.setItem("atlas_access_token", "payments-e2e-token");
    });
    return;
  }
  await page.goto("/login");
  await expect(page.getByRole("button", { name: "Sign in" })).toBeEnabled();
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard$/, { timeout: 30_000 });
  await expect(
    page.getByRole("heading", { name: "Recovery Command Center" }),
  ).toBeVisible();
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

test("payment settlement can be split across KES claims responsively", async ({ page }) => {
  let allocationRequest: Record<string, unknown> | undefined;
  await page.route("**/api/v1/payments", async (route) => {
    await route.fulfill({
      json: {
        summary: {
          total_recovered: 0,
          total_fees: 0,
          net_recovered: 0,
          payment_count: 1,
          invoices_generated: 0,
        },
        payments: [],
      },
    });
  });
  await page.route("**/api/v1/payments/records", async (route) => {
    await route.fulfill({
      json: [
        {
          id: 81,
          claim_id: null,
          submission_id: null,
          payer_name: "Social Health Authority",
          payment_reference: "SHA-SETTLEMENT-2026-10",
          payment_date: "2026-10-15",
          expected_amount: "1000.00",
          paid_amount: "1000.00",
          adjustment_amount: "0.00",
          currency: "KES",
          payment_terms_days: 30,
          payment_method: "eft",
          status: "paid",
          source: "portal_export",
          matched_at: null,
          matched_by_id: null,
          matching_method: null,
          matching_reason: null,
          correlation_id: "payment-e2e-81",
          created_at: "2026-10-15T09:30:00Z",
          allocated_amount: "0.00",
          unallocated_amount: "1000.00",
        },
      ],
    });
  });
  await page.route("**/api/v1/payments/records/81/candidates", async (route) => {
    await route.fulfill({
      json: [
        {
          claim_id: 701,
          claim_number: "SHA-CLAIM-701",
          payer_name: "Social Health Authority",
          billed_amount: "700.00",
          paid_amount: "0.00",
          outstanding_amount: "700.00",
          currency: "KES",
          confidence: 90,
          reasons: ["claim_reference", "payer_name", "currency_match"],
        },
        {
          claim_id: 702,
          claim_number: "SHA-CLAIM-702",
          payer_name: "Social Health Authority",
          billed_amount: "300.00",
          paid_amount: "0.00",
          outstanding_amount: "300.00",
          currency: "KES",
          confidence: 85,
          reasons: ["payer_name", "exact_outstanding_amount", "currency_match"],
        },
      ],
    });
  });
  await page.route("**/api/v1/payments/records/81/allocations", async (route) => {
    allocationRequest = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 201,
      json: {
        allocations: [],
        created: true,
        allocated_amount: "1000.00",
        unallocated_amount: "0.00",
      },
    });
  });

  await page.goto("/payments");
  await expect(page).toHaveURL(/\/payments$/, { timeout: 30_000 });
  await expect(page.getByRole("heading", { name: "Needs reconciliation" })).toBeVisible();
  await expect(page.getByText(/1,000\.00/)).toBeVisible();
  await page.getByRole("button", { name: "Review" }).click();
  await page.getByLabel("Allocation for SHA-CLAIM-701").fill("700");
  await page.getByLabel("Allocation for SHA-CLAIM-702").fill("300");
  await page.getByRole("button", { name: "Allocate selected" }).click();

  await expect(
    page.getByText(
      "Payment allocated. Recovery evidence is ready for finance verification.",
    ),
  ).toBeVisible();
  expect(allocationRequest?.allocations).toEqual([
    { claim_id: 701, amount: "700" },
    { claim_id: 702, amount: "300" },
  ]);
  expect(allocationRequest?.reason).toBe("Matched against insurer payment advice");
  expect(typeof allocationRequest?.idempotency_key).toBe("string");
  await expectNoPageOverflow(page);
});