import QtQuick
import QtQml.Models

Item {
    id: root
    visible: false
    property var windowModel
    property bool pauseFullscreen: false
    property bool pauseMaximized: false
    property bool pauseFocused: false
    property int blockingWindows: 0
    readonly property bool shouldPause: blockingWindows > 0
    function update() {
        let count = 0;
        for (let i = 0; i < windows.count; i++) {
            const item = windows.objectAt(i);
            if (item && item.blocksWallpaper) count++;
        }
        blockingWindows = count;
    }
    Instantiator {
        id: windows
        model: root.windowModel
        delegate: QtObject {
            required property var model
            readonly property bool blocksWallpaper: !model.IsMinimized &&
                ((root.pauseFullscreen && model.IsFullScreen) ||
                 (root.pauseMaximized && model.IsMaximized) ||
                 (root.pauseFocused && model.IsWindow && model.IsActive))
            onBlocksWallpaperChanged: Qt.callLater(root.update)
        }
        onObjectAdded: Qt.callLater(root.update)
        onObjectRemoved: Qt.callLater(root.update)
    }
}
