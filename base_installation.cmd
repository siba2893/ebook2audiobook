@echo off
REM ===========================================================================
REM base_installation.cmd
REM
REM Step 1 of the install flow.  Installs the engine-agnostic base —
REM everything that does NOT depend on a specific PyTorch version.
REM
REM Idempotent by default: re-running this script just verifies that the
REM expected packages are installed and skips pip work if they are.
REM Use `base_installation.cmd --force` to wipe python_env/ pip packages
REM and do a full clean reinstall.
REM
REM At the end, prompts you to pick one of the three engine profiles to
REM install on top.  Run individually later if you skip the prompt:
REM   1_regular_engines_install.cmd      ->  XTTS, Bark, Tortoise, VITS,
REM                                          Fairseq, GlowTTS, Tacotron2,
REM                                          YourTTS, Fish Speech 1.5
REM   2_cosy_voice_engine_install.cmd    ->  CosyVoice 3 only
REM   3_qwen3tts_engine_install.cmd      ->  Qwen3-TTS only
REM ===========================================================================
setlocal
cd /d %~dp0

set PY=%~dp0python_env\python.exe
if not exist "%PY%" (
    echo [ERROR] python_env\python.exe not found at %PY%
    echo         Bootstrap python_env first ^(conda or installer^).
    exit /b 1
)

REM Forward --force to the Python helper.
set FORCE_FLAG=
if /I "%~1"=="--force" set FORCE_FLAG=--force
if /I "%~1"=="-f" set FORCE_FLAG=--force

echo === [1/2] Checking / installing engine-agnostic base packages ===
"%PY%" tools\base_install.py %FORCE_FLAG%
if errorlevel 1 (
    echo [ERROR] base install failed.  See output above.
    exit /b 1
)

echo === [2/2] Resetting marker files ===
type nul > .project-root
> .engine-mode echo none

echo.
echo ===========================================================================
echo   Base install ready.
echo ===========================================================================
echo.
echo   Pick an engine profile to install on top of base:
echo.
echo     [1] Regular engines    (XTTS, Bark, Tortoise, VITS, Fairseq,
echo                             GlowTTS, Tacotron2, YourTTS, Fish Speech 1.5)
echo     [2] CosyVoice 3        (zero-shot voice clone, Apache 2.0)
echo     [3] Qwen3-TTS          (zero-shot voice clone)
echo     [Q] Quit               (skip engine install for now)
echo.

:prompt
set CHOICE=
set /p CHOICE="Enter choice [1/2/3/Q]: "
if /I "%CHOICE%"=="1" goto :run_regular
if /I "%CHOICE%"=="2" goto :run_cosyvoice
if /I "%CHOICE%"=="3" goto :run_qwen3tts
if /I "%CHOICE%"=="Q" goto :skip
echo Invalid choice "%CHOICE%". Type 1, 2, 3, or Q.
goto :prompt

:run_regular
call "%~dp01_regular_engines_install.cmd"
exit /b %ERRORLEVEL%

:run_cosyvoice
call "%~dp02_cosy_voice_engine_install.cmd"
exit /b %ERRORLEVEL%

:run_qwen3tts
call "%~dp03_qwen3tts_engine_install.cmd"
exit /b %ERRORLEVEL%

:skip
echo.
echo Skipped engine install.  Run one of these whenever ready:
echo   1_regular_engines_install.cmd
echo   2_cosy_voice_engine_install.cmd
echo   3_qwen3tts_engine_install.cmd
exit /b 0
