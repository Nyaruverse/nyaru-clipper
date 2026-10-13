from __future__ import annotations

import argparse
import importlib
import json
import subprocess
import sys
from pathlib import Path

from app.arctime import media, workflow
from app.arctime.local_asr import DEFAULT_MODEL, LocalASR


def _asr_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL, help="本地 whisper.cpp GGML 模型路径")
    parser.add_argument("--language", default="auto", help="原视频语种，例如 zh、en、ja 或 auto")
    parser.add_argument("--threads", type=int, default=4, help="识别线程数，默认 4")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="本地视频配套工具：链接下载、字幕识别、时间轴和切片")
    commands = parser.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="检查本地运行环境")
    _asr_options(doctor)
    run = commands.add_parser("run", help="下载视频、生成字幕并导出切片")
    run.add_argument("url", help="单个 HTTP(S) 视频链接")
    run.add_argument("--output-dir", type=Path, default=Path("data/local-runs"), help="任务输出根目录")
    selection = run.add_mutually_exclusive_group(required=True)
    selection.add_argument("--range", dest="ranges", action="append", nargs=2, metavar=("START", "END"),
                           help="秒数或 HH:MM:SS.mmm，可重复指定")
    selection.add_argument("--highlights", type=int, help="按本地规则选择最多 N 个非重叠高光")
    _asr_options(run)
    resume = commands.add_parser("resume", help="恢复已下载的本地任务")
    resume.add_argument("directory", type=Path, help="含 job.json 的任务目录")
    gui = commands.add_parser("gui", help="启动本地图形界面")
    gui.add_argument("--output-dir", type=Path, default=Path("data/local-runs"))
    gui.add_argument("--port", type=int, default=8787)
    gui.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    gui.add_argument("--threads", type=int, default=4)
    args = parser.parse_args(argv)
    directory: Path | None = None
    try:
        if args.command == "gui":
            import uvicorn
            from app.arctime.gui import WEB_DIST, create_app

            if not (WEB_DIST / "companion.html").is_file():
                raise ValueError("请先在 web 目录执行 corepack pnpm build 构建界面")
            if not 1 <= args.port <= 65535:
                raise ValueError("端口必须在 1 到 65535 之间")
            print(f"本地界面：http://127.0.0.1:{args.port}", file=sys.stderr, flush=True)
            uvicorn.run(create_app(args.output_dir, args.model, args.threads), host="127.0.0.1", port=args.port)
            return 0
        if args.command == "doctor":
            checks = {}
            try:
                importlib.import_module("app.services.export_encoding")
                checks["python"] = {"ready": True}
            except ImportError as exc:
                checks["python"] = {"ready": False, "error": str(exc)}
            for name in ("yt-dlp", "ffmpeg", "ffprobe", "whisper-cli"):
                try:
                    checks[name] = {"ready": True, "path": media.tool_path(name)}
                except FileNotFoundError:
                    checks[name] = {"ready": False, "error": "未安装或未加入 PATH"}
            try:
                checks["model"] = {"ready": True, "identity": LocalASR(args.model, args.language, args.threads).identity()}
            except (OSError, ValueError) as exc:
                checks["model"] = {"ready": False, "error": str(exc)}
            ready = all(item["ready"] for item in checks.values())
            print(json.dumps({"ready": ready, "checks": checks}, ensure_ascii=False, indent=2))
            return 0 if ready else 1
        if args.command == "run":
            ranges = [(media.parse_time(s), media.parse_time(e)) for s, e in (args.ranges or [])]
            adapter = LocalASR(args.model, args.language, args.threads)
            print("正在检查环境并下载视频", file=sys.stderr, flush=True)
            directory = workflow.create_run(args.url, args.output_dir, ranges, args.highlights, adapter)
        else:
            directory = args.directory.expanduser().resolve()
            adapter = None
        print(f"任务目录：{directory}", file=sys.stderr, flush=True)
        job = workflow.resume_run(directory, transcriber=adapter, progress=lambda message: print(message, file=sys.stderr, flush=True))
        print(json.dumps({"state": job["state"], "directory": str(directory),
                          "clip_count": len(job["completed_clips"]), "clips": job["completed_clips"],
                          "subtitles": str(directory / "subtitles.srt"), "transcript": str(directory / "transcript.txt")},
                         ensure_ascii=False, indent=2))
        return 0
    except KeyboardInterrupt:
        print("已停止本地处理；下载完成的任务可用 resume 恢复，下载中断需重新 run。", file=sys.stderr)
        return 130
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, ImportError, subprocess.TimeoutExpired) as exc:
        for note in getattr(exc, "__notes__", []):
            if note.startswith("Run directory: "):
                directory = Path(note.removeprefix("Run directory: "))
        message = "外部工具执行超时" if isinstance(exc, subprocess.TimeoutExpired) else str(exc)
        print(json.dumps({"error": message, "directory": str(directory) if directory else None}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
