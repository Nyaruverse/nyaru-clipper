import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {fireEvent, render, screen, waitFor, within} from '@testing-library/react';
import {afterEach, beforeEach, expect, it, vi} from 'vitest';
import {Companion} from './Companion';
import {defaultStyle} from './subtitleStyle';
import {documentFixture} from './subtitleDocument.fixture';

beforeEach(() => localStorage.clear());
afterEach(() => vi.unstubAllGlobals());
function setup(options: {model?: string; configured?: boolean; unified?: boolean; translationState?: string; config?: Record<string, unknown>; library?: boolean} = {}) {
  const unified = options.unified ?? true, configured = options.configured ?? true;
  const job = {id: 'review-task', title: '保存的视频标题', source_label: 'BV1xx411c7mD', state: 'completed', phase: 'completed',
    message: '处理完成', error: null, started_at: 0, duration: 60, mode: 'ranges', can_resume: false, has_source: true, language: 'ja',
    clips: [], segments: [{id: 'one', start_seconds: 1, end_seconds: 5, text: 'こんにちは'}], bilingual_segments: [],
    translation: {state: options.translationState ?? 'not_started', model: options.model ?? 'existing-result', done: 0, total: 1, error: null}};
  const libraryItem = () => ({task_id: job.id, title: job.title, tags: [], archived: false, version: job.title});
  const posts: {url: string; body: unknown}[] = [];
  vi.stubGlobal('EventSource', class {addEventListener() {} close() {}});
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, request?: RequestInit) => {
    const url = input instanceof Request ? input.url : String(input);
    if (input instanceof Request && input.method === 'PATCH') {
      const patch = await input.json();job.title = patch.title;return Response.json(libraryItem());
    }
    if (request?.method === 'POST') {posts.push({url, body: typeof request.body === "string" ? JSON.parse(request.body) : request.body});return new Response('{"id":"review-task"}');}
    const value = url.endsWith('/config') ? {unified_operations: unified, ready: true, missing: [], translation_configured: false,
      llm_provider: 'chatgpt', llm_model: 'account-model', llm_configured: configured, chatgpt: {connected: configured, sharing: configured}, ...options.config}
      : url.endsWith('/jobs') ? [job]
      : url.endsWith('/studio-settings') ? {language: 'auto', mode: 'ranges', highlights: 3, export_format: 'ass', bilingual: true, default_template_id: null}
      : url.endsWith('/subtitle-settings') ? {style: defaultStyle, templates: [], arctime_templates: []}
      : url.endsWith('/subtitle-document') ? {...documentFixture(), duration: 60}
      : url.includes('/api/v2/library') ? {items: options.library ? [libraryItem()] : [], total: options.library ? 1 : 0, page: 1, page_size: 25}
      : url.endsWith('/operations') ? {operations: [], paused: false, revision: 0}
      : url.endsWith('/subtitle-exports') ? {active: null, outputs: []}
      : url.endsWith('/topic-segments') ? {state: 'completed', operation_id: 'analysis', created_at: 1, document_revision: 0,
        segments: [{index: 0, title: '候选一', summary: '内容', start_seconds: 10, end_seconds: 20}]}
      : url.endsWith('/topic-clips') ? {state: 'completed', items: [{index: 0, state: 'completed', url: '/companion-api/jobs/review-task/files/topic-one.mp4'}], combined: {url: '/companion-api/jobs/review-task/files/combined.mp4'}}
      : url.endsWith('/danmaku') ? {count: 0} : job;
    return new Response(JSON.stringify(value));
  }));
  const client = new QueryClient({defaultOptions: {queries: {retry: false}, mutations: {retry: false}}});
  render(<QueryClientProvider client={client}><Companion/></QueryClientProvider>);
  return {posts};
}

it.each(['existing-result', 'saved-document'])('uses selected configured provider for untranslated %s provenance', async model => {
  const {posts} = setup({model});
  const button = await screen.findByRole('button', {name: '生成中日双语字幕'});
  expect(button).toBeEnabled();fireEvent.click(button);
  await waitFor(() => expect(posts.some(post => post.url.endsWith('/translate'))).toBe(true));
});
it('still requires configured authentication for provenance-only translation', async () => {
  setup({configured: false});
  expect(await screen.findByRole('button', {name: '生成中日双语字幕'})).toBeDisabled();
});
it('preserves frozen legacy task provider instead of using newly selected provider', async () => {
  setup({unified: false, model: 'deepseek-flash', translationState: 'interrupted'});
  expect(await screen.findByRole('button', {name: '继续生成中日双语字幕'})).toBeDisabled();
});
it('creates unified recordings with no upfront default clip while keeping manual ranges available', async () => {
  const {posts} = setup();await screen.findByText('处理完成');
  fireEvent.click(screen.getByRole('button', {name: '新建任务'}));
  fireEvent.click(screen.getByRole('button', {name: /指定时间段 ·|先识别，再审阅高光/}));
  expect(await screen.findByRole('radio', {name: '先识别，再审阅高光'})).toBeChecked();
  fireEvent.click(screen.getByRole('button', {name: '新建任务'}));
  fireEvent.change(screen.getByLabelText('BV 号'), {target: {value: 'BV1xx411c7mD'}});
  fireEvent.click(screen.getByRole('button', {name: '加入队列'}));
  await waitFor(() => expect(posts.some(post => post.url.endsWith('/jobs'))).toBe(true));
  expect(posts.find(post => post.url.endsWith('/jobs'))?.body).toMatchObject({ranges: [], highlights: null, recognition_only: true});
});
it('keeps explicitly selected manual ranges when creating a unified task', async () => {
  const {posts} = setup();await screen.findByText('处理完成');
  fireEvent.click(screen.getByRole('button', {name: '新建任务'}));
  fireEvent.click(screen.getByRole('button', {name: /指定时间段 ·|先识别，再审阅高光/}));
  fireEvent.click(await screen.findByRole('radio', {name: '指定时间段'}));
  fireEvent.click(screen.getByRole('button', {name: '新建任务'}));
  fireEvent.change(screen.getByLabelText('BV 号'), {target: {value: 'BV1xx411c7mD'}});
  fireEvent.click(screen.getByRole('button', {name: '加入队列'}));
  await waitFor(() => expect(posts.some(post => post.url.endsWith('/jobs'))).toBe(true));
  expect(posts.find(post => post.url.endsWith('/jobs'))?.body).toMatchObject({ranges: [['00:00', '00:30']]});
});
it('shows saved task title and source identity above the workbench', async () => {
  setup();
  expect(await screen.findByRole('heading', {name: '保存的视频标题'})).toBeVisible();
  expect(document.querySelector('.watch-task-context')).toHaveTextContent('BV1xx411c7mD');
});
it.each([['播放话题 1', 'topic-one.mp4'], ['播放组合视频', 'combined.mp4']])('plays %s without source overlays or source loop and returns to source preview', async (label, name) => {
  setup();fireEvent.click(await screen.findByRole('button', {name: '预览候选一'}));
  fireEvent.click(await screen.findByRole('button', {name: label}));
  const player = await screen.findByLabelText('高光成片预览');
  expect(player).toHaveAttribute('src', `/companion-api/jobs/review-task/files/${name}`);
  expect(screen.queryByLabelText('样式字幕预览')).not.toBeInTheDocument();
  expect(document.querySelector('track')).toBeNull();
  expect(screen.queryByLabelText('切片时间轴')).not.toBeInTheDocument();
  expect(screen.queryByLabelText('循环当前高光')).not.toBeInTheDocument();
  Object.defineProperty(player, 'paused', {value: false});
  fireEvent.timeUpdate(player, {target: {currentTime: 25}});
  expect(player).toHaveProperty('currentTime', 25);
  fireEvent.click(screen.getByRole('button', {name: '完整视频'}));
  expect(await screen.findByLabelText('完整视频预览')).toHaveAttribute('src', '/companion-api/jobs/review-task/files/source.mp4');
  expect(within(screen.getByLabelText('视频预览')).getByText('样式字幕预览')).toBeVisible();
});

it('sends explicit recognition-only mode when uploading a local recording', async () => {
  const {posts} = setup();await screen.findByText('处理完成');
  fireEvent.click(screen.getByRole('button', {name: '新建任务'}));
  fireEvent.click(screen.getByRole('button', {name: '本地视频'}));
  const file = new File(['test-video'], 'video.mp4', {type: 'video/mp4'});
  fireEvent.change(screen.getByLabelText('本地视频文件'), {target: {files: [file]}});
  fireEvent.click(screen.getByRole('button', {name: '加入队列'}));
  await waitFor(() => expect(posts.some(post => post.url.includes('/jobs/upload?'))).toBe(true));
  const request = posts.find(post => post.url.includes('/jobs/upload?'));
  const parameters = new URL(request?.url ?? '', window.location.origin).searchParams;
  expect(parameters.get('recognition_only')).toBe('true');
  expect(JSON.parse(parameters.get('ranges') ?? 'null')).toEqual([]);
  expect(request?.body).toBe(file);
});

it('keeps rejected saved API credentials disabled when the config uses the legacy readiness fields', async () => {
  setup({config: {llm_configured: undefined, llm_provider: 'deepseek', translation_configured: true,
    translation_model: 'deepseek-flash', translation_config_error: 'saved key rejected'}});
  expect(await screen.findByRole('button', {name: '生成中日双语字幕'})).toBeDisabled();
});

it('refreshes the workbench task header immediately after saving its library title', async () => {
  setup({library: true});
  expect(await screen.findByRole('heading', {name: '保存的视频标题'})).toBeVisible();
  fireEvent.click(screen.getByRole('button', {name: '任务记录'}));
  fireEvent.click(await screen.findByText('任务标题与标签'));
  fireEvent.change(screen.getByLabelText('任务标题'), {target: {value: '审阅后的任务标题'}});
  await waitFor(() => expect(screen.getByRole('button', {name: '保存任务信息'})).toBeEnabled());
  fireEvent.click(screen.getByRole('button', {name: '保存任务信息'}));
  expect(await screen.findByText('审阅后的任务标题')).toBeVisible();
  fireEvent.click(screen.getByRole('button', {name: '任务记录'}));
  expect(await screen.findByRole('heading', {name: '审阅后的任务标题'})).toBeVisible();
});
