@echo off
REM ===========================================================================
REM 5_qwen_fast_install.cmd
REM
REM Installs the "qwen_fast" profile on top of the base install.  Same model
REM weights as profile 3 (Qwen/Qwen3-TTS-12Hz-1.7B-Base) but routed through
REM the faster-qwen3-tts PyPI fork (CUDA Graphs + static KV cache).  The
REM upstream qwen-tts package is still installed because the fork imports
REM types and prompt-builder logic from it.
REM
REM Profile 3 (qwen3tts) and profile 5 (qwen_fast) cannot coexist in the
REM same env — they share the torch trio and transformers pin but install
REM different inference packages.  Switch profiles by running the relevant
REM install script; it uninstalls the other side first.
REM
REM Tradeoffs vs profile 3:
REM   + ~5-10x faster inference once CUDA graphs are captured.
REM   - First-call latency: graph capture takes a few seconds on cold start.
REM   - Sub-talker sampling kwargs (subtalker_temperature/top_p/top_k) are
REM     ignored on this backend — talker-level drift control is preserved.
REM
REM Requirements: ~6 GB VRAM (bfloat16) + 1-2 GB headroom for graph buffers.
REM On an 8 GB card, lower max_seq_len via session['qwen3tts_max_seq_len']
REM if you hit OOM during capture.
REM
REM Prerequisite: run base_installation.cmd first.
REM ===========================================================================
setlocal
cd /d %~dp0

set PY=%~dp0python_env\python.exe
if not exist "%PY%" (
    echo [ERROR] python_env\python.exe not found at %PY%
    exit /b 1
)

echo === [1/5] Removing cross-profile engine packages ===
REM Same uninstall list as profile 3 — we reinstall qwen-tts in step 3
REM because faster-qwen3-tts imports from it.
"%PY%" -m pip uninstall -y torch torchaudio torchvision torchcodec ^
    transformers accelerate ^
    coqui-tts fish_speech pyannote-audio gruut demucs torchvggish ^
    conformer diffusers hyperpyyaml hydra-core onnxruntime onnxruntime-gpu ^
    deepspeed ormsgpack descript-audio-codec einops ^
    f5-tts vocos x_transformers torchdiffeq ema_pytorch cached_path ^
    transformers_stream_generator pypinyin rjieba ^
    gradio wandb datasets bitsandbytes 2>nul
if errorlevel 1 (
    echo [WARN] pip uninstall reported errors; continuing.
)

echo === [2/5] Installing torch 2.7.1+cu128 trio ===
"%PY%" -m pip install --no-cache-dir torch==2.7.1 torchaudio==2.7.1 torchvision==0.22.1 ^
    --index-url https://download.pytorch.org/whl/cu128 || goto :err

echo === [3/5] Installing qwen-tts + faster-qwen3-tts + faster-whisper ===
REM qwen-tts provides the model classes and create_voice_clone_prompt that
REM faster-qwen3-tts wraps.  Install it first so faster-qwen3-tts pip-resolves
REM against the already-present version rather than its own pinned default.
"%PY%" -m pip install --no-cache-dir -U qwen-tts || goto :err
"%PY%" -m pip install --no-cache-dir -U faster-qwen3-tts || goto :err
REM faster-whisper auto-transcribes reference voice WAVs into ref_text for
REM full-fidelity ICL voice cloning.  Sidecar <voice>.transcript.txt cache.
"%PY%" -m pip install --no-cache-dir faster-whisper || goto :err

echo === [4/5] Installing flash-attn 2.7.4 ^(Windows wheel for cp312 + cu128 + torch 2.7^) ===
REM PyPI ships flash-attn for Linux only; this Windows wheel comes from
REM the lldacing prebuild repo and matches our exact env (cp312 +
REM torch 2.7 + cu128 + cxx11abiFALSE).  flash-attn is required for the
REM 'flash_attention_2' attn_implementation we pass to FasterQwen3TTS;
REM without it, the model falls back to SDPA (still works, slower).
"%PY%" -m pip install --no-cache-dir "https://huggingface.co/lldacing/flash-attention-windows-wheel/resolve/main/flash_attn-2.7.4.post1%%2Bcu128torch2.7.0cxx11abiFALSE-cp312-cp312-win_amd64.whl"
if errorlevel 1 (
    echo [WARN] flash-attn install failed — qwen_fast will fall back to SDPA ^(slower but functional^).
)

echo === [5/5] Setting active engine profile ===
type nul > .project-root
> .engine-mode echo qwen_fast

echo.
echo === Done ===
echo   Active profile: qwen_fast ^(Qwen3-TTS via faster-qwen3-tts CUDA-graph fork^)
echo   Model weights will download on first inference ^(~3 GB, shared with profile 3^).
echo   Run start_webui.cmd to launch.
exit /b 0

:err
echo.
echo [ERROR] Install step failed.  See output above.
exit /b 1
