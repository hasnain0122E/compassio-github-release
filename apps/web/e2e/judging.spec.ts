import { expect, test, type Page } from "@playwright/test";

async function save(page: Page, id: string) {
  await page.goto(`/projects/${encodeURIComponent(id)}`);
  await page
    .getByRole("button", { name: "Add to shortlist", exact: true })
    .first()
    .click();
  await expect(
    page.getByRole("button", { name: "Shortlisted", exact: true }).first(),
  ).toBeVisible();
}
async function settled(page: Page) {
  await expect(page.locator(".skeleton:visible")).toHaveCount(0);
}
async function noOverflow(page: Page) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBe(true);
}

test("Discover flood projects in Pakistan, understand evidence, shortlist and compare", async ({
  page,
}) => {
  await page.goto("/projects");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Find projects worth a closer look.",
  );
  await expect(page.getByRole("table")).toHaveCount(0);
  await expect(page.locator("#f-source")).not.toBeVisible();
  await page.locator("#f-q").fill("flood");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page).toHaveURL(/q=flood/);
  await page.locator("#f-country").selectOption("PAK");
  await expect(page).toHaveURL(/country=PAK/);
  await settled(page);
  const firstTitle = await page.locator("article h2").first().innerText();
  await page
    .getByRole("link", { name: "View project", exact: true })
    .first()
    .click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(firstTitle);
  await expect(
    page.getByRole("heading", { name: "What is this project?" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "What do we know about its funding?" }),
  ).toBeVisible();
  await expect(page.getByRole("table")).not.toBeVisible();
  await page.getByText("View evidence and sources", { exact: true }).click();
  await expect(
    page.getByText("Source and provenance", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Add to shortlist", exact: true })
    .first()
    .click();
  await page.goto("/projects?q=flood&country=PAK");
  await settled(page);
  await page
    .getByRole("button", { name: "Add to shortlist", exact: true })
    .first()
    .click();
  await page.goto("/workspace");
  await expect(page.getByText("2 of 10 projects saved")).toBeVisible();
  const comparison = page.waitForResponse(
    (r) =>
      r.url().endsWith("/decision/compare") && r.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Compare selected projects", exact: true })
    .click();
  expect((await comparison).ok()).toBe(true);
  await expect(
    page.getByRole("heading", {
      name: "Funding side by side",
    }),
  ).toBeVisible();
  await page.screenshot({
    path: "../../artifacts/frontend/redesign-shortlist-comparison.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 900 });
  await noOverflow(page);
  await page.screenshot({ path: "../../artifacts/frontend/redesign-390-comparison.png", fullPage: true });
});

test("topic suggestions, drawer, URL chips and reset use real keyword filters", async ({
  page,
}) => {
  await page.goto("/projects");
  await page.getByRole("button", { name: "Clean energy", exact: true }).click();
  await expect(page).toHaveURL(/q=solar/);
  await expect(page.locator("#f-q")).toHaveValue("solar");
  await page.getByRole("button", { name: "More filters", exact: true }).click();
  await expect(
    page.getByRole("dialog", { name: "More filters", exact: true }),
  ).toBeVisible();
  await page.locator("#f-source").selectOption("aiddata");
  await page.locator("#f-climate").selectOption("true");
  await page.setViewportSize({ width: 390, height: 900 });
  await noOverflow(page);
  await page.screenshot({ path: "../../artifacts/frontend/redesign-390-filter-drawer.png", fullPage: true });
  await page
    .getByRole("button", { name: "Show projects", exact: true })
    .click();
  await expect(page).toHaveURL(/source=aiddata/);
  await expect(page).toHaveURL(/climate_related=true/);
  await expect(
    page.getByRole("button", { name: "More filters", exact: true }),
  ).toBeFocused();
  await page.getByRole("button", { name: "Reset", exact: true }).click();
  await expect(page).toHaveURL(/\/projects$/);
  await expect(page.locator("#f-q")).toHaveValue("");
});

test("empty shortlist guides discovery and duplicate funding warnings remain intact", async ({
  page,
}) => {
  await page.goto("/workspace");
  await expect(
    page.getByRole("heading", { name: "Your shortlist is empty." }),
  ).toBeVisible();
  await save(page, "climate_funds_update:projects-r10");
  await save(page, "gcf_projects:FP005");
  await page.goto("/workspace");
  await page.getByRole("button", { name: "Compare selected projects", exact: true }).click();
  await expect(page.getByText("Probably the same project in two sources", { exact: true })).toBeVisible();
  for (let i = 0; i < 2; i++) {
    await page.getByRole("button", { name: /^Remove / }).first().click();
  }
  await expect(page.getByRole("textbox")).toHaveCount(0);
  await save(page, "aiddata:35266");
  await save(page, "aiddata:54087");
  await page.goto("/workspace");
  await page
    .getByRole("button", { name: "Compare selected projects", exact: true })
    .click();
  await expect(
    page.getByText("Same funding package", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("No total:", { exact: false }).first(),
  ).toBeVisible();
  await page
    .getByRole("button", { name: /^Remove / })
    .first()
    .click();
  await page
    .getByRole("button", { name: /^Remove / })
    .first()
    .click();
  await expect(
    page.getByRole("heading", { name: "Your shortlist is empty." }),
  ).toBeVisible();
});

test("analysis gives a real ML v2 signal with optional details and same-input v1 comparison", async ({
  page,
}) => {
  await page.goto("/screening");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Compassio Climate Intelligence",
  );
  await expect(page.getByRole("table")).not.toBeVisible();
  await page
    .locator("#s-title")
    .fill("Example solar mini-grid for rural health clinics");
  await page
    .locator("#s-desc")
    .fill(
      "Example text: install solar photovoltaic panels and battery storage to replace diesel generators at district health facilities.",
    );
  const response = page.waitForResponse((r) =>
    r.url().endsWith("/screening/text"),
  );
  await page
    .getByRole("button", { name: "Analyze project", exact: true })
    .click();
  const data = await (await response).json();
  expect(data.model.model_key).toBe("ml_v2");
  expect(data.prediction.is_climate_related).toBe(true);
  await expect(
    page.getByRole("heading", {
      name: "Potentially climate-related",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "What influenced the result?",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Compare with ML v1" }),
  ).not.toBeVisible();
  await page.getByText("Model details", { exact: true }).click();
  await page.locator("#s-title").fill("Unsubmitted edited title");
  const comparison = page.waitForResponse((r) =>
    r.url().endsWith("/screening/text"),
  );
  await page.getByRole("button", { name: "Compare with ML v1" }).click();
  const compared = await comparison;
  expect(compared.request().postDataJSON().title).toBe(
    "Example solar mini-grid for rural health clinics",
  );
  expect((await compared.json()).model.model_key).toBe("ml_v1");
  await page.getByText("Model details", { exact: true }).click();
  await page.screenshot({
    path: "../../artifacts/frontend/redesign-analysis-result.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 900 });
  await noOverflow(page);
  await page.screenshot({ path: "../../artifacts/frontend/redesign-390-analysis-result.png", fullPage: true });
});

test("permitted record analysis and denied access keep source restrictions", async ({
  page,
}) => {
  await page.goto("/screening?project=aiddata%3A35266");
  await expect(
    page.getByRole("heading", {
      name: "Potentially climate-related",
      exact: true,
    }),
  ).toBeVisible();
  await page.getByText("Model details", { exact: true }).click();
  await expect(
    page.getByText("Screened record: aiddata:35266", { exact: false }),
  ).toBeVisible();
  await page.goto("/projects/gcf_projects%3AFP085");
  await expect(
    page.getByRole("link", { name: "Analyze climate relevance", exact: true }),
  ).toHaveCount(0);
  await page.goto("/screening?project=gcf_projects%3AFP085");
  await expect(
    page.getByText("source_not_permitted_for_model_input", { exact: false }),
  ).toBeVisible();
});

test("prioritization organizes only the saved shortlist", async ({ page }) => {
  await save(page, "aiddata:35266");
  await save(page, "aiddata:54087");
  await page.goto("/workspace?tab=prioritize");
  await expect(page.getByRole("slider")).not.toBeVisible();
  const response = page.waitForResponse((r) =>
    r.url().endsWith("/decision/prioritize"),
  );
  await page
    .getByRole("button", { name: "Prioritize my shortlist", exact: true })
    .click();
  const ranked = await response;
  expect(ranked.request().postDataJSON().filters.project_ids).toEqual([
    "aiddata:35266",
    "aiddata:54087",
  ]);
  expect((await ranked.json()).candidates).toBe(2);
  await page
    .getByText("Why this rank: score breakdown", { exact: true })
    .first()
    .click();
  await page.setViewportSize({ width: 390, height: 900 });
  await noOverflow(page);
  await page.screenshot({ path: "../../artifacts/frontend/redesign-390-priorities.png", fullPage: true });
});

test("secondary scenario conserves the hypothetical budget", async ({
  page,
}) => {
  for (const id of [
    "climate_funds_update:projects-r1115",
    "climate_funds_update:projects-r300",
    "climate_funds_update:projects-r315",
  ])
    await save(page, id);
  await page.goto("/workspace");
  await page
    .getByRole("link", {
      name: "Explore a hypothetical funding scenario",
      exact: true,
    })
    .click();
  await expect(page.locator("#b-obj")).not.toBeVisible();
  const response = page.waitForResponse((r) =>
    r.url().endsWith("/decision/scenarios"),
  );
  await page
    .getByRole("button", { name: "Run hypothetical scenario", exact: true })
    .click();
  const data = await (await response).json();
  expect(data.allocated_total).toBe("1000000.00");
  expect(data.unallocated).toBe("0.00");
  await page.locator("#b-amount").fill("-1");
  await expect(
    page.getByRole("button", {
      name: "Run hypothetical scenario",
      exact: true,
    }),
  ).toBeDisabled();
});

test("advanced insights remain available; errors and empty searches recover", async ({
  page,
}) => {
  await page.goto("/analytics");
  for (const name of [
    "Countries",
    "Sectors",
    "Institutions",
    "Approved vs disbursed",
    "Climate labels",
    "Country profile",
    "Coverage & freshness",
  ]) {
    await page.getByRole("tab", { name, exact: true }).click();
    await settled(page);
    await expect(
      page.getByRole("alert").filter({ hasText: "Code:" }),
    ).toHaveCount(0);
  }
  await page.goto("/projects?q=example_nonexistent_783920");
  await expect(
    page.getByText("Let's try a broader search", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Reset search", exact: true }).click();
  await expect(page.locator("article").first()).toBeVisible();
  await page.goto("/projects/example_source%3Amissing");
  await expect(
    page.getByText("project_not_found", { exact: false }),
  ).toBeVisible();
  await page.route("**/api/v1/**", (r) => r.abort("failed"));
  await page.goto("/projects");
  await expect(
    page.getByText("The Compassio API is not running", { exact: true }).first(),
  ).toBeVisible();
  await page.unroute("**/api/v1/**");
  await page.getByRole("button", { name: /Retry/ }).first().click();
  await expect(page.locator("article").first()).toBeVisible();
});

for (const width of [390, 768, 1440])
  test(`focused product at ${width}px, dark mode and keyboard`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    for (const route of [
      "/",
      "/dashboard",
      "/projects?country=PAK&q=flood",
      "/projects/aiddata%3A35266",
      "/screening",
      "/workspace",
      "/analytics",
      "/scenarios",
      "/challenges",
    ]) {
      await page.goto(route);
      await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
      await settled(page);
      await noOverflow(page);
      await page.screenshot({
        path: `../../artifacts/frontend/redesign-${width}-${route.replace(/[^a-z0-9]/gi, "_")}.png`,
        fullPage: true,
      });
    }
    await page.goto("/projects?country=PAK&q=flood");
    await settled(page);
    if (width < 1024) {
      await page.getByRole("button", { name: "Open menu" }).click();
      await expect(
        page.getByRole("dialog", { name: "Menu", exact: true }),
      ).toBeVisible();
      await expect(
        page
          .getByRole("dialog", { name: "Menu", exact: true })
          .getByRole("link"),
      ).toHaveCount(5);
      await page
        .getByRole("button", { name: "Dark theme", exact: true })
        .click();
      await page.keyboard.press("Escape");
      await expect(
        page.getByRole("button", { name: "Open menu" }),
      ).toBeFocused();
    } else {
      await expect(
        page
          .getByRole("navigation", { name: "Main", exact: true })
          .first()
          .getByRole("link"),
      ).toHaveCount(4);
      await page.getByRole("button", { name: "Switch colour theme" }).click();
    }
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await noOverflow(page);
    await page.screenshot({
      path: `../../artifacts/frontend/redesign-${width}-dark-discover.png`,
      fullPage: true,
    });
    await page.keyboard.press("Control+k");
    await page
      .getByRole("textbox", { name: "Command", exact: true })
      .fill("Discover");
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/projects/);
    expect(errors).toEqual([]);
  });
