from __future__ import annotations

import json
import os
import re
import shlex
import shutil

import pytest
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPORT_SCRIPT = REPO_ROOT / "scripts" / "export_backend_requirements.sh"
OPENAPI_EXPORT_SCRIPT = REPO_ROOT / "scripts" / "export_openapi_schema.py"
WEB_DIR = REPO_ROOT / "web"
CUDA_PROFILE_PATH = REPO_ROOT / "backend" / "requirements-linux-cuda.txt"
WSL_ROCM_PROFILE_PATH = REPO_ROOT / "backend" / "requirements-wsl-rocm.txt"
WSL_ROCM_INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install_backend_wsl_rocm.sh"
DEV_COMMON_SCRIPT = REPO_ROOT / "scripts" / "_dev_common.sh"

ACCELERATOR_PACKAGE_NAMES = {
    "ctranslate2",
    "faster-whisper",
    "torch",
    "torchaudio",
    "torchvision",
    "whisperx",
}
ACCELERATOR_PACKAGE_PREFIXES = ("nvidia-",)
PACKAGE_NAME_PATTERN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)")


def _run_export(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(EXPORT_SCRIPT), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _run_wsl_rocm_install(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(WSL_ROCM_INSTALL_SCRIPT), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _run_openapi_export(output_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(OPENAPI_EXPORT_SCRIPT), "--output", str(output_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _read_requirement_entries(path: Path) -> list[str]:
    return [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#") and not line.startswith("--")
    ]


def _package_names(lines: list[str]) -> set[str]:
    package_names: set[str] = set()
    for line in lines:
        match = PACKAGE_NAME_PATTERN.match(line)
        if match is None:
            continue
        package_name = match.group(1)
        if package_name.startswith((".", "/")):
            continue
        package_names.add(package_name.lower())
    return package_names


def _package_versions(lines: list[str]) -> dict[str, str]:
    package_versions: dict[str, str] = {}
    for line in lines:
        match = PACKAGE_NAME_PATTERN.match(line)
        if match is None:
            continue
        package_name = match.group(1).lower()
        if package_name.startswith((".", "/")) or "==" not in line:
            continue
        package_versions[package_name] = line.strip()
    return package_versions


def test_export_script_generates_accelerator_neutral_repo_root_installable_requirements(tmp_path) -> None:
    output_path = tmp_path / "requirements.txt"

    result = _run_export("--output", str(output_path))

    assert result.returncode == 0, result.stderr or result.stdout
    assert output_path.exists()

    lines = output_path.read_text(encoding="utf-8").splitlines()
    package_names = _package_names(lines)

    assert "./backend" in lines
    assert "." not in lines
    assert "-e ." not in lines
    assert package_names.isdisjoint(ACCELERATOR_PACKAGE_NAMES)
    assert not any(name.startswith(ACCELERATOR_PACKAGE_PREFIXES) for name in package_names)


def test_export_script_check_detects_stale_requirements_file(tmp_path) -> None:
    output_path = tmp_path / "requirements.txt"

    generate_result = _run_export("--output", str(output_path))
    assert generate_result.returncode == 0, generate_result.stderr or generate_result.stdout

    check_result = _run_export("--check", "--output", str(output_path))
    assert check_result.returncode == 0, check_result.stderr or check_result.stdout

    output_path.write_text(output_path.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")

    stale_result = _run_export("--check", "--output", str(output_path))

    assert stale_result.returncode == 1
    assert "stale" in (stale_result.stderr or stale_result.stdout).lower()


@pytest.fixture
def export_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "checkout with spaces"
    (root / "scripts").mkdir(parents=True)
    backend = root / "backend"
    backend.mkdir()
    shutil.copy2(EXPORT_SCRIPT, root / "scripts" / EXPORT_SCRIPT.name)
    for source in (REPO_ROOT / "backend").glob("requirements*.txt"):
        shutil.copy2(source, backend / source.name)
    shutil.copy2(REPO_ROOT / "backend" / "pyproject.toml", backend / "pyproject.toml")
    fake_bin = root / "bin"
    fake_bin.mkdir()
    python = backend / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text(f"#!/bin/sh\nexec {shlex.quote(sys.executable)} \"$@\"\n")
    python.chmod(0o755)
    system_python = fake_bin / "python3"
    system_python.write_text("#!/bin/sh\necho unexpected-system-python >&2\nexit 77\n")
    system_python.chmod(0o755)
    fake_uv = fake_bin / "uv"
    fake_uv.write_text(f"#!{sys.executable}\n" + r'''import json
import os
import sys
from pathlib import Path
args = sys.argv[1:]
root = Path.cwd()
with (root / "uv-calls.jsonl").open("a") as log:
    log.write(json.dumps(args) + "\n")
source = Path(args[2]).read_text()
profile = "" if "./backend" in source else ("-wsl-rocm" if "rocm" in source else "-linux-cuda")
artifact = root / "snapshots" / f"requirements{profile}.txt"
constraints = "\n".join(Path(args[i+1]).read_text() for i, arg in enumerate(args) if arg == "--constraints")
assert not any(line.startswith(("#", "./", "--")) for line in constraints.splitlines())
if "fastapi>=99" in (root / "backend/pyproject.toml").read_text() and "fastapi==" in constraints:
    print("No solution: declared minimum conflicts with fixed pin", file=sys.stderr)
    sys.exit(1)
if os.environ.get("FAKE_UV_FAIL"):
    sys.exit(42)
output = artifact.read_text().split("\n", 1)[1]
if "certifi==" not in constraints:
    output = output.replace("certifi==2026.6.17", "certifi==2099.1.1")
if profile and "certifi==2099.1.1" in constraints:
    output = output.replace("certifi==2026.6.17", "certifi==2099.1.1")
if (not profile and '"pytest>=8"' in (root / "backend/pyproject.toml").read_text()) or "pytest>=8\n" in source:
    output += "pytest==9.1.1\n"
print(output, end="")
''')
    fake_uv.chmod(0o755)
    shutil.copytree(backend, root / "snapshots", ignore=shutil.ignore_patterns(".venv"))
    monkeypatch.delenv("BACKEND_PYTHON", raising=False)
    monkeypatch.setenv("PATH", f"{fake_bin}{os.pathsep}{os.environ['PATH']}")
    return root


def _run_checkout(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(root / "scripts" / EXPORT_SCRIPT.name), *args], cwd=root,
                          capture_output=True, text=True, check=False)


@pytest.mark.parametrize("profile,count", [("base", 1), ("linux-cuda", 2), ("wsl-rocm", 2), ("all", 3)])
def test_check_uses_existing_pins_and_only_selected_profiles(export_checkout: Path, profile: str, count: int) -> None:
    before = {p: p.read_bytes() for p in (export_checkout / "backend").glob("requirements*.txt")}
    result = _run_checkout(export_checkout, "--check", "--profile", profile)
    assert result.returncode == 0, result.stderr
    calls = [json.loads(line) for line in (export_checkout / "uv-calls.jsonl").read_text().splitlines()]
    assert len(calls) == count
    assert all("--constraints" in call for call in calls)
    assert all(call[call.index("--python-platform") + 1] == "x86_64-unknown-linux-gnu" for call in calls)
    assert all(call[call.index("--python-version") + 1] == "3.11" for call in calls)
    if profile in {"base", "linux-cuda"}:
        assert not any("--extra-index-url" in call for call in calls)
    assert before == {p: p.read_bytes() for p in before}


def test_export_script_prefers_the_backend_virtualenv_python_over_system_python(export_checkout: Path) -> None:
    result = _run_checkout(export_checkout, "--check", "--profile", "base")
    assert result.returncode == 0, result.stderr


def test_export_honors_explicit_python(export_checkout: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BACKEND_PYTHON", sys.executable)
    (export_checkout / "backend/.venv/bin/python").write_text("#!/bin/sh\nexit 76\n")
    result = _run_checkout(export_checkout, "--check", "--profile", "base")
    assert result.returncode == 0, result.stderr


def test_export_reports_missing_explicit_interpreter(export_checkout: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BACKEND_PYTHON", str(export_checkout / "absent-python"))
    result = _run_checkout(export_checkout, "--check")
    assert result.returncode == 1
    assert "required command not found" in result.stderr


def test_export_rejects_incompatible_declaration_without_rewriting(export_checkout: Path) -> None:
    pyproject = export_checkout / "backend/pyproject.toml"
    pyproject.write_text(pyproject.read_text().replace("fastapi>=0.115.0", "fastapi>=99"))
    before = (export_checkout / "backend/requirements.txt").read_bytes()
    result = _run_checkout(export_checkout, "--check", "--profile", "base")
    assert result.returncode == 1
    assert "No solution" in result.stderr
    assert (export_checkout / "backend/requirements.txt").read_bytes() == before


@pytest.mark.parametrize("problem", ["missing", "conflict"])
def test_export_rejects_missing_or_conflicting_pins_before_resolution(export_checkout: Path, problem: str) -> None:
    profile = export_checkout / "backend/requirements-linux-cuda.txt"
    if problem == "missing":
        profile.unlink()
    else:
        profile.write_text(profile.read_text().replace("certifi==2026.6.17", "certifi==2099.1.1"))
    result = _run_checkout(export_checkout, "--profile", "linux-cuda")
    assert result.returncode == 1
    assert ("missing pinned" if problem == "missing" else "conflicting pin") in result.stderr
    assert not (export_checkout / "uv-calls.jsonl").exists()


@pytest.mark.parametrize("args", [("--check", "--upgrade"), ("--profile", "linux-cuda", "--output", "out.txt"),
                                  ("--output", "out.txt", "--profile", "all")])
def test_export_rejects_incompatible_options(export_checkout: Path, args: tuple[str, ...]) -> None:
    result = _run_checkout(export_checkout, *args)
    assert result.returncode == 1
    assert not (export_checkout / "uv-calls.jsonl").exists()


def test_output_uses_authoritative_base_pins(export_checkout: Path) -> None:
    output = export_checkout / "custom.txt"
    result = _run_checkout(export_checkout, "--output", str(output))
    assert result.returncode == 0, result.stderr
    assert output.read_bytes() == (export_checkout / "backend/requirements.txt").read_bytes()
    assert _run_checkout(export_checkout, "--check", "--output", str(output)).returncode == 0
    output.write_text(output.read_text() + "# drift\n")
    assert _run_checkout(export_checkout, "--check", "--output", str(output)).returncode == 1


def test_upgrade_requires_all_profiles_when_base_changes(export_checkout: Path) -> None:
    before = (export_checkout / "backend/requirements.txt").read_bytes()
    result = _run_checkout(export_checkout, "--upgrade", "--profile", "base")
    assert result.returncode == 1
    assert "--profile all" in result.stderr
    assert (export_checkout / "backend/requirements.txt").read_bytes() == before


def test_upgrade_bootstraps_all_artifacts_with_candidate_base_constraints(export_checkout: Path) -> None:
    for path in (export_checkout / "backend").glob("requirements*.txt"):
        path.unlink()
    result = _run_checkout(export_checkout, "--upgrade")
    assert result.returncode == 0, result.stderr
    for path in (export_checkout / "backend").glob("requirements*.txt"):
        assert "certifi==2099.1.1" in path.read_text()
    rocm = (export_checkout / "backend/requirements-wsl-rocm.txt").read_text()
    assert "--extra-index-url https://repo.radeon.com" in rocm
    assert "torch @ https://repo.radeon.com" in rocm


def test_solver_failure_keeps_status_and_artifacts(export_checkout: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_UV_FAIL", "1")
    temporary = export_checkout / "temporary"
    temporary.mkdir()
    monkeypatch.setenv("TMPDIR", str(temporary))
    before = (export_checkout / "backend/requirements.txt").read_bytes()
    result = _run_checkout(export_checkout, "--profile", "base")
    assert result.returncode == 42
    assert list(temporary.iterdir()) == []
    assert (export_checkout / "backend/requirements.txt").read_bytes() == before


def test_openapi_export_is_deterministic_and_contains_workstation_task_contract(tmp_path) -> None:
    first_output_path = tmp_path / "first-openapi.json"
    second_output_path = tmp_path / "second-openapi.json"

    first_result = _run_openapi_export(first_output_path)
    second_result = _run_openapi_export(second_output_path)

    assert first_result.returncode == 0, first_result.stderr or first_result.stdout
    assert second_result.returncode == 0, second_result.stderr or second_result.stdout
    assert first_output_path.read_bytes() == second_output_path.read_bytes()

    schema = json.loads(first_output_path.read_text(encoding="utf-8"))
    assert "/api/v2/tasks" in schema["paths"]


def test_openapi_declares_queue_conflicts_as_current_queue_snapshots(tmp_path) -> None:
    output_path = tmp_path / "workstation-openapi.json"

    result = _run_openapi_export(output_path)

    assert result.returncode == 0, result.stderr or result.stdout
    schema = json.loads(output_path.read_text(encoding="utf-8"))
    response = schema["paths"]["/api/v2/queue/order"]["put"]["responses"]["409"]
    assert response["content"]["application/json"]["schema"] == {"$ref": "#/components/schemas/QueueSnapshotResponse"}


def test_checked_in_workstation_contract_matches_the_backend_openapi_export(tmp_path) -> None:
    output_path = tmp_path / "workstation-openapi.json"

    result = _run_openapi_export(output_path)

    assert result.returncode == 0, result.stderr or result.stdout
    assert output_path.read_bytes() == (WEB_DIR / "openapi.json").read_bytes()


def test_checked_in_linux_cuda_profile_artifact_contains_cuda_runtime_requirements() -> None:
    assert CUDA_PROFILE_PATH.exists(), f"missing profile artifact: {CUDA_PROFILE_PATH}"

    lines = _read_requirement_entries(CUDA_PROFILE_PATH)
    package_names = _package_names(lines)

    assert "torch" in package_names
    assert "whisperx" in package_names
    assert any(name.startswith(ACCELERATOR_PACKAGE_PREFIXES) for name in package_names)
    assert not any("rocm" in line.lower() for line in lines)


def test_checked_in_wsl_rocm_profile_artifact_contains_rocm_torch_without_nvidia_packages() -> None:
    assert WSL_ROCM_PROFILE_PATH.exists(), f"missing profile artifact: {WSL_ROCM_PROFILE_PATH}"

    lines = _read_requirement_entries(WSL_ROCM_PROFILE_PATH)
    package_names = _package_names(lines)

    assert "torch" in package_names
    assert "whisperx" in package_names
    assert any("rocm" in line.lower() for line in lines)
    assert not any(name.startswith(ACCELERATOR_PACKAGE_PREFIXES) for name in package_names)


def test_wsl_rocm_installer_dry_run_includes_hip_ctranslate2_build() -> None:
    result = _run_wsl_rocm_install("--dry-run")

    assert result.returncode == 0, result.stderr or result.stdout
    output = result.stdout + result.stderr
    assert "build_ctranslate2_wsl_rocm.sh" in output
    assert "-DWITH_HIP=ON" in output
    assert "-DCMAKE_HIP_COMPILER=/opt/rocm/lib/llvm/bin/clang++" in output
    assert "-DCMAKE_PREFIX_PATH=/opt/rocm" in output


def test_wsl_rocm_installer_creates_the_python_311_venv_before_validating_requirements() -> None:
    result = _run_wsl_rocm_install("--dry-run")

    assert result.returncode == 0, result.stderr or result.stdout
    output = result.stdout + result.stderr
    assert output.index("uv venv") < output.index("export_backend_requirements.sh --check --profile wsl-rocm") < output.index("uv pip sync")


def test_shared_runtime_environment_unconditionally_exports_wsl_dxg_detection() -> None:
    script = DEV_COMMON_SCRIPT.read_text(encoding="utf-8")

    assert "enable_wsl_rocm_dxg_detection() {\n  export HSA_ENABLE_DXG_DETECTION=1\n}" in script


def test_profile_artifacts_keep_shared_dependency_pins_consistent_with_base_artifact() -> None:
    base_versions = _package_versions(_read_requirement_entries(REPO_ROOT / "backend" / "requirements.txt"))

    for profile_path in (CUDA_PROFILE_PATH, WSL_ROCM_PROFILE_PATH):
        profile_versions = _package_versions(_read_requirement_entries(profile_path))
        conflicting_pins = {
            package_name: (base_versions[package_name], profile_versions[package_name])
            for package_name in sorted(base_versions.keys() & profile_versions.keys())
            if base_versions[package_name] != profile_versions[package_name]
        }

        assert conflicting_pins == {}, (
            f"shared dependencies diverged between {profile_path.name} and requirements.txt: {conflicting_pins}"
        )


@pytest.mark.parametrize("profile", ["linux-cuda", "wsl-rocm"])
def test_installer_dry_run_checks_only_its_profile(profile: str) -> None:
    result = subprocess.run([str(REPO_ROOT / "scripts" / f"install_backend_{profile.replace('-', '_')}.sh"), "--dry-run"],
                            cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    output = result.stdout + result.stderr
    assert f"export_backend_requirements.sh --check --profile {profile}" in output
    assert output.index("uv venv") < output.index("export_backend_requirements.sh") < output.index("uv pip sync")


def test_missing_base_artifact_cannot_bootstrap_without_upgrade(export_checkout: Path) -> None:
    (export_checkout / "backend/requirements.txt").unlink()
    result = _run_checkout(export_checkout, "--output", str(export_checkout / "custom.txt"))
    assert result.returncode == 1
    assert "missing pinned" in result.stderr
    assert not (export_checkout / "uv-calls.jsonl").exists()


@pytest.mark.parametrize("profile", ["base", "linux-cuda", "wsl-rocm", "all", "output"])
def test_new_unpinned_runtime_dependency_requires_upgrade(export_checkout: Path, profile: str) -> None:
    pyproject = export_checkout / "backend/pyproject.toml"
    pyproject.write_text(pyproject.read_text().replace("dependencies = [", 'dependencies = [\n  "pytest>=8",', 1))
    before = {p: p.read_bytes() for p in (export_checkout / "backend").glob("requirements*.txt")}
    output = export_checkout / "custom.txt"
    args = ("--output", str(output)) if profile == "output" else ("--profile", profile)
    result = _run_checkout(export_checkout, *args)
    assert result.returncode == 1, result.stderr
    assert "--upgrade" in result.stderr
    assert before == {p: p.read_bytes() for p in before}
    assert not output.exists()


@pytest.mark.parametrize("profile", ["linux-cuda", "wsl-rocm"])
def test_new_unpinned_profile_dependency_blocks_all_publication(export_checkout: Path, profile: str) -> None:
    pyproject = export_checkout / "backend/pyproject.toml"
    declaration = "linux-cuda = [" if profile == "linux-cuda" else "requirements = ["
    pyproject.write_text(pyproject.read_text().replace(declaration, declaration + '\n  "pytest>=8",', 1))
    base = export_checkout / "backend/requirements.txt"
    base.write_text(base.read_text() + "# preserve this until all candidates pass\n")
    before = {p: p.read_bytes() for p in (export_checkout / "backend").glob("requirements*.txt")}
    result = _run_checkout(export_checkout, "--profile", "all")
    assert result.returncode == 1, result.stderr
    assert "--upgrade" in result.stderr
    assert before == {p: p.read_bytes() for p in before}


def test_generation_accepts_comment_whitespace_and_pin_order_changes(export_checkout: Path) -> None:
    base = export_checkout / "backend/requirements.txt"
    base.write_text("# operator note\n" + "\n".join("  " + line + "  " for line in reversed(base.read_text().splitlines())) + "\n")
    result = _run_checkout(export_checkout, "--profile", "all")
    assert result.returncode == 0, result.stderr
    assert base.read_bytes() == (export_checkout / "snapshots/requirements.txt").read_bytes()


def test_explicit_upgrade_can_select_new_runtime_dependency(export_checkout: Path) -> None:
    pyproject = export_checkout / "backend/pyproject.toml"
    pyproject.write_text(pyproject.read_text().replace("dependencies = [", 'dependencies = [\n  "pytest>=8",', 1))
    result = _run_checkout(export_checkout, "--upgrade", "--profile", "all")
    assert result.returncode == 0, result.stderr
    assert "pytest==9.1.1" in (export_checkout / "backend/requirements.txt").read_text()
