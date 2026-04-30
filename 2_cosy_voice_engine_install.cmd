@echo off
REM ===========================================================================
REM 2_cosy_voice_engine_install.cmd
REM
REM Wipes python_env/ pip packages and installs the "cosyvoice" profile.
REM Uses torch 2.3.1+cu121 — the version CosyVoice 3 was developed and tested
REM against.  The other 9 engines are NOT supported in this profile (their
REM tooling expects newer torch + cu128).
REM
REM After this script, the WebUI engine dropdown shows ONLY CosyVoice 3.
REM To switch back to the regular engines, run 1_regular_engines_install.cmd.
REM
REM Prerequisite: third_party/CosyVoice/ must already be cloned with its
REM Matcha-TTS submodule (git submodule update --init --recursive).
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

if not exist tmp\nul mkdir tmp

echo === [1/4] Snapshotting current packages and uninstalling ===
"%PY%" -m pip freeze > tmp\pip_freeze_before.txt
findstr /V /B /C:"pip==" /C:"setuptools==" /C:"wheel==" tmp\pip_freeze_before.txt > tmp\pip_to_uninstall.txt
"%PY%" -m pip uninstall -y -r tmp\pip_to_uninstall.txt
if errorlevel 1 (
    echo [WARN] pip uninstall reported errors; continuing.
)

echo === [2/4] Installing torch 2.3.1+cu121 ^(CosyVoice's tested baseline^) ===
"%PY%" -m pip install --no-cache-dir torch==2.3.1 torchaudio==2.3.1 torchvision==0.18.1 --index-url https://download.pytorch.org/whl/cu121 || goto :err

echo === [3/4] Installing CosyVoice requirements ===
"%PY%" -m pip install --no-cache-dir -r third_party\CosyVoice\requirements.txt || goto :err
REM hyperpyyaml is needed by cosyvoice.cli but not always pulled by the txt
"%PY%" -m pip install --no-cache-dir hyperpyyaml || goto :err
REM Project also needs these regardless of profile
"%PY%" -m pip install --no-cache-dir cryptography fastapi uvicorn requests iso639-lang regex tqdm beautifulsoup4 pymupdf mutagen ebooklib || goto :err

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
