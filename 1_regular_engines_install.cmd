@echo off
REM ===========================================================================
REM 1_regular_engines_install.cmd
REM
REM Wipes python_env/ pip packages and installs the "regular" 9-engine
REM profile: XTTSv2, Bark, Tortoise, VITS, Fairseq, GlowTTS, Tacotron2,
REM YourTTS, Fish Speech 1.5.  CosyVoice 3 is NOT supported in this profile
REM (its required torch version conflicts with the rest).
REM
REM After this script, the WebUI engine dropdown shows the 9 regular engines.
REM To switch to CosyVoice-only, run 2_cosy_voice_engine_install.cmd.
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

echo === [2/5] Installing matched torch trio ^(2.7.1+cu128^) ===
"%PY%" -m pip install --no-cache-dir torch==2.7.1 torchaudio==2.7.1 torchvision==0.22.1 --index-url https://download.pytorch.org/whl/cu128 || goto :err

echo === [3/5] Installing project requirements ===
"%PY%" -m pip install --no-cache-dir -r requirements.txt || goto :err

echo === [4/5] Installing extras ^(fish_speech, gruut, torchcodec, iso639-lang^) ===
"%PY%" -m pip install --no-cache-dir torchcodec gruut iso639-lang || goto :err
"%PY%" -m pip install --no-cache-dir "git+https://github.com/fishaudio/fish-speech.git@v1.5.1" || goto :err

echo === [5/5] Setting active engine profile ===
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
