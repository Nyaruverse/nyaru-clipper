# Three task sources

Approved in chat on 2026-10-16. New Task begins with three labelled buttons: 实时录播, 下载视频, 本地视频. Live accepts a Bilibili room number and records/processes until stopped. The GUI accepts a numeric room ID or BV identifier only and generates the URL internally; existing full-URL API/CLI clients remain compatible. Local opens the native file chooser and imports a task-owned copy. Preserve each source's draft when switching.

Source selection is independent of slicing. Download and local support explicit ranges, subtitle-based highlights and saozi. Live always uses existing real-time saozi, with clear AI requirements and the existing stop control. Switching away from live restores the previous non-live slicing mode. Invalid source/selection fails before upload or job reservation. Empty uploads release the single job reservation. The original local file is never modified.

Use the current ivory Companion drawer, spacing/type/color tokens, neutral button borders, ink selected state and visible keyboard focus. Three source buttons share one row at supported widths; inputs remain labelled. Test through UI submission plus the real local API in an isolated temporary data directory. External download/live/provider success is separate from routing acceptance.
