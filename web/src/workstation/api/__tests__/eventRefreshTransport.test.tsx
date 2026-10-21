import { act, cleanup, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ContextInspector } from "../../components/ContextInspector";
import { TaskInspector } from "../../features/task-library/TaskInspector";
import { TaskLibraryPage } from "../../features/task-library/TaskLibraryPage";
import { workstationKeys } from "../queryKeys";
import { captureRequests, EventStream, latestStream, mountTransport, QueueProbe, respondAll, tick } from "./eventTransportHarness";

describe("event projection refresh at the fetch boundary", () => {
  beforeEach(() => { vi.useFakeTimers(); vi.stubGlobal("EventSource", EventStream); });
  afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); EventStream.instances = []; });

  it.each([false, true])("coalesces 100 events and aborts stale requests (cached=%s)", async (cached) => {
    const requests = captureRequests();
    const { client } = mountTransport(<><TaskLibraryPage /><ContextInspector /><TaskInspector taskId="a" /><TaskInspector taskId="b" /><QueueProbe /></>);
    expect(requests).toHaveLength(6);
    if (cached) {
      await respondAll(requests);
      act(() => { void client.refetchQueries({ queryKey: workstationKeys.all }); });
      expect(requests).toHaveLength(12);
    }
    const before = requests.length;
    const staleRequests = requests.slice(-6);
    act(() => {
      for (let index = 1; index <= 100; index += 1) latestStream().emit("stage.updated", "a", String(index));
      latestStream().emit("task.updated", "b", "101");
      latestStream().emit("task.deleted", "a", "102");
      for (let index = 0; index < 100; index += 1) latestStream().emit("queue.updated", "a", "103");
    });
    expect(screen.getByTestId("connection")).toHaveTextContent(":103");
    expect(requests).toHaveLength(before);
    await tick(50);
    expect(requests).toHaveLength(before + 6);
    expect(staleRequests.every(({ request }) => request.signal.aborted)).toBe(true);
    const refreshed = requests.slice(before);
    expect(new Set(refreshed.map(({ request }) => request.url)).size).toBe(6);
    await respondAll(refreshed, 100);
    await respondAll(staleRequests, 0);
    expect(client.getQueryData(workstationKeys.summary)).toMatchObject({ active: 100 });
    expect(client.getQueryData(workstationKeys.detail("a"))).toMatchObject({ progress_percent: 100 });
    expect(client.getQueryData(workstationKeys.detail("b"))).toMatchObject({ progress_percent: 100 });
    expect(client.getQueryData(workstationKeys.queue)).toMatchObject({ revision: 100 });
    expect(screen.getByRole("heading", { name: "Task a v100" })).toBeVisible();
  });

  it("refreshes every fixed window during a continuous event stream", async () => {
    const requests = captureRequests();
    mountTransport(<TaskInspector taskId="a" />);
    await respondAll(requests);
    for (let index = 0; index < 15; index += 1) {
      act(() => latestStream().emit("task.updated", "a", String(index + 1)));
      await tick(10);
      if (index % 5 === 4) {
        expect(requests).toHaveLength(2 + Math.floor(index / 5));
        await respondAll(requests.slice(-1), index + 1);
      }
    }
    expect(screen.getByRole("heading", { name: "Task a v15" })).toBeVisible();
  });

  it("refreshes active capacity and both lists after a terminal task.updated event", async () => {
    const requests = captureRequests();
    const { client } = mountTransport(<><TaskLibraryPage /><ContextInspector /></>);
    await respondAll(requests, 1);
    expect(screen.getByText("运行中 1")).toBeVisible();
    act(() => latestStream().listeners.get("task.updated")?.(new MessageEvent("task.updated", {
      data: JSON.stringify({ task_id: "a", status: "failed" }), lastEventId: "18",
    })));
    await tick(50);
    expect(requests).toHaveLength(6);
    await respondAll(requests.slice(3), 0);
    expect(screen.getByText("运行中 0")).toBeVisible();
    expect(client.getQueriesData({ queryKey: ["workstation", "tasks", "list"] }).every(([, data]) => data !== undefined)).toBe(true);
  });

  it("flushes pending work on disconnect before reconnecting from the latest cursor", async () => {
    const requests = captureRequests();
    mountTransport(<TaskInspector taskId="a" />);
    await respondAll(requests);
    const first = latestStream();
    act(() => { first.emit("task.updated", "a", "37"); first.onerror?.(); });
    expect(requests).toHaveLength(2);
    await respondAll(requests.slice(-1), 37);
    await tick(1_000);
    expect(first.closed).toBe(true);
    expect(new URL(latestStream().url).searchParams.get("cursor")).toBe("37");
    expect(screen.getByRole("heading", { name: "Task a v37" })).toBeVisible();
    expect(requests).toHaveLength(2);
  });

  it("polls actual projections after five failures and stops on open and unmount", async () => {
    const requests = captureRequests();
    const view = mountTransport(<><TaskInspector taskId="a" /><QueueProbe /></>);
    const invalidations = vi.spyOn(view.client, "invalidateQueries");
    await respondAll(requests);
    for (const delay of [1_000, 2_000, 5_000, 10_000]) {
      act(() => latestStream().onerror?.());
      await tick(delay);
    }
    act(() => latestStream().onerror?.());
    await tick(15_000);
    expect(requests).toHaveLength(4);
    await respondAll(requests.slice(-2), 2);
    await tick(15_000);
    act(() => latestStream().onopen?.());
    const afterOpen = requests.length;
    await tick(30_000);
    expect(requests).toHaveLength(afterOpen);
    act(() => latestStream().emit("stage.updated"));
    view.unmount();
    invalidations.mockClear();
    expect(latestStream().closed).toBe(true);
    act(() => latestStream().emit("stage.updated"));
    await tick(60_000);
    expect(requests).toHaveLength(afterOpen);
    expect(invalidations).not.toHaveBeenCalled();
  });

  it("cancels the reconnect and polling timers on unmount during fallback", async () => {
    const requests = captureRequests();
    const { unmount } = mountTransport(<TaskInspector taskId="a" />);
    for (const delay of [1_000, 2_000, 5_000, 10_000]) {
      act(() => latestStream().onerror?.());
      await tick(delay);
    }
    act(() => latestStream().onerror?.());
    const connections = EventStream.instances.length;
    unmount();
    await tick(60_000);
    expect(EventStream.instances).toHaveLength(connections);
    expect(requests).toHaveLength(1);
    expect(requests[0]?.request.signal.aborted).toBe(true);
  });
});
