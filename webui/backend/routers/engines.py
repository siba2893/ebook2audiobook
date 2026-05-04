"""TTS-engine catalog — filters available engines by the active install profile.

The frontend's engine dropdown reads from `/api/engines` instead of hardcoding
the list, so the visible engines match what's actually installed in
`python_env/`.  The active profile is selected by a `.engine-mode` marker file
at the repo root, written by one of the install scripts:

  - `1_regular_engines_install.cmd`   →  .engine-mode = "regular"
                                         (XTTS, Bark, Tortoise, VITS, Fairseq,
                                          GlowTTS, Tacotron2, YourTTS,
                                          Fish Speech 1.5)
  - `2_cosy_voice_engine_install.cmd` →  .engine-mode = "cosyvoice"
                                         (CosyVoice 3 only)
  - `3_qwen3tts_engine_install.cmd`   →  .engine-mode = "qwen3tts"
                                         (Qwen3-TTS only)
  - `4_f5tts_engine_install.cmd`      →  .engine-mode = "f5tts"
                                         (F5-TTS — English/Chinese via
                                          F5TTS_v1_Base; Spanish via
                                          jpgallegoar/F5-Spanish fine-tune)
  - `5_qwen_fast_install.cmd`         →  .engine-mode = "qwen_fast"
                                         (Qwen3-TTS routed through
                                          faster-qwen3-tts CUDA-graph fork;
                                          same dropdown entry as qwen3tts,
                                          backend auto-selected by the engine
                                          class)

The "regular", "cosyvoice", "qwen3tts", "f5tts", and "qwen_fast" installs use
mutually-incompatible PyTorch/package sets, so the dropdown only shows the
engines the current install actually supports.  No marker → defaults to
"regular".
"""
import os

from fastapi import APIRouter

router = APIRouter()

_REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

_LABELS = {
    "xtts":       "XTTSv2",
    "bark":       "Bark",
    "tortoise":   "Tortoise",
    "vits":       "VITS",
    "fairseq":    "Fairseq",
    "glowtts":    "GlowTTS",
    "tacotron":   "Tacotron2",
    "yourtts":    "YourTTS",
    "fishspeech": "Fish Speech 1.5",
    "cosyvoice":  "CosyVoice 3",
    "qwen3tts":   "Qwen3-TTS",
    "f5tts":      "F5-TTS",
}

_REGULAR = ["xtts", "bark", "tortoise", "vits", "fairseq",
            "glowtts", "tacotron", "yourtts", "fishspeech"]
_COSYVOICE_ONLY = ["cosyvoice"]
_QWEN3TTS_ONLY = ["qwen3tts"]
_F5TTS_ONLY = ["f5tts"]


def _read_mode() -> str:
    marker = os.path.join(_REPO_ROOT, ".engine-mode")
    try:
        with open(marker, "r", encoding="utf-8") as f:
            value = f.read().strip().lower()
        return value or "regular"
    except FileNotFoundError:
        return "regular"


@router.get("/engines")
def list_engines():
    mode = _read_mode()
    if mode == "cosyvoice":
        keys = _COSYVOICE_ONLY
    elif mode in ("qwen3tts", "qwen_fast"):
        # qwen_fast routes the same Qwen3-TTS engine through the
        # faster-qwen3-tts CUDA-graph fork — the engine class auto-detects
        # the backend from .engine-mode, so the dropdown surfaces the same
        # qwen3tts entry under both profiles.
        keys = _QWEN3TTS_ONLY
    elif mode == "f5tts":
        keys = _F5TTS_ONLY
    else:
        keys = _REGULAR
    return {
        "mode": mode,
        "engines": [{"key": k, "label": _LABELS[k]} for k in keys],
    }
