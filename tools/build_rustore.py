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
dst.parent.mkdir(parents=True, exist_ok=True)
dst.write_text(s2, encoding='utf-8')
print('вариант RuStore собран:', dst.relative_to(ROOT))
