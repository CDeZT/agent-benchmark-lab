# Browser Visual Verification

The browser visual scorer is an evidence-producing evaluator, not a textual HTML check.

## Setup

```bash
python3 -m pip install -r requirements-browser.txt
npm ci
npx playwright install chromium
```

`agent-benchmark doctor` reports Node and the local Playwright Chromium path. `node_modules/` and downloaded browsers are local runtime assets, not committed benchmark evidence.

## Task Check

Use a `browser_screenshot` entry in `visual_checks`:

```json
{
  "type": "browser_screenshot",
  "path": "index.html",
  "viewport": {"width": 800, "height": 600},
  "required_selectors": ["h1", "#status"],
  "min_non_background_pixels": 200,
  "min_channel_stddev": 2.0
}
```

The evaluator opens the local HTML page in headless Chromium, checks that required selectors have a visible rendered box, saves a PNG under `runs/.../repetition_N/visual/`, and records screenshot size, non-background pixel count, and per-channel standard deviation.

If Node, Playwright, Chromium, or image inspection is unavailable, the check is marked `unavailable`; it does not become visual evidence coverage. Browser execution failures and failed visibility/pixel thresholds are recorded as verified failed evidence.

This first browser engine targets static local pages. Server-backed routes, interaction flows, reference-image diffs, and mobile viewport matrices remain later work.
