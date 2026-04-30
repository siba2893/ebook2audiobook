import asyncio
import io
import os
import shutil
import sys
import tempfile
import threading
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Ensure repo root is in path and cwd (lib/conf.py needs VERSION.txt from cwd)
# ---------------------------------------------------------------------------
_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
os.chdir(_ROOT)

import lib.core as _core
from lib.conf_models import default_fine_tuned
from webui.backend.session_store import save as _meta_save, load as _meta_load, all_sessions as _meta_all

# Access context lazily — it is None until lifespan initializes it
def _ctx():
    return _core.context

status_tags = _core.status_tags

router = APIRouter()

# ---------------------------------------------------------------------------
# Per-session event queues (asyncio-safe, lives in this process)
# ---------------------------------------------------------------------------
_event_queues: dict[str, asyncio.Queue] = {}

# ---------------------------------------------------------------------------
# Wrap show_alert to capture events for SSE
# ---------------------------------------------------------------------------
_orig_show_alert = _core.show_alert

def _patched_show_alert(session_id, state):
    _orig_show_alert(session_id, state)
    if session_id and state and state.get("msg"):
        q = _event_queues.get(session_id)
        if q:
            try:
                q.put_nowait({
                    "type": "alert",
                    "alert_type": state.get("type", "info"),
                    "msg": state["msg"].replace("<br/>", "\n"),
                })
            except asyncio.QueueFull:
                pass

_core.show_alert = _patched_show_alert

# ---------------------------------------------------------------------------
# stdout capture — redirects print() calls into the SSE queue for a session
# ---------------------------------------------------------------------------

# Thread-local storage so concurrent sessions don't clobber each other
_tls = threading.local()

class _SessionStdout(io.TextIOBase):
    """Wraps sys.stdout; forwards each line to the session's SSE queue."""

    def __init__(self, session_id: str, real_stdout):
        self._session_id = session_id
        self._real = real_stdout
        self._buf = ""

    def write(self, text: str) -> int:
        self._real.write(text)
        self._real.flush()
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            line = line.strip()
            if line:
                q = _event_queues.get(self._session_id)
                if q:
                    try:
                        q.put_nowait({"type": "stdout", "msg": line})
                    except asyncio.QueueFull:
                        pass
        return len(text)

    def flush(self):
        self._real.flush()

    @property
    def encoding(self):
        return getattr(self._real, "encoding", "utf-8")

    @property
    def errors(self):
        return getattr(self._real, "errors", "replace")


from contextlib import contextmanager

@contextmanager
def _capture_stdout(session_id: str):
    """Context manager: redirect this thread's stdout into the SSE queue."""
    real = sys.stdout
    sys.stdout = _SessionStdout(session_id, real)
    try:
        yield
    finally:
        sys.stdout = real

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ACCEPTED_EXTENSIONS = {".epub", ".pdf", ".txt", ".mobi", ".azw3", ".fb2",
                       ".lit", ".html", ".rtf", ".doc"}


# ---------------------------------------------------------------------------
# Session persistence helpers
# ---------------------------------------------------------------------------

def _save_meta(session_id: str, extra: dict | None = None):
    """Persist lightweight session metadata to disk."""
    import datetime
    session = _ctx().get_session(session_id)
    if not session:
        return
    # Preserve created_at from any existing record
    existing = _meta_load(session_id) or {}
    data: dict[str, Any] = {
        "session_id": session_id,
        "ebook_src": session.get("ebook_src"),
        "filename": session.get("filename_noext") or os.path.basename(str(session.get("ebook_src") or "")),
        "filename_noext": session.get("filename_noext"),
        "status": session.get("status"),
        "blocks_current_json": session.get("blocks_current_json"),
        "process_dir": session.get("process_dir"),
        "audiobook": session.get("audiobook"),
        "created_at": existing.get("created_at") or datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    if extra:
        data.update(extra)
    _meta_save(session_id, data)


def recover_sessions_from_disk():
    """Called once at startup. Rebuilds in-memory sessions from disk metadata."""
    recovered = 0
    for meta in _meta_all():
        sid = meta.get("session_id")
        if not sid:
            continue
        # Skip if ebook source is gone
        ebook_src = meta.get("ebook_src")
        if not ebook_src or not os.path.exists(ebook_src):
            continue
        try:
            _ctx().set_session(sid)
            session = _ctx().get_session(sid)
            session["ebook_src"] = ebook_src
            session["is_gui_process"] = False
            if meta.get("filename_noext"):
                session["filename_noext"] = meta["filename_noext"]
            elif meta.get("filename"):
                session["filename_noext"] = meta["filename"]
            if meta.get("process_dir") and os.path.isdir(meta["process_dir"]):
                session["process_dir"] = meta["process_dir"]
            if meta.get("blocks_current_json") and os.path.exists(meta["blocks_current_json"]):
                from lib.core import load_json_blocks
                blocks = load_json_blocks(meta["blocks_current_json"])
                if blocks:
                    session["blocks_current"] = blocks
                    session["blocks_current_json"] = meta["blocks_current_json"]
                    # Only mark EDIT if status wasn't already completed
                    if str(meta.get("status") or "").lower() != "end":
                        session["status"] = status_tags.get("EDIT")
            if meta.get("audiobook") and os.path.exists(str(meta.get("audiobook") or "")):
                session["audiobook"] = meta["audiobook"]
                session["status"] = status_tags.get("END")
            elif str(meta.get("status") or "").lower() == "end":
                # Combine completed but audiobook path wasn't saved — still mark done
                session["status"] = status_tags.get("END")
            _event_queues[sid] = asyncio.Queue(maxsize=500)
            recovered += 1
            print(f"[sessions] Recovered session {sid} ({meta.get('filename', 'unknown')})")
        except Exception as e:
            print(f"[sessions] Failed to recover session {sid}: {e}")
    if recovered:
        print(f"[sessions] {recovered} session(s) recovered from disk.")


def _session_status(session_id: str) -> dict:
    session = _ctx().get_session(session_id)
    if not session or not session.get("id"):
        raise HTTPException(status_code=404, detail="Session not found")

    raw_status = session.get("status")
    # Map internal status tags to simple strings
    tag_map = {
        status_tags.get("READY"): "ready",
        status_tags.get("EDIT"): "edit",
        status_tags.get("CONVERTING"): "converting",
        status_tags.get("END"): "done",
        None: "ready",
    }
    status_str = tag_map.get(raw_status, str(raw_status or "ready"))

    # Check for explicit cancellation
    if session.get("cancellation_requested") and status_str not in ("done", "error"):
        status_str = "cancelled"

    blocks_current = session.get("blocks_current") or {}

    # Don't report "edit" if blocks haven't been written yet — keep frontend polling
    if status_str == "edit" and not (blocks_current.get("blocks")):
        status_str = "ready"
    blocks_total = 0
    if blocks_current:
        try:
            blocks_total = sum(
                1 for b in (blocks_current.get("blocks") or [])
                if b.get("keep") and str(b.get("text", "")).strip()
            )
        except Exception:
            pass

    return {
        "session_id": session_id,
        "status": status_str,
        "block_resume": int(blocks_current.get("block_resume") or 0),
        "blocks_total": blocks_total,
        "sentence_resume": int(blocks_current.get("sentence_resume") or 0),
        "filename": session.get("filename_noext"),
        "audiobook_path": session.get("audiobook"),
        "error": None,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/sessions/upload", status_code=201)
async def upload_ebook(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ACCEPTED_EXTENSIONS:
        raise HTTPException(status_code=422, detail=f"Unsupported file type: {ext}")

    session_id = str(uuid.uuid4())

    # Save upload to a temp file that persists (NamedTemporaryFile would delete on close)
    tmp_dir = tempfile.mkdtemp(prefix="e2a_upload_")
    dest = os.path.join(tmp_dir, file.filename or f"upload{ext}")
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Create session and point it at the file
    _ctx().set_session(session_id)
    session = _ctx().get_session(session_id)
    session["ebook_src"] = dest
    session["is_gui_process"] = False

    # Create per-session event queue
    _event_queues[session_id] = asyncio.Queue(maxsize=500)

    # Persist metadata so we can recover after a restart
    import datetime as _dt
    _meta_save(session_id, {
        "session_id": session_id,
        "ebook_src": dest,
        "filename": os.path.basename(dest),
        "status": None,
        "blocks_current_json": None,
        "process_dir": None,
        "audiobook": None,
        "created_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
    })

    return {"session_id": session_id, "filename": os.path.basename(dest)}


@router.post("/sessions/test-run", status_code=201)
async def create_test_run_session():
    """Create a session pre-loaded with assets/sample.epub for engine comparison."""
    sample_path = os.path.join(_ROOT, "assets", "sample.epub")
    if not os.path.isfile(sample_path):
        raise HTTPException(status_code=404, detail="assets/sample.epub not found — run tools/gen_sample_epub.py first")

    session_id = str(uuid.uuid4())
    _ctx().set_session(session_id)
    session = _ctx().get_session(session_id)
    session["ebook_src"] = sample_path
    session["is_gui_process"] = False
    session["filename_noext"] = "sample"

    _event_queues[session_id] = asyncio.Queue(maxsize=500)

    import datetime as _dt
    _meta_save(session_id, {
        "session_id": session_id,
        "ebook_src": sample_path,
        "filename": "sample.epub",
        "filename_noext": "sample",
        "status": None,
        "blocks_current_json": None,
        "process_dir": None,
        "audiobook": None,
        "created_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
    })

    return {"session_id": session_id, "filename": "sample.epub", "is_test_run": True}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    return _session_status(session_id)


@router.delete("/sessions/{session_id}", status_code=200)
async def delete_session(session_id: str):
    """Remove session from memory and delete its persisted metadata + tmp files."""
    import shutil
    ctx = _ctx()
    session = ctx.get_session(session_id)

    # Resolve ebook_src and process_dir from memory or fallback to disk meta
    meta = _meta_load(session_id) or {}
    ebook_src = (session.get("ebook_src") if session else None) or meta.get("ebook_src")
    process_dir = (session.get("process_dir") if session else None) or meta.get("process_dir")

    # Delete the tmp/proc-{session_id}/ parent dir (contains the hash subdir and all chapters)
    _ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    proc_parent = os.path.join(_ROOT, "tmp", f"proc-{session_id}")
    for d in [proc_parent, process_dir]:
        if d and os.path.isdir(d):
            try:
                shutil.rmtree(d)
                print(f"[sessions] delete_session: removed {d}")
            except Exception as e:
                print(f"[sessions] delete_session: could not remove {d}: {e}")

    # Delete the uploaded ebook file and its parent upload dir if it only contained that file
    if ebook_src and os.path.isfile(ebook_src):
        upload_dir = os.path.dirname(ebook_src)
        try:
            os.remove(ebook_src)
        except Exception as e:
            print(f"[sessions] delete_session: could not remove ebook_src {ebook_src}: {e}")
        # Remove the upload dir if now empty
        if upload_dir and os.path.isdir(upload_dir):
            try:
                if not os.listdir(upload_dir):
                    shutil.rmtree(upload_dir)
            except Exception as e:
                print(f"[sessions] delete_session: could not remove upload_dir {upload_dir}: {e}")

    # Remove from in-memory store
    if session:
        ctx.sessions.pop(session_id, None)

    # Clean up disk metadata
    meta_dir = os.path.join(
        os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..")),
        "run", "__sessions", session_id
    )
    if os.path.isdir(meta_dir):
        try:
            shutil.rmtree(meta_dir)
        except Exception as e:
            print(f"[sessions] delete_session: could not remove meta_dir {meta_dir}: {e}")

    # Close SSE queue
    _event_queues.pop(session_id, None)

    return {"deleted": session_id}


@router.get("/sessions")
async def list_recoverable_sessions():
    """Return all sessions currently alive in memory (survived restart or just uploaded)."""
    ctx = _ctx()
    results = []
    for sid in list(ctx.sessions.keys()):
        try:
            results.append(_session_status(sid))
        except Exception:
            pass
    return results


class StartRequest(BaseModel):
    language: str = "spa"
    voice_path: str | None = None
    tts_engine: str = "xtts"
    device: str = "cuda"
    output_format: str = "m4b"
    xtts_speed: float = 1.0
    xtts_temperature: float = 0.85
    fishspeech_temperature: float = 0.8
    fishspeech_top_p: float = 0.8
    fishspeech_repetition_penalty: float = 1.1
    fishspeech_max_new_tokens: int = 1024
    cosyvoice_speed: float = 1.0
    cosyvoice_instruct_text: str = ""


def _build_args(session_id: str, req: "StartRequest", lang_pt3: str, lang_pt1: str, blocks_preview: bool) -> dict[str, Any]:
    """Build the full args dict required by convert_ebook."""
    from lib.conf_models import default_engine_settings, TTS_ENGINES
    from lib.conf import default_output_channel
    xtts = default_engine_settings[TTS_ENGINES["XTTSv2"]]
    bark = default_engine_settings[TTS_ENGINES["BARK"]]
    session = _ctx().get_session(session_id)
    # Write output under audiobooks/webui/<session_id>/ so library.py can find it
    _ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    output_dir = os.path.join(_ROOT, "audiobooks", "webui", session_id)
    os.makedirs(output_dir, exist_ok=True)
    return {
        "id": session_id,
        "language": lang_pt3,
        "language_iso1": lang_pt1,
        "voice": req.voice_path,
        "tts_engine": req.tts_engine,
        "fine_tuned": default_fine_tuned,
        "device": req.device,
        "ebook_src": session["ebook_src"],
        "ebook_mode": "single",
        "is_gui_process": False,
        "script_mode": "native",
        "blocks_preview": blocks_preview,
        "output_format": req.output_format,
        "output_dir": output_dir,
        "output_channel": default_output_channel,
        "output_split": False,
        "output_split_hours": None,
        "xtts_speed": req.xtts_speed,
        "xtts_temperature": req.xtts_temperature,
        "xtts_length_penalty": xtts["length_penalty"],
        "xtts_num_beams": xtts["num_beams"],
        "xtts_repetition_penalty": xtts["repetition_penalty"],
        "xtts_top_k": xtts["top_k"],
        "xtts_top_p": xtts["top_p"],
        "xtts_enable_text_splitting": xtts["enable_text_splitting"],
        "bark_text_temp": bark["text_temp"],
        "bark_waveform_temp": bark["waveform_temp"],
        # Fish Speech
        "fishspeech_temperature": req.fishspeech_temperature,
        "fishspeech_top_p": req.fishspeech_top_p,
        "fishspeech_repetition_penalty": req.fishspeech_repetition_penalty,
        "fishspeech_max_new_tokens": req.fishspeech_max_new_tokens,
        # CosyVoice
        "cosyvoice_speed": req.cosyvoice_speed,
        "cosyvoice_instruct_text": req.cosyvoice_instruct_text,
        "ebook_list": None,
        "ebook_textarea": None,
        "custom_model": None,
    }


def _run_conversion(session_id: str, req: StartRequest):
    """Blocking — runs in a thread executor."""
    try:
        from iso639 import Lang
        lang_obj = Lang(req.language)
        lang_pt3 = lang_obj.pt3
        lang_pt1 = lang_obj.pt1
    except Exception:
        lang_pt3 = req.language
        lang_pt1 = req.language[:2] if len(req.language) >= 2 else req.language

    session = _ctx().get_session(session_id)
    if not session:
        return

    args = _build_args(session_id, req, lang_pt3, lang_pt1, blocks_preview=False)

    from lib.core import convert_ebook
    with _capture_stdout(session_id):
        error, _ok = convert_ebook(args)
    # Persist metadata so audiobook path and final status survive restarts
    _save_meta(session_id)
    if error:
        q = _event_queues.get(session_id)
        if q:
            try:
                q.put_nowait({"type": "status", "status": "error", "error": str(error)})
            except asyncio.QueueFull:
                pass
    else:
        q = _event_queues.get(session_id)
        if q:
            try:
                q.put_nowait({"type": "status", "status": "done"})
            except asyncio.QueueFull:
                pass


@router.post("/sessions/{session_id}/start", status_code=202)
async def start_conversion(session_id: str, req: StartRequest, background_tasks: BackgroundTasks):
    session = _ctx().get_session(session_id)
    if not session or not session.get("id"):
        raise HTTPException(status_code=404, detail="Session not found")
    if session.get("status") == status_tags.get("CONVERTING"):
        raise HTTPException(status_code=409, detail="Conversion already running")

    # Apply XTTS settings to session before conversion
    session["xtts_speed"] = req.xtts_speed
    session["xtts_temperature"] = req.xtts_temperature

    loop = asyncio.get_event_loop()
    background_tasks.add_task(
        lambda: loop.run_in_executor(None, _run_conversion, session_id, req)
    )
    return {"session_id": session_id, "status": "started"}


@router.post("/sessions/{session_id}/cancel")
async def cancel_conversion(session_id: str):
    session = _ctx().get_session(session_id)
    if not session or not session.get("id"):
        raise HTTPException(status_code=404, detail="Session not found")
    session["cancellation_requested"] = True
    return {"session_id": session_id, "status": "cancelling"}


def _run_parse(session_id: str, req: StartRequest):
    """Blocking — runs in a thread executor. Parses the ebook into blocks without doing TTS."""
    try:
        from iso639 import Lang
        lang_obj = Lang(req.language)
        lang_pt3 = lang_obj.pt3
        lang_pt1 = lang_obj.pt1
    except Exception:
        lang_pt3 = req.language
        lang_pt1 = req.language[:2] if len(req.language) >= 2 else req.language

    session = _ctx().get_session(session_id)
    if not session:
        return

    args = _build_args(session_id, req, lang_pt3, lang_pt1, blocks_preview=True)

    from lib.core import convert_ebook
    with _capture_stdout(session_id):
        error, _ok = convert_ebook(args)
    q = _event_queues.get(session_id)
    # Save metadata so blocks_current_json path is persisted
    _save_meta(session_id)
    if q:
        try:
            if error:
                q.put_nowait({"type": "parse_done", "ok": False, "error": str(error)})
            else:
                q.put_nowait({"type": "parse_done", "ok": True})
        except asyncio.QueueFull:
            pass


@router.post("/sessions/{session_id}/parse", status_code=202)
async def parse_ebook(session_id: str, req: StartRequest, background_tasks: BackgroundTasks):
    """Parse the ebook into blocks (blocks_preview mode) without starting TTS.
    Poll GET /sessions/{id} until status == 'ready' (EDIT tag), then fetch /blocks."""
    session = _ctx().get_session(session_id)
    if not session or not session.get("id"):
        raise HTTPException(status_code=404, detail="Session not found")

    loop = asyncio.get_event_loop()
    background_tasks.add_task(
        lambda: loop.run_in_executor(None, _run_parse, session_id, req)
    )
    return {"session_id": session_id, "status": "parsing"}


def _run_combine(session_id: str):
    """Blocking — runs in a thread executor. Calls combine_audio_chapters only (no TTS)."""
    session = _ctx().get_session(session_id)
    if not session:
        return

    # Ensure required fields are populated so combine_audio_chapters works
    process_dir = session.get("process_dir", "")
    _ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

    if not session.get("chapters_dir"):
        session["chapters_dir"] = os.path.join(process_dir, "chapters")
    if not session.get("audiobooks_dir"):
        output_dir = os.path.join(_ROOT, "audiobooks", "webui", session_id)
        os.makedirs(output_dir, exist_ok=True)
        session["audiobooks_dir"] = output_dir
    if not session.get("output_format"):
        session["output_format"] = "m4b"
    if not session.get("final_name"):
        fname = (
            session.get("filename_noext")
            or session.get("filename")
            or os.path.splitext(os.path.basename(str(session.get("ebook_src") or "")))[0]
            or session_id
        )
        session["final_name"] = f"{fname}.{session['output_format']}"
    if not session.get("metadata") or not session["metadata"].get("title"):
        fname = (
            session.get("filename_noext")
            or session.get("filename")
            or os.path.splitext(os.path.basename(str(session.get("ebook_src") or "")))[0]
            or session_id
        )
        session["metadata"] = {
            **(session.get("metadata") or {}),
            "title": fname,
        }
        session["metadata"].setdefault("creator", None)
        session["metadata"].setdefault("language", None)
        session["metadata"].setdefault("description", None)
        session["metadata"].setdefault("publisher", None)
        session["metadata"].setdefault("published", None)
    session.setdefault("is_gui_process", False)
    session.setdefault("cancellation_requested", False)
    session.setdefault("output_split", False)
    session.setdefault("output_split_hours", None)

    from lib.core import combine_audio_chapters
    q = _event_queues.get(session_id)
    with _capture_stdout(session_id):
        exported = combine_audio_chapters(session_id)

    if exported:
        audiobook_path = exported[0]
        session["audiobook"] = audiobook_path
        session["status"] = status_tags.get("END")
        _save_meta(session_id)
        if q:
            try:
                q.put_nowait({"type": "status", "status": "done", "audiobook": audiobook_path})
            except asyncio.QueueFull:
                pass
    else:
        if q:
            try:
                q.put_nowait({"type": "status", "status": "error", "error": "combine_audio_chapters returned no output"})
            except asyncio.QueueFull:
                pass


@router.post("/sessions/{session_id}/combine", status_code=202)
async def combine_session(session_id: str, background_tasks: BackgroundTasks):
    """Finish a stalled session by running the combine step only (no TTS re-run).
    Requires all chapter .flac files to already exist in process_dir/chapters/."""
    session = _ctx().get_session(session_id)
    if not session or not session.get("id"):
        raise HTTPException(status_code=404, detail="Session not found")
    if session.get("status") == status_tags.get("CONVERTING"):
        raise HTTPException(status_code=409, detail="Conversion already running")

    loop = asyncio.get_event_loop()
    background_tasks.add_task(
        lambda: loop.run_in_executor(None, _run_combine, session_id)
    )
    return {"session_id": session_id, "status": "combining"}


@router.get("/sessions/{session_id}/blocks")
async def get_blocks(session_id: str):
    session = _ctx().get_session(session_id)
    if not session or not session.get("id"):
        raise HTTPException(status_code=404, detail="Session not found")
    blocks_current = session.get("blocks_current") or {}
    raw_blocks = blocks_current.get("blocks") or []
    result = []
    for i, b in enumerate(raw_blocks):
        text = str(b.get("text") or "")
        result.append({
            "id": str(b.get("id") or i),
            "title": str(b.get("title") or f"Chapter {i + 1}"),
            "keep": bool(b.get("keep", True)),
            "text_preview": text[:800],
            "sentence_count": len(b.get("sentences") or []),
        })
    return result


class BlockPatch(BaseModel):
    keep: bool | None = None
    text: str | None = None
    title: str | None = None


@router.get("/sessions/{session_id}/blocks/{block_id}")
async def get_block(session_id: str, block_id: str):
    session = _ctx().get_session(session_id)
    if not session or not session.get("id"):
        raise HTTPException(status_code=404, detail="Session not found")
    blocks_current = session.get("blocks_current") or {}
    raw_blocks = blocks_current.get("blocks") or []
    for i, b in enumerate(raw_blocks):
        if str(b.get("id")) == block_id:
            text = str(b.get("text") or "")
            return {
                "id": str(b.get("id") or i),
                "title": str(b.get("title") or f"Chapter {i + 1}"),
                "keep": bool(b.get("keep", True)),
                "text": text,
                "sentence_count": len(b.get("sentences") or []),
            }
    raise HTTPException(status_code=404, detail="Block not found")


@router.put("/sessions/{session_id}/blocks/{block_id}")
async def update_block(session_id: str, block_id: str, patch: BlockPatch):
    session = _ctx().get_session(session_id)
    if not session or not session.get("id"):
        raise HTTPException(status_code=404, detail="Session not found")
    blocks_current = session.get("blocks_current") or {}
    raw_blocks = blocks_current.get("blocks") or []
    for b in raw_blocks:
        if str(b.get("id")) == block_id:
            if patch.keep is not None:
                b["keep"] = patch.keep
            if patch.text is not None:
                b["text"] = patch.text
            if patch.title is not None:
                b["title"] = patch.title
            break
    else:
        raise HTTPException(status_code=404, detail="Block not found")
    blocks_current["blocks"] = raw_blocks
    session["blocks_current"] = blocks_current
    return {"ok": True}


@router.delete("/sessions/{session_id}/blocks/{block_id}", status_code=200)
async def delete_block(session_id: str, block_id: str):
    session = _ctx().get_session(session_id)
    if not session or not session.get("id"):
        raise HTTPException(status_code=404, detail="Session not found")
    blocks_current = session.get("blocks_current") or {}
    raw_blocks = blocks_current.get("blocks") or []
    new_blocks = [b for b in raw_blocks if str(b.get("id")) != block_id]
    if len(new_blocks) == len(raw_blocks):
        raise HTTPException(status_code=404, detail="Block not found")
    blocks_current["blocks"] = new_blocks
    session["blocks_current"] = blocks_current
    return {"ok": True}


class BlockMove(BaseModel):
    direction: str  # "up" or "down"


@router.post("/sessions/{session_id}/blocks/{block_id}/move", status_code=200)
async def move_block(session_id: str, block_id: str, body: BlockMove):
    session = _ctx().get_session(session_id)
    if not session or not session.get("id"):
        raise HTTPException(status_code=404, detail="Session not found")
    blocks_current = session.get("blocks_current") or {}
    raw_blocks = blocks_current.get("blocks") or []
    idx = next((i for i, b in enumerate(raw_blocks) if str(b.get("id")) == block_id), None)
    if idx is None:
        raise HTTPException(status_code=404, detail="Block not found")
    if body.direction == "up" and idx > 0:
        raw_blocks[idx - 1], raw_blocks[idx] = raw_blocks[idx], raw_blocks[idx - 1]
        new_idx = idx - 1
    elif body.direction == "down" and idx < len(raw_blocks) - 1:
        raw_blocks[idx], raw_blocks[idx + 1] = raw_blocks[idx + 1], raw_blocks[idx]
        new_idx = idx + 1
    else:
        new_idx = idx  # already at boundary — no-op
    blocks_current["blocks"] = raw_blocks
    session["blocks_current"] = blocks_current
    return {"ok": True, "new_index": new_idx}


@router.get("/sessions/{session_id}/events")
async def session_events(session_id: str):
    session = _ctx().get_session(session_id)
    if not session or not session.get("id"):
        raise HTTPException(status_code=404, detail="Session not found")

    q = _event_queues.get(session_id)
    if q is None:
        q = asyncio.Queue(maxsize=500)
        _event_queues[session_id] = q

    import json

    async def stream():
        ping_interval = 15
        elapsed = 0
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=1.0)
                yield f"data: {json.dumps(event)}\n\n"
                # Stop streaming when terminal state reached
                if event.get("type") == "status" and event.get("status") in ("done", "error", "cancelled"):
                    break
            except asyncio.TimeoutError:
                elapsed += 1
                if elapsed >= ping_interval:
                    yield ": ping\n\n"
                    elapsed = 0

    return StreamingResponse(stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })
