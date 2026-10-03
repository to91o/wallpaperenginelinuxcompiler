"""Render local HTML wallpapers with Chromium and encode frames with FFmpeg."""
from datetime import datetime, timedelta, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
from urllib.parse import quote

from platform_support import package_hint
from playwright.sync_api import sync_playwright, Error as BrowserError


class ProjectHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        resolved = Path(super().translate_path(path)).resolve()
        root = Path(self.directory).resolve()
        return str(resolved if resolved.is_relative_to(root) else root / '.blocked')

    def list_directory(self, path):
        self.send_error(403)
        return None

    def log_message(self, *args):
        pass


STEP_ANIMATIONS = """time => {
    window.__exportAnimations ||= new Map();
    for (const a of document.getAnimations()) {
        if (!window.__exportAnimations.has(a)) {
            window.__exportAnimations.set(a, {time, offset:Number(a.currentTime || 0)});
            a.pause();
        }
        const base = window.__exportAnimations.get(a);
        a.currentTime = base.offset + time - base.time;
    }
}"""


def render_web(entry, output, seconds, fps, width, height, crf, warmup,
               overwrite, supersample, log, cancel, hide_clock=False):
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise RuntimeError('Missing ffmpeg. ' + package_hint('ffmpeg'))
    root = entry.parent
    # For nested HTML entrypoints, serve the complete project, including sibling assets.
    for candidate in (entry.parent, *entry.parents):
        if (candidate / 'project.json').is_file():
            root = candidate
            break
    properties = {}
    if (root / 'project.json').is_file():
        data = json.loads((root / 'project.json').read_text(encoding='utf-8-sig'))
        properties = data.get('general', {}).get('properties', {})
    if hide_clock:
        if 'clock' in properties:properties['clock']={**properties['clock'],'value':False}
        else:log("This web project has no 'clock' property; its original clock cannot be hidden automatically.")
    server = ThreadingHTTPServer(('127.0.0.1', 0),
        lambda *a, **kw: ProjectHandler(*a, directory=str(root), **kw))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, staging = tempfile.mkstemp(prefix='.web-wallpaper-', suffix='.mp4', dir=output.parent)
    os.close(fd)
    process = None
    try:
        with tempfile.TemporaryFile(mode='w+b') as errors, sync_playwright() as pw:
            executable = shutil.which('chromium') or shutil.which('chromium-browser')
            launch = {'headless':True, 'args':['--autoplay-policy=no-user-gesture-required']}
            if executable:launch['executable_path'] = executable
            try:
                browser = pw.chromium.launch(**launch)
            except BrowserError as e:
                raise RuntimeError('Chromium could not start. Install a compatible Chromium, or run .venv/bin/python -m playwright install chromium.\n' + str(e)) from e
            try:
                page = browser.new_page(viewport={'width':width, 'height':height},
                                        device_scale_factor=supersample)
                now = datetime.now(timezone.utc)
                page.clock.install(time=now)
                page.clock.pause_at(now + timedelta(seconds=1))
                page.add_init_script('window.wallpaperRegisterAudioListener = callback => {window.__exportAudio = callback;};')
                failures = []
                page.on('pageerror', lambda e: failures.append(str(e)))
                url = f'http://127.0.0.1:{server.server_port}/' + quote(entry.relative_to(root).as_posix())
                page.goto(url, wait_until='load', timeout=30000)
                page.evaluate('p => window.wallpaperPropertyListener?.applyUserProperties?.(p)',properties)
                page.evaluate('fps => window.wallpaperPropertyListener?.applyGeneralProperties?.({fps, isPaused:false})',fps)
                page.clock.run_for(round(warmup*1000))
                # Pause CSS/Web Animations and advance their timelines alongside JS timers.
                page.evaluate(STEP_ANIMATIONS,0)
                page.evaluate('document.querySelectorAll("video,audio").forEach(v=>v.pause())')
                log('Web: rendering HTML with Chromium. Audio is omitted; audio-reactive input is silence.')
                command = [ffmpeg,'-v','error','-y','-f','image2pipe','-framerate',str(fps),
                           '-c:v','png','-i','pipe:0','-vf',f'scale={width}:{height}:flags=lanczos,setsar=1',
                           '-an','-c:v','libx264','-preset','veryfast','-crf',str(crf),
                           '-pix_fmt','yuv420p','-movflags','+faststart',staging]
                process = subprocess.Popen(command,stdin=subprocess.PIPE,stderr=errors)
                frames = max(1,round(seconds*fps))
                previous = 0
                for i in range(frames):
                    if cancel and cancel.is_set():raise RuntimeError('Cancelled.')
                    milliseconds = round(i*1000/fps)
                    if milliseconds>previous:page.clock.run_for(milliseconds-previous)
                    previous=milliseconds
                    page.evaluate(STEP_ANIMATIONS,milliseconds)
                    page.evaluate('window.__exportAudio?.(Array(128).fill(0))')
                    # Seek embedded media to the same export time rather than wall time.
                    page.evaluate('''time => {
                        document.querySelectorAll('video').forEach(v => {
                            if (!Number.isFinite(v.duration) || v.duration<=0) return;
                            const target=v.loop ? time % v.duration : Math.min(time,v.duration-0.001);
                            if (Math.abs(v.currentTime-target)<0.001) return;
                            v.currentTime=target;
                        });
                    }''',i/fps)
                    page.wait_for_function('!Array.from(document.querySelectorAll("video")).some(v=>v.seeking)',
                                           polling=50,timeout=5000)
                    try:process.stdin.write(page.screenshot(type='png',timeout=30000))
                    except BrokenPipeError:
                        errors.seek(0);raise RuntimeError('FFmpeg failed: '+errors.read().decode(errors='replace')[-4000:])
                    if i%fps==0:log(f'Web: {i}/{frames} frames')
                process.stdin.close()
                if process.wait():
                    errors.seek(0);raise RuntimeError('FFmpeg failed: '+errors.read().decode(errors='replace')[-4000:])
                if failures:log('Web script errors (some Wallpaper Engine APIs may be unsupported): '+ '; '.join(failures[:3]))
                if overwrite:os.replace(staging,output)
                else:os.link(staging,output);os.unlink(staging)
                log(f'Saved: {output}')
            finally:
                browser.close()
    except BrowserError as e:
        raise RuntimeError('Web rendering failed: '+str(e)) from e
    finally:
        if process and process.poll() is None:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait()
        Path(staging).unlink(missing_ok=True)
        server.shutdown();server.server_close();thread.join(timeout=2)
