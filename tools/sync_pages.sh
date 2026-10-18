#!/bin/sh
# GitHub Pages публикует корень репозитория: копируем веб-файлы из www/ в корень.
# Запускать после каждой правки www/index.html, коммитить вместе.
cd "$(dirname "$0")/.." || exit 1
cp www/index.html www/sw.js www/manifest.webmanifest www/_headers .
cp -r www/icons .
python3 tools/build_public.py >/dev/null && echo "общая версия пересобрана: public/"
cmp -s www/index.html index.html && echo "корень синхронизирован с www/"
