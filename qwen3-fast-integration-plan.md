# Qwen3-TTS Speed Plan — Dual Backend (`qwen-tts` + `faster-qwen3-tts`)

**Goal:** keep the proven `qwen-tts` path as default, add `faster-qwen3-tts` as an opt-in backend, and land a small set of "free" perf wins that apply to both.

**Non-goals:** swapping to the 0.6B model, quantization, dropping our prompt-cache contract, exposing a backend dropdown in the WebUI (env / `.engine-mode` sidecar is enough for now).

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

## Phase 2 — Backend abstraction (still on default `qwen-tts` path)

Refactor without changing behavior. Goal: every `qwen-tts`-specific call routed through a backend object so Phase 3 can swap the impl in cleanly.

- [ ] Add `_Backend` ABC (or duck-typed protocol) inside `qwen3tts.py` (no new file — keep changes local). Methods:
  - [ ] `load(repo, dtype, device_map, attn_impl) -> engine`
  - [ ] `build_prompt(engine, voice_path, ref_text) -> prompt_handle`
  - [ ] `generate(engine, text, language, prompt_handle, gen_kwargs) -> (wavs, sr)`
- [ ] Implement `_QwenTtsBackend` wrapping the existing three call sites (qwen3tts.py:155, :273, :343).
- [ ] Replace direct calls in `Qwen3TTS.load_engine` / `_get_voice_clone_prompt` / `convert` with `self._backend.<method>`.
- [ ] Keep `_voice_prompt_cache` keyed on `(voice_path, ref_text)` regardless of backend — cache lives on the wrapper, not inside the backend.
- [ ] Backend selection: read `self.session.get('qwen3tts_backend', 'qwen-tts')`. For now only `'qwen-tts'` is wired; unknown values raise.
- [ ] Re-run e2e test, audio must be byte-identical to Phase 1 output (same seed → same waveform).
- [ ] Commit: `refactor(qwen3tts): route through backend abstraction (no behavior change)`.

---

## Phase 3 — `faster-qwen3-tts` backend

Implement the second backend; opt-in only.

- [ ] Implement `_FasterQwenTtsBackend`:
  - [ ] `load`: `FasterQwen3TTS.from_pretrained(repo, device='cuda', dtype=torch.bfloat16, attn_implementation='flash_attention_2', max_seq_len=session.get('qwen3tts_max_seq_len', 2048))`. Translate our `device_map='cuda:0'` → `device='cuda'`.
  - [ ] `build_prompt`: call `engine.model.create_voice_clone_prompt(ref_audio, ref_text, x_vector_only_mode=not bool(ref_text))` — same args as today, just one extra `.model` hop.
  - [ ] `generate`: call `engine.generate_voice_clone(text=..., language=..., voice_clone_prompt=..., temperature=, top_p=, top_k=, repetition_penalty=, do_sample=True)`. **Skip** `subtalker_*` kwargs — fork doesn't accept them.
- [ ] Add session knob `qwen3tts_max_seq_len` (default 2048) for VRAM-tight users on 4060.
- [ ] Try / except around `FasterQwen3TTS` import and graph-capture path: on failure raise with a clear message ("install faster-qwen3-tts or unset qwen3tts_backend"). Don't silently fall back — user explicitly opted in.
- [ ] First-call latency note: CUDA-graph capture on first `generate_voice_clone` is slow (graph trace). Subsequent calls are fast. Acceptable; warn in commit message.
- [ ] Commit: `feat(qwen3tts): add faster-qwen3-tts backend (opt-in)`.

---

## Phase 4 — Install profile updates

- [ ] Extend `3_qwen3tts_engine_install.cmd`:
  - [ ] Renumber existing `[5/5]` to `[6/6]`.
  - [ ] Add new `[5/6] Installing faster-qwen3-tts (optional)` step. Use whichever distribution Phase 0 confirmed (PyPI `pip install faster-qwen3-tts` or `pip install git+https://...`). Mark non-fatal: log a warning, leave the user on the default backend.
- [ ] Verify cross-profile uninstall in `[1/4]` doesn't strip `faster-qwen3-tts` accidentally on a profile switch (if it ships as an additional package, add it to the uninstall list to keep profiles clean).
- [ ] Test: fresh `3_qwen3tts_engine_install.cmd` run from a `1_regular_engines_install.cmd` baseline, confirm both backends instantiate.

---

## Phase 5 — Tests + docs

- [ ] `tools/test_engines_e2e.py`: add a `--backend {qwen-tts,faster-qwen-tts}` flag (or `QWEN3TTS_BACKEND` env var) that sets `session['qwen3tts_backend']` before instantiating.
- [ ] Run both backends end-to-end on the same 5-sentence sample, save to `tmp/engine_previews/qwen3tts_{backend}.wav`, log per-sentence wall-clock and total RTF. Paste numbers into this file's **Results** section below.
- [ ] Add a one-paragraph note to `AGENTS.md` Qwen3-TTS section about the backend toggle and where to set it. Reference this plan file.
- [ ] Update `CLAUDE.md` only if the operating instructions for the backend differ in a non-obvious way.

---

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| ~~Reusable prompt handle missing in fork~~ | Resolved: `engine.model.create_voice_clone_prompt(...)` works |
| Sub-talker sampling control gone on fast backend | Documented; talker-level control retained; fall back to default backend if drift regresses on long books |
| Graph capture OOM on 4060 8 GB | Expose `qwen3tts_max_seq_len` session knob; default 2048 (fork default); user can lower if VRAM-tight |
| `torch.compile` flakes on Windows | Out of scope for v1 — only the upstream fork's pre-baked graph capture, no ad-hoc `torch.compile` calls in our code |
| Profile-switch leaves `faster-qwen3-tts` installed under a non-qwen profile | Add to the cross-profile uninstall list in each other install script |
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

| Backend | RTF (1-sentence smoke) | Notes |
|---|---|---|
| `qwen-tts` + TF32 + cudnn.benchmark | 8.5 (3.13s audio in 26.7s inference) | First-call includes cudnn autotune cost; not a steady-state number. Phase 1 e2e smoke run on TEXT_SPA, 4060 8 GB. |
| `qwen-tts` (no Phase 1 knobs) | not measured | We didn't capture a pre-Phase-1 baseline before applying the change; would need to revert+rerun. Acceptable since the change is non-invasive. |
| `faster-qwen-tts` | TBD | Phase 5 |

For meaningful comparison, Phase 5 will run a 5+ sentence batch on each backend (so first-call autotune amortizes) and measure both total RTF and time-to-first-audio.
