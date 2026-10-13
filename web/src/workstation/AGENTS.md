# WORKSTATION KNOWLEDGE BASE

## OVERVIEW

Active task library, queue, creation drawer and task overview, sharing query state with the context inspector.

## WHERE TO LOOK

| Task | Location | Notes |
| --- | --- | --- |
| Event connection | `WorkstationApp.tsx`, `api/useWorkstationEvents.ts`, `api/events.ts` | one hook feeds connection state into the shell |
| Typed requests/cache keys | `api/client.ts`, `api/queryKeys.ts`, `features/*/api.ts` | openapi-fetch client and shared projections |
| Library state | `features/task-library/filters.ts`, `features/task-library/TaskLibraryPage.tsx` | URL parsing, query mapping, pagination, selection |
| Queue concurrency | `features/queue/api.ts`, `features/queue/QueuePage.tsx` | revision requests, optimistic snapshots, conflict recovery |
| Task creation | `features/task-create/NewTaskDrawer.tsx` | reducer-driven source/inspection/options/submission steps |
| Overview and review | `features/task-overview/TaskOverviewPage.tsx`, `features/task-overview/ExistingReviewWorkspace.tsx` | v2 overview plus legacy subtitle/export functionality |
| Shell/inspector | `components/AppShell.tsx`, `components/ContextInspector.tsx` | route/selection context and drawer focus return |
| Styling | `design/` | tokens.css, global.css, primitives.css, workstation-shell.css; `--ny-*` tokens and `ny-*` classes |
| Unit harness | `testing/renderWorkstation.tsx`, `testing/fixtures.ts` | QueryClientProvider + MemoryRouter and optional seeded cache |

## API AND STATE CONVENTIONS

- The client uses generated `paths`; feature APIs derive response/request types from generated `components` or `operations`.
- Client and event URL builders remove trailing slashes and a terminal `/api` from `VITE_API_BASE_URL`; endpoint paths already contain `/api/v2`.
- Reuse `workstationKeys` for summary/list/detail/queue projections so mutations, inspectors and SSE invalidate the same cache entries.
- SSE task/stage/artifact events invalidate task projections; `queue.updated` invalidates the queue. Events signal refetches rather than replacing query data.
- Reconnect carries the last received event ID as `cursor` only when it is a nonnegative decimal integer; delays are 1/2/5/10/30 seconds.
- Five consecutive failures start 15-second fallback invalidation while reconnecting continues. Opening a connection stops polling; unmount closes the source and timers.
- Library filters serialize through `filters.ts`; URL `selected` drives inspector selection, while task overview uses `stage`. Preserve unrelated parameters when updating selection.
- Queue reorder sends the cached `revision` as `expected_revision`. Valid HTTP 409 snapshots replace optimistic state; other reorder failures restore the previous snapshot.
- Queue mutation locking, query cancellation and settled refetch prevent stale GETs or overlapping actions from overwriting authoritative snapshots; preserve that sequence.

## UI CONVENTIONS

- Use the existing `--ny-*` tokens for color, spacing, type, targets and focus indicators; `AppShell.tsx` loads the four design stylesheets.
- Inspector mode follows route and URL selection: queue, selected task, task overview, or workspace summary.
- New-task UI uses Radix Dialog and a separate discard alert dialog; preserve dirty-draft handling and the shell's focus return to its trigger.
- `ExistingReviewWorkspace.tsx` imports legacy API, artifact readiness, types and copy from `web/src/lib/`; preserve its subtitle, highlight confirmation and download contracts.
- Workstation components contain inline Chinese text; shared legacy review copy remains in its existing modules.

## VALIDATION POINTERS

- Colocated `__tests__` cover features, routes and API behavior. `__tests__/WorkstationApp.test.tsx` and `api/__tests__/useWorkstationEvents.test.tsx` provide EventSource stubs.
- Queue tests exercise optimistic order, revision conflicts, stale fetches and keyboard selection; keep those scenarios when changing mutation or selection behavior.
- Browser scenarios are under `../../e2e/`: `workstation-shell`, `workstation-queue`, `workstation-task-create`, `workstation-task-overview` and `task-library-controls` specs.
- These browser fixtures intercept HTTP; they verify UI behavior, not live backend or GPU execution.

## ANTI-PATTERNS

- Do not create feature-local cache keys that bypass shared SSE invalidation or inspector updates.
- Do not overwrite a queue conflict snapshot with the old optimistic order or unlock before the settled refetch completes.
- Do not replace keyboard row actions, dialog focus behavior or accessible status announcements with pointer-only controls.
