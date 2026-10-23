# SCRIPTS KNOWLEDGE BASE

## OVERVIEW

Sourced Bash helpers define installation, development environment, release-smoke lifecycle, and generated-artifact workflows.

## WHERE TO LOOK

| Task | Location | Notes |
| --- | --- | --- |
| Shared dev env | `_dev_common.sh` | repo `.bin` PATH, storage/cache paths, WSL compatibility, readiness polling |
| Dev processes | `dev_up.sh`, `dev_api.sh`, `dev_worker.sh`, `dev_web.sh` | combined child cleanup or individual services |
| Profile install | `_backend_profile_common.sh`, `install_backend_linux_cuda.sh`, `install_backend_wsl_rocm.sh` | base + profile requirements and existing venv |
| HIP build/doctor | `build_ctranslate2_wsl_rocm.sh`, `check_wsl_rocm.sh` | pinned CTranslate2 HIP build; runtime capability check |
| Requirements export | `export_backend_requirements.sh` | compile/normalize base and platform artifacts; `--output` selects base only |
| OpenAPI export | `export_openapi_schema.py` | recursively sorted object keys, preserved list order |
| Smoke common | `_release_smoke_common.sh` | health/readiness/tool assertions and downstream checks |
| Smoke entry | `release_smoke.sh`, `release_smoke_non_docker.sh`, `release_smoke_wsl_rocm.sh`, `release_smoke_docker.sh` | alias, host, ROCm doctor, compose |
| Companion smoke | `release_smoke_companion.sh` | existing temporary parent, optional candidate frozen backend, real same-origin page/API |
| Failure fixture | `seed_failure_fixture.py` | static frontend fixture seeded/cleaned by smoke |

## CONVENTIONS

- Entry scripts resolve repo paths from `BASH_SOURCE`; extend the corresponding sourced helper rather than duplicating setup.
- Profile installation creates/reuses Python 3.11 `backend/.venv` before checking generated requirements, then uses `uv pip sync`. Both installers support `--dry-run`.
- WSL installation additionally builds HIP CTranslate2; inspect the build script's architecture detection/override before changing GPU flags.
- API/worker scripts execute the existing venv interpreter directly; they do not install dependencies on startup.
- Shared dev setup exports `HSA_ENABLE_DXG_DETECTION=1`; WSL defaults `HF_HUB_DISABLE_XET=1`. Preserve operator overrides for data/cache/API/web paths.
- Requirements checks constrain resolution from the checked-in fixed runtime artifacts before comparing temporary output; package metadata may need cache/network. `--profile base|linux-cuda|wsl-rocm|all` selects base plus only the needed accelerator profile; default is all. Only explicit `--upgrade` permits pin-set changes, and changed base pins require all-profile regeneration. `uv.lock` retains its separate development role.
- OpenAPI export requires a backend-capable Python interpreter and an existing output parent directory; frontend generation consumes that JSON.
- API startup/smoke share `wait_for_api_readiness`: HTTP200 and `status=ok,database=ok`; Compose probes `/api/health`. GPU warnings remain non-blocking.
- Downstream smoke uses the prepared `BACKEND_PYTHON` (otherwise the backend venv), full frontend unit/build and five current workstation specs. Frontend commands run from `web/` through Corepack when available. Companion uses its independent config with no Vite webServer and is excluded from the main config.
- Companion smoke removes only its own unique child directory and stops/waits its own child process; the existing caller-provided temporary parent is preserved. It checks empty jobs/settings UI without tasks, models, providers or credentials.

## COMMANDS

From repository root:

```bash
./scripts/install_backend_linux_cuda.sh --dry-run
./scripts/install_backend_wsl_rocm.sh --dry-run
./scripts/export_backend_requirements.sh --check
pnpm --dir web api:generate
./scripts/check_wsl_rocm.sh
./scripts/release_smoke_non_docker.sh
./scripts/release_smoke_wsl_rocm.sh
./scripts/release_smoke_docker.sh
./scripts/release_smoke_companion.sh /path/to/existing/temp-parent
```

## ANTI-PATTERNS / COVERAGE LIMITS

- Host smoke starts a process group with `setsid`; do not assume macOS portability.
- Linux/WSL/Docker entries need matching platform acceptance; macOS shared-suite/Companion checks do not establish GPU or full-platform acceptance.
- Smoke's backend E2E and browser routes use fakes; readiness and mocked flows do not validate live ASR, downloads, or proofreading.
- Keep EXIT/INT/TERM cleanup of child processes and seeded fixtures when changing smoke lifecycle.
- `pnpm --dir web api:check` regenerates before running a Git diff; it writes generated artifacts and requires Git metadata.
- `README.md` in this directory still describes reserved scaffolding; inspect actual scripts for the current contract.
