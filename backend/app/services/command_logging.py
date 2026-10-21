from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any


def append_stage_log(log_path: Path, message: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"{message}\n")


def run_logged_command(
    args: list[str],
    *,
    log_path: Path,
    redactions: dict[str, str] | None = None,
    redact_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run a command, sanitizing diagnostics before logging or returning them."""
    def redact(message: str) -> str:
        if redactions is None:
            return message
        pattern = "|".join(re.escape(value) for value in sorted(redactions, key=len, reverse=True) if value)
        return re.sub(pattern, lambda match: redactions[match.group()], message) if pattern else message

    def redact_json(value: Any) -> Any:
        if isinstance(value, str):
            return redact(value)
        if isinstance(value, list):
            return [redact_json(item) for item in value]
        if isinstance(value, dict):
            return {redact(key): redact_json(item) for key, item in value.items()}
        return value

    def redact_diagnostic(message: str) -> str:
        if redact_output:
            try:
                payload = json.loads(message)
            except json.JSONDecodeError:
                return redact(message)
            return json.dumps(redact_json(payload), ensure_ascii=False)
        return redact(message)

    append_stage_log(log_path, redact(f"$ {' '.join(args)}"))
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    if redact_output:
        result.stdout = redact_diagnostic(result.stdout)
        result.stderr = redact_diagnostic(result.stderr)
    if result.stdout:
        append_stage_log(log_path, result.stdout.rstrip() if redact_output else redact(result.stdout.rstrip()))
    if result.stderr:
        append_stage_log(log_path, result.stderr.rstrip() if redact_output else redact(result.stderr.rstrip()))
    append_stage_log(log_path, f"exit_code={result.returncode}")
    return result
