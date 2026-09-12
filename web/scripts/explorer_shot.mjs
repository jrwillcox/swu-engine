import { chromium } from "@playwright/test";

const base = process.env.URL ?? "http://127.0.0.1:5174";
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
page.on("console", (m) => console.log("PAGE:", m.type(), m.text()));
page.on("pageerror", (e) => console.log("PAGEERROR:", e.message));

await page.goto(base, { waitUntil: "networkidle" });
await page.getByText("Browse the card explorer").click();
await page.waitForSelector(".xtile-img", { timeout: 15000 });
await page.waitForTimeout(1500); // let lazy images settle
await page.screenshot({ path: "screenshots/explorer-grid.png" });

// Apply a filter and open a zoom.
await page.getByLabel("Available").selectOption("yes");
await page.getByLabel("Aspect").selectOption("Heroism");
await page.waitForTimeout(800);
await page.screenshot({ path: "screenshots/explorer-filtered.png" });

await page.locator(".xtile-img").first().click();
await page.waitForSelector(".xzoom", { timeout: 5000 });
await page.waitForTimeout(800);
await page.screenshot({ path: "screenshots/explorer-zoom.png" });

const count = await page.locator(".xtile").count();
console.log("RENDERED TILES:", count);
await browser.close();
