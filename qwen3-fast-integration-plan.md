# Qwen3-TTS Speed Plan — Dual Backend (`qwen-tts` + `faster-qwen3-tts`)

**Goal:** keep the proven `qwen-tts` path as default, add `faster-qwen3-tts` as an opt-in backend, and land a small set of "free" perf wins that apply to both.

**Architecture decision (2026-05-03):** the two backends ship as **separate install profiles**, not as opt-in within profile 3.  Profile 3 (`qwen3tts`) keeps the proven `qwen-tts` path untouched.  A new profile 5 (`qwen_fast`) installs `faster-qwen3-tts` alongside `qwen-tts` (the fork still depends on the upstream package types) and selects the fast backend automatically by writing `qwen_fast` into `.engine-mode`.  The user picks the speed/safety tradeoff at install time, no runtime toggle required.

**Non-goals:** swapping to the 0.6B model, quantization, dropping our prompt-cache contract, exposing a backend dropdown in the WebUI.

**Hardware target:** RTX 4060 8 GB (Ada). VRAM is tight — anything that pre-allocates (CUDA Graphs, `torch.compile` w/ `max-autotune`) needs a sequence-length cap.

---

## Phase 0 — Research & verify ✅ DONE

- [x] **Distribution.** PyPI: `pip install faster-qwen3-tts` (v0.2.6).
- [x] **Version pins.** Python 3.10+, PyTorch 2.5.1+. Our profile (torch 2.7.1+cu128) is fine.
- [x] **Class & load signature.**
  ```python
  FasterQwen3TTS.from_pretrained(
      model_name, device='cuda', dtype=torch.bfloat16,
      attn_implementation='sdpa', max_seq_len=2048,
  )
  ```
  Differences vs current `Qwen3TTSModel.from_pretrained`:
  - `device='cuda'` (string), not `device_map='cuda:0'`.
  - `attn_implementation` defaults to `'sdpa'` — we must pass `'flash_attention_2'` explicitly to match our current behavior.
  - New `max_seq_len=2048` knob — sets the CUDA-graph buffer size. 2048 is fine for our sentence-level inputs.
- [x] **Prompt cache survives the swap.** The fork exposes the original model under `.model`, so `model.model.create_voice_clone_prompt(...)` returns a reusable `voice_clone_prompt` handle that `generate_voice_clone(..., voice_clone_prompt=...)` accepts. Our `_voice_prompt_cache` keying on `(voice_path, ref_text)` works unchanged.
- [x] **Output contract identical.** Returns `Tuple[List[np.ndarray], int]` — same as `qwen-tts` today. No adapter glue needed.
- [x] **`use_fast_codebook` does NOT exist** in the installed `qwen_tts` package (grep returned nothing). Grok was wrong on that one — **dropped from Phase 1**.
- [x] **Sampling kwargs — partial parity.**
  - Talker-level **exposed**: `temperature`, `top_p`, `top_k`, `repetition_penalty`, `do_sample`, `max_new_tokens`, `min_new_tokens`. ✅
  - Sub-talker-level **NOT exposed**: `subtalker_temperature`, `subtalker_top_p`, `subtalker_top_k`. ⚠ Logged as risk below.
  - Fork's defaults (`temp=0.9, top_p=1.0, rep_penalty=1.05`) match the package defaults we deliberately tuned away from — we must pass our narration values explicitly.

### Phase 0 risk: sub-talker sampling control gone on the fast backend

The fork's `generate_voice_clone` does not expose `subtalker_*` kwargs and does not accept `**kwargs` to pass them through. On the fast backend we lose fine control over the sub-talker that generates additional codebook tokens. Talker-level drift control (the dominant timbre/prosody knob) is preserved. **Acceptable** — document it; if drift on long books regresses, fall back to the default backend for that job.

---

## Phase 1 — Free wins (apply to both backends)

Single small commit. Land before any backend abstraction work so we get the gain regardless of which path the user runs.

- [ ] In `lib/classes/tts_engines/qwen3tts.py:load_engine()` (before `from_pretrained`):
  - [ ] `torch.set_float32_matmul_precision('high')` — TF32 enable on Ada.
  - [ ] `torch.backends.cudnn.benchmark = True` — fixed-shape kernel autotune.
- [ ] ~~`use_fast_codebook=True`~~ — **dropped**. Phase 0 confirmed the kwarg does not exist in installed `qwen-tts`.
- [ ] Add a static guard to `tools/test_performance.py` so these lines can't silently regress (mirror the existing pattern for other guarded perf opts — see AGENTS.md "Performance optimizations").
- [ ] Run `.\python_env\python.exe tools\test_engines_e2e.py qwen3tts` — verify audio still saves to `tmp/engine_previews/` and sounds identical. Time it for a baseline RTF number.
- [ ] Commit: `perf(qwen3tts): enable TF32 + cudnn.benchmark`.

---

## Phase 2 — Backend abstraction ✅ DONE

- [x] `_Backend` ABC + `_QwenTtsBackend` impl wired into `Qwen3TTS.load_engine` / `_get_voice_clone_prompt` / `convert`.
- [x] Backend selection via `session['qwen3tts_backend']`; default `'qwen-tts'`; unknown raises `ValueError` up front.
- [x] E2E smoke passes through the new path. Commit `83aabcfa`.

---

## Phase 3 — `_FasterQwenTtsBackend` impl

Lands together with Phase 4 because the package only exists under the new install profile, so the impl is untestable without the script.

- [ ] Add `_FasterQwenTtsBackend` to `lib/classes/tts_engines/qwen3tts.py`:
  - [ ] `load`: `FasterQwen3TTS.from_pretrained(repo, device='cuda', dtype=torch.bfloat16, attn_implementation='flash_attention_2', max_seq_len=session.get('qwen3tts_max_seq_len', 2048))`. Translate our `device_map='cuda:0'` → `device='cuda'`.
  - [ ] `build_prompt`: call `engine.model.create_voice_clone_prompt(ref_audio, ref_text, x_vector_only_mode=not bool(ref_text))` — one extra `.model` hop.
  - [ ] `generate`: call `engine.generate_voice_clone(text=..., language=..., voice_clone_prompt=..., temperature=, top_p=, top_k=, repetition_penalty=, do_sample=True)`. **Filter out** `subtalker_*` kwargs from `gen_kwargs` — fork doesn't accept them and has no `**kwargs` passthrough. Filter belongs in the backend so the wrapping `Qwen3TTS` class stays backend-agnostic.
- [ ] Update `_resolve_backend` to register `'faster-qwen-tts'` and add `.engine-mode` auto-detection: when the file contains `qwen_fast`, default the session backend to `'faster-qwen-tts'` (session override still wins, useful for tests).
- [ ] Add session knob `qwen3tts_max_seq_len` (default 2048) for VRAM-tight users.
- [ ] Try / except around the `FasterQwen3TTS` import: on failure raise with a clear message pointing at `5_qwen_fast_install.cmd`. Don't silently fall back to the default backend — the user picked the fast profile, fail loudly if it isn't installed.
- [ ] Commit: `feat(qwen3tts): add faster-qwen3-tts backend wired to qwen_fast profile`.

---

## Phase 4 — New install profile `5_qwen_fast_install.cmd`

Standalone profile, mirrors `3_qwen3tts_engine_install.cmd` line-for-line with `faster-qwen3-tts` added. Profile 3 stays untouched.

- [ ] Create `5_qwen_fast_install.cmd`:
  - [ ] Step 1: uninstall cross-profile packages — same list as profile 3, but **also** uninstall standalone `qwen3tts`-profile residue (`qwen-tts` is reinstalled in step 3 since the fork still imports types from it).
  - [ ] Step 2: install torch 2.7.1+cu128 trio (same as profile 3).
  - [ ] Step 3: `pip install -U qwen-tts faster-qwen3-tts faster-whisper`. Verify upstream package compatibility — if `faster-qwen3-tts` pulls a different transformers/accelerate pin than `qwen-tts`, document and pin explicitly.
  - [ ] Step 4: install flash-attn windows wheel (same as profile 3).
  - [ ] Step 5: `> .engine-mode echo qwen_fast`.
- [ ] Update profiles 1, 2, 3, 4 to add `faster-qwen3-tts` to their step-1 uninstall list, so a profile switch doesn't leave the fork's package straddling environments.
- [ ] Verify `webui/backend/routers/engines.py` shows the `qwen3tts` engine in the dropdown when `.engine-mode == 'qwen_fast'` — either add `qwen_fast` as an alias, or expose a separate engine entry. Pick whichever requires the smaller diff.
- [ ] Smoke test: fresh `5_qwen_fast_install.cmd` from a profile-3 baseline, run e2e, compare output WAV against profile 3.

---

## Phase 5 — Tests + docs

- [ ] `tools/test_engines_e2e.py`: add a `--backend {qwen-tts,faster-qwen-tts}` flag that sets `session['qwen3tts_backend']` before instantiating, so a single profile (whichever is installed) can run both backends side-by-side when both packages happen to be available. Skip cleanly when the package for the requested backend is absent.
- [ ] Run profile 3 e2e and profile 5 e2e on the same 5-sentence sample, save to `tmp/engine_previews/qwen3tts_{profile}.wav`, log per-sentence wall-clock and total RTF. Paste numbers into the **Results** section below.
- [ ] Add a paragraph to `AGENTS.md` describing the two profiles and the speed/safety tradeoff. Reference this file.
- [ ] Update `CLAUDE.md` Common-commands table with the new install script row.

---

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| ~~Reusable prompt handle missing in fork~~ | Resolved: `engine.model.create_voice_clone_prompt(...)` works |
| Sub-talker sampling control gone on fast backend | Documented; talker-level control retained; fall back to default backend if drift regresses on long books |
| Graph capture OOM on 4060 8 GB | Expose `qwen3tts_max_seq_len` session knob; default 2048 (fork default); user can lower if VRAM-tight |
| `torch.compile` flakes on Windows | Out of scope for v1 — only the upstream fork's pre-baked graph capture, no ad-hoc `torch.compile` calls in our code |
| Profile-switch leaves `faster-qwen3-tts` installed under a non-qwen profile | Add to the cross-profile uninstall list in scripts 1, 2, 3, 4 |
| Fork's deps conflict with `qwen-tts`'s pins (transformers / accelerate) | Verify during Phase 4. If they diverge, pin the working set in profile 5 explicitly and document. |
| User installed profile 5 but `faster-qwen3-tts` import fails | Backend raises with a pointer to `5_qwen_fast_install.cmd`; no silent fallback |
| `cudnn.benchmark = True` slows the first 1–2 sentences (autotune) | Acceptable; warn in commit message; long conversions amortize it |
| First-call CUDA-graph capture is slow | Inherent to the fork. Document; long conversions amortize it |

---

## Open questions — resolved

1. ~~PyPI or git-only?~~ → PyPI: `faster-qwen3-tts` v0.2.6.
2. ~~Same `from_pretrained` API?~~ → Different class (`FasterQwen3TTS`) but compatible signature; minor name swap (`device_map`→`device`) and a new `max_seq_len` arg.
3. ~~Prompt-cache equivalent?~~ → Yes, via `engine.model.create_voice_clone_prompt(...)` returning a reusable handle.
4. ~~Max-decode-length knob?~~ → `max_seq_len` at `from_pretrained` (default 2048). Sets the CUDA-graph buffer pre-allocation. Expose via session key for VRAM-tight users.
5. ~~`use_fast_codebook` in installed `qwen-tts`?~~ → No. Dropped from Phase 1.

---

## Results

_Filled in after Phase 5._

### Steady-state benchmark (5 sentences, RTX 4060 8 GB, profile 5)

`tools/bench_qwen3tts.py` runs the same 5-sentence Spanish script through each backend in a fresh subprocess (so model caches and CUDA graphs don't leak across).

| Backend | Load | s1 (cold) | s2..s5 (steady) | All 5 |
|---|---|---|---|---|
| `qwen-tts` (upstream) | 10.84 s | 13.63 s / 3.27 s audio (RTF 4.17) | 51.68 s / 17.57 s audio (RTF **2.94**) | 65.31 s / 20.84 s audio (RTF **3.13**) |
| `faster-qwen-tts` (fork) | 10.64 s | 12.60 s / 3.16 s audio (RTF 3.99) | 20.58 s / 18.56 s audio (RTF **1.11**) | 33.18 s / 21.72 s audio (RTF **1.53**) |

**Speedup, fast vs upstream:**
- Steady-state per-sentence: **2.65x** (RTF 2.94 → 1.11)
- Whole 5-sentence batch including cold-start: **2.05x** (RTF 3.13 → 1.53)
- For a multi-thousand-sentence audiobook the steady-state number dominates: expect ~2.6-2.7x wall-clock reduction.

The fork's first sentence (12.60 s, includes both predictor and talker CUDA-graph capture) is already faster than the upstream's first sentence (13.63 s). After that, fast backend runs ~5 s/sentence vs upstream's ~12 s/sentence on the same hardware.

### Phase 5 finding: force SDPA on the fast backend

First run with `flash_attention_2` failed: `transformers/integrations/flash_attention.py` does CPU/GPU sync ops (`.item()` calls inside `is_fa_with_varlen_kwargs` / `position_ids` checks) that are forbidden during CUDA-graph capture. The fork errors out with `CUDA error: operation not permitted when stream is capturing` the first time `generate_voice_clone` runs. Fix: `_FasterQwenTtsBackend.load()` ignores the wrapper's `attn_impl` and forces `'sdpa'` (the fork's documented default). Profile 5's install script no longer installs flash-attn — useless on this path, reinstalled when switching back to profile 3.
