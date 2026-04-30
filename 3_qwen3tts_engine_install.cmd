@echo off
REM ===========================================================================
REM 3_qwen3tts_engine_install.cmd
REM
REM Wipes python_env/ pip packages and installs the "qwen3tts" profile.
REM Uses torch 2.7.1+cu128 with qwen-tts (transformers 4.57.3, accelerate
REM 1.12.0). The other 9 regular engines are NOT included in this profile.
REM
REM Model weights (~3 GB) are downloaded automatically from HuggingFace on
REM first inference: Qwen/Qwen3-TTS-12Hz-1.7B-Base
REM
REM Requirements: ~6 GB VRAM (bfloat16), CUDA 11.8+.
REM
REM After this script, the WebUI engine dropdown shows ONLY Qwen3-TTS.
REM To switch back to the regular engines, run 1_regular_engines_install.cmd.
REM To switch to CosyVoice, run 2_cosy_voice_engine_install.cmd.
REM ===========================================================================
setlocal
cd /d %~dp0

set PY=%~dp0python_env\python.exe
if not exist "%PY%" (
    echo [ERROR] python_env\python.exe not found at %PY%
    echo         Bootstrap python_env first ^(conda or installer^).
    exit /b 1
)

if not exist tmp\nul mkdir tmp

echo === [1/5] Snapshotting current packages and uninstalling ===
"%PY%" -m pip freeze > tmp\pip_freeze_before.txt
findstr /V /B /C:"pip==" /C:"setuptools==" /C:"wheel==" tmp\pip_freeze_before.txt > tmp\pip_to_uninstall.txt
"%PY%" -m pip uninstall -y -r tmp\pip_to_uninstall.txt
if errorlevel 1 (
    echo [WARN] pip uninstall reported errors; continuing.
)

echo === [2/5] Installing torch 2.7.1+cu128 ===
"%PY%" -m pip install --no-cache-dir torch==2.7.1 torchaudio==2.7.1 torchvision==0.22.1 --index-url https://download.pytorch.org/whl/cu128 || goto :err

echo === [3/5] Installing project requirements ===
"%PY%" -m pip install --no-cache-dir -r requirements.txt || goto :err

echo === [4/5] Installing qwen-tts ===
"%PY%" -m pip install --no-cache-dir -U qwen-tts || goto :err

echo === [5/5] Setting active engine profile ===
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
