import { expect, test } from "@playwright/test";

// Bases and leaders in the rail must keep their 418:300 card shape whatever the
// pixel size of their art. An older iPad Safari that didn't apply aspect-ratio
// there sized each card from its image's pixel width, so a 1000px-wide leader
// image turned into a long thin strip. Current browsers apply aspect-ratio, so
// the test switches it off to stand in for that browser. Only WebKit shows the
// bug that way (Chromium still sizes the card correctly), so this file runs on
// WebKit: `npx playwright install webkit` once.
test.use({ browserName: "webkit" });

test("bases and leaders keep their card shape with high-res art", async ({ page }) => {
  await page.setViewportSize({ width: 1180, height: 820 });
  await page.goto("/");
  await page.getByLabel("Username").fill("player");
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByPlaceholder(/password/i).fill("e2e-password");
  await page.getByRole("button", { name: /create account|sign in/i }).click();
  await page.getByRole("button", { name: /start game/i }).click();
  await expect(page.locator(".table")).toBeVisible();

  await page.addStyleTag({ content: ".card { aspect-ratio: auto !important; }" });
  // Give every leader in-memory art 1000px wide (bases stay at their usual size).
  await page.$$eval(".base-slot .card.leader img", (imgs) => {
    const svg =
      '<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="716">' +
      '<rect width="1000" height="716" fill="teal"/></svg>';
    for (const img of imgs)
      (img as HTMLImageElement).src = "data:image/svg+xml," + encodeURIComponent(svg);
  });
  await page.waitForTimeout(300);

  const cards = page.locator(".base-slot .card.landscape");
  expect(await cards.count()).toBeGreaterThanOrEqual(4);
  for (const box of await cards.evaluateAll((els) => els.map((e) => e.getBoundingClientRect()))) {
    expect(box.width / box.height).toBeCloseTo(418 / 300, 1);
  }
});
