/**
 * render.ts — Convert an ASCII art .txt to a styled terminal PNG.
 *
 * Usage:
 *   npx ts-node src/render.ts <input.txt> [output.png] [options]
 *
 * Options:
 *   --font-size <n>   Character size in CSS px (default: 14)
 *   --color <hex>     Text color (default: #33ff33)
 *   --min-height <n>  Minimum output PNG height in px (default: 1440)
 *   --info-panel      Add BBS header + Mayday 5525 info panel on the right
 */

import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import puppeteer from "puppeteer";

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const FONT_PATH = path.resolve(__dirname, "../../SarasaMonoSC-Regular.ttf");
const DEFAULT_FONT_SIZE = 14;
const DEFAULT_COLOR = "#ffffff";
const DEFAULT_MIN_HEIGHT = 1440;
const PADDING = 40; // px around the art

// ---------------------------------------------------------------------------
// CLI args
// ---------------------------------------------------------------------------

function parseArgs(argv: string[]): {
  txtPath: string;
  outputPath: string;
  fontSize: number;
  color: string;
  minHeight: number;
  infoPanel: boolean;
} {
  const args = argv.slice(2);

  const txtPath = args.find((a) => !a.startsWith("--"));
  if (!txtPath) {
    console.error(
      [
        "Usage: render <input.txt> [output.png] [options]",
        "Options:",
        "  --font-size <n>   default: 14",
        "  --color <hex>     default: #33ff33",
        "  --min-height <n>  default: 1440",
        "  --info-panel      add BBS header + Mayday 5525 panel",
      ].join("\n")
    );
    process.exit(1);
  }

  const positional = args.filter((a) => !a.startsWith("--"));
  const outputPath =
    positional[1] ?? txtPath.replace(/\.txt$/, "_rendered.png");

  const flag = (name: string, fallback: string): string => {
    const idx = args.indexOf(`--${name}`);
    return idx !== -1 && args[idx + 1] ? args[idx + 1] : fallback;
  };

  return {
    txtPath: path.resolve(txtPath),
    outputPath: path.resolve(outputPath),
    fontSize: parseInt(flag("font-size", String(DEFAULT_FONT_SIZE)), 10),
    color: flag("color", DEFAULT_COLOR),
    minHeight: parseInt(flag("min-height", String(DEFAULT_MIN_HEIGHT)), 10),
    infoPanel: args.includes("--info-panel"),
  };
}

// ---------------------------------------------------------------------------
// HTML helpers
// ---------------------------------------------------------------------------

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/** BBS-style login prompt rendered above the ASCII art. */
function bbsHeaderHtml(): string {
  return `
<div class="bbs-header">
  <span class="white">歡迎光臨 </span><span class="orange">5525</span><span class="white"> 回到第一天 [目前共有 </span><span class="yellow">5525</span><span class="white"> 人上線]</span><br>
  <span class="white">請輸入代號 (試用請輸入 \`</span><span class="green">guest</span><span class="white">\`，注冊請輸入 \`</span><span class="green">new</span><span class="white">\`) ：</span><span class="yellow">plumage</span><br>
  <span class="white">請輸入密碼：</span><span class="white">*******</span>
</div>`;
}

/** Mayday 5525 info panel rendered to the right of the ASCII art. */
function infoPanelHtml(): string {
  const crownLines = [
    "       /\\",
    "      /  \\",
    "|\\   /    \\   /|",
    "| \\ /      \\ / |",
    "|  X        X  |",
    "| / \\      / \\ |",
    "|/   \\    /   \\|",
    "|      ||      |",
    "|______/\\______|",
  ];
  const crown = crownLines.map((l) => escapeHtml(l)).join("\n");

  return `
<div class="info-panel">
  <div class="panel-inner">
    <div class="white" style="text-align:center;margin-bottom:8px;">25</div>
    <pre class="crown white">${crown}</pre>
    <div class="red panel-title">歡 迎 光 臨</div>
    <div class="cyan">5525 回到那一天 XMN 站</div>
    <div class="yellow">Welcome to #5525 LIVE TOUR</div>
    <div class="green panel-stars">****************************************</div>
    <div class="yellow">In 2025.5.25</div>
    <div class="yellow">5521~5525</div>
  </div>
</div>`;
}

// ---------------------------------------------------------------------------
// HTML template
// ---------------------------------------------------------------------------

function buildHtml(
  asciiText: string,
  fontSizePx: number,
  color: string,
  fontDataUri: string,
  infoPanel: boolean
): string {
  const lines = asciiText.split("\n");
  const maxLen = Math.max(...lines.map((l) => l.length));
  const paddedBody = lines.map((l) => l.padEnd(maxLen, " ")).join("\n");

  const header = infoPanel ? bbsHeaderHtml() : "";
  const panel = infoPanel ? infoPanelHtml() : "";

  return `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @font-face {
    font-family: 'SarasaMono';
    src: url('${fontDataUri}') format('truetype');
    font-weight: normal;
    font-style: normal;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body {
    background: #0a0a0a;
    display: inline-block;
  }
  .frame {
    padding: ${PADDING}px;
    background: #0a0a0a;
    font-family: 'SarasaMono', 'Courier New', monospace;
    font-size: ${fontSizePx}px;
    line-height: 1.4;
    letter-spacing: 0;
  }

  /* BBS header */
  .bbs-header {
    margin-bottom: ${PADDING}px;
    line-height: 1.6;
    white-space: nowrap;
  }

  /* ASCII art + panel side-by-side */
  .content-row {
    display: flex;
    align-items: center;
    gap: ${PADDING}px;
  }
  pre {
    font-family: inherit;
    font-size: inherit;
    line-height: 1;
    letter-spacing: 0;
    color: ${color};
    white-space: pre;
  }

  /* Info panel */
  .info-panel {
    flex-shrink: 0;
    width: 22em;
    border-left: 1px solid #333;
    padding-left: ${PADDING / 2}px;
  }
  .panel-inner {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    text-align: center;
  }
  .crown {
    line-height: 1.2;
    text-align: left;
    font-family: inherit;
    font-size: inherit;
    white-space: pre;
  }
  .panel-title { font-size: 1.4em; }
  .panel-stars { font-size: 0.7em; word-break: break-all; }

  /* Colour helpers */
  .white  { color: #c8c8c8; }
  .orange { color: #ff8c00; }
  .yellow { color: #ffff32; }
  .green  { color: #32c864; }
  .cyan   { color: #64ffc8; }
  .red    { color: #ff3232; }
</style>
</head>
<body>
<div class="frame">
  ${header}
  <div class="content-row">
    <pre>${escapeHtml(paddedBody)}</pre>
    ${panel}
  </div>
</div>
</body>
</html>`;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function render(
  txtPath: string,
  outputPath: string,
  fontSize: number,
  color: string,
  minHeight: number,
  infoPanel: boolean
): Promise<void> {
  if (!fs.existsSync(txtPath)) {
    throw new Error(`Input file not found: ${txtPath}`);
  }

  const asciiText = fs.readFileSync(txtPath, "utf-8");

  const fontData = fs.readFileSync(FONT_PATH);
  const fontDataUri = `data:font/truetype;base64,${fontData.toString("base64")}`;

  const html = buildHtml(asciiText, fontSize, color, fontDataUri, infoPanel);

  const tmpHtml = path.join(os.tmpdir(), `geink_render_${Date.now()}.html`);
  fs.writeFileSync(tmpHtml, html, "utf-8");

  const browser = await puppeteer.launch({ headless: true });
  try {
    const page = await browser.newPage();

    // Pass 1 — large unconstrained viewport, measure natural content size
    await page.setViewport({ width: 8000, height: 4000, deviceScaleFactor: 1 });
    await page.goto(`file://${tmpHtml}`, { waitUntil: "networkidle0" });

    // Compute frame dimensions:
    //   - <pre> height = 70% of total height
    //   - total aspect ratio = 3:4 (portrait)
    // Take whichever constraint needs more space so nothing is clipped.
    const { frameW, frameH } = await page.evaluate((padding: number) => {
      const frame = document.querySelector(".frame") as HTMLElement;
      const pre   = document.querySelector("pre")   as HTMLElement;

      const preH      = pre.scrollHeight;
      const naturalW  = frame.scrollWidth;
      const naturalH  = frame.scrollHeight;

      // From 70% rule
      const hFromPre  = Math.ceil(preH / 0.8);
      const wFromPre  = Math.ceil(hFromPre * 3 / 4);  // portrait 3:4

      // From 3:4 rule applied to natural content width
      const hFromW    = Math.ceil(naturalW * 4 / 3);
      const wFromW    = naturalW;

      // Pick whichever is larger so both constraints are satisfied
      let totalW: number, totalH: number;
      if (wFromPre >= wFromW) {
        totalW = wFromPre;
        totalH = hFromPre;
      } else {
        totalW = wFromW;
        totalH = Math.max(hFromW, hFromPre); // still respect 70% rule
      }

      // Distribute extra space as padding
      const extraV = Math.max(0, totalH - naturalH);
      const extraH = Math.max(0, totalW - naturalW);

      frame.style.paddingTop    = padding + extraV / 2 + "px";
      frame.style.paddingBottom = padding + extraV / 2 + "px";
      frame.style.paddingLeft   = padding + extraH / 2 + "px";
      frame.style.paddingRight  = padding + extraH / 2 + "px";
      frame.style.width         = totalW + "px";
      frame.style.height        = totalH + "px";

      return { frameW: totalW, frameH: totalH };
    }, PADDING);

    // Pass 2 — set exact viewport and scale for minHeight
    const scale = Math.max(1, Math.ceil(minHeight / frameH));

    await page.setViewport({
      width: frameW,
      height: frameH,
      deviceScaleFactor: scale,
    });

    await page.goto(`file://${tmpHtml}`, { waitUntil: "networkidle0" });

    // Re-apply layout after reload (viewport change invalidates the DOM edits)
    await page.evaluate((args: { padding: number; frameW: number; frameH: number }) => {
      const { padding, frameW, frameH } = args;
      const frame = document.querySelector(".frame") as HTMLElement;
      const pre   = document.querySelector("pre")   as HTMLElement;

      const preH     = pre.scrollHeight;
      const naturalW = frame.scrollWidth;
      const naturalH = frame.scrollHeight;

      const extraV = Math.max(0, frameH - naturalH);
      const extraH = Math.max(0, frameW - naturalW);

      frame.style.paddingTop    = padding + extraV / 2 + "px";
      frame.style.paddingBottom = padding + extraV / 2 + "px";
      frame.style.paddingLeft   = padding + extraH / 2 + "px";
      frame.style.paddingRight  = padding + extraH / 2 + "px";
      frame.style.width         = frameW + "px";
      frame.style.height        = frameH + "px";
    }, { padding: PADDING, frameW, frameH });

    await page.screenshot({ path: outputPath as `${string}.png`, fullPage: false });

    const finalW = frameW * scale;
    const finalH = frameH * scale;
    console.log(`Rendered: ${outputPath} (${finalW}×${finalH}px, scale=${scale}×)`);
  } finally {
    await browser.close();
    fs.unlinkSync(tmpHtml);
  }
}

const { txtPath, outputPath, fontSize, color, minHeight, infoPanel } =
  parseArgs(process.argv);

render(txtPath, outputPath, fontSize, color, minHeight, infoPanel).catch((err) => {
  console.error(err);
  process.exit(1);
});
