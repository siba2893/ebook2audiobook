// Curated language list for the upload-step picker.  Codes are ISO 639-3
// (matching `voices/<code>/...` directory layout and what each engine's
// `languages` dict in lib/conf_models.py keys on).  This is the union of
// commonly-supported languages across the available engines, with display
// names. The 8 languages that currently have voice samples bundled are
// flagged via `hasBundledVoices` so the UI can surface that.
export interface LanguageOption {
  code: string;       // ISO 639-3
  name: string;       // English display name
  native?: string;    // Endonym (where it materially differs)
  hasBundledVoices?: boolean;
}

export const LANGUAGES: LanguageOption[] = [
  { code: "eng", name: "English",     hasBundledVoices: true },
  { code: "spa", name: "Spanish",     native: "Español", hasBundledVoices: true },
  { code: "fra", name: "French",      native: "Français", hasBundledVoices: true },
  { code: "deu", name: "German",      native: "Deutsch" },
  { code: "ita", name: "Italian",     native: "Italiano" },
  { code: "por", name: "Portuguese",  native: "Português" },
  { code: "nld", name: "Dutch",       native: "Nederlands" },
  { code: "pol", name: "Polish",      native: "Polski" },
  { code: "ces", name: "Czech",       native: "Čeština", hasBundledVoices: true },
  { code: "hun", name: "Hungarian",   native: "Magyar" },
  { code: "tur", name: "Turkish",     native: "Türkçe" },
  { code: "rus", name: "Russian",     native: "Русский", hasBundledVoices: true },
  { code: "ukr", name: "Ukrainian",   native: "Українська" },
  { code: "zho", name: "Chinese",     native: "中文" },
  { code: "jpn", name: "Japanese",    native: "日本語", hasBundledVoices: true },
  { code: "kor", name: "Korean",      native: "한국어" },
  { code: "ara", name: "Arabic",      native: "العربية", hasBundledVoices: true },
  { code: "fas", name: "Persian",     native: "فارسی", hasBundledVoices: true },
  { code: "hin", name: "Hindi",       native: "हिन्दी" },
  { code: "vie", name: "Vietnamese",  native: "Tiếng Việt" },
  { code: "ind", name: "Indonesian",  native: "Bahasa Indonesia" },
  { code: "tha", name: "Thai",        native: "ไทย" },
  { code: "ben", name: "Bengali",     native: "বাংলা" },
  { code: "tam", name: "Tamil",       native: "தமிழ்" },
  { code: "tel", name: "Telugu",      native: "తెలుగు" },
  { code: "urd", name: "Urdu",        native: "اردو" },
  { code: "heb", name: "Hebrew",      native: "עברית" },
  { code: "ron", name: "Romanian",    native: "Română" },
  { code: "swe", name: "Swedish",     native: "Svenska" },
  { code: "dan", name: "Danish",      native: "Dansk" },
  { code: "fin", name: "Finnish",     native: "Suomi" },
  { code: "nor", name: "Norwegian",   native: "Norsk" },
];

export function getLanguage(code: string): LanguageOption | undefined {
  return LANGUAGES.find((l) => l.code === code);
}

export function languageLabel(code: string): string {
  const l = getLanguage(code);
  if (!l) return code;
  return l.native ? `${l.name} — ${l.native}` : l.name;
}
