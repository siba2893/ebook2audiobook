import { useEffect, useRef, useState } from "react";
import {
  LibraryEntry,
  LibrarySession,
  downloadUrl,
  getSession,
  listLibrary,
  listLibrarySessions,
  deleteSession,
  combineSession,
} from "../api";

function fmtBytes(b: number): string {
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  if (b < 1024 * 1024 * 1024) return `${(b / 1024 / 1024).toFixed(1)} MB`;
  return `${(b / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString(undefined, {
      year: "numeric", month: "short", day: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return "";
  }
}

function statusLabel(s: string): string {
  const map: Record<string, string> = {
    ready: "ready",
    edit: "reviewing chapters",
    converting: "converting",
    done: "done",
    interrupted: "interrupted",
    cancelled: "cancelled",
    error: "error",
  };
  return map[s] ?? s;
}

function statusDot(s: string): string {
  if (s === "done") return "bg-zinc-400";
  if (s === "converting") return "bg-yellow-500 animate-pulse";
  if (s === "error" || s === "cancelled") return "bg-red-500";
  if (s === "interrupted") return "bg-orange-500";
  return "bg-zinc-600";
}

export default function Library() {
  const [entries, setEntries] = useState<LibraryEntry[] | null>(null);
  const [sessions, setSessions] = useState<LibrarySession[] | null>(null);
  const [deleting, setDeleting] = useState<Set<string>>(new Set());
  const [combining, setCombining] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function load() {
    Promise.all([listLibrary(), listLibrarySessions()])
      .then(([e, s]) => {
        setEntries(e);
        setSessions(s);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }

  useEffect(() => { load(); }, []);

  async function handleDelete(sessionId: string) {
    setDeleting((prev) => new Set(prev).add(sessionId));
    try {
      await deleteSession(sessionId);
      setSessions((prev) => prev?.filter((s) => s.session_id !== sessionId) ?? null);
    } catch {
      // ignore
    } finally {
      setDeleting((prev) => { const n = new Set(prev); n.delete(sessionId); return n; });
    }
  }

  async function handleCombine(sessionId: string) {
    setCombining((prev) => new Set(prev).add(sessionId));
    try {
      await combineSession(sessionId);
      // Poll session status every 2 s until done or error
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = setInterval(async () => {
        try {
          const s = await getSession(sessionId);
          if (s.status === "done" || s.status === "error") {
            clearInterval(pollRef.current!);
            pollRef.current = null;
            setCombining((prev) => { const n = new Set(prev); n.delete(sessionId); return n; });
            load();
          }
        } catch {
          clearInterval(pollRef.current!);
          pollRef.current = null;
          setCombining((prev) => { const n = new Set(prev); n.delete(sessionId); return n; });
        }
      }, 2000);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setCombining((prev) => { const n = new Set(prev); n.delete(sessionId); return n; });
    }
  }

  // Sessions that are NOT done (in-progress / incomplete)
  const incompleteSessions = (sessions ?? []).filter((s) => s.status !== "done");

  return (
    <section className="space-y-10">

      {/* ── Completed audiobooks ── */}
      <div className="space-y-4">
        <div>
          <p className="text-xs uppercase tracking-widest text-zinc-500">library</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight">Completed Audiobooks</h2>
        </div>

        {error && <p className="text-sm text-red-400">{error}</p>}

        {entries === null ? (
          <p className="text-sm text-zinc-500">loading…</p>
        ) : entries.length === 0 ? (
          <div className="surface p-10 text-center text-sm text-zinc-500">
            no audiobooks yet — finish a conversion to populate the library.
          </div>
        ) : (
          <div className="space-y-3">
            {entries.map((e) => (
              <div key={e.rel_path} className="surface p-5 flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <h3 className="text-sm font-medium tracking-tight truncate">{e.filename}</h3>
                  <p className="text-xs text-zinc-500 font-mono mt-0.5">
                    {fmtBytes(e.size_bytes)}
                    {e.created_at && <span className="ml-3">{fmtDate(e.created_at)}</span>}
                  </p>
                  <p className="text-xs text-zinc-700 font-mono mt-0.5">{e.rel_path.split("/")[1] ?? ""}</p>
                </div>
                <a
                  href={downloadUrl(e.rel_path)}
                  download={e.filename}
                  className="btn flex-shrink-0 text-xs"
                >
                  download
                </a>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Incomplete / in-progress sessions ── */}
      <div className="space-y-4">
        <div>
          <p className="text-xs uppercase tracking-widest text-zinc-500">in progress</p>
          <h2 className="mt-2 text-xl font-semibold tracking-tight">Incomplete Conversions</h2>
        </div>

        {sessions === null ? (
          <p className="text-sm text-zinc-500">loading…</p>
        ) : incompleteSessions.length === 0 ? (
          <div className="surface p-8 text-center text-sm text-zinc-500">
            no incomplete conversions.
          </div>
        ) : (
          <div className="space-y-3">
            {incompleteSessions.map((s) => {
              const pct = s.blocks_total > 0
                ? Math.round((s.block_resume / s.blocks_total) * 100)
                : 0;
              const isDel = deleting.has(s.session_id);
              const isCombining = combining.has(s.session_id);
              const canFinish = s.blocks_total > 0 && s.block_resume >= s.blocks_total;
              return (
                <div key={s.session_id} className="surface p-5 space-y-3">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${isCombining ? "bg-yellow-500 animate-pulse" : statusDot(s.status)}`} />
                        <span className="text-xs text-zinc-500 uppercase tracking-widest">
                          {isCombining ? "combining audio…" : statusLabel(s.status)}
                        </span>
                      </div>
                      <h3 className="text-sm font-medium tracking-tight truncate">{s.filename}</h3>
                      <p className="text-xs text-zinc-500 font-mono mt-0.5">
                        {s.blocks_total > 0
                          ? `${s.block_resume} / ${s.blocks_total} chapters`
                          : "0 chapters completed"}
                        {s.created_at && <span className="ml-3">{fmtDate(s.created_at)}</span>}
                      </p>
                      <p className="text-xs text-zinc-700 font-mono mt-0.5">{s.session_id}</p>
                    </div>
                    <div className="flex items-center gap-3 flex-shrink-0">
                      {canFinish && (
                        <button
                          className="btn text-xs"
                          onClick={() => handleCombine(s.session_id)}
                          disabled={isCombining}
                        >
                          {isCombining ? "combining…" : "finish"}
                        </button>
                      )}
                      <button
                        className="text-xs text-zinc-600 hover:text-red-400 transition-colors"
                        onClick={() => handleDelete(s.session_id)}
                        disabled={isDel}
                      >
                        {isDel ? "deleting…" : "delete"}
                      </button>
                    </div>
                  </div>

                  {/* Progress bar */}
                  {s.blocks_total > 0 && (
                    <div className="space-y-1">
                      <div className="h-1 bg-zinc-800 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-zinc-400 rounded-full transition-all"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <p className="text-xs text-zinc-600 text-right">{pct}%</p>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

    </section>
  );
}
