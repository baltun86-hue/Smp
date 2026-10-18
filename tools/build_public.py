#!/usr/bin/env python3
"""Сборка общей версии справочника из рабочей (www/index.html).

Рабочая версия — для сотрудников ГАУЗ «Альметьевская ССМП»: содержит приказы, маршрутизацию
по г. Альметьевску, местные телефоны и пометки «нет в укладке». В общую версию они не попадают.
Рабочий файл не меняется; общая версия пересобирается скриптом (источник правды — www/).

Запуск: python3 tools/build_public.py   → public/ (index.html, sw.js, manifest.webmanifest, _headers, icons/)
"""
import re, shutil, sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'www'); OUT = os.path.join(ROOT, 'public')
s = open(os.path.join(SRC, 'index.html'), encoding='utf-8').read()
log = []

def sub(pat, rep, flags=0, minimum=1, note=''):
    global s
    s, n = re.subn(pat, rep, s, flags=flags)
    if n < minimum: sys.exit(f'ОШИБКА: правило не сработало ({note or pat[:60]})')
    log.append((note or pat[:60], n))

# 1) Приказы и маршрутизация: данные, комментарий к ним, плитка на главной, вкладка
a = s.index('const ORDERS=['); a = s.rfind('/* ', 0, a); b = s.index('function ordersHTML')
s = s[:a] + '/* Приказы и маршрутизация — только во внутренней версии */\nconst ORDERS=[];\n' + s[b:]; log.append(('ORDERS вырезаны', 1))
sub(r"\n\s*\{id:'tabOrders'[^\n]*\},", '', note='плитка «Приказы» на главной')
sub(r'<button id="tabOrders">Приказы и маршрутизация</button>', '<button id="tabOrders" style="display:none" hidden>Приказы и маршрутизация</button>', note='кнопка вкладки скрыта')

# 2) Автоподстановка местных телефонов (код 8553) — в общей версии телефонов нет
a = s.index('/* Превращает номера телефонов'); b = s.index('function fmt(n)')
s = s[:a] + 'const linkTel=s=>String(s);\n' + s[b:]; log.append(('linkTel без телефонов', 1))

# 3) Местные пометки об укладке станции (чистка текста алгоритмов — только в общей версии)
R = [
 (r'\s*\(пропранолол — нет в укладке\)', ''),
 (r'\s*\(в/в нитроглицерина в укладке нет\)', ''),
 (r'; в/в нитратов в укладке нет — спрей', ''),
 (r'\s*Эноксапарина нет в укладке\.', ''),
 (r'\s*—\s*эноксапарина нет в укладке', ''),
 (r'\s*\(нет в укладке\)', ''),
 (r'\s*—\s*НЕТ в укладке \(вне МОССМП 2026\)', ' (вне МОССМП 2026)'),
 (r'\s*—\s*(?:тиосульфата )?нет в укладке', ''),
 (r'\s*—\s*НЕТ В УКЛАДКЕ \(утеротоников в укладке нет\)', ''),
 (r'\s*\(нет в укладке\)', ''),
 (r'; вне укладки\)', ')'),
 (r'\s*\(вне укладки\)', ''),
 (r' — эти препараты не входят в укладку СМП', ''),
 (r'Реактиватор холинэстеразы \(нет в укладке\)', 'Реактиватор холинэстеразы'),
 (r'числится в официальной укладке СМП\. Карточка (?:ранее )?отсутствовала в базе справочника[^"]*?(?:Метамизол \(Анальгин\), не указанный в алгоритмах МОССМП 2026 для этих состояний\.|«нет в укладке»\.)', 'входит в перечень препаратов СМП (МОССМП 2026).'),
 (r'Карточка ранее отсутствовала в базе справочника — часть протоколов помечала препарат «нет в укладке»; добавлена как отсутствовавшая позиция, применяемая согласно алгоритмам МОССМП 2026\.', 'Применяется согласно алгоритмам МОССМП 2026.'),
 (r'Карточка ранее отсутствовала в базе справочника — часть протоколов помечала препарат «нет в укладке»\.', 'Применяется согласно алгоритмам МОССМП 2026.'),
 (r'Препараты из укладки', 'Препараты по алгоритму'),
 (r'чипы «Препараты из укладки»', 'чипы «Препараты по алгоритму»'),
 (r'Полоса препаратов из укладки', 'Полоса препаратов'),
 (r'чипы укладки', 'чипы препаратов'),
]
for pat, rep in R:
    s, n = re.subn(pat, rep, s); log.append((pat[:50], n))
left = [m.start() for m in re.finditer('укладк|УКЛАДК', s)]
if left:
    for i in left: print('ОСТАЛОСЬ:', s[max(0, i-90):i+60].replace('\n', ' '))
    sys.exit('ОШИБКА: остались упоминания укладки')

# 4) Контроль: ничего местного не осталось
BAD = r'Альметьев|АССМП|Агзамов|8553|Татнефть|\b\d{2}-\d{2}-\d{2}\b|8\s\d{3}\s\d{3}-\d{2}-\d{2}'
bad = [(m.start(), s[max(0, m.start()-60):m.end()+40].replace('\n', ' ')) for m in re.finditer(BAD, s)]
if bad:
    for b_ in bad[:20]: print('МЕСТНОЕ:', b_)
    sys.exit('ОШИБКА: остались местные данные')


# 5) Метка версии: общая сборка
sub(r"document\.getElementById\('ver'\)\.textContent='v'\+VERSION;", "document.getElementById('ver').textContent='v'+VERSION+' · общая';", note='метка «общая» у версии')

os.makedirs(OUT, exist_ok=True)
open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8').write(s)
for f in ('sw.js', '_headers'):
    shutil.copy(os.path.join(SRC, f), os.path.join(OUT, f))
import json
m = json.load(open(os.path.join(SRC, 'manifest.webmanifest'), encoding='utf-8'))
m['name'] = 'СМП Справочник — общая версия'; m['short_name'] = 'Справочник СМП'
m['description'] = 'Офлайн-справочник для бригад скорой помощи: препараты, алгоритмы, ЭКГ, МКБ-10 (общая версия)'
json.dump(m, open(os.path.join(OUT, 'manifest.webmanifest'), 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
shutil.rmtree(os.path.join(OUT, 'icons'), ignore_errors=True); shutil.copytree(os.path.join(SRC, 'icons'), os.path.join(OUT, 'icons'))
print('общая версия собрана:', OUT, f'({len(s)//1024} КБ)')
for k, n in log: print(f'  {n:3d} × {k}')
