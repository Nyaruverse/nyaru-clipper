#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
NAME = "Nyaru Clipper"


def run(args: list[str], *, cwd: Path = ROOT) -> str:
    result = subprocess.run(args, cwd=cwd, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return result.stdout


def dependencies(binary: Path) -> list[str]:
    return [line.strip().split(" (", 1)[0] for line in run(["/usr/bin/otool", "-L", str(binary)]).splitlines()[1:]]


def validate_subtitle_tool(binary: Path) -> None:
    if not binary.is_file():
        raise ValueError("Build requires FFmpeg with libass subtitles support")
    result = subprocess.run([str(binary), "-hide_banner", "-filters"], capture_output=True, text=True, timeout=15, check=False)
    if result.returncode or not any(" ass " in line for line in result.stdout.splitlines()):
        raise ValueError("Build requires FFmpeg with libass subtitles support")


def native_dependencies(binaries: list[tuple[str, str]]) -> set[Path]:
    sources = {Path(source).resolve() for source, _ in binaries}
    pending = list(sources)
    while pending:
        current = pending.pop()
        linked = dependencies(current)
        if current.name.startswith("libSDL2"):
            # SDL2 compatibility loads SDL3 at runtime, outside otool's dependency graph.
            sdl3 = Path("/opt/homebrew/opt/sdl3/lib/libSDL3.dylib")
            if not sdl3.is_file():
                raise ValueError("SDL2 compatibility requires the SDL3 runtime")
            linked.append(str(sdl3))
            if (str(sdl3), ".") not in binaries:
                binaries.append((str(sdl3), "."))
        for value in linked:
            path = Path(value)
            if value.startswith("/opt/homebrew/") and path.is_file() and path.resolve() not in sources:
                sources.add(path.resolve())
                pending.append(path.resolve())
    return sources


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a self-contained Apple Silicon local companion")
    parser.add_argument("--model", type=Path, default=Path.home() / ".cache/nyaru-clipper/models/ggml-small.bin")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    parser.add_argument("--ffmpeg", type=Path, default=Path("/opt/homebrew/opt/ffmpeg@7/bin/ffmpeg"))
    options = parser.parse_args()
    if sys.platform != "darwin" or platform.machine() != "arm64":
        parser.error("This build requires an Apple Silicon macOS host")
    sys.path.insert(0, str(ROOT / "backend"))
    from app.arctime.macos import MODEL_SHA256
    from app.arctime.media import fingerprint
    if fingerprint(options.model) != MODEL_SHA256:
        parser.error("The model does not match the verified multilingual small model")

    validate_subtitle_tool(options.ffmpeg)
    tools = {"ffmpeg": options.ffmpeg, "ffprobe": options.ffmpeg.with_name("ffprobe"),
             "whisper-cli": Path(shutil.which("whisper-cli") or "")}
    for name, path in tools.items():
        if not path.is_file():
            parser.error(f"Build tool is missing: {name}")
    corepack = shutil.which("corepack")
    if not corepack:
        parser.error("Build requires Corepack and the web package dependencies")
    print("Building companion interface…", flush=True)
    print(run([corepack, "pnpm", "build"], cwd=ROOT / "web"), flush=True)

    output = options.output_dir.expanduser().resolve()
    app = output / f"{NAME}.app"
    if app.exists():
        raise FileExistsError(f"Preserving existing build: {app}. Move it before rebuilding.")
    resources = app / "Contents/Resources"
    macos = app / "Contents/MacOS"
    macos.mkdir(parents=True)
    resources.mkdir(parents=True)
    work = output / "macos-build"
    work.mkdir(exist_ok=True)
    model_source = work / "model/ggml-small.bin"
    model_source.parent.mkdir(exist_ok=True)
    shutil.copyfile(options.model, model_source)

    binaries = [(str(path), ".") for path in tools.values()]
    whisper_prefix = tools["whisper-cli"].resolve().parents[1]
    binaries.append((str(whisper_prefix / "lib/libwhisper.1.dylib"), "."))
    ggml_path = next(Path(value).resolve().parent for value in dependencies(whisper_prefix / "lib/libwhisper.1.dylib") if value.endswith("libggml.0.dylib"))
    binaries.extend((str(path), ".") for path in (ggml_path.parent / "libexec").glob("libggml-*.so"))
    native_sources = native_dependencies(binaries)
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--name", "nyaru-backend",
               "--target-arch", "arm64", "--paths", str(ROOT / "backend"), "--distpath", str(resources / "runtime"),
               "--workpath", str(work / "pyinstaller"), "--specpath", str(work), "--collect-all", "yt_dlp",
               "--add-data", f"{ROOT / 'web/dist'}:web", "--add-data", f"{model_source}:models"]
    for source, destination in binaries:
        command.extend(["--add-binary", f"{source}:{destination}"])
    command.append(str(ROOT / "scripts/macos_companion.py"))
    print("Freezing backend, tools and model…", flush=True)
    try:
        log = run(command)
        (work / "pyinstaller.log").write_text(log)
    except subprocess.CalledProcessError as exc:
        (work / "pyinstaller.log").write_text(exc.stdout)
        raise
    validate_subtitle_tool(resources / "runtime/nyaru-backend/_internal/ffmpeg")

    print("Compiling native window…", flush=True)
    print(run(["xcrun", "swiftc", "-parse-as-library", "-O", "-target", "arm64-apple-macos27.0", "-framework", "AppKit", "-framework", "WebKit",
               str(ROOT / "desktop/macos/App.swift"), "-o", str(macos / NAME)]), flush=True)
    with (app / "Contents/Info.plist").open("wb") as handle:
        plistlib.dump({"CFBundleExecutable": NAME, "CFBundleIdentifier": "local.nyaru.clipper", "CFBundleName": NAME,
                      "CFBundleDisplayName": NAME, "CFBundlePackageType": "APPL", "CFBundleShortVersionString": "0.1.9",
                      "CFBundleVersion": "17", "LSMinimumSystemVersion": "27.0", "LSArchitecturePriority": ["arm64"],
                      "NSHighResolutionCapable": True, "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True}}, handle)

    licenses = resources / "Licenses"
    licenses.mkdir()
    for dist in importlib.metadata.distributions():
        for file in dist.files or []:
            if "license" in str(file).lower() or Path(file).name.lower() in {"copying", "notice"}:
                source = Path(dist.locate_file(file))
                if source.is_file():
                    destination = licenses / dist.metadata["Name"] / str(file)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, destination)
    formulae = {parent for path in native_sources for parent in path.parents if parent.parent.parent.name == "Cellar"}
    for formula in formulae:
        for path in formula.iterdir():
            if path.is_file() and any(word in path.name.lower() for word in ("license", "copying", "notice", "authors", "sbom")):
                target = licenses / formula.parent.name / path.name
                target.parent.mkdir(exist_ok=True)
                shutil.copyfile(path, target)
    for path in [ROOT / "LICENSE", whisper_prefix / "LICENSE", ggml_path.parent / "LICENSE"]:
        if path.is_file():
            shutil.copyfile(path, licenses / f"{path.parent.name}-{path.name}")
    (resources / "build-info.json").write_text(json.dumps({"architecture": "arm64", "minimum_macos": "27.0", "model_sha256": MODEL_SHA256,
        "python": platform.python_version(), "subtitle_renderer": "libass", "packages": {dist.metadata["Name"]: dist.version for dist in importlib.metadata.distributions()}}, indent=2))
    print(run(["/usr/bin/codesign", "--force", "--deep", "--sign", "-", str(app)]), flush=True)
    run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app)])
    print(f"Built: {app}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
