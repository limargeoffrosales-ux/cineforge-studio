import { useEffect, useRef, useState } from "react";

// Live pipeline updates over WebSocket with automatic polling fallback.
// In the hosted preview the browser cannot reach the API directly, so we
// connect via the same origin (`/api/backend/ws` — proxied by Next.js).
// If the socket fails, we fall back to polling the REST status endpoint.

export interface WsEvent {
  type: string;
  project_id?: string;
  stage_id?: string;
  status?: string;
  progress?: number;
  project_progress?: number;
  error?: string;
  stages?: Record<string, any>;
  running?: boolean;
}

export function usePipelineSocket(
  projectId: string | null,
  onEvent: (ev: WsEvent) => void
): { connected: boolean; mode: "ws" | "poll" } {
  const [connected, setConnected] = useState(false);
  const [mode, setMode] = useState<"ws" | "poll">("ws");
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    if (!projectId) return;
    let ws: WebSocket | null = null;
    let pollTimer: ReturnType<typeof setInterval> | null = null;
    let wsOk = false;
    let closed = false;

    const startPolling = () => {
      if (pollTimer || closed) return;
      setMode("poll");
      const tick = async () => {
        try {
          const res = await fetch(`/api/backend/pipeline/projects/${projectId}`);
          if (res.ok) {
            const data = await res.json();
            onEventRef.current({ type: "poll", project_progress: data.progress, stages: data.stages, running: data.running });
          }
        } catch {
          /* offline */
        }
      };
      tick();
      pollTimer = setInterval(tick, 2000);
    };

    const token = localStorage.getItem("cineforge_token") || "";
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    try {
      ws = new WebSocket(`${proto}://${window.location.host}/api/backend/ws?token=${encodeURIComponent(token)}`);
    } catch {
      startPolling();
      return () => {};
    }

    ws.onopen = () => {
      wsOk = true;
      setConnected(true);
      setMode("ws");
      ws?.send(JSON.stringify({ type: "subscribe", project_id: projectId }));
    };
    ws.onmessage = (e) => {
      try {
        onEventRef.current(JSON.parse(e.data) as WsEvent);
      } catch {
        /* ignore */
      }
    };
    ws.onclose = () => {
      setConnected(false);
      if (!closed) startPolling();
    };
    ws.onerror = () => {
      // Dev/proxy environments often can't upgrade — fall back to polling.
      if (!wsOk && !closed) startPolling();
    };

    return () => {
      closed = true;
      if (pollTimer) clearInterval(pollTimer);
      try {
        ws?.close();
      } catch {
        /* noop */
      }
    };
  }, [projectId]);

  return { connected, mode };
}
