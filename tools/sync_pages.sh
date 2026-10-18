#!/bin/sh
# GitHub Pages публикует корень репозитория: копируем веб-файлы из www/ в корень.
# Запускать после каждой правки www/index.html, коммитить вместе.
cd "$(dirname "$0")/.." || exit 1
cp www/index.html www/sw.js www/manifest.webmanifest www/_headers .
cp -r www/icons .
cmp -s www/index.html index.html && echo "корень синхронизирован с www/"
