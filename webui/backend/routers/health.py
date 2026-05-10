"""Dependency health checks — torch, CUDA, faster-whisper, engine mode."""
import os
import sys

from fastapi import APIRouter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

router = APIRouter()


@router.get("/health")
async def health():
    result: dict = {}

    # torch + CUDA
    try:
        import torch
        result["torch"] = True
        result["cuda"] = torch.cuda.is_available()
        if result["cuda"]:
            try:
                free, total = torch.cuda.mem_get_info()
                result["vram_free_gb"] = round(free / (1024 ** 3), 1)
                result["vram_total_gb"] = round(total / (1024 ** 3), 1)
            except Exception:
                result["vram_free_gb"] = 0.0
                result["vram_total_gb"] = 0.0
        else:
            result["vram_free_gb"] = 0.0
            result["vram_total_gb"] = 0.0
    except ImportError:
        result["torch"] = False
        result["cuda"] = False
        result["vram_free_gb"] = 0.0
        result["vram_total_gb"] = 0.0

    # faster-whisper
    try:
        import faster_whisper  # noqa: F401
        result["faster_whisper"] = True
    except ImportError:
        result["faster_whisper"] = False

    # active engine profile
    from routers.engines import _read_mode
    result["engine_mode"] = _read_mode()

    return result
