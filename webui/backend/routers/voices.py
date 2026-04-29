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
