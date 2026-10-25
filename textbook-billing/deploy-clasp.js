#!/usr/bin/env node
/**
 * 用本機已登入的 clasp，把 textbook-billing/ 的新版 Code.gs、index.html
 * 上傳到「練習版-教科書對帳單含族群弱勢和無力繳交含學校用書」綁定的 Apps Script 專案。
 *
 * 用法（在自己電腦上，需已安裝 Node.js 與 git，並已執行過 clasp login）：
 *   node deploy-clasp.js
 *
 * 每個會刪除檔案或推送的步驟都會先詢問確認。不會讀取 .clasprc.json 的內容。
 */
'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const readline = require('readline');
const { spawnSync } = require('child_process');

const SCRIPT_ID = '11AtBOZuHEyIj6Jyvj3QXcOrhjjDlLgxdQiuyylTL22aCUTGh30DjiQ0o';
const REPO_URL = 'https://github.com/kingvincentwang/gses.git';
const BRANCH = 'claude/gifted-hamilton-2ci1b3';
const WORK_DIR = process.env.WORK_DIR || path.join(os.homedir(), 'textbook-billing-gas');
const CLASP = (process.env.CLASP_CMD || 'npx @google/clasp').split(' ');
const OLD_SYSTEM_FUNCS = ['doGet', 'getWebAppData', 'onOpen', 'generateGradeExpenseReport'];

const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
const lines = [];
const waiters = [];
rl.on('line', (l) => (waiters.length ? waiters.shift()(l) : lines.push(l)));
rl.on('close', () => waiters.splice(0).forEach((w) => w('')));
const ask = (q) => {
  process.stdout.write(q);
  return new Promise((res) => (lines.length ? res(lines.shift()) : waiters.push(res))).then((a) => a.trim());
};
const yes = async (q) => /^y(es)?$/i.test(await ask(q + ' (y/N) '));

function run(cmd, args, opts = {}) {
  const r = spawnSync(cmd, args, { encoding: 'utf8', shell: process.platform === 'win32', ...opts });
  return { code: r.status, out: (r.stdout || '') + (r.stderr || '') };
}
const clasp = (args, opts) => run(CLASP[0], CLASP.slice(1).concat(args), opts);
const claspLive = (args) => clasp(args, { stdio: 'inherit', cwd: WORK_DIR }).code;

function fail(msg) {
  console.error('\n✖ ' + msg);
  rl.close();
  process.exit(1);
}

function listFiles(dir, skip = []) {
  const result = [];
  (function walk(d) {
    for (const name of fs.readdirSync(d)) {
      const full = path.join(d, name);
      const rel = path.relative(dir, full).split(path.sep).join('/');
      if (skip.some((s) => rel === s || rel.startsWith(s + '/'))) continue;
      if (fs.statSync(full).isDirectory()) walk(full);
      else result.push(rel);
    }
  })(dir);
  return result.sort();
}

async function main() {
  // 1. clasp 版本與登入狀態
  console.log('== 步驟 1：檢查 clasp ==');
  const ver = clasp(['--version']);
  if (ver.code !== 0) fail('無法執行 clasp：\n' + ver.out);
  console.log('clasp 版本：' + ver.out.trim().split('\n').pop());
  // 只檢查檔案是否存在，不讀取內容
  if (!fs.existsSync(path.join(os.homedir(), '.clasprc.json'))) {
    console.log('⚠ 家目錄找不到 .clasprc.json，clasp 可能尚未登入（若你用自訂位置登入可忽略）。');
    if (!(await yes('仍要繼續嗎？'))) fail('請先執行 npx @google/clasp login 再重試。');
  } else {
    console.log('已找到 clasp 登入憑證檔。');
  }

  // 2. clone
  console.log('\n== 步驟 2：clone 雲端專案到 ' + WORK_DIR + ' ==');
  if (fs.existsSync(WORK_DIR) && fs.readdirSync(WORK_DIR).length > 0) {
    fail(WORK_DIR + ' 已存在且不是空資料夾，請改名或移走後重試（或設定環境變數 WORK_DIR 指定其他資料夾）。');
  }
  fs.mkdirSync(WORK_DIR, { recursive: true });
  const cl = clasp(['clone', SCRIPT_ID], { cwd: WORK_DIR });
  console.log(cl.out.trim());
  if (cl.code !== 0 || !fs.existsSync(path.join(WORK_DIR, '.clasp.json'))) {
    if (/Apps Script API|usersettings/i.test(cl.out)) {
      fail('Apps Script API 尚未啟用。請到 https://script.google.com/home/usersettings 開啟「Google Apps Script API」，等一兩分鐘後刪除 ' + WORK_DIR + ' 再重新執行本腳本。');
    }
    fail('clasp clone 失敗，請看上方訊息。');
  }

  // 3. 備份 + .claspignore + 列出雲端檔案
  console.log('\n== 步驟 3：備份原始檔案 ==');
  const original = listFiles(WORK_DIR, ['.clasp.json']);
  const backupDir = path.join(WORK_DIR, 'backup');
  fs.mkdirSync(backupDir);
  for (const f of original) {
    fs.mkdirSync(path.dirname(path.join(backupDir, f)), { recursive: true });
    fs.copyFileSync(path.join(WORK_DIR, f), path.join(backupDir, f));
  }
  fs.writeFileSync(path.join(WORK_DIR, '.claspignore'),
    ['backup/**', '**/node_modules/**', '.git/**', '_new/**', ''].join('\n'));
  console.log('已備份到 ' + backupDir + '，並建立 .claspignore 排除 backup/。');
  console.log('雲端專案目前的檔案：');
  original.forEach((f) => console.log('  - ' + f));

  // 4. 取得新版檔案
  console.log('\n== 步驟 4：從 GitHub 取得新版檔案 ==');
  const newDir = path.join(WORK_DIR, '_new');
  const g = run('git', ['clone', '--depth', '1', '-b', BRANCH, REPO_URL, newDir]);
  if (g.code !== 0) fail('git clone 失敗：\n' + g.out);
  const newCode = fs.readFileSync(path.join(newDir, 'textbook-billing', 'Code.gs'), 'utf8');
  const newHtml = fs.readFileSync(path.join(newDir, 'textbook-billing', 'index.html'), 'utf8');
  fs.rmSync(newDir, { recursive: true, force: true });
  console.log('已取得 Code.gs（' + newCode.split('\n').length + ' 行）與 index.html（' + newHtml.split('\n').length + ' 行）。');

  // 5. 刪除舊的伺服器端檔案，寫入新版
  console.log('\n== 步驟 5：替換檔案 ==');
  const serverFiles = original.filter((f) => /\.(gs|js)$/i.test(f));
  const htmlFiles = original.filter((f) => /\.html$/i.test(f));
  const toDelete = [];
  for (const f of serverFiles) {
    const src = fs.readFileSync(path.join(WORK_DIR, f), 'utf8');
    const hits = OLD_SYSTEM_FUNCS.filter((fn) => new RegExp('function\\s+' + fn + '\\s*\\(').test(src));
    if (hits.length) {
      console.log('  ' + f + '：含 ' + hits.join(', ') + ' → 屬於本系統，將被新版 Code 取代');
      toDelete.push(f);
    } else if (await yes('  ' + f + '：看不出是本系統的檔案。要刪除它嗎？（選 N 保留，但若有同名函式會衝突）')) {
      toDelete.push(f);
    }
  }
  for (const f of htmlFiles) {
    if (f.toLowerCase() === 'index.html') continue;
    if (await yes('  ' + f + '：其他 HTML 檔，與本系統無關嗎？要刪除它嗎？（選 N 保留）')) toDelete.push(f);
  }
  // 新版伺服器檔沿用 clasp clone 的副檔名慣例（.js），推送後在雲端顯示為 Code.gs
  const codeTarget = 'Code.js';
  for (const f of toDelete) if (f !== codeTarget) fs.unlinkSync(path.join(WORK_DIR, f));
  fs.writeFileSync(path.join(WORK_DIR, codeTarget), newCode);
  fs.writeFileSync(path.join(WORK_DIR, 'index.html'), newHtml);
  if (!fs.existsSync(path.join(WORK_DIR, 'appsscript.json'))) fail('找不到 appsscript.json，停止推送。');

  // 6. 確認後推送
  console.log('\n== 步驟 6：確認推送清單 ==');
  const pushList = listFiles(WORK_DIR, ['.clasp.json', '.claspignore', 'backup', 'node_modules', '.git']);
  pushList.forEach((f) => console.log('  ✓ ' + f));
  const removed = toDelete.filter((f) => f !== codeTarget);
  if (removed.length) console.log('雲端將被移除的檔案：' + removed.join(', '));
  console.log('（clasp push 會讓雲端專案只剩上面這些檔案）');
  if (!(await yes('確定要執行 clasp push 嗎？'))) {
    console.log('已取消。檔案保留在 ' + WORK_DIR + '，確認後可在該資料夾手動執行 npx @google/clasp push。');
    rl.close();
    return;
  }
  rl.close();
  if (claspLive(['push']) !== 0) fail('clasp push 失敗，請看上方訊息。原始檔案在 ' + backupDir + '。');

  // 7. 提醒
  console.log('\n✔ 推送完成！接下來：');
  console.log('  1. 回到試算表重新整理頁面。');
  console.log('  2. 執行「📋 教科書工具 → ★ 全部重新生成」（第一次會要求授權）。');
  console.log('  3. 若有使用網頁版：Apps Script 編輯器「部署 → 管理部署作業」→ 編輯 → 版本選「新版本」→ 部署，網頁才會更新。');
  console.log('  若要還原：把 ' + backupDir + ' 裡的檔案複製回 ' + WORK_DIR + '，刪掉新的 Code.js 後再 clasp push。');
}

main().catch((e) => fail(e.stack || String(e)));
