# Wallpaper Engine to MP4 — Linux

**Very early alpha - purely a vibecoding passion project.** Features and compatibility are still evolving; expect bugs and rough edges.

Export video, image, extracted web and **supported** Wallpaper Engine scenes to H.264 MP4 on Linux. Targets Arch Linux and Linux Mint with KDE Plasma 6 Wayland (including 6.4.5); Mint desktop validation is pending. A separate custom renderer handles Moon Workshop 3453730450; shared export controls and the KDE live-clock plugin work across supported wallpapers.

This is not a universal Wallpaper Engine compiler. General scenes depend on linux-wallpaperengine compatibility. Arbitrary shaders, SceneScript, effects, perspective cameras and Windows application wallpapers may not work. Unsupported inputs should be reported rather than silently replaced with a Moon render.

## Arch setup and fish shell

Install system prerequisites once:

```fish
sudo pacman -S --needed python python-pip tk ffmpeg mesa chromium xdotool xorg-server-xvfb
```

For general scene wallpapers, install the renderer separately, for example through an AUR helper:

```fish
yay -S linux-wallpaperengine-git
```

From this project folder, launch with:

```fish
bash launch.sh
```

These commands work from fish: Bash runs the scripts, and you do not need to source a Bash activation script. The app creates a local `.venv`, installs its Python dependencies and uses that interpreter. It never runs sudo or installs system packages. Direct `python3 wallpaper_to_mp4.py` also prepares and switches to the local environment for exports. If system Chromium is missing, setup tries Playwright's browser download; a failed download does not prevent non-web exports.

Read-only commands do not create an environment, install anything or require Tk:

```fish
bash launch.sh --help
bash launch.sh --doctor
bash launch.sh --list-wallpapers
bash launch.sh --list-wallpapers --steam-folder /mnt/games/SteamLibrary
```

`--doctor` reports command/module presence for the interpreter running it. To inspect the prepared app environment, use `.venv/bin/python wallpaper_to_mp4.py --doctor`. Presence does not prove driver, renderer or Plasma compatibility.

## Linux Mint with KDE Plasma 6.4.5

Mint support is experimental. This targets an existing **Plasma 6** installation, not Mint's default Cinnamon desktop. Do not install a different KDE version to use the converter. The scripts also work from fish via `bash`; no environment activation is needed.

Install the shared export prerequisites:

```fish
sudo apt update
sudo apt install python3 python3-venv python3-pip python3-tk ffmpeg libegl1 libgl1 libgl1-mesa-dri xvfb xdotool libglib2.0-bin
bash setup.sh
```

For web exports, setup downloads Playwright Chromium if a system Chromium executable is unavailable. If the downloaded browser reports missing system libraries, install its supported dependencies explicitly:

```fish
.venv/bin/python -m playwright install-deps chromium
```

That Playwright command can request sudo; the app's own setup does not. A browser-download failure leaves other export paths usable.

The KDE plugin needs `kpackagetool6` and **Qt 6 Multimedia/QML matching the Qt libraries used by your Plasma installation**. On Ubuntu-based Mint, the package names commonly include `kpackagetool6`, `qml6-module-qtmultimedia` and `libqt6multimedia6`. Check availability and source before installation:

```fish
plasmashell --version
apt-cache policy kpackagetool6 qml6-module-qtmultimedia libqt6multimedia6
```

Use the same repository/source that supplied your Plasma 6.4.5 installation. If the packages are absent or their Qt versions conflict, resolve that through your KDE package source; do not mix Qt libraries from unrelated repositories. Then install the plugin:

```fish
bash install.sh
bash launch.sh --doctor
bash launch.sh
```

The installer discovers Qt tools outside PATH and rejects a detected Plasma 5 session. Export-and-apply supports qdbus6, Qt's private bin directories, or Mint's `gdbus` (`libglib2.0-bin`) fallback. It needs a running Plasma session; installing the plugin alone does not change the desktop wallpaper.

For **general scene exports**, install a compatible `linux-wallpaperengine` build using its upstream instructions for your Ubuntu/Mint base and Plasma package source. The Arch AUR command does not apply on Mint. `--doctor` reports whether the renderer is discoverable. Video, image, web and the asset-specific Moon backend do not need that renderer. No automatic source build or promise of arbitrary scene compatibility is included.

On your desktop, first export a short image or video with the KDE checkbox enabled. Confirm silent looping playback and the live clock/calendar, then test a supported scene with preview disabled. These are required desktop checks before Mint/Plasma support can be considered verified.

## No unwanted preview window

Hidden export is the default. Video/image exports use FFmpeg, web uses headless Chromium, Moon uses headless EGL, and other supported scenes use a private Xvfb display. General-scene capture now waits for the renderer's window, checks its dimensions and captures that window. Missing windows stop the export rather than producing a blank screen capture. The private display does not use your desktop's Wayland display or X authority file, and is cleaned up afterward.

Hidden scene rendering needs Xvfb and xdotool. It may use software rendering and run slowly. Scene capture is real-time; slow rendering may repeat frames. Hidden mode cannot make an unsupported scene compatible.

Visible GPU capture remains available only when explicitly selected with **Show preview window for scene GPU capture** or `--mode gpu`. On KDE Wayland this requires XWayland and a valid `DISPLAY`; it opens an X11 renderer window that must stay visible. If the desktop resizes it, reduce resolution/supersampling or use hidden mode. Failed hidden exports never automatically open a desktop preview.

## Export and apply to KDE

The standalone **Plasma Video Wallpaper** plugin is included in [`plugin/`](plugin/README.md). It needs neither the converter nor Wallpaper Engine; it can play existing local videos from any source. Codec support depends on Qt Multimedia.

Install the included Plasma 6 plugin once:

```fish
sudo pacman -S --needed qt6-multimedia qt6-multimedia-ffmpeg qt6-tools
bash install.sh
```

In the app, select **Use finished MP4 as wallpaper on all KDE desktops** to apply a successful export. This is off by default and explicitly changes the wallpaper on all Plasma desktop containments. Existing clock, date and calendar settings are retained. It requires an installed plugin, a running Plasma session and qdbus6, a compatible qdbus, or gdbus. It uses Plasma's D-Bus scripting API rather than editing configuration files behind Plasma.

CLI example, usable in fish:

```fish
bash launch.sh /path/to/wallpaper --seconds 30 --width 2560 --height 1440 --apply-kde
```

An application failure leaves the exported MP4 saved and reports that desktop application could not be confirmed. The plugin plays videos silently. It does not restore the previous wallpaper automatically.

For manual selection: right-click the desktop → Configure Desktop and Wallpaper → **Plasma Video Wallpaper**, enter the permanent absolute MP4 path, and Apply. Configure each monitor separately. Log out/in if the plugin is not listed. Plugin ID `org.talal.moonlive` is retained for upgrades. It independently plays local videos supported by Qt Multimedia (including MP4 and supported WebM/MKV files) and adds a live system clock, weekday/date and optional current-month calendar, with Monday first and today highlighted. MP4 exports alone have no live clock; clocks baked into video pixels cannot be removed by this plugin.

## Supported inputs

| Input | Backend | Limits |
| --- | --- | --- |
| Video projects, MP4/WebM/MKV/MOV/AVI/GIF/M4V | FFmpeg | Loops to the chosen duration; optional source audio is encoded to AAC. |
| PNG/JPEG/WebP/BMP | FFmpeg | Static video with aspect-preserving scaling and padding. |
| Extracted web projects, HTML or folders with index.html | Headless Chromium | Timers/canvas and CSS/Web Animations are stepped; embedded videos are seeked. Audio is omitted and reactive input is silence. Browser APIs/codecs/WebGL/native integrations may differ. |
| Supported scene projects | linux-wallpaperengine | Hidden Xvfb or explicitly selected visible XWayland capture; compatibility depends on the renderer. |
| Moon Workshop 3453730450 | Custom headless OpenGL renderer | Requires original scene.pkg; adapted lighting/motion, not a faithful implementation of every original effect. |
| Windows application wallpapers | Unsupported | Require their Windows program/runtime. |

Web projects require an extracted HTML entrypoint and assets. Project defaults are supplied to `applyUserProperties`; external content, iframes, advanced Wallpaper Engine APIs and audio-driven behavior may differ. The **Hide original clock** option only sets a property named `clock` for web/general scene projects that expose it; otherwise it reports the limitation. It cannot erase clock pixels from an existing video. The Moon renderer omits the original clock.

## Shared controls and filenames

Resolution presets (1080p, 1440p, 4K), custom even dimensions, FPS (1–120), duration, CRF (0–51), source-folder selection and Steam discovery apply across supported inputs. Supersampling 2 renders scene/web/Moon at twice the output width and height, then downsamples with Lanczos. This uses four times as many pixels and costs more time and memory. Video/images use high-quality resampling without inventing source detail. Moon additionally uses 4× MSAA by default, falling back to supported sample counts with a log message.

Automatic naming defaults to `~/Videos/WallpaperExports`:

```text
Wallpaper_Title_3840x2160_60fps_30s.mp4
Wallpaper_Title_3840x2160_60fps_30s_ss2.mp4
Wallpaper_Title_3840x2160_60fps_30s_2.mp4
```

Names use the project title or source filename, preserve Unicode, clean invalid characters and number collisions. Automatic naming never overwrites existing files. GUI exports always use the selected wallpaper library folder, including manual file names. The folder is displayed in the export tab and saved for subsequent GUI and default CLI exports. Explicit CLI output paths and `--output-dir` remain available. Disable automatic naming for a custom output path. CLI can omit the output filename or supply `--output-dir`; explicit output paths can use `--overwrite`. MP4 outputs are staged on the destination filesystem and published after successful encoding. Cancel removes partial staged files.

```fish
bash launch.sh /path/to/project --output-dir "$HOME/Videos/WallpaperExports" --supersample 2
bash launch.sh /path/to/image.png /path/to/output.mp4 --seconds 10 --fps 30
```

## Export your library to the KDE gallery

The converter and KDE plugin are separate components. The plugin can be installed on its own from `plugin/` using `bash install.sh`; the converter is needed only to create videos from wallpaper projects.

In the converter, choose an export folder (default `~/Videos/WallpaperExports`), refresh the Steam library and click **Export all installed wallpapers**. This exports all discovered projects, including ones hidden by the search filter, one at a time using your current quality settings. Unsupported or failed wallpapers are reported and the remaining projects continue. Existing files are preserved with numbered filenames. Cancel stops the batch. There is no automatic download of wallpaper subscriptions.

CLI equivalent:

```fish
bash launch.sh --export-library --output-dir "$HOME/Videos/WallpaperExports"
```

Add `--steam-folder /path/to/SteamLibrary` for another library. Video exports include a sidecar `filename.mp4.jpg` thumbnail; thumbnail failures do not discard a successful MP4. Each batch writes an `export-report-*.json` listing successful files, failures and unprocessed projects. CLI returns failure if any project fails. Repeating a batch creates numbered exports rather than overwriting or skipping previous ones.

Install or upgrade the plugin with `bash install.sh`. In KDE's wallpaper settings choose **Plasma Video Wallpaper**, set **Wallpaper folder** to the same export folder, and click a video thumbnail, then **Apply**. Click **Refresh** after new exports if necessary. Videos without thumbnails remain selectable. You can also enter a video path manually.

These videos appear in the **Plasma Video Wallpaper** page, not KDE's built-in **Image** wallpaper gallery. The plugin does not render Wallpaper Engine scenes directly. All playable videos in the selected folder appear; unsupported scenes that failed export cannot appear as playable videos.

The gallery requires Qt's FolderListModel and QtCore QML modules. On Ubuntu-based Mint, matching packages commonly include `qml6-module-qt-labs-folderlistmodel` and `qml6-module-qtcore`; install them from the Qt source used by your Plasma desktop. Actual gallery rendering remains unverified in this cloud environment.

## Steam discovery and refresh

The library tab finds native and Flatpak Steam, additional drives from `libraryfolders.vdf`, Workshop wallpapers, personal projects and default projects. Search by title/type/Workshop ID; double-click to select. **Add folder** accepts a Steam library, Workshop `431960` folder or individual project. Refresh runs in a worker; auto-sync is enabled every 15 seconds. Assets are selected automatically when found.

**Follow saved active wallpaper** reads Wallpaper Engine's `selectedwallpapers` from local `config.json` while idle. Windows Workshop paths are mapped by ID; with multiple monitors the first matched wallpaper is used. Playlists and missing configs require manual selection. This is saved-configuration discovery, not live Windows/KDE control. Scene user properties are not imported. Steam handles downloads; the app does not subscribe, download or modify Steam/Wallpaper Engine files. Exports start explicitly, and sync does not interrupt them.

Preferences are stored in `~/.config/wallpaper-to-mp4/settings.json`.

## Additional Moon backend

`render_moon.py` reads PKGV0022, MDLV0023 mesh data and the texture types used by Workshop 3453730450. No original assets are bundled. It ports known moon rotation/orbit equations, uses original meshes/textures and adapted shaders. Menus, orbit overlays, typography, audio-reactive effects, particles, mouse interaction and camera intro are omitted. The animations have different periods, so an arbitrary-duration export may jump at the loop boundary.

```fish
.venv/bin/python render_moon.py /path/to/3453730450 /path/to/moon.mp4 --width 2560 --height 1440 --fps 60 --seconds 30 --msaa 4 --supersample 2
```

Standalone options include `--msaa 0|2|4|8`, `--supersample 1|2`, `--camera` (greater than 2), `--start`, `--no-orbits`, `--preview` (PNG output), `--crf` and `--overwrite`. EGL may use a GPU or Mesa software rendering; the selected renderer is logged. Frames use fixed export time rather than screen-recording time. Unsupported package/model layouts fail explicitly. No embedded scene scripts are executed and input assets are not modified.

## Validation and remaining limitations

Run regression tests without installing rendering dependencies:

```fish
python3 -m unittest discover -s tests -v
```

This update verified headless Chromium canvas motion with 2× supersampling and five decoded frames, plus real FFmpeg image/video exports, H.264 dimensions/frame counts, looping, existing-output protection, cancellation cleanup, Unicode collision naming, malformed metadata and non-finite settings. The hidden-scene failure/cleanup path and KDE D-Bus request/response handling have simulated tests. Read-only launcher commands and Bash syntax were checked.

This cloud machine has no Plasma session, linux-wallpaperengine, or original Moon assets. Actual KDE playback/application, hidden and visible general-scene rendering, and Moon rendering require validation on the target desktop. Successful exports from one scene do not establish compatibility with other scenes.

Code is MIT licensed; original wallpaper/assets retain their creators' rights. This project is not affiliated with Wallpaper Engine.

## GitHub Packages

The standalone KDE plugin and converter are also distributed as separate GHCR file packages. See [package instructions](packaging/README.md). They contain installable project files, not a runnable desktop container; release ZIPs remain the recommended download.

The KDE gallery uses larger preview tiles and readable wallpaper titles, with full export filenames available on hover. Export settings and clock options scroll on smaller displays. Applying a video from the converter also sets the plugin’s wallpaper folder to the video’s parent folder. Actual Plasma appearance still needs desktop validation.

Gallery troubleshooting: use **Choose folder…** to select the directory containing exported MP4 files, not the original Steam project folders. The settings show the resolved path and video count. Empty saved settings fall back to `~/Videos/WallpaperExports`; typed `~/`, quoted paths and file URLs are accepted. Folder paths with `#` or `%` are handled through a Qt FolderListModel escaping workaround. The folder picker additionally requires QtQuick.Dialogs (on Mint, matching package `qml6-module-qtquick-dialogs`).
