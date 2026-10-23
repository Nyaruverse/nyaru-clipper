#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
DEFAULT_OUTPUT_PATH="${BACKEND_DIR}/requirements.txt"
LINUX_CUDA_OUTPUT_PATH="${BACKEND_DIR}/requirements-linux-cuda.txt"
WSL_ROCM_OUTPUT_PATH="${BACKEND_DIR}/requirements-wsl-rocm.txt"
OUTPUT_PATH="${DEFAULT_OUTPUT_PATH}"
CHECK_ONLY=0
PROFILE="all"
PROFILE_EXPLICIT=0
CUSTOM_OUTPUT=0
UPGRADE=0
CUDA_SELECTED=0
ROCM_SELECTED=0
PYTHON_VERSION="3.11"
PYTHON_BIN="${BACKEND_PYTHON:-}"

if [[ -z "${PYTHON_BIN}" ]]; then
  if [[ -x "${BACKEND_DIR}/.venv/bin/python" ]]; then
    PYTHON_BIN="${BACKEND_DIR}/.venv/bin/python"
  else
    PYTHON_BIN="python3"
  fi
fi

usage() {
  printf 'Usage: %s [--check | --upgrade] [--profile base|linux-cuda|wsl-rocm|all] [--output PATH]\n' "$(basename "$0")" >&2
}

require_commands() {
  local command_name
  for command_name in "$@"; do
    if ! command -v "${command_name}" >/dev/null 2>&1; then
      printf 'required command not found: %s\n' "${command_name}" >&2
      exit 1
    fi
  done
}

while (($# > 0)); do
  case "$1" in
    --check)
      CHECK_ONLY=1
      shift
      ;;
    --output)
      if (($# < 2)); then
        usage
        exit 1
      fi
      OUTPUT_PATH="$2"
      CUSTOM_OUTPUT=1
      shift 2
      ;;
    --profile)
      if (($# < 2)); then usage; exit 1; fi
      PROFILE="$2"
      PROFILE_EXPLICIT=1
      shift 2
      ;;
    --upgrade)
      UPGRADE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'unknown argument: %s\n' "$1" >&2
      usage
      exit 1
      ;;
  esac
done

if ((CHECK_ONLY && UPGRADE)); then
  printf '%s\n' '--check and --upgrade cannot be combined' >&2
  exit 1
fi
if ((CUSTOM_OUTPUT)); then
  if ((PROFILE_EXPLICIT)) && [[ "${PROFILE}" != base ]]; then
    printf '%s\n' '--output supports only --profile base' >&2
    exit 1
  fi
  PROFILE=base
fi
case "${PROFILE}" in
  base) ;;
  linux-cuda) CUDA_SELECTED=1 ;;
  wsl-rocm) ROCM_SELECTED=1 ;;
  all) CUDA_SELECTED=1; ROCM_SELECTED=1 ;;
  *) usage; exit 1 ;;
esac

require_commands uv "${PYTHON_BIN}" cmp mktemp

GENERIC_INPUT_PATH="$(mktemp)"
GENERIC_RAW_PATH="$(mktemp)"
GENERIC_NORMALIZED_PATH="$(mktemp)"
GENERIC_CONSTRAINTS_PATH="$(mktemp)"
EXPECTED_PINS_PATH="$(mktemp)"
CANDIDATE_PINS_PATH="$(mktemp)"
LINUX_CUDA_CONSTRAINTS_PATH="$(mktemp)"
WSL_ROCM_CONSTRAINTS_PATH="$(mktemp)"
LINUX_CUDA_INPUT_PATH="$(mktemp)"
LINUX_CUDA_RAW_PATH="$(mktemp)"
LINUX_CUDA_NORMALIZED_PATH="$(mktemp)"
WSL_ROCM_INPUT_PATH="$(mktemp)"
WSL_ROCM_RAW_PATH="$(mktemp)"
WSL_ROCM_NORMALIZED_PATH="$(mktemp)"

cleanup() {
  rm -f \
    "${GENERIC_INPUT_PATH}" "${GENERIC_RAW_PATH}" "${GENERIC_NORMALIZED_PATH}" "${GENERIC_CONSTRAINTS_PATH}" \
    "${EXPECTED_PINS_PATH}" "${CANDIDATE_PINS_PATH}" \
    "${LINUX_CUDA_CONSTRAINTS_PATH}" "${WSL_ROCM_CONSTRAINTS_PATH}" \
    "${LINUX_CUDA_INPUT_PATH}" "${LINUX_CUDA_RAW_PATH}" "${LINUX_CUDA_NORMALIZED_PATH}" \
    "${WSL_ROCM_INPUT_PATH}" "${WSL_ROCM_RAW_PATH}" "${WSL_ROCM_NORMALIZED_PATH}"
}

trap cleanup EXIT

write_generic_input() {
  printf './backend\n' >"${GENERIC_INPUT_PATH}"
}

write_profile_input() {
  local profile_name="$1"
  local destination_path="$2"

  PROFILE_NAME="${profile_name}" BACKEND_PYPROJECT_PATH="${BACKEND_DIR}/pyproject.toml" DESTINATION_PATH="${destination_path}" "${PYTHON_BIN}" - <<'PY'
from __future__ import annotations

import os
import tomllib
from pathlib import Path

profile_name = os.environ["PROFILE_NAME"]
pyproject_path = Path(os.environ["BACKEND_PYPROJECT_PATH"])
destination_path = Path(os.environ["DESTINATION_PATH"])
data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

if profile_name == "linux-cuda":
    requirements = data["dependency-groups"]["linux-cuda"]
elif profile_name == "wsl-rocm":
    requirements = data["tool"]["nyaru"]["backend-accelerator-profiles"]["wsl-rocm"]["requirements"]
else:
    raise SystemExit(f"unsupported profile: {profile_name}")

destination_path.write_text("\n".join(requirements) + "\n", encoding="utf-8")
PY
}

read_wsl_rocm_extra_index_url() {
  BACKEND_PYPROJECT_PATH="${BACKEND_DIR}/pyproject.toml" "${PYTHON_BIN}" - <<'PY'
from __future__ import annotations

import os
import tomllib
from pathlib import Path

pyproject_path = Path(os.environ["BACKEND_PYPROJECT_PATH"])
data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
print(data["tool"]["nyaru"]["backend-accelerator-profiles"]["wsl-rocm"]["extra-index-url"])
PY
}

normalize_requirements_file() {
  local raw_path="$1"
  local normalized_path="$2"

  RAW_EXPORT_PATH="${raw_path}" NORMALIZED_EXPORT_PATH="${normalized_path}" "${PYTHON_BIN}" - <<'PY'
from __future__ import annotations

import os
from pathlib import Path

raw_path = Path(os.environ["RAW_EXPORT_PATH"])
normalized_path = Path(os.environ["NORMALIZED_EXPORT_PATH"])

raw_lines = raw_path.read_text(encoding="utf-8").splitlines()
normalized_lines: list[str] = []

for line in raw_lines:
    if line in {".", "-e ."}:
        normalized_lines.append("./backend")
        continue
    normalized_lines.append(line)

normalized_path.write_text(
    "# Generated by ./scripts/export_backend_requirements.sh; do not edit by hand.\n"
    + "\n".join(normalized_lines)
    + "\n",
    encoding="utf-8",
)
PY
}

write_constraints_file() {
  local source_path="$1"
  local destination_path="$2"

  shift 2
  "${PYTHON_BIN}" - "${destination_path}" "${source_path}" "$@" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

pins: dict[str, str] = {}
for source in sys.argv[2:]:
    source_path = Path(source)
    if not source_path.is_file():
        raise SystemExit(f"missing pinned requirements artifact: {source}; use --upgrade to bootstrap")
    for line in source_path.read_text(encoding="utf-8").splitlines():
        normalized = line.strip()
        if not normalized or normalized.startswith(("#", "--")) or normalized == "./backend":
            continue
        name = re.split(r"[= @;\[]", normalized, maxsplit=1)[0]
        name = re.sub(r"[-_.]+", "-", name).lower()
        if name in pins and pins[name] != normalized:
            raise SystemExit(f"conflicting pin for {name}: {pins[name]} vs {normalized}")
        pins[name] = normalized

Path(sys.argv[1]).write_text("\n".join(sorted(pins.values())) + "\n", encoding="utf-8")
PY
}

compile_generic_requirements() {
  write_generic_input
  (
    cd "${ROOT_DIR}"
    uv pip compile "${GENERIC_INPUT_PATH}" \
      --project "${BACKEND_DIR}" \
      --python-version "${PYTHON_VERSION}" \
      --python-platform x86_64-unknown-linux-gnu \
      "${BASE_RESOLUTION_ARGS[@]}" \
      --no-header \
      --no-annotate \
      >"${GENERIC_RAW_PATH}"
  )
  normalize_requirements_file "${GENERIC_RAW_PATH}" "${GENERIC_NORMALIZED_PATH}"
  if ((UPGRADE)); then
    write_constraints_file "${GENERIC_NORMALIZED_PATH}" "${LINUX_CUDA_CONSTRAINTS_PATH}"
    cp "${LINUX_CUDA_CONSTRAINTS_PATH}" "${WSL_ROCM_CONSTRAINTS_PATH}"
  fi
}

compile_linux_cuda_requirements() {
  write_profile_input "linux-cuda" "${LINUX_CUDA_INPUT_PATH}"
  (
    cd "${ROOT_DIR}"
    uv pip compile "${LINUX_CUDA_INPUT_PATH}" \
      --project "${BACKEND_DIR}" \
      --python-version "${PYTHON_VERSION}" \
      --python-platform x86_64-unknown-linux-gnu \
      --constraints "${LINUX_CUDA_CONSTRAINTS_PATH}" \
      --no-header \
      --no-annotate \
      >"${LINUX_CUDA_RAW_PATH}"
  )
  normalize_requirements_file "${LINUX_CUDA_RAW_PATH}" "${LINUX_CUDA_NORMALIZED_PATH}"
}

compile_wsl_rocm_requirements() {
  local extra_index_url
  extra_index_url="$(read_wsl_rocm_extra_index_url)"
  write_profile_input "wsl-rocm" "${WSL_ROCM_INPUT_PATH}"
  (
    cd "${ROOT_DIR}"
    uv pip compile "${WSL_ROCM_INPUT_PATH}" \
      --project "${BACKEND_DIR}" \
      --python-version "${PYTHON_VERSION}" \
      --python-platform x86_64-unknown-linux-gnu \
      --constraints "${WSL_ROCM_CONSTRAINTS_PATH}" \
      --extra-index-url "${extra_index_url}" \
      --index-strategy unsafe-best-match \
      --emit-index-url \
      --no-header \
      --no-annotate \
      >"${WSL_ROCM_RAW_PATH}"
  )
  normalize_requirements_file "${WSL_ROCM_RAW_PATH}" "${WSL_ROCM_NORMALIZED_PATH}"
}

check_pinned_versions() {
  local generated_path="$1"
  local authoritative_path="$2"

  write_constraints_file "${generated_path}" "${CANDIDATE_PINS_PATH}"
  write_constraints_file "${authoritative_path}" "${EXPECTED_PINS_PATH}"
  if ! cmp -s "${CANDIDATE_PINS_PATH}" "${EXPECTED_PINS_PATH}"; then
    printf 'dependency pins changed for %s; use --upgrade --profile all to select new versions\n' "${authoritative_path}" >&2
    return 1
  fi
}

write_generated_file() {
  local generated_path="$1"
  local target_path="$2"

  mkdir -p "$(dirname "${target_path}")"
  cp "${generated_path}" "${target_path}"
  printf 'wrote %s\n' "${target_path}" >&2
}

check_generated_file() {
  local generated_path="$1"
  local target_path="$2"

  if [[ ! -f "${target_path}" ]]; then
    printf 'requirements file is stale or missing: %s\n' "${target_path}" >&2
    return 1
  fi

  if ! cmp -s "${generated_path}" "${target_path}"; then
    printf 'requirements file is stale: %s\n' "${target_path}" >&2
    return 1
  fi

  printf 'requirements file is up to date: %s\n' "${target_path}" >&2
}

# Existing installation artifacts constrain resolution before any solver runs.
BASE_RESOLUTION_ARGS=(--upgrade)
if ((!UPGRADE)); then
  write_constraints_file "${DEFAULT_OUTPUT_PATH}" "${GENERIC_CONSTRAINTS_PATH}"
  BASE_RESOLUTION_ARGS=(--constraints "${GENERIC_CONSTRAINTS_PATH}")
  if ((CUDA_SELECTED)); then
    write_constraints_file "${DEFAULT_OUTPUT_PATH}" "${LINUX_CUDA_CONSTRAINTS_PATH}" "${LINUX_CUDA_OUTPUT_PATH}"
  fi
  if ((ROCM_SELECTED)); then
    write_constraints_file "${DEFAULT_OUTPUT_PATH}" "${WSL_ROCM_CONSTRAINTS_PATH}" "${WSL_ROCM_OUTPUT_PATH}"
  fi
fi

compile_generic_requirements
if ((UPGRADE)) && [[ "${PROFILE}" != all ]] && ! cmp -s "${GENERIC_NORMALIZED_PATH}" "${DEFAULT_OUTPUT_PATH}"; then
  printf '%s\n' 'base pins changed; use --upgrade --profile all to regenerate consistent installation artifacts' >&2
  exit 1
fi
if ((CUDA_SELECTED)); then compile_linux_cuda_requirements; fi
if ((ROCM_SELECTED)); then compile_wsl_rocm_requirements; fi

if ((!UPGRADE)); then
  check_pinned_versions "${GENERIC_NORMALIZED_PATH}" "${DEFAULT_OUTPUT_PATH}"
  if ((CUDA_SELECTED)); then check_pinned_versions "${LINUX_CUDA_NORMALIZED_PATH}" "${LINUX_CUDA_OUTPUT_PATH}"; fi
  if ((ROCM_SELECTED)); then check_pinned_versions "${WSL_ROCM_NORMALIZED_PATH}" "${WSL_ROCM_OUTPUT_PATH}"; fi
fi

if ((CHECK_ONLY)); then
  check_generated_file "${GENERIC_NORMALIZED_PATH}" "${OUTPUT_PATH}"
  if ((CUDA_SELECTED)); then check_generated_file "${LINUX_CUDA_NORMALIZED_PATH}" "${LINUX_CUDA_OUTPUT_PATH}"; fi
  if ((ROCM_SELECTED)); then check_generated_file "${WSL_ROCM_NORMALIZED_PATH}" "${WSL_ROCM_OUTPUT_PATH}"; fi
  exit 0
fi

write_generated_file "${GENERIC_NORMALIZED_PATH}" "${OUTPUT_PATH}"
if ((CUDA_SELECTED)); then write_generated_file "${LINUX_CUDA_NORMALIZED_PATH}" "${LINUX_CUDA_OUTPUT_PATH}"; fi
if ((ROCM_SELECTED)); then write_generated_file "${WSL_ROCM_NORMALIZED_PATH}" "${WSL_ROCM_OUTPUT_PATH}"; fi
