# AGENTS.md — ebook2audiobook

Read this before working on the project. Every section codifies a decision
that's already been made; reverting one without re-reading the rationale
will reintroduce a bug or regression we've already paid for.

---

## Project at a glance

- Converts ebooks (epub/pdf/azw3/mobi/...) to audiobooks via local TTS.
- 10 TTS engines: `xtts`, `bark`, `tortoise`, `vits`, `fairseq`, `glowtts`,
  `tacotron`, `yourtts`, `fishspeech`, `cosyvoice`, `qwen3tts` (the user only
  cares about XTTSv2 in production; the other engines exist for completeness).
- React (Vite) + FastAPI WebUI under `webui/`. Backend is a thin shim around
  `lib.core.convert_chapters2audio()`.
- Target hardware: Windows 11 + RTX 4060 (8 GB VRAM, CUDA 12.8, cc 8.9). Most
  perf decisions are tuned for this combination.

---

## Repo map

| Path | Role |
|---|---|
| `lib/conf.py` | Paths, devices, env vars, sample rates, format defaults |
| `lib/conf_models.py` | `TTS_ENGINES` registry, `default_engine_settings` per engine |
| `lib/core.py` | Conversion pipeline; sentence loop at ~line 2292 (`convert_chapters2audio`) |
| `lib/classes/tts_engines/<name>.py` | One module per engine; each subclasses `TTSUtils` + `TTSRegistry` |
| `lib/classes/tts_engines/common/utils.py` | Shared `TTSUtils` (`_apply_gpu_policy`, `_load_checkpoint`, `_split_sentence_on_sml`, `_check_xtts_builtin_speakers`) |
| `lib/classes/tts_engines/common/torch_compat.py` | Two compat shims (auto-CPU on `__array__`, `weights_only=False`); imported via `headers.py` so every engine gets them |
| `lib/classes/tts_engines/common/headers.py` | Common imports re-exported to engines |
| `lib/classes/tts_manager.py` | Thin dispatcher: `TTSManager(session).convert(...)` → engine |
| `webui/backend/main.py` | FastAPI app + lifespan; `chdir`s to repo root because `lib/conf.py` reads `VERSION.txt` relative to cwd |
| `webui/backend/routers/preview.py` | `POST /api/preview` — same code path the test suite exercises |
| `webui/backend/routers/engines.py` | `GET /api/engines` — reads `.engine-mode` marker, returns filtered dropdown list |
| `webui/frontend/src/components/ConfigureCard.tsx` | Engine dropdown fetches from `/api/engines` |
| `python_env/` | Conda env where deps live (`python_env/python.exe`). NOT a venv |
| `third_party/CosyVoice/` | Vendored CosyVoice repo + Matcha-TTS submodule (cosyvoice profile only) |
| `tools/test_performance.py` | Static-source regression guards for perf optimizations |
| `tools/test_engines_e2e.py` | In-process per-engine voice-preview tests; saves WAVs to `tmp/engine_previews/` |
| `tools/test_webui_e2e.py` | WebUI session-lifecycle integration tests (needs running server) |
| `tools/base_install.py` | Idempotent base-package installer (called from `base_installation.cmd`) |

---

## Three install profiles (mutually exclusive)

The 10 engines split across three Python environments because their torch
versions don't coexist. The active profile is recorded in a `.engine-mode`
marker file at the repo root and read by `routers/engines.py`.

| Profile | Marker | torch | Engines |
|---|---|---|---|
| **regular** | `regular` | 2.7.1+cu128 | xtts, bark, tortoise, vits, fairseq, glowtts, tacotron, yourtts, fishspeech (9) |
| **cosyvoice** | `cosyvoice` | 2.3.1+cu121 | cosyvoice (1) |
| **qwen3tts** | `qwen3tts` | 2.7.1+cu128 | qwen3tts (1, with `transformers` pinned by qwen-tts) |

**Install flow:**
1. `base_installation.cmd` — wipes/installs engine-agnostic base packages
   (no torch). Idempotent: skips work if everything is current. Pass `--force`
   to wipe and reinstall.
2. Pick **one** of `1_regular_engines_install.cmd`,
   `2_cosy_voice_engine_install.cmd`, `3_qwen3tts_engine_install.cmd`.
   Each script uninstalls the *other profiles'* packages before installing
   its own, so switching profiles is safe without re-running base.
3. The dropdown in the WebUI auto-filters to whatever the active marker says.

**Rule:** never add a package to `requirements.txt` that's torch-version-
dependent. If it pulls torch as a dep, it goes into the per-profile script.
The base list lives in `tools/base_install.py:BASE_PACKAGES`.

---

## Critical compat shims (`lib/classes/tts_engines/common/torch_compat.py`)

These keep older third-party libs working on modern torch. Don't remove
either without finding a real replacement.

1. **`Tensor.__array__` auto-CPU.** torch >= 2.x made `np.asarray(cuda_tensor)`
   raise instead of silently moving to CPU. Coqui-TTS and librosa code paths
   assume the older behavior (`xtts.py:367`, Bark's HuBERT, etc.). The shim
   restores auto-CPU for that one method.
2. **`torch.load(weights_only=False)` forced.** torch >= 2.6 changed the default
   to `True`, which rejects `collections.defaultdict` in older Tacotron / GlowTTS
   checkpoints (and trainer.io passes `weights_only=True` explicitly, so a
   `setdefault` shim isn't enough — we *override* it).

Both shims are activated by `headers.py` importing the module, so anything
that does `from lib.classes.tts_engines.common.headers import *` gets them.

---

## Engine quirks (the non-obvious bits)

| Engine | Quirk | Why |
|---|---|---|
| **xtts** | `librosa_trim_db` arg dropped from `get_conditioning_latents()` | Upstream calls `librosa.effects.trim()` on a CUDA tensor (xtts.py:367); without the arg, that branch is skipped. |
| **xtts** | `torch.compile` opt-in via `OMC_XTTS_COMPILE=1` | `reduce-overhead` mode elided `.cpu()` transfers; `default` mode wraps in `OptimizedModule` whose `__bool__` raises. Default OFF. |
| **xtts** | DeepSpeed opt-in via `OMC_XTTS_DEEPSPEED=1` | Failed init partially mutates the model before raising; harder to recover from. Default OFF. |
| **xtts/utils** | All `if engine` checks use `is None` | Same `OptimizedModule.__bool__` issue from torch.compile. |
| **bark** | Forced `amp_dtype = float32`; runs on CPU in tests | FP16 autocast clashes with FP32 biases; Bark's voice-clone HuBERT runs on CPU and feeds CPU tensors to GPU sub-models — `cat()` fails. CPU mode is the working path. Voice "cloning" with a custom WAV is broken upstream on torch 2.x; tests use a synthetic `en_speaker_6.wav` path so the engine takes the *built-in* prompt-cache route. |
| **bark** | Per-part `engine.to(device)`/`engine.to(cpu)` shuffle restored (only engine that does this) | The HuBERT/cat issue means GPU residency across parts breaks. Documented exception to the residency rule. |
| **tortoise** | Forced `amp_dtype = float32` | HiFiGAN vocoder has FP32 biases. Same fix as Bark. |
| **fairseq/glowtts/tacotron** | `proc_dir = os.path.join(voice_dir, 'proc')` is built outside the per-part loop only when needed | If `voice_dir` is None it crashes early with `NoneType` path error. Preview endpoint provides a temp dir. |
| **tacotron** | `torch.load(weights_only=False)` required | Checkpoint contains `collections.defaultdict`. Handled by the shim above. |
| **glowtts/tacotron** | Need `gruut` phonemizer | Installed in the regular profile. |
| **fishspeech** | Tries `models.dac.inference` then falls back to `models.vqgan.inference` | 1.5 ships VQ-GAN, 1.6+ renamed to DAC. Either works. |
| **fishspeech** | Result codes are `header`/`segment`/`final`/`error` (NOT `data`) | Engine collects audio from `final` (non-streaming) or `segment` (streaming). |
| **fishspeech** | Requires `.project-root` marker file at repo root | Upstream `pyrootutils.setup_root()` walks up looking for it. Empty file is fine. |
| **cosyvoice** | `snapshot_download(ignore_patterns=['*.md', 'LICENSE'])` — does NOT exclude `.txt` | Qwen2 tokenizer needs `merges.txt`; excluding `*.txt` breaks it ("vocab and merges must be both be from memory or both filenames"). |
| **cosyvoice** | Uses `inference_cross_lingual` with `<\|es\|>`-style tag prefix | We don't have transcripts of reference voices; cross_lingual mode skips the prompt-text requirement. |
| **cosyvoice** | Currently **broken upstream on torch >= 2.7** | hift's f0_predictor conv (kernel=4) gets a 3-frame mel and crashes. Tracking [issue #1422](https://github.com/FunAudioLLM/CosyVoice/issues/1422). Marked `known_broken` in the test suite. Same failure with `Fun-CosyVoice3-0.5B-2512` model variant — codebase issue, not weights. |
| **qwen3tts** | Auto-transcribes reference voice with faster-whisper, caches to `<voice>.transcript.txt` sidecar | Provides `ref_text` for full-fidelity voice clone (upstream README: `x_vector_only_mode=True` "may reduce cloning quality"). User can override via WebUI textarea. |
| **qwen3tts** | `create_voice_clone_prompt(...)` cached per `(voice_path, ref_text)` | Avoids per-sentence x-vector recompute and removes timbre drift. |
| **qwen3tts** | flash-attn 2.7.4 wheel auto-installed | Upstream prints "flash-attn is not installed" warning and falls back to eager attention; the wheel is opt-in via `attn_implementation='flash_attention_2'` only when `import flash_attn` succeeds. ~2-3× speedup. |

---

## Performance optimizations (don't undo these)

These are committed and guarded by tests in `tools/test_performance.py`.

1. **`inference_mode` everywhere** instead of `no_grad`. ~10% on autoregressive TTS.
2. **TF32 + Flash SDPA + Memory-Efficient SDPA** enabled in `_apply_gpu_policy`
   for cc>=8 (Ampere+). ~20-40% on matmul-heavy code paths.
3. **Model GPU residency across the per-part loop** in 7 of 8 engines (Bark
   excepted). The original code was shuffling ~1.8 GB GPU↔CPU per sentence-part
   — ~37 minutes of pure transfer overhead on a 10k-sentence book.
4. **WAV intermediate format** (not FLAC). FLAC encoding was ~5-10% of total wall
   time for nothing — intermediates are short-lived.
5. **Hoisted per-part invariants in xtts.py:** `fine_tuned_params` dict (built
   once per `convert()` call via `TTSUtils._build_xtts_fine_tuned_params()`),
   `language_iso1`, `amp_enabled`, `samplerate`, `trim_audio_buffer`.
6. **SML fast-path** in `_split_sentence_on_sml`: `if '[' not in sentence:
   return [sentence]`. ~99% of book sentences have no SML.
7. **Silence-tensor cache** in xtts.py keyed on sample-count. ~30 unique values,
   never mutated (safe to share by reference — `torch.cat` doesn't write back).
8. **O(1) dict membership** for `latent_embedding` / `semitones` caches: use
   `key in dict`, never `key in dict.keys()`.
9. **Skip `cleanup_memory()` on cache hit** in `_load_checkpoint` /
   `_check_xtts_builtin_speakers`. Cleanup runs only on cold loads.

**Rule:** if a performance change re-introduces any of the patterns the
regression tests check for (`if engine:` truthy, `engine.to(cpu)` inside a
per-part loop, `dict.keys()` membership, `librosa_trim_db=30` in
`get_conditioning_latents`), the test fails with a clear message. Read it
before "fixing" it.

---

## Engineering rules

1. **Don't remove the compat shims.** `torch_compat.py` is load-bearing for
   most non-XTTS engines.
2. **Don't add abstractions beyond what the task requires.** A bug fix doesn't
   need surrounding cleanup; a one-shot operation doesn't need a helper. Three
   similar lines is better than a premature abstraction.
3. **Don't write narrating comments.** Comments explaining WHAT the code does
   are forbidden — well-named identifiers do that. Only add a comment when
   the WHY is non-obvious (hidden constraint, subtle invariant, workaround for
   a specific upstream bug).
4. **All `loaded_tts.get(key)` plus truthy check → use `is None`** for any
   engine that gets `_load_checkpoint`-ed (xtts and `_check_xtts_builtin_speakers`).
   torch.compile's `OptimizedModule.__bool__` raises.
5. **Engine code should read `voice_dir` lazily** and only when `current_voice`
   is set. The preview endpoint provides a real temp dir, but full-conversion
   code paths might pass None.
6. **Don't pin a package in `requirements.txt` if it depends on torch.** Move it
   to the per-profile script. The base list lives in
   `tools/base_install.py:BASE_PACKAGES`.
7. **Don't commit per-machine markers.** `.engine-mode`, `*.transcript.txt`,
   `.installed`, `Hardware`, `Miniforge3*.exe`, `voices/uploaded/`, and
   `voices/spa/*.wav` (user voices) are gitignored. The `.project-root` marker
   IS committed (empty file required by fish_speech's `pyrootutils`).

---

## Test infrastructure

| File | Run via | What it covers |
|---|---|---|
| `tools/test_performance.py` | `python tools/test_performance.py` | Static-source regression guards for every perf optimization. Passes 17/17 on a healthy install. |
| `tools/test_engines_e2e.py` | `./python_env/python.exe tools/test_engines_e2e.py [engine ...]` | In-process per-engine voice preview. Calls the same `_synthesize()` the WebUI uses, validates the WAV, saves it to `tmp/engine_previews/<engine>.wav`. Skips engines whose backend libs aren't installed (cosyvoice, fishspeech depending on profile). |
| `tools/test_webui_e2e.py` | `python tools/test_webui_e2e.py` | WebUI session-lifecycle integration. Requires `start_webui.cmd` running on `localhost:8000`. |

**Always run the e2e suite via `python_env/python.exe`** — fishspeech and
cosyvoice live in that env, not in the system Python. ffmpeg-shared must be
on `PATH` (`scoop install ffmpeg-shared`).

The e2e test for Bark uses a synthetic `voices/eng/en_speaker_6.wav` path
(file doesn't need to exist — the engine reads the basename only). This is
the documented "use built-in Bark prompt cache" path; voice cloning with
custom WAVs is broken upstream.

---

## Operational rules

- **`python_env/python.exe`** is the canonical interpreter. The system Python
  is not the right env. Tests, scripts, and the WebUI all run via python_env.
- **`scoop install ffmpeg-shared`** is required on Windows for torchaudio /
  torchcodec to load. Restart your terminal after install for the PATH update
  to take effect.
- **Don't run `pip install -r requirements.txt`** as a one-shot recipe. It pulls
  the wrong torch for the active profile. Use the install scripts.
- **`start_webui.cmd`** runs `uvicorn webui.backend.main:app --reload`. The
  reload watcher only watches `webui/backend`; changes elsewhere need a
  restart.
- **VS Code Python interpreter selector** should point at
  `C:\ebook2audiobook\python_env\python.exe` for IntelliSense to work. Don't
  point it at the Microsoft Store Python.

---

## Token-efficiency rules for agents

These exist because long debug sessions in this project are expensive — see
the post-mortem from 2026-04-30 (`12% of daily budget for one debug session`).

1. **Don't re-read files you've already read this session.** Cache the relevant
   facts as one-line summaries in your working memory.
2. **Use `Grep` with `output_mode=content` + `head_limit`** instead of `Read`
   for files where you only need 5-20 lines.
3. **For broad codebase searches, delegate to the Explore subagent.**
   Subagents return condensed summaries; main-context greps return full content.
4. **Don't re-run the same diagnostic.** If the e2e suite already showed engine
   X passes, don't re-run it to confirm.
5. **For log files, use `tail -N` or `python -c "f.readlines()[-N:]"`** instead
   of cat/Read. The full log rarely matters — the last 20 lines almost always do.
6. **WebFetch returns large payloads.** Use very specific prompts
   ("quote the exact line that imports X" / "list filenames matching Y") so the
   model summarizing the page returns tokens, not a full mirror.
7. **Pause and start a fresh session** when one engine is solved before
   debugging the next. Don't carry the full prior context into unrelated work.

---

## Known upstream limitations

- **CosyVoice 3** crashes on torch >= 2.7 (issue #1422). No fix as of
  2026-04-30. Skipped in the e2e suite via `known_broken`.
- **Bark voice cloning with custom WAV** is broken on torch 2.x + coqui-tts
  0.27.5 (HuBERT-CPU/Bark-GPU mismatch). Built-in prompt-cache speakers work.
- **DeepSpeed inference init** mutates the engine before failing on Windows
  without full CUDA Toolkit. Gated behind `OMC_XTTS_DEEPSPEED=1`.
- **`flash-attn`** is not on PyPI for Windows. We pin a community wheel
  ([lldacing/flash-attention-windows-wheel](https://huggingface.co/lldacing/flash-attention-windows-wheel))
  for the qwen3tts profile (cp312 + cu128 + torch 2.7).
- **Microsoft Store Python** is incompatible with this project (sandboxed
  site-packages, brittle pip behavior). Use a real Python install or the
  conda `python_env/`.

---

## When in doubt

- The optimization plans we executed are in the commit history; `git log
  --grep="perf"` and `git log --grep="fix"` give a fast tour.
- The reasoning behind each optimization tier is in the commit messages of
  `682edbad`, `00f6ad57`, `241742b9`, `e7b24e63`.
- Per-engine bug fixes are in `cb14f5c8` (XTTS truthy checks),
  `e62e94bb` (multi-engine GPU residency), and the engine-specific commits
  that followed.
- For the install-script split rationale, see the "build:" commits.
