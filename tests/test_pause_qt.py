"""Exercise window pause decisions using Qt's real model notifications."""
import os
from pathlib import Path
import unittest
try:
    from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, QEventLoop, QTimer
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
except ImportError:
    QGuiApplication = None

if QGuiApplication:
    class Windows(QAbstractListModel):
        names = {Qt.UserRole + 1: b'IsFullScreen', Qt.UserRole + 2: b'IsMaximized', Qt.UserRole + 3: b'IsMinimized'}
        def __init__(self):
            super().__init__(); self.flags = dict.fromkeys(self.names, False)
        def rowCount(self, parent=QModelIndex()): return 0 if parent.isValid() else 1
        def roleNames(self): return self.names
        def data(self, index, role): return self.flags.get(role, None) if index.isValid() else None
        def change(self, name, value):
            role = next(key for key, field in self.names.items() if field.decode() == name)
            self.flags[role] = value
            self.dataChanged.emit(self.index(0), self.index(0), [role])


@unittest.skipIf(QGuiApplication is None, 'Optional PySide6 runtime not installed')
class PauseTests(unittest.TestCase):
    def test_pause_and_resume_follow_window_state_and_options(self):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        app = QGuiApplication.instance() or QGuiApplication([])
        engine = QQmlApplicationEngine()
        engine.load(str(Path(__file__).resolve().parents[1] / 'plugin/contents/ui/WindowPausePolicy.qml'))
        self.assertTrue(engine.rootObjects())
        policy = engine.rootObjects()[0]; windows = Windows()
        policy.setProperty('windowModel', windows)
        def settle():
            loop = QEventLoop(); QTimer.singleShot(50, loop.quit); loop.exec()
        settle(); self.assertFalse(policy.property('shouldPause'))
        windows.change('IsFullScreen', True)
        settle(); self.assertFalse(policy.property('shouldPause'))
        policy.setProperty('pauseFullscreen', True)
        settle(); self.assertTrue(policy.property('shouldPause'))
        windows.change('IsMinimized', True)
        settle(); self.assertFalse(policy.property('shouldPause'))
        windows.change('IsMinimized', False)
        settle(); self.assertTrue(policy.property('shouldPause'))
        windows.change('IsFullScreen', False)
        windows.change('IsMaximized', True)
        settle(); self.assertFalse(policy.property('shouldPause'))
        policy.setProperty('pauseMaximized', True)
        settle(); self.assertTrue(policy.property('shouldPause'))
        policy.setProperty('pauseMaximized', False)
        settle(); self.assertFalse(policy.property('shouldPause'))
        engine.deleteLater(); app.processEvents()
