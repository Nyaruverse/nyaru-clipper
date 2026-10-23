from __future__ import annotations

import argparse
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

from pydantic import BaseModel, ConfigDict, JsonValue

from app.services.asr_child_runner import JsonlAsrObserver
from app.services.asr_whisperx import AsrPipelineError, execute_asr_pipeline
from app.services.task_operations import digest
from app.settings import Settings


class ChildRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    audio: Path
    work: Path
    settings: dict[str, JsonValue]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('request', type=Path)
    parser.add_argument('--sha256', required=True)
    options = parser.parse_args()
    content = options.request.read_bytes()
    if digest(content) != options.sha256:
        return 2
    request = ChildRequest.model_validate_json(content)
    observer = JsonlAsrObserver(sys.stdout)
    try:
        with redirect_stdout(sys.stderr):
            result = execute_asr_pipeline(audio_path=request.audio, work_dir=request.work,
                settings=Settings.model_validate(request.settings), observer=observer)
        if result.transcript_path is None or result.subtitle_path is None or result.raw_alignment_path is None:
            return 2
        return 0
    except AsrPipelineError as error:
        print(json.dumps({'event': 'failure', 'code': error.code, 'phase': error.phase}), flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
