import { useEffect, useState } from "react";
import UploadCard from "./components/UploadCard";
import ConfigureCard from "./components/ConfigureCard";
import ChaptersEditor from "./components/ChaptersEditor";
import ConversionProgress from "./components/ConversionProgress";
import Library from "./components/Library";
import StatusBar from "./components/StatusBar";
import { ConversionSettings, getSession, listSessions, startConversion } from "./api";
import { DEFAULT_SETTINGS } from "./settings";

type Stage = "upload" | "configure" | "chapters" | "running" | "library";

const LS_SESSION = "ebook2audiobook:session_id";
const LS_STAGE = "ebook2audiobook:stage";
const LS_FILENAME = "ebook2audiobook:filename";
const LS_LANGUAGE = "ebook2audiobook:language";

export default function App() {
  const [stage, setStage] = useState<Stage>("upload");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [filename, setFilename] = useState<string | null>(null);
  const [isTestRun, setIsTestRun] = useState(false);
  const [language, setLanguageState] = useState<string>(() => {
    return localStorage.getItem(LS_LANGUAGE) || "spa";
  });
  const [resumable, setResumable] = useState<{ id: string; name: string; status: string } | null>(null);

  function setLanguage(code: string) {
    setLanguageState(code);
    localStorage.setItem(LS_LANGUAGE, code);
  }

  useEffect(() => {
    const savedId = localStorage.getItem(LS_SESSION);
    const savedStage = localStorage.getItem(LS_STAGE) as Stage | null;
    const savedFilename = localStorage.getItem(LS_FILENAME);

    if (!savedId || !savedStage || savedStage === "upload") return;

    getSession(savedId)
      .then((s) => {
        // Stopped/cancelled is resumable too — backend's auto_resume='y' picks
        // up from the last persisted block_resume/sentence_resume in
        // blocks_current.json.  Only `error` is a dead end.
        if (s.status && s.status !== "error") {
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

  function resumeSession(id: string, name: string, status: string) {
    setSessionId(id);
    setFilename(name);
    if (status === "done") {
      setStage("library");
      persistSession(id, "library", name);
      setResumable(null);
      return;
    }
    // Resume directly into running — chapters were already reviewed when /start
    // was first clicked. Re-issue /start with saved settings; backend's
    // auto_resume='y' continues the existing conversion in place.
    const raw = localStorage.getItem("ebook2audiobook:settings");
    const settings: ConversionSettings = raw
      ? { ...DEFAULT_SETTINGS, ...JSON.parse(raw) }
      : { ...DEFAULT_SETTINGS, language };
    startConversion(id, settings).catch(() => undefined);
    setStage("running");
    persistSession(id, "running", name);
    setResumable(null);
  }

  function resume() {
    if (!resumable) return;
    resumeSession(resumable.id, resumable.name, resumable.status);
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
              language={language}
              onLanguageChange={setLanguage}
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
              language={language}
              onLanguageChange={setLanguage}
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
              onResume={() => resumeSession(sessionId, filename || "unknown", "cancelled")}
            />
          )}
          {stage === "library" && <Library onResume={resumeSession} />}
        </div>
      </main>

      <footer className="border-t border-zinc-900">
        <div className="max-w-3xl mx-auto px-6 py-4 text-xs text-zinc-500 flex justify-between items-center">
          <StatusBar />
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
