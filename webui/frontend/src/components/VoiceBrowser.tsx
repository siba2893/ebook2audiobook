import { useEffect, useRef, useState } from "react";
import { Voice, deleteVoice, listVoices, uploadVoice } from "../api";

interface Props {
  selected: string | null;
  onSelect: (path: string | null) => void;
}

export default function VoiceBrowser({ selected, onSelect }: Props) {
  const [voices, setVoices] = useState<Voice[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  function refresh() {
    listVoices()
      .then(setVoices)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }
  useEffect(refresh, []);

  async function handleUpload(file: File) {
    setBusy(true);
    setError(null);
    try {
      const v = await uploadVoice(file);
      onSelect(v.path);
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(v: Voice) {
    if (!window.confirm(`Delete "${v.name}"?`)) return;
    try {
      await deleteVoice(v.name);
      if (selected === v.path) onSelect(null);
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="surface-muted p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="label !mb-0">voice sample</span>
        <div className="flex gap-2">
          <input
            ref={inputRef}
            type="file"
            accept=".wav,.mp3,.flac"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleUpload(f);
            }}
          />
          <button
            className="btn-ghost text-xs"
            disabled={busy}
            onClick={() => inputRef.current?.click()}
          >
            {busy ? "uploading…" : "+ upload"}
          </button>
          <button
            className="btn-ghost text-xs"
            disabled={selected === null}
            onClick={() => onSelect(null)}
          >
            clear
          </button>
        </div>
      </div>

      {error && <p className="text-xs text-red-400">{error}</p>}

      {voices.length === 0 ? (
        <p className="text-xs text-zinc-500 italic">
          no voice samples found — upload a 30–60 second clean voice clip.
        </p>
      ) : (
        <ul className="space-y-1">
          {voices.map((v) => {
            const active = selected === v.path;
            return (
              <li
                key={v.name}
                className={`flex items-center gap-3 px-2 py-1.5 rounded transition-colors border ${
                  active
                    ? "bg-zinc-100 text-zinc-950 border-zinc-400"
                    : "hover:bg-zinc-800 border-transparent"
                }`}
              >
                <span className="w-4 text-sm flex-shrink-0 text-zinc-400">
                  {active ? "✓" : ""}
                </span>
                <button
                  className={`text-left text-xs flex-1 truncate ${active ? "text-zinc-950" : "text-zinc-200"}`}
                  onClick={() => onSelect(v.path)}
                  title={v.path}
                >
                  {v.name}
                </button>
                <audio src={v.url} controls preload="none" className="h-6 max-w-[180px]" />
                <button
                  className="text-[10px] uppercase tracking-wider px-2 py-1 rounded text-zinc-500 hover:text-red-400 transition-colors"
                  onClick={() => handleDelete(v)}
                >
                  remove
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
