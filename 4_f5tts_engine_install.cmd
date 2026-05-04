@echo off
REM ===========================================================================
REM 4_f5tts_engine_install.cmd
REM
REM Installs the "f5tts" profile on top of the base install.
REM Uses torch 2.7.1+cu128 with the f5-tts PyPI package.  The 9 regular
REM engines, CosyVoice 3, and Qwen3-TTS are NOT supported in this profile —
REM f5-tts pulls a transformers version we do not pin and bundles bloat
REM (gradio, wandb, datasets, bitsandbytes) we keep isolated to this profile.
REM
REM Model weights (~1.5 GB) are downloaded automatically from HuggingFace on
REM first inference: SWivid/F5-TTS (F5TTS_v1_Base + Vocos vocoder).
REM Languages: English + Chinese (out of the box).  Code: MIT.
REM Weights: CC-BY-NC (non-commercial — see AGENTS.md "License notes").
REM Requirements: ~3 GB VRAM (DiT 335M params).
REM
REM Prerequisite: run base_installation.cmd first.
REM
REM After this script, the WebUI engine dropdown shows ONLY F5-TTS.
REM Switch to other profiles with 1_regular_engines_install.cmd,
REM 2_cosy_voice_engine_install.cmd, or 3_qwen3tts_engine_install.cmd.
REM ===========================================================================
setlocal
cd /d %~dp0

set PY=%~dp0python_env\python.exe
if not exist "%PY%" (
    echo [ERROR] python_env\python.exe not found at %PY%
    exit /b 1
)

echo === [1/4] Removing cross-profile engine packages ===
"%PY%" -m pip uninstall -y torch torchaudio torchvision torchcodec ^
    transformers accelerate qwen-tts faster-qwen3-tts flash-attn ^
    coqui-tts fish_speech pyannote-audio gruut demucs torchvggish ^
    conformer diffusers hyperpyyaml hydra-core onnxruntime onnxruntime-gpu ^
    deepspeed ormsgpack descript-audio-codec einops 2>nul
if errorlevel 1 (
    echo [WARN] pip uninstall reported errors; continuing.
)

echo === [2/4] Installing torch 2.7.1+cu128 trio ===
"%PY%" -m pip install --no-cache-dir torch==2.7.1 torchaudio==2.7.1 torchvision==0.22.1 ^
    --index-url https://download.pytorch.org/whl/cu128 || goto :err

echo === [3/5] Installing f5-tts ===
REM f5-tts pulls vocos, x_transformers, torchdiffeq, ema_pytorch, hydra-core,
REM transformers, accelerate, plus heavyweight optional deps (gradio, wandb,
REM datasets, bitsandbytes).  We accept the full install in this profile —
REM isolating them here keeps the regular profile lean.
"%PY%" -m pip install --no-cache-dir -U f5-tts || goto :err

echo === [4/5] Removing torchcodec (incompatible with torch 2.7) ===
REM transformers >= 5.x pulls torchcodec as a transitive dep, but the only
REM Windows wheels available (0.7+) are ABI-locked to torch >= 2.8 and the
REM DLL fails to load with our torch 2.7.1.  F5-TTS doesn't import torchcodec
REM at runtime; transformers' ASR pipeline falls back to soundfile, which is
REM enough for the whisper-large-v3-turbo path.
"%PY%" -m pip uninstall -y torchcodec 2>nul

echo === [5/5] Setting active engine profile ===
type nul > .project-root
> .engine-mode echo f5tts

echo.
echo === Done ===
echo   Active profile: f5tts ^(F5-TTS only^)
echo   Model weights will download on first inference ^(~1.5 GB^).
echo   Run start_webui.cmd to launch.
exit /b 0

:err
echo.
echo [ERROR] Install step failed.  See output above.
exit /b 1
