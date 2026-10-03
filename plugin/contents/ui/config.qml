import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtCore
import QtQuick.Dialogs as Dialogs
import Qt.labs.folderlistmodel

ScrollView {
    id: root
    clip: true
    contentWidth: availableWidth
    // Plasma passes these when constructing the wallpaper configuration page.
    property var configDialog: null
    property var wallpaperConfiguration: null
    readonly property bool pauseSettingsAvailable: {
        const config = configDialog && configDialog.wallpaperConfiguration
            ? configDialog.wallpaperConfiguration : wallpaperConfiguration;
        if (!config || typeof config.keys !== "function") return true;
        const keys = config.keys();
        return ["PausePlayback", "PauseFullscreen", "PauseMaximized", "PauseFocused", "PauseWhenHidden"]
            .every(function(key) { return keys.indexOf(key) >= 0; });
    }
    property string cfg_LibraryFolder
    property bool refreshing: false
    readonly property string homePath: StandardPaths.writableLocation(StandardPaths.HomeLocation)
    readonly property string defaultLibrary: homePath + "/Videos/WallpaperExports"
    function normalizeFolder(value) {
        let path = String(value || "").trim();
        if ((path.startsWith('"') && path.endsWith('"')) || (path.startsWith("'") && path.endsWith("'")))
            path = path.slice(1, -1);
        if (!path) return defaultLibrary;
        if (path.startsWith("file://")) {
            try { path = decodeURIComponent(path.replace(/^file:\/\/(?:localhost)?/, "")); }
            catch (e) { return ""; }
        }
        if (path === "~") path = homePath;
        if (path.startsWith("~/")) path = homePath + path.slice(1);
        return path;
    }
    readonly property string libraryPath: normalizeFolder(cfg_LibraryFolder)
    readonly property url folderUrl: libraryPath.charAt(0) === "/"
        ? "file://" + encodeURI(libraryPath).replace(/#/g, "%23").replace(/\?/g, "%3F") : ""
    property alias cfg_PauseFocused: optionPauseFocused.checked
    property alias cfg_PausePlayback: optionPausePlayback.checked
    property alias cfg_PauseFullscreen: optionPauseFullscreen.checked
    property alias cfg_PauseMaximized: optionPauseMaximized.checked
    property alias cfg_PauseWhenHidden: optionPauseWhenHidden.checked
    property string cfg_VideoFile
    property real cfg_ClockX
    property real cfg_ClockY
    property int cfg_ClockSize
    property string cfg_ClockColor
    property string cfg_AccentColor
    property alias cfg_ShowSeconds: optionShowSeconds.checked
    property alias cfg_Use12Hour: optionUse12Hour.checked
    property alias cfg_ShowDate: optionShowDate.checked
    property alias cfg_ShowClock: optionShowClock.checked
    property alias cfg_ShowCalendar: optionShowCalendar.checked
    ColumnLayout {
    width: root.availableWidth
    Label { text: "Video wallpapers"; font.bold: true }
    Label { Layout.fillWidth: true; wrapMode: Text.Wrap; text: "Turn off the live overlay below to hide its clock, date, calendar and accent line. This is separate from a clock embedded in the video." }
    CheckBox { id: optionShowClock; objectName: "optionShowClock"; text: "Show clock, date and calendar" }
    GroupBox {
        title: "Playback and automatic pause"
        Layout.fillWidth: true
        ColumnLayout {
            anchors.fill: parent
            Label {
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                visible: !root.pauseSettingsAvailable
                text: "Plasma still has the previous plugin settings loaded. Switch Wallpaper type to Image and Apply, then switch back to Plasma Video Wallpaper. If these options remain unavailable, log out and back in."
            }
            CheckBox { enabled: root.pauseSettingsAvailable; id: optionPausePlayback; text: "Pause video now" }
            CheckBox { enabled: root.pauseSettingsAvailable; id: optionPauseFullscreen; text: "Pause when a window is fullscreen" }
            CheckBox { enabled: root.pauseSettingsAvailable; id: optionPauseMaximized; text: "Pause when a window is maximized" }
            CheckBox { enabled: root.pauseSettingsAvailable; id: optionPauseFocused; text: "Pause when an application window is focused" }
            CheckBox { enabled: root.pauseSettingsAvailable; id: optionPauseWhenHidden; text: "Pause when Plasma hides the wallpaper" }
            Label {
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                text: "Window rules apply to this screen, desktop and activity. Playback resumes automatically; the live clock keeps updating."
            }
        }
    }
    Label { text: "Wallpaper folder" }
    RowLayout {
        TextField {
            Layout.fillWidth: true
            text: root.cfg_LibraryFolder || root.defaultLibrary
            onTextEdited: root.cfg_LibraryFolder = text
            placeholderText: StandardPaths.writableLocation(StandardPaths.HomeLocation) + "/Videos/WallpaperExports"
        }
        Button { text: "Choose folder…"; onClicked: folderPicker.open() }
        Button { text: "Refresh"; onClicked: { root.refreshing = true; refreshTimer.restart(); } }
    }
    Dialogs.FolderDialog {
        id: folderPicker
        title: "Choose the folder containing exported videos"
        currentFolder: root.folderUrl
        onAccepted: root.cfg_LibraryFolder = root.normalizeFolder(selectedFolder)
    }
    Label {
        Layout.fillWidth: true
        wrapMode: Text.Wrap
        text: String(root.folderUrl) === "" ? "Enter an absolute folder path or use Choose folder."
            : library.status === FolderListModel.Loading ? "Reading " + root.libraryPath
            : library.count + " videos in " + root.libraryPath
    }
    Timer { id: refreshTimer; interval: 100; onTriggered: root.refreshing = false }
    FolderListModel {
        id: library
        // Qt 6 FolderListModel reparses its decoded local path as a URL.
        // Preserve escaping through that second parse (not needed by FolderDialog).
        folder: root.refreshing ? "" : String(root.folderUrl).replace(/%/g, "%25")
        nameFilters: ["*.[mM][pP]4", "*.[wW][eE][bB][mM]", "*.[mM][kK][vV]", "*.[mM][oO][vV]", "*.[mM]4[vV]"]
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
        text: "No playable video files were found here. Choose the folder containing your MP4 exports (not the Steam project folders), then Refresh. Subfolders are not scanned."
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

    CheckBox { id: optionShowDate; objectName: "optionShowDate"; text: "Show date" }
    CheckBox { id: optionShowCalendar; objectName: "optionShowCalendar"; text: "Show calendar" }
    CheckBox { id: optionShowSeconds; objectName: "optionShowSeconds"; text: "Show seconds" }
    CheckBox { id: optionUse12Hour; objectName: "optionUse12Hour"; text: "12-hour time" }
    Label { Layout.fillWidth: true; wrapMode: Text.Wrap; text: "Works with local videos supported by your Qt Multimedia backend, including MP4 and supported WebM/MKV files. No Wallpaper Engine or converter is required. Clock, date, and calendar use your computer's timezone and remain live while the video loops. If the source video already contains a clock, that baked-in clock remains visible." }
    Item { Layout.fillHeight: true }
}
}
