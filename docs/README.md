# Documentation Index

Latest local candidate: [App02 historical-task fixes, repackaging and frozen-package revalidation](candidate-fixes-2026-10-23.md), with new hashes,25/25 historical-copy scenarios, real-source/native save/reopen and independent recovery evidence. No formal App replacement or data cutover.

This directory contains the current MVP documentation set for the Bilibili VTuber workstation.

Start here for setup and local deployment:

- `deployment-guide.md`: English deployment guide, includes the dedicated WSL + ROCm install, doctor, shared runtime, and smoke path
- `deployment-guide.zh-CN.md`: Chinese deployment guide, includes the dedicated WSL + ROCm install, doctor, shared runtime, and smoke path

Available documents:

- [Unified architecture design: Option B](superpowers/specs/2026-10-22-unified-architecture-design.md) and [phased implementation plan](superpowers/plans/2026-10-22-unified-architecture.md): retain desktop and GPU workstation capabilities, define migration boundaries, A1-A12 acceptance and R0-R2 rollback; planned, not implemented. See the [Chinese design](superpowers/specs/2026-10-22-unified-architecture-design.zh-CN.md) and [Chinese plan](superpowers/plans/2026-10-22-unified-architecture.zh-CN.md).

- [Eight-phase improvement rollup](/Users/drm/project/nyaru-clipper/docs/code-improvement-rollup-2026-10-21.md) and [Chinese counterpart](/Users/drm/project/nyaru-clipper/docs/code-improvement-rollup-2026-10-21.zh-CN.md):44/44 bounded acceptance, cumulative changes, portable evidence summary and commit exclusions

- [project-handoff.md](project-handoff.md): Current local companion/macOS handoff, evidence, runtime snapshot and next actions
- [project-handoff.zh-CN.md](project-handoff.zh-CN.md): Chinese handoff

- [Code and Architecture Improvement Plan (2026-10-20)](/Users/drm/project/nyaru-clipper/docs/code-improvement-plan-2026-10-20.md): All 44 findings from six audit rounds, priorities, work packages, acceptance criteria and current implementation status
- [Chinese improvement plan](/Users/drm/project/nyaru-clipper/docs/code-improvement-plan-2026-10-20.zh-CN.md)
- [Phase-one results](/Users/drm/project/nyaru-clipper/docs/phase1-improvement-results-2026-10-21.md) and [Chinese counterpart](/Users/drm/project/nyaru-clipper/docs/phase1-improvement-results-2026-10-21.zh-CN.md)
- [Phase-two and combined results](/Users/drm/project/nyaru-clipper/docs/phase2-improvement-results-2026-10-21.md) and [Chinese counterpart](/Users/drm/project/nyaru-clipper/docs/phase2-improvement-results-2026-10-21.zh-CN.md): Current implementation, acceptance evidence and platform limits
- [Phase-three and cumulative results](/Users/drm/project/nyaru-clipper/docs/phase3-improvement-results-2026-10-21.md) and [Chinese counterpart](/Users/drm/project/nyaru-clipper/docs/phase3-improvement-results-2026-10-21.zh-CN.md): Historical phase-three 18 accepted / 26 pending ledger
- [Phase-four and cumulative results](/Users/drm/project/nyaru-clipper/docs/phase4-improvement-results-2026-10-21.md) and [Chinese counterpart](/Users/drm/project/nyaru-clipper/docs/phase4-improvement-results-2026-10-21.zh-CN.md): Historical phase-four23 accepted /21 pending ledger
- [Phase-five and cumulative results](/Users/drm/project/nyaru-clipper/docs/phase5-improvement-results-2026-10-21.md) and [Chinese counterpart](/Users/drm/project/nyaru-clipper/docs/phase5-improvement-results-2026-10-21.zh-CN.md): Historical phase-five28 accepted /16 pending ledger, legacy compatibility and platform limits
- [Phase-six and cumulative results](/Users/drm/project/nyaru-clipper/docs/phase6-improvement-results-2026-10-21.md) and [Chinese counterpart](/Users/drm/project/nyaru-clipper/docs/phase6-improvement-results-2026-10-21.zh-CN.md): Historical phase-six33 accepted /11 pending ledger, eight-line captions/5000-cue previews and platform limits
- [Phase-seven and cumulative results](/Users/drm/project/nyaru-clipper/docs/phase7-improvement-results-2026-10-21.md) and [Chinese counterpart](/Users/drm/project/nyaru-clipper/docs/phase7-improvement-results-2026-10-21.zh-CN.md): Historical phase-seven closing ledger38accepted/6pending, cumulative and native evidence from that phase
- [Phase-eight and cumulative44-item results](/Users/drm/project/nyaru-clipper/docs/phase8-improvement-results-2026-10-21.md) and [Chinese counterpart](/Users/drm/project/nyaru-clipper/docs/phase8-improvement-results-2026-10-21.zh-CN.md): Latest44accepted within recorded scope/0pending, six final changes, current cumulative checks, latest native two-task save/quit/reopen, final gate and limits

- [task-sources-acceptance-2026-10-16.md](task-sources-acceptance-2026-10-16.md): Direct room/BV inputs, local video, build17 installation and data preservation

- [subtitle-editor.md](subtitle-editor.md): Per-cue content, pixel positioning, styles, timing and export
- [subtitle-editor-acceptance-2026-10-16.md](subtitle-editor-acceptance-2026-10-16.md): Web/macOS tests, preview/ASS/burn consistency and build16 installation

- `macos-app.md`: Bundled macOS companion, persistent data and build instructions
- `macos-app.zh-CN.md`: Chinese macOS app guide

- `local-companion.md`: Local URL download, offline ASR, range/highlight clipping and recovery
- `local-companion.zh-CN.md`: Chinese local companion guide
- [openai-subscription.md](openai-subscription.md): ChatGPT subscription authorization and provider selection
- [openai-subscription-acceptance-2026-10-15.md](openai-subscription-acceptance-2026-10-15.md): Actual subscription and bilingual acceptance

- `user-manual.md`: English user manual
- `operator-manual.md`: English operator manual
- `deployment-guide.md`: English deployment guide
- `wsl-rocm-investigation.zh-CN.md`: Chinese WSL + ROCm investigation note, root cause background for the dedicated support path
- `wireframes.md`: English MVP wireframes
- `processing-flow.md`: English processing flow and artifact layout
- `README.zh-CN.md`: Chinese documentation index
- `user-manual.zh-CN.md`: Chinese user manual
- `operator-manual.zh-CN.md`: Chinese operator manual
- `deployment-guide.zh-CN.md`: Chinese deployment guide
- `wireframes.zh-CN.md`: Chinese MVP wireframes
- `processing-flow.zh-CN.md`: Chinese processing flow and artifact layout

The deployment guides are the fastest way to reach the supported local and self-hosted workflows. If you need WSL + ROCm, start from the deployment guides first, then use the operator manuals after the stack is up and reachable.

The English and Chinese manuals are kept as parallel document sets so operators and users can work in either language without losing MVP scope fidelity.

The operator and deployment guides now also document the current ASR lifecycle observability contract, including active phase timing visibility, `cancel_requested` overlay behavior, the narrower `force-kill` availability rules, worker execution-token boundaries for stage updates, and the developer regression commands for backend/frontend task-state changes.
