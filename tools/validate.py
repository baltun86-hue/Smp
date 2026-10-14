#!/usr/bin/env python3
"""Проверка справочника СМП (www/index.html) — см. CLAUDE.md, «Обязательная проверка».

Только читает файл и печатает отчёт, ничего не меняет.

  python3 tools/validate.py                 # всё, включая калькулятор в Chromium
  python3 tools/validate.py --no-browser    # без браузера (нет Node/Playwright)
  python3 tools/validate.py -v              # подробно: все контрольные расчёты

Код выхода: 0 — ошибок нет (предупреждения допустимы), 1 — есть ошибки.
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from decimal import Decimal, ROUND_HALF_UP

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_HTML = os.path.join(ROOT, 'www', 'index.html')
VERSION_RE = re.compile(r'VERSION\s*=\s*"([^"]+)"')
CONSTS = ['DRUGS', 'STANDARDS', 'SCEN', 'CARD_TEMPLATES', 'ECG2_DATA', 'ICD10_FULL',
          'SCALES', 'ORDERS', 'REFERENCE', 'INFUS_PRESETS']
ADULT_MONTHS = 216  # 18 лет — порог взрослого в приложении


class Report:
    def __init__(self, verbose):
        self.verbose = verbose
        self.errors = 0
        self.warns = 0

    def section(self, title):
        print(f'\n== {title}')

    def ok(self, msg):
        print(f'  ✓ {msg}')

    def info(self, msg):
        print(f'    {msg}')

    def warn(self, msg):
        self.warns += 1
        print(f'  ⚠ {msg}')

    def err(self, msg):
        self.errors += 1
        print(f'  ✗ {msg}')

    def items(self, rows, limit=15):
        """Список деталей: в кратком режиме — первые limit строк."""
        shown = rows if self.verbose else rows[:limit]
        for r in shown:
            print(f'      · {r}')
        if len(rows) > len(shown):
            print(f'      … и ещё {len(rows) - len(shown)} (подробно: -v)')


# ---------- извлечение констант ----------

def literal_end(src, i):
    """Конец JS-литерала, начинающегося с [ или { в позиции i (учёт строк и комментариев)."""
    depth = 0
    n = len(src)
    while i < n:
        c = src[i]
        if c in '"\'`':
            q = c
            i += 1
            while i < n and src[i] != q:
                i += 2 if src[i] == '\\' else 1
        elif c == '/' and src[i + 1] == '/':
            i = src.index('\n', i)
        elif c == '/' and src[i + 1] == '*':
            i = src.index('*/', i) + 1
        elif c in '[{(':
            depth += 1
        elif c in ']})':
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ValueError('литерал не закрыт')


def extract_literal(src, name):
    m = re.search(r'\bconst\s+' + name + r'\s*=\s*', src)
    if not m:
        return None
    start = m.end()
    return src[start:literal_end(src, start)]


def js_eval_literal(text):
    """Разбор не-JSON литерала (ключи без кавычек, одинарные кавычки) через Node в пустом контексте.
    Вызовы функций приложения внутри данных (ecgSvg(…) и т.п.) заменяются заглушками."""
    code = r"""const vm=require('vm');let s='';process.stdin.on('data',d=>s+=d).on('end',()=>{
      const ctx={};
      for(let i=0;i<30;i++){
        try{process.stdout.write(JSON.stringify(vm.runInNewContext('('+s+')',ctx,{timeout:5000})));return;}
        catch(e){const m=/^(\w+) is not defined/.exec(e.message);
          if(!m){console.error(e.message);process.exit(1);} ctx[m[1]]=()=>'';}
      }
      console.error('слишком много неизвестных имён');process.exit(1);})"""
    r = subprocess.run(['node', '-e', code], input=text, capture_output=True, text=True)
    if r.returncode:
        raise ValueError(r.stderr.strip().splitlines()[0] if r.stderr.strip() else 'ошибка node')
    return json.loads(r.stdout)


def load_consts(src, rep):
    rep.section('Константы данных')
    data = {}
    for name in CONSTS:
        try:
            text = extract_literal(src, name)
        except ValueError as e:
            rep.err(f'{name}: {e}')
            continue
        if text is None:
            rep.err(f'{name}: не найдена (const {name}=…)')
            continue
        try:
            data[name] = json.loads(text)
            how = 'JSON'
        except json.JSONDecodeError:
            try:
                data[name] = js_eval_literal(text)
                how = 'JS-литерал'
            except (ValueError, FileNotFoundError) as e:
                rep.err(f'{name}: не разбирается — {e}')
                continue
        v = data[name]
        size = len(v) if isinstance(v, (list, dict)) else '?'
        rep.ok(f'{name}: {how}, {size} записей')
    return data


# ---------- проверки ----------

def check_version(src, rep, today):
    rep.section('VERSION')
    found = VERSION_RE.findall(src)
    if len(found) != 1:
        rep.err(f'ожидалась одна константа VERSION, найдено {len(found)}')
        return
    v = found[0]
    m = re.fullmatch(r'(\d+)\.(\d{2}) \((\d{2})\.(\d{2})\.(\d{4})\)', v)
    if not m:
        rep.err(f'формат «{v}» ≠ «6.87 (09.10.2026)»')
        return
    if re.search(r'VERSION\s+=|VERSION=\s', src):
        rep.warn('VERSION записан с пробелами — по CLAUDE.md без пробелов: VERSION="…"')
    try:
        d = dt.date(int(m[5]), int(m[4]), int(m[3]))
    except ValueError:
        rep.err(f'дата в VERSION некорректна: {v}')
        return
    if d > today:
        rep.warn(f'дата в VERSION ({d:%d.%m.%Y}) позже сегодняшней ({today:%d.%m.%Y})')
    elif d < today:
        rep.info(f'дата в VERSION не сегодняшняя — после правки поднять версию на 0.01 и дату')
    rep.ok(f'VERSION="{v}"')


def check_scripts(src, rep):
    rep.section('Синтаксис <script> (node --check)')
    if not shutil.which('node'):
        rep.warn('node не найден — проверка синтаксиса пропущена')
        return
    scripts = re.findall(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', src, re.S)
    with tempfile.TemporaryDirectory() as td:
        for i, code in enumerate(scripts):
            p = os.path.join(td, f's{i}.js')
            with open(p, 'w', encoding='utf-8') as f:
                f.write(code)
            r = subprocess.run(['node', '--check', p], capture_output=True, text=True)
            if r.returncode:
                rep.err(f'script #{i}: ' + ' '.join(r.stderr.split())[:400])
            else:
                rep.ok(f'script #{i} ({len(code) // 1024} КБ)')


def check_offline(src, rep):
    rep.section('Офлайн: нет внешних ресурсов')
    pats = [
        (r'<(?:script|link|img|iframe|source|audio|video)\b[^>]*\b(?:src|href)\s*=\s*["\'](?:https?:)?//', 'тег с внешним src/href'),
        (r'@import\s+(?:url\()?["\']?(?:https?:)?//', 'CSS @import внешнего файла'),
        (r'url\(\s*["\']?(?:https?:)?//', 'CSS url() на внешний адрес'),
        (r'\bfetch\s*\(\s*["\'`]https?:', 'fetch() на внешний адрес'),
        (r'fonts\.googleapis|fonts\.gstatic|cdnjs|jsdelivr|unpkg\.com', 'CDN / внешние шрифты'),
    ]
    bad = 0
    for pat, what in pats:
        for m in re.finditer(pat, src, re.I):
            line = src.count('\n', 0, m.start()) + 1
            rep.err(f'{what}, строка {line}: {src[m.start():m.start() + 90]!r}')
            bad += 1
    if not bad:
        rep.ok('внешних загрузок не найдено')


def check_drugs(drugs, rep):
    rep.section('DRUGS: обязательные поля и типы')
    probs, no_fa_age, no_conc = [], [], []
    seen = {}
    for i, d in enumerate(drugs):
        n = d.get('n', f'#{i}')
        for k in ('n', 'lat', 'r', 'det', 'g'):
            if not isinstance(d.get(k), str) or not d.get(k).strip():
                probs.append(f'{n}: нет поля {k}')
        ma = d.get('minAge')
        if not isinstance(ma, (int, float)) or isinstance(ma, bool) or ma < 0:
            probs.append(f'{n}: minAge={ma!r} — нужно число месяцев ≥ 0')
        if n in seen:
            probs.append(f'{n}: дубль названия (записи #{seen[n]} и #{i})')
        seen[n] = i
        for k in ('conc', 'amp'):
            if k in d and d[k] is not None and not (isinstance(d[k], (int, float)) and d[k] > 0):
                probs.append(f'{n}: {k}={d[k]!r} — нужно число > 0')
        ds = d.get('dose')
        if ds:
            if not (isinstance(ds.get('lo'), (int, float)) and isinstance(ds.get('hi'), (int, float))):
                probs.append(f'{n}: dose.lo/hi не числа')
            elif ds['lo'] > ds['hi']:
                probs.append(f'{n}: dose.lo {ds["lo"]} > hi {ds["hi"]}')
            if not re.fullmatch(r'(мг|мкг|г|мл|ЕД)/кг(/мин|/ч)?', str(ds.get('unit'))):
                probs.append(f'{n}: dose.unit={ds.get("unit")!r} — неизвестная единица')
            if ds.get('unit') in ('мг/кг', 'мкг/кг', 'ЕД/кг') and not d.get('conc') \
                    and re.search(r'в/в|в/м|п/к', d.get('r', '')):
                no_conc.append(f'{n} ({d.get("r")})')
        fa = d.get('fixedAdult')
        if fa and not isinstance(fa.get('txt'), str):
            probs.append(f'{n}: fixedAdult без txt')
        elif fa and not isinstance(fa.get('minAgeMonths'), (int, float)):
            no_fa_age.append(n)
        mc = d.get('maxCumulative')
        if mc and not all(k in mc for k in ('unit', 'val')):
            probs.append(f'{n}: maxCumulative без unit/val')
        ms = d.get('maxSingle')
        if ms and 'unit' not in ms:
            probs.append(f'{n}: maxSingle без unit')
    if probs:
        rep.err(f'проблем: {len(probs)}')
        rep.items(probs)
    else:
        rep.ok(f'{len(drugs)} препаратов, обязательные поля и типы в порядке')
    if no_conc:
        rep.warn(f'инъекционные с dose, но без conc — калькулятор не переводит в мл: {len(no_conc)}')
        rep.items(no_conc)
    if no_fa_age:
        # renderDoseCalc показывает fixedAdult только при amCalc >= minAgeMonths; больше нигде txt не выводится
        rep.warn(f'fixedAdult без minAgeMonths: {len(no_fa_age)} — «доза по стандарту (взрослым)» '
                 f'нигде не показывается; при наличии dose взрослому считается доза по весу')
        rep.items(no_fa_age)


def check_links(data, rep):
    rep.section('Связность')
    drugs = data.get('DRUGS') or []
    names = {d['n'] for d in drugs if 'n' in d}
    std = data.get('STANDARDS') or {}

    def hint(x):
        # подсказка: какой препарат DRUGS начинается с того же слова
        w = re.split(r'[ ,(]', x)[0].lower()
        c = [n for n in names if n.lower().startswith(w)] if len(w) > 3 else []
        return f' → похоже: {"; ".join(sorted(c)[:2])}' if c else ' → в DRUGS нет'

    # kit: чип в алгоритме открывает openDrug(n) по точному совпадению — иначе нажатие ничего не делает
    miss = {}
    for sp, arr in std.items():
        for a in arr:
            for k in a.get('kit') or []:
                if k not in names:
                    miss.setdefault(k, []).append(f'{sp} / {a.get("t")}')
    if miss:
        rep.warn(f'kit: {len(miss)} названий не совпадают с DRUGS.n — чип в «Препараты из укладки» не открывается')
        rep.items([f'«{k}» ×{len(v)}{hint(k)}' for k, v in sorted(miss.items(), key=lambda x: -len(x[1]))])
    else:
        rep.ok('kit: все названия есть в DRUGS')

    # SCEN: приложение фильтрует DRUGS по n.startsWith(ключ)
    bad = [f'{sc}: «{k}»' for sc, arr in (data.get('SCEN') or {}).items()
           for k in arr if not any(n.startswith(k) for n in names)]
    if bad:
        rep.warn(f'SCEN: {len(bad)} ключей не находят ни одного препарата (n.startsWith)')
        rep.items(bad)
    else:
        rep.ok('SCEN: каждый ключ находит препарат в DRUGS')

    # CARD_TEMPLATES[].std ↔ STANDARDS
    bad = []
    for grp in data.get('CARD_TEMPLATES') or []:
        g, arr = grp[0], grp[1]
        for t in arr:
            s = t.get('std')
            if s and s not in std:
                bad.append(f'{g} / {t.get("t")}: std=«{s}»')
    if bad:
        rep.warn(f'CARD_TEMPLATES: {len(bad)} шаблонов ссылаются на несуществующую специальность — '
                 f'кнопка «Тактика и дозы» падает с ошибкой JS (stdHTML: STANDARDS[std] нет)')
        rep.items(bad)
    else:
        rep.ok('CARD_TEMPLATES: все std есть в STANDARDS')

    check_doses_vs_drugs(std, drugs, rep)


def num(s):
    return float(s.replace(',', '.'))


def in_range(lo, hi, unit, d):
    """Доза из алгоритма [lo, hi] unit попадает в DRUGS.dose (мг/кг ↔ мл/кг — через conc)."""
    du, dlo, dhi = d['dose']['unit'], d['dose']['lo'], d['dose']['hi']
    if unit != du:
        c = d.get('conc')
        if c and unit == 'мг/кг' and du == 'мл/кг':
            lo, hi = lo / c, hi / c
        elif c and unit == 'мл/кг' and du == 'мг/кг':
            lo, hi = lo * c, hi * c
        else:
            return False
    return dlo - 1e-9 <= lo and hi <= dhi + 1e-9


def check_doses_vs_drugs(std, drugs, rep):
    """STANDARDS.doses: детская доза «X–Y мг/кг» против DRUGS.dose того же препарата."""
    by_first = {}
    for d in drugs:
        by_first.setdefault(re.split(r'[ ,(]', d['n'])[0].lower(), []).append(d)
    rows, nomatch, checked = [], set(), 0
    for sp, arr in std.items():
        for a in arr:
            for x in a.get('doses') or []:
                name = x.get('drug') or ''
                ds = [d for d in by_first.get(re.split(r'[ ,(]', name)[0].lower(), []) if d.get('dose')]
                ped = x.get('pediatricDose') or ''
                m = re.search(r'(\d+(?:[.,]\d+)?)(?:\s*[–-]\s*(\d+(?:[.,]\d+)?))?\s*((?:мг|мкг|мл|ЕД|г)/кг(?:/мин|/ч)?)', ped)
                if not m:
                    continue
                if not ds:
                    nomatch.add(name)
                    continue
                checked += 1
                lo, hi, unit = num(m[1]), num(m[2] or m[1]), m[3]
                ok = [d for d in ds if in_range(lo, hi, unit, d)]
                if not ok:
                    ref = '; '.join(f'{d["n"]}: {d["dose"]["lo"]}–{d["dose"]["hi"]} {d["dose"]["unit"]}' for d in ds)
                    rows.append(f'{sp} / {a.get("t")} — {name}: «{ped[:70]}» vs DRUGS {ref}')
    if rows:
        rep.warn(f'STANDARDS.doses: {len(rows)} детских доз мг/кг вне диапазона DRUGS.dose (из {checked} сверенных)')
        rep.items(rows)
    else:
        rep.ok(f'STANDARDS.doses: {checked} детских доз мг/кг совпадают с DRUGS.dose')
    if nomatch:
        rep.info(f'не с чем сверить (в DRUGS нет расчёта по весу): {", ".join(sorted(nomatch)[:8])}'
                 + (' …' if len(nomatch) > 8 else ''))


def check_ecg(ecg, rep):
    rep.section('ECG2_DATA')
    probs, ids = [], set()
    for e in ecg or []:
        i = e.get('id', '?')
        if i in ids:
            probs.append(f'{i}: дубль id')
        ids.add(i)
        for k in ('id', 'cat', 'urgency', 'title'):
            if not e.get(k):
                probs.append(f'{i}: нет {k}')
        for k in ('leadsSte', 'leadsStd'):
            if k not in e:
                probs.append(f'{i}: нет {k}')
        if not e.get('redFlag'):
            probs.append(f'{i}: нет redFlag')
        if str(e.get('cat', '')).lower() in ('stemi', 'omi', 'mi') and not e.get('artery'):
            probs.append(f'{i}: ИМ без artery')
    if probs:
        rep.warn(f'{len(probs)} замечаний по {len(ecg or [])} паттернам')
        rep.items(probs)
    else:
        rep.ok(f'{len(ecg or [])} паттернов, поля на месте')


# ---------- калькулятор: ожидаемые значения (порт fmt() из index.html) ----------

def _fixed(x, k):
    return str(Decimal(x).quantize(Decimal(1).scaleb(-k), rounding=ROUND_HALF_UP))


def fmt(x):
    if x >= 100:
        return _fixed(x, 0)
    if x >= 10:
        s = _fixed(x, 1)
        return s[:-2] if s.endswith('.0') else s
    if x >= 1:
        s = _fixed(x, 2)
        s = s[:-1] if s.endswith('0') else s
        return s[:-1] if s.endswith('.') else s
    if x >= 0.1:
        return _fixed(x, 2)
    if x >= 0.01:
        return _fixed(x, 3)
    return f'{Decimal(x):.2g}' if x else '0'


def max_single(d, am, w):
    m = d.get('maxSingle')
    if not m:
        return None
    if 'tiers' not in m:
        return m['unit'], m['val']
    for t in m['tiers']:
        a_def = t.get('minAgeMonths') is not None or t.get('maxAgeMonths') is not None
        w_def = t.get('maxWeightKg') is not None
        if not a_def and not w_def:
            return m['unit'], t['val']
        am_ok = a_def and am is not None and (t.get('minAgeMonths') is None or am >= t['minAgeMonths']) \
            and (t.get('maxAgeMonths') is None or am < t['maxAgeMonths'])
        w_ok = w_def and w is not None and w < t['maxWeightKg']
        if am_ok or w_ok:
            return m['unit'], t['val']
    return None


def expected(d, w, am):
    """Что должен показать калькулятор: ('ban'|'fixedAdult'|'calc', [строки, которые обязаны быть в тексте], ВРД)."""
    if d.get('minAge') is not None and am < d['minAge']:
        return 'ban', ['Не вводить'], False
    fa = d.get('fixedAdult')
    if fa and isinstance(fa.get('minAgeMonths'), (int, float)) and am >= fa['minAgeMonths']:
        return 'fixedAdult', [' '.join(fa['txt'].split())], False
    ds = d['dose']
    lo, hi = ds['lo'] * w, ds['hi'] * w
    u = ds['unit'].replace('/кг', '')
    need = [f'{fmt(lo)}{"–" + fmt(hi) if hi > lo else ""} {u}']
    conc = d.get('conc')
    if conc and ds['unit'] in ('мг/кг', 'ЕД/кг'):
        m1, m2 = lo / conc, hi / conc
        need.append(f'{fmt(m1)}{"–" + fmt(m2) if m2 > m1 else ""} мл')
    elif conc and ds['unit'] == 'мкг/кг':
        m1, m2 = lo / 1000 / conc, hi / 1000 / conc
        need.append(f'{fmt(m1)}{"–" + fmt(m2) if m2 > m1 else ""} мл')
    ms = max_single(d, am, w)
    exceeded = bool(ms and ms[0] == u and hi > ms[1])
    return 'calc', need, exceeded


def scenarios(d):
    """Контрольные расчёты по CLAUDE.md: взрослый 70 кг, ребёнок 10 кг (1 год), граничный возраст."""
    sc = [('взрослый 70 кг, 35 лет', 70, 420), ('ребёнок 10 кг, 1 год', 10, 12)]
    # граничный возраст: порог запрета и порог «взрослой» фиксированной дозы
    for lim, what in ((d.get('minAge') or 0, 'minAge'),
                      ((d.get('fixedAdult') or {}).get('minAgeMonths') or 0, 'fixedAdult')):
        if 0 < lim <= 1200:
            for am in (lim - 1, lim):
                if am >= 0:
                    w = 70 if am >= ADULT_MONTHS else (10 if am < 24 else round(2 * am / 12 + 8, 1))
                    sc.append((f'граница {what}: {am} мес, {w} кг', w, am))
    return sc


def check_calculator(html_path, drugs, rep):
    rep.section('Калькулятор доз в браузере (контрольные расчёты)')
    calc = [d for d in drugs if d.get('dose')]
    cases = [{'n': d['n'], 'label': lbl, 'w': w, 'am': am}
             for d in calc for lbl, w, am in scenarios(d)]
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'calc_check.mjs')
    if not shutil.which('node'):
        rep.warn('node не найден — пропущено')
        return
    r = subprocess.run(['node', script, html_path], input=json.dumps(cases, ensure_ascii=False),
                       capture_output=True, text=True, timeout=600)
    if r.returncode == 3:
        rep.warn('Playwright не установлен — пропущено (npm i -g playwright или --no-browser)')
        return
    if r.returncode:
        rep.err('сбой браузерной проверки: ' + (r.stderr.strip()[-500:] or r.stdout[-500:]))
        return
    res = json.loads(r.stdout)
    for e in res['pageErrors']:
        rep.err(f'ошибка JS на странице: {e[:200]}')
    for u in res['requests']:
        rep.err(f'сетевой запрос: {u[:150]}')
    by = {d['n']: d for d in calc}
    bad, table = [], []
    for c, text in zip(cases, res['texts']):
        d = by[c['n']]
        flat = ' '.join(text.split())
        low = flat.lower()  # заголовки в интерфейсе ЗАГЛАВНЫМИ (text-transform)
        kind, need, exceeded = expected(d, c['w'], c['am'])
        miss = [s for s in need if s.lower() not in low]
        if exceeded != ('превышена врд' in low):
            miss.append('флаг «превышена ВРД» ' + ('ожидался' if exceeded else 'лишний'))
        line = f'{c["n"]} — {c["label"]}: {flat[:110]}'
        table.append(('✗ ' if miss else '') + line)
        if miss:
            bad.append(f'{line}\n          ожидалось: {"; ".join(need)}; не совпало: {"; ".join(miss)}')
    if bad:
        rep.err(f'{len(bad)} из {len(cases)} расчётов не совпали с ожидаемыми по DRUGS')
        rep.items(bad)
    else:
        rep.ok(f'{len(cases)} расчётов по {len(calc)} препаратам совпали с DRUGS (мг, мл, запрет по возрасту, ВРД)')
    if rep.verbose:
        rep.items(table)
    else:
        sample = [t for t in table if t.split(' — ')[0].lstrip('✗ ') in ('Атропин', 'Амиодарон (кордарон)', 'Адреналин (эпинефрин)')]
        rep.items(sample, limit=12)


def main():
    ap = argparse.ArgumentParser(description='Проверка справочника СМП')
    ap.add_argument('html', nargs='?', default=DEFAULT_HTML)
    ap.add_argument('--no-browser', action='store_true', help='без проверки калькулятора в Chromium')
    ap.add_argument('-v', '--verbose', action='store_true')
    ap.add_argument('--today', help='дата ДД.ММ.ГГГГ (по умолчанию — сегодня)')
    a = ap.parse_args()
    today = dt.datetime.strptime(a.today, '%d.%m.%Y').date() if a.today else dt.date.today()

    with open(a.html, encoding='utf-8') as f:
        src = f.read()
    rep = Report(a.verbose)
    print(f'Файл: {os.path.relpath(a.html)} ({len(src.encode()) / 1e6:.2f} МБ)')
    check_version(src, rep, today)
    check_scripts(src, rep)
    check_offline(src, rep)
    data = load_consts(src, rep)
    if 'DRUGS' in data:
        check_drugs(data['DRUGS'], rep)
    check_links(data, rep)
    if 'ECG2_DATA' in data:
        check_ecg(data['ECG2_DATA'], rep)
    if not a.no_browser and 'DRUGS' in data:
        check_calculator(os.path.abspath(a.html), data['DRUGS'], rep)

    print(f'\nИтог: ошибок {rep.errors}, предупреждений {rep.warns}')
    sys.exit(1 if rep.errors else 0)


if __name__ == '__main__':
    main()
