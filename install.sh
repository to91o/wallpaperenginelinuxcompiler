#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
package_tool=$(python3 platform_support.py --tool kpackagetool6)
if command -v plasmashell >/dev/null; then
    version=$(plasmashell --version 2>/dev/null)
    if [[ "$version" =~ [[:space:]]5\. ]]; then
        echo 'This plugin requires Plasma 6; Plasma 5 was detected.' >&2
        exit 1
    fi
fi
if "$package_tool" --type Plasma/Wallpaper --show org.talal.moonlive >/dev/null 2>&1; then
    "$package_tool" --type Plasma/Wallpaper --upgrade "$PWD/plugin"
else
    "$package_tool" --type Plasma/Wallpaper --install "$PWD/plugin"
fi
printf '\nInstalled. Right-click desktop → Configure Desktop and Wallpaper → Wallpaper type: Video Wallpaper + Live Clock.\n'
