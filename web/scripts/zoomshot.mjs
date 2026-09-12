import { chromium } from "@playwright/test";
const URL = process.env.SWU_URL ?? "http://localhost:5173";
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.addInitScript(() => localStorage.setItem("swu.speed", '"fast"'));
await page.goto(URL, { waitUntil: "networkidle" });
await page.getByRole("button", { name: /start game/i }).click();
await page.waitForTimeout(800);
// Hover my leader (a Leader card in my rail) to trigger the landscape zoom.
const leader = page.locator(".rail .card.leader").last();
await leader.hover();
await page.waitForTimeout(400);
await page.screenshot({ path: process.argv[2] ?? "zoom.png" });
console.log("zoom faces:", await page.locator(".card-zoom .zoom-face").count());
await browser.close();
