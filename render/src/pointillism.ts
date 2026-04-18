import { createCanvas, loadImage, Image } from "canvas";
import * as fs from "fs";
import * as path from "path";

interface Dot {
  x: number;
  y: number;
  r: number;
  rgb: [number, number, number];
}

interface DotsData {
  width: number;
  height: number;
  step: number;
  bg: [number, number, number];
  alpha: number;
  texture_dir: string | null;
  dots: Dot[];
}

async function loadTextures(dir: string): Promise<Image[]> {
  if (!fs.existsSync(dir)) return [];
  const files = fs.readdirSync(dir).filter((f) => /\.(png|jpg|jpeg)$/i.test(f));
  const results: Image[] = [];
  for (const f of files) {
    try {
      results.push(await loadImage(path.join(dir, f)));
    } catch {}
  }
  return results;
}

async function main() {
  const [, , inputPath, outputPath] = process.argv;
  if (!inputPath || !outputPath) {
    console.error("Usage: ts-node pointillism.ts <dots.json> <output.png>");
    process.exit(1);
  }

  const data: DotsData = JSON.parse(fs.readFileSync(inputPath, "utf8"));
  const { bg, step, alpha, texture_dir, dots } = data;
  const maxGradR = step / 2;

  const textures = texture_dir ? await loadTextures(texture_dir) : [];
  console.log(`loaded ${textures.length} brush textures`);

  // canvas size derived from actual dot extents, not original image dimensions
  const canvasW = Math.ceil(dots.reduce((m, d) => Math.max(m, d.x + maxGradR), 0));
  const canvasH = Math.ceil(dots.reduce((m, d) => Math.max(m, d.y + maxGradR), 0));

  const canvas = createCanvas(canvasW, canvasH);
  const ctx = canvas.getContext("2d");

  ctx.fillStyle = `rgb(${bg[0]},${bg[1]},${bg[2]})`;
  ctx.fillRect(0, 0, canvasW, canvasH);

  ctx.globalCompositeOperation = "source-over";

  for (const { x, y, r, rgb } of dots) {
    const [cr, cg, cb] = rgb;

    if (textures.length > 0) {
      const texture = textures[Math.floor(Math.random() * textures.length)];
      const size = r;
      const diameter = size * 2;

      // off-screen stamp: fill color, then clip to texture alpha
      const stamp = createCanvas(diameter, diameter);
      const sCtx = stamp.getContext("2d");

      sCtx.fillStyle = `rgba(${cr},${cg},${cb},${alpha})`;
      sCtx.fillRect(0, 0, diameter, diameter);

      sCtx.globalCompositeOperation = "destination-in";
      sCtx.save();
      sCtx.translate(size, size);
      sCtx.rotate(Math.random() * Math.PI * 2);
      sCtx.drawImage(texture, -size, -size, diameter, diameter);
      sCtx.restore();

      ctx.drawImage(stamp, x - size, y - size);
    } else {
      // fallback: radial gradient
      const gradR = Math.min(r, maxGradR);
      const grad = ctx.createRadialGradient(x, y, 0, x, y, gradR);
      grad.addColorStop(0, `rgba(${cr},${cg},${cb},${alpha})`);
      grad.addColorStop(0.5, `rgba(${cr},${cg},${cb},${(alpha * 0.6).toFixed(3)})`);
      grad.addColorStop(1, `rgba(${cr},${cg},${cb},0)`);
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(x, y, gradR, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  fs.writeFileSync(outputPath, canvas.toBuffer("image/png"));
  console.log(`rendered ${dots.length} dots → ${outputPath}`);
}

main();
