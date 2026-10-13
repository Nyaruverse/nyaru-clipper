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
| Failure fixture | `seed_failure_fixture.py` | static frontend fixture seeded/cleaned by smoke |

## CONVENTIONS

- Entry scripts resolve repo paths from `BASH_SOURCE`; extend the corresponding sourced helper rather than duplicating setup.
- Profile installation creates/reuses Python 3.11 `backend/.venv` before checking generated requirements, then uses `uv pip sync`. Both installers support `--dry-run`.
- WSL installation additionally builds HIP CTranslate2; inspect the build script's architecture detection/override before changing GPU flags.
- API/worker scripts execute the existing venv interpreter directly; they do not install dependencies on startup.
- Shared dev setup exports `HSA_ENABLE_DXG_DETECTION=1`; WSL defaults `HF_HUB_DISABLE_XET=1`. Preserve operator overrides for data/cache/API/web paths.
- Requirements `--check` compiles into temporary files and compares; it may resolve dependencies over the network.
- OpenAPI export requires a backend-capable Python interpreter and an existing output parent directory; frontend generation consumes that JSON.

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
```

## ANTI-PATTERNS / COVERAGE LIMITS

- Host smoke starts a process group with `setsid`; do not assume macOS portability.
- Downstream smoke currently selects missing `web/e2e/task-flow.spec.ts`; the release path is not validated while this selection remains stale.
- Smoke's backend E2E and browser routes use fakes; readiness and mocked flows do not validate live ASR, downloads, or proofreading.
- Keep EXIT/INT/TERM cleanup of child processes and seeded fixtures when changing smoke lifecycle.
- `pnpm --dir web api:check` regenerates before running a Git diff; it writes generated artifacts and requires Git metadata.
- `README.md` in this directory still describes reserved scaffolding; inspect actual scripts for the current contract.
