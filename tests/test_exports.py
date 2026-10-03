import json
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

import wallpaper_to_mp4 as app


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def project(self, data):
        path = self.root / 'project.json'
        path.write_text(json.dumps(data))
        return path

    @unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg required')
    def test_batch_exports_supported_projects_and_reports_failures(self):
        projects = []
        for name, kind in [('one', 'video'), ('unsupported', 'application'), ('two', 'video')]:
            folder = self.root / name; folder.mkdir()
            (folder / 'project.json').write_text(json.dumps({'title': name, 'type': kind, 'file': 'clip.mp4'}))
            if kind == 'video':
                subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=red:s=32x32:r=10',
                                '-t', '0.2', '-pix_fmt', 'yuv420p', str(folder / 'clip.mp4')], check=True)
            projects.append({'title': name, 'path': str(folder)})
        out = self.root / 'gallery'
        report = app.export_library(projects, out, seconds=.2, fps=10, width=32, height=32, log=lambda _: None)
        self.assertEqual(len(report['exported']), 2)
        self.assertEqual(len(report['failed']), 1)
        self.assertEqual(report['unprocessed'], 0)
        self.assertIn('Windows application', report['failed'][0]['error'])
        for exported in report['exported']:
            self.assertTrue(Path(exported['output']).is_file())
            self.assertTrue(Path(exported['output'] + '.jpg').stat().st_size > 0)
        self.assertEqual(json.loads(next(out.glob('export-report-*.json')).read_text()), report)
        repeat = app.export_library(projects, out, seconds=.2, fps=10, width=32, height=32, log=lambda _: None)
        self.assertEqual([x['output'] for x in report['exported']], [x['output'] for x in repeat['exported']])
        self.assertEqual(len(list(out.glob('*.mp4'))), 2)
        cancel = threading.Event(); cancel.set()
        cancelled = app.export_library(projects, out, cancel=cancel, log=lambda _: None)
        self.assertTrue(cancelled['cancelled'])
        self.assertEqual(cancelled['unprocessed'], 3)
        self.assertEqual(len(list(out.glob('*.mp4'))), 2)

    def test_saved_folder_is_shared_by_cli_defaults(self):
        home = self.root / 'home'
        config = home / '.config/wallpaper-to-mp4'
        config.mkdir(parents=True)
        target = self.root / 'shared-library'
        (config / 'settings.json').write_text(json.dumps({'output_folder': str(target)}))
        with patch.object(app.Path, 'home', return_value=home):
            self.assertEqual(app.library_directory(), target)
            self.assertEqual(app.automatic_output(self.root).parent, target)

    def test_gui_manual_filename_stays_in_library(self):
        target = self.root / 'library'
        self.assertEqual(app.library_output('custom.mp4', target), target / 'custom.mp4')
        for name in ('../outside.mp4', '/tmp/outside.mp4', '', 'sub/video.mp4'):
            with self.subTest(name=name), self.assertRaises(app.ConversionError):
                app.library_output(name, target)

    def test_duplicate_archiving_preserves_different_videos_and_sidecars(self):
        (self.root / 'one.mp4').write_bytes(b'same video')
        (self.root / 'one_2.mp4').write_bytes(b'same video')
        (self.root / 'two.mp4').write_bytes(b'different video')
        (self.root / 'one_2.mp4.jpg').write_bytes(b'preview')
        self.assertEqual(app.deduplicate_library(self.root, log=lambda _: None), 1)
        self.assertTrue((self.root / 'one.mp4').exists())
        self.assertTrue((self.root / 'two.mp4').exists())
        self.assertFalse((self.root / 'one_2.mp4').exists())
        self.assertEqual((self.root / '.duplicate-exports/one_2.mp4').read_bytes(), b'same video')
        self.assertEqual((self.root / '.duplicate-exports/one_2.mp4.jpg').read_bytes(), b'preview')
        self.assertEqual(app.deduplicate_library(self.root, log=lambda _: None), 0)

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
    def test_preview_samples_after_black_intro(self):
        video = self.root / 'intro.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=black:s=32x32:r=10:d=0.5',
                        '-f', 'lavfi', '-i', 'color=red:s=32x32:r=10:d=0.5',
                        '-filter_complex', '[0:v][1:v]concat=n=2:v=1:a=0', '-pix_fmt', 'yuv420p',
                        str(video)], check=True)
        app.refresh_previews(self.root, log=lambda _: None)
        thumbnail = Path(str(video) + '.jpg')
        self.assertTrue(thumbnail.is_file())
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(thumbnail), '-f', 'rawvideo',
                              '-pix_fmt', 'rgb24', 'pipe:1'], check=True, capture_output=True).stdout
        self.assertGreater(sum(raw[0::3]) / len(raw[0::3]), 150)
        self.assertLess(sum(raw[1::3]) / len(raw[1::3]), 50)

    def test_invalid_metadata_is_actionable(self):
        for data in ([], None, {'type': 'video', 'file': 3},
                     {'type': 'scene', 'general': None},
                     {'type': 'web', 'general': {'properties': {'clock': False}}}):
            with self.subTest(data=data), self.assertRaises(app.ConversionError):
                app.resolve(self.project(data))

    def test_project_paths_cannot_escape(self):
        outside = self.root.parent / 'outside-test.mp4'
        self.project({'type': 'video', 'file': str(outside)})
        with self.assertRaisesRegex(app.ConversionError, 'invalid or missing'):
            app.resolve(self.root)

    def test_nonfinite_settings_fail_before_rendering(self):
        for key in ('seconds', 'warmup'):
            for value in (float('nan'), float('inf')):
                with self.subTest(key=key, value=value), self.assertRaises(app.ConversionError):
                    app.convert('missing', self.root / 'output.mp4', **{key: value})

    def test_automatic_names_keep_unicode_and_number_collisions(self):
        self.project({'title': 'قمر / Wallpaper', 'type': 'scene'})
        first = app.automatic_output(self.root, self.root)
        self.assertIn('قمر', first.name)
        first.touch()
        second = app.automatic_output(self.root, self.root)
        self.assertEqual(second.stem, first.stem + '_2')

    def test_kde_apply_escapes_path_and_checks_response(self):
        output = self.root / 'video "quotes" $x.mp4'
        output.touch()
        success = subprocess.CompletedProcess([], 0, '{"ok":true,"desktops":2}', '')
        with patch.object(app, 'require', return_value='kpackagetool6'), \
             patch.object(app, 'find_tool', return_value='qdbus6'), \
             patch.object(app.subprocess, 'run', side_effect=[subprocess.CompletedProcess([], 0), success]) as run:
            messages = []
            app.apply_kde_wallpaper(output, messages.append)
            script = run.call_args.args[0][-1]
            self.assertIn(json.dumps(str(output)), script)
            self.assertIn('LibraryFolder', script)
            self.assertIn(json.dumps(str(output.parent)), script)
            self.assertIn('2 Plasma desktops', messages[0])
        failure = subprocess.CompletedProcess([], 0, '{"ok":false,"error":"No Plasma desktops found"}', '')
        with patch.object(app, 'require', return_value='kpackagetool6'), \
             patch.object(app, 'find_tool', return_value='qdbus6'), \
             patch.object(app.subprocess, 'run', side_effect=[subprocess.CompletedProcess([], 0), failure]), \
             self.assertRaisesRegex(app.ConversionError, 'MP4 is saved'):
            app.apply_kde_wallpaper(output)
        self.assertTrue(output.is_file())

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe') and
                         (shutil.which('chromium') or shutil.which('chromium-browser')) and
                         importlib.util.find_spec('playwright'), 'Chromium/Playwright and FFmpeg required')
    def test_headless_web_motion_and_supersampling(self):
        entry = self.root / 'index.html'
        entry.write_text('<html><body style="margin:0"><canvas id="c" width="160" height="90"></canvas>'
                         '<script>let x=0; function draw(){let ctx=c.getContext("2d");'
                         'ctx.fillStyle="black";ctx.fillRect(0,0,160,90);ctx.fillStyle="red";'
                         'ctx.fillRect((x++*3)%140,10,20,20);requestAnimationFrame(draw)}draw()</script></body></html>')
        output = self.root / 'web.mp4'
        app.convert(entry, output, seconds=.5, fps=10, width=160, height=90,
                    warmup=0, supersample=2, log=lambda _: None)
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(output), '-f', 'rawvideo',
                              '-pix_fmt', 'rgb24', 'pipe:1'], capture_output=True, check=True).stdout
        frame_size = 160 * 90 * 3
        self.assertEqual(len(raw), 5 * frame_size)
        self.assertNotEqual(raw[:frame_size], raw[-frame_size:])

    def test_gdbus_fallback_checks_structured_plasma_response(self):
        output = self.root / 'wallpaper.mp4'
        output.touch()
        response = subprocess.CompletedProcess([], 0, repr(('{"ok":true,"desktops":1}',)), '')
        with patch.object(app, 'require', return_value='kpackagetool6'), \
             patch.object(app, 'find_tool', return_value=None), \
             patch.object(app.shutil, 'which', return_value='/usr/bin/gdbus'), \
             patch.object(app.subprocess, 'run', side_effect=[subprocess.CompletedProcess([], 0), response]) as run:
            app.apply_kde_wallpaper(output, lambda _: None)
            command = run.call_args.args[0]
            self.assertEqual(command[:3], ['/usr/bin/gdbus', 'call', '--session'])
            self.assertIn(json.dumps(str(output)), command[-1])

    def test_hidden_scene_without_window_fails_and_cleans_up(self):
        self.project({'type': 'scene'})
        processes = []

        class FakeProcess:
            def __init__(self):
                self.returncode = None
                processes.append(self)
            def poll(self): return self.returncode
            def terminate(self): self.returncode = 0
            def wait(self, timeout=None): return self.returncode

        def launch(command, **kwargs):
            import os
            if command[0] == 'Xvfb':
                os.write(kwargs['pass_fds'][0], b'99\n')
            else:
                self.assertNotIn('WAYLAND_DISPLAY', kwargs['env'])
                self.assertNotIn('XAUTHORITY', kwargs['env'])
                self.assertEqual(kwargs['env']['DISPLAY'], ':99')
            return FakeProcess()

        output = self.root / 'scene.mp4'
        with patch.object(app, 'require', side_effect=lambda name: name), \
             patch.object(app.subprocess, 'Popen', side_effect=launch), \
             patch.object(app.time, 'monotonic', side_effect=[0, 1, 0, 16]), \
             patch.dict(app.os.environ, {'WAYLAND_DISPLAY': 'wayland-0', 'XAUTHORITY': '/desktop-cookie'}), \
             self.assertRaisesRegex(app.ConversionError, 'blank video'):
            app.convert(self.root, output, warmup=0, width=160, height=90, log=lambda _: None)
        self.assertFalse(output.exists())
        self.assertFalse(list(self.root.glob('.wallpaper-*.mp4')))
        self.assertEqual(len(processes), 2)
        self.assertTrue(all(p.poll() is not None for p in processes))

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
    def test_image_video_exports_and_output_protection(self):
        # PPM fixture converted to PNG by real FFmpeg; no Pillow dependency needed.
        ppm = self.root / 'source.ppm'
        ppm.write_bytes(b'P6\n8 8\n255\n' + bytes((255, 0, 0)) * 64)
        image = self.root / 'source.png'
        subprocess.run(['ffmpeg', '-v', 'error', '-i', str(ppm), str(image)], check=True)
        output = self.root / 'image.mp4'
        app.convert(image, output, seconds=.5, fps=10, width=160, height=90, supersample=2, log=lambda _: None)
        before = output.read_bytes()
        with self.assertRaisesRegex(app.ConversionError, 'already exists'):
            app.convert(image, output)
        self.assertEqual(before, output.read_bytes())
        video = self.root / 'video.mp4'
        app.convert(output, video, seconds=1, fps=10, width=160, height=90, log=lambda _: None)
        for path, count in ((output, 5), (video, 10)):
            probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                                    '-show_entries', 'stream=width,height,codec_name,nb_read_frames',
                                    '-of', 'json', str(path)], capture_output=True, text=True, check=True)
            stream = json.loads(probe.stdout)['streams'][0]
            self.assertEqual((stream['width'], stream['height'], stream['codec_name']), (160, 90, 'h264'))
            self.assertEqual(int(stream['nb_read_frames']), count)
        cancel = threading.Event(); cancel.set()
        cancelled = self.root / 'cancelled.mp4'
        with self.assertRaisesRegex(app.ConversionError, 'Cancelled'):
            app.convert(image, cancelled, seconds=30, cancel=cancel, log=lambda _: None)
        self.assertFalse(cancelled.exists())
        self.assertFalse(list(self.root.glob('.wallpaper-*.mp4')))


if __name__ == '__main__':
    unittest.main()
