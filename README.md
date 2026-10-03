# Wallpaper Engine to MP4 — Linux

**Very early alpha — a vibecoding project.** Features and compatibility are still evolving; expect bugs and rough edges.

Export video, image, extracted web and **supported** Wallpaper Engine scenes to H.264 MP4 on Linux. Designed for Arch Linux and KDE Plasma 6 Wayland. A separate custom renderer handles Moon Workshop 3453730450; shared export controls and the KDE live-clock plugin work across supported wallpapers.

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

## No unwanted preview window

Hidden export is the default. Video/image exports use FFmpeg, web uses headless Chromium, Moon uses headless EGL, and other supported scenes use a private Xvfb display. General-scene capture now waits for the renderer's window, checks its dimensions and captures that window. Missing windows stop the export rather than producing a blank screen capture. The private display does not use your desktop's Wayland display or X authority file, and is cleaned up afterward.

Hidden scene rendering needs Xvfb and xdotool. It may use software rendering and run slowly. Scene capture is real-time; slow rendering may repeat frames. Hidden mode cannot make an unsupported scene compatible.

Visible GPU capture remains available only when explicitly selected with **Show preview window for scene GPU capture** or `--mode gpu`. On KDE Wayland this requires XWayland and a valid `DISPLAY`; it opens an X11 renderer window that must stay visible. If the desktop resizes it, reduce resolution/supersampling or use hidden mode. Failed hidden exports never automatically open a desktop preview.

## Export and apply to KDE

Install the included Plasma 6 plugin once:

```fish
sudo pacman -S --needed qt6-multimedia qt6-multimedia-ffmpeg qt6-tools
bash install.sh
```

In the app, select **Use finished MP4 as wallpaper on all KDE desktops** to apply a successful export. This is off by default and explicitly changes the wallpaper on all Plasma desktop containments. Existing clock, date and calendar settings are retained. It requires an installed plugin, a running Plasma session and qdbus6 (or a compatible qdbus). It uses Plasma's D-Bus scripting API rather than editing configuration files behind Plasma.

CLI example, usable in fish:

```fish
bash launch.sh /path/to/wallpaper --seconds 30 --width 2560 --height 1440 --apply-kde
```

An application failure leaves the exported MP4 saved and reports that desktop application could not be confirmed. The plugin plays videos silently. It does not restore the previous wallpaper automatically.

For manual selection: right-click the desktop → Configure Desktop and Wallpaper → **Video Wallpaper + Live Clock**, enter the permanent absolute MP4 path, and Apply. Configure each monitor separately. Log out/in if the plugin is not listed. Plugin ID `org.talal.moonlive` is retained for upgrades. It accepts any local MP4 and adds a live system clock, weekday/date and optional current-month calendar, with Monday first and today highlighted. MP4 exports alone have no live clock; clocks baked into video pixels cannot be removed by this plugin.

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

Names use the project title or source filename, preserve Unicode, clean invalid characters and number collisions. Automatic naming never overwrites existing files. GUI output-folder and naming preferences are saved. Disable automatic naming for a custom output path. CLI can omit the output filename or supply `--output-dir`; explicit output paths can use `--overwrite`. MP4 outputs are staged on the destination filesystem and published after successful encoding. Cancel removes partial staged files.

```fish
bash launch.sh /path/to/project --output-dir "$HOME/Videos/WallpaperExports" --supersample 2
bash launch.sh /path/to/image.png /path/to/output.mp4 --seconds 10 --fps 30
```

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
