import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ClipExportResponse, HighlightArtifactPayload } from "../../../../lib/types";
import { exportTaskClip } from "../../../../lib/api";
import { workstationKeys } from "../../../api/queryKeys";
import { getWorkstationTaskOverview, type WorkstationTaskOverview } from "../api";
import { TaskOverviewPage } from "../TaskOverviewPage";

vi.mock("../api", () => ({ getWorkstationTaskOverview: vi.fn() }));
vi.mock("../../../../lib/api", async (importOriginal) => ({
  ...await importOriginal<typeof import("../../../../lib/api")>(),
  exportTaskClip: vi.fn(),
}));

const clip: ClipExportResponse = {
  artifact_id: 9, candidate_id: 8, end_s: 20, filename: "task-a-clip.mp4",
  path: "/api/tasks/task-a/artifacts/9/content/task-a-clip.mp4", start_s: 10, task_id: "task-a",
};

function overview(taskId: string): WorkstationTaskOverview {
  const path = `/api/tasks/${taskId}/artifacts/3/content/highlights.json`;
  return {
    archived_at: null, artifact_readiness: [{ artifact_id: 3, kind: "highlight_candidates_json", path, stage_name: "highlight", status: "ready" }],
    artifacts: [{ artifact_id: 3, created_at: "2026-10-21T00:00:00Z", kind: "highlight_candidates_json", metadata_json: "{}", path, stage_name: "highlight" }],
    created_at: "2026-10-21T00:00:00Z", current_stage: null, execution_progress: null,
    highlight_filtering_enabled: true, pipeline_run_id: null, progress_percent: 100,
    recovery_actions: [], safe_logs: [], source_kind: "local", source_label: taskId,
    stages: [], status: "success", storage_bytes: 0, tags: [], task_id: taskId,
    title: `Overview ${taskId}`, updated_at: "2026-10-21T00:00:00Z",
  };
}

function persistedOverview(): WorkstationTaskOverview {
  const task = overview("task-a");
  return {
    ...task,
    artifacts: [...task.artifacts, {
      artifact_id: clip.artifact_id, created_at: "2026-10-21T00:01:00Z", kind: "clip_export",
      metadata_json: JSON.stringify({ candidate_id: clip.candidate_id, start_s: clip.start_s, end_s: clip.end_s }),
      path: clip.path, stage_name: "export",
    }],
  };
}

function SwitchableOverview() {
  const [taskId, setTaskId] = useState("task-a");
  return <>
    <button onClick={() => setTaskId("task-a")} type="button">Open A</button>
    <button onClick={() => setTaskId("task-b")} type="button">Open B</button>
    <TaskOverviewPage taskId={taskId} />
  </>;
}

function renderCachedTasks() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity }, mutations: { retry: false } } });
  for (const taskId of ["task-a", "task-b"]) {
    client.setQueryData(workstationKeys.detail(taskId), overview(taskId));
    const start = taskId === "task-a" ? 10 : 30;
    client.setQueryData<HighlightArtifactPayload>(["artifact", taskId, 3], {
      candidates: [{ candidate_id: 8, default_range: { start_s: start, end_s: start + 10 }, end_s: start + 10, rank: 1, reasons: [], score: 0.9, start_s: start }],
    });
  }
  render(<QueryClientProvider client={client}><MemoryRouter><SwitchableOverview /></MemoryRouter></QueryClientProvider>);
  return client;
}

function deferredExport() {
  let resolve: (value: ClipExportResponse) => void = () => { throw new Error("Export promise not initialized"); };
  let reject: (error: Error) => void = () => { throw new Error("Export promise not initialized"); };
  const promise = new Promise<ClipExportResponse>((onResolve, onReject) => { resolve = onResolve; reject = onReject; });
  return { promise, resolve, reject };
}

function switchToB() {
  fireEvent.click(screen.getByRole("button", { name: "Open B" }));
  expect(screen.getByRole("heading", { name: "Overview task-b" })).toBeVisible();
  expect(getWorkstationTaskOverview).not.toHaveBeenCalledWith("task-b", expect.any(AbortSignal));
}

function expectOnlyTaskALinks() {
  const links = screen.getAllByRole("link", { name: "下载已导出片段" });
  expect(links.length).toBeGreaterThan(0);
  for (const link of links) expect(link).toHaveAttribute("href", `http://127.0.0.1:8000${clip.path}`);
}

describe("task ownership in the real overview/review component tree", () => {
  afterEach(() => vi.resetAllMocks());

  it("keeps a completed A export out of cached B and reloads persisted output when returning to A", async () => {
    vi.mocked(exportTaskClip).mockResolvedValue(clip);
    vi.mocked(getWorkstationTaskOverview).mockResolvedValue(persistedOverview());
    renderCachedTasks();
    fireEvent.click(screen.getByTestId("candidate-confirm-button"));
    await waitFor(expectOnlyTaskALinks);
    expect(exportTaskClip).toHaveBeenCalledWith("task-a", { candidate_id: 8, start_s: 10, end_s: 20 });

    switchToB();
    expect(screen.queryByRole("link", { name: "下载已导出片段" })).not.toBeInTheDocument();
    expect(screen.getByTestId("candidate-start-input")).toHaveValue(30);
    fireEvent.click(screen.getByRole("button", { name: "Open A" }));
    await waitFor(expectOnlyTaskALinks);
    expect(getWorkstationTaskOverview).toHaveBeenCalledWith("task-a", expect.any(AbortSignal));
  });

  it("settles delayed A success against A's inactive cache without changing B's output or mutation state", async () => {
    const pending = deferredExport();
    vi.mocked(exportTaskClip).mockReturnValue(pending.promise);
    vi.mocked(getWorkstationTaskOverview).mockResolvedValue(persistedOverview());
    const client = renderCachedTasks();
    fireEvent.click(screen.getByTestId("candidate-confirm-button"));
    await waitFor(() => expect(exportTaskClip).toHaveBeenCalledWith("task-a", { candidate_id: 8, start_s: 10, end_s: 20 }));
    switchToB();
    const bWasEnabled = !screen.getByTestId("candidate-confirm-button").hasAttribute("disabled");

    await act(async () => pending.resolve(clip));
    await waitFor(() => expect(client.getMutationCache().getAll()[0]?.state.status).toBe("success"));
    expect(screen.queryByRole("link", { name: "下载已导出片段" })).not.toBeInTheDocument();
    expect(bWasEnabled).toBe(true);
    expect(client.getQueryState(workstationKeys.detail("task-a"))?.isInvalidated).toBe(true);
    expect(client.getQueryState(workstationKeys.detail("task-b"))?.isInvalidated).toBe(false);
    expect(getWorkstationTaskOverview).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Open A" }));
    await waitFor(expectOnlyTaskALinks);
    expect(getWorkstationTaskOverview).toHaveBeenCalledTimes(1);
    expect(getWorkstationTaskOverview).toHaveBeenCalledWith("task-a", expect.any(AbortSignal));
  });

  it("keeps B's error and edited range when A fails after the task switch", async () => {
    const pending = deferredExport();
    vi.mocked(exportTaskClip).mockReturnValueOnce(pending.promise).mockRejectedValueOnce(new Error("B export failed"));
    renderCachedTasks();
    fireEvent.click(screen.getByTestId("candidate-confirm-button"));
    await waitFor(() => expect(exportTaskClip).toHaveBeenCalledTimes(1));
    switchToB();
    const bWasEnabled = !screen.getByTestId("candidate-confirm-button").hasAttribute("disabled");
    fireEvent.change(screen.getByTestId("candidate-start-input"), { target: { value: "31" } });
    fireEvent.click(screen.getByTestId("candidate-confirm-button"));
    await act(async () => pending.reject(new Error("A export failed late")));

    expect(await screen.findByText("B export failed")).toBeVisible();
    expect(screen.queryByText("A export failed late")).not.toBeInTheDocument();
    expect(screen.getByTestId("candidate-start-input")).toHaveValue(31);
    expect(screen.getByTestId("candidate-end-input")).toHaveValue(40);
    expect(bWasEnabled).toBe(true);
    expect(exportTaskClip).toHaveBeenLastCalledWith("task-b", { candidate_id: 8, start_s: 31, end_s: 40 });
  });

  it("resets candidate edits and validation errors when the same candidate id belongs to another task", () => {
    renderCachedTasks();
    fireEvent.change(screen.getByTestId("candidate-start-input"), { target: { value: "25" } });
    fireEvent.click(screen.getByTestId("candidate-confirm-button"));
    expect(screen.getByText("开始时间必须早于结束时间")).toBeVisible();

    switchToB();
    expect(screen.queryByText("开始时间必须早于结束时间")).not.toBeInTheDocument();
    expect(screen.getByTestId("candidate-start-input")).toHaveValue(30);
    expect(screen.getByTestId("candidate-end-input")).toHaveValue(40);
    expect(screen.getByTestId("candidate-confirm-button")).toBeEnabled();
    expect(exportTaskClip).not.toHaveBeenCalled();
  });
});
