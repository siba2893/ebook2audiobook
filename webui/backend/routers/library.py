"""
Library: list completed audiobooks, in-progress sessions, and serve downloads.
"""
import os
import sys

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

router = APIRouter()

AUDIOBOOKS_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "audiobooks"))
AUDIO_EXTS = {".m4b", ".mp3", ".opus", ".flac"}


def _scan_library():
    results = []
    if not os.path.isdir(AUDIOBOOKS_DIR):
        return results
    for root, _dirs, files in os.walk(AUDIOBOOKS_DIR):
        for fname in sorted(files):
            if os.path.splitext(fname)[1].lower() not in AUDIO_EXTS:
                continue
            full = os.path.realpath(os.path.join(root, fname))
            rel = os.path.relpath(full, AUDIOBOOKS_DIR).replace("\\", "/")
            import datetime
            mtime = os.path.getmtime(full)
            created_at = datetime.datetime.fromtimestamp(mtime, tz=datetime.timezone.utc).isoformat()
            results.append({
                "filename": fname,
                "rel_path": rel,
                "size_bytes": os.path.getsize(full),
                "url": f"/api/library/file/{rel}",
                "created_at": created_at,
            })
    results.sort(key=lambda e: e.get("created_at", ""), reverse=True)
    return results


@router.get("/library")
async def list_library():
    return _scan_library()


@router.get("/library/sessions")
async def list_library_sessions():
    """
    Return all persisted sessions enriched with chapter-completion counts.
    Excludes sessions whose ebook source file no longer exists (orphaned).
    """
    from webui.backend.session_store import all_sessions as _all_sessions
    from webui.backend.routers.sessions import _session_status
    from fastapi import HTTPException as _HTTPException

    results = []
    for meta in _all_sessions():
        sid = meta.get("session_id")
        if not sid:
            continue
        # Try live status first, fall back to persisted metadata
        try:
            live = _session_status(sid)
        except _HTTPException:
            live = None

        status = (live or {}).get("status") or _map_raw_status(meta.get("status"))
        block_resume = (live or {}).get("block_resume", 0)
        blocks_total = (live or {}).get("blocks_total", 0)
        filename = (
            (live or {}).get("filename")
            or meta.get("filename_noext")
            or meta.get("filename")
            or os.path.basename(str(meta.get("ebook_src") or ""))
            or sid
        )

        # Count completed chapters from chapters dir if available
        if block_resume == 0 and meta.get("process_dir"):
            chapters_dir = os.path.join(meta["process_dir"], "chapters")
            if os.path.isdir(chapters_dir):
                block_resume = sum(
                    1 for f in os.listdir(chapters_dir)
                    if os.path.splitext(f)[1].lower() == ".flac"
                    and not f.startswith(".")
                )

        results.append({
            "session_id": sid,
            "filename": filename,
            "status": status,
            "block_resume": block_resume,
            "blocks_total": blocks_total,
            "audiobook_path": (live or {}).get("audiobook_path") or meta.get("audiobook"),
            "created_at": meta.get("created_at"),
        })

    return results


def _map_raw_status(raw: str | None) -> str:
    mapping = {
        "ready": "ready",
        "edit": "edit",
        "converting": "converting",
        "end": "done",
        "disconnected": "interrupted",
    }
    return mapping.get(str(raw or "").lower(), str(raw or "ready"))


@router.get("/library/file/{rel_path:path}")
async def download_audiobook(rel_path: str):
    full = os.path.realpath(os.path.join(AUDIOBOOKS_DIR, rel_path))
    if not full.startswith(AUDIOBOOKS_DIR):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not os.path.isfile(full):
        raise HTTPException(status_code=404, detail="File not found")
    fname = os.path.basename(full)
    return FileResponse(
        full,
        filename=fname,
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
