import { useEffect, useRef, useState } from "react";
import { previewVoice, type ConversionSettings } from "../api";

interface Props {
  settings: ConversionSettings;
}

const PLACEHOLDER =
  "Era una mañana fría cuando el aprendiz cruzó las puertas de piedra por primera vez.";

const MAX_CHARS = 500;

export default function VoicePreview({ settings }: Props) {
  const [text, setText] = useState(PLACEHOLDER);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const prevUrlRef = useRef<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Revoke previous blob URL on unmount or replacement
  useEffect(() => {
    return () => {
      if (prevUrlRef.current) URL.revokeObjectURL(prevUrlRef.current);
    };
  }, []);

  async function generate() {
    if (loading) return;
    setError(null);
    setLoading(true);

    // Revoke previous blob
    if (prevUrlRef.current) {
      URL.revokeObjectURL(prevUrlRef.current);
      prevUrlRef.current = null;
    }
    setAudioUrl(null);

    try {
      const url = await previewVoice({ ...settings, text });
      prevUrlRef.current = url;
      setAudioUrl(url);
      // Auto-play
      setTimeout(() => audioRef.current?.play(), 50);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Preview failed");
    } finally {
      setLoading(false);
    }
  }

  const charsLeft = MAX_CHARS - text.length;
  const overLimit = charsLeft < 0;

  return (
    <div className="surface p-6 space-y-4">
      <p className="text-xs uppercase tracking-widest text-zinc-500">voice preview</p>

      <div className="space-y-2">
        <textarea
          className="input w-full resize-none font-mono text-sm leading-relaxed"
          rows={4}
          maxLength={MAX_CHARS}
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            setAudioUrl(null);
            setError(null);
          }}
          placeholder="Type a sentence to preview…"
        />
        <p className={`text-xs text-right ${overLimit ? "text-red-400" : "text-zinc-600"}`}>
          {charsLeft} chars remaining
        </p>
      </div>

      <div className="flex items-center gap-4">
        <button
          className="btn-primary flex items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
          onClick={generate}
          disabled={loading || overLimit || !text.trim()}
        >
          {loading ? (
            <>
              <Spinner />
              generating…
            </>
          ) : (
            <>
              <PlayIcon />
              generate preview
            </>
          )}
        </button>

        {!settings.voice_path && (
          <p className="text-xs text-zinc-500">no voice selected — using default</p>
        )}
      </div>

      {error && (
        <p className="text-xs text-red-400 font-mono">{error}</p>
      )}

      {audioUrl && (
        <div className="pt-1">
          {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
          <audio
            ref={audioRef}
            controls
            src={audioUrl}
            className="w-full h-8 accent-zinc-300"
            style={{ colorScheme: "dark" }}
          />
        </div>
      )}

      {loading && (
        <p className="text-xs text-zinc-500 animate-pulse">
          Loading TTS model if not yet cached — first run may take a minute…
        </p>
      )}
    </div>
  );
}

function Spinner() {
  return (
    <svg
      className="animate-spin h-3.5 w-3.5"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2.5}
    >
      <circle cx="12" cy="12" r="10" strokeOpacity={0.25} />
      <path d="M12 2a10 10 0 0 1 10 10" />
    </svg>
  );
}

function PlayIcon() {
  return (
    <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="currentColor">
      <path d="M6 3.5l7 4.5-7 4.5V3.5z" />
    </svg>
  );
}
