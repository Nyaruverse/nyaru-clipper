import { useQueryClient } from "@tanstack/react-query";
import type { QueryKey } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { getWorkstationEventsUrl, workstationEventNames, workstationFallbackPollingInterval, workstationReconnectDelays } from "./events";
import { workstationKeys } from "./queryKeys";

export type WorkstationConnectionState = "connecting" | "open" | "fallback";

export interface WorkstationEventConnection {
  readonly state: WorkstationConnectionState;
  readonly lastEventId: string | null;
}

interface EventPayload {
  readonly task_id?: string;
}

function hasTaskId(value: unknown): value is { readonly task_id: string } {
  return value !== null && typeof value === "object" && "task_id" in value && typeof value.task_id === "string";
}

function parseEventPayload(data: string): EventPayload {
  try {
    const parsed: unknown = JSON.parse(data);
    if (hasTaskId(parsed)) {
      return { task_id: parsed.task_id };
    }
  } catch {
    return {};
  }

  return {};
}

function isTaskProjectionEvent(eventName: string): boolean {
  return eventName === "task.created" || eventName === "task.deleted" || eventName === "task.updated" || eventName === "stage.updated" || eventName === "artifact.ready";
}

export function useWorkstationEvents(): WorkstationEventConnection {
  const queryClient = useQueryClient();
  const [state, setState] = useState<WorkstationConnectionState>("connecting");
  const [lastEventId, setLastEventId] = useState<string | null>(null);

  useEffect(() => {
    let eventSource: EventSource | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let fallbackTimer: ReturnType<typeof setInterval> | null = null;
    let refreshTimer: ReturnType<typeof setTimeout> | null = null;
    let tasksPending = false;
    let queuePending = false;
    const pendingTaskIds = new Set<string>();
    let consecutiveFailures = 0;
    let lastReceivedEventId: string | null = null;
    let disposed = false;

    const refreshProjection = (queryKey: QueryKey) => {
      // Invalidation alone reuses an initial pending fetch with no cached data.
      void queryClient.cancelQueries({ queryKey });
      void queryClient.invalidateQueries({ queryKey });
    };

    const flushPendingProjections = () => {
      if (refreshTimer !== null) {
        clearTimeout(refreshTimer);
        refreshTimer = null;
      }
      if (tasksPending) {
        refreshProjection(workstationKeys.summary);
        refreshProjection(["workstation", "tasks", "list"]);
        for (const taskId of pendingTaskIds) refreshProjection(workstationKeys.detail(taskId));
      }
      if (queuePending) refreshProjection(workstationKeys.queue);
      tasksPending = false;
      queuePending = false;
      pendingTaskIds.clear();
    };

    const scheduleRefresh = () => {
      if (refreshTimer === null) refreshTimer = setTimeout(flushPendingProjections, 50);
    };

    const invalidateFallbackProjections = () => {
      void queryClient.invalidateQueries({ queryKey: ["workstation", "tasks"] });
      void queryClient.invalidateQueries({ queryKey: workstationKeys.queue });
    };

    const stopFallbackPolling = () => {
      if (fallbackTimer !== null) {
        clearInterval(fallbackTimer);
        fallbackTimer = null;
      }
    };

    const startFallbackPolling = () => {
      if (fallbackTimer === null) {
        fallbackTimer = setInterval(invalidateFallbackProjections, workstationFallbackPollingInterval);
      }
    };

    const connect = () => {
      if (disposed) {
        return;
      }

      setState(consecutiveFailures >= workstationReconnectDelays.length ? "fallback" : "connecting");
      eventSource = new EventSource(getWorkstationEventsUrl(lastReceivedEventId));
      eventSource.onopen = () => {
        if (disposed) {
          return;
        }
        consecutiveFailures = 0;
        stopFallbackPolling();
        setState("open");
      };
      eventSource.onerror = () => {
        if (disposed) {
          return;
        }

        eventSource?.close();
        flushPendingProjections();
        consecutiveFailures += 1;
        const delayIndex = Math.min(consecutiveFailures - 1, workstationReconnectDelays.length - 1);
        const retryDelay = workstationReconnectDelays[delayIndex];

        if (consecutiveFailures >= workstationReconnectDelays.length) {
          setState("fallback");
          startFallbackPolling();
        } else {
          setState("connecting");
        }

        reconnectTimer = setTimeout(connect, retryDelay);
      };

      for (const eventName of workstationEventNames) {
        eventSource.addEventListener(eventName, (event) => {
          if (disposed || !(event instanceof MessageEvent) || typeof event.data !== "string") {
            return;
          }
          if (event.lastEventId !== "") {
            lastReceivedEventId = event.lastEventId;
            setLastEventId(event.lastEventId);
          }
          if (isTaskProjectionEvent(eventName)) {
            tasksPending = true;
            const taskId = parseEventPayload(event.data).task_id;
            if (taskId !== undefined) pendingTaskIds.add(taskId);
            scheduleRefresh();
            return;
          }
          if (eventName === "queue.updated") {
            queuePending = true;
            scheduleRefresh();
          }
        });
      }
    };

    connect();

    return () => {
      disposed = true;
      eventSource?.close();
      if (reconnectTimer !== null) {
        clearTimeout(reconnectTimer);
      }
      if (refreshTimer !== null) clearTimeout(refreshTimer);
      stopFallbackPolling();
    };
  }, [queryClient]);

  return { state, lastEventId };
}
