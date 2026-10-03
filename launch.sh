#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
# Read-only CLI commands need neither the rendering environment nor Tk.
for arg in "$@"; do
    case "$arg" in
        --help|-h|--list-wallpapers|--doctor|--refresh-previews|--deduplicate-library)
            exec python3 wallpaper_to_mp4.py "$@"
            ;;
    esac
done
if ! .venv/bin/python -c 'import lz4.block, moderngl, numpy, PIL, playwright.sync_api' >/dev/null 2>&1; then
    bash setup.sh
fi
exec .venv/bin/python wallpaper_to_mp4.py "$@"
