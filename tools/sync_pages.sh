#!/bin/sh
# GitHub Pages публикует корень репозитория: копируем веб-файлы из www/ в корень.
# Запускать после каждой правки www/index.html, коммитить вместе.
cd "$(dirname "$0")/.." || exit 1
cp www/index.html www/sw.js www/manifest.webmanifest www/_headers .
cp -r www/icons .
python3 tools/build_public.py >/dev/null && echo "общая версия пересобрана: public/"
python3 tools/build_rustore.py || exit 1   # вариант для RuStore: общая версия без доната
# правка 2026-10 (8.30): версия RuStore отдельной папкой на GitHub Pages — …/rustore/ (для установки на iPhone)
mkdir -p rustore && cp android/app/src/rustore/assets/public/index.html rustore/index.html \
  && cp www/sw.js www/manifest.webmanifest www/_headers rustore/ && cp -r www/icons rustore/ && echo "папка rustore/ обновлена"
cmp -s www/index.html index.html && echo "корень синхронизирован с www/"
