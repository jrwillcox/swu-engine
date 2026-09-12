// Quick visual check: start a game, play a few human actions, screenshot.
import { chromium } from "@playwright/test";

const URL = process.env.SWU_URL ?? "http://localhost:5173";
const OUT = process.argv[2] ?? "screenshot.png";

const VW = Number(process.env.SWU_VW ?? 1440);
const VH = Number(process.env.SWU_VH ?? 900);
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: VW, height: VH } });
await page.addInitScript(() => localStorage.setItem("swu.speed", '"fast"'));
const log = [];
page.on("console", (m) => log.push(`[console] ${m.text()}`));
page.on("pageerror", (e) => log.push(`[pageerror] ${e.message}`));

await page.goto(URL, { waitUntil: "networkidle" });
await page.getByRole("button", { name: /start game/i }).click();

const steps = Number(process.argv[3] ?? 60);
for (let i = 0; i < steps; i++) {
  await page.waitForTimeout(260);
  // Targeting: if a target is highlighted, complete the action.
  const target = page.locator(".card.hl-target").first();
  if (await target.count()) {
    try {
      await target.click({ timeout: 700 });
      continue;
    } catch {
      /* */
    }
  }
  // Prefer attacking (units in my ground/space arena), then playing from hand.
  const legal = page.locator(".card.hl-legal");
  const n = await legal.count();
  if (n) {
    try {
      await legal.nth(i % n).click({ timeout: 700 });
      continue;
    } catch {
      /* */
    }
  }
  // Context action (after selecting a multi-option card).
  const ctx = page.locator(".action-buttons .btn").first();
  if (await ctx.count()) {
    try {
      await ctx.click({ timeout: 700 });
    } catch {
      /* */
    }
  }
}
await page.mouse.move(2, 2); // move pointer away so the hover-zoom doesn't cover the board
await page.waitForTimeout(700);
await page.screenshot({ path: OUT, fullPage: false });
console.log("Saved", OUT);
if (log.length) console.log(log.join("\n"));
await browser.close();
