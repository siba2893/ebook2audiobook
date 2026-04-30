"""
Voice preview: synthesize a short text snippet and return it as a WAV audio stream.
Reuses the same XTTS engine instance if already loaded (fast), or cold-starts it.
"""
import os
import sys
import tempfile
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

router = APIRouter()

MAX_CHARS = 500  # guard against accidentally sending a whole chapter


class PreviewRequest(BaseModel):
    text: str
    voice_path: str | None = None
    language: str = "spa"
    tts_engine: str = "xtts"
    device: str = "cuda"
    xtts_speed: float = 1.0
    xtts_temperature: float = 0.85
    fishspeech_temperature: float = 0.8
    fishspeech_top_p: float = 0.8
    fishspeech_repetition_penalty: float = 1.1
    fishspeech_max_new_tokens: int = 1024
    cosyvoice_speed: float = 1.0
    cosyvoice_instruct_text: str = ""


@router.post("/preview")
async def preview_voice(req: PreviewRequest):
    import asyncio

    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="text is required")
    if len(text) > MAX_CHARS:
        raise HTTPException(status_code=422, detail=f"text too long (max {MAX_CHARS} chars)")

    loop = asyncio.get_event_loop()
    try:
        out_path = await loop.run_in_executor(None, _synthesize, req, text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return FileResponse(
        out_path,
        media_type="audio/wav",
        filename="preview.wav",
        headers={"Cache-Control": "no-store"},
    )


def _synthesize(req: PreviewRequest, text: str) -> str:
    """Blocking — runs in thread executor. Returns path to a temp WAV file."""
    import lib.core as _core

    # Resolve language codes
    try:
        from iso639 import Lang
        lang_obj = Lang(req.language)
        lang_pt3 = lang_obj.pt3
        lang_pt1 = lang_obj.pt1
    except Exception:
        lang_pt3 = req.language
        lang_pt1 = req.language[:2] if len(req.language) >= 2 else req.language

    # Build a minimal throw-away session dict (plain dict, not DictProxy)
    # so we don't pollute the session store with preview sessions
    from lib.conf import default_output_channel
    from lib.conf_models import (
        default_tts_engine, default_fine_tuned,
        default_engine_settings, TTS_ENGINES,
    )

    preview_id = f"preview-{uuid.uuid4()}"

    session: dict = {
        "id": preview_id,
        "script_mode": "native",
        "is_gui_process": False,
        "device": req.device,
        "tts_engine": req.tts_engine,
        "fine_tuned": default_fine_tuned,
        "model_cache": f"{req.tts_engine}-{default_fine_tuned}",
        "model_zs_cache": None,
        "stanza_cache": None,
        "language": lang_pt3,
        "language_iso1": lang_pt1,
        "voice": req.voice_path,
        "voice_dir": None,
        "custom_model": None,
        "custom_model_dir": "",
        "output_format": "wav",
        "output_channel": default_output_channel,
        "free_vram_gb": _get_free_vram(),
        "cancellation_requested": False,
        # XTTS-specific
        "xtts_speed": req.xtts_speed,
        "xtts_temperature": req.xtts_temperature,
        "xtts_length_penalty": default_engine_settings[TTS_ENGINES["XTTSv2"]]["length_penalty"],
        "xtts_num_beams": default_engine_settings[TTS_ENGINES["XTTSv2"]]["num_beams"],
        "xtts_repetition_penalty": default_engine_settings[TTS_ENGINES["XTTSv2"]]["repetition_penalty"],
        "xtts_top_k": default_engine_settings[TTS_ENGINES["XTTSv2"]]["top_k"],
        "xtts_top_p": default_engine_settings[TTS_ENGINES["XTTSv2"]]["top_p"],
        "xtts_enable_text_splitting": default_engine_settings[TTS_ENGINES["XTTSv2"]]["enable_text_splitting"],
        # Fish Speech-specific
        "fishspeech_temperature": req.fishspeech_temperature,
        "fishspeech_top_p": req.fishspeech_top_p,
        "fishspeech_repetition_penalty": req.fishspeech_repetition_penalty,
        "fishspeech_max_new_tokens": req.fishspeech_max_new_tokens,
        # CosyVoice-specific
        "cosyvoice_speed": req.cosyvoice_speed,
        "cosyvoice_instruct_text": req.cosyvoice_instruct_text,
    }

    # Wrap in a DictProxy-compatible shim so engine code can use [] and .get()
    session = _DictShim(session)

    # Output WAV file + per-call scratch dir for engines that materialise
    # intermediate audio (fairseq/tacotron/glowtts/vits write tmp WAVs into
    # voice_dir/proc/ during voice-conversion).
    tmp_dir = tempfile.mkdtemp(prefix="e2a_preview_")
    out_wav = os.path.join(tmp_dir, "preview.wav")
    session["voice_dir"] = tmp_dir

    from lib.classes.tts_manager import TTSManager
    tts: TTSManager = TTSManager(session)
    engine = tts.engine

    success, error = engine.convert(sentence_file=out_wav, sentence=text)
    if not success or error:
        raise RuntimeError(error or "TTS conversion failed")

    if not os.path.isfile(out_wav):
        raise RuntimeError("TTS produced no output file")

    return out_wav


def _get_free_vram() -> float:
    try:
        import torch
        if torch.cuda.is_available():
            free, _ = torch.cuda.mem_get_info()
            return free / (1024 ** 3)
    except Exception:
        pass
    return 0.0


class _DictShim(dict):
    """Plain dict that also supports attribute-style .get() — already works since dict has .get()."""
    pass
