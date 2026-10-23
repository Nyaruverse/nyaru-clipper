import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { act, render } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import { getQueue } from "../../features/queue/api";
import { workstationKeys } from "../queryKeys";
import { useWorkstationEvents } from "../useWorkstationEvents";

export class EventStream {
  static instances: EventStream[] = [];
  readonly listeners = new Map<string, EventListener>();
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  constructor(readonly url: string) { EventStream.instances.push(this); }
  addEventListener(name: string, listener: EventListener): void { this.listeners.set(name, listener); }
  close(): void { this.closed = true; }
  emit(name: string, taskId = "a", id = "1"): void {
    this.listeners.get(name)?.(new MessageEvent(name, { data: JSON.stringify({ task_id: taskId }), lastEventId: id }));
  }
}

export function latestStream(): EventStream {
  const stream = EventStream.instances[EventStream.instances.length - 1];
  if (!stream) throw new Error("Expected a connected EventSource");
  return stream;
}

export interface PendingRequest {
  readonly request: Request;
  readonly respond: (body: unknown) => void;
}

export function captureRequests(): PendingRequest[] {
  const requests: PendingRequest[] = [];
  vi.stubGlobal("fetch", (input: RequestInfo | URL) => {
    if (!(input instanceof Request)) throw new Error("Expected openapi-fetch Request");
    return new Promise<Response>((resolve, reject) => {
      requests.push({ request: input, respond: (body) => resolve(new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" } })) });
      input.signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true });
    });
  });
  return requests;
}

export function responseFor(request: Request, version = 1): object {
  const url = new URL(request.url);
  if (url.pathname.endsWith("/summary")) return { active: version, archived: 0, queued: 0, failed: 0, review_required: 0, storage_bytes: 0 };
  if (url.pathname.endsWith("/tasks")) return { items: [], page: 1, page_count: 1, page_size: 50, total: 0 };
  if (url.pathname.endsWith("/queue")) return { active: null, paused: [], queued: [], revision: version };
  const taskId = url.pathname.split("/").pop();
  return {
    archived_at: null, artifact_readiness: [], artifacts: [], created_at: "2026-10-21T00:00:00Z",
    current_stage: null, execution_progress: null, pipeline_run_id: null, progress_percent: version,
    recovery_actions: [], safe_logs: [], source_kind: "local", source_label: taskId, stages: [],
    status: "success", storage_bytes: 0, tags: [], task_id: taskId, title: `Task ${taskId} v${version}`,
    updated_at: "2026-10-21T00:00:00Z", highlight_filtering_enabled: false,
  };
}

export async function respondAll(requests: readonly PendingRequest[], version = 1): Promise<void> {
  await act(async () => {
    for (const entry of requests) entry.respond(responseFor(entry.request, version));
  });
  await tick(1);
}

export async function tick(ms: number): Promise<void> {
  await act(async () => { await vi.advanceTimersByTimeAsync(ms); });
}

export function ConnectionProbe(): ReactNode {
  const connection = useWorkstationEvents();
  return <output data-testid="connection">{connection.state}:{connection.lastEventId}</output>;
}

export function QueueProbe(): ReactNode {
  useQuery({ queryKey: workstationKeys.queue, queryFn: ({ signal }) => getQueue(signal) });
  return null;
}

export function mountTransport(children: ReactNode, route = "/workstation") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });
  const view = render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[route]}><ConnectionProbe />{children}</MemoryRouter></QueryClientProvider>);
  return { client, ...view };
}
