#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if ! python3 -m venv .venv; then
    printf '\nPython venv setup failed.\n' >&2
    python3 platform_support.py --hint venv >&2
    exit 1
fi
if .venv/bin/python -m pip --version >/dev/null 2>&1; then
    .venv/bin/python -m pip install -r requirements.txt
elif python3 -m pip --version >/dev/null 2>&1; then
    python3 -m pip --python .venv install -r requirements.txt
else
    printf '\nMissing pip.\n' >&2
    python3 platform_support.py --hint venv >&2
    exit 1
fi
if ! command -v chromium >/dev/null 2>&1 && ! command -v chromium-browser >/dev/null 2>&1; then
    if ! .venv/bin/python -m playwright install chromium; then
        printf '\nBrowser download failed. Other exports still work.\n' >&2
        python3 platform_support.py --hint browser >&2
    fi
fi
printf '\nReady. Run: bash launch.sh\n'
