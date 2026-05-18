import { useEffect, useRef, useState } from "react";
import type { ConnState, PipelineEvent } from "./types";

/** Subscribes to the FastAPI SSE feed (`/events`, event name "pipeline"). */
export function useEvents() {
  const [events, setEvents] = useState<PipelineEvent[]>([]);
  const [conn, setConn] = useState<ConnState>("connecting");
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const es = new EventSource("/events");
    esRef.current = es;
    es.onopen = () => setConn("live");
    es.onerror = () => setConn("lost");
    es.addEventListener("pipeline", (e) => {
      try {
        const ev = JSON.parse((e as MessageEvent).data) as PipelineEvent;
        setEvents((prev) => [...prev, ev]);
      } catch {
        /* ignore malformed frame */
      }
    });
    return () => es.close();
  }, []);

  return { events, conn };
}

export async function drivePatient(message: string): Promise<string> {
  const r = await fetch("/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const j = await r.json();
  return j.reply ?? JSON.stringify(j);
}
