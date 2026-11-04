import { expect, test } from "@playwright/test";

// End-to-end smoke: create a game, play a few human actions against the bot,
// and reach a coherent in-progress (or finished) state — the UI equivalent of
// the backend's scripted-game test. Runs headless for CI.
test("play a few turns against the bot and stay coherent", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));

  await page.goto("/");
  // Sign in. The e2e backend's user store lives in test-results/, which
  // Playwright empties each run, so this normally creates the account.
  await page.getByLabel("Username").fill("player");
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByPlaceholder(/password/i).fill("e2e-password");
  await page.getByRole("button", { name: /create account|sign in/i }).click();

  await page.getByRole("button", { name: /start game/i }).click();

  // The table should appear (HUD + arenas).
  await expect(page.locator(".table")).toBeVisible();
  await expect(page.locator(".arena")).toHaveCount(2);

  // The mulligan moment opens first — keep the opening hand to proceed.
  const keep = page.getByRole("button", { name: /keep this hand/i });
  if (await keep.count()) await keep.click().catch(() => {});

  // Drive a handful of human actions; the bot turns resolve automatically.
  for (let i = 0; i < 16; i++) {
    await page.waitForTimeout(220);
    if (await page.locator(".end-screen").count()) break;
    // A late mulligan overlay (defensive) — dismiss it before clicking cards.
    const mull = page.getByRole("button", { name: /keep this hand/i });
    if (await mull.count()) {
      await mull.click().catch(() => {});
      continue;
    }

    // New-round pacing gate (B2): dismiss it to take our turn.
    const startTurn = page.getByRole("button", { name: /start round/i });
    if (await startTurn.count()) {
      await startTurn.click().catch(() => {});
      continue;
    }

    // Two-stage resourcing: once enough cards are staged, Confirm commits them.
    const confirmRes = page.getByRole("button", { name: /confirm resources/i });
    if ((await confirmRes.count()) && (await confirmRes.isEnabled().catch(() => false))) {
      await confirmRes.click().catch(() => {});
      continue;
    }

    const target = page.locator(".card.hl-target").first();
    if (await target.count()) {
      await target.click({ timeout: 700 }).catch(() => {});
      continue;
    }
    const legal = page.locator(".card.hl-legal");
    const n = await legal.count();
    if (n) {
      await legal
        .nth(i % n)
        .click({ timeout: 700 })
        .catch(() => {});
      continue;
    }
    const btn = page.locator(".action-buttons .btn").first();
    if (await btn.count()) {
      await btn.click({ timeout: 700 }).catch(() => {});
    }
  }

  // Coherent state: either still playing (HUD round visible) or a result screen.
  const finished = await page.locator(".end-screen").count();
  if (!finished) {
    await expect(page.locator(".topbar")).toBeVisible();
    await expect(page.locator(".topbar .pill", { hasText: /Round/ })).toBeVisible();
  }
  expect(errors, errors.join("\n")).toHaveLength(0);
});
