import { ConversionSettings } from "./api";

// Defaults match the per-engine narration-tuned values in
// lib/classes/tts_engines/<engine>.py.  Exported so App.tsx's resume
// fallback can reuse the same constants (otherwise the two literals drift).
export const DEFAULT_SETTINGS: ConversionSettings = {
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
  qwen3tts_temperature: 0.7,
  qwen3tts_top_p: 0.9,
  qwen3tts_top_k: 50,
  qwen3tts_repetition_penalty: 1.1,
  qwen3tts_subtalker_temperature: 0.7,
  qwen3tts_subtalker_top_p: 0.9,
  qwen3tts_subtalker_top_k: 50,
  qwen3tts_seed: 0,
  qwen3tts_silence_min: 0.3,
  qwen3tts_silence_max: 0.6,
  f5tts_ref_text: "",
  f5tts_speed: 0.85,
  f5tts_nfe_step: 32,
  f5tts_cfg_strength: 2.0,
};

const STORAGE_KEY = "ebook2audiobook:settings";

export function loadSettings(): ConversionSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
  } catch { /* ignore */ }
  return DEFAULT_SETTINGS;
}

export function saveSettings(s: ConversionSettings): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
}
