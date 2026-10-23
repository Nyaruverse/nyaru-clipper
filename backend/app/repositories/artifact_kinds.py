from typing import Final


EXPECTED_ARTIFACT_KINDS: Final[dict[str, tuple[str, tuple[str, ...]]]] = {
    "ingest": ("source_video", ("source_video",)),
    "media_prep": ("prepared_audio", ("prepared_audio", "asr_audio")),
    "asr": ("transcript_json", ("transcript_json",)),
    "translation": ("translated_segments", ("translated_segments", "bilingual_transcript_json")),
    "highlight": ("highlight_candidates", ("highlight_candidates", "highlight_candidates_json")),
    "export": ("clip_video", ("clip_video", "exported_clip", "clip_export")),
    "report": ("report", ("report", "task_report_markdown")),
}
