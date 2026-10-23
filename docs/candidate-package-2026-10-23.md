# Unified candidate packages and isolated acceptance (2026-10-23)

**Local packaging and isolated workflow acceptance are complete; the installed App/formal data were not replaced or switched.** [中文](candidate-package-2026-10-23.zh-CN.md). This run packages the M03/M24 recovery fixes without additional application-source changes. Source is the isolated `codex/unified-architecture-2026-10-22` worktree, base HEAD `428ba833193db888c6b049ac2983abe1b2ecae17`; implementation remains uncommitted and cannot be reconstructed from HEAD alone.

## 1. Deliverables and identity

| Artifact | Exact location/identity |
| --- | --- |
| Candidate App | `/Users/drm/.cache/nyaru-clipper/unified-native-build-20261023-01/Nyaru Clipper.app` |
| [Candidate App ZIP](/Users/drm/.cache/nyaru-clipper/unified-native-build-20261023-01/Nyaru-Clipper-unified-candidate-20261023-01.zip) | SHA256 `7a5c3cad144c57dc74bda2391e157452b69418d1476fdd40e2895f3b310ad6a9`; 633635601 bytes |
| Independent recovery directory | `/Users/drm/.cache/nyaru-clipper/unified-recovery-20261023-01`; fixed for this run's new ownership epochs |
| [Independent recovery ZIP](/Users/drm/.cache/nyaru-clipper/unified-recovery-20261023-01.zip) | SHA256 `47f34e5b0d577b20be6d4990bdfd6e093c946159581b4cd1a6035b548b969082` |
| Both bundle.json files | App `Contents/Resources/recovery/bundle.json` and standalone directory match, SHA256 `1ce64b4effcc38a592d90b12e879dcc02a990a62316af8fbdc8e23e16b31ff12` |
| Native executable | SHA256 `75921310a9f3e903c047ae1b1b2d412ada8a4b53ef68cf3c4f37d1f989c74017` |
| Frozen backend | SHA256 `0807970e0f22d950b0736542dbdd4dd23bfa21b6d535504bd98c32f2d3690798` |

Display version remains **0.1.19 build27**, which is not candidate identity. This is an ad-hoc signed local Apple Silicon/minimum macOS 27.0 candidate, without notarization or publication. App ZIP CRC passed; **5406 extracted files and modes** match, and both original/extracted Apps pass `codesign --verify --deep --strict`.

All **3619 resource hashes** match across bundled/standalone/extracted recovery. Nine reader modules (including `recovery_thaw_resume.py`) and 150 archived helper modules match current source; extracted Python/helper executable bits and reader startup passed. The independent path/hash was fixed before takeover and never relocated/replaced. Recovery packages contain no formal credentials or task data.

Build input matches the [202-file source seal](/Users/drm/project/nyaru-clipper/.omo/evidence/m03-m24-20261023-source.json), digest `1e10e6b3d72ea396b8b0223c1dea3251cfbbf807c51062407b1e31e2078df7ba`. Only this run's documentation changed subsequently; the old seal is not a complete post-documentation working-tree digest.

## 2. Actual acceptance

| Scenario | Actual entry and outcome |
| --- | --- |
| Empty-root native start/reopen | New App with explicit `--unified-runtime`; both normal quits exit0, helpers exit and ready files disappear; ports 52006→52198, zero tasks and paused queue |
| Real frozen takeover | App backend `--unified-cli`/`--migration-cli` executes init, pin, public settings, register, prepare, verify, takeover, category and recipe export; HTTP verifies saved draft/templates/paused queue. Development Python only creates fixtures and inspects DB |
| R0/R1 | Independent frozen Python `-I -S -B` performs six-root same-epoch snapshot/read-only/thaw; whole group withdrawn/thawed, old bytes/inodes/modes/flags exact; R0 never activated |
| R1 kill/resume | Actual SIGKILL after group thawed but before final receipt, exit -9; pinned `thaw-intent.json` via `interrupted_thaw` resumes independently with exit0, demonstrating that the delivered package contains the fix |
| Archived-helper rollback/reopen | Independent old-format archive/working copy created before sealing; saved revision1 readable, online-processing POST403; helper/launcher exit, original source unchanged |
| R2 | Frozen takeover followed by revision2 save; snapshot/read-only export identical; thaw exit2, old source/new DB stay immutable, no thaw permission receipt |
| Native migrated save/reopen | In another new root, task `987473f590455e688376ce7d1f63fc55` advances from r2 to **r3** in the native window, text “新候选包原生接管验收：保存并重开。”; normal quit/same runtime+guard reopen changes port 52506→52607, retains same task/r3/paused queue and identical full HTTP document; both exit0 and helpers exit |
| Independent native-draft recovery | After native shutdown, fresh complete snapshot; both HTTP documents=DB=independent export; r3 body SHA256 `ed3d5139f18e3c34fbaf74d507024c781a9ec4e4a49d0f6c6b3b68504eb8c8fd`; R2 thaw still exits2 |

Media is newly generated real five-second H264; subtitles/templates are controlled fixtures. No ASR, online translation, real live capture or GPU was rerun. The migrated native fixture explicitly uses a missing model path, hence its model warning; empty-root startup references the real App-bundled small model. The older 1538/46 regression counts are not presented as rerun here.

## 3. Startup and rollback boundaries

**Explicitly pass an isolated runtime; do not double-click or omit arguments.** Omission still selects the compatibility default data path. This is the tested, writable independent empty root, not a sealed sample:

```bash
"/Users/drm/.cache/nyaru-clipper/unified-native-build-20261023-01/Nyaru Clipper.app/Contents/MacOS/Nyaru Clipper" \
  --unified-runtime /Users/drm/.cache/nyaru-clipper/packaged-native-empty-20261023-01/runtime.json
```

For another root, follow the [runtime/rollback guide](unified-runtime-guide.md) with new data/credential directories. Taken-over roots require their fixed runtime and guard. These R2 samples are now sealed: **do not launch or unseal them**:

- `/Users/drm/.cache/nyaru-clipper/candidate-package-20261023-recovery-03/R2`
- `/Users/drm/.cache/nyaru-clipper/candidate-package-20261023-native-guarded-01/R2`

R0/R1 must withdraw the whole group before restoring old permissions. R2 retains seals and uses snapshot/read-only export or an independent old-format working copy. Permission restoration is still per-file; changed originals stop recovery and preserve new data. Never silently rebind an existing epoch's bundle path/hash. ZIP extraction to a new verified location can precede a new epoch; it does not authorize relocating an existing pinned directory. The 22 October build-04 sample reader/build-05 App remain unchanged and are not replaced by this package.

## 4. Protection, evidence and pending qualification

Before/after build and acceptance, all **1496 installed-App file content hashes** match; **6815 formal-data metadata entries** (relative path, mode, size, mtime, inode, flags) match. Formal-data bodies/credential plaintext were not read; this is not a full data-content hash claim. All owned App/API/helper processes ended; R2 seals and failed attempts remain retained.

- [Build log](/Users/drm/project/nyaru-clipper/.omo/evidence/candidate-package-20261023-build.log), [App/ZIP identity](/Users/drm/project/nyaru-clipper/.omo/evidence/candidate-package-20261023-app-manifest.json)
- [Empty native receipt](/Users/drm/project/nyaru-clipper/.omo/evidence/candidate-package-20261023-native-empty.json), [native migrated save/reopen](/Users/drm/project/nyaru-clipper/.omo/evidence/candidate-package-20261023-native-guarded.json)
- [Recovery receipt](/Users/drm/project/nyaru-clipper/.omo/evidence/candidate-package-20261023-recovery/receipt.md), [detailed frozen commands/artifacts](../.omo/evidence/candidate-package-20261023-recovery/report.md)
- Formal environment [before](/Users/drm/project/nyaru-clipper/.omo/evidence/candidate-package-20261023-formal-before.json)/[after](/Users/drm/project/nyaru-clipper/.omo/evidence/candidate-package-20261023-formal-after.json), [main-session final receipt](/Users/drm/project/nyaru-clipper/.omo/evidence/candidate-package-20261023-receipt.md)

Failed recovery-01 (missing public settings correctly rejected) and recovery-02 (QA copied immutable directories into the helper archive) remain. Corrected fixtures passed in fresh recovery-03 without product-source changes.

M03 remains local_passed, M24 partial; matrix stays **22/3/3**. Controlled OS reboot, boot-time protection ordering/other platform profiles, CUDA/WSL ROCm, Windows AMF, real live capture, notarization/cross-machine qualification gained no acceptance; P6 stays planned. No formal install/migration, commit/push/merge occurred.
