// Diagnose clickability: drive into ACTION phase, click a legal card with a real
// mouse event, and report whether an action POST fired and what the UI showed.
import { chromium } from "@playwright/test";

const URL = process.env.SWU_URL ?? "http://localhost:5173";
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.addInitScript(() => localStorage.setItem("swu.speed", '"fast"'));
const posts = [];
page.on("request", (r) => {
  if (r.method() === "POST" && /\/actions\/|\/advance/.test(r.url()))
    posts.push(r.url().split("/api/games/")[1]);
});
page.on("pageerror", (e) => console.log("PAGEERROR", e.message));

await page.goto(URL, { waitUntil: "networkidle" });
await page.getByRole("button", { name: /start game/i }).click();

// Advance through setup using buttons until we reach ACTION (legal cards appear).
for (let i = 0; i < 40; i++) {
  await page.waitForTimeout(150);
  const phase = await page
    .locator(".hud .pill.phase")
    .textContent()
    .catch(() => "");
  const legalCount = await page.locator(".card.hl-legal").count();
  if (phase && phase.includes("ACTION") && legalCount > 0) break;
  // setup: prefer a legal card (resource), else first control button
  const legal = page.locator(".card.hl-legal").first();
  if (await legal.count()) {
    await legal.click({ timeout: 600 }).catch(() => {});
    continue;
  }
  const btn = page.locator(".action-buttons .btn").first();
  if (await btn.count()) await btn.click({ timeout: 600 }).catch(() => {});
}

const phase = await page
  .locator(".hud .pill.phase")
  .textContent()
  .catch(() => "?");
const legalCount = await page.locator(".card.hl-legal").count();
console.log("PHASE:", phase, "| awaiting legal cards:", legalCount);

const before = posts.length;
if (legalCount > 0) {
  const card = page.locator(".card.hl-legal").first();
  const name = await card.getAttribute("data-card-name");
  const box = await card.boundingBox();
  console.log(
    "Clicking legal card:",
    name,
    "box:",
    box && `${Math.round(box.width)}x${Math.round(box.height)}`,
  );
  await card.hover();
  await page.waitForTimeout(120);
  await card.click({ timeout: 1000 }).catch((e) => console.log("CLICK FAILED", e.message));
  await page.waitForTimeout(400);
}
const ctxBtns = await page.locator(".action-buttons .btn").allTextContents();
console.log("POSTs fired by click:", posts.length - before);
console.log("Action bar buttons after click:", ctxBtns);
console.log("All POSTs so far:", posts.length);
await browser.close();
