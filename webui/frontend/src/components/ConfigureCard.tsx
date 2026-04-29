import { useState } from "react";
import { ConversionSettings } from "../api";
import VoiceBrowser from "./VoiceBrowser";
import VoicePreview from "./VoicePreview";

interface Props {
  sessionId: string;
  filename: string | null;
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

export default function ConfigureCard({ sessionId, filename, onNext }: Props) {
  const [settings, setSettings] = useState<ConversionSettings>(loadSettings());

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
        <p className="text-xs uppercase tracking-widest text-zinc-500">step 02</p>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight">Configure Conversion</h2>
        {filename && (
          <p className="mt-1 text-sm text-zinc-400 font-mono">{filename}</p>
        )}
        <p className="mt-1 text-xs text-zinc-600 font-mono">session {sessionId}</p>
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
              <option value="xtts">XTTSv2</option>
              <option value="bark">Bark</option>
              <option value="vits">VITS</option>
              <option value="yourtts">YourTTS</option>
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
        </div>
      </div>

      <div className="flex justify-end">
        <button className="btn-primary" onClick={handleNext}>
          next: review chapters
        </button>
      </div>
    </section>
  );
}
