# ChatGPT subscription connection

The local companion supports two selectable AI providers: DeepSeek Flash and ChatGPT subscription. They supply semantic Saozi cut choices and Japanese/Chinese subtitle translation; recording, transcription and video export stay local.

Choose **ChatGPT subscription** under **AI provider**, click **Continue with ChatGPT**, then the browser continuation link. Complete the official sign-in and grant ChatGPT plan usage. Return to Nyaru Clipper, select a model returned for your account, and save the provider/model. The saved choice applies to new tasks; started jobs retain their original provider/model and cache. DeepSeek Pro is disabled.

Connecting an identity or reading the model catalog does not prove inference access. Subscription availability and usage limits are enforced by OpenAI; failures preserve original clips and completed subtitle batches. No provider fallback happens automatically. The UI provides account usage and sign-out actions.

Credentials are stored separately under `runs/.chatgpt/` using owner-only directory/file permissions and atomic replacement. The interface, task manifests and downloads do not receive tokens. This connection uses its own official registration; it does not reuse another application's credentials.

The implementation uses the official [Sign in with ChatGPT flow](https://developers.openai.com/siwc/token-sharing-open-source), with supported [Responses requests](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference) and current [preview limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations). Real-account and native acceptance are recorded separately; this usage guide is not proof of a completed live request.
