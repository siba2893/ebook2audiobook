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

The "regular" and "cosyvoice" installs use mutually-incompatible PyTorch
versions, so the dropdown only shows the engines the current install actually
supports.  No marker → defaults to "regular".
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
}

_REGULAR = ["xtts", "bark", "tortoise", "vits", "fairseq",
            "glowtts", "tacotron", "yourtts", "fishspeech"]
_COSYVOICE_ONLY = ["cosyvoice"]


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
    keys = _COSYVOICE_ONLY if mode == "cosyvoice" else _REGULAR
    return {
        "mode": mode,
        "engines": [{"key": k, "label": _LABELS[k]} for k in keys],
    }
