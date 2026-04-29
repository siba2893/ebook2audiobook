## Problem

On Windows, if a conversion is interrupted (power cut, OS shutdown, session expiry), restarting and resuming always re-renders from block 0 — even when most chapter `.flac` files already exist in the `chapters/` temp folder.

Two root causes:

1. **`blocks_saved` JSON is never written on a fresh run** — it is only saved after a fully clean conversion completes. On resume, `block_ref` is always `None`, so `hash_ref` is always `None`, so `block_changed = True` for every block, and every chapter reconverts regardless.

2. **Skip logic was gated on `x < block_resume`** — even when `block_changed=False`, blocks with index >= `block_resume` were never checked for an existing chapter `.flac`, so they were always re-rendered.

Additionally, on Windows the `sentences/` temp folder (individual per-sentence audio files) gets cleaned up by the OS on hard shutdown, while the combined `chapters/*.flac` files survive. The old code only checked for sentence files, so every chapter appeared incomplete.

## Fix

- **`_check_block_sentences`**: returns empty set (no missing sentences) immediately if the combined chapter `.flac` already exists — handles the case where sentence temp files were wiped by a hard shutdown but the chapter audio survived.

- **`convert_chapters2audio` resume logic**: when `block_changed=False`, check for an existing chapter `.flac` first and skip the block entirely, regardless of `block_resume` index. This means any chapter that was fully rendered in a previous run is never re-rendered, even if `block_resume` points to an earlier block.

- **`utils.py`**: force `amp_dtype = torch.float16` for Ampere GPUs (CC >= 8) on Windows to fix `Got unsupported ScalarType BFloat16` / CUDA to numpy crash on RTX 30xx/40xx series.

## Testing

Verified on Windows 11 + RTX 4060 (CUDA) converting a 13,153-sentence Spanish epub with XTTSv2. After a hard power cut at ~90% completion:
- All 27 completed chapter `.flac` files were correctly skipped on resume
- Conversion resumed from the interrupted chapter without re-rendering anything
- Final audiobook output was correct
