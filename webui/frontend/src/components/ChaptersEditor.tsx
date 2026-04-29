import { useEffect, useRef, useState } from "react";
import {
  Block,
  BlockFull,
  ConversionSettings,
  deleteBlock,
  getBlock,
  getBlocks,
  getSession,
  moveBlock,
  parseEbook,
  startConversion,
  subscribeEvents,
  updateBlock,
} from "../api";

interface Props {
  sessionId: string;
  onStarted: () => void;
}

export default function ChaptersEditor({ sessionId, onStarted }: Props) {
  const [blocks, setBlocks] = useState<Block[]>([]);
  const [active, setActive] = useState(0);
  const [fullBlock, setFullBlock] = useState<BlockFull | null>(null);
  const [loadingFull, setLoadingFull] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editText, setEditText] = useState("");
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [parseStatus, setParseStatus] = useState<"idle" | "parsing" | "done">("idle");
  const [parseLog, setParseLog] = useState<string[]>([]);
  const [parseProgress, setParseProgress] = useState<{ current: number; total: number } | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const unsubRef = useRef<(() => void) | null>(null);
  const logEndRef = useRef<HTMLDivElement | null>(null);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Parse / init ────────────────────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;

    async function init() {
      try {
        const s = await getSession(sessionId);
        if (cancelled) return;
        if (s.status === "edit") {
          const b = await getBlocks(sessionId);
          if (cancelled) return;
          if (b.length > 0) {
            setBlocks(b);
            setActive(0);
            setParseStatus("done");
            return;
          }
        }
      } catch { /* fall through */ }

      const raw = localStorage.getItem("ebook2audiobook:settings");
      const settings: ConversionSettings = raw ? JSON.parse(raw) : {
        language: "spa", voice_path: null, tts_engine: "xtts",
        device: "cuda", output_format: "m4b", xtts_speed: 1.0, xtts_temperature: 0.85,
      };

      setParseStatus("parsing");

      unsubRef.current = subscribeEvents(sessionId, (e) => {
        if (e.type === "alert" || e.type === "stdout") {
          const msg = e.msg;
          const m = msg.match(/Parsing chapter\s+(\d+)\s*\/\s*(\d+)/i);
          if (m) setParseProgress({ current: parseInt(m[1]), total: parseInt(m[2]) });
          setParseLog((prev) => [...prev, msg].slice(-120));
        }
      });

      parseEbook(sessionId, settings).catch((e) => {
        if (!cancelled) { setError(e instanceof Error ? e.message : String(e)); setParseStatus("idle"); }
      });

      pollRef.current = setInterval(async () => {
        if (cancelled) { clearInterval(pollRef.current!); return; }
        try {
          const s = await getSession(sessionId);
          if (s.status === "edit") {
            const b = await getBlocks(sessionId);
            if (b.length === 0) return;
            clearInterval(pollRef.current!); pollRef.current = null;
            if (unsubRef.current) { unsubRef.current(); unsubRef.current = null; }
            if (!cancelled) { setBlocks(b); setActive(0); setParseStatus("done"); }
          } else if (s.status === "error" || s.status === "cancelled") {
            clearInterval(pollRef.current!); pollRef.current = null;
            if (unsubRef.current) { unsubRef.current(); unsubRef.current = null; }
            if (!cancelled) { setError("Parse failed: " + (s.error ?? s.status)); setParseStatus("idle"); }
          }
        } catch { /* keep polling */ }
      }, 2000);
    }

    init();
    return () => {
      cancelled = true;
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
      if (unsubRef.current) { unsubRef.current(); unsubRef.current = null; }
    };
  }, [sessionId]);

  // Auto-scroll parse log
  useEffect(() => { logEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [parseLog]);

  // ── Load full block when active changes ─────────────────────────────────────
  useEffect(() => {
    if (parseStatus !== "done" || blocks.length === 0) return;
    const block = blocks[active];
    if (!block) return;
    let cancelled = false;
    setLoadingFull(true);
    setFullBlock(null);
    setDirty(false);
    getBlock(sessionId, block.id)
      .then((fb) => {
        if (cancelled) return;
        setFullBlock(fb);
        setEditTitle(fb.title);
        setEditText(fb.text);
        setLoadingFull(false);
      })
      .catch(() => { if (!cancelled) setLoadingFull(false); });
    return () => { cancelled = true; };
  }, [active, blocks, parseStatus, sessionId]);

  // ── Autosave on text/title change (debounced 800 ms) ────────────────────────
  useEffect(() => {
    if (!fullBlock || !dirty) return;
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(async () => {
      setSaving(true);
      try {
        const patch: { text?: string; title?: string } = {};
        if (editText !== fullBlock.text) patch.text = editText;
        if (editTitle !== fullBlock.title) patch.title = editTitle;
        if (Object.keys(patch).length > 0) {
          await updateBlock(sessionId, fullBlock.id, patch);
          // Sync title back into the list view
          if (patch.title) {
            setBlocks((bs) => bs.map((b) => b.id === fullBlock.id ? { ...b, title: patch.title! } : b));
          }
          setFullBlock((fb) => fb ? { ...fb, ...patch } : fb);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setSaving(false);
        setDirty(false);
      }
    }, 800);
    return () => { if (saveTimerRef.current) clearTimeout(saveTimerRef.current); };
  }, [editText, editTitle, dirty, fullBlock, sessionId]);

  // ── Block actions ────────────────────────────────────────────────────────────
  async function toggleKeep(i: number) {
    const block = blocks[i];
    const updated = { ...block, keep: !block.keep };
    setBlocks((bs) => bs.map((b, idx) => idx === i ? updated : b));
    try { await updateBlock(sessionId, block.id, { keep: updated.keep }); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }

  async function handleDelete() {
    const block = blocks[active];
    if (!block) return;
    try {
      await deleteBlock(sessionId, block.id);
      const newBlocks = blocks.filter((_, i) => i !== active);
      setBlocks(newBlocks);
      setActive(Math.min(active, newBlocks.length - 1));
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }

  async function handleMove(direction: "up" | "down") {
    const block = blocks[active];
    if (!block) return;
    try {
      const { new_index } = await moveBlock(sessionId, block.id, direction);
      // Swap locally to match server
      const newBlocks = [...blocks];
      const swapWith = direction === "up" ? active - 1 : active + 1;
      if (swapWith >= 0 && swapWith < newBlocks.length) {
        [newBlocks[active], newBlocks[swapWith]] = [newBlocks[swapWith], newBlocks[active]];
      }
      setBlocks(newBlocks);
      setActive(new_index);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }

  async function handleStart() {
    setBusy(true);
    setError(null);
    try {
      const raw = localStorage.getItem("ebook2audiobook:settings");
      const settings: ConversionSettings = raw ? JSON.parse(raw) : {
        language: "spa", voice_path: null, tts_engine: "xtts",
        device: "cuda", output_format: "m4b", xtts_speed: 1.0, xtts_temperature: 0.85,
      };
      await startConversion(sessionId, settings);
      onStarted();
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); setBusy(false); }
  }

  // ── Render: parsing ─────────────────────────────────────────────────────────
  if (error) return <p className="text-sm text-red-400">{error}</p>;

  if (parseStatus === "parsing") {
    const pct = parseProgress ? Math.round((parseProgress.current / parseProgress.total) * 100) : 0;
    return (
      <section className="space-y-5">
        <p className="text-xs uppercase tracking-widest text-zinc-500">step 03</p>
        <h2 className="text-2xl font-semibold tracking-tight">Review Chapters</h2>
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs text-zinc-500">
            <span className="flex items-center gap-2">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-zinc-400 animate-pulse" />
              {parseProgress ? `Parsing chapter ${parseProgress.current} of ${parseProgress.total}` : "Loading NLP model..."}
            </span>
            {parseProgress && <span className="font-mono">{pct}%</span>}
          </div>
          <div className="h-1 w-full rounded-full bg-zinc-800 overflow-hidden">
            <div className="h-full bg-zinc-300 rounded-full transition-all duration-500" style={{ width: `${pct}%` }} />
          </div>
        </div>
        {parseLog.length > 0 ? (
          <div className="surface-muted rounded p-3 h-36 overflow-y-auto font-mono text-xs text-zinc-500 space-y-0.5">
            {parseLog.map((line, i) => <p key={i} className="leading-snug">{line}</p>)}
            <div ref={logEndRef} />
          </div>
        ) : (
          <p className="text-xs text-zinc-600">Waiting for first progress event...</p>
        )}
      </section>
    );
  }

  if (blocks.length === 0) return <p className="text-sm text-zinc-500">No chapters found.</p>;

  const block = blocks[active];
  const keepCount = blocks.filter((b) => b.keep).length;

  // ── Render: editor ──────────────────────────────────────────────────────────
  return (
    <section className="space-y-6">
      <div className="flex items-baseline justify-between">
        <div>
          <p className="text-xs uppercase tracking-widest text-zinc-500">step 03</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight">Review Chapters</h2>
          <p className="mt-1 text-xs text-zinc-500">{keepCount} of {blocks.length} chapters selected</p>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-4" style={{ minHeight: "70vh" }}>
        {/* ── Chapter list ── */}
        <aside className="col-span-4 surface-muted rounded overflow-auto" style={{ maxHeight: "70vh" }}>
          <ul className="space-y-px text-sm p-2">
            {blocks.map((b, i) => (
              <li key={b.id} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={b.keep}
                  onChange={() => toggleKeep(i)}
                  className="ml-1 h-3.5 w-3.5 rounded border-zinc-700 bg-zinc-950 flex-shrink-0"
                />
                <button
                  className={`flex-1 text-left px-2 py-2 rounded text-xs transition-colors ${
                    i === active
                      ? "bg-zinc-100 text-zinc-950"
                      : b.keep
                      ? "hover:bg-zinc-800 text-zinc-300"
                      : "hover:bg-zinc-800 text-zinc-600 line-through"
                  }`}
                  onClick={() => setActive(i)}
                >
                  <span className="font-mono text-zinc-500 mr-1">{String(i + 1).padStart(2, "0")}</span>
                  {b.title || "(untitled)"}
                </button>
              </li>
            ))}
          </ul>
        </aside>

        {/* ── Detail panel ── */}
        <div className="col-span-8 flex flex-col gap-3">
          {loadingFull ? (
            <p className="text-xs text-zinc-500 animate-pulse">Loading...</p>
          ) : fullBlock ? (
            <>
              {/* Title row */}
              <div className="space-y-1">
                <label className="text-xs uppercase tracking-widest text-zinc-500">Chapter Title</label>
                <input
                  className="input text-sm w-full"
                  value={editTitle}
                  onChange={(e) => { setEditTitle(e.target.value); setDirty(true); }}
                />
              </div>

              {/* Text area */}
              <div className="space-y-1 flex-1">
                <div className="flex items-center justify-between">
                  <label className="text-xs uppercase tracking-widest text-zinc-500">Paragraphs</label>
                  <span className="text-xs text-zinc-600 font-mono">
                    {saving ? "saving..." : dirty ? "unsaved" : "saved"}
                  </span>
                </div>
                <textarea
                  className="input font-mono text-xs leading-relaxed resize-none w-full"
                  rows={22}
                  value={editText}
                  onChange={(e) => { setEditText(e.target.value); setDirty(true); }}
                />
              </div>

              {/* Action bar */}
              <div className="flex items-center gap-4 pt-1">
                <button
                  className="text-xs text-zinc-400 hover:text-zinc-100 disabled:opacity-30 transition-colors"
                  disabled={active === 0}
                  onClick={() => handleMove("up")}
                >
                  ↑ move up
                </button>
                <button
                  className="text-xs text-zinc-400 hover:text-zinc-100 disabled:opacity-30 transition-colors"
                  disabled={active === blocks.length - 1}
                  onClick={() => handleMove("down")}
                >
                  ↓ move down
                </button>
                <button
                  className="text-xs text-red-500 hover:text-red-400 transition-colors ml-2"
                  onClick={handleDelete}
                >
                  delete
                </button>
                <span className="text-xs text-zinc-600 font-mono ml-auto">
                  {fullBlock.sentence_count} sentences
                </span>
              </div>
            </>
          ) : null}
        </div>
      </div>

      {error && <p className="text-xs text-red-400">{error}</p>}

      <div className="flex justify-end">
        <button className="btn-primary" disabled={busy || keepCount === 0} onClick={handleStart}>
          {busy ? "starting..." : "start conversion"}
        </button>
      </div>
    </section>
  );
}
