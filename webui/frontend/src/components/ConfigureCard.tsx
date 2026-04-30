import { useEffect, useState } from "react";
import { ConversionSettings } from "../api";
import VoiceBrowser from "./VoiceBrowser";
import VoicePreview from "./VoicePreview";

interface EngineOption {
  key: string;
  label: string;
}

interface Props {
  sessionId: string;
  filename: string | null;
  isTestRun?: boolean;
  onNext: (settings: ConversionSettings) => void;
}

const DEFAULTS: ConversionSettings = {
  language: "spa",
  voice_path: null,
  tts_engine: "xtts",
  device: "cuda",
  output_format: "m4b",
  xtts_speed: 1.0,
  xtts_temperature: 0.85,
  fishspeech_temperature: 0.8,
  fishspeech_top_p: 0.8,
  fishspeech_repetition_penalty: 1.1,
  fishspeech_max_new_tokens: 1024,
  cosyvoice_speed: 1.0,
  cosyvoice_instruct_text: "",
  qwen3tts_ref_text: "",
};

function loadSettings(): ConversionSettings {
  try {
    const raw = localStorage.getItem("ebook2audiobook:settings");
    if (raw) return { ...DEFAULTS, ...JSON.parse(raw) };
  } catch { /* ignore */ }
  return DEFAULTS;
}

function saveSettings(s: ConversionSettings) {
  localStorage.setItem("ebook2audiobook:settings", JSON.stringify(s));
}

export default function ConfigureCard({ sessionId, filename, isTestRun, onNext }: Props) {
  const [settings, setSettings] = useState<ConversionSettings>(loadSettings());
  const [engines, setEngines] = useState<EngineOption[]>([]);

  // Fetch the engine list filtered by the install profile (.engine-mode marker).
  useEffect(() => {
    fetch("/api/engines")
      .then((r) => r.json())
      .then((data: { mode: string; engines: EngineOption[] }) => {
        setEngines(data.engines);
        // If the previously-saved engine isn't supported by the active install,
        // fall back to the first one so the dropdown isn't blank.
        if (data.engines.length && !data.engines.find((e) => e.key === settings.tts_engine)) {
          setSettings((s) => ({ ...s, tts_engine: data.engines[0].key }));
        }
      })
      .catch(() => {
        /* leave engines = [] — UI shows an empty dropdown */
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function set<K extends keyof ConversionSettings>(key: K, value: ConversionSettings[K]) {
    setSettings((s) => ({ ...s, [key]: value }));
  }

  function handleNext() {
    saveSettings(settings);
    onNext(settings);
  }

  return (
    <section className="space-y-6">
      <div>
        <div className="flex items-center gap-3">
          <p className="text-xs uppercase tracking-widest text-zinc-500">step 02</p>
          {isTestRun && (
            <span className="text-xs uppercase tracking-widest text-amber-500 border border-amber-700 rounded px-1.5 py-0.5">
              test run
            </span>
          )}
        </div>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight">Configure Conversion</h2>
        {filename && (
          <p className="mt-1 text-sm text-zinc-400 font-mono">{filename}</p>
        )}
        <p className="mt-1 text-xs text-zinc-600 font-mono">session {sessionId}</p>
        {isTestRun && (
          <p className="mt-2 text-xs text-zinc-500">
            Using the built-in sample — chapters editor will be skipped and conversion starts immediately.
          </p>
        )}
      </div>

      <VoiceBrowser
        selected={settings.voice_path}
        onSelect={(p) => set("voice_path", p)}
      />

      <VoicePreview settings={settings} />

      <div className="surface p-6 space-y-4">
        <p className="text-xs uppercase tracking-widest text-zinc-500 mb-2">settings</p>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">language</label>
            <input
              className="input"
              value={settings.language}
              onChange={(e) => set("language", e.target.value)}
              placeholder="spa, eng, fra…"
            />
          </div>

          <div>
            <label className="label">tts engine</label>
            <select
              className="input"
              value={settings.tts_engine}
              onChange={(e) => set("tts_engine", e.target.value)}
            >
              {engines.map((e) => (
                <option key={e.key} value={e.key}>{e.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="label">device</label>
            <select
              className="input"
              value={settings.device}
              onChange={(e) => set("device", e.target.value)}
            >
              <option value="cuda">CUDA (GPU)</option>
              <option value="cpu">CPU</option>
            </select>
          </div>

          <div>
            <label className="label">output format</label>
            <select
              className="input"
              value={settings.output_format}
              onChange={(e) => set("output_format", e.target.value)}
            >
              <option value="m4b">m4b</option>
              <option value="mp3">mp3</option>
              <option value="opus">opus</option>
            </select>
          </div>

          {settings.tts_engine === "xtts" && (
            <>
              <div>
                <label className="label">speed</label>
                <input
                  className="input"
                  type="number"
                  min={0.5}
                  max={2.0}
                  step={0.1}
                  value={settings.xtts_speed}
                  onChange={(e) => set("xtts_speed", Number(e.target.value))}
                />
              </div>
              <div>
                <label className="label">temperature</label>
                <input
                  className="input"
                  type="number"
                  min={0.1}
                  max={1.0}
                  step={0.05}
                  value={settings.xtts_temperature}
                  onChange={(e) => set("xtts_temperature", Number(e.target.value))}
                />
              </div>
            </>
          )}

          {settings.tts_engine === "fishspeech" && (
            <>
              <div>
                <label className="label">temperature</label>
                <input
                  className="input"
                  type="number"
                  min={0.1}
                  max={1.0}
                  step={0.05}
                  value={settings.fishspeech_temperature}
                  onChange={(e) => set("fishspeech_temperature", Number(e.target.value))}
                />
              </div>
              <div>
                <label className="label">top p</label>
                <input
                  className="input"
                  type="number"
                  min={0.1}
                  max={1.0}
                  step={0.05}
                  value={settings.fishspeech_top_p}
                  onChange={(e) => set("fishspeech_top_p", Number(e.target.value))}
                />
              </div>
              <div>
                <label className="label">repetition penalty</label>
                <input
                  className="input"
                  type="number"
                  min={1.0}
                  max={2.0}
                  step={0.05}
                  value={settings.fishspeech_repetition_penalty}
                  onChange={(e) => set("fishspeech_repetition_penalty", Number(e.target.value))}
                />
              </div>
              <div>
                <label className="label">max new tokens</label>
                <input
                  className="input"
                  type="number"
                  min={256}
                  max={4096}
                  step={256}
                  value={settings.fishspeech_max_new_tokens}
                  onChange={(e) => set("fishspeech_max_new_tokens", Number(e.target.value))}
                />
              </div>
            </>
          )}

          {settings.tts_engine === "cosyvoice" && (
            <>
              <div>
                <label className="label">speed</label>
                <input
                  className="input"
                  type="number"
                  min={0.5}
                  max={2.0}
                  step={0.1}
                  value={settings.cosyvoice_speed}
                  onChange={(e) => set("cosyvoice_speed", Number(e.target.value))}
                />
              </div>
              <div className="col-span-2">
                <label className="label">instruct text (optional)</label>
                <input
                  className="input"
                  type="text"
                  placeholder="e.g. 请用广东话表达。 — leave empty for zero-shot cloning"
                  value={settings.cosyvoice_instruct_text}
                  onChange={(e) => set("cosyvoice_instruct_text", e.target.value)}
                />
              </div>
            </>
          )}

          {settings.tts_engine === "qwen3tts" && (
            <div className="col-span-2">
              <label className="label">
                voice transcript <span className="text-zinc-500">(optional)</span>
              </label>
              <textarea
                className="input min-h-[80px]"
                value={settings.qwen3tts_ref_text}
                onChange={(e) => set("qwen3tts_ref_text", e.target.value)}
                placeholder="Transcript of the reference voice WAV. Leave blank to auto-transcribe with whisper on first use (cached as <voice>.transcript.txt next to the WAV)."
              />
              <p className="mt-1 text-xs text-zinc-500">
                Providing a transcript switches Qwen3-TTS to full-fidelity cloning mode (better timbre + accent). Empty = auto-transcribe with whisper.
              </p>
            </div>
          )}
        </div>
      </div>

      <div className="flex justify-end">
        <button className="btn-primary" onClick={handleNext}>
          {isTestRun ? "start test run" : "next: review chapters"}
        </button>
      </div>
    </section>
  );
}
