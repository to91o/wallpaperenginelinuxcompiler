"""Optional Qt 6 integration tests: install PySide6-Essentials to run."""
import os
from pathlib import Path
import tempfile
import unittest
try:
    from PySide6.QtCore import QObject, QEventLoop, QTimer, QUrl, QMetaObject
    from PySide6.QtGui import QGuiApplication, QImage
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtQml import QQmlApplicationEngine, QQmlExpression
except ImportError:
    QGuiApplication = None


@unittest.skipIf(QGuiApplication is None, 'Optional PySide6 Qt runtime not installed')
class GalleryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def settle(self):
        loop = QEventLoop()
        QTimer.singleShot(350, loop.quit)
        loop.exec()

    def test_gallery_paths_listing_and_selection(self):
        engine = QQmlApplicationEngine()
        engine.load(str(Path(__file__).resolve().parents[1] / 'plugin/contents/ui/config.qml'))
        self.assertTrue(engine.rootObjects(), 'Plugin settings must load without QML errors')
        root = engine.rootObjects()[0]
        root.setProperty('width', 700); root.setProperty('height', 650)
        window = QQuickWindow(); window.resize(700, 650)
        root.setParentItem(window.contentItem()); window.show()
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / 'Videos # percent%'; folder.mkdir()
            for name in ('one.mp4', 'two.Mp4', 'ignore.jpg'):
                (folder / name).touch()
            preview = QImage(32, 18, QImage.Format_RGB32); preview.fill(0xff00ff00)
            self.assertTrue(preview.save(str(folder / 'one.mp4.jpg')))
            (folder / 'nested').mkdir()
            (folder / 'nested/hidden.mp4').touch()
            for value in (str(folder), '"' + str(folder) + '"', QUrl.fromLocalFile(str(folder)).toString()):
                root.setProperty('cfg_LibraryFolder', value)
                self.settle()
                self.assertEqual(root.property('libraryPath'), str(folder))
                views = [obj for obj in root.findChildren(QObject) if obj.metaObject().className().startswith('QQuickGridView')]
                self.assertEqual(len(views), 1)
                self.assertEqual(views[0].property('count'), 2)
                self.assertGreater(views[0].property('width'), 0)
            visuals = []; pending = [root]
            while pending:
                item = pending.pop(); visuals.append(item); pending.extend(item.childItems())
            delegates = [obj for obj in visuals if obj.property('filePath') is not None]
            self.assertTrue(delegates, 'Visible video tiles must exist')
            images = [obj for obj in visuals if obj.metaObject().className().startswith('QQuickImage')]
            ready = [QQmlExpression(engine.rootContext(), obj, 'status === 1').evaluate()[0] for obj in images]
            self.assertIn(True, ready, 'A sidecar thumbnail must load for a path containing # and %')
            self.assertTrue(QMetaObject.invokeMethod(delegates[0], 'clicked'))
            self.assertEqual(root.property('cfg_VideoFile'), delegates[0].property('filePath'))
            root.setProperty('cfg_LibraryFolder', '')
            self.assertEqual(root.property('libraryPath'), root.property('defaultLibrary'))
            expression = QQmlExpression(engine.rootContext(), root, "normalizeFolder('~/Videos/WallpaperExports')")
            result, _ = expression.evaluate()
            self.assertEqual(result, root.property('defaultLibrary'))
        window.close()
        engine.deleteLater()
        self.app.processEvents()
