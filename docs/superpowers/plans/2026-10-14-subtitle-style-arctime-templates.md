# Subtitle styles and ArcTime handoff implementation plan

> For agentic workers: use subagent-driven-development for bounded units, then review and real-surface QA. User approved implementation on 2026-10-14.

**Goal:** Editable subtitle styles, both template kinds, ASS, safe clip burn-in and portable ArcTime handoff in browser and macOS.

**Architecture:** A validated style model and independent template store feed both browser overlay and ASS generation. A single-worker export manager creates immutable checked products without mutating ASR/translation manifests. ArcTime templates remain opaque native files.

**Tech Stack:** Existing Pydantic/FastAPI, React/TypeScript, FFmpeg/libass, zipfile, Swift WKWebView.

## Global constraints

- Work in the browser checkout first; sync owned files to macOS without overwriting its frozen-tool lookup or existing handoff edits. Do not commit or push unless asked.
- Python 3.11; existing companion venv and pnpm 10.33.2. No new web dependencies.
- Never read private config into outputs, never overwrite originals, no cloud transcription/translation during QA.
- UI follows existing DESIGN.md and ny tokens. Tests precede implementation.

## Shared contract

`SubtitleStyle`: `{version:1, original:TextStyle, translation:TextStyle}`. `TextStyle`: `{font:string,size:number,color:'#RRGGBB',outline_color:'#RRGGBB',outline:number,background_color:'#RRGGBB',background_opacity:number,position:'top'|'bottom',margin:number}`. Metrics use a 1080-high reference canvas, width derived from source aspect ratio. Defaults original Arial/48/white/black outline2/transparent/bottom96, translation Arial/40/yellow/black outline2/transparent/bottom40.

`GET /companion-api/subtitle-settings` returns `{style,templates,arctime_templates,burn_available}`. Style templates `{id,name,style,arctime_template_id:null|string,builtin:boolean}`; project templates `{id,name,sha256,size}`.

`POST /companion-api/subtitle-settings`: `{style}` persists default independent of Key. `POST /companion-api/style-templates`: `{id?:string,name,style,arctime_template_id?:null|string}` creates/updates (builtin read-only). `POST .../style-templates/{id}/delete`: delete user template. GET `.../style-templates/{id}/download`: versioned JSON.

`POST /companion-api/arctime-templates?name=NAME&filename=NAME.atpj`: raw bytes (bounded 16MiB), no multipart dependency. POST `.../arctime-templates/{id}/delete`; GET `.../arctime-templates/{id}/download`. Missing/corrupt files surface errors, never silently reset defaults.

`POST /companion-api/jobs/{id}/subtitle-export`: `{kind:'ass'|'burn'|'arctime',video:'source.mp4'|'clip-NNN.mp4',bilingual:boolean,style,arctime_template_id:null|string}` ->202 `{id:jobid}`. Burn only clips. GET `.../jobs/{id}/subtitle-exports` returns `{active:null|{state,message,error},outputs:[{id,kind,video,bilingual,filename}]}`. Files use existing /files route; name safe and output hash checked. API errors use human detail text. All jobs share single executor/active lock.

## Task 1: Style and templates (worker owns only new modules/tests)

- [ ] Write and run failing tests for invalid numbers/color/font/control injection, ASS Unicode/multiline/bilingual events and centisecond timing, template persistence/rename/copy/import/delete, builtin protection, project blob preservation and symlinks.
- [ ] Create `backend/app/arctime/subtitle_style.py`: Pydantic models and `render_ass(original, translated_or_none, style, width, height)->str`; no template I/O.
- [ ] Create `backend/app/arctime/subtitle_templates.py`: `TemplateStore(root)` independent directory, defaults/list/save/delete/download for both kinds, exact interface communicated to root.
- [ ] Run `PYTHONPATH=backend ~/.cache/nyaru-clipper/companion-venv/bin/python -m pytest backend/tests/test_subtitle_style.py backend/tests/test_subtitle_templates.py -q` and report results.

## Task 2: Browser editor and preview (worker owns Companion UI/tests)

- [ ] Write tests showing changing styles changes overlay; CRUD/default-save/project upload/export requests conform to shared contract, failures visible and busy jobs disabled.
- [ ] Create small typed style/editor/preview components; integrate with `Companion.tsx`, preserve current translation/history/download behavior.
- [ ] Overlay uses text nodes and current-time events; derive clip cue positions from source ranges. Hide duplicate native captions in styled preview, preserve native text track and fullscreen via wrapper Fullscreen API. Scale against video image box, not letterbox container.
- [ ] Run `cd web && corepack pnpm test --run src/companion && corepack pnpm build`. Give root real UI QA entrypoint.

## Task 3: Export worker and HTTP integration (root)

- [ ] Write failing API tests for templates/routes, validation, parallel task conflicts, bounded upload, tampered artifacts, isolated export errors and immutable products.
- [ ] Implement `subtitle_exports.py`: verify managed inputs, dimensions, language pairing, render ASS, content-derived export identity, locked temp generation and publication; ZIP fixed filenames/readme/sha256; FFmpeg progress and timeouts; output registry independent from job.json.
- [ ] Implement routes in a separate `subtitle_api.py` mounted by `gui.py`; share manager active/executor lock; extend file whitelist to hash-checked exports and config/active projections without private information.
- [ ] Run selected companion backend suites plus unchanged media/workflow/translation cases.

## Task 4: Real tools, App and QA (root)

- [ ] Install/use libass-enabled FFmpeg without replacing system ffmpeg. Validate filters and a real short video export (audio, dimensions, duration, decoded frames).
- [ ] Sync only modified shared sources to macOS. Update packager with explicit output directory/tool selection and version 0.1.5 build6, retain prior package. Frozen build must discover new modules and libass libraries.
- [ ] Generate synthetic short bilingual task and fresh ArcTime template. Operate browser, ArcTime4.5 and native WKWebView: template save/restart/import, ASS import/edit/save, native template style reuse and native ASS/ZIP/MP4 saves. Do not replace unrelated editor projects.
- [ ] Capture desktop/mobile screenshots, fullscreen and playback cue evidence; retain original-file hashes and real ArcTime/native limitations accurately. Run one read-only gate review after QA.
- [ ] Write paired usage/acceptance docs linking evidence and actual supported scope; finish with delivered App/artifacts and remaining limits.
