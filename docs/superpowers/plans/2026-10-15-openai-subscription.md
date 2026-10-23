# OpenAI Subscription Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Shared workspace, separate ownership, no commits or pushes.

**Goal:** Add official ChatGPT subscription authorization and use it for Saozi semantic cuts and automatic bilingual subtitles, update the macOS App, and observe real results.

**Architecture:** Existing HTTPX/FastAPI backend owns OAuth and credentials. A narrowly injected JSON-text request callable lets existing cut selection and translation validation handle either Flash or ChatGPT Responses without changing subtitle publication. React selects provider and account models; the native app opens external authorization in the system browser.

**Tech Stack:** Python3.11, existing HTTPX/FastAPI/Pydantic, PyJWT[crypto] for verified OIDC, React/TypeScript/pnpm, Swift/WKWebView, PyInstaller.

## Global Constraints

- User approved official subscription direct connection, semantic cuts AND bilingual translation, native App update and actual validation.
- DeepSeek Pro is prohibited. Flash remains available. No automatic provider fallback, external credential reuse, Codex token copying, backend-api calls, commits or pushes.
- Protect 40c0c9a8e93e, all 35 slices of 1bd089ad75b3, existing translations, configurations and models.
- OAuth credentials stay in a dedicated atomic0600 file outside task folders, with symlink rejection; no secrets in API/UI/logs/artifacts or process arguments. This follows the current official SIWC credential-file guidance.
- Use the already isolated web worktree first, then synchronize only owned changed sources to the existing mac worktree, preserving its frozen media.py behavior.
- Models are discovered from the connected account. HTTP Responses uses store=false, stream=true, array input and instructions; omit unsupported subscription parameters. Completed event plus existing structural validation is mandatory.
- Existing task/cache model identities remain stable; new ChatGPT model identities use the prefix chatgpt: before the actual slug. Old absent provider defaults to DeepSeek. Changing defaults affects new tasks only.

## Task 1: Official local OAuth and credential lifecycle

Ownership: new backend/app/arctime/chatgpt_auth.py (split models/credentials helper if warranted), backend/tests/test_chatgpt_auth.py. Parent owns manifests, GUI endpoints and manager.

Interface consumed by parent/provider:

```python
auth = ChatGPTAuth(root: Path)
auth.status()  # safe dict: connected, sharing, account_label, error, manage_url
auth.begin(redirect_uri: str) -> str  # authorize URL, pending request only in memory
auth.complete(*, code: str, state: str, client_id: str | None = None,
              error: str | None = None) -> None
auth.token() -> SecretStr  # refresh when expiry is near, serialized refresh
auth.models() -> list[dict[str, str]]  # slug, display_name only, visibility=list
auth.logout() -> None
```

AuthError subclasses ValueError and carries sanitized user-facing messages. Constructor may accept test client/store/clock interfaces. Status must not perform an inference request. Models uses the same selected account token as inference. Safe manage_url follows official account settings.

- [ ] Write and run failures for wrong/expired/replayed state, missing issued client_id, invalid JWT signature/issuer/audience/nonce/expiry, returning subject mismatch, absent plan scope, symlink and insecure credential paths, refresh rotation and logout.
- [ ] Implement official dynamic_agent_client registration, stable host UUID, fresh state/nonce/PKCE, loopback /auth/callback, issued-client persistence, signature verification using published JWKS and PyJWT[crypto]. Exact auth URLs and scope/refresh behavior come from the approved official references in the spec.
- [ ] Persist registrations and verified credentials atomically0600; preserve the existing session until replacement validates. Refresh updates rotating credentials together; rejected refresh gives reauthorization state with no secret-bearing exception.
- [ ] Run `PYTHONPATH=backend ~/.cache/nyaru-clipper/companion-venv/bin/python -m pytest backend/tests/test_chatgpt_auth.py -q`. Record actual red/green output and boundaries in `.omo/evidence/openai-auth-report.md` in web worktree.

## Task 2: Responses transport and shared cut/translation boundary

Ownership: new backend/app/arctime/chatgpt_provider.py, translation.py, saozi.py, saozi_translation.py; corresponding focused provider/translation/selector tests. Parent owns manager, workflow, live manifest, projection, API, CLI if integration requires it.

Interface:

```python
JsonRequest = Callable[[str, str], str]  # instructions, JSON input -> completed JSON text
provider = ChatGPTProvider(model: str, token: Callable[[], SecretStr], *, transport=None)
text = provider(instructions: str, input_json: str) -> str
# model passed to provider is the server slug, WITHOUT chatgpt: prefix.
# Add request_json: JsonRequest | None = None to SaoziSelector constructor,
# translation._request / translate_run and saozi_translation.translate.
```

ChatGPT identities use model="chatgpt:<slug>" in saved job/cache; permit this only when an injected request_json exists. Legacy Flash identity and old cache contents remain byte-compatible. MODELS must no longer offer/call Pro. Cloud request branches keep IDs/count/candidate/schema validation in existing callers.

- [ ] Write failures for response.failed/incomplete/missing terminal/empty output, chunked SSE framing, credentials redaction, subscription quota rejection, absolute timeout and zero tools/unsupported parameters.
- [ ] Implement HTTPS /v1/responses SSE with a bounded total deadline and bounded retry before any output, request token at each attempt, only accept response.completed and nonempty JSON. Parse SSE safely across chunks and cap output.
- [ ] Inject JsonRequest at existing smallest request boundaries; accept namespaced ChatGPT model only with matching callable. Reuse existing rendering/checkpoints and reject provider-mismatched cache. Apply the shared callable to normal manual bilingual generation as well as Saozi live/offline.
- [ ] Run focused provider, translation, selector and Saozi translation tests. Record actual results in `.omo/evidence/openai-provider-report.md` in web worktree.

## Task 3: Account/provider UI

Ownership: web/src/companion/Companion.tsx, companionApi.ts, companion.css, new ChatGPTConnection.tsx if useful, focused tests. Parent owns native Swift and backend routes. Follow existing DESIGN.md and components; read routed frontend design/perfection references before editing.

API contract provided by parent:

```text
GET /companion-api/config:
  old fields retained; adds llm_provider: deepseek|chatgpt, llm_model: string,
  llm_configured: bool, chatgpt: {connected, sharing, account_label, error, manage_url}
POST /companion-api/llm-config {provider: deepseek|chatgpt, model: string}
GET /companion-api/chatgpt -> safe status object above
POST /companion-api/chatgpt/login -> {url: string}
POST /companion-api/chatgpt/logout -> safe status
GET /companion-api/chatgpt/models -> [{slug, display_name}]
```

Frontend passes raw selected server slug when saving chatgpt provider; config llm_model also raw slug. Job model labels may be chatgpt:<slug>. Login opens returned official URL through an ordinary user-activated external link/new window; parent ensures WKWebView opens it in the system browser. No token/pasted-cookie fields. Poll safe status during pending authorization, refresh models when connection changes. Logout disabled while a task is busy. Never choose Pro or assume model list means inference passed.

- [ ] Add and run failing UI scenarios for subscription connect, plan permission missing, server model selection/provider persistence, failed login/expired session, current task retaining its saved provider, and only Flash under DeepSeek.
- [ ] Implement accessible controls using current labels/tokens; only relevant provider settings shown. Replace hard-coded DeepSeek readiness/copy for Saozi with selected-provider readiness and subscription usage wording.
- [ ] Run `corepack pnpm test --run src/companion/Companion.test.tsx src/companion/ChatGPTConnection.test.tsx` (only existing selected files), then `corepack pnpm build`. Record results and visual scope in `.omo/evidence/openai-ui-report.md` in web worktree.

## Task 4: Parent integration, native update and actual acceptance

Ownership: companion_manager.py, companion_models.py, companion_projection.py, gui.py, saozi_api.py, workflow.py, saozi_live.py as needed; desktop/macos/App.swift; manifests and generated dependencies; docs/build and integration tests.

- [ ] Add PyJWT[crypto]>=2.10,<3 to backend pyproject; install into the companion runtime via uv, refresh lock/generated requirements through project generators, and update paired companion setup docs. Never hand-edit generated requirement files.
- [ ] Add auth routes via a small chatgpt_api.py router and instantiate ChatGPTAuth per manager. Callback HTML must not echo query values/secrets and sends no-store/referrer-policy. Disable access-log query capture for the OAuth callback server path/runtime.
- [ ] Persist provider/model defaults atomically with the existing DeepSeek configuration intact. Snapshot namespaced model at submit/upload before upload finishes, validate configured account/model, and pass refreshed JsonRequest to every appropriate selector/translator. Resume uses saved provider/model, never silently defaults a saved ChatGPT task to Flash. Persist explicit llm_provider in new job manifests and project it safely.
- [ ] Test HTTP authorization/denial/CSRF/invalid callback, safe config responses, upload snapshot, offline/live auto translation integration and old outputs/cache compatibility, including Pro API rejection. Run meaningful related backend and companion frontend suites.
- [ ] Update native navigation for exact official authorization URL initiated by the UI; preserve main local workbench, open Safari/system browser and handle popup links. Build version0.1.8 build12 in a fresh output directory after web-to-mac synchronization; preserve0.1.7build11 backup, verify installed file hashes and strict signature.
- [ ] On real App, show login UI and let the user complete account login/consent when required. Confirm OAuth state and granted sharing, discover model and complete a tiny actual inference through the same provider. Do not treat login/catalog as inference acceptance.
- [ ] Run new local150sec sample requiring semantic cut choice and automatic Japanese/Chinese subtitles; run real Bilibili room545068 if still live, observe downloadable first bilingual slice while recording, then stop and validate tail. Verify paired source/translation counts/times, zero-based slice times, downloads and a semantic sample. Preserve source40c0c9 and35 old slices.
- [ ] Obtain scoped task reviews and a final whole-feature review; address material findings, then update paired handoff/acceptance docs with verified results and any external authorization/provider blocker. No commit, push, public release or notarization.
