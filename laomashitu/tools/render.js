const { chromium } = require('playwright'); const fs = require('fs');
const S = process.argv[2];
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1280, height: 720 } });
  p.on('pageerror', e => console.log('ERR', e.message));
  await p.goto('http://localhost:8765/laomashitu/index.html');
  const voice = JSON.parse(fs.readFileSync(S + '/vo/voice.json'));
  await p.evaluate(v => RENDER.init(v), voice);
  let n = 0;
  while (true) {
    const urls = await p.evaluate(() => { const a = []; for (let i = 0; i < 10; i++) { const u = RENDER.step(); if (!u) break; a.push(u); } return a; });
    for (const u of urls) fs.writeFileSync(`${S}/frames/${String(n++).padStart(5, '0')}.jpg`, Buffer.from(u.split(',')[1], 'base64'));
    if (urls.length < 10) break;
  }
  const log = await p.evaluate(() => RENDER.log);
  fs.writeFileSync(S + '/log.json', JSON.stringify(log));
  const wav = await p.evaluate(() => RENDER.audio());
  fs.writeFileSync(S + '/music.wav', Buffer.from(wav, 'base64'));
  console.log('frames', n, JSON.stringify(log));
  await b.close();
})();
