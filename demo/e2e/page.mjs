// Usage: node page.mjs <path> <out.png>   e.g. node page.mjs /results shot.png
import { chromium } from "playwright-core";
const [path, out] = process.argv.slice(2);
const browser = await chromium.launch({ executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
page.on("pageerror", (e) => console.log("PAGEERROR", e.message));
await page.goto(`http://localhost:8765${path}`);
await page.waitForTimeout(1500);
await page.screenshot({ path: out, fullPage: true });
await browser.close();
