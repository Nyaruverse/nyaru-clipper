from pathlib import Path
import runpy


def test_packager_accepts_separate_output_and_checks_subtitle_renderer():
    source = Path(__file__).resolve().parents[2] / "scripts/build_macos_app.py"
    namespace = runpy.run_path(str(source))
    assert callable(namespace.get("validate_subtitle_tool"))
    namespace["validate_subtitle_tool"](Path("/opt/homebrew/opt/ffmpeg@7/bin/ffmpeg"))


def test_packager_rejects_tool_without_libass(tmp_path):
    import pytest
    source = Path(__file__).resolve().parents[2] / "scripts/build_macos_app.py"
    namespace = runpy.run_path(str(source))
    with pytest.raises(ValueError, match="libass"):
        namespace["validate_subtitle_tool"](tmp_path / "missing-ffmpeg")


def test_packager_includes_sdl3_runtime_dependency():
    source = Path(__file__).resolve().parents[2] / "scripts/build_macos_app.py"
    namespace = runpy.run_path(str(source))
    binaries = [("/opt/homebrew/opt/ffmpeg@7/bin/ffmpeg", ".")]
    sources = namespace["native_dependencies"](binaries)
    assert Path("/opt/homebrew/opt/sdl3/lib/libSDL3.dylib").resolve() in sources
    assert ("/opt/homebrew/opt/sdl3/lib/libSDL3.dylib", ".") in binaries
