// Usage: node photos.mjs <outdir>   Live run on the shipped model (hybrid), 1920x1080 at 2x. Writes 01..06 PNGs.
import { chromium } from "playwright-core";
const out = process.argv[2], CASE = "test_iid-hard-23-00001";
const browser = await chromium.launch({ executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 2 });
page.on("pageerror", (e) => console.log("PAGEERROR", e.message));
const top = () => page.evaluate(() => document.querySelectorAll("*").forEach((e) => { if (e.scrollTop > 0) e.scrollTop = 0; }));
const snap = async (n) => { await page.waitForTimeout(500); await page.screenshot({ path: `${out}/${n}.png` }); console.log("shot", n); };
await page.goto(`http://localhost:8765/?case=${CASE}`);
await page.waitForSelector("#modelSeg button"); await page.waitForSelector("#srvStatus.up");
await page.waitForTimeout(1200);
// 05 first, idle: a messy scan next to the model switcher (nothing running yet)
await page.click('#docTabs [data-doc="D05"]'); await snap("05-messy-scan-and-model-switcher");
await page.click("#runBtn");
await page.waitForSelector(".call.ok", { timeout: 60000 }); await page.waitForTimeout(12000);
await snap("01-hybrid-pipeline-mid-run");
await page.waitForFunction(() => !document.body.classList.contains("running"), null, { timeout: 280000 });
await page.waitForTimeout(1500);
console.log(await page.evaluate(() => document.querySelector(".stats")?.innerText.replace(/\n/g, " | ")));
console.log(await page.evaluate(() => document.querySelector(".cards, .headline")?.innerText?.replace(/\n/g, " | ")));
await page.click('#callStrip button[data-doc="D01"]'); await top(); await snap("04-decision-trace-blocked-and-deferred");
// 03 totals vs truth: collapse the two open traces (clicking a row also moves panels 1 and 2 to that document)
await page.click('tbody[data-id="D02"] tr.main'); await page.click('tbody[data-id="D01"] tr.main');
await page.click('#callStrip button[data-doc="D01"]'); await top(); await snap("03-totals-vs-ground-truth");
// 02 panel 2: a messy WhatsApp document next to the JSON the model read
await page.click('#docTabs [data-doc="D05"]'); await page.click('#callStrip button[data-doc="D05"]'); await top(); await snap("02-messy-scan-and-model-json");
await page.goto("http://localhost:8765/results"); await page.waitForTimeout(1800); await snap("06-real-document-results");
await browser.close();
