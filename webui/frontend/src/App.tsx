import { useEffect, useState } from "react";
import UploadCard from "./components/UploadCard";
import ConfigureCard from "./components/ConfigureCard";
import ChaptersEditor from "./components/ChaptersEditor";
import ConversionProgress from "./components/ConversionProgress";
import Library from "./components/Library";
import { getSession, listSessions } from "./api";

type Stage = "upload" | "configure" | "chapters" | "running" | "library";

const LS_SESSION = "ebook2audiobook:session_id";
const LS_STAGE = "ebook2audiobook:stage";
const LS_FILENAME = "ebook2audiobook:filename";

export default function App() {
  const [stage, setStage] = useState<Stage>("upload");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [filename, setFilename] = useState<string | null>(null);
  const [isTestRun, setIsTestRun] = useState(false);
  const [resumable, setResumable] = useState<{ id: string; name: string; status: string } | null>(null);

  // On first load, check for a resumable session
  useEffect(() => {
    const savedId = localStorage.getItem(LS_SESSION);
    const savedStage = localStorage.getItem(LS_STAGE) as Stage | null;
    const savedFilename = localStorage.getItem(LS_FILENAME);

    if (!savedId || !savedStage || savedStage === "upload") return;

    getSession(savedId)
      .then((s) => {
        if (s.status && s.status !== "error" && s.status !== "cancelled") {
          setResumable({
            id: savedId,
            name: savedFilename || s.filename || "unknown",
            status: s.status,
          });
        }
      })
      .catch(() => {
        // Session gone — clear stale localStorage
        localStorage.removeItem(LS_SESSION);
        localStorage.removeItem(LS_STAGE);
        localStorage.removeItem(LS_FILENAME);
      });
  }, []);

  function persistSession(sid: string, s: Stage, fname: string | null) {
    localStorage.setItem(LS_SESSION, sid);
    localStorage.setItem(LS_STAGE, s);
    if (fname) localStorage.setItem(LS_FILENAME, fname);
  }

  function advanceTo(s: Stage) {
    setStage(s);
    if (sessionId) persistSession(sessionId, s, filename);
  }

  function resume() {
    if (!resumable) return;
    setSessionId(resumable.id);
    setFilename(resumable.name);
    const s = resumable.status;
    if (s === "done") setStage("library");
    else if (s === "converting") setStage("running");
    else if (s === "edit") setStage("chapters");
    else setStage("configure");
    setResumable(null);
  }

  function reset() {
    setStage("upload");
    setSessionId(null);
    setFilename(null);
    setIsTestRun(false);
    setResumable(null);
    localStorage.removeItem(LS_SESSION);
    localStorage.removeItem(LS_STAGE);
    localStorage.removeItem(LS_FILENAME);
  }

  return (
    <div className="min-h-full flex flex-col bg-zinc-950">
      <header className="border-b border-zinc-900">
        <div className="max-w-3xl mx-auto px-6 py-5 flex items-baseline justify-between">
          <button
            className="text-lg font-semibold tracking-tight hover:text-white"
            onClick={reset}
          >
            ebook2audiobook
          </button>
          <nav className="flex gap-5 text-xs uppercase tracking-widest">
            <button
              className={stage !== "library" ? "text-zinc-200" : "text-zinc-500 hover:text-zinc-300"}
              onClick={reset}
            >
              convert
            </button>
            <button
              className={stage === "library" ? "text-zinc-200" : "text-zinc-500 hover:text-zinc-300"}
              onClick={() => setStage("library")}
            >
              library
            </button>
          </nav>
        </div>
      </header>

      <main className="flex-1">
        <div className="max-w-3xl mx-auto px-6 py-10 space-y-8">

          {/* Resume banner */}
          {resumable && stage === "upload" && (
            <div className="border border-zinc-700 rounded p-4 flex items-center justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-widest text-zinc-500 mb-1">Resume previous session</p>
                <p className="text-sm text-zinc-200 font-medium truncate max-w-sm">{resumable.name}</p>
                <p className="text-xs text-zinc-500 mt-0.5">Status: {resumable.status}</p>
              </div>
              <div className="flex gap-3 flex-shrink-0">
                <button className="btn-primary text-xs" onClick={resume}>Resume</button>
                <button className="text-xs text-zinc-500 hover:text-zinc-300" onClick={() => setResumable(null)}>Dismiss</button>
              </div>
            </div>
          )}

          {stage === "upload" && (
            <UploadCard
              onUploaded={(sid, fname, testRun) => {
                setSessionId(sid);
                setFilename(fname);
                setIsTestRun(!!testRun);
                persistSession(sid, "configure", fname);
                setStage("configure");
              }}
            />
          )}
          {stage === "configure" && sessionId && (
            <ConfigureCard
              sessionId={sessionId}
              filename={filename}
              isTestRun={isTestRun}
              onNext={() => {
                if (isTestRun) {
                  advanceTo("running");
                } else {
                  advanceTo("chapters");
                }
              }}
            />
          )}
          {stage === "chapters" && sessionId && (
            <ChaptersEditor
              sessionId={sessionId}
              onStarted={() => advanceTo("running")}
            />
          )}
          {stage === "running" && sessionId && (
            <ConversionProgress
              sessionId={sessionId}
              onDone={() => advanceTo("library")}
            />
          )}
          {stage === "library" && <Library />}
        </div>
      </main>

      <footer className="border-t border-zinc-900">
        <div className="max-w-3xl mx-auto px-6 py-4 text-xs text-zinc-500 flex justify-between">
          <span>monochromatic ui</span>
          <a
            href="https://github.com/siba2893/ebook2audiobook"
            target="_blank"
            rel="noreferrer"
            className="hover:text-zinc-300"
          >
            github
          </a>
        </div>
      </footer>
    </div>
  );
}
