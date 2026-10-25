# Nyaru Studio prototype v1

## 1. Atmosphere & identity
An approved light macOS creative workspace. Video leads, mint identifies actions and selected content. Daily use and template design share a stable toolbar, preview and inspector. This is a standalone interactive prototype, not production integration. The earlier generated concept defines direction, not an exact pixel target: the subsequently approved two-mode control and separate settings page supersede its six-button toolbar.

## 2. Color
Canvas #F3F5F7; surface #FFFFFF; subtle #F8FAFB; ink #20292E; secondary #58666E; line #DDE3E7; accent #146F66; hover #105B54; selected #E7F3EF; warning #855518; danger #A33737; video #172927; white #FFFFFF. Light appearance is explicitly selected by the user and remains light under either system preference. AA text contrast, selection also marked by check or shape.

## 3. Typography
System sans: -apple-system, BlinkMacSystemFont, PingFang SC, Hiragino Sans GB, sans-serif. Timecodes: ui-monospace, SFMono-Regular, monospace. Caption 12, secondary 13, body 14, emphasis 16, section 18, page 24px. Phone body 17 and secondary 15px. Natural CJK wrapping; no negative CJK tracking.

## 4. Spacing & layout
4px rhythm: 4/8/12/16/20/24/32/40/48. Controls at least 44px interactive height. Toolbar 72px, task context 72px. Workspace grid minmax(0,1fr) plus 336px inspector. Preview capped by available window height, subtitle list below. Main workspace and inspector independently own bounded vertical scrolling. Settings: 232px navigation with scrolling main content. At <=1000px inspector below preview; <=640px single-column shell, toolbar wraps, page scrolls. No horizontal overflow at 390px.

## 5. Primitives
Button: neutral, primary, quiet, disabled; hover/press/focus and icon+text; 44px hit area. Segmented control: semantic tablist, selected wash plus raised thumb; arrow/Home/End keyboard. Field: visible label, native input/select, focus ring; errors next to field. Panel: white surface, 1px line only where needed. Settings row: descriptive label plus control, helper below. Drawer: native dialog, visible close, Escape and focus return. Subtitle row: button with timecode and bilingual content, selected wash+check. Status: glyph+label. All reused across daily/designer/settings. A primitives state harness is available at #components.

## 6. Motion & interaction
140ms opacity/color; segmented thumb transform 180ms ease-out, reduced-motion cross-fade. No decorative animation or fake progress. Preview uses a generated still explicitly labeled as demo. Changing cues updates still subtitle/timecode, play toggles demo preview state only. Unsaved template drafts survive mode/settings changes, labeled as drafts. Settings have explicit save/discard and a leave guard. Daily task overrides are cloned from a template snapshot; saving a template cannot mutate existing task appearance. No backend requests or credentials.

## 7. Depth & surface
White editor surface and cool gray background, fine dividers; subtle 0 1px 3px ink/5% control shadow and 0 16px 48px ink/12% dialog shadow. Radius 7px controls, 12px panels, 16px dialog. Avatar simple typographic mark. All interface is real DOM, only the landscape is raster artwork.

## 8. Accessibility & scope
Visible focus, named icon controls, native forms/dialogs, focus restoration, no autoplay audio, keyboard modes, meaningful image alt. Three main routes and six settings categories must be captured at 390/1440/1920 with both system color preferences; light result expected. Prototype buttons label simulated operations; no real login, ASR, export, recording, native app integration, persistence or credentials. State persists in memory for this page session only, explicitly explained. Generated scenery: built-in ImageGen, original coastal illustration without UI or text. Source prompt in asset-prompt.txt.

## Production integration (2026-10-17)
The approved v1 prototype above is the visual reference. Production uses no generated landscape and no demo task records. `StudioToolbar` owns the single 72px toolbar and sliding mode tabs. `StudioSettings` owns six dedicated categories. `WorkflowFields` supplies the same processing/export controls to defaults and worktemplate metadata. Companion-scoped CSS overrides only Companion tokens. Controls use 7px, panels 12px radii.

Daily keeps the real player and exact subtitle document renderer mounted, with the actual subtitle transcript below and compact cue content/size/position inspector on the right. Advanced per-cue editing remains available through an explicit action. Template Design owns a separate style/project draft, and uses `TemplatePreview` against the server's libass PNG renderer with explicitly labeled editable sample text and neutral safe-area canvas. There is no fake recorded scenery or fake progress. Settings uses existing provider authorization components and actual environment/export capability reports.

Default workflow settings save explicitly and guard departure/page close while dirty. Task input and editor state survive mode/settings navigation. Existing template updates include expected revision, builtin templates can be duplicated, and new task inputs snapshot selected templates for URL/live/upload. New template metadata records streamer/workflow; task edit APIs remain separate. Settings full template editor and design inspector each retain independent complete drafts: selection, name, revision, workflow, appearance and project binding. Neither can overwrite the other editor’s appearance while retaining a different template ID. Repeated Studio radius, spacing and caption values use scoped --studio-* tokens.

Acceptance still requires parent real-browser/native checks against the referenced 390/1440/1920 layouts. Unit suite/build are not native playback or provider authorization acceptance. No dependencies or external design components were added. No Lighthouse or react-doctor install was performed under the explicit no-install boundary.

## Selective highlight/editor integration (2026-10-25)
The existing inspector gains Highlighter using the same fields/buttons and scroll owner. Topic rows show time, optional relative score, summary and ordered selection; absent factors are labeled, never shown as zero-confidence success. Analysis/export use saved editing revisions and the unified queue. Font search remains a native editable input/datalist; pinned-family buttons share browser-local preferences across editors. Multi-outline controls extend the current style fields (base stroke plus up to two extra layers), common exact preview and export. Preserve split/merge/timing/position/undo and the light appearance. No new visual tokens, motion, dependency or graphics mode.
The added highlighter/font/outline controls use the established phone body/helper sizes (17/15px) at <=640px. Native file upload keeps a 44px target. Capture every actual scroll owner and wait for the exact libass PNG before judging layout.
