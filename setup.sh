#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if ! python3 -m venv .venv; then
    printf '\nPython venv setup failed. On Arch install: sudo pacman -S --needed python python-pip\n' >&2
    exit 1
fi
if .venv/bin/python -m pip --version >/dev/null 2>&1; then
    .venv/bin/python -m pip install -r requirements.txt
elif python3 -m pip --version >/dev/null 2>&1; then
    python3 -m pip --python .venv install -r requirements.txt
else
    printf '\nMissing pip. On Arch install: sudo pacman -S --needed python-pip\n' >&2
    exit 1
fi
if ! command -v chromium >/dev/null 2>&1 && ! command -v chromium-browser >/dev/null 2>&1; then
    if ! .venv/bin/python -m playwright install chromium; then
        printf '\nBrowser download failed. Other exports still work. For web wallpapers on Arch: sudo pacman -S --needed chromium\n' >&2
    fi
fi
printf '\nReady. Run: bash launch.sh\n'
