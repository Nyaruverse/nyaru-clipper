# WEB KNOWLEDGE BASE

## OVERVIEW

Vite React/TypeScript package containing the workstation entry and shared legacy review code; workstation-specific rules live in `src/workstation/AGENTS.md`.

## STRUCTURE

```text
web/
├── src/
│   ├── workstation/     # Active shell, routes, features, design, tests
│   ├── generated/       # OpenAPI TypeScript output
│   ├── lib/             # Legacy API/types, task state, review copy
│   ├── pages/           # Legacy pages and compatibility tests
│   └── test/            # Vitest setup, PointerEvent shim, smoke
├── e2e/                 # Browser scenarios and HTTP fixtures
├── openapi.json         # Exported backend contract
├── package.json         # pnpm scripts, Node/pnpm constraints
├── vite.config.ts       # Vitest jsdom config
└── playwright.config.ts # e2e dev server config
```

## WHERE TO LOOK

| Task | Location | Notes |
| --- | --- | --- |
| Bootstrap | `src/main.tsx`, `src/App.tsx` | StrictMode, QueryClientProvider; DEV-only react-grab/react-scan imports |
| Public entry routes | `src/router.tsx` | `/` and `/workstation/*` mount WorkstationApp; `/tasks/:taskId` redirects with replace |
| Nested routes | `src/workstation/routes/WorkstationRouter.tsx` | library index, queue, task overview; design-system only in DEV |
| Contract export | `../scripts/export_openapi_schema.py`, `package.json` | backend export then openapi-typescript generation |
| Legacy compatibility | `src/lib/api.ts`, `src/lib/types.ts`, `src/lib/copy/` | review payloads, downloads, Chinese copy |
| Legacy behavior tests | `src/pages/__tests__/`, `src/lib/__tests__/` | task detail, subtitle/export, API and readiness behavior |
| Test runners | `vite.config.ts`, `playwright.config.ts` | jsdom unit suite versus browser suite |

## CONVENTIONS

- Node `>=20`; pnpm pinned to `10.33.2`.
- TypeScript is strict: no JS, isolated modules, no emit, casing enforced.
- `src/App.tsx` disables query/mutation retries and query refetch-on-window-focus globally.
- For v2 contract changes, run `api:generate`: it exports `openapi.json` with `BACKEND_PYTHON` (default `../backend/.venv/bin/python`), then regenerates `src/generated/api-schema.ts`.
- `api:check` regenerates both files before `git diff --exit-code`; it is not read-only and requires usable Git metadata, unavailable in this local copy.
- Legacy API/type/copy modules remain shared with review features; inspect their callers before removing older pages or payload shapes.

## ANTI-PATTERNS

- Do not hand-edit generated v2 schemas or replace them with independently maintained backend payload interfaces.
- Do not assume legacy pages are the mounted routes; check both router files and their compatibility tests.
- Do not make `pnpm test` cover e2e; Vitest excludes `e2e/**` by design.

## COMMANDS

```bash
pnpm --dir web install --frozen-lockfile
pnpm --dir web dev --host 0.0.0.0 --port 5173
pnpm --dir web test --run
pnpm --dir web build
pnpm --dir web test:e2e
pnpm --dir web exec playwright test e2e/workstation-shell.spec.ts --reporter=line
```

## NOTES

- Playwright uses `http://127.0.0.1:5173`, starts Vite when needed, and reuses an existing server only outside CI.
- `PLAYWRIGHT_CHROME_EXECUTABLE` is read by the browser config; traces are retained on failure.
- Shared `src/styles.css` loads before workstation CSS; inspect legacy review rendering when changing global selectors.
