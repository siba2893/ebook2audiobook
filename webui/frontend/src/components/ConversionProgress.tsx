import { useEffect, useRef, useState } from "react";
import { SessionStatus, SseEvent, cancelConversion, getSession, subscribeEvents } from "../api";

interface Props {
  sessionId: string;
  onDone: () => void;
  onResume?: () => void;
}

function fmtSeconds(s: number): string {
  if (s < 60) return `${Math.round(s)}s`;
  if (s < 3600) {
    const m = Math.floor(s / 60);
    const r = Math.round(s % 60);
    return `${m}m ${r}s`;
  }
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return `${h}h ${m}m`;
}

export default function ConversionProgress({ sessionId, onDone, onResume }: Props) {
  const [status, setStatus] = useState<SessionStatus | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [elapsed, setElapsed] = useState(0);
  const [stopping, setStopping] = useState(false);
  // Bumped each time we resume; the SSE subscription closes on the terminal
  // "cancelled" event, so we need a fresh EventSource for the new run.
  const [subKey, setSubKey] = useState(0);
  const logsRef = useRef<HTMLDivElement | null>(null);
  const startRef = useRef<number>(Date.now());

  // Poll session status every 4s
  useEffect(() => {
    getSession(sessionId).then(setStatus).catch(() => undefined);
    const tick = setInterval(() => {
      getSession(sessionId).then(setStatus).catch(() => undefined);
    }, 4000);
    return () => clearInterval(tick);
  }, [sessionId]);

  // Elapsed timer
  useEffect(() => {
    startRef.current = Date.now();
    const t = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startRef.current) / 1000));
    }, 1000);
    return () => clearInterval(t);
  }, []);

  // SSE events.  The dependency on subKey makes resume re-open the stream
  // (the prior EventSource was closed when "cancelled" arrived).
  useEffect(() => {
    const unsub = subscribeEvents(sessionId, (e: SseEvent) => {
      if (e.type === "alert") {
        setLogs((l) => [...l, e.msg].slice(-200));
      } else if (e.type === "status") {
        setStatus((s) => s ? { ...s, status: e.status } : s);
        if (e.status === "done" || e.status === "error" || e.status === "cancelled") {
          getSession(sessionId).then(setStatus).catch(() => undefined);
        }
      }
    });
    return unsub;
  }, [sessionId, subKey]);

  // Auto-scroll log
  useEffect(() => {
    if (logsRef.current) {
      logsRef.current.scrollTop = logsRef.current.scrollHeight;
    }
  }, [logs]);

  const isDone = status?.status === "done";
  const isStopped = status?.status === "cancelled";
  const isError = status?.status === "error";
  const isTerminal = isDone || isError || isStopped;
  const isCancelling = stopping && !isTerminal;

  // Reset the local "stopping" flag once the backend confirms the stop —
  // the SSE/poll path eventually flips status to "cancelled".
  useEffect(() => {
    if (isStopped && stopping) setStopping(false);
  }, [isStopped, stopping]);

  const ratio = status && status.blocks_total > 0
    ? Math.min(1, status.block_resume / status.blocks_total)
    : 0;

  return (
    <section className="space-y-6">
      <div className="flex items-baseline justify-between">
        <div>
          <p className="text-xs uppercase tracking-widest text-zinc-500">step 04</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight">Converting</h2>
          {status?.filename && (
            <p className="mt-1 text-xs text-zinc-500 font-mono">{status.filename}</p>
          )}
        </div>
        <div className="text-right">
          <div className="text-xs uppercase tracking-widest text-zinc-500">status</div>
          <div className="mt-1 text-sm font-mono">{status?.status ?? "—"}</div>
        </div>
      </div>

      <div className="surface p-6 space-y-5">
        <div className="grid grid-cols-3 text-center">
          <Stat
            label="block"
            value={status ? `${status.block_resume}/${status.blocks_total || "?"}` : "—"}
          />
          <Stat label="elapsed" value={fmtSeconds(elapsed)} />
          <Stat label="state" value={status?.status ?? "—"} />
        </div>

        <div className="h-1.5 bg-zinc-900 rounded-full overflow-hidden">
          <div
            className="h-full bg-zinc-100 transition-all duration-700 ease-out"
            style={{ width: `${ratio * 100}%` }}
          />
        </div>
      </div>

      <div className="surface-muted">
        <div className="px-4 py-2 text-xs uppercase tracking-wider text-zinc-500 border-b border-zinc-800">
          log
        </div>
        <div
          ref={logsRef}
          className="px-4 py-3 max-h-72 overflow-auto font-mono text-xs leading-relaxed space-y-1"
        >
          {logs.length === 0 ? (
            <span className="text-zinc-600">waiting for events…</span>
          ) : (
            logs.map((l, i) => (
              <div key={i} className="text-zinc-300 whitespace-pre-wrap">{l}</div>
            ))
          )}
        </div>
      </div>

      {status?.error && (
        <p className="text-xs text-red-400">{status.error}</p>
      )}

      <div className="flex justify-between items-center gap-3">
        {isStopped && onResume ? (
          <button
            className="btn-primary"
            onClick={() => {
              setStatus((s) => s ? { ...s, status: "converting" } : s);
              setLogs([]);
              startRef.current = Date.now();
              setSubKey((k) => k + 1);
              onResume();
            }}
          >
            resume
          </button>
        ) : (
          <button
            className="btn"
            disabled={isTerminal || isCancelling}
            onClick={() => {
              setStopping(true);
              cancelConversion(sessionId).catch(() => setStopping(false));
            }}
          >
            {isCancelling ? "stopping…" : "stop"}
          </button>
        )}
        {isStopped && (
          <p className="text-xs text-zinc-500">
            stopped at block {status?.block_resume ?? 0}
            {status && status.blocks_total > 0 ? ` / ${status.blocks_total}` : ""} —
            click resume to continue from here.
          </p>
        )}
        {isDone && (
          <button className="btn-primary" onClick={onDone}>
            open library
          </button>
        )}
      </div>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-widest text-zinc-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>
    </div>
  );
}
