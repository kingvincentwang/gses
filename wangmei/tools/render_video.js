// 把 index.html 的動畫逐格擷取並與配樂合成 MP4。
// 用法：先在 wangmei/ 目錄啟動 `python3 -m http.server 8765`，再執行
//   node render_video.js <輸出.mp4>
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const path = require('path');

(async () => {
  const out = process.argv[2] || 'wangmei.mp4';
  const audio = path.join(__dirname, '..', 'assets', 'soundtrack.mp3');
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
  await page.goto('http://127.0.0.1:8765/index.html?capture=1');
  await page.evaluate(() => window.__ready);
  const { total, fps } = await page.evaluate(() => window.TIMELINE);
  const ff = spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'image2pipe', '-framerate', String(fps), '-i', '-', '-i', audio,
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '23', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k',
    '-shortest', '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
  const n = Math.floor(total * fps);
  for (let i = 0; i < n; i++) {
    const d = await page.evaluate(t => { window.__render(t); return document.getElementById('cv').toDataURL('image/jpeg', .92); }, i / fps);
    if (!ff.stdin.write(Buffer.from(d.split(',')[1], 'base64'))) await new Promise(r => ff.stdin.once('drain', r));
    if (i % 300 === 0) console.log(`${i}/${n}`);
  }
  ff.stdin.end();
  await new Promise(r => ff.on('close', r));
  await browser.close();
  console.log('done', out);
})();
