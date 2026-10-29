from __future__ import annotations

import csv
import io
import re
import signal
import subprocess
import sys
import threading
from pathlib import Path

from app.arctime import media


class LiveCapture:
    def __init__(self, url: str, directory: Path, stop: threading.Event):
        if not re.fullmatch(r'https?://live\.bilibili\.com/(?:blanc/)?[1-9][0-9]*/?', url):
            raise ValueError('请输入不带参数的 Bilibili 数字直播间 HTTPS 链接')
        self.url = 'https://live.bilibili.com/' + url.rstrip('/').rsplit('/', 1)[-1]
        self.directory, self.stop = directory, stop
        self.process = None
        self.error = None
        self.done = threading.Event()
        self.thread = None

    @staticmethod
    def recorded(directory: Path) -> list[Path]:
        result = []
        for listing in sorted(directory.glob('capture-*/closed.csv')):
            if listing.is_symlink() or listing.parent.is_symlink():
                raise ValueError('录制缓存路径无效')
            text = listing.read_text(encoding='utf-8')
            text = text[:text.rfind('\n') + 1]
            for row in csv.reader(io.StringIO(text)):
                if not row or not re.fullmatch(r'chunk-[0-9]{5}\.(?:ts|mp4)', row[0]):
                    raise ValueError('录制缓存索引无效')
                path = listing.parent / row[0]
                if path.is_symlink() or not path.is_file():
                    raise ValueError('已关闭录制块缺失')
                result.append(path)
        return result

    def _resolve(self) -> str:
        downloader = [media.tool_path('yt-dlp')]
        if getattr(sys, 'frozen', False):
            downloader.append('--yt-dlp')
        result = subprocess.run([*downloader, '--no-playlist', '--no-warnings',
                                 '-f', 'best', '-g', '--', self.url],
                                capture_output=True, text=True, timeout=30, check=False)
        lines = result.stdout.strip().splitlines()
        if result.returncode or len(lines) != 1 or not lines[0].startswith(('https://', 'http://')):
            raise ValueError('无法解析 Bilibili 直播流，请确认直播间正在直播')
        return lines[0]

    def _record(self):
        try:
            for attempt in range(3):
                if self.stop.is_set():
                    break
                try:
                    stream = self._resolve()
                    if self.stop.is_set():
                        break
                    session = self.directory / f'capture-{len(list(self.directory.glob("capture-*"))):04d}'
                    session.mkdir()
                    self.process = subprocess.Popen([
                        media.tool_path('ffmpeg'), '-nostdin', '-hide_banner', '-loglevel', 'error',
                        '-rw_timeout', '15000000', '-i', stream, '-map', '0:v:0', '-map', '0:a:0?',
                        '-c', 'copy', '-f', 'segment', '-segment_time', '20', '-reset_timestamps', '1',
                        '-segment_list', 'closed.csv', '-segment_list_type', 'csv', 'chunk-%05d.mp4'],
                        cwd=session, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)
                    while self.process.poll() is None:
                        if self.stop.wait(.2):
                            self._terminate()
                            break
                except Exception:
                    # Stream URLs and downloader diagnostics may contain reusable tokens.
                    self.error = '直播连接失败；已保留已关闭录制块'
                if self.stop.is_set():
                    break
                self.error = '直播断流；缺失区间无法恢复，已保留各连接的独立录制块'
                if attempt < 2 and self.stop.wait(2 ** attempt):
                    break
        finally:
            try:
                self._terminate()
            except Exception:
                pass
            self.done.set()

    def _terminate(self):
        process = self.process
        if process is None or process.poll() is not None:
            return
        try:
            process.send_signal(signal.SIGINT)
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        except (ProcessLookupError, OSError, ValueError):
            # Windows 上 SIGINT 可能无法送达子进程（控制台事件组不存在），直接强杀
            try:
                process.kill()
                process.wait(timeout=5)
            except (ProcessLookupError, OSError):
                pass

    def chunks(self):
        self.thread = threading.Thread(target=self._record, name='bilibili-capture', daemon=True)
        self.thread.start()
        seen = set()
        while True:
            finished = self.done.is_set()
            for path in self.recorded(self.directory):
                if path not in seen:
                    seen.add(path)
                    yield path
            if finished:
                break
            self.done.wait(.2)

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=50)
            if self.thread.is_alive():
                raise RuntimeError('直播录制进程尚未退出')
