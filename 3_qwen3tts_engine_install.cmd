@echo off
REM ===========================================================================
REM 3_qwen3tts_engine_install.cmd
REM
REM Installs the "qwen3tts" profile on top of the base install.
REM Uses torch 2.7.1+cu128 with qwen-tts (which pulls transformers / accelerate
REM at the versions it pins).  The 9 regular engines and CosyVoice 3 are NOT
REM supported in this profile.
REM
REM Model weights (~3 GB) are downloaded automatically from HuggingFace on
REM first inference: Qwen/Qwen3-TTS-12Hz-1.7B-Base.
REM Requirements: ~6 GB VRAM (bfloat16), CUDA 11.8+.
REM
REM Prerequisite: run base_installation.cmd first.
REM
REM After this script, the WebUI engine dropdown shows ONLY Qwen3-TTS.
REM Switch to other profiles with 1_regular_engines_install.cmd or
REM 2_cosy_voice_engine_install.cmd.
REM ===========================================================================
setlocal
cd /d %~dp0

set PY=%~dp0python_env\python.exe
if not exist "%PY%" (
    echo [ERROR] python_env\python.exe not found at %PY%
    exit /b 1
)

echo === [1/4] Removing cross-profile engine packages ===
REM Uninstall packages that the regular / cosyvoice profiles install, plus
REM the torch trio (we'll reinstall cu128 below).  qwen-tts will pull the
REM transformers/accelerate versions it needs in step 3.
"%PY%" -m pip uninstall -y torch torchaudio torchvision torchcodec ^
    transformers accelerate ^
    coqui-tts fish_speech pyannote-audio gruut demucs torchvggish ^
    conformer diffusers hyperpyyaml hydra-core onnxruntime onnxruntime-gpu ^
    deepspeed ormsgpack descript-audio-codec einops 2>nul
if errorlevel 1 (
    echo [WARN] pip uninstall reported errors; continuing.
)

echo === [2/4] Installing torch 2.7.1+cu128 trio ===
"%PY%" -m pip install --no-cache-dir torch==2.7.1 torchaudio==2.7.1 torchvision==0.22.1 ^
    --index-url https://download.pytorch.org/whl/cu128 || goto :err

echo === [3/4] Installing qwen-tts ===
"%PY%" -m pip install --no-cache-dir -U qwen-tts || goto :err

echo === [4/4] Setting active engine profile ===
type nul > .project-root
> .engine-mode echo qwen3tts

echo.
echo === Done ===
echo   Active profile: qwen3tts ^(Qwen3-TTS only^)
echo   Model weights will download on first inference ^(~3 GB^).
echo   Run start_webui.cmd to launch.
exit /b 0

:err
echo.
echo [ERROR] Install step failed.  See output above.
exit /b 1
