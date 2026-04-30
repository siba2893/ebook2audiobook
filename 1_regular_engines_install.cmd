@echo off
REM ===========================================================================
REM 1_regular_engines_install.cmd
REM
REM Installs the "regular" 9-engine profile on top of the base install:
REM   XTTSv2, Bark, Tortoise, VITS, Fairseq, GlowTTS, Tacotron2, YourTTS,
REM   Fish Speech 1.5.  CosyVoice 3 / Qwen3-TTS are NOT supported in this
REM   profile (their required torch versions / package sets conflict).
REM
REM Prerequisite: run base_installation.cmd first.  This script only
REM uninstalls the cross-profile / engine-specific packages and replaces
REM them with the regular profile's set, so it's safe to run when switching
REM from CosyVoice or Qwen3-TTS.
REM
REM After this script, the WebUI engine dropdown shows the 9 regular engines.
REM ===========================================================================
setlocal
cd /d %~dp0

set PY=%~dp0python_env\python.exe
if not exist "%PY%" (
    echo [ERROR] python_env\python.exe not found at %PY%
    exit /b 1
)

echo === [1/4] Removing cross-profile engine packages ===
REM Uninstall packages that the cosyvoice / qwen3tts profiles install, plus
REM the torch trio (we'll reinstall the right cu128 build below).  -y avoids
REM prompts; missing packages emit a benign warning we suppress.
"%PY%" -m pip uninstall -y torch torchaudio torchvision torchcodec ^
    transformers accelerate qwen-tts flash-attn faster-whisper ^
    coqui-tts fish_speech pyannote-audio gruut demucs torchvggish ^
    conformer diffusers hyperpyyaml hydra-core onnxruntime onnxruntime-gpu ^
    deepspeed ormsgpack descript-audio-codec einops 2>nul
if errorlevel 1 (
    echo [WARN] pip uninstall reported errors; continuing.
)

echo === [2/4] Installing torch 2.7.1+cu128 trio ===
"%PY%" -m pip install --no-cache-dir torch==2.7.1 torchaudio==2.7.1 torchvision==0.22.1 ^
    --index-url https://download.pytorch.org/whl/cu128 || goto :err

echo === [3/4] Installing engine-specific packages ===
"%PY%" -m pip install --no-cache-dir ^
    "transformers==4.57.6" "coqui-tts[languages]==0.27.5" ^
    torchvggish torchcodec gruut ^
    ormsgpack descript-audio-codec "einops>=0.7.0" || goto :err
REM pyannote-audio>=4.0 declares lightning>=2.4 which has no Py3.12 wheel on
REM PyPI.  --no-deps is safe: runtime shims live in
REM lib/classes/background_detector.py (pyannote_patch).
"%PY%" -m pip install --no-cache-dir --no-deps "pyannote-audio>=4.0.0" || goto :err
REM fish-speech declares lightning>=2.1.0 which also has no Py3.12 wheel.
REM Our engine only uses fish-speech's inference path; full deps satisfied above.
"%PY%" -m pip install --no-cache-dir --no-deps "git+https://github.com/fishaudio/fish-speech.git@v1.5.1" || goto :err
"%PY%" -m pip install --no-cache-dir ext/py/demucs || goto :err

echo === [4/4] Setting active engine profile ===
type nul > .project-root
> .engine-mode echo regular

echo.
echo === Done ===
echo   Active profile: regular ^(9 engines^)
echo   Run start_webui.cmd to launch.
exit /b 0

:err
echo.
echo [ERROR] Install step failed.  See output above.
exit /b 1
