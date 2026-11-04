import { expect, test } from "@playwright/test";

// E2E for Part D: start a game, keep the opening hand, quick-save, return to the
// menu, and resume the saved game from the start screen. Also checks the SWUDB
// import box reports gaps. Requires the auto-started backend + dev server.
// HIDDEN 2026-09-01: these cover the start-screen tools (Resume a saved game /
// Import a deck), which are commented out in NewGameScreen.tsx. Un-skip with them.
// Before un-skipping: add the sign-in step from smoke.spec.ts, and give the e2e
// backend its own save folder, or this test overwrites data/saves/quicksave.json.
test.skip("save a game and resume it from the start screen", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));

  await page.goto("/");
  await page.getByRole("button", { name: /start game/i }).click();
  await expect(page.locator(".table")).toBeVisible();

  // Keep the opening hand (mulligan moment).
  const keep = page.getByRole("button", { name: /keep this hand/i });
  if (await keep.count()) await keep.click();

  // Quick-save, then reload to return to the menu.
  await page.getByTitle("Save game").click();
  await expect(page.getByText(/Game saved/)).toBeVisible();

  await page.reload();
  await expect(page.getByText("Resume a saved game")).toBeVisible();
  await page.getByRole("button", { name: "quicksave" }).click();

  // The resumed game shows the table again.
  await expect(page.locator(".table")).toBeVisible();
  expect(errors, errors.join("\n")).toHaveLength(0);
});

// HIDDEN 2026-09-01: these cover the start-screen tools (Resume a saved game /
// Import a deck), which are commented out in NewGameScreen.tsx. Un-skip with them.
test.skip("the SWUDB import box reports unplayable cards", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Import a deck (SWUDB)")).toBeVisible();
  const deck = JSON.stringify({
    leader: { id: "SHD_13" },
    base: { id: "SHD_24" },
    deck: [{ id: "SHD_160", count: 3 }],
  });
  await page.getByLabel("SWUDB decklist JSON").fill(deck);
  await page.getByRole("button", { name: "Check deck" }).click();
  await expect(page.getByText(/cards playable/)).toBeVisible();
});
