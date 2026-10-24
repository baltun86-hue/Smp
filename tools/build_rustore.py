#!/usr/bin/env python3
"""Сборка index.html для варианта RuStore (правка 2026-10, 8.08).
Берёт общую версию public/index.html (её делает build_public.py), убирает ссылку «Поддержать проект»
(сбор денег в RuStore — только для ИП и юрлиц) и кладёт файл в ресурсы варианта rustore:
android/app/src/rustore/assets/public/index.html — он перекрывает личную версию из src/main.
"""
import re, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
src = ROOT / 'public' / 'index.html'
dst = ROOT / 'android' / 'app' / 'src' / 'rustore' / 'assets' / 'public' / 'index.html'
s = src.read_text(encoding='utf-8')
s2, n = re.subn(r'<div style="margin:0 0 18px">Спасибо, что пользуетесь приложением!.*?Поддержать проект</a></div>', '', s, flags=re.S)
if n != 1:
    sys.exit('build_rustore: блок доната не найден (%d) — проверьте разметку «О программе»' % n)
for bad in ('cloudtips', 'Альметьев', 'АССМП', '8553', 'Татнефть'):
    if bad in s2:
        sys.exit('build_rustore: в версии для RuStore осталось «%s»' % bad)
# своя нумерация RuStore: VERSION в файле = versionName из android/rustore.properties, дата — как у исходной версии;
# (из какой сборки справочника сделана версия — видно в выводе скрипта и в коммите)
props = dict(l.split('=', 1) for l in (ROOT / 'android' / 'rustore.properties').read_text(encoding='utf-8').splitlines()
             if l and not l.startswith('#') and '=' in l)
rv = props['versionName'].strip()
m = re.search(r'VERSION="([^ "]+) \(([^)]+)\)"', s2)
if not m:
    sys.exit('build_rustore: VERSION не найдена')
base, date = m.group(1), m.group(2)
s2 = s2.replace(m.group(0), 'VERSION="%s (%s)"' % (rv, date), 1)
s2 = s2.replace("textContent='v'+VERSION+' · общая';", "textContent='v'+VERSION;", 1)  # в RuStore пометка «общая» не нужна
dst.parent.mkdir(parents=True, exist_ok=True)
dst.write_text(s2, encoding='utf-8')
print('вариант RuStore собран: v%s (данные %s) →' % (rv, base), dst.relative_to(ROOT))
