# Web verification before App branch delivery

Verified15October2026 on macOS in a real in-app browser at `http://127.0.0.1:61026/`, served by the installed Nyaru Clipper0.1.8 build14 helper. This tests the browser surface against the installed helper, not a second standalone backend process.

- Changed the default provider to DeepSeek Flash, saved it, then restored ChatGPT subscription/GPT-6-Luna. The existing task retained its namespaced ChatGPT model. After reload, the saved provider/model and completed task were visible. The model catalog recovered on reload after a transient network failure.
- Selected Saozi/local recording, imported the existing150.033333-second Japanese source through the browser file chooser and created independent task `472c1adbd0d1`. Real local ASR and `chatgpt:gpt-6-luna` semantic decisions exported114-second and36.033333-second clips. The short tail is retained.
- Automatic translation initially stopped at0/21 with a sanitized network/stream error. The page offered continuation; one UI retry completed21/21 cues without recreating the task or switching provider. This is successful recovery, not uninterrupted provider availability.
- Full and clip bilingual subtitles became available. Browser clip playback advanced from0.021333to21.149613seconds with1280×720 decoded video and visible Japanese/Chinese captions. The subtitle/timeline controls rendered correctly.
- Downloaded clip1 bilingual SRT through its browser link. SHA256 matched the task artifact: `c6130fd4e6e193523d06cf0d785067502adacb22b75610c5411a6ba139924ee6`.
- Reload retained the completed task,21/21 translation status, ChatGPT provider and GPT-6-Luna selection. The browser console had no warning/error entries at final inspection.

Fresh checks: Web backend375passed; App backend including macOS cases382passed; Companion frontend41passed across5files; TypeScript/Vite production build passed; `git diff --check` passed. The two backend counts overlap and must not be added. One existing Starlette HTTPX deprecation warning remains. These are selected companion tests, not whole-repository coverage.

Browser-created outputs and screenshots remain local outside Git. Actual Bilibili live processing and native-save verification are recorded in the [subscription acceptance](openai-subscription-acceptance-2026-10-15.md); they were not rerun during this browser check. Desktop browser playback does not independently validate audio listening, other browsers, mobile layouts or Apple notarization. Downloads permission in WKWebView remains ungranted/user-accepted; the browser SRT download passed independently.
