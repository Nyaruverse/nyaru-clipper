import math
from pathlib import Path

import pytest

from app.arctime import media
from app.services.subtitles import SubtitleSegment


@pytest.mark.parametrize("value,seconds", [("12.5", 12.5), ("01:02", 62), ("1:02:03.250", 3723.25)])
def test_parse_time(value, seconds):
    assert media.parse_time(value) == seconds


@pytest.mark.parametrize("value", ["nan", "inf", "-1", "1:60", "1:2:60", "1:2:3:4", "", "a", "1:-2"])
def test_invalid_time(value):
    with pytest.raises(ValueError):
        media.parse_time(value)


def test_ass_preserves_commas_and_removes_formatting(tmp_path):
    path = tmp_path / "video.ass"
    path.write_text("[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
                    "Dialogue: 0,0:00:01.00,0:00:03.50,Default,,0,0,0,,{\\b1}你好,世界\\N第二行\n", encoding="utf-8")
    result = media.read_subtitles(path)
    assert len(result) == 1
    assert (result[0].start_seconds, result[0].end_seconds, result[0].text) == (1, 3.5, "你好,世界\n第二行")


def test_srt_bom_multiline_and_crlf(tmp_path):
    path = tmp_path / "video.srt"
    path.write_bytes("\ufeff1\r\n00:00:01,200 --> 00:00:02,300\r\n你好\r\n世界\r\n".encode())
    result = media.read_subtitles(path)
    assert result[0].text == "你好\n世界"
    assert result[0].start_seconds == 1.2


@pytest.mark.parametrize("content", ["", "1\n00:00:02,000 --> 00:00:01,000\nwrong", "1\n00:00:00,000 --> 00:00:01,000\n",
    "1\n00:00:00,000 --> 00:00:01,000\nvalid\n\n2\nINVALID\nignored"])
def test_bad_or_partial_srt_is_rejected(tmp_path, content):
    path = tmp_path / "bad.srt"
    path.write_text(content)
    with pytest.raises(ValueError):
        media.read_subtitles(path)


def test_clipped_cues_are_rebased():
    cues = [SubtitleSegment("1", 1, 4, "a"), SubtitleSegment("2", 5, 7, "b"), SubtitleSegment("3", 8, 9, "c")]
    result = media.clip_subtitles(cues, 2, 6)
    assert [(s.start_seconds, s.end_seconds, s.text) for s in result] == [(0, 2, "a"), (3, 4, "b")]
    assert cues[0].start_seconds == 1


@pytest.mark.parametrize("ranges", [[(-1, 3)], [(2, 2)], [(3, 2)], [(0, 11)], [(0, math.inf)], [(math.nan, 5)]])
def test_out_of_range_selection_is_rejected(ranges):
    with pytest.raises(ValueError):
        media.select_clips([], 10, ranges, None)


def test_manual_selection_requires_no_highlight_candidate():
    assert media.select_clips([], 10, [(1, 3), (5, 8)], None) == [
        {"start": 1.0, "end": 3.0, "score": None, "reasons": ["manual"]},
        {"start": 5.0, "end": 8.0, "score": None, "reasons": ["manual"]},
    ]


def test_highlights_rank_by_score_and_deduplicate_overlap(monkeypatch):
    monkeypatch.setattr(media, "score_candidate_windows", lambda *a, **kw: [
        {"score": .6, "default_range": {"start_s": 0, "end_s": 5}, "reasons": ["a"]},
        {"score": .9, "default_range": {"start_s": 2, "end_s": 7}, "reasons": ["b"]},
        {"score": .7, "default_range": {"start_s": 8, "end_s": 10}, "reasons": ["c"]},
    ])
    clips = media.select_clips([SubtitleSegment("1", 0, 10, "hello")], 10, [], 2)
    assert [(c["start"], c["score"]) for c in clips] == [(2, .9), (8, .7)]


def test_empty_highlights_dont_fabricate_a_clip():
    assert media.select_clips([], 10, [], 3) == []


def test_failed_export_never_overwrites_previous_file(tmp_path, monkeypatch):
    final = tmp_path / "clip.mp4"
    final.write_bytes(b"previous good output")
    monkeypatch.setattr(media, "probe_video", lambda path: 10)
    with pytest.raises(FileExistsError):
        media.export_clip(tmp_path / "video.mp4", final, 1, 3, [])
    assert final.read_bytes() == b"previous good output"


def test_download_rejects_non_http_urls(tmp_path):
    for url in ["file:///etc/passwd", "--exec=malicious", "ftp://example.com/v.mp4", "https://user:password@example.com/v.mp4"]:
        with pytest.raises(ValueError):
            media.download_video(url, tmp_path)


def test_tool_finds_program_in_active_python_environment(tmp_path, monkeypatch):
    import sys
    tool = tmp_path / "yt-dlp"
    tool.write_text("program")
    tool.chmod(0o700)
    monkeypatch.setattr(media.shutil, "which", lambda name: None)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "python"))
    assert media.tool_path("yt-dlp") == str(tool)


def test_failed_encoding_keeps_diagnostic_log(tmp_path, monkeypatch):
    import subprocess
    from app.services import export_encoding

    monkeypatch.setattr(media, "probe_video", lambda path: 10)
    monkeypatch.setattr(media, "tool_path", lambda name: name)

    def failed(invocation, settings, log_path):
        log_path.write_text("encoder failure diagnostic")
        return export_encoding.ExportExecution("cpu", "libx264", subprocess.CompletedProcess([], 1))

    monkeypatch.setattr(export_encoding, "execute_video_export", failed)
    with pytest.raises(RuntimeError):
        media.export_clip(tmp_path / "source.mp4", tmp_path / "clip.mp4", 0, 10, [])
    assert (tmp_path / "clip.log").read_text() == "encoder failure diagnostic"
    assert not (tmp_path / "clip.mp4").exists()


def test_matching_orphan_subtitle_is_preserved_during_recovery(tmp_path, monkeypatch):
    import subprocess
    from app.services import export_encoding

    cues = [SubtitleSegment("1", 1, 3, "hello")]
    target = tmp_path / "clip.mp4"
    subtitle = target.with_suffix(".srt")
    subtitle.write_text(media.render_srt(cues))
    before = subtitle.stat().st_ino
    monkeypatch.setattr(media, "probe_video", lambda path: 10)
    monkeypatch.setattr(media, "tool_path", lambda name: name)

    def success(invocation, settings, log_path):
        invocation.output_path.write_bytes(b"encoded video")
        return export_encoding.ExportExecution("cpu", "libx264", subprocess.CompletedProcess([], 0))

    monkeypatch.setattr(export_encoding, "execute_video_export", success)
    media.export_clip(tmp_path / "source.mp4", target, 0, 10, cues)
    assert target.read_bytes() == b"encoded video"
    assert subtitle.stat().st_ino == before


def test_changed_orphan_subtitle_is_not_overwritten(tmp_path, monkeypatch):
    target = tmp_path / "clip.mp4"
    subtitle = target.with_suffix(".srt")
    subtitle.write_text("manual edits")
    monkeypatch.setattr(media, "probe_video", lambda path: 10)
    with pytest.raises(FileExistsError):
        media.export_clip(tmp_path / "source.mp4", target, 0, 10, [])
    assert subtitle.read_text() == "manual edits"
