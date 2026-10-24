// Usage: node shot.mjs <out.png> [--kind hybrid|e2e] [--mode live|replay] [--model base:sft] [--case ID] [--speed 8] [--wait-done] [--click-row D01]
import { chromium } from "playwright-core";

const a = process.argv.slice(2), out = a[0];
const opt = (k, d) => (a.includes(`--${k}`) ? a[a.indexOf(`--${k}`) + 1] : d);
const browser = await chromium.launch({ executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
page.on("pageerror", (e) => console.log("PAGEERROR", e.message));
page.on("console", (m) => m.type() === "error" && console.log("CONSOLE", m.text()));
await page.goto(`http://localhost:8765/?case=${opt("case", "easy-21-00001")}`);
await page.waitForSelector("#caseSel option", { state: "attached" });
await page.waitForSelector("#srvStatus.up, #srvStatus.down");
await page.waitForSelector("#modelSeg button");
await page.waitForTimeout(800);
if (opt("mode") === "replay") await page.waitForFunction(() => document.querySelector('#modeSeg [data-mode="replay"]'));
if (opt("kind")) await page.click(`#kindSeg [data-kind="${opt("kind")}"]`);
if (opt("mode")) await page.click(`#modeSeg [data-mode="${opt("mode")}"]`);
if (opt("speed")) await page.click(`#speedSeg [data-speed="${opt("speed")}"]`);
if (opt("model")) await page.click(`#modelSeg [data-model="${opt("model")}"]`);
if (a.includes("--run")) {
  await page.click("#runBtn");
  const midShot = opt("mid");
  if (midShot) { await page.waitForTimeout(+midShot); await page.screenshot({ path: out.replace(".png", "-mid.png") }); }
  await page.waitForFunction(() => !document.body.classList.contains("running"), null, { timeout: 280000 });
  await page.waitForTimeout(1200);
}
if (opt("click-row")) { await page.click(`tbody[data-id="${opt("click-row")}"] tr.main`); await page.waitForTimeout(400); }
await page.screenshot({ path: out });
await browser.close();
