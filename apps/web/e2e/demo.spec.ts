import { test, expect } from "@playwright/test";

test("demo discovery, refresh, shortlist, comparison and illustrative analysis need no backend", async ({ page }) => {
  const external: string[] = [];
  page.on("request", request => { if (!request.url().startsWith("http://127.0.0.1:3019")) external.push(request.url()); });
  await page.goto("/");
  await expect(page.getByRole("note")).toContainText("Interactive demo");
  await page.goto("/projects?country=PAK&q=flood");
  await expect(page.getByRole("link", { name: /Synthetic .*Pakistan flood protection/ }).first()).toBeVisible();
  await expect(page.getByRole("link", { name: /Synthetic .*Pakistan solar energy/ })).toHaveCount(0);
  await page.reload();
  await page.getByRole("button", { name: "Add to shortlist", exact: true }).first().click();
  await page.goto("/projects/pak-flood");
  await expect(page.getByRole("heading", { name: /Synthetic .*Pakistan flood protection/ })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("button", { name: "Shortlisted", exact: true }).first()).toBeVisible();
  await page.goto("/projects/pak-solar");
  await page.getByRole("button", { name: "Add to shortlist", exact: true }).first().click();
  await page.goto("/workspace");
  await page.getByRole("button", { name: "Compare selected projects" }).click();
  await expect(page.getByText(/Synthetic .*Pakistan flood protection/).first()).toBeVisible();
  await page.goto("/screening");
  await page.getByLabel("Project title", { exact: true }).fill("Solar energy demo");
  await page.getByRole("button", { name: "Analyze project", exact: true }).click();
  await expect(page.getByText("ILLUSTRATIVE SCREENING RESULTS")).toBeVisible();
  await page.goto("/challenges");
  await expect(page.getByText(/prior local evaluations/).first()).toBeVisible();
  expect(external).toEqual([]);
});

test("mobile search and direct project refresh", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/projects");
  await page.getByLabel("Search projects by keyword").fill("water");
  await page.getByRole("region", { name: "Find projects" }).getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByRole("link", { name: /Synthetic .*Pakistan water resilience/ }).first()).toBeVisible();
  await page.goto("/projects/pak-water");
  await page.reload();
  await expect(page.getByRole("heading", { name: /Synthetic .*Pakistan water resilience/ })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("all navigation views and recorded evidence load without a backend", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  for (const route of ["/", "/dashboard", "/analytics", "/analytics?tab=institutions", "/analytics?tab=approved", "/analytics?tab=profile", "/analytics?tab=coverage", "/scenarios", "/challenges", "/screening?project=pak-flood"]) {
    await page.goto(route);
    await expect(page.getByRole("note")).toContainText("Interactive demo");
    await page.waitForTimeout(500);
  }
  for (const challenge of ["c05", "c09", "c11"]) {
    const response = await page.request.get(`/evidence/${challenge}_scorecard.md`);
    expect(response.ok()).toBe(true);
  }
  expect(errors).toEqual([]);
});

