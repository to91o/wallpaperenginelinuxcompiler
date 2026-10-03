from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import platform_support as platform


class PlatformTests(unittest.TestCase):
    def test_os_release_detection(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'os-release'
            for contents, expected in [('ID=linuxmint\nID_LIKE="ubuntu debian"\n', 'debian'),
                                       ('ID=arch\n', 'arch'), ('ID=unknown\n', 'unknown')]:
                path.write_text(contents)
                self.assertEqual(platform.distribution(path), expected)
            self.assertEqual(platform.distribution(Path(d) / 'missing'), 'unknown')

    def test_mint_hints_do_not_use_pacman(self):
        with patch.object(platform, 'distribution', return_value='debian'):
            self.assertEqual(platform.package_hint('venv'), 'sudo apt install python3-venv python3-pip')
            self.assertEqual(platform.package_hint('Xvfb'), 'sudo apt install xvfb')

    def test_qt_private_bin_fallback(self):
        with patch.object(platform.shutil, 'which', side_effect=lambda name:
                          name if name == '/usr/lib/qt6/bin/qdbus' else None):
            self.assertEqual(platform.find_tool('qdbus6'), '/usr/lib/qt6/bin/qdbus')


if __name__ == '__main__':
    unittest.main()
