import { expect, test } from "@playwright/test";

for (const width of [390, 768, 1440]) {
  test(`Trust & Resilience live canonical screening at ${width}px`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto("/challenges");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Compassio Trust & Resilience");
    await expect(page.locator("article")).toHaveCount(3);
    const api = process.env.COMPASSIO_API_URL ?? "http://127.0.0.1:8000";
    const projectResponse = await request.get(`${api}/api/v1/projects/aiddata:35266`);
    expect(projectResponse.status()).toBe(200);
    const project = await projectResponse.json();
    await page.getByLabel("Project description", { exact: true }).fill(project.title.replace(/a/i, "$&\u200b"));
    const response = page.waitForResponse(r => r.url().endsWith("/api/v1/challenges/c09/screen") && r.request().method() === "POST");
    await page.getByRole("button", { name: "Run live input protection" }).click();
    const live = await response;
    expect(live.status()).toBe(200);
    const result = await live.json();
    expect(result.raw.model.artifact_sha256).toBe("654336052ba75aae97a5c20db1c3ce9bb06792640abe6f660973318852358574");
    expect(result.raw.model).toEqual(result.guarded.model);
    expect(result.raw.prediction.threshold).toBe(result.guarded.prediction.threshold);
    await expect(page.getByText(/Live model label scores/)).toBeVisible();
    for (const id of ["c05", "c09", "c11"]) {
      expect((await request.get(`/evidence/${id}_scorecard.md`)).status()).toBe(200);
    }
    await page.getByText("Demonstrate C05 locally", { exact: true }).click();
    await expect(page.getByText(/cli live --sample 3000/, { exact: false })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await page.evaluate(() => localStorage.setItem("compassio.theme", "dark"));
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await page.screenshot({ path: `../../artifacts/task012/showcase-dark-${width}.png`, fullPage: true });
  });
}

test("real C11 rejection exposes Retry-After and a typed recovery message", async ({ page, request }) => {
  const api = process.env.COMPASSIO_API_URL ?? "http://127.0.0.1:8000";
  const project = await (await request.get(`${api}/api/v1/projects/aiddata:35266`)).json();
  await page.goto("/challenges");
  await page.getByLabel("Project description", { exact: true }).fill(project.title);
  const rejection = await page.evaluate(async ({ api, title }) => {
    for (let i = 0; i < 12; i++) {
      const response = await fetch(`${api}/api/v1/challenges/c09/screen`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });
      if (response.status === 429) return { code: (await response.json()).code, retry: response.headers.get("Retry-After") };
      if (!response.ok) throw new Error(`Unexpected response: ${response.status}`);
    }
    throw new Error("The C11 demo configuration did not reject the bounded burst");
  }, { api, title: project.title });
  expect(rejection.code).toBe("rate_limited");
  expect(Number(rejection.retry)).toBeGreaterThanOrEqual(1);
  await page.getByRole("button", { name: "Run live input protection" }).click();
  await expect(page.getByRole("alert").getByText("Too many requests", { exact: true })).toBeVisible();
  await expect(page.getByText(/Try again in \d+ s\./)).toBeVisible();
});
