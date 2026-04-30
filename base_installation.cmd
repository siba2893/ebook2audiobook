@echo off
REM ===========================================================================
REM base_installation.cmd
REM
REM Step 1 of the install flow.  Wipes python_env/ pip packages and installs
REM the engine-agnostic base — everything that does NOT depend on a specific
REM PyTorch version.  At the end, prompts you to pick one of the three engine
REM profiles to install on top.
REM
REM Profiles (run individually after base, or pick one at the prompt below):
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

if not exist tmp\nul mkdir tmp

echo === [1/3] Wiping python_env packages ===
"%PY%" -m pip freeze > tmp\pip_freeze_before.txt
findstr /V /B /C:"pip==" /C:"setuptools==" /C:"wheel==" tmp\pip_freeze_before.txt > tmp\pip_to_uninstall.txt
"%PY%" -m pip uninstall -y -r tmp\pip_to_uninstall.txt
if errorlevel 1 (
    echo [WARN] pip uninstall reported errors; continuing.
)

echo === [2/3] Installing engine-agnostic base packages ===
REM Pure-Python or near-pure-Python deps from requirements.txt that DO NOT
REM depend on a specific torch version.  Each engine profile installs its
REM own torch + engine-specific libs on top of this.
"%PY%" -m pip install --no-cache-dir ^
    cryptography py-cpuinfo tqdm regex docker ebooklib python-pptx python-docx ^
    fastapi "uvicorn[standard]" hf_xet beautifulsoup4 nagisa pymupdf pymupdf-layout ^
    pytesseract unidic hangul-romanize iso639-lang soynlp jieba pycantonese ^
    pypinyin pythainlp mutagen PyOpenGL phonemizer-fork pydub unidecode langdetect ^
    phonemizer indic-nlp-library "stanza==1.10.1" "argostranslate==1.11.0" ^
    "pandas>=1.0,<4.0" "gradio>=5.49.1" "huggingface_hub>=0.36.2" basedpyright ^
    requests soundfile || goto :err
"%PY%" -m pip install --no-cache-dir ext/py/num2words || goto :err

echo === [3/3] Resetting marker files ===
type nul > .project-root
> .engine-mode echo none

echo.
echo ===========================================================================
echo   Base install complete.
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

:err
echo.
echo [ERROR] base install step failed.  See output above.
exit /b 1
