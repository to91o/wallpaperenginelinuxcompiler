import QtQuick
import org.kde.taskmanager as TaskManager

Item {
    id: root
    visible: false
    property bool pauseFullscreen: false
    property bool pauseMaximized: false
    property bool pauseFocused: false
    property rect screenGeometry
    readonly property bool shouldPause: policy.shouldPause
    TaskManager.VirtualDesktopInfo { id: desktops }
    TaskManager.ActivityInfo { id: activities }
    TaskManager.TasksModel {
        id: tasks
        groupMode: TaskManager.TasksModel.GroupDisabled
        filterByScreen: true
        screenGeometry: root.screenGeometry
        filterByVirtualDesktop: true
        virtualDesktop: desktops.currentDesktop
        filterByActivity: true
        activity: activities.currentActivity
        filterMinimized: true
    }
    WindowPausePolicy {
        id: policy
        windowModel: tasks
        pauseFullscreen: root.pauseFullscreen
        pauseMaximized: root.pauseMaximized
        pauseFocused: root.pauseFocused
    }
}
