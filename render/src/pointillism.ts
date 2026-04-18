import { createCanvas } from "canvas";
import * as fs from "fs";

interface Dot {
  x: number;
  y: number;
  r: number;
  rgb: [number, number, number];
}

interface DotsData {
  width: number;
  height: number;
  bg: [number, number, number];
  alpha: number;
  dots: Dot[];
}

const [, , inputPath, outputPath] = process.argv;

if (!inputPath || !outputPath) {
  console.error("Usage: ts-node pointillism.ts <dots.json> <output.png>");
  process.exit(1);
}

const data: DotsData = JSON.parse(fs.readFileSync(inputPath, "utf8"));
const { width, height, bg, alpha, dots } = data;

const canvas = createCanvas(width, height);
const ctx = canvas.getContext("2d");

ctx.fillStyle = `rgb(${bg[0]},${bg[1]},${bg[2]})`;
ctx.fillRect(0, 0, width, height);

ctx.globalCompositeOperation = "source-over";

for (const { x, y, r, rgb } of dots) {
  const [cr, cg, cb] = rgb;
  // radial gradient: opaque center → transparent edge, radius = r*2 for soft bleed
  const grad = ctx.createRadialGradient(x, y, 0, x, y, r * 2);
  grad.addColorStop(0, `rgba(${cr},${cg},${cb},${alpha})`);
  grad.addColorStop(0.55, `rgba(${cr},${cg},${cb},${(alpha * 0.5).toFixed(3)})`);
  grad.addColorStop(1, `rgba(${cr},${cg},${cb},0)`);

  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.arc(x, y, r * 2, 0, Math.PI * 2);
  ctx.fill();
}

fs.writeFileSync(outputPath, canvas.toBuffer("image/png"));
console.log(`rendered ${dots.length} dots → ${outputPath}`);
