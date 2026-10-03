"""Distribution-aware hints and KDE tool discovery; never installs system packages."""
import argparse
from pathlib import Path
import shutil


def find_tool(name):
    candidates = {'qdbus6': ('qdbus6', '/usr/lib/qt6/bin/qdbus', 'qdbus', '/usr/lib/qt5/bin/qdbus'),
                  'kpackagetool6': ('kpackagetool6', '/usr/lib/qt6/bin/kpackagetool6')}.get(name, (name,))
    return next((path for candidate in candidates if (path := shutil.which(candidate))), None)


def distribution(path='/etc/os-release'):
    try:
        values = dict(line.split('=', 1) for line in Path(path).read_text().splitlines()
                      if '=' in line and not line.startswith('#'))
    except OSError:
        return 'unknown'
    ids = (values.get('ID', '') + ' ' + values.get('ID_LIKE', '')).replace('"', '').split()
    if 'arch' in ids: return 'arch'
    if any(value in ids for value in ('linuxmint', 'ubuntu', 'debian')): return 'debian'
    return 'unknown'


def package_hint(component):
    packages = {
        'venv': ('python python-pip', 'python3-venv python3-pip'),
        'tk': ('tk', 'python3-tk'),
        'Xvfb': ('xorg-server-xvfb', 'xvfb'),
        'xdotool': ('xdotool', 'xdotool'),
        'ffmpeg': ('ffmpeg', 'ffmpeg'),
    }
    if component == 'browser':
        return 'Install Chromium from your distribution, or run .venv/bin/python -m playwright install chromium.'
    if component == 'kde':
        return 'Use the same package source as your Plasma 6 installation for kpackagetool6 and Qt 6 Multimedia/QML. See README.md (Mint setup).'
    if component not in packages: return 'See README.md for installation instructions.'
    distro = distribution()
    arch, debian = packages[component]
    if distro == 'arch': return 'sudo pacman -S --needed ' + arch
    if distro == 'debian': return 'sudo apt install ' + debian
    return f'Arch: sudo pacman -S --needed {arch}; Mint/Ubuntu: sudo apt install {debian}'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--tool')
    group.add_argument('--hint')
    args = parser.parse_args()
    if args.hint:
        print(package_hint(args.hint))
    else:
        tool = find_tool(args.tool)
        if not tool: parser.exit(1, package_hint('kde') + '\n')
        print(tool)
