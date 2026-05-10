import { useEffect, useRef, useState } from "react";
import { Voice, deleteVoice, listVoices, uploadVoice } from "../api";
import { languageLabel } from "../languages";

interface Props {
  selected: string | null;
  language: string;
  onSelect: (voice: Voice | null) => void;
}

// A voice is relevant for the selected language if its `name` (which is the
// path under voices/) starts with `<lang>/` OR lives under `uploaded/` (where
// user uploads land — language-agnostic).
function isVoiceForLanguage(name: string, lang: string): boolean {
  return name.startsWith(`${lang}/`) || name.startsWith("uploaded/");
}

export default function VoiceBrowser({ selected, language, onSelect }: Props) {
  const [voices, setVoices] = useState<Voice[]>([]);
  const [showAll, setShowAll] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // Expand by default when no voice is selected — nudges the user to pick one.
  const [expanded, setExpanded] = useState<boolean>(selected === null);
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
      onSelect(v);
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

  const selectedVoice = voices.find((v) => v.path === selected) || null;
  const summary = selectedVoice?.name ?? "no voice selected";

  const visibleVoices = showAll
    ? voices
    : voices.filter((v) => isVoiceForLanguage(v.name, language));
  const filteredCount = voices.length - visibleVoices.length;

  return (
    <div className="surface-muted p-4 space-y-3">
      <button
        type="button"
        className="w-full flex items-center justify-between gap-3 text-left"
        onClick={() => setExpanded((e) => !e)}
        aria-expanded={expanded}
      >
        <span className="flex items-baseline gap-2 min-w-0">
          <span className="label !mb-0">voice sample</span>
          <span
            className={`text-xs truncate ${selectedVoice ? "text-zinc-200" : "text-zinc-500 italic"}`}
            title={selectedVoice?.path}
          >
            {summary}
          </span>
        </span>
        <span className="flex items-center gap-3 flex-shrink-0">
          <span className="text-[10px] uppercase tracking-widest text-zinc-500">
            {visibleVoices.length} {visibleVoices.length === 1 ? "voice" : "voices"}
            {!showAll && filteredCount > 0 && ` · ${languageLabel(language)}`}
          </span>
          <span className={`text-zinc-500 transition-transform ${expanded ? "rotate-90" : ""}`}>›</span>
        </span>
      </button>

      {expanded && (
        <div className="space-y-3 pt-1">
          <div className="flex justify-end gap-2">
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
            {filteredCount > 0 && (
              <button
                className="btn-ghost text-xs"
                onClick={() => setShowAll((s) => !s)}
                title={showAll ? "Filter to current language + uploads" : "Show every voice regardless of language"}
              >
                {showAll ? `filter · ${language}` : `show all (${filteredCount} more)`}
              </button>
            )}
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

          {error && <p className="text-xs text-red-400">{error}</p>}

          {visibleVoices.length === 0 ? (
            <p className="text-xs text-zinc-500 italic">
              {voices.length === 0
                ? "no voice samples found — upload a 30–60 second clean voice clip."
                : `no voice samples for ${languageLabel(language)} — upload one above, or click "show all" to use a voice from another language.`}
            </p>
          ) : (
            <ul className="space-y-1">
              {visibleVoices.map((v) => {
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
                      onClick={() => onSelect(v)}
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
      )}
    </div>
  );
}
