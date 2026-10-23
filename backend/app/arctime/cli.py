from __future__ import annotations

import argparse
import importlib
import json
import signal
import subprocess
import sys
import threading
import uuid
from pathlib import Path

from app.arctime import companion_llm, media, workflow
from app.arctime.local_asr import DEFAULT_MODEL, LocalASR
from app.services.runtime_guard import SlotBusy, execution_slot


def _selector(config: companion_llm.LLMConfig, saved: dict):
    from app.arctime.saozi import SaoziSelector
    model = companion_llm.job_model(config, saved)
    key = companion_llm.require_key(config, model)
    return SaoziSelector(key, model, request_json=companion_llm.requester(config, model))


def _asr_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL, help="本地 whisper.cpp GGML 模型路径")
    parser.add_argument("--language", default="auto", help="原视频语种，例如 zh、en、ja 或 auto")
    parser.add_argument("--threads", type=int, default=4, help="识别线程数，默认 4")


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments and arguments[0] in {"run", "resume"}:
        try:
            with execution_slot():
                return _main(arguments)
        except SlotBusy:
            print("其他入口正在处理，请稍后重试；已有结果已保留", file=sys.stderr)
            return 1
    return _main(arguments)


def _main(argv: list[str] | None = None) -> int:
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
    selection.add_argument("--saozi", action="store_true", help="臊子：使用已配置供应商连续语义切片，每片约1–2分钟")
    run.add_argument("--local", action="store_true", help="将输入作为本地录像路径（仅臊子）")
    run.add_argument("--live", action="store_true", help="Bilibili 实时臊子；Ctrl+C停止录制并导出尾段")
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
    config: companion_llm.LLMConfig | None = None
    try:
        if args.command == "gui":
            import uvicorn
            from app.arctime.gui import WEB_DIST, create_app

            if not (WEB_DIST / "companion.html").is_file():
                raise ValueError("请先在 web 目录执行 corepack pnpm build 构建界面")
            if not 1 <= args.port <= 65535:
                raise ValueError("端口必须在 1 到 65535 之间")
            print(f"本地界面：http://127.0.0.1:{args.port}", file=sys.stderr, flush=True)
            uvicorn.run(create_app(args.output_dir, args.model, args.threads), host="127.0.0.1", port=args.port, access_log=False)
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
            if (args.local or args.live) and (not args.saozi or (args.local and args.live)):
                raise ValueError("本地或实时输入需要臊子模式，且不能同时选择")
            ranges = [(media.parse_time(s), media.parse_time(e)) for s, e in (args.ranges or [])]
            adapter = LocalASR(args.model, args.language, args.threads)
            config = companion_llm.LLMConfig(args.output_dir) if args.saozi else None
            selector = _selector(config, {}) if config is not None else None
            print("正在检查环境并下载视频", file=sys.stderr, flush=True)
            if args.live:
                from app.arctime.companion_models import JobInput
                JobInput(url=args.url, saozi=True, live=True, language=args.language)
                directory = args.output_dir.expanduser().resolve() / uuid.uuid4().hex[:12]
                directory.mkdir(mode=0o700, parents=True)
            else:
                options = {"saozi":True,"local_source":Path(args.url).expanduser().resolve() if args.local else None,
                           "llm_model": selector.model} if args.saozi else {}
                directory = workflow.create_run(args.url, args.output_dir, ranges, args.highlights, adapter, **options)
        else:
            directory = args.directory.expanduser().resolve()
            adapter = None
            saved = json.loads((directory / "job.json").read_text()) if (directory / "job.json").is_file() else {}
            config = companion_llm.LLMConfig(directory.parent) if saved.get('saozi') else None
            selector = _selector(config, saved) if config is not None else None
        print(f"任务目录：{directory}", file=sys.stderr, flush=True)
        notify = lambda message: print(message, file=sys.stderr, flush=True)
        saved = json.loads((directory / "job.json").read_text()) if (directory / "job.json").is_file() else {}
        translation_failed = False
        def bilingual(path: Path, final: bool, *, locked: bool = True):
            nonlocal translation_failed
            if translation_failed and not final:
                return
            from app.arctime.saozi_translation import translate
            try:
                options = {'request_json': selector.request_json} if selector.request_json is not None else {}
                translate(path, selector.key, model=selector.model, final=final, locked=locked, progress=notify, **options)
                translation_failed = False
            except (ValueError, OSError):
                translation_failed = True
                notify("双语字幕未完成；保留原文切片并继续录制，可用 resume 重试")
        if (args.command == "run" and args.live) or saved.get("live"):
            from app.arctime.saozi_live import run_live
            stop = threading.Event()
            previous = signal.signal(signal.SIGINT, lambda *_: stop.set())
            try:
                if adapter is None:
                    adapter = LocalASR(Path(saved["asr"]["model"]), saved["asr"]["language"], saved["asr"]["threads"])
                job = run_live(directory, selector, adapter, stop, notify, url=args.url if args.command == "run" else None,
                               bilingual=bilingual)
            finally:
                signal.signal(signal.SIGINT, previous)
        else:
            job = workflow.resume_run(directory, transcriber=adapter, progress=notify, selector=selector)
            if job.get("saozi"):
                bilingual(directory, True, locked=False)
        print(json.dumps({"state": job["state"], "directory": str(directory),
                          "clip_count": len(job["completed_clips"]), "clips": job["completed_clips"],
                          "subtitles": str(directory / "subtitles.srt"), "transcript": str(directory / "transcript.txt")},
                         ensure_ascii=False, indent=2))
        return 1 if translation_failed else 0
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
    finally:
        if config is not None:
            config.chatgpt.close()


if __name__ == "__main__":
    raise SystemExit(main())
