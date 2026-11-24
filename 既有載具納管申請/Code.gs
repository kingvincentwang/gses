/**
 * 既有載具納管申請系統
 * Google Sheets + Google Apps Script + HTML
 */
const CONFIG = {
  SPREADSHEET_ID: '1FcLlW7bKjF-uHWuJhtuvMGsZcYkWXDs0sHCiRrAxhQM',
  SHEET_NAME: '申請資料',
  HEADERS: ['申請編號', '申請時間', '申請學校', '聯絡人', '聯絡電話/Email',
            '納管載具', 'iPad 世代', '數量', '載具序號', '備註', '處理狀態'],
  ADMIN_PASSWORD: 'admin1234',   // ← 請自行修改管理密碼
  CHAT_WEBHOOK: ''               // ← 若要 Google Chat 通知，貼上 Webhook URL
};

function doGet(e) {
  const page = (e && e.parameter && e.parameter.page) || 'index';
  const file = page === 'admin' ? 'admin' : 'index';
  return HtmlService.createTemplateFromFile(file).evaluate()
    .setTitle(page === 'admin' ? '既有載具納管申請｜管理後台' : '既有載具納管申請')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

/** 給 R-Page 等外部網頁以 fetch POST 呼叫（Content-Type: text/plain） */
function doPost(e) {
  try {
    const req = JSON.parse(e.postData.contents);
    if (req.action === 'submit') return json_(submitApplication(req.data));
    if (req.action === 'list') return json_(getAllData(req.password));
    return json_({ ok: false, msg: '未知的 action' });
  } catch (err) {
    return json_({ ok: false, msg: String(err) });
  }
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function getSheet_() {
  const ss = SpreadsheetApp.openById(CONFIG.SPREADSHEET_ID);
  let sh = ss.getSheetByName(CONFIG.SHEET_NAME);
  if (!sh) {
    sh = ss.insertSheet(CONFIG.SHEET_NAME);
    sh.getRange(1, 1, 1, CONFIG.HEADERS.length).setValues([CONFIG.HEADERS])
      .setFontWeight('bold').setBackground('#1a5aa6').setFontColor('#ffffff');
    sh.setFrozenRows(1);
  }
  return sh;
}

function clean_(v) {
  return String(v == null ? '' : v).trim().slice(0, 5000);
}

/**
 * 送出申請
 * data = { school, contact, phone, note, items:[{device, generation, qty, serials:[...]}] }
 */
function submitApplication(data) {
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const school = clean_(data.school);
    if (!school) return { ok: false, msg: '請填寫申請學校' };
    const items = Array.isArray(data.items) ? data.items : [];
    if (!items.length) return { ok: false, msg: '請至少新增一項納管載具' };

    const rows = [];
    const now = new Date();
    const appId = 'A' + Utilities.formatDate(now, 'Asia/Taipei', 'yyyyMMddHHmmss') +
                  Math.floor(Math.random() * 90 + 10);

    for (let i = 0; i < items.length; i++) {
      const it = items[i];
      const device = clean_(it.device);
      if (device !== 'iPad' && device !== 'Chromebook')
        return { ok: false, msg: '第 ' + (i + 1) + ' 項：納管載具需為 iPad 或 Chromebook' };
      const gen = device === 'iPad' ? clean_(it.generation) : '';
      if (device === 'iPad' && !gen)
        return { ok: false, msg: '第 ' + (i + 1) + ' 項：請填寫 iPad 為第幾代' };
      const qty = parseInt(it.qty, 10);
      if (!(qty > 0)) return { ok: false, msg: '第 ' + (i + 1) + ' 項：數量需為正整數' };
      const serials = (Array.isArray(it.serials) ? it.serials : [])
        .map(clean_).filter(String);
      if (serials.length !== qty)
        return { ok: false, msg: '第 ' + (i + 1) + ' 項：序號筆數(' + serials.length + ')與數量(' + qty + ')不符' };
      const dup = serials.filter((s, k) => serials.indexOf(s) !== k);
      if (dup.length) return { ok: false, msg: '第 ' + (i + 1) + ' 項：序號重複：' + dup.join(', ') };

      rows.push([
        appId + '-' + (i + 1), now, school, clean_(data.contact), clean_(data.phone),
        device, gen, qty, serials.join('\n'), clean_(data.note), '待處理'
      ]);
    }

    const sh = getSheet_();
    // 以文字格式寫入序號，避免被轉為數字或日期
    const start = sh.getLastRow() + 1;
    sh.getRange(start, 1, rows.length, CONFIG.HEADERS.length).setNumberFormat('@');
    sh.getRange(start, 2, rows.length, 1).setNumberFormat('yyyy/MM/dd HH:mm:ss');
    sh.getRange(start, 8, rows.length, 1).setNumberFormat('0');
    sh.getRange(start, 1, rows.length, CONFIG.HEADERS.length).setValues(rows);

    notifyChat_(school, rows);
    const total = rows.reduce((s, r) => s + r[7], 0);
    return { ok: true, appId: appId, count: rows.length, total: total };
  } catch (err) {
    return { ok: false, msg: '系統錯誤：' + err };
  } finally {
    lock.releaseLock();
  }
}

function notifyChat_(school, rows) {
  if (!CONFIG.CHAT_WEBHOOK) return;
  try {
    const lines = rows.map(r => '• ' + r[5] + (r[6] ? '（第 ' + r[6] + ' 代）' : '') + ' × ' + r[7]);
    UrlFetchApp.fetch(CONFIG.CHAT_WEBHOOK, {
      method: 'post',
      contentType: 'application/json; charset=UTF-8',
      payload: JSON.stringify({ text: '📱 既有載具納管申請\n學校：' + school + '\n' + lines.join('\n') }),
      muteHttpExceptions: true
    });
  } catch (e) { console.warn(e); }
}

/** 管理後台：取得所有資料 */
function getAllData(password) {
  if (password !== CONFIG.ADMIN_PASSWORD) return { ok: false, msg: '密碼錯誤' };
  const sh = getSheet_();
  const values = sh.getDataRange().getDisplayValues();
  return { ok: true, headers: values[0], rows: values.slice(1).reverse() };
}

/** 管理後台：更新處理狀態 */
function updateStatus(password, appId, status) {
  if (password !== CONFIG.ADMIN_PASSWORD) return { ok: false, msg: '密碼錯誤' };
  const sh = getSheet_();
  const ids = sh.getRange(2, 1, Math.max(sh.getLastRow() - 1, 1), 1).getDisplayValues();
  for (let i = 0; i < ids.length; i++) {
    if (ids[i][0] === appId) {
      sh.getRange(i + 2, 11).setValue(clean_(status));
      return { ok: true };
    }
  }
  return { ok: false, msg: '找不到申請編號' };
}
