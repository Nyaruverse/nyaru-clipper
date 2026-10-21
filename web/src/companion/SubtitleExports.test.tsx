import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { SubtitleExports, useSubtitleExports } from './SubtitleExports';
import type { Job } from './companionApi';
import { documentFixture } from './subtitleDocument.fixture';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers(); });

it('stops idle polling and wakes for parent auto/manual transitions, invalidation and selection', async () => {
  vi.useFakeTimers();
  let state = 'completed';
  const fetcher = vi.fn(async () => new Response(JSON.stringify({active:{state,message:state,error:null},outputs:[]})));
  vi.stubGlobal('fetch', fetcher);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const parent = {id:'first', state:'completed', clips:[], translation:{state:'completed'}};
  function Harness({id, job, listed}: {id:string;job?:Job;listed?:Job}) {
    const result = useSubtitleExports(id, job, listed);
    return <span>{result.data?.active?.state}</span>;
  }
  const job = (value: typeof parent, busy = false): Job => ({...value, subtitle_export_busy:busy,
    phase:'completed', message:'', error:null, started_at:0, duration:6,mode:'ranges',segments:[],
    has_source:true,can_resume:false,language:'ja',bilingual_segments:[],
    translation:{...value.translation,done:0,total:0,error:null,message:null}});
  const component = (id='first', detail=job(parent), listed=detail) => <QueryClientProvider client={client}>
    <Harness id={id} job={detail} listed={listed}/>
  </QueryClientProvider>;
  const view = render(component());
  const tick = async (ms=10) => { await act(async () => { await vi.advanceTimersByTimeAsync(ms); }); };
  await tick();
  const idle = fetcher.mock.calls.length;
  await tick(6000);
  expect(fetcher).toHaveBeenCalledTimes(idle);
  state = 'exporting';
  view.rerender(component('first', job({...parent,state:'recording'})));
  await tick(2100);
  expect(fetcher.mock.calls.length).toBeGreaterThan(idle + 1);
  state = 'completed';
  view.rerender(component());
  await tick();
  expect(screen.getByText('completed')).toBeInTheDocument();
  const terminal = fetcher.mock.calls.length;
  await tick(5000);
  expect(fetcher).toHaveBeenCalledTimes(terminal);
  state = 'exporting';
  view.rerender(component('first', job(parent), job(parent,true)));
  await tick();
  expect(screen.getByText('exporting')).toBeInTheDocument();
  state = 'completed';
  view.rerender(component());
  await tick();
  const external = fetcher.mock.calls.length;
  await act(async () => { await client.invalidateQueries({queryKey:['companion']}); });
  await tick();
  expect(fetcher.mock.calls.length).toBeGreaterThan(external);
  view.rerender(component('second'));
  await tick();
  expect(client.getQueryData(['companion','subtitle-exports','second'])).toBeDefined();
  client.clear();
});

it.each([
  ['ass', '导出 ASS'], ['burn', '烧录切片 MP4'], ['arctime', '导出 ArcTime ZIP'],
])('sends only applicable %s fields after project selection changes', async (kind, label) => {
  const posts: Record<string, unknown>[] = [];
  vi.stubGlobal('fetch', vi.fn(async (_url: string, init?: RequestInit) => {
    posts.push(JSON.parse(String(init?.body)));
    return new Response(JSON.stringify({ id: 'job' }));
  }));
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  const document = documentFixture();
  const component = (project: string | null) => <QueryClientProvider client={client}>
    <SubtitleExports id="job" video="clip-001.mp4" bilingual style={document.style} project={project}
      busy={false} burnAvailable nativeAvailable={false} error={null} document={document}/>
  </QueryClientProvider>;
  const view = render(component('first-project'));
  for (const project of ['first-project', 'switched-project', null]) {
    view.rerender(component(project));
    await waitFor(() => expect(screen.getByRole('button', { name: label })).toBeEnabled());
    const count = posts.length;
    fireEvent.click(screen.getByRole('button', { name: label }));
    await waitFor(() => expect(posts).toHaveLength(count + 1));
    expect(posts[count]).toEqual({ kind, video: 'clip-001.mp4', bilingual: true, style: document.style, document,
      ...(kind === 'arctime' ? { arctime_template_id: project } : {}) });
  }
});
