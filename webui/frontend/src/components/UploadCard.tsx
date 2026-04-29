import { useRef, useState } from "react";
import { uploadEbook, createTestRun } from "../api";

interface Props {
  onUploaded: (sessionId: string, filename: string, isTestRun?: boolean) => void;
}

const ACCEPTED = ".epub,.pdf,.txt,.mobi,.azw3,.fb2,.lit,.html,.rtf,.doc";

export default function UploadCard({ onUploaded }: Props) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  async function handleFile(file: File) {
    setBusy(true);
    setError(null);
    try {
      const res = await uploadEbook(file);
      onUploaded(res.session_id, res.filename);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function handleTestRun() {
    setBusy(true);
    setError(null);
    try {
      const res = await createTestRun();
      onUploaded(res.session_id, res.filename, true);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-widest text-zinc-500">step 01</p>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight">Pick an Ebook</h2>
        <p className="mt-2 text-sm text-zinc-400">
          Supported formats: epub, pdf, mobi, azw3, fb2, lit, html, rtf, doc, txt.
        </p>
      </div>

      <div
        className={`surface p-12 flex flex-col items-center gap-4 text-center transition-colors cursor-pointer ${
          dragging ? "border-zinc-500 bg-zinc-800" : ""
        }`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const f = e.dataTransfer.files[0];
          if (f) handleFile(f);
        }}
        onClick={() => !busy && inputRef.current?.click()}
      >
        <div className="text-4xl text-zinc-700 select-none">↑</div>
        <p className="text-sm text-zinc-500">
          drag and drop a file here, or
        </p>
        <button
          className="btn-primary"
          disabled={busy}
          onClick={(e) => { e.stopPropagation(); inputRef.current?.click(); }}
        >
          {busy ? "uploading…" : "choose file"}
        </button>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED}
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) handleFile(f);
        }}
      />

      <div className="flex items-center gap-3">
        <div className="flex-1 border-t border-zinc-800" />
        <span className="text-xs text-zinc-600 uppercase tracking-widest">or</span>
        <div className="flex-1 border-t border-zinc-800" />
      </div>

      <div className="surface p-5 flex items-center justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-zinc-200">Test Run</p>
          <p className="text-xs text-zinc-500 mt-0.5">
            Use the built-in sample to compare engines and settings.
          </p>
        </div>
        <button
          className="btn-primary flex-shrink-0 disabled:opacity-40 disabled:cursor-not-allowed"
          disabled={busy}
          onClick={handleTestRun}
        >
          {busy ? "loading…" : "try sample"}
        </button>
      </div>

      {error && <p className="text-xs text-red-400">{error}</p>}
    </section>
  );
}
