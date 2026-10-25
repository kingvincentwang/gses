/**
 * 教科書對帳單 - 統計報表產生與網頁查詢
 *
 * 輸入工作表：各年級人數、選用版本、各版本價格
 * 產生工作表：年級費用統計、各版本統計（康軒／翰林／南一／何嘉仁）、學校用書統計
 *
 * 弱勢補助（原住民／身障學生／身障子女）每位學生只能擇一身分：
 * 「各年級人數」請依學校規定的優先順序，把每位學生只填在其中一欄。
 */

const SHEET_COUNTS = '各年級人數';
const SHEET_VERSIONS = '選用版本';
const SHEET_PRICES = '各版本價格';
const SHEET_GRADE_REPORT = '年級費用統計';
const SHEET_SCHOOL_REPORT = '學校用書統計';

const PUBLISHERS = ['康軒', '翰林', '南一', '何嘉仁'];
const GRADE_NAMES = ['一年級', '二年級', '三年級', '四年級', '五年級', '六年級'];
const BOOK_TYPES = ['課本', '習作'];
const PROP_GENERATED_AT = 'generatedAt';

// ==================== 網頁應用程式 ====================

function doGet() {
  return HtmlService.createTemplateFromFile('index')
    .evaluate()
    .setTitle('教科書費用統計查詢系統')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

/**
 * 回傳所有已產生的統計表與產生時間，供網頁顯示
 */
function getWebAppData() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const names = [SHEET_GRADE_REPORT, SHEET_SCHOOL_REPORT].concat(PUBLISHERS.map(p => p + '統計'));
  const generatedAt = readGeneratedAt();
  const sheets = [];

  names.forEach(name => {
    const sheet = ss.getSheetByName(name);
    if (!sheet) return;
    sheets.push({
      name: name,
      values: sheet.getDataRange().getValues(),
      generatedAt: generatedAt[name] || ''
    });
  });

  return { sheets: sheets };
}

// ==================== 選單 ====================

function onOpen() {
  SpreadsheetApp.getUi().createMenu('📋 教科書工具')
    .addItem('★ 全部重新生成（建議）', 'generateAllReports')
    .addSeparator()
    .addItem('1. 生成年級費用總表', 'generateGradeExpenseReport')
    .addItem('2. 生成各版本分類報表', 'generatePublisherReports')
    .addItem('3. 生成學校用書專屬報表', 'generateSchoolBookReport')
    .addToUi();
}

function generateAllReports() {
  const ctx = loadInputs();
  writeGradeExpenseReport(ctx);
  writePublisherReports(ctx);
  writeSchoolBookReport(ctx);
  finish(ctx, '全部報表已重新生成！');
}

function generateGradeExpenseReport() {
  const ctx = loadInputs();
  writeGradeExpenseReport(ctx);
  finish(ctx, '年級費用總表已生成！');
}

function generatePublisherReports() {
  const ctx = loadInputs();
  writePublisherReports(ctx);
  finish(ctx, '各版本分類報表已生成！');
}

function generateSchoolBookReport() {
  const ctx = loadInputs();
  writeSchoolBookReport(ctx);
  finish(ctx, '學校用書統計報表已生成！');
}

// ==================== 讀取與檢查輸入資料 ====================

function loadInputs() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const read = name => {
    const sheet = ss.getSheetByName(name);
    if (!sheet) throw new Error('找不到工作表「' + name + '」，請檢查名稱是否正確。');
    return sheet.getDataRange().getValues();
  };
  const ctx = parseInputs(read(SHEET_COUNTS), read(SHEET_VERSIONS), read(SHEET_PRICES));
  ctx.ss = ss;
  ctx.written = [];
  return ctx;
}

/**
 * 把三張輸入表整理成：各年級人數、選用書目清單（含單價）、警告訊息
 */
function parseInputs(countsData, versionsData, pricesData) {
  const warnings = [];

  // --- 各版本價格 ---
  const pHeader = pricesData[0].map(clean);
  const pCol = {
    subject: findCol(pHeader, ['學習領域(科)', '科目'], 1),
    grade: findCol(pHeader, ['適用年級', '年級'], 2),
    type: findCol(pHeader, ['類別'], 4)
  };
  const pubCols = {};
  PUBLISHERS.forEach(pub => {
    const idx = pHeader.indexOf(pub);
    if (idx >= 0) pubCols[pub] = idx;
  });

  const priceMap = {};
  const anyPriceMap = {}; // 任一版本有此冊，用來判斷是否漏填價格
  for (let i = 1; i < pricesData.length; i++) {
    const row = pricesData[i];
    const subject = clean(row[pCol.subject]);
    const grade = parseGrade(row[pCol.grade]);
    const type = clean(row[pCol.type]);
    if (!subject || !grade || BOOK_TYPES.indexOf(type) < 0) continue;

    Object.keys(pubCols).forEach(pub => {
      const price = toNumber(row[pubCols[pub]]);
      if (price > 0) {
        priceMap[priceKey(grade, subject, type, pub)] = price;
        anyPriceMap[priceKey(grade, subject, type, '')] = true;
      }
    });
  }

  // --- 各年級人數 ---
  const cHeader = countsData[0].map(clean);
  const cCol = {
    total: findCol(cHeader, ['人數', '總人數'], 2),
    indigen: findCol(cHeader, ['原住民'], 4),
    disabledStu: findCol(cHeader, ['身心障礙學生', '身障學生'], 5),
    disabledChild: findCol(cHeader, ['身心障礙子女', '身障子女'], 6),
    financialAid: findCol(cHeader, ['無力繳交'], 7),
    schoolQty: findCol(cHeader, ['學校用書申請', '學校用書'], 9)
  };

  const counts = {};
  GRADE_NAMES.forEach(gradeName => {
    const row = countsData.find((r, i) => i > 0 && clean(r[0]) === gradeName);
    if (!row) {
      warnings.push(gradeName + '：「' + SHEET_COUNTS + '」找不到這個年級，人數以 0 計算。');
    }
    const c = {};
    Object.keys(cCol).forEach(k => { c[k] = row ? toNumber(row[cCol[k]]) : 0; });
    c.disadvantaged = c.indigen + c.disabledStu + c.disabledChild;

    if (c.disadvantaged > c.total) {
      warnings.push(gradeName + '：弱勢人數合計 ' + c.disadvantaged + ' 人，超過總人數 ' + c.total +
        ' 人。弱勢身分只能擇一，請檢查是否有學生重複填在多個欄位。');
    } else if (c.disadvantaged + c.financialAid > c.total) {
      warnings.push(gradeName + '：弱勢人數 ' + c.disadvantaged + ' 人＋無力繳交 ' + c.financialAid +
        ' 人，超過總人數 ' + c.total + ' 人，請檢查是否重複填寫。');
    }
    counts[gradeName] = c;
  });

  // --- 選用版本 → 書目清單 ---
  const vHeader = versionsData[0].map(clean);
  const gradeCols = GRADE_NAMES.map((g, i) => {
    const idx = vHeader.indexOf(g);
    return idx >= 0 ? idx : i + 1;
  });

  const items = [];
  for (let i = 1; i < versionsData.length; i++) {
    const subject = clean(versionsData[i][0]);
    if (!subject) continue;

    GRADE_NAMES.forEach((gradeName, gIdx) => {
      const pub = clean(versionsData[i][gradeCols[gIdx]]);
      if (!pub) return;
      const label = gradeName + subject;

      if (PUBLISHERS.indexOf(pub) < 0) {
        warnings.push(label + '：選用版本「' + pub + '」不是 ' + PUBLISHERS.join('、') + ' 其中之一，未計入。');
        return;
      }

      let found = 0;
      BOOK_TYPES.forEach(type => {
        const price = priceMap[priceKey(gIdx + 1, subject, type, pub)];
        if (price) {
          items.push({ gradeIdx: gIdx, gradeName: gradeName, subject: subject, type: type, pub: pub, price: price });
          found++;
        } else if (anyPriceMap[priceKey(gIdx + 1, subject, type, '')]) {
          warnings.push(label + type + '：其他版本有價格，但 ' + pub + ' 沒有（或為「-」），此冊未計入。');
        }
      });
      if (!found && !BOOK_TYPES.some(t => anyPriceMap[priceKey(gIdx + 1, subject, t, '')])) {
        warnings.push(label + '：「' + SHEET_PRICES + '」找不到這個科目的價格，未計入（請檢查科目名稱是否一致）。');
      }
    });
  }
  // 依年級排序（同年級維持選用版本表的科目順序）
  items.sort((a, b) => a.gradeIdx - b.gradeIdx);

  return { counts: counts, items: items, warnings: warnings };
}

// ==================== 報表內容 ====================

const GRADE_HEADERS = [
  '年級', '總人數', '單生課本費', '單生習作費', '全年級書款', '單生註冊費',
  '原住民人數', '原住民費用', '身障學生人數', '身障學生費用', '身障子女人數', '身障子女費用',
  '弱勢人數(擇一)', '弱勢補助費用', '無力繳交人數', '無力繳交費用',
  '學校用書(申請套數)', '學校用書費用', '總計(含學校用書)'
];
const GRADE_PER_STUDENT_COLS = [2, 3, 5]; // 每人單價，合計列不加總

function buildGradeExpenseRows(ctx) {
  const rows = [GRADE_HEADERS];

  GRADE_NAMES.forEach((gradeName, gIdx) => {
    const c = ctx.counts[gradeName];
    let textbook = 0, workbook = 0;
    ctx.items.forEach(item => {
      if (item.gradeIdx !== gIdx) return;
      if (item.type === '課本') textbook += item.price;
      else workbook += item.price;
    });
    const fee = textbook + workbook;

    rows.push([
      gradeName, c.total, textbook, workbook, c.total * fee, fee,
      c.indigen, c.indigen * fee,
      c.disabledStu, c.disabledStu * fee,
      c.disabledChild, c.disabledChild * fee,
      c.disadvantaged, c.disadvantaged * fee,
      c.financialAid, c.financialAid * fee,
      c.schoolQty, c.schoolQty * fee,
      (c.total + c.schoolQty) * fee
    ]);
  });

  rows.push(sumFooter(rows, '合計', GRADE_PER_STUDENT_COLS));
  return rows;
}

const PUB_HEADERS = [
  '年級', '科目', '類別', '單價', '學生數', '學生用書小計', '學校用書(申請數)', '學校用書小計',
  '原住民人數', '原住民金額', '身障學生人數', '身障學生金額', '身障子女人數', '身障子女金額',
  '弱勢人數(擇一)', '弱勢補助金額', '無力繳交人數', '無力繳交金額'
];
const PUB_MONEY_COLS = [5, 7, 9, 11, 13, 15, 17];

function buildPublisherRows(ctx, pub) {
  const rows = [PUB_HEADERS];
  ctx.items.filter(item => item.pub === pub).forEach(item => {
    const c = ctx.counts[item.gradeName];
    const p = item.price;
    rows.push([
      item.gradeName, item.subject, item.type, p, c.total, c.total * p,
      c.schoolQty, c.schoolQty * p,
      c.indigen, c.indigen * p,
      c.disabledStu, c.disabledStu * p,
      c.disabledChild, c.disabledChild * p,
      c.disadvantaged, c.disadvantaged * p,
      c.financialAid, c.financialAid * p
    ]);
  });

  if (rows.length === 1) return rows; // 此版本沒有被選用

  // 合計列只加總金額欄
  const skip = PUB_HEADERS.map((h, i) => i).filter(i => PUB_MONEY_COLS.indexOf(i) < 0);
  rows.push(sumFooter(rows, '合計', skip));
  return rows;
}

function buildSchoolBookRows(ctx) {
  const rows = [];
  let grandTotal = 0;
  const usedPubs = PUBLISHERS.filter(pub => ctx.items.some(item => item.pub === pub));

  usedPubs.forEach(pub => {
    rows.push([pub + ' 版本 - 學校用書明細', '', '', '', '', '']);
    rows.push(['年級', '科目', '類別', '單價', '申請數量', '金額小計']);

    let subTotal = 0;
    ctx.items.filter(item => item.pub === pub).forEach(item => {
      const qty = ctx.counts[item.gradeName].schoolQty;
      if (qty <= 0) return;
      rows.push([item.gradeName, item.subject, item.type, item.price, qty, qty * item.price]);
      subTotal += qty * item.price;
    });
    if (rows[rows.length - 1][0] === '年級') {
      rows.push(['-', '各年級皆未申請學校用書', '-', '-', '-', 0]);
    }

    rows.push([pub + ' 合計', '', '', '', '', subTotal]);
    rows.push(['', '', '', '', '', '']);
    grandTotal += subTotal;
  });

  rows.push(['全校學校用書總計', '', '', '', '', grandTotal]);
  return rows;
}

// ==================== 寫入工作表 ====================

function writeGradeExpenseReport(ctx) {
  const rows = buildGradeExpenseRows(ctx);
  const sheet = prepareSheet(ctx.ss, SHEET_GRADE_REPORT);
  const width = rows[0].length;

  sheet.getRange(1, 1, rows.length, width).setValues(rows);
  sheet.getRange(2, 2, rows.length - 1, width - 1).setNumberFormat('#,##0');
  sheet.getRange(1, 1, 1, width).setBackground('#DDEBF7').setFontWeight('bold');
  [8, 10, 12, 14, 16].forEach(c => sheet.getRange(2, c, rows.length - 1, 1).setBackground('#F2F2F2'));
  sheet.getRange(1, 18, rows.length, 1).setBackground('#FCE4D6');
  sheet.getRange(1, 19, rows.length, 1).setBackground('#E2EFDA').setFontWeight('bold');
  sheet.getRange(rows.length, 1, 1, width).setBackground('#FFF2CC').setFontWeight('bold');
  sheet.setFrozenRows(1);
  sheet.autoResizeColumns(1, width);

  ctx.written.push(SHEET_GRADE_REPORT);
}

function writePublisherReports(ctx) {
  PUBLISHERS.forEach(pub => {
    const name = pub + '統計';
    const rows = buildPublisherRows(ctx, pub);
    const width = PUB_HEADERS.length;

    // 沒被選用、也從未產生過的版本（例如何嘉仁）就不建立工作表
    if (rows.length === 1 && !ctx.ss.getSheetByName(name)) return;

    const sheet = prepareSheet(ctx.ss, name);
    if (rows.length === 1) {
      const note = new Array(width).fill('');
      note[0] = '本學期無選用此版本';
      rows.push(note);
    }
    sheet.getRange(1, 1, rows.length, width).setValues(rows);
    sheet.getRange(1, 1, 1, width).setBackground('#D9EAD3').setFontWeight('bold');

    if (rows[rows.length - 1][0] === '合計') {
      sheet.getRange(2, 4, rows.length - 1, width - 3).setNumberFormat('#,##0');
      PUB_MONEY_COLS.forEach(idx => sheet.getRange(2, idx + 1, rows.length - 2, 1).setBackground('#F2F2F2'));
      sheet.getRange(rows.length, 1, 1, width).setBackground('#FFF2CC').setFontWeight('bold');
    }
    sheet.setFrozenRows(1);
    sheet.autoResizeColumns(1, width);

    ctx.written.push(name);
  });
}

function writeSchoolBookReport(ctx) {
  const rows = buildSchoolBookRows(ctx);
  const sheet = prepareSheet(ctx.ss, SHEET_SCHOOL_REPORT);

  sheet.getRange(1, 1, rows.length, 6).setValues(rows);
  sheet.getRange(1, 4, rows.length, 3).setNumberFormat('#,##0');

  rows.forEach((row, i) => {
    const first = String(row[0]);
    const range = sheet.getRange(i + 1, 1, 1, 6);
    if (first.indexOf('版本 - 學校用書明細') >= 0) {
      range.merge().setBackground('#D9EAD3').setFontWeight('bold');
    } else if (first === '年級') {
      range.setBackground('#F3F4F6').setFontWeight('bold');
    } else if (first === '全校學校用書總計') {
      range.setBackground('#F4CCCC').setFontWeight('bold').setFontSize(12);
    } else if (first.indexOf('合計') >= 0) {
      range.setBackground('#FFF2CC').setFontWeight('bold');
    }
  });
  sheet.autoResizeColumns(1, 6);

  ctx.written.push(SHEET_SCHOOL_REPORT);
}

// ==================== 共用工具 ====================

/**
 * 取得（或新增）報表工作表並完全清空，包含上次留下的合併儲存格
 */
function prepareSheet(ss, name) {
  const sheet = ss.getSheetByName(name) || ss.insertSheet(name);
  sheet.getRange(1, 1, sheet.getMaxRows(), sheet.getMaxColumns()).breakApart();
  sheet.clear();
  sheet.setFrozenRows(0);
  return sheet;
}

/**
 * 產生合計列：第 1 欄放標籤，skipCols 內的欄位留空，其餘加總
 */
function sumFooter(rows, label, skipCols) {
  const footer = new Array(rows[0].length).fill('');
  footer[0] = label;
  for (let col = 1; col < footer.length; col++) {
    if (skipCols.indexOf(col) >= 0) continue;
    let sum = 0;
    for (let r = 1; r < rows.length; r++) sum += Number(rows[r][col]) || 0;
    footer[col] = sum;
  }
  return footer;
}

function finish(ctx, message) {
  const tz = Session.getScriptTimeZone();
  const now = Utilities.formatDate(new Date(), tz, 'yyyy/MM/dd HH:mm');
  const generatedAt = readGeneratedAt();
  ctx.written.forEach(name => { generatedAt[name] = now; });
  PropertiesService.getDocumentProperties().setProperty(PROP_GENERATED_AT, JSON.stringify(generatedAt));

  let text = message;
  if (ctx.warnings.length) {
    text += '\n\n⚠️ 請確認以下問題（相關項目未計入或資料可能有誤）：\n' +
      ctx.warnings.map(w => '• ' + w).join('\n');
  }
  try {
    SpreadsheetApp.getUi().alert(text);
  } catch (e) {
    Logger.log(text); // 從觸發器執行時沒有 UI
  }
}

function readGeneratedAt() {
  const raw = PropertiesService.getDocumentProperties().getProperty(PROP_GENERATED_AT);
  try {
    return raw ? JSON.parse(raw) : {};
  } catch (e) {
    return {};
  }
}

function findCol(header, names, fallback) {
  for (let i = 0; i < names.length; i++) {
    const idx = header.indexOf(names[i]);
    if (idx >= 0) return idx;
  }
  return fallback;
}

function priceKey(grade, subject, type, pub) {
  return grade + '_' + subject + '_' + type + '_' + pub;
}

function parseGrade(value) {
  const text = clean(value);
  const byName = GRADE_NAMES.indexOf(text);
  if (byName >= 0) return byName + 1;
  const n = parseInt(text, 10);
  return n >= 1 && n <= 6 ? n : 0;
}

function toNumber(value) {
  const n = Number(clean(value).replace(/,/g, ''));
  return isFinite(n) && n > 0 ? n : 0;
}

function clean(value) {
  return value === null || value === undefined ? '' : String(value).trim();
}
