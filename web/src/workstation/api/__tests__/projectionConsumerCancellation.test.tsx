import { cleanup, fireEvent, screen } from "@testing-library/react";
import { useState } from "react";
import { Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ContextInspector } from "../../components/ContextInspector";
import { TaskInspector } from "../../features/task-library/TaskInspector";
import { TaskLibraryPage } from "../../features/task-library/TaskLibraryPage";
import { TaskOverviewPage } from "../../features/task-overview/TaskOverviewPage";
import { captureRequests, EventStream, mountTransport, respondAll, tick } from "./eventTransportHarness";

describe("projection query consumers forward cancellation to fetch", () => {
  beforeEach(() => { vi.useFakeTimers(); vi.stubGlobal("EventSource", EventStream); });
  afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); EventStream.instances = []; });

  it.each([
    { name: "library summary and list", ui: <TaskLibraryPage />, route: "/workstation", count: 2 },
    { name: "workspace inspector summary and running list", ui: <ContextInspector />, route: "/workstation", count: 2 },
    { name: "selected task inspector", ui: <TaskInspector taskId="a" />, route: "/workstation", count: 1 },
    { name: "task overview page wrapper", ui: <TaskOverviewPage taskId="a" />, route: "/workstation/tasks/a", count: 1 },
    { name: "overview context inspector wrapper", ui: <Routes><Route path="/workstation/tasks/:taskId" element={<ContextInspector />} /></Routes>, route: "/workstation/tasks/a", count: 1 },
  ])("aborts pending $name requests on unmount", ({ ui, route, count }) => {
    const requests = captureRequests();
    const { unmount } = mountTransport(ui, route);
    expect(requests).toHaveLength(count);
    unmount();
    expect(requests.every(({ request }) => request.signal.aborted)).toBe(true);
  });

  it("aborts a slow A response when overview switches to B and retains B ownership", async () => {
    function Switcher() {
      const [taskId, setTaskId] = useState("a");
      return <><button onClick={() => setTaskId("b")}>Open B</button><TaskOverviewPage taskId={taskId} /></>;
    }
    const requests = captureRequests();
    mountTransport(<Switcher />);
    fireEvent.click(screen.getByRole("button", { name: "Open B" }));
    expect(requests).toHaveLength(2);
    expect(requests[0]?.request.signal.aborted).toBe(true);
    await respondAll(requests.slice(1), 2);
    await respondAll(requests.slice(0, 1), 1);
    expect(screen.getByRole("heading", { name: "Task b v2" })).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Task a v1" })).not.toBeInTheDocument();
  });

  it("retains the library while canceling a superseded slow filter request", async () => {
    const requests = captureRequests();
    mountTransport(<TaskLibraryPage />);
    await respondAll(requests);
    const search = screen.getByRole("searchbox", { name: "搜索任务" });
    fireEvent.change(search, { target: { value: "first" } });
    await tick(250);
    expect(requests).toHaveLength(3);
    expect(screen.getByRole("searchbox", { name: "搜索任务" })).toBeVisible();
    fireEvent.change(search, { target: { value: "second" } });
    await tick(250);
    expect(requests).toHaveLength(4);
    expect(requests[2]?.request.signal.aborted).toBe(true);
    expect(new URL(requests[3]?.request.url ?? "http://example.test").searchParams.get("query")).toBe("second");
    await respondAll(requests.slice(3));
    await respondAll(requests.slice(2, 3));
    expect(search).toHaveValue("second");
  });
});
