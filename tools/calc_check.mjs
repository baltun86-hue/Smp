// Прогон калькулятора доз справочника в headless Chromium (вызывается из tools/validate.py).
// stdin: JSON [{n, w, am}], argv[2]: путь к index.html.
// stdout: {texts: [текст doseBox], pageErrors: [...], requests: [внешние запросы]}.
// Код 3 — Playwright не найден.
import { createRequire } from 'module';
import { execSync } from 'child_process';
import { pathToFileURL } from 'url';

const require = createRequire(import.meta.url);
let pw;
try { pw = require('playwright'); } catch {
  try { pw = require(execSync('npm root -g').toString().trim() + '/playwright'); } catch { process.exit(3); }
}

let input = '';
for await (const ch of process.stdin) input += ch;
const cases = JSON.parse(input);

const browser = await pw.chromium.launch();
const page = await browser.newPage({ viewport: { width: 360, height: 800 } });
const pageErrors = [], requests = [];
page.on('pageerror', e => pageErrors.push(e.message));
page.on('request', r => { const u = r.url(); if (!/^(file|data|blob|about):/.test(u)) requests.push(u); });
await page.goto(pathToFileURL(process.argv[2]).href);

// Те же действия, что у пользователя: открыть карточку, ввести вес и возраст (в месяцах), пересчитать
const texts = await page.evaluate(cases => cases.map(({ n, w, am }) => {
  openDrug(n);
  const sw = document.getElementById('sw'), sag = document.getElementById('sag'), sau = document.getElementById('sau');
  if (sw) sw.value = w;
  if (sag) sag.value = am;
  if (sau) sau.value = 'm';
  refreshDose(n);
  const box = document.getElementById('doseBox');
  return box ? box.innerText : '';
}), cases);

await browser.close();
process.stdout.write(JSON.stringify({ texts, pageErrors, requests }));
