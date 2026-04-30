import sys
import os

# lib/conf.py opens VERSION.txt relative to cwd — must be repo root
_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
_BACKEND = os.path.normpath(os.path.dirname(__file__))
os.chdir(_ROOT)
# Repo root (for lib.*) and backend dir (for routers.*) both on path
for _p in (_ROOT, _BACKEND):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import lib.core as _core


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize the session context (multiprocessing Manager) exactly as app.py does
    if _core.context is None:
        _core.context = _core.SessionContext()
    if _core.context_tracker is None:
        _core.context_tracker = _core.SessionTracker()
    if _core.active_sessions is None:
        _core.active_sessions = set()
    # Recover any sessions that were alive before a restart
    from routers.sessions import recover_sessions_from_disk
    recover_sessions_from_disk()
    yield
    # Shutdown: nothing to explicitly clean up


from routers import sessions, voices, library, preview, engines

app = FastAPI(title="ebook2audiobook API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router, prefix="/api")
app.include_router(voices.router, prefix="/api")
app.include_router(library.router, prefix="/api")
app.include_router(preview.router, prefix="/api")
app.include_router(engines.router, prefix="/api")

# Serve built frontend if it exists
_frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(_frontend_dist):
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="frontend")
