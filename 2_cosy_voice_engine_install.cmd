@echo off
REM ===========================================================================
REM 2_cosy_voice_engine_install.cmd
REM
REM Installs the "cosyvoice" profile on top of the base install.
REM Uses torch 2.3.1+cu121 — the version CosyVoice 3 was developed and tested
REM against.  The 9 regular engines and Qwen3-TTS are NOT supported in this
REM profile (their tooling expects newer torch + cu128).
REM
REM Prerequisite 1: run base_installation.cmd first.
REM Prerequisite 2: third_party/CosyVoice/ must already be cloned with its
REM Matcha-TTS submodule (git submodule update --init --recursive).
REM
REM After this script, the WebUI engine dropdown shows ONLY CosyVoice 3.
REM Switch to other profiles with 1_regular_engines_install.cmd or
REM 3_qwen3tts_engine_install.cmd.
REM ===========================================================================
setlocal
cd /d %~dp0

set PY=%~dp0python_env\python.exe
if not exist "%PY%" (
    echo [ERROR] python_env\python.exe not found at %PY%
    exit /b 1
)
if not exist third_party\CosyVoice\cosyvoice\cli\cosyvoice.py (
    echo [ERROR] third_party\CosyVoice not cloned.
    echo         Run: git clone --recursive https://github.com/FunAudioLLM/CosyVoice third_party\CosyVoice
    exit /b 1
)

echo === [1/4] Removing cross-profile engine packages ===
REM Uninstall packages that the regular / qwen3tts profiles install, plus
REM the torch trio (we'll reinstall cu121 below).  Missing-package warnings
REM are suppressed.
"%PY%" -m pip uninstall -y torch torchaudio torchvision torchcodec ^
    transformers accelerate qwen-tts ^
    coqui-tts fish_speech pyannote-audio gruut demucs torchvggish ^
    ormsgpack descript-audio-codec einops 2>nul
if errorlevel 1 (
    echo [WARN] pip uninstall reported errors; continuing.
)

echo === [2/4] Installing torch 2.3.1+cu121 ^(CosyVoice's tested baseline^) ===
"%PY%" -m pip install --no-cache-dir torch==2.3.1 torchaudio==2.3.1 torchvision==0.18.1 ^
    --index-url https://download.pytorch.org/whl/cu121 || goto :err

echo === [3/4] Installing CosyVoice deps ===
"%PY%" -m pip install --no-cache-dir -r third_party\CosyVoice\requirements.txt || goto :err
REM hyperpyyaml is needed by cosyvoice.cli but not always pulled by the txt
"%PY%" -m pip install --no-cache-dir hyperpyyaml || goto :err

echo === [4/4] Setting active engine profile ===
> .engine-mode echo cosyvoice

echo.
echo === Done ===
echo   Active profile: cosyvoice ^(CosyVoice 3 only^)
echo   Run start_webui.cmd to launch.
exit /b 0

:err
echo.
echo [ERROR] Install step failed.  See output above.
exit /b 1
