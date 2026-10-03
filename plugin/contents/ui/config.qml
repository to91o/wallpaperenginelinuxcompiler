import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtCore
import Qt.labs.folderlistmodel

ScrollView {
    id: root
    clip: true
    contentWidth: availableWidth
    property string cfg_LibraryFolder
    property bool refreshing: false
    readonly property string libraryPath: String(cfg_LibraryFolder || "").trim()
    readonly property string folderUrl: libraryPath.charAt(0) === "/"
        ? "file://" + encodeURI(libraryPath).replace(/#/g, "%23").replace(/\?/g, "%3F") : ""
    Component.onCompleted: {
        if (!cfg_LibraryFolder) cfg_LibraryFolder = StandardPaths.writableLocation(StandardPaths.HomeLocation) + "/Videos/WallpaperExports";
    }
    property string cfg_VideoFile
    property real cfg_ClockX
    property real cfg_ClockY
    property int cfg_ClockSize
    property string cfg_ClockColor
    property string cfg_AccentColor
    property bool cfg_ShowSeconds
    property bool cfg_Use12Hour
    property bool cfg_ShowDate
    property bool cfg_ShowClock
    property bool cfg_ShowCalendar
    ColumnLayout {
    width: root.availableWidth
    Label { text: "Video wallpapers"; font.bold: true }
    Label { text: "Wallpaper folder" }
    RowLayout {
        TextField {
            Layout.fillWidth: true
            text: root.cfg_LibraryFolder
            onTextEdited: root.cfg_LibraryFolder = text
            placeholderText: StandardPaths.writableLocation(StandardPaths.HomeLocation) + "/Videos/WallpaperExports"
        }
        Button { text: "Refresh"; onClicked: { root.refreshing = true; refreshTimer.restart(); } }
    }
    Timer { id: refreshTimer; interval: 100; onTriggered: root.refreshing = false }
    FolderListModel {
        id: library
        folder: root.refreshing ? "" : root.folderUrl
        nameFilters: ["*.mp4", "*.webm", "*.mkv", "*.mov", "*.m4v", "*.MP4", "*.WEBM", "*.MKV"]
        showDirs: false
        showHidden: false
        sortField: FolderListModel.Name
    }
    ScrollView {
        Layout.fillWidth: true
        Layout.preferredHeight: 320
        clip: true
        GridView {
            id: gallery
            model: library
            cellWidth: Math.max(150, Math.floor(width / Math.max(1, Math.floor(width / 220))))
            cellHeight: 160
            delegate: ItemDelegate {
                required property string fileName
                required property string filePath
                required property url fileUrl
                readonly property string wallpaperTitle: fileName.replace(/\.[^.]+$/, "")
                    .replace(/_\d+x\d+_\d+fps_[\d.]+s(?:_ss2)?(?:_\d+)?$/, "").replace(/_/g, " ")
                ToolTip.visible: hovered
                ToolTip.text: fileName
                width: gallery.cellWidth - 8
                height: gallery.cellHeight - 8
                highlighted: root.cfg_VideoFile === filePath || root.cfg_VideoFile === String(fileUrl)
                onClicked: root.cfg_VideoFile = filePath
                contentItem: ColumnLayout {
                    Image {
                        id: thumbnail
                        Layout.fillWidth: true
                        Layout.preferredHeight: 110
                        source: String(fileUrl) + ".jpg"
                        fillMode: Image.PreserveAspectFit
                        asynchronous: true
                        cache: false
                        Label { anchors.centerIn: parent; visible: thumbnail.status === Image.Error; text: "Video" }
                    }
                    Label { Layout.fillWidth: true; text: wallpaperTitle; horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight }
                }
            }
        }
    }
    Label {
        Layout.fillWidth: true
        wrapMode: Text.Wrap
        visible: library.count === 0
        text: "Your library is empty. Export wallpapers into this folder, then click Refresh."
    }
    Label { text: "Selected wallpaper (full file path)" }
    TextField { Layout.fillWidth: true; text: root.cfg_VideoFile; onTextEdited: root.cfg_VideoFile = text; placeholderText: "/home/user/Videos/wallpaper.mp4" }
    Label { text: "Live clock — position from left and top (%)" }
    RowLayout {
        Label { text: "Left" }
        Slider { Layout.fillWidth: true; from: 0; to: 95; value: root.cfg_ClockX; onMoved: root.cfg_ClockX = value }
        Label { text: Math.round(root.cfg_ClockX) + "%" }
        Label { text: "Top" }
        Slider { Layout.fillWidth: true; from: 0; to: 95; value: root.cfg_ClockY; onMoved: root.cfg_ClockY = value }
        Label { text: Math.round(root.cfg_ClockY) + "%" }
    }
    RowLayout {
        Label { text: "Clock size (pixels)" }
        SpinBox { from: 12; to: 160; value: root.cfg_ClockSize; editable: true; onValueModified: root.cfg_ClockSize = value }
    }
    RowLayout {
        Label { text: "Text color" }
        TextField { text: root.cfg_ClockColor; onTextEdited: root.cfg_ClockColor = text }
        Label { text: "Accent color" }
        TextField { text: root.cfg_AccentColor; onTextEdited: root.cfg_AccentColor = text }
    }
    CheckBox { text: "Show clock"; checked: root.cfg_ShowClock; onToggled: root.cfg_ShowClock = checked }
    CheckBox { text: "Show date"; checked: root.cfg_ShowDate; onToggled: root.cfg_ShowDate = checked }
    CheckBox { text: "Show calendar"; checked: root.cfg_ShowCalendar; onToggled: root.cfg_ShowCalendar = checked }
    CheckBox { text: "Show seconds"; checked: root.cfg_ShowSeconds; onToggled: root.cfg_ShowSeconds = checked }
    CheckBox { text: "12-hour time"; checked: root.cfg_Use12Hour; onToggled: root.cfg_Use12Hour = checked }
    Label { Layout.fillWidth: true; wrapMode: Text.Wrap; text: "Works with local videos supported by your Qt Multimedia backend, including MP4 and supported WebM/MKV files. No Wallpaper Engine or converter is required. Clock, date, and calendar use your computer's timezone and remain live while the video loops. If the source video already contains a clock, that baked-in clock remains visible." }
    Item { Layout.fillHeight: true }
}
}
