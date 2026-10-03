import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: root
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
    Label { text: "Looping video with a live system clock"; font.bold: true }
    Label { text: "MP4 path (absolute, without quotes or ~)" }
    TextField { Layout.fillWidth: true; text: root.cfg_VideoFile; onTextEdited: root.cfg_VideoFile = text; placeholderText: "/home/talal/wallpaper.mp4" }
    Label { text: "Clock position — percentage from the left and top" }
    RowLayout {
        Label { text: "X" }
        Slider { Layout.fillWidth: true; from: 0; to: 95; value: root.cfg_ClockX; onMoved: root.cfg_ClockX = value }
        Label { text: Math.round(root.cfg_ClockX) + "%" }
        Label { text: "Y" }
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
        Label { text: "Line color" }
        TextField { text: root.cfg_AccentColor; onTextEdited: root.cfg_AccentColor = text }
    }
    CheckBox { text: "Show clock"; checked: root.cfg_ShowClock; onToggled: root.cfg_ShowClock = checked }
    CheckBox { text: "Show weekday and date"; checked: root.cfg_ShowDate; onToggled: root.cfg_ShowDate = checked }
    CheckBox { text: "Show current month calendar"; checked: root.cfg_ShowCalendar; onToggled: root.cfg_ShowCalendar = checked }
    CheckBox { text: "Show seconds"; checked: root.cfg_ShowSeconds; onToggled: root.cfg_ShowSeconds = checked }
    CheckBox { text: "12-hour time"; checked: root.cfg_Use12Hour; onToggled: root.cfg_Use12Hour = checked }
    Label { Layout.fillWidth: true; wrapMode: Text.Wrap; text: "Works with any local MP4. Clock, date, and calendar use your computer's timezone and remain live while the video loops. If the source video already contains a clock, that baked-in clock remains visible." }
    Item { Layout.fillHeight: true }
}
