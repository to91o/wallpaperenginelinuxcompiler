import QtQuick
import QtQuick.Window
import QtMultimedia
import org.kde.plasma.plasmoid

WallpaperItem {
    id: root
    property date currentTime: new Date()
    readonly property int monthOffset: (new Date(currentTime.getFullYear(), currentTime.getMonth(), 1).getDay() + 6) % 7
    readonly property int monthDays: new Date(currentTime.getFullYear(), currentTime.getMonth() + 1, 0).getDate()
    readonly property real calendarCell: Math.max(22, configuration.ClockSize * .85)
    readonly property string videoPath: String(configuration.VideoFile || "").trim()
    readonly property bool pauseRequested: Boolean(configuration.PausePlayback) ||
        (Boolean(configuration.PauseWhenHidden) && !visible) ||
        (autoPause.item !== null && autoPause.item.shouldPause)
    onPauseRequestedChanged: Qt.callLater(syncPlayback)
    function syncPlayback() {
        if (String(player.source) === "") return;
        if (pauseRequested) player.pause();
        else player.play();
    }
    Loader {
        id: autoPause
        active: Boolean(root.configuration.PauseFullscreen) || Boolean(root.configuration.PauseMaximized) || Boolean(root.configuration.PauseFocused)
        source: "AutoPause.qml"
        onLoaded: {
            item.pauseFullscreen = Qt.binding(function() { return Boolean(root.configuration.PauseFullscreen); });
            item.pauseFocused = Qt.binding(function() { return Boolean(root.configuration.PauseFocused); });
            item.pauseMaximized = Qt.binding(function() { return Boolean(root.configuration.PauseMaximized); });
            item.screenGeometry = Qt.binding(function() { return Qt.rect(root.Screen.virtualX, root.Screen.virtualY, root.Screen.width, root.Screen.height); });
        }
    }
    function asUrl(path) {
        if (path === "") return "";
        if (path.indexOf("file:") === 0) return path;
        if (path.charAt(0) === "/") return "file://" + encodeURI(path).replace(/#/g, "%23").replace(/\?/g, "%3F");
        return "";
    }
    Rectangle { anchors.fill: parent; color: "#090b0c" }
    VideoOutput { id: video; anchors.fill: parent; fillMode: VideoOutput.PreserveAspectCrop }
    MediaPlayer {
        id: player
        source: root.asUrl(root.videoPath)
        videoOutput: video
        loops: MediaPlayer.Infinite
        onSourceChanged: Qt.callLater(root.syncPlayback)
        Component.onCompleted: Qt.callLater(root.syncPlayback)
        // No AudioOutput: desktop wallpaper remains silent.
    }
    Timer { interval: 250; running: true; repeat: true; onTriggered: root.currentTime = new Date() }
    Item {
        id: clock
        visible: root.configuration.ShowClock
        x: root.width * root.configuration.ClockX / 100
        y: root.height * root.configuration.ClockY / 100
        width: textColumn.width + 16
        height: textColumn.height
        Rectangle {
            x: 0; y: 0; width: Math.max(1, root.configuration.ClockSize / 22)
            height: parent.height; color: root.configuration.AccentColor
        }
        Column {
            id: textColumn; x: Math.max(8, root.configuration.ClockSize * .3); spacing: 2
            Text {
                color: root.configuration.ClockColor
                font.family: "Sans Serif"; font.pixelSize: root.configuration.ClockSize
                font.weight: Font.Light
                text: Qt.formatTime(root.currentTime, root.configuration.Use12Hour
                    ? (root.configuration.ShowSeconds ? "h:mm:ss AP" : "h:mm AP")
                    : (root.configuration.ShowSeconds ? "HH:mm:ss" : "HH:mm"))
            }
            Text {
                visible: root.configuration.ShowDate
                color: root.configuration.ClockColor
                font.family: "Sans Serif"; font.pixelSize: Math.max(10, root.configuration.ClockSize * .45)
                text: Qt.formatDate(root.currentTime, "dddd")
            }
            Text {
                visible: root.configuration.ShowDate
                color: root.configuration.ClockColor
                font.family: "Sans Serif"; font.pixelSize: Math.max(10, root.configuration.ClockSize * .45)
                text: Qt.formatDate(root.currentTime, "yyyy-MM-dd")
            }
            Column {
                visible: root.configuration.ShowCalendar
                spacing: 4
                Text {
                    color: root.configuration.ClockColor
                    font.pixelSize: Math.max(12, root.configuration.ClockSize * .5)
                    text: Qt.formatDate(root.currentTime, "MMMM yyyy")
                }
                Row {
                    Repeater {
                        model: ["M", "T", "W", "T", "F", "S", "S"]
                        Text {
                            required property string modelData
                            width: root.calendarCell
                            horizontalAlignment: Text.AlignHCenter
                            color: root.configuration.ClockColor
                            font.pixelSize: Math.max(10, root.configuration.ClockSize * .4)
                            text: modelData
                        }
                    }
                }
                Grid {
                    columns: 7
                    Repeater {
                        model: 42
                        Rectangle {
                            required property int index
                            readonly property int day: index - root.monthOffset + 1
                            width: root.calendarCell; height: root.calendarCell
                            radius: 3
                            color: day === root.currentTime.getDate() ? root.configuration.AccentColor : "transparent"
                            Text {
                                anchors.centerIn: parent
                                color: root.configuration.ClockColor
                                font.pixelSize: Math.max(10, root.configuration.ClockSize * .4)
                                text: parent.day >= 1 && parent.day <= root.monthDays ? String(parent.day) : ""
                            }
                        }
                    }
                }
            }
        }
    }
    Text {
        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
        anchors.margins: 16
        wrapMode: Text.Wrap; color: "white"
        visible: autoPause.active && autoPause.status === Loader.Error
        text: "Window-based pause is unavailable: Plasma's TaskManager module could not load. Manual pause remains available."
    }
    Text {
        anchors.centerIn: parent; width: parent.width * .8; wrapMode: Text.Wrap
        horizontalAlignment: Text.AlignHCenter; color: "white"; font.pixelSize: 20
        visible: root.videoPath === "" || player.error !== MediaPlayer.NoError || root.asUrl(root.videoPath) === ""
        text: player.error !== MediaPlayer.NoError ? "Could not play video: " + player.errorString
            : "Configure this wallpaper and paste an absolute local video path, such as /home/user/Videos/wallpaper.mp4."
    }
}
