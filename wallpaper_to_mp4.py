#!/usr/bin/env python3
"""Render Wallpaper Engine scenes or transcode video projects to H.264 MP4."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import sys
import signal
import queue
import re
import unicodedata
import math
import importlib.util
from platform_support import find_tool, package_hint

VIDEO = {'.mp4', '.webm', '.mkv', '.mov', '.avi', '.gif', '.m4v'}
IMAGES = {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}

def use_local_environment():
    """Use this package's environment even when launched with system python3."""
    venv = Path(__file__).resolve().parent / '.venv'
    python = venv / 'bin' / 'python'
    if Path(sys.prefix).resolve() == venv.resolve():return
    if any(flag in sys.argv for flag in ('--help', '-h', '--list-wallpapers', '--doctor')):return
    ready = python.is_file() and subprocess.run(
        [str(python),'-c','import lz4.block, moderngl, numpy, PIL, playwright.sync_api'],
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
    if not ready:
        bash=shutil.which('bash')
        if not bash:raise SystemExit('Run setup.sh with Bash to install this app environment.')
        print('Setting up the app Python environment…',flush=True)
        if subprocess.run([bash,str(venv.parent/'setup.sh')]).returncode:
            raise SystemExit('Setup failed. See the installation message above.')
    if python.is_file() and Path(sys.prefix).resolve() != venv.resolve():
        os.execv(str(python), [str(python), str(Path(__file__).resolve()), *sys.argv[1:]])

class ConversionError(Exception):
    pass

def read_project(path):
    """Validate metadata before any backend consumes it."""
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except (ValueError, OSError) as e:
        raise ConversionError(f'Cannot read project.json: {e}') from e
    if not isinstance(data, dict):
        raise ConversionError('project.json must contain a JSON object.')
    for field in ('type', 'file'):
        if field in data and not isinstance(data[field], str):
            raise ConversionError(f'project.json field {field!r} must be a string.')
    general = data.get('general', {})
    if not isinstance(general, dict) or not isinstance(general.get('properties', {}), dict):
        raise ConversionError('project.json general/properties must contain JSON objects.')
    if any(not isinstance(value, dict) for value in general.get('properties', {}).values()):
        raise ConversionError('Each project user property must contain a JSON object.')
    return data


def dependency_report():
    """Report capabilities without installing packages or opening a display."""
    commands = {name: shutil.which(name) is not None for name in
                ('ffmpeg', 'ffprobe', 'chromium', 'chromium-browser',
                 'linux-wallpaperengine', 'Xvfb', 'xdotool', 'kpackagetool6', 'qdbus6', 'qdbus', 'gdbus')}
    modules = {name: importlib.util.find_spec(name) is not None for name in
               ('tkinter', 'playwright', 'moderngl', 'numpy', 'PIL', 'lz4')}
    return {'python': sys.executable, 'commands': commands, 'python_modules': modules,
            'kde_tools': {name: find_tool(name) for name in ('qdbus6', 'kpackagetool6')},
            'desktop': {name: bool(os.environ.get(name)) for name in
                        ('DISPLAY', 'WAYLAND_DISPLAY')},
            'requirements': {
                'video_image': ['ffmpeg'],
                'web': ['ffmpeg', 'playwright', 'system Chromium or Playwright Chromium'],
                'scene_hidden': ['ffmpeg', 'linux-wallpaperengine', 'Xvfb', 'xdotool'],
                'scene_visible': ['ffmpeg', 'linux-wallpaperengine', 'xdotool', 'DISPLAY (XWayland on KDE Wayland)'],
                'moon': ['ffmpeg', 'moderngl', 'numpy', 'PIL', 'lz4', 'working EGL driver', 'original Moon assets'],
                'gui': ['tkinter', 'desktop display'],
                'plugin': ['Plasma 6', 'kpackagetool6', 'Qt 6 Multimedia FFmpeg backend']},
            'note': 'Presence checks only; scene compatibility, browser/EGL startup and Plasma playback require runtime validation.'}


def apply_kde_wallpaper(output, log=print):
    """Apply an exported MP4 to Plasma desktops only when explicitly requested."""
    output = Path(output).expanduser().resolve()
    if not output.is_file() or output.suffix.lower() != '.mp4':
        raise ConversionError('KDE wallpaper needs an existing MP4 file.')
    package_tool = require('kpackagetool6')
    plugin = 'org.talal.moonlive'
    try:
        installed = subprocess.run([package_tool, '--type', 'Plasma/Wallpaper', '--show', plugin],
                                   capture_output=True, text=True, timeout=15)
    except subprocess.TimeoutExpired as e:
        raise ConversionError('KDE plugin lookup timed out. The exported MP4 is saved.') from e
    if installed.returncode:
        raise ConversionError('Install the included KDE plugin first: bash install.sh. The exported MP4 is saved.')
    dbus = find_tool('qdbus6')
    gdbus = shutil.which('gdbus') if not dbus else None
    if not dbus and not gdbus:
        raise ConversionError('KDE integration needs qdbus6 or gdbus (Mint package libglib2.0-bin). The exported MP4 is saved.')
    # JSON escaping preserves quotes, newlines and Unicode in filenames as JS strings.
    script = 'print((function() { try { var ds = desktops(); if (!ds.length) throw new Error("No Plasma desktops found");' + \
        'for (var i=0; i<ds.length; i++) { var d=ds[i]; d.wallpaperPlugin=' + json.dumps(plugin) + \
        '; d.currentConfigGroup=["Wallpaper",' + json.dumps(plugin) + ',"General"];' + \
        'd.writeConfig("VideoFile",' + json.dumps(str(output)) + '); }' + \
        'return JSON.stringify({ok:true, desktops:ds.length});' + \
        '} catch(e) { return JSON.stringify({ok:false, error:String(e)}); } })());'
    try:
        command = ([dbus, 'org.kde.plasmashell', '/PlasmaShell',
                    'org.kde.PlasmaShell.evaluateScript', script] if dbus else
                   [gdbus, 'call', '--session', '--dest', 'org.kde.plasmashell',
                    '--object-path', '/PlasmaShell', '--method',
                    'org.kde.PlasmaShell.evaluateScript', script])
        result = subprocess.run(command, capture_output=True, text=True, timeout=15)
    except subprocess.TimeoutExpired as e:
        raise ConversionError('Plasma did not respond. The MP4 is saved; desktop application could not be confirmed.') from e
    try:
        text = result.stdout
        if gdbus:
            # gdbus serializes the returned string as a GVariant tuple.
            import ast
            values = ast.literal_eval(text.strip())
            if not isinstance(values, tuple) or len(values) != 1 or not isinstance(values[0], str):
                raise ValueError('Unexpected Plasma D-Bus response')
            text = values[0]
        response = json.loads(text)
    except (ValueError, SyntaxError):
        response = {}
    if result.returncode or not isinstance(response, dict) or response.get('ok') is not True:
        detail = response.get('error', '') if isinstance(response, dict) else ''
        raise ConversionError('Plasma wallpaper application could not be confirmed: ' +
                              str(detail or result.stderr or result.stdout).strip()[-2000:] +
                              '. The exported MP4 is saved.')
    log(f'Applied video wallpaper to {response.get("desktops")} Plasma desktops. Clock settings are retained.')



def automatic_output(source, directory=None, width=1920, height=1080, fps=30, seconds=30, supersample=1):
    """Propose a readable, safe, unused filename without creating or overwriting files."""
    path=Path(str(source).strip().strip('\"\'')).expanduser()
    title=path.name if path.is_dir() else path.stem
    root=path if path.is_dir() else path.parent
    for candidate in (root,*root.parents):
        project=candidate/'project.json'
        if project.is_file():
            try:title=str(json.loads(project.read_text(encoding='utf-8-sig')).get('title') or title)
            except (OSError,ValueError,AttributeError):pass
            break
    title=''.join('_' if c in '/\\:*?\"<>|' or unicodedata.category(c).startswith('C') else c for c in title)
    title=re.sub(r'[\s_]+','_',title).strip('._ ')
    title=title.encode('utf-8')[:100].decode('utf-8',errors='ignore').rstrip('._') or 'wallpaper'
    stem=f'{title}_{width}x{height}_{fps}fps_{seconds:g}s' + ('_ss2' if supersample==2 else '')
    folder=Path(directory or Path.home()/'Videos/WallpaperExports').expanduser().resolve()
    result=folder/(stem+'.mp4');number=2
    while result.exists() or result.is_symlink():
        result=folder/f'{stem}_{number}.mp4';number+=1
    return result

def require(name):
    found = find_tool(name)
    if not found:
        raise ConversionError(f'Missing {name}. {package_hint("kde" if name == "kpackagetool6" else name)}')
    return found

def resolve(source):
    source = Path(str(source).strip().strip('\"\'')).expanduser().resolve()
    if not source.exists():
        raise ConversionError(f'Input does not exist: {source}')
    if source.is_file() and source.suffix.lower() in VIDEO:
        return 'video', source
    if source.is_file() and source.suffix.lower() in IMAGES:
        return 'image', source
    if source.is_file() and source.suffix.lower() in {'.html','.htm'}:
        return 'web', source
    root = source if source.is_dir() else source.parent
    project = root / 'project.json'
    if project.exists():
        data = read_project(project)
        kind = str(data.get('type', '')).lower()
        if kind == 'video':
            media = (root / data.get('file', '')).resolve()
            if not media.is_relative_to(root) or not media.is_file() or media.suffix.lower() not in VIDEO:
                raise ConversionError('Video project has an invalid or missing media file.')
            return 'video', media
        if kind == 'web':
            entry = (root / data.get('file', 'index.html')).resolve()
            if not entry.is_relative_to(root) or not entry.is_file() or entry.suffix.lower() not in {'.html','.htm'}:
                raise ConversionError('Web project has an invalid or missing HTML entry file. Select its complete extracted folder.')
            return 'web', entry
        if kind == 'application':
            raise ConversionError('Windows application wallpapers cannot be rendered by this Linux converter. Use a video, web, or supported scene project.')
        if kind == 'scene':
            return 'scene', root
    if source.suffix.lower() == '.pkg' or (root / 'scene.pkg').exists() or (root / 'scene.json').exists():
        # The renderer takes the containing project folder, including project.json.
        if not project.exists():
            raise ConversionError('Scene input needs its original project.json. Select the complete Workshop folder, not an isolated .pkg.')
        return 'scene', root
    if source.is_dir() and (source / 'index.html').is_file():
        return 'web', source / 'index.html'
    raise ConversionError('Select a video, image, HTML file, project.json, scene.pkg, or complete Wallpaper Engine project folder.')

def stop(process):
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()

def convert(source, output, seconds=30, fps=30, width=1920, height=1080,
            crf=18, assets=None, warmup=3, overwrite=False, log=print, cancel=None, mode="isolated", hide_clock=False,
            msaa=4, supersample=1):
    if not math.isfinite(seconds) or seconds <= 0 or not 1 <= fps <= 120 or width < 2 or height < 2 or width % 2 or height % 2:
        raise ConversionError('Duration must be positive; FPS 1–120; dimensions must be positive even numbers.')
    if not 0 <= crf <= 51 or not math.isfinite(warmup) or warmup < 0:
        raise ConversionError('CRF must be 0–51 and warmup cannot be negative.')
    if msaa not in (0,2,4,8) or supersample not in (1,2):
        raise ConversionError('MSAA must be 0, 2, 4, or 8; supersampling must be 1 or 2.')
    kind, target = resolve(source)
    output = Path(output).expanduser().resolve()
    if output.suffix.lower() != '.mp4':
        raise ConversionError('Output filename must end in .mp4.')
    if output.exists() and not overwrite:
        raise ConversionError('Output already exists. Choose another name or enable overwrite.')
    if output == target:
        raise ConversionError('Input and output must be different files.')
    if kind == 'web':
        try:
            from render_web import render_web
            render_web(target, output, seconds, fps, width, height, crf, warmup,
                       overwrite, supersample, log, cancel, hide_clock=hide_clock)
        except ImportError as e:
            raise ConversionError('Web renderer dependencies are missing. Close the app and run: bash launch.sh') from e
        except (RuntimeError, OSError) as e:
            raise ConversionError(str(e)) from e
        return
    if kind == 'scene':
        project = read_project(target / 'project.json')
        if str(project.get('workshopid', '')) == '3453730450':
            script = Path(__file__).with_name('render_moon.py')
            if not script.is_file():
                raise ConversionError('Moon renderer script is missing from this package.')
            if not (target / 'scene.pkg').is_file():
                raise ConversionError('Moon input folder must contain scene.pkg.')
            log('Moon: rendering original 3D assets with adapted lighting. Clock omitted for live overlay.')
            command = [sys.executable, '-u', str(script), str(target / 'scene.pkg'), str(output),
                       '--seconds', str(seconds), '--fps', str(fps), '--width', str(width),
                       '--height', str(height), '--crf', str(crf),
                       '--msaa', str(msaa), '--supersample', str(supersample)]
            if overwrite: command.append('--overwrite')
            messages = queue.Queue()
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            def reader():
                for line in process.stdout: messages.put(line.rstrip())
            thread = threading.Thread(target=reader, daemon=True); thread.start()
            recent = []
            try:
                while process.poll() is None or not messages.empty():
                    if cancel and cancel.is_set():
                        process.send_signal(signal.SIGINT)
                        raise ConversionError('Cancelled.')
                    try:
                        line = messages.get(timeout=.1)
                        recent.append(line); recent = recent[-20:]; log(line)
                    except queue.Empty: pass
                thread.join(timeout=1)
                while not messages.empty():
                    line = messages.get(); recent.append(line); log(line)
                if process.returncode:
                    raise ConversionError('Moon rendering failed:\n' + '\n'.join(recent[-20:]))
                log(f'Saved: {output}')
                return
            finally:
                if process.poll() is None:
                    process.send_signal(signal.SIGINT)
                    try: process.wait(timeout=5)
                    except subprocess.TimeoutExpired: stop(process)
    ffmpeg = require('ffmpeg')
    render_width, render_height = width*supersample, height*supersample
    renderer = require('linux-wallpaperengine') if kind == 'scene' else None
    if mode not in {'gpu', 'isolated'}:
        raise ConversionError('Mode must be gpu or isolated.')
    if kind == 'scene':require('xdotool')
    xvfb = require('Xvfb') if kind == 'scene' and mode == 'isolated' else None
    if kind == 'scene' and mode == 'gpu':
        require('xdotool')
        if not os.environ.get('DISPLAY'):
            raise ConversionError('GPU mode requires an X11/XWayland DISPLAY. Launch from your desktop terminal.')
    output.parent.mkdir(parents=True, exist_ok=True)
    # Temporary output on the same filesystem enables atomic publication.
    fd, staging = tempfile.mkstemp(prefix='.wallpaper-', suffix='.mp4', dir=output.parent)
    os.close(fd)
    display_proc = render_proc = encode_proc = None
    try:
        with tempfile.TemporaryDirectory(prefix='wallpaper-render-') as work:
            with open(Path(work) / 'renderer.log', 'w+') as render_log:
                if kind in {'video','image'}:
                    inputs = (['-stream_loop', '-1'] if kind=='video' else ['-loop','1','-framerate',str(fps)]) + ['-i',str(target)]
                    audio = ['-map', '0:a?', '-c:a', 'aac', '-b:a', '192k'] if kind=='video' else ['-an']
                else:
                    if mode == 'isolated':
                        log('Rendering scene in a hidden display. No desktop preview window (scene export is silent).')
                        read_fd, write_fd = os.pipe()
                        try:
                            display_proc = subprocess.Popen([xvfb, '-displayfd', str(write_fd), '-screen', '0',
                                f'{render_width}x{render_height}x24', '-nolisten', 'tcp', '+extension', 'GLX'],
                                pass_fds=(write_fd,), stdout=render_log, stderr=render_log)
                        finally:
                            os.close(write_fd)
                        try:
                            import select
                            if not select.select([read_fd], [], [], 15)[0]:
                                raise ConversionError('Xvfb did not start within 15 seconds.')
                            number = os.read(read_fd, 64).decode().strip()
                            if not number.isdigit():
                                raise ConversionError('Xvfb failed to allocate a display.')
                        finally:
                            os.close(read_fd)
                    else:
                        log('Starting desktop GPU window. Keep it visible; do not minimize or resize it.')
                    env = os.environ.copy()
                    env['DISPLAY'] = ':' + number if mode == 'isolated' else os.environ['DISPLAY']
                    env.pop('WAYLAND_DISPLAY', None)
                    if mode == 'isolated':env.pop('XAUTHORITY', None)
                    env['XDG_SESSION_TYPE'] = 'x11'
                    env['GLFW_PLATFORM'] = 'x11'
                    env['SDL_VIDEODRIVER'] = 'x11'
                    command = [renderer, '--window', f'0x0x{render_width}x{render_height}', '--fps', str(fps),
                               '--silent', '--disable-mouse', '--no-fullscreen-pause']
                    if assets:
                        command += ['--assets-dir', str(Path(assets).expanduser().resolve())]
                    if hide_clock:
                        properties=read_project(target/'project.json').get('general',{}).get('properties',{})
                        if 'clock' in properties:command += ['--set-property', 'clock=0']
                        else:log("This scene has no 'clock' property; its original clock cannot be hidden automatically.")
                    command += [str(target)]
                    render_proc = subprocess.Popen(command, env=env, stdout=render_log, stderr=render_log)
                    deadline = time.monotonic() + warmup
                    while time.monotonic() < deadline:
                        if cancel and cancel.is_set():
                            raise ConversionError('Cancelled.')
                        if render_proc.poll() is not None:
                            render_log.flush(); render_log.seek(0)
                            raise ConversionError('Renderer exited:\n' + render_log.read()[-6000:])
                        time.sleep(.1)
                    if kind == 'scene':
                        deadline = time.monotonic() + 15
                        window = None
                        while time.monotonic() < deadline:
                            if cancel and cancel.is_set():
                                raise ConversionError('Cancelled.')
                            if render_proc.poll() is not None:
                                render_log.flush(); render_log.seek(0)
                                raise ConversionError('Renderer exited:\n' + render_log.read()[-6000:])
                            found = subprocess.run(['xdotool', 'search', '--onlyvisible', '--pid', str(render_proc.pid)],
                                                   env=env, capture_output=True, text=True, timeout=3)
                            candidates = found.stdout.split()
                            if candidates:
                                window = candidates[-1]; break
                            time.sleep(.2)
                        if not window:
                            raise ConversionError('No renderer window appeared on the capture display. Export was stopped to avoid saving a blank video. Check linux-wallpaperengine compatibility and assets.')
                        geometry = subprocess.run(['xdotool','getwindowgeometry','--shell',window],
                            env=env,capture_output=True,text=True,timeout=3)
                        dimensions = dict(line.split('=',1) for line in geometry.stdout.splitlines() if '=' in line)
                        if dimensions.get('WIDTH') != str(render_width) or dimensions.get('HEIGHT') != str(render_height):
                            raise ConversionError(f'Render window dimensions do not match the required {render_width}x{render_height}. '
                                'Check renderer support for window sizing; in visible mode, try a lower resolution or hidden mode.')
                        inputs = ['-thread_queue_size', '512', '-f', 'x11grab', '-draw_mouse', '0',
                                  '-framerate', str(fps), '-window_id', window, '-i', env['DISPLAY']]
                    audio = ['-an']
                vf = (f'scale={render_width}:{render_height}:force_original_aspect_ratio=decrease:flags=lanczos,'
                      f'pad={render_width}:{render_height}:(ow-iw)/2:(oh-ih)/2,'
                      f'scale={width}:{height}:flags=lanczos,setsar=1')
                if supersample>1:
                    if kind=='scene':log(f'Supersampling: render at {render_width}x{render_height}, downsample to {width}x{height}.')
                    else:log('High quality resampling enabled. Video/image detail is limited to the original source resolution.')
                command = [ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', *inputs,
                           '-t', str(seconds), '-map', '0:v:0', *audio, '-vf', vf,
                           '-r', str(fps), '-c:v', 'libx264', '-preset', 'veryfast', '-crf', str(crf),
                           '-pix_fmt', 'yuv420p', '-movflags', '+faststart', staging]
                log(f'Exporting {seconds:g}s at {width}×{height}, {fps} FPS…')
                with open(Path(work) / 'ffmpeg.log', 'w+') as encode_log:
                    encode_proc = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=encode_log)
                    while encode_proc.poll() is None:
                        if cancel and cancel.is_set():
                            raise ConversionError('Cancelled.')
                        if render_proc and render_proc.poll() is not None:
                            render_log.flush(); render_log.seek(0)
                            raise ConversionError('Scene renderer stopped:\n' + render_log.read()[-6000:])
                        time.sleep(.1)
                    if encode_proc.returncode:
                        encode_log.seek(0)
                        raise ConversionError('FFmpeg failed:\n' + encode_log.read()[-6000:])
                if output.exists() and not overwrite:
                    raise ConversionError('Output was created by another process; refusing to replace it.')
                if overwrite:
                    os.replace(staging, output)
                else:
                    os.link(staging, output)
                    os.unlink(staging)
                log(f'Saved: {output}')
    finally:
        stop(encode_proc); stop(render_proc); stop(display_proc)
        Path(staging).unlink(missing_ok=True)

def gui():
    import tkinter as tk
    from tkinter import filedialog, ttk, messagebox
    import queue
    try:
        root = tk.Tk()
    except tk.TclError as e:
        raise ConversionError('GUI needs a desktop display. Run from your KDE terminal, or use CLI export arguments.') from e
    root.title('Wallpaper → MP4 — Linux'); root.geometry('840x890')
    notebook = ttk.Notebook(root); notebook.pack(fill='both',expand=True)
    frame = ttk.Frame(notebook, padding=18)
    library_frame = ttk.Frame(notebook,padding=18)
    notebook.add(frame,text='Export'); notebook.add(library_frame,text='Wallpaper Engine library')
    values = {}; entries = {}; browse_buttons = {}
    def field(label, default, browse=None):
        row = ttk.Frame(frame); row.pack(fill='x', pady=4)
        ttk.Label(row, text=label, width=18).pack(side='left')
        var = tk.StringVar(value=default); values[label] = var
        entry=ttk.Entry(row,textvariable=var);entries[label]=entry
        entry.pack(side='left', fill='x', expand=True)
        if browse:
            button=ttk.Button(row,text='Browse',command=lambda: var.set(browse() or var.get()))
            browse_buttons[label]=button;button.pack(side='left',padx=4)
    ttk.Label(frame, text='Wallpaper Engine to MP4', font=('', 18, 'bold')).pack(anchor='w', pady=(0,12))
    field('Input', '', lambda: filedialog.askopenfilename(title='Choose project.json, scene.pkg, HTML, image, or video'))
    ttk.Button(frame, text='Select project folder', command=lambda: values['Input'].set(filedialog.askdirectory() or values['Input'].get())).pack(anchor='e')
    field('Output', str(Path.home() / 'wallpaper.mp4'), lambda: filedialog.asksaveasfilename(defaultextension='.mp4'))
    auto_name=tk.BooleanVar(value=True)
    output_folder=tk.StringVar(value=str(Path.home()/'Videos/WallpaperExports'))
    naming_row=ttk.Frame(frame);naming_row.pack(fill='x',pady=4)
    ttk.Checkbutton(naming_row,text='Automatic file naming',variable=auto_name,
                    command=lambda: (update_filename(),save_preferences())).pack(side='left')
    def choose_output_folder():
        selected=filedialog.askdirectory(title='Choose folder for automatically named exports',initialdir=str(Path.home()))
        if selected:output_folder.set(selected);update_filename();save_preferences()
    ttk.Button(naming_row,text='Choose export folder',command=choose_output_folder).pack(side='left',padx=12)
    for label, default in [('Duration (seconds)','30'), ('FPS','30'), ('Width','1920'), ('Height','1080'), ('CRF (quality)','18')]:
        field(label, default)
    preset_row = ttk.Frame(frame); preset_row.pack(fill='x', pady=4)
    ttk.Label(preset_row, text='Resolution preset', width=18).pack(side='left')
    preset_var = tk.StringVar(value='1080p')
    presets = {'1080p':(1920,1080), '1440p':(2560,1440), '4K':(3840,2160)}
    preset_box = ttk.Combobox(preset_row, textvariable=preset_var, values=list(presets), state='readonly')
    preset_box.pack(side='left')
    def choose_resolution(event=None):
        w,h=presets[preset_var.get()]; values['Width'].set(str(w)); values['Height'].set(str(h))
    preset_box.bind('<<ComboboxSelected>>',choose_resolution)
    ss_var = tk.StringVar(value='1')
    for label,var,choices in [('Supersampling',ss_var,['1','2'])]:
        row = ttk.Frame(frame); row.pack(fill='x', pady=4)
        ttk.Label(row,text=label,width=24).pack(side='left')
        ttk.Combobox(row,textvariable=var,values=choices,state='readonly').pack(side='left')
    ttk.Label(frame,text='2×: scenes/web render at twice the width/height, then downsample. Export takes longer.').pack(anchor='w')
    ttk.Label(frame,text='Video/image sources use Lanczos resampling; their original detail cannot be increased.').pack(anchor='w')
    field('Assets folder', '', filedialog.askdirectory)
    ttk.Label(frame, text='Video/image: FFmpeg • Web: Chromium • Moon: offline 3D • Other scenes: Linux renderer').pack(anchor='w', pady=8)
    ttk.Label(frame, text='Exports run without a desktop preview. Hidden scene rendering may be slower.').pack(anchor='w')
    show_preview = tk.BooleanVar(value=False)
    mode_row = ttk.Frame(frame); mode_row.pack(fill='x', pady=4)
    ttk.Checkbutton(mode_row,text='Show preview window for scene GPU capture (keep visible during export)',
                    variable=show_preview).pack(side='left')
    hide_clock = tk.BooleanVar(value=False)
    ttk.Checkbutton(frame, text="Hide original clock when the project exposes a 'clock' property", variable=hide_clock).pack(anchor='w')
    apply_kde = tk.BooleanVar(value=False)
    ttk.Checkbutton(frame, text='Use finished MP4 as wallpaper on all KDE desktops (requires installed plugin)',
                    variable=apply_kde).pack(anchor='w')
    overwrite = tk.BooleanVar(); ttk.Checkbutton(frame, text='Overwrite existing output', variable=overwrite).pack(anchor='w')
    status = tk.StringVar(value='Ready'); ttk.Label(frame, textvariable=status, wraplength=640).pack(anchor='w', pady=8)
    events = queue.Queue(); cancelled = threading.Event()
    # Scan in a worker so slower Steam drives never block the interface.
    from steam_sync import scan
    preferences = Path.home()/'.config/wallpaper-to-mp4/settings.json'
    try:
        saved=json.loads(preferences.read_text())
    except (OSError,ValueError):saved={}
    extra=list(saved.get('folders',[]))
    auto_name.set(saved.get('auto_name',True))
    output_folder.set(saved.get('output_folder',output_folder.get()))
    auto_sync=tk.BooleanVar(value=saved.get('auto_sync',True))
    follow=tk.BooleanVar(value=saved.get('follow_active',False))
    sync_status=tk.StringVar(value='Looking for Steam libraries…')
    search_var=tk.StringVar()
    projects=[];scan_running=False;last_active=None
    def save_preferences():
        try:
            preferences.parent.mkdir(parents=True,exist_ok=True)
            preferences.write_text(json.dumps({'folders':extra,'auto_sync':auto_sync.get(),'follow_active':follow.get(),
                                              'auto_name':auto_name.get(),'output_folder':output_folder.get()},indent=2))
        except OSError as e:sync_status.set(f'Could not save preferences: {e}')
    ttk.Label(library_frame,text='Installed Wallpaper Engine wallpapers',font=('',17,'bold')).pack(anchor='w')
    ttk.Label(library_frame,text='Finds native Steam, Flatpak Steam, and additional Steam libraries.').pack(anchor='w',pady=8)
    switches=ttk.Frame(library_frame);switches.pack(fill='x')
    ttk.Checkbutton(switches,text='Auto-sync every 15 seconds',variable=auto_sync,command=save_preferences).pack(side='left')
    ttk.Checkbutton(switches,text='Follow saved active wallpaper',variable=follow,command=save_preferences).pack(side='left',padx=12)
    ttk.Label(library_frame,text='Follow updates Input while idle. It does not change your desktop or start exports.').pack(anchor='w',pady=6)
    toolbar=ttk.Frame(library_frame);toolbar.pack(fill='x',pady=6)
    ttk.Label(toolbar,text='Search').pack(side='left')
    ttk.Entry(toolbar,textvariable=search_var).pack(side='left',fill='x',expand=True,padx=8)
    tree=ttk.Treeview(library_frame,columns=('title','type','id'),show='headings',selectmode='browse')
    for key,label,size in [('title','Wallpaper',420),('type','Type',90),('id','Workshop ID',150)]:
        tree.heading(key,text=label);tree.column(key,width=size)
    tree.pack(fill='both',expand=True)
    ttk.Label(library_frame,textvariable=sync_status,wraplength=750).pack(anchor='w',pady=8)
    buttons_library=ttk.Frame(library_frame);buttons_library.pack(fill='x')
    def show_projects(*unused):
        selected=tree.selection()
        tree.delete(*tree.get_children())
        query=search_var.get().casefold()
        for i,item in enumerate(projects):
            if query in (item['title']+' '+item['type']+' '+item['id']).casefold():
                tree.insert('', 'end',iid=str(i),values=(item['title'],item['type'],item['id']))
        if selected and tree.exists(selected[0]):tree.selection_set(selected[0])
    search_var.trace_add('write',show_projects)
    def choose_project(event=None):
        selected=tree.selection()
        if selected:
            follow.set(False);save_preferences()
            values['Input'].set(projects[int(selected[0])]['path'])
            notebook.select(frame)
    tree.bind('<Double-1>',choose_project)
    ttk.Button(buttons_library,text='Use selected wallpaper',command=choose_project).pack(side='left')
    def refresh_library():
        nonlocal scan_running
        if scan_running:return
        scan_running=True
        folders=tuple(extra)
        def scanner():
            try:events.put(('library',scan(folders)))
            except Exception as e:events.put(('library_error',str(e)))
        threading.Thread(target=scanner,daemon=True).start()
    ttk.Button(buttons_library,text='Refresh',command=refresh_library).pack(side='left',padx=8)
    def add_folder():
        selected=filedialog.askdirectory(title='Select Steam library, Workshop 431960 folder, or project folder')
        if selected and selected not in extra:
            extra.append(selected);save_preferences();refresh_library()
    ttk.Button(buttons_library,text='Add folder',command=add_folder).pack(side='left')
    def periodic_sync():
        if auto_sync.get():refresh_library()
        root.after(15000,periodic_sync)
    pending_name=None
    def update_filename():
        entries['Output'].configure(state='readonly' if auto_name.get() else 'normal')
        browse_buttons['Output'].configure(state='disabled' if auto_name.get() else 'normal')
        if not auto_name.get():return
        try:
            path=automatic_output(values['Input'].get(),output_folder.get(),int(values['Width'].get()),
                int(values['Height'].get()),int(values['FPS'].get()),float(values['Duration (seconds)'].get()),int(ss_var.get()))
            values['Output'].set(str(path))
        except (ValueError,OSError):pass
    def schedule_filename(*unused):
        nonlocal pending_name
        if pending_name is not None:root.after_cancel(pending_name)
        pending_name=root.after(300,refresh_filename)
    def refresh_filename():
        nonlocal pending_name
        pending_name=None
        if run.instate(['!disabled']):update_filename()
    for name in ['Input','Width','Height','FPS','Duration (seconds)']:
        values[name].trace_add('write',schedule_filename)
    ss_var.trace_add('write',schedule_filename)
    def start():
        if auto_name.get():update_filename()
        try:
            kwargs = dict(source=values['Input'].get(), output=values['Output'].get(),
                seconds=float(values['Duration (seconds)'].get()), fps=int(values['FPS'].get()),
                width=int(values['Width'].get()), height=int(values['Height'].get()),
                crf=int(values['CRF (quality)'].get()), assets=values['Assets folder'].get() or None,
                overwrite=False if auto_name.get() else overwrite.get(), log=lambda s: events.put(('status',s)), cancel=cancelled,
                mode='gpu' if show_preview.get() else 'isolated', hide_clock=hide_clock.get(),
                msaa=4, supersample=int(ss_var.get()))
        except ValueError:
            messagebox.showerror('Invalid settings', 'Enter valid numeric settings.'); return
        apply_after_export = apply_kde.get()
        cancelled.clear(); run.configure(state='disabled'); cancel_button.configure(state='normal')
        def worker():
            try:
                convert(**kwargs)
                if apply_after_export and not cancelled.is_set():
                    apply_kde_wallpaper(kwargs['output'], kwargs['log'])
            except Exception as e:
                events.put(('error',str(e)))
            finally:
                events.put(('done',None))
        threading.Thread(target=worker, daemon=False).start()
    buttons = ttk.Frame(frame); buttons.pack(fill='x')
    run = ttk.Button(buttons, text='Export MP4', command=start); run.pack(side='left')
    cancel_button = ttk.Button(buttons, text='Cancel', command=cancelled.set, state='disabled'); cancel_button.pack(side='left', padx=8)
    def poll():
        nonlocal projects,scan_running,last_active
        while not events.empty():
            kind, value = events.get()
            if kind == 'status': status.set(value)
            elif kind == 'error': status.set(value); messagebox.showerror('Export failed',value)
            elif kind == 'library':
                scan_running=False;projects=value['projects'];show_projects()
                active=value['active']
                text=f'{len(projects)} wallpapers found in {len(value["libraries"])} Steam libraries.'
                if not active:text+=' No saved active wallpaper found.'
                elif len(active)>1:text+=' Multiple monitors found; Follow uses the first saved wallpaper.'
                if value['warnings']:text+=' '+value['warnings'][0]
                sync_status.set(text)
                if value['assets'] and not values['Assets folder'].get():values['Assets folder'].set(value['assets'][0])
                if follow.get() and active and run.instate(['!disabled']):
                    if active[0]!=last_active or values['Input'].get()!=active[0]:values['Input'].set(active[0])
                    last_active=active[0]
            elif kind == 'library_error':scan_running=False;sync_status.set(value)
            else: run.configure(state='normal'); cancel_button.configure(state='disabled'); update_filename()
        root.after(150,poll)
    def close():
        cancelled.set()
        root.destroy()
    root.protocol('WM_DELETE_WINDOW',close); update_filename(); refresh_library(); periodic_sync(); poll(); root.mainloop()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', nargs='?'); parser.add_argument('output', nargs='?')
    parser.add_argument('--hide-clock', action='store_true', help="Disable the 'clock' property when exposed by a scene/web project")
    parser.add_argument('--mode', choices=['gpu', 'isolated'], default='isolated',
                        help='Scene capture: isolated hides the preview (default); gpu opens a visible window')
    parser.add_argument('--gui', action='store_true')
    parser.add_argument('--apply-kde', action='store_true', help='After export, apply MP4 to all Plasma desktops using the installed plugin')
    parser.add_argument('--doctor', action='store_true', help='Report dependency presence as JSON without setup or a GUI')
    parser.add_argument('--list-wallpapers',action='store_true',help='List automatically discovered installed wallpapers as JSON')
    parser.add_argument('--steam-folder',action='append',default=[],help='Additional Steam library or wallpaper folder')
    parser.add_argument('--output-dir',help='Export folder for automatic naming when output filename is omitted')
    parser.add_argument('--seconds', type=float, default=30)
    parser.add_argument('--fps', type=int, default=30)
    parser.add_argument('--width', type=int, default=1920); parser.add_argument('--height', type=int, default=1080)
    parser.add_argument('--crf', type=int, default=18); parser.add_argument('--warmup', type=float, default=3)
    parser.add_argument('--msaa', type=int, choices=[0,2,4,8], default=4, help='Moon renderer edge antialiasing (default: 4)')
    parser.add_argument('--supersample', type=int, choices=[1,2], default=1, help='Scene/web render multiplier; video/image resampling factor (default: 1)')
    parser.add_argument('--assets'); parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    if args.doctor:
        print(json.dumps(dependency_report(), indent=2)); return
    if args.list_wallpapers:
        from steam_sync import scan
        print(json.dumps(scan(args.steam_folder),indent=2));return
    if args.gui or not args.input:
        try:
            gui()
        except ImportError:
            parser.exit(1, f'Error: GUI needs Tk. {package_hint("tk")}\n')
        except ConversionError as e:
            parser.exit(1, f'Error: {e}\n')
        return
    if args.output and args.output_dir:parser.error('Use an output filename or --output-dir, not both.')
    if not args.output:
        args.output=str(automatic_output(args.input,args.output_dir,args.width,args.height,args.fps,args.seconds,args.supersample))
        args.overwrite=False
    try:
        convert(args.input, args.output, args.seconds, args.fps, args.width, args.height,
                args.crf, args.assets, args.warmup, args.overwrite, mode=args.mode, hide_clock=args.hide_clock,
                msaa=args.msaa, supersample=args.supersample)
        if args.apply_kde:apply_kde_wallpaper(args.output)
    except (ConversionError, OSError, KeyboardInterrupt) as e:
        parser.exit(1, f'Error: {e}\n')

if __name__ == '__main__':
    use_local_environment()
    main()
