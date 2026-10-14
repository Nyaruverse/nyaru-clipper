# Persistent DeepSeek Key acceptance

The user requested a persistent Key controlled by a configuration file, replacing the 0.1.2 session-memory behavior. App 0.1.3 build 4 was installed and started; original-checkout App/ZIP artifacts were updated with previous packages and installation preserved.

- Saving creates or replaces `~/Library/Application Support/Nyaru Clipper/runs/config.json`, with permissions 0600, and loads it on restart.
- The field is `deepseek_api_key`; manual changes take effect after restart, and an empty string disables the Key. Invalid configuration reports an error and can be repaired by saving. Symlinks are rejected, and failed writes do not activate the new Key.
- The Key is excluded from API responses, downloadable task artifacts and task records. The configuration is plaintext; GUI saves guarantee 0600, while manually created files require appropriate permissions.
- Selected App backend tests (117), UI tests (6) and TypeScript/Vite build passed; independent review found no blockers. The frozen backend was tested in an isolated temporary directory with a non-real Key for saving, restart loading, 0600 and API isolation, without provider requests.
- Strict signature and ZIP integrity checks passed. The browser GUI connected to the installed backend displayed the new configuration entry. Native observation failed due to screen capture, so the native save-button action was not reaccepted.
- All 86 original files across 40c0c9 and 7fe886 retain their checksums. The user has not entered a real Key; real translation and semantic quality remain pending.

Source changes were synchronized to the original checkout and browser/App worktrees, without commit or push. See the [guide](deepseek-bilingual.md). The private local check is `.omo/evidence/2026-10-14-persistent-key/check_frozen_config.py`.
