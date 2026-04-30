"""
Voice management: list, upload, delete voice samples.
"""
import os
import shutil
import sys

from fastapi import APIRouter, HTTPException, UploadFile, File

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

router = APIRouter()

VOICES_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "voices"))
UPLOAD_DIR = os.path.join(VOICES_DIR, "uploaded")
AUDIO_EXTS = {".wav", ".mp3", ".flac"}


def _scan_voices():
    results = []
    for root, _dirs, files in os.walk(VOICES_DIR):
        for fname in sorted(files):
            if os.path.splitext(fname)[1].lower() in AUDIO_EXTS:
                full = os.path.realpath(os.path.join(root, fname))
                rel = os.path.relpath(full, VOICES_DIR).replace("\\", "/")
                results.append({
                    "name": rel,
                    "path": full,
                    "size_bytes": os.path.getsize(full),
                    "url": f"/api/voices/audio/{rel}",
                })
    return results


@router.get("/voices")
async def list_voices():
    return _scan_voices()


@router.post("/voices", status_code=201)
async def upload_voice(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in AUDIO_EXTS:
        raise HTTPException(status_code=422, detail=f"Unsupported audio format: {ext}")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    dest = os.path.realpath(os.path.join(UPLOAD_DIR, file.filename or f"voice{ext}"))
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    rel = os.path.relpath(dest, VOICES_DIR).replace("\\", "/")
    return {
        "name": rel,
        "path": dest,
        "size_bytes": os.path.getsize(dest),
        "url": f"/api/voices/audio/{rel}",
    }


@router.get("/voices/transcript/{name:path}")
async def get_voice_transcript(name: str):
    full = os.path.normpath(os.path.join(VOICES_DIR, name))
    if not full.startswith(os.path.normpath(VOICES_DIR)):
        raise HTTPException(status_code=400, detail="Invalid path")
    sidecar = full + ".transcript.txt"
    if not os.path.isfile(sidecar):
        return {"transcript": ""}
    try:
        with open(sidecar, "r", encoding="utf-8") as f:
            return {"transcript": f.read().strip()}
    except Exception:
        return {"transcript": ""}


@router.post("/voices/transcribe/{name:path}")
async def transcribe_voice(name: str):
    """Run faster-whisper on the voice file and cache the result as a sidecar
    <voice>.transcript.txt next to the audio file.  Returns the transcript."""
    full = os.path.normpath(os.path.join(VOICES_DIR, name))
    if not full.startswith(os.path.normpath(VOICES_DIR)):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not os.path.isfile(full):
        raise HTTPException(status_code=404, detail="Voice file not found")

    # Return cached sidecar immediately if it already exists.
    sidecar = full + ".transcript.txt"
    if os.path.isfile(sidecar):
        try:
            with open(sidecar, "r", encoding="utf-8") as f:
                return {"transcript": f.read().strip()}
        except Exception:
            pass  # Fall through to re-transcribe if the sidecar is unreadable.

    try:
        import torch
        from faster_whisper import WhisperModel
    except ImportError:
        raise HTTPException(status_code=501, detail="faster-whisper is not installed")

    try:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = "float16" if device == "cuda" else "int8"
        model = WhisperModel("small", device=device, compute_type=compute_type)
        segments, _ = model.transcribe(full, beam_size=5)
        transcript = " ".join(seg.text.strip() for seg in segments).strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}")

    # Cache sidecar so the engine can use it later without re-running whisper.
    try:
        with open(sidecar, "w", encoding="utf-8") as f:
            f.write(transcript)
    except Exception:
        pass  # Non-fatal — return transcript even if caching fails.

    return {"transcript": transcript}


@router.delete("/voices/{name:path}")
async def delete_voice(name: str):
    full = os.path.normpath(os.path.join(VOICES_DIR, name))
    # Guard against path traversal
    if not full.startswith(os.path.normpath(VOICES_DIR)):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not os.path.isfile(full):
        raise HTTPException(status_code=404, detail="Voice file not found")
    os.unlink(full)
    return {"deleted": name}


@router.get("/voices/audio/{name:path}")
async def stream_voice(name: str):
    from fastapi.responses import FileResponse
    full = os.path.normpath(os.path.join(VOICES_DIR, name))
    if not full.startswith(os.path.normpath(VOICES_DIR)):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not os.path.isfile(full):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(full)
