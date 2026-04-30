// Typed API client for the FastAPI backend.

const API = "";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) msg = body.detail;
    } catch { /* swallow */ }
    throw new Error(msg);
  }
  return (await res.json()) as T;
}

// ---------------------------------------------------------------------------
// Sessions
// ---------------------------------------------------------------------------

export interface UploadResponse {
  session_id: string;
  filename: string;
}

export interface SessionStatus {
  session_id: string;
  status: string; // ready | converting | done | error | cancelled
  block_resume: number;
  blocks_total: number;
  sentence_resume: number;
  filename: string | null;
  audiobook_path: string | null;
  error: string | null;
}

export interface Block {
  id: string;
  title: string;
  keep: boolean;
  text_preview: string;
  sentence_count: number;
}

export interface BlockFull {
  id: string;
  title: string;
  keep: boolean;
  text: string;
  sentence_count: number;
}

export async function getBlocks(id: string): Promise<Block[]> {
  return json(await fetch(`${API}/api/sessions/${id}/blocks`));
}

export async function getBlock(id: string, blockId: string): Promise<BlockFull> {
  return json(await fetch(`${API}/api/sessions/${id}/blocks/${blockId}`));
}

export async function updateBlock(
  id: string,
  blockId: string,
  patch: { keep?: boolean; text?: string; title?: string }
): Promise<void> {
  await fetch(`${API}/api/sessions/${id}/blocks/${blockId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
}

export async function deleteBlock(id: string, blockId: string): Promise<void> {
  await fetch(`${API}/api/sessions/${id}/blocks/${blockId}`, { method: "DELETE" });
}

export async function moveBlock(
  id: string,
  blockId: string,
  direction: "up" | "down"
): Promise<{ new_index: number }> {
  return json(
    await fetch(`${API}/api/sessions/${id}/blocks/${blockId}/move`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ direction }),
    })
  );
}

export async function uploadEbook(file: File): Promise<UploadResponse> {
  const fd = new FormData();
  fd.append("file", file);
  return json(await fetch(`${API}/api/sessions/upload`, { method: "POST", body: fd }));
}

export async function createTestRun(): Promise<UploadResponse & { is_test_run: boolean }> {
  return json(await fetch(`${API}/api/sessions/test-run`, { method: "POST" }));
}

export async function getSession(id: string): Promise<SessionStatus> {
  return json(await fetch(`${API}/api/sessions/${id}`));
}

export async function listSessions(): Promise<SessionStatus[]> {
  return json(await fetch(`${API}/api/sessions`));
}

export interface ConversionSettings {
  language: string;
  voice_path: string | null;
  tts_engine: string;
  device: string;
  output_format: string;
  xtts_speed: number;
  xtts_temperature: number;
  fishspeech_temperature: number;
  fishspeech_top_p: number;
  fishspeech_repetition_penalty: number;
  fishspeech_max_new_tokens: number;
  cosyvoice_speed: number;
  cosyvoice_instruct_text: string;
}

export async function startConversion(
  id: string,
  opts: ConversionSettings
): Promise<void> {
  await fetch(`${API}/api/sessions/${id}/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(opts),
  });
}

export async function cancelConversion(id: string): Promise<void> {
  await fetch(`${API}/api/sessions/${id}/cancel`, { method: "POST" });
}

export async function parseEbook(
  id: string,
  opts: ConversionSettings
): Promise<void> {
  await fetch(`${API}/api/sessions/${id}/parse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(opts),
  });
}

export type SseEvent =
  | { type: "alert"; alert_type: string; msg: string }
  | { type: "stdout"; msg: string }
  | { type: "status"; status: string }
  | { type: "parse_done"; ok: boolean; error?: string }
  | { type: "ping" };

export function subscribeEvents(
  id: string,
  onEvent: (e: SseEvent) => void
): () => void {
  const es = new EventSource(`${API}/api/sessions/${id}/events`);
  es.onmessage = (msg) => {
    if (!msg.data) return;
    try { onEvent(JSON.parse(msg.data) as SseEvent); } catch { /* malformed */ }
  };
  es.onerror = () => { /* auto-reconnects */ };
  return () => es.close();
}

// ---------------------------------------------------------------------------
// Voices
// ---------------------------------------------------------------------------

export interface Voice {
  name: string;
  path: string;
  size_bytes: number;
  url: string;
}

export async function listVoices(): Promise<Voice[]> {
  return json(await fetch(`${API}/api/voices`));
}

export async function uploadVoice(file: File): Promise<Voice> {
  const fd = new FormData();
  fd.append("file", file);
  return json(await fetch(`${API}/api/voices`, { method: "POST", body: fd }));
}

export async function deleteVoice(name: string): Promise<void> {
  await fetch(`${API}/api/voices/${encodeURIComponent(name)}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Library
// ---------------------------------------------------------------------------

export interface LibraryEntry {
  filename: string;
  rel_path: string;
  size_bytes: number;
  url: string;
  created_at: string | null;
}

export interface LibrarySession {
  session_id: string;
  filename: string;
  status: string;
  block_resume: number;
  blocks_total: number;
  audiobook_path: string | null;
  created_at: string | null;
}

export async function listLibrary(): Promise<LibraryEntry[]> {
  return json(await fetch(`${API}/api/library`));
}

export async function listLibrarySessions(): Promise<LibrarySession[]> {
  return json(await fetch(`${API}/api/library/sessions`));
}

export function downloadUrl(rel_path: string): string {
  return `${API}/api/library/file/${rel_path}`;
}

export async function deleteSession(id: string): Promise<void> {
  await fetch(`${API}/api/sessions/${id}`, { method: "DELETE" });
}

export async function combineSession(id: string): Promise<void> {
  const res = await fetch(`${API}/api/sessions/${id}/combine`, { method: "POST" });
  if (!res.ok) {
    let msg = res.statusText;
    try { const b = await res.json(); if (b?.detail) msg = b.detail; } catch { /* swallow */ }
    throw new Error(msg);
  }
}

// ---------------------------------------------------------------------------
// Voice Preview
// ---------------------------------------------------------------------------

export interface PreviewRequest {
  text: string;
  voice_path: string | null;
  language: string;
  tts_engine: string;
  device: string;
  xtts_speed: number;
  xtts_temperature: number;
  fishspeech_temperature: number;
  fishspeech_top_p: number;
  fishspeech_repetition_penalty: number;
  fishspeech_max_new_tokens: number;
  cosyvoice_speed: number;
  cosyvoice_instruct_text: string;
}

/**
 * Synthesize a short text snippet and return an object URL for the audio blob.
 * Caller is responsible for calling URL.revokeObjectURL() when done.
 */
export async function previewVoice(req: ConversionSettings & { text: string }): Promise<string> {
  const res = await fetch(`${API}/api/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) msg = body.detail;
    } catch { /* swallow */ }
    throw new Error(msg);
  }
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}
