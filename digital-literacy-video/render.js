// 用法：node render.js [輸出檔名=digital-literacy.mp4] [--fps 30]
//       node render.js --shots 3,12,30   （只截圖指定秒數，用於檢查）
const path = require("path");
const fs = require("fs");
const { spawn, execFileSync } = require("child_process");
let chromium;
try { ({ chromium } = require("playwright")); } catch { ({ chromium } = require("/opt/node22/lib/node_modules/playwright")); }

const args = process.argv.slice(2);
const opt = k => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : null; };
const FPS = +(opt("--fps") || 30);
const shots = opt("--shots");
const shotDir = opt("--shot-dir") || path.join(__dirname, "shots");
const out = path.resolve(args.find(a => a.endsWith(".mp4")) || path.join(__dirname, "digital-literacy.mp4"));
const ROOT = path.resolve(__dirname, "..");

// 簡易靜態伺服器（避免 file:// 字型與圖片限制）
const http = require("http");
const types = { ".html": "text/html", ".js": "text/javascript", ".svg": "image/svg+xml", ".ttf": "font/ttf", ".mp3": "audio/mpeg" };
const server = http.createServer((req, res) => {
  const f = path.join(ROOT, decodeURIComponent(req.url.split("?")[0]));
  if (!f.startsWith(ROOT) || !fs.existsSync(f)) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { "Content-Type": types[path.extname(f)] || "application/octet-stream" });
  fs.createReadStream(f).pipe(res);
});

(async () => {
  await new Promise(r => server.listen(0, r));
  const url = `http://127.0.0.1:${server.address().port}/digital-literacy-video/index.html?render=1`;
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
  await page.goto(url, { waitUntil: "networkidle" });
  await page.evaluate(() => document.fonts.ready);
  const total = await page.evaluate(() => window.TOTAL);
  const cues = await page.evaluate(() => window.AUDIO_CUES);
  console.log(`影片長度 ${total.toFixed(2)} 秒，旁白 ${cues.length} 段`);

  if (shots) {
    fs.mkdirSync(shotDir, { recursive: true });
    for (const s of shots.split(",").map(Number)) {
      await page.evaluate(t => window.seek(t), s);
      await page.screenshot({ path: path.join(shotDir, `t${String(s).padStart(5, "0")}.png`) });
    }
    await browser.close(); server.close(); return;
  }

  const silent = out.replace(/\.mp4$/, ".silent.mp4");
  const ff = spawn("ffmpeg", ["-v", "error", "-y", "-f", "image2pipe", "-framerate", String(FPS), "-i", "-",
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "20", silent], { stdio: ["pipe", "inherit", "inherit"] });
  const frames = Math.ceil(total * FPS);
  for (let i = 0; i < frames; i++) {
    await page.evaluate(t => window.seek(t), i / FPS);
    const buf = await page.screenshot({ type: "jpeg", quality: 92 });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once("drain", r));
    if (i % (FPS * 5) === 0) process.stdout.write(`\r${(i / FPS).toFixed(0)}s / ${total.toFixed(0)}s`);
  }
  ff.stdin.end();
  await new Promise(r => ff.on("close", r));
  await browser.close(); server.close();
  console.log("\n合成音訊…");

  // 旁白依時間點放置，背景音樂循環並在旁白時自動壓低（ducking）
  const inputs = [], filters = [];
  cues.forEach((c, i) => {
    inputs.push("-i", path.join(__dirname, c.file));
    const ms = Math.round(c.start * 1000);
    filters.push(`[${i + 1}:a]aformat=sample_rates=44100:channel_layouts=stereo,adelay=${ms}|${ms}[v${i}]`);
  });
  const n = cues.length;
  filters.push(`${cues.map((_, i) => `[v${i}]`).join("")}amix=inputs=${n}:normalize=0,apad,atrim=0:${total.toFixed(3)},asplit=2[voice][key]`);
  filters.push(`[${n + 1}:a]aformat=sample_rates=44100:channel_layouts=stereo,volume=0.32,atrim=0:${total.toFixed(3)},afade=t=out:st=${(total - 2).toFixed(2)}:d=2[bgm]`);
  filters.push(`[bgm][key]sidechaincompress=threshold=0.02:ratio=6:attack=50:release=600[duck]`);
  filters.push(`[voice][duck]amix=inputs=2:normalize=0,alimiter=limit=0.95[aout]`);
  execFileSync("ffmpeg", ["-v", "error", "-y", "-i", silent, ...inputs,
    "-stream_loop", "-1", "-i", path.join(__dirname, "bgm.mp3"),
    "-filter_complex", filters.join(";"), "-map", "0:v", "-map", "[aout]",
    "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out], { stdio: "inherit" });
  fs.unlinkSync(silent);
  console.log("完成：" + out);
})();
