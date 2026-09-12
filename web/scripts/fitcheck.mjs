// Check whether the action bar is on-screen at common laptop viewport heights,
// at the very start of a game (mulligan), where only the buttons can progress.
import { chromium } from "@playwright/test";
const URL = process.env.SWU_URL ?? "http://localhost:5173";
const browser = await chromium.launch();

for (const vh of [900, 768, 720, 650]) {
  const page = await browser.newPage({ viewport: { width: 1366, height: vh } });
  await page.goto(URL, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: /start game/i }).click();
  await page.waitForTimeout(600);
  const bar = await page
    .locator(".action-bar")
    .boundingBox()
    .catch(() => null);
  const btns = await page.locator(".action-buttons .btn").allTextContents();
  const onScreen = bar ? bar.y + bar.height <= vh + 1 : false;
  console.log(
    `vh=${vh} | action-bar bottom=${bar ? Math.round(bar.y + bar.height) : "MISSING"} | onScreen=${onScreen} | buttons=${JSON.stringify(btns)}`,
  );
  await page.close();
}
await browser.close();
