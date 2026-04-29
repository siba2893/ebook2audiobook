@echo off
REM Start ebook2audiobook FastAPI backend on port 8000
cd /d C:\ebook2audiobook
C:\ebook2audiobook\python_env\python.exe -m uvicorn webui.backend.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir webui\backend
