import { useEffect, useState } from "react";
import { ConversionSettings, Voice, fetchVoiceTranscript, listVoices, transcribeVoice } from "../api";
import { LANGUAGES, languageLabel } from "../languages";
import { loadSettings, saveSettings } from "../settings";
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
  language: string;
  onLanguageChange: (code: string) => void;
  onNext: (settings: ConversionSettings) => void;
}

export default function ConfigureCard({ sessionId, filename, isTestRun, language, onLanguageChange, onNext }: Props) {
  const [settings, setSettings] = useState<ConversionSettings>(() => ({
    ...loadSettings(),
    language,
  }));
  const [engines, setEngines] = useState<EngineOption[]>([]);
  const [selectedVoice, setSelectedVoice] = useState<Voice | null>(null);
  const [transcribing, setTranscribing] = useState(false);
  const [transcribeError, setTranscribeError] = useState<string | null>(null);

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

  // When the selected voice or engine changes, load the cached transcript sidecar
  // (<voice>.transcript.txt) into the qwen3tts_ref_text field.
  useEffect(() => {
    if (!selectedVoice || settings.tts_engine !== "qwen3tts") return;
    fetchVoiceTranscript(selectedVoice.name).then((t) => {
      setSettings((s) => ({ ...s, qwen3tts_ref_text: t }));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedVoice, settings.tts_engine]);

  // Same sidecar lookup for F5-TTS (which also requires ref_text).
  useEffect(() => {
    if (!selectedVoice || settings.tts_engine !== "f5tts") return;
    fetchVoiceTranscript(selectedVoice.name).then((t) => {
      setSettings((s) => ({ ...s, f5tts_ref_text: t }));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedVoice, settings.tts_engine]);

  // Resolve a localStorage-restored voice_path into the full Voice object so
  // the "selected voice" card and transcript loader work after a page reload.
  useEffect(() => {
    if (!settings.voice_path || selectedVoice) return;
    listVoices().then((voices) => {
      const match = voices.find((v) => v.path === settings.voice_path);
      if (match) setSelectedVoice(match);
    }).catch(() => { /* ignore */ });
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
        language={language}
        onSelect={(v: Voice | null) => {
          set("voice_path", v?.path ?? null);
          setSelectedVoice(v);
        }}
      />

      <VoicePreview settings={settings} />

      <div className="surface p-6 space-y-4">
        <p className="text-xs uppercase tracking-widest text-zinc-500 mb-2">settings</p>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">language</label>
            <select
              className="input"
              value={settings.language}
              onChange={(e) => {
                set("language", e.target.value);
                onLanguageChange(e.target.value);
              }}
            >
              {LANGUAGES.map((l) => (
                <option key={l.code} value={l.code}>
                  {languageLabel(l.code)}
                </option>
              ))}
            </select>
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
                onChange={(e) => {
                  set("qwen3tts_ref_text", e.target.value);
                  setTranscribeError(null);
                }}
                placeholder="Transcript of the reference voice WAV. Leave blank to auto-transcribe with whisper on first use (cached as <voice>.transcript.txt next to the WAV)."
              />
              <div className="mt-2 flex items-center gap-3">
                <button
                  className="btn-ghost flex items-center gap-1.5 text-xs disabled:opacity-40 disabled:cursor-not-allowed"
                  disabled={transcribing || !selectedVoice}
                  onClick={async () => {
                    if (!selectedVoice) return;
                    setTranscribing(true);
                    setTranscribeError(null);
                    try {
                      const t = await transcribeVoice(selectedVoice.name);
                      set("qwen3tts_ref_text", t);
                    } catch (e: unknown) {
                      setTranscribeError(e instanceof Error ? e.message : "Transcription failed");
                    } finally {
                      setTranscribing(false);
                    }
                  }}
                >
                  {transcribing ? (
                    <>
                      <TranscribeSpinner />
                      transcribing…
                    </>
                  ) : (
                    <>
                      <MicIcon />
                      transcribe voice
                    </>
                  )}
                </button>
                {!selectedVoice && (
                  <span className="text-xs text-zinc-500">select a voice first</span>
                )}
                {transcribeError && (
                  <span className="text-xs text-red-400 font-mono">{transcribeError}</span>
                )}
              </div>
              <p className="mt-1 text-xs text-zinc-500">
                Providing a transcript switches Qwen3-TTS to full-fidelity cloning mode (better timbre + accent). Empty = auto-transcribe with whisper.
              </p>

              <div className="mt-3 surface-muted rounded p-3">
                <p className="text-[10px] uppercase tracking-widest text-zinc-500 mb-2">selected voice</p>
                {selectedVoice ? (
                  <div className="flex items-center gap-3">
                    <span
                      className="text-xs text-zinc-200 truncate flex-1"
                      title={selectedVoice.path}
                    >
                      {selectedVoice.name}
                    </span>
                    <audio src={selectedVoice.url} controls preload="none" className="h-7 max-w-[220px]" />
                  </div>
                ) : (
                  <p className="text-xs text-amber-400">
                    No voice selected. Qwen3-TTS requires a reference WAV — pick or upload one above.
                  </p>
                )}
              </div>

              <div className="mt-3 grid grid-cols-3 gap-3">
                <div>
                  <label className="label">narration speed</label>
                  <input
                    className="input"
                    type="number"
                    min={0.5}
                    max={2.0}
                    step={0.05}
                    value={settings.qwen3tts_speed}
                    onChange={(e) => set("qwen3tts_speed", Number(e.target.value))}
                  />
                </div>
                <div>
                  <label className="label">silence min (s)</label>
                  <input
                    className="input"
                    type="number"
                    min={0}
                    max={5}
                    step={0.05}
                    value={settings.qwen3tts_silence_min}
                    onChange={(e) => set("qwen3tts_silence_min", Number(e.target.value))}
                  />
                </div>
                <div>
                  <label className="label">silence max (s)</label>
                  <input
                    className="input"
                    type="number"
                    min={0}
                    max={5}
                    step={0.05}
                    value={settings.qwen3tts_silence_max}
                    onChange={(e) => set("qwen3tts_silence_max", Number(e.target.value))}
                  />
                </div>
                <p className="col-span-3 text-xs text-zinc-500">
                  Speed &lt; 1.0 slows narration with pitch preserved (phase-vocoder time-stretch). Silence min/max set the random gap inserted after each punctuation-terminated sentence-part. Use <code>[pause:N]</code> in the source text for an exact N-second break at a specific spot.
                </p>
              </div>

              <details className="mt-3">
                <summary className="cursor-pointer text-[10px] uppercase tracking-widest text-zinc-500 select-none">
                  advanced sampling
                </summary>
                <div className="mt-2 grid grid-cols-2 gap-3 surface-muted rounded p-3">
                  <div>
                    <label className="label">temperature</label>
                    <input
                      className="input"
                      type="number"
                      min={0.1}
                      max={1.5}
                      step={0.05}
                      value={settings.qwen3tts_temperature}
                      onChange={(e) => set("qwen3tts_temperature", Number(e.target.value))}
                    />
                  </div>
                  <div>
                    <label className="label">top_p</label>
                    <input
                      className="input"
                      type="number"
                      min={0.1}
                      max={1.0}
                      step={0.05}
                      value={settings.qwen3tts_top_p}
                      onChange={(e) => set("qwen3tts_top_p", Number(e.target.value))}
                    />
                  </div>
                  <div>
                    <label className="label">top_k</label>
                    <input
                      className="input"
                      type="number"
                      min={1}
                      max={500}
                      step={1}
                      value={settings.qwen3tts_top_k}
                      onChange={(e) => set("qwen3tts_top_k", Number(e.target.value))}
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
                      value={settings.qwen3tts_repetition_penalty}
                      onChange={(e) => set("qwen3tts_repetition_penalty", Number(e.target.value))}
                    />
                  </div>
                  <div>
                    <label className="label">subtalker temperature</label>
                    <input
                      className="input"
                      type="number"
                      min={0.1}
                      max={1.5}
                      step={0.05}
                      value={settings.qwen3tts_subtalker_temperature}
                      onChange={(e) => set("qwen3tts_subtalker_temperature", Number(e.target.value))}
                    />
                  </div>
                  <div>
                    <label className="label">subtalker top_p</label>
                    <input
                      className="input"
                      type="number"
                      min={0.1}
                      max={1.0}
                      step={0.05}
                      value={settings.qwen3tts_subtalker_top_p}
                      onChange={(e) => set("qwen3tts_subtalker_top_p", Number(e.target.value))}
                    />
                  </div>
                  <div>
                    <label className="label">subtalker top_k</label>
                    <input
                      className="input"
                      type="number"
                      min={1}
                      max={500}
                      step={1}
                      value={settings.qwen3tts_subtalker_top_k}
                      onChange={(e) => set("qwen3tts_subtalker_top_k", Number(e.target.value))}
                    />
                  </div>
                  <div>
                    <label className="label">seed</label>
                    <input
                      className="input"
                      type="number"
                      min={0}
                      step={1}
                      value={settings.qwen3tts_seed}
                      onChange={(e) => set("qwen3tts_seed", Number(e.target.value))}
                    />
                  </div>
                  <p className="col-span-2 text-xs text-zinc-500">
                    Lower temperature → tighter timbre across sentences; higher → more expressive.
                    Defaults (0.7 / 0.9 / 1.1 / 0.7) are tuned for narration.
                    Settings auto-save to your browser and apply on next conversion.
                  </p>
                </div>
              </details>
            </div>
          )}

          {settings.tts_engine === "f5tts" && (
            <div className="col-span-2 space-y-4">
              <div>
                <label className="label">speed</label>
                <input
                  className="input"
                  type="number"
                  min={0.3}
                  max={2.0}
                  step={0.05}
                  value={settings.f5tts_speed}
                  onChange={(e) => set("f5tts_speed", Number(e.target.value))}
                />
                <p className="mt-1 text-xs text-zinc-500">
                  0.85 = steady narration, 1.0 = upstream default (rushed for audiobooks).
                </p>
              </div>

              <label className="label">
                voice transcript <span className="text-zinc-500">(required)</span>
              </label>
              <textarea
                className="input min-h-[80px]"
                value={settings.f5tts_ref_text}
                onChange={(e) => {
                  set("f5tts_ref_text", e.target.value);
                  setTranscribeError(null);
                }}
                placeholder="Transcript of the reference voice WAV. Leave blank to auto-transcribe with whisper on first use (cached as <voice>.transcript.txt next to the WAV)."
              />
              <div className="mt-2 flex items-center gap-3">
                <button
                  className="btn-ghost flex items-center gap-1.5 text-xs disabled:opacity-40 disabled:cursor-not-allowed"
                  disabled={transcribing || !selectedVoice}
                  onClick={async () => {
                    if (!selectedVoice) return;
                    setTranscribing(true);
                    setTranscribeError(null);
                    try {
                      const t = await transcribeVoice(selectedVoice.name);
                      set("f5tts_ref_text", t);
                    } catch (e: unknown) {
                      setTranscribeError(e instanceof Error ? e.message : "Transcription failed");
                    } finally {
                      setTranscribing(false);
                    }
                  }}
                >
                  {transcribing ? (
                    <>
                      <TranscribeSpinner />
                      transcribing…
                    </>
                  ) : (
                    <>
                      <MicIcon />
                      transcribe voice
                    </>
                  )}
                </button>
                {!selectedVoice && (
                  <span className="text-xs text-zinc-500">select a voice first</span>
                )}
                {transcribeError && (
                  <span className="text-xs text-red-400 font-mono">{transcribeError}</span>
                )}
              </div>
              <p className="mt-1 text-xs text-zinc-500">
                F5-TTS requires a transcript of the reference WAV. Native languages: English + Chinese. Empty = auto-transcribe with whisper on first run.
              </p>

              <div className="mt-3 surface-muted rounded p-3">
                <p className="text-[10px] uppercase tracking-widest text-zinc-500 mb-2">selected voice</p>
                {selectedVoice ? (
                  <div className="flex items-center gap-3">
                    <span
                      className="text-xs text-zinc-200 truncate flex-1"
                      title={selectedVoice.path}
                    >
                      {selectedVoice.name}
                    </span>
                    <audio src={selectedVoice.url} controls preload="none" className="h-7 max-w-[220px]" />
                  </div>
                ) : (
                  <p className="text-xs text-amber-400">
                    No voice selected. F5-TTS requires a reference WAV — pick or upload one above.
                  </p>
                )}
              </div>

              <details className="mt-3">
                <summary className="cursor-pointer text-[10px] uppercase tracking-widest text-zinc-500 select-none">
                  advanced sampling
                </summary>
                <div className="mt-2 grid grid-cols-2 gap-3 surface-muted rounded p-3">
                  <div>
                    <label className="label">nfe step</label>
                    <input
                      className="input"
                      type="number"
                      min={4}
                      max={64}
                      step={1}
                      value={settings.f5tts_nfe_step}
                      onChange={(e) => set("f5tts_nfe_step", Number(e.target.value))}
                    />
                  </div>
                  <div>
                    <label className="label">cfg strength</label>
                    <input
                      className="input"
                      type="number"
                      min={0.5}
                      max={5.0}
                      step={0.1}
                      value={settings.f5tts_cfg_strength}
                      onChange={(e) => set("f5tts_cfg_strength", Number(e.target.value))}
                    />
                  </div>
                  <p className="col-span-2 text-xs text-zinc-500">
                    nfe_step 32 = best WER (paper); 16 = ~2× faster, minor quality loss. cfg_strength 2.0 is the upstream default — higher over-emphasises the reference and can sound metallic.
                  </p>
                </div>
              </details>
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

function TranscribeSpinner() {
  return (
    <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
      <circle cx="12" cy="12" r="10" strokeOpacity={0.25} />
      <path d="M12 2a10 10 0 0 1 10 10" />
    </svg>
  );
}

function MicIcon() {
  return (
    <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <rect x="9" y="2" width="6" height="12" rx="3" />
      <path d="M5 10a7 7 0 0 0 14 0" />
      <line x1="12" y1="19" x2="12" y2="22" />
      <line x1="9" y1="22" x2="15" y2="22" />
    </svg>
  );
}
