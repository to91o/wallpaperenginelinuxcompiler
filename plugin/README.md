# Plasma Video Wallpaper

A standalone KDE Plasma 6 wallpaper plugin for looping local videos with an optional live clock, date and calendar. It works independently of Wallpaper Engine, the exporter and the Moon backend. No Python environment, Steam account or original wallpaper assets are needed to play an existing video.

## Install

From the repository root, run `bash install.sh`. If you downloaded only the plugin folder, run `bash install.sh` from inside that folder instead. Both work from fish. Installation is per user and does not run sudo or change your current wallpaper.

Requires Plasma 6, kpackagetool6 and Qt 6 Multimedia/QML with compatible codecs. On Arch, install `qt6-multimedia qt6-multimedia-ffmpeg`. On Mint with Plasma 6, use the same Qt package source as your desktop; typical packages include `kpackagetool6 qml6-module-qtmultimedia libqt6multimedia6`. See the repository README for Mint details. Do not install mismatched Qt libraries.

Right-click the desktop → Configure Desktop and Wallpaper → **Plasma Video Wallpaper**. Set **Wallpaper folder** (default `~/Videos/WallpaperExports`), click a video tile, then Apply. The folder setting needs an absolute path without `~`. Refresh after adding videos. You can also enter an absolute local video path manually. Configure each monitor separately. If the plugin is absent, reopen the wallpaper settings or log out/in.

## Videos and overlays

MP4 with H.264 is the recommended format. WebM, MKV and other local video formats work when your Qt Multimedia backend supports their containers and codecs. This is a general video player, not an arbitrary Wallpaper Engine scene renderer. Videos loop silently with aspect-preserving crop. Keep the video in a permanent location.

Clock position, size, colors, 12/24-hour time, seconds, date and calendar are configurable. Disable **Show clock** for video-only playback. The live overlay uses the system timezone; a clock already baked into a video remains visible.

The plugin is displayed under its new generic name. Internal ID `org.talal.moonlive` remains for upgrades and retained settings; it does not restrict which videos can play.

Very early alpha. Intended for Plasma 6 X11 and Wayland, including Mint with Plasma 6.4.5; real desktop playback remains unverified in the cloud development environment.

## Folder gallery

The gallery lists local MP4/WebM/MKV/MOV/M4V videos in the selected folder without launching preview players. Converter exports include JPEG sidecars named `video.mp4.jpg`. Existing videos without sidecars show a generic tile and remain selectable. Nothing needs to be converted again just to appear in this gallery.

Requires QtCore and Qt.labs.folderlistmodel QML modules in addition to the playback dependencies. On Ubuntu-based Mint, matching packages commonly include `qml6-module-qtcore` and `qml6-module-qt-labs-folderlistmodel`. Use your Plasma/Qt package source. The gallery is under the **Plasma Video Wallpaper** wallpaper type, not the built-in Image type.
