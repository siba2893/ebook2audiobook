# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Read AGENTS.md first

`AGENTS.md` is the canonical project guide. It documents the install profiles, every engine's quirks, the load-bearing torch compat shims, performance optimizations guarded by regression tests, and the engineering rules. Do not work in this repo without reading it — every section codifies a decision whose reversal has already cost time once.

## Canonical Python interpreter

Use `python_env/python.exe` for everything (tests, scripts, ad-hoc commands). It is a conda env, not a venv. The system Python is the wrong env — fishspeech, cosyvoice, and the active-profile torch live only in `python_env/`.

```powershell
.\python_env\python.exe tools\test_engines_e2e.py xtts
.\python_env\python.exe tools\test_performance.py
```

## Common commands

| Task | Command |
|---|---|
| Start WebUI (dev) | `start_webui.cmd` — uvicorn `webui.backend.main:app --reload` on `localhost:8000`. Reload only watches `webui/backend/`. |
| Build frontend | `cd webui/frontend && npm run build` — backend serves `dist/`; there is no Vite dev server. **Rebuild after every `src/` edit or your changes will not appear.** |
| Perf regression guards | `python tools\test_performance.py` (17 static-source checks) |
| Per-engine e2e | `.\python_env\python.exe tools\test_engines_e2e.py [engine ...]` — saves WAVs to `tmp/engine_previews/` |
| WebUI session e2e | `python tools\test_webui_e2e.py` (needs `start_webui.cmd` running) |
| Switch install profile | Run one of `1_regular_engines_install.cmd` / `2_cosy_voice_engine_install.cmd` / `3_qwen3tts_engine_install.cmd` / `4_f5tts_engine_install.cmd` / `5_qwen_fast_install.cmd`. Each uninstalls other profiles' packages first. Active profile is recorded in `.engine-mode`. Profile 5 routes Qwen3-TTS through the `faster-qwen3-tts` CUDA-graph fork (~2.6× steady-state speedup, same model weights). |
| Base packages (torch-agnostic) | `base_installation.cmd` (idempotent; `--force` to wipe & reinstall). Package list is in `tools/base_install.py:BASE_PACKAGES`. |

Do **not** run `pip install -r requirements.txt` directly — it pulls the wrong torch for the active profile.

## Architecture in one paragraph

The conversion pipeline is `lib/core.py:convert_chapters2audio()` (sentence loop ~line 2292). It dispatches per-sentence work through `lib/classes/tts_manager.py:TTSManager(session).convert(...)`, which routes to one of eleven engine modules under `lib/classes/tts_engines/<name>.py`. Each engine subclasses `TTSUtils` + `TTSRegistry` from `common/utils.py` and inherits two load-bearing torch-compat shims (`Tensor.__array__` auto-CPU, forced `weights_only=False`) via `common/headers.py` → `common/torch_compat.py`. Engine config defaults live in `lib/conf_models.py:default_engine_settings`; global paths/devices/sample-rates live in `lib/conf.py`. The WebUI under `webui/` is a thin FastAPI shim — `routers/preview.py` exercises the same code path the engine e2e tests do, and `routers/engines.py` reads `.engine-mode` to filter the dropdown to whatever profile is installed. The five install profiles (regular, cosyvoice, qwen3tts, f5tts, qwen_fast) exist because their torch versions / transformers pins / dep bloat don't coexist; switching profiles via the install scripts is safe. `qwen_fast` shares the qwen3tts engine class but constructs `_FasterQwenTtsBackend` automatically based on `.engine-mode` — see `qwen3-fast-integration-plan.md` for the full backend abstraction.

## Hard rules (full rationale in AGENTS.md)

- **Don't remove the compat shims** in `lib/classes/tts_engines/common/torch_compat.py`.
- **Use `is None` checks** (never truthy) on anything that goes through `_load_checkpoint` or `_check_xtts_builtin_speakers` — `OptimizedModule.__bool__` raises.
- **Don't add a torch-dependent package to `requirements.txt`.** It belongs in the per-profile install script.
- **Don't undo the perf optimizations** listed in AGENTS.md "Performance optimizations" — `tools/test_performance.py` will fail with a pointed message if you do.
- **Don't write narrating WHAT-comments.** Only write a comment when the WHY is non-obvious (upstream bug workaround, hidden constraint).
- **Engine code reads `voice_dir` lazily** — full-conversion paths may pass `None`.

## Frontend gotcha

The backend serves `webui/frontend/dist/`. There is no Vite dev server in this setup. If you edit anything under `webui/frontend/src/` and forget to `npm run build`, the running app keeps serving the stale bundle and you will chase a phantom bug.
