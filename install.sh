#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if ! command -v kpackagetool6 >/dev/null; then
    echo 'Install KDE Plasma 6 / kpackage first.' >&2
    exit 1
fi
if kpackagetool6 --type Plasma/Wallpaper --show org.talal.moonlive >/dev/null 2>&1; then
    kpackagetool6 --type Plasma/Wallpaper --upgrade "$PWD/plugin"
else
    kpackagetool6 --type Plasma/Wallpaper --install "$PWD/plugin"
fi
printf '\nInstalled. Right-click desktop → Configure Desktop and Wallpaper → Wallpaper type: Video Wallpaper + Live Clock.\n'
