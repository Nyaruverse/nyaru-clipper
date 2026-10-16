# Three task sources implementation plan

**Goal:** Expose real-time Bilibili capture, BV video download and local video import directly in New Task, as approved in chat.

**Architecture:** Reuse Companion's form, JobInput validation, streamed upload and workflow.local_source. Source is independent of slicing; live uses saozi while video/local preserve the chosen slicing mode. Keep both existing Companion branches synchronized without changing installed app data.

**Initial implementation constraints:** No new dependencies, public services, credentials, model downloads, master changes or app installation. Preserve existing full URL API clients and /saozi/upload; the GUI requests identifiers only.

**Subsequent authorization:** The user later requested packaging and replacing the local App while preserving tasks/configuration, followed by commits/pushes to the two development branches. Build17 installation and data checks passed. Publication details and evidence limits are maintained in the current handoff and task-sources acceptance record; master remains outside the release scope.

- [x] Add failing JobInput tests for room IDs/BV IDs and API tests for local ranges/highlights without AI configuration, invalid selections and empty uploads.
- [x] Normalize identifiers at JobInput boundary. Extend streamed upload with /jobs/upload and validated slicing parameters, preserving the old endpoint and cleanup.
- [x] Add failing UI tests for three source buttons, BV submission, live mode without hidden ranges, local slicing and source draft preservation.
- [x] Render labelled pressed buttons using existing tokens, independent room/video/file drafts and effective live slicing; send local selection to streamed upload.
- [x] Run targeted backend/Companion tests and production build. Copy only shared changes to the macOS worktree and run the same checks.
- [x] Drive a temporary isolated service in a real browser: three sources, invalid inputs, slicing and keyboard behavior; capture 390/1440/1920 CSS widths and drawer scroll ends. Record the in-app browser limitations for color-scheme/device emulation; perform a scoped self-review of fresh captures.
- [x] Update paired usage docs and record exact verification limits. Deliver source paths and preview evidence; subsequently install build17 under the separate authorization above.
