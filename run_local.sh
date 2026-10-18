#!/usr/bin/env sh
# Запуск FishStocke без Docker (Linux/macOS)
cd "$(dirname "$0")" && exec python3 deploy/run_local.py "$@"
