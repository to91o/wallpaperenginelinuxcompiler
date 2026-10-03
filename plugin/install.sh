#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
package_tool=""
for candidate in kpackagetool6 /usr/lib/qt6/bin/kpackagetool6; do
    if command -v "$candidate" >/dev/null 2>&1; then
        package_tool=$(command -v "$candidate")
        break
    fi
done
if [[ -z "$package_tool" ]]; then
    echo 'Plasma Video Wallpaper needs kpackagetool6 from your Plasma 6 package source.' >&2
    exit 1
fi
if command -v plasmashell >/dev/null 2>&1; then
    version=$(plasmashell --version 2>/dev/null)
    if [[ "$version" =~ [[:space:]]5\. ]]; then
        echo 'Plasma Video Wallpaper requires Plasma 6; Plasma 5 was detected.' >&2
        exit 1
    fi
fi
# Keep the original ID so existing installations and settings can be upgraded.
if "$package_tool" --type Plasma/Wallpaper --show org.talal.moonlive >/dev/null 2>&1; then
    "$package_tool" --type Plasma/Wallpaper --upgrade "$PWD"
else
    "$package_tool" --type Plasma/Wallpaper --install "$PWD"
fi
printf '\nInstalled Plasma Video Wallpaper for your user.\nRight-click desktop → Configure Desktop and Wallpaper → Plasma Video Wallpaper.\n'
