import { chromium } from "playwright";

function argument(name) {
  const index = process.argv.indexOf(name);
  if (index < 0 || !process.argv[index + 1]) {
    throw new Error(`Missing required argument: ${name}`);
  }
  return process.argv[index + 1];
}

const url = argument("--url");
const output = argument("--output");
const width = Number(argument("--width"));
const height = Number(argument("--height"));
const timeout = Number(argument("--timeout-ms"));
const selectors = JSON.parse(argument("--selectors"));

if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
  throw new Error("Viewport width and height must be positive numbers.");
}

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width, height } });
  await page.goto(url, { waitUntil: "load", timeout });
  const selectorResults = {};
  for (const selector of selectors) {
    selectorResults[selector] = await page.locator(selector).evaluateAll((elements) => elements.some((element) => {
      const style = window.getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity) > 0 && rect.width > 0 && rect.height > 0;
    }));
  }
  await page.screenshot({ path: output, fullPage: false });
  process.stdout.write(JSON.stringify({
    url,
    output,
    viewport: { width, height },
    selectors: selectorResults,
  }));
} finally {
  await browser.close();
}
