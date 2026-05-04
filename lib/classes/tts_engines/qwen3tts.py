from lib.classes.tts_engines.common.headers import *
from lib.classes.tts_engines.common.preset_loader import load_engine_presets

# Qwen3-TTS — zero-shot voice cloning via transformer-based TTS.
# Model weights: Apache 2.0 (commercial use allowed).
# Codebase: Apache 2.0.  https://github.com/QwenLM/Qwen3-TTS
#
# Quality levers tuned here, in order of fidelity impact:
#   1. ref_text (transcript of the reference audio).  Upstream README says
#      x_vector_only_mode=True "may reduce cloning quality" — supplying a
#      real transcript switches to full-fidelity mode.  We resolve ref_text
#      from, in order: session override → sidecar `<voice>.transcript.txt`
#      → faster-whisper auto-transcribe (cached to sidecar on first use).
#   2. create_voice_clone_prompt(...) is built ONCE per voice + ref_text and
#      reused across every sentence in a conversion job.  Saves the per-call
#      prompt-feature recomputation and removes a source of timbre drift.
#   3. Sampling temperature is dropped from the package default 0.9 to 0.7
#      (talker + sub-talker) and repetition_penalty bumped to 1.1.  Audiobook
#      narration wants timbre/prosody stability across thousands of sentences;
#      0.9 is creative-speech territory and produces noticeable per-sentence
#      drift.  See qwen_tts/inference/qwen3_tts_model.py:_merge_generate_kwargs
#      for the full hard-default table.
#   4. torch.manual_seed is set before each generate_voice_clone call so the
#      sampler starts from the same RNG state every sentence — same input,
#      same output, with no cross-sentence randomness leaking through.

# Tuned generation defaults for narration.  Each may be overridden via
# session['qwen3tts_<key>'] (no UI exposure today; see preview.py wiring
# pattern if you ever want to surface these).
_NARRATION_GEN_DEFAULTS = {
    'temperature': 0.7,
    'top_p': 0.9,
    'top_k': 50,
    'repetition_penalty': 1.1,
    'subtalker_temperature': 0.7,
    'subtalker_top_p': 0.9,
    'subtalker_top_k': 50,
}
_NARRATION_SEED_DEFAULT = 0

# Backend selection.  In priority order: explicit session override
# (`session['qwen3tts_backend']`, mainly for tests), then auto-detect from
# `.engine-mode` at the repo root (`qwen_fast` profile → fast backend),
# then fall back to the upstream qwen-tts package.
_DEFAULT_BACKEND = 'qwen-tts'
_FAST_BACKEND = 'faster-qwen-tts'

# .engine-mode marker → backend name.  Add new modes here as install
# profiles are added.
_ENGINE_MODE_TO_BACKEND = {
    'qwen_fast': _FAST_BACKEND,
    # 'qwen3tts' (the default profile) and any unknown value resolve to
    # the upstream qwen-tts backend below.
}

# qwen3tts.py lives at lib/classes/tts_engines/qwen3tts.py — four
# dirnames up is the repo root where .engine-mode is written.
_REPO_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', '..', '..',
))


def _backend_from_engine_mode() -> str:
    """Pick the default backend from the .engine-mode marker.

    Mirrors webui/backend/routers/engines.py:_read_mode().  Returning the
    upstream backend on missing/unreadable file keeps non-qwen3tts
    profiles working unchanged.
    """
    marker = os.path.join(_REPO_ROOT, '.engine-mode')
    try:
        with open(marker, 'r', encoding='utf-8') as f:
            mode = f.read().strip().lower()
    except (FileNotFoundError, OSError):
        return _DEFAULT_BACKEND
    return _ENGINE_MODE_TO_BACKEND.get(mode, _DEFAULT_BACKEND)

# ISO 639-3 → Qwen3-TTS language string mapping.
_LANG_MAP = {
    'ara': 'Arabic',
    'deu': 'German',
    'eng': 'English',
    'fra': 'French',
    'ita': 'Italian',
    'jpn': 'Japanese',
    'kor': 'Korean',
    'por': 'Portuguese',
    'rus': 'Russian',
    'spa': 'Spanish',
    'zho': 'Chinese',
    'yue': 'Chinese',  # Cantonese → fallback to Chinese
}

# Whisper model is shared across all Qwen3TTS instances.  ~250 MB download
# on first use; cached under HF_HOME afterwards.
_WHISPER_MODEL = None


def _get_whisper_model():
    global _WHISPER_MODEL
    if _WHISPER_MODEL is not None:
        return _WHISPER_MODEL
    try:
        import torch
        from faster_whisper import WhisperModel
    except ImportError:
        return None
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    compute_type = 'float16' if device == 'cuda' else 'int8'
    # 'small' balances accuracy and speed.  We only need a transcript good
    # enough for the LLM's voice-clone prompt — not a publishable transcript.
    try:
        _WHISPER_MODEL = WhisperModel('small', device=device, compute_type=compute_type)
    except Exception as e:
        print(f'[qwen3tts] faster-whisper init failed: {e}')
        _WHISPER_MODEL = None
    return _WHISPER_MODEL


# ---------------------------------------------------------------------------
# Backend abstraction
# ---------------------------------------------------------------------------
# Every engine-specific call (load, build prompt, generate) is routed through
# a Backend object so a second backend can be plugged in without touching the
# Qwen3TTS class.  The wrapping class still owns the prompt cache, sampling
# kwargs, seed reset, resampler cache, SML splitting, and silence insertion —
# all backend-agnostic.  See qwen3-fast-integration-plan.md.

class _Backend:
    name: str = ''

    def load(self, repo: str, dtype, device_map: str, attn_impl: str, **opts) -> Any:
        raise NotImplementedError

    def build_prompt(self, engine: Any, voice_path: str, ref_text: str) -> Any:
        raise NotImplementedError

    def generate(self, engine: Any, text: str, language: str, prompt: Any, gen_kwargs: dict):
        raise NotImplementedError


class _QwenTtsBackend(_Backend):
    """Default backend — straight wrapper around the `qwen-tts` PyPI package."""
    name = 'qwen-tts'

    def load(self, repo, dtype, device_map, attn_impl, **opts):
        try:
            from qwen_tts import Qwen3TTSModel
        except ImportError as e:
            raise RuntimeError(
                f'Qwen3-TTS Python package could not be imported. '
                f'Install with:\n'
                f'  pip install -U qwen-tts\n'
                f'Original error: {e}'
            ) from e
        return Qwen3TTSModel.from_pretrained(
            repo,
            device_map=device_map,
            dtype=dtype,
            attn_implementation=attn_impl,
        )

    def build_prompt(self, engine, voice_path, ref_text):
        return engine.create_voice_clone_prompt(
            ref_audio=voice_path,
            ref_text=ref_text,
            x_vector_only_mode=not bool(ref_text),
        )

    def generate(self, engine, text, language, prompt, gen_kwargs):
        return engine.generate_voice_clone(
            text=text,
            language=language,
            voice_clone_prompt=prompt,
            **gen_kwargs,
        )


class _FasterQwenTtsBackend(_Backend):
    """CUDA-graph-optimized backend via the `faster-qwen3-tts` PyPI fork.

    Active when the `qwen_fast` install profile is selected
    (.engine-mode == 'qwen_fast').  The fork keeps the same prompt-handle
    contract (engine.model.create_voice_clone_prompt) and return type
    (Tuple[List[np.ndarray], int]) as upstream `qwen-tts`, so the
    wrapping Qwen3TTS class needs no changes beyond backend dispatch.

    Two API divergences vs upstream:
      - load takes `device` (string), not `device_map`; we translate.
        It also takes `max_seq_len` for CUDA-graph buffer pre-allocation.
      - generate_voice_clone does NOT accept `subtalker_*` kwargs and
        has no **kwargs passthrough.  We strip those from gen_kwargs
        here so the wrapping class can stay backend-agnostic.
    """
    name = _FAST_BACKEND

    def load(self, repo, dtype, device_map, attn_impl, **opts):
        try:
            from faster_qwen3_tts import FasterQwen3TTS
        except ImportError as e:
            raise RuntimeError(
                f'faster-qwen3-tts is not installed but the qwen_fast install '
                f'profile is selected.  Run 5_qwen_fast_install.cmd, or revert '
                f'to 3_qwen3tts_engine_install.cmd for the upstream backend.\n'
                f'Original error: {e}'
            ) from e
        # device_map='cuda:0' / 'cpu' -> device='cuda' / 'cpu'.  The fork
        # only supports a single CUDA device; the index is ignored.
        device = 'cuda' if device_map.startswith('cuda') else device_map
        max_seq_len = int(opts.get('max_seq_len') or 2048)
        # Ignore `attn_impl` from the wrapper and force SDPA: transformers'
        # flash_attention_2 forward path does CPU/GPU sync ops (`.item()`
        # inside is_fa_with_varlen_kwargs / position_ids checks) that are
        # forbidden during CUDA-graph capture, so the fork errors out with
        # "operation not permitted when stream is capturing" the first time
        # generate_voice_clone is called.  SDPA is the fork's documented
        # default and is graph-capture-safe.
        return FasterQwen3TTS.from_pretrained(
            repo,
            device=device,
            dtype=dtype,
            attn_implementation='sdpa',
            max_seq_len=max_seq_len,
        )

    def build_prompt(self, engine, voice_path, ref_text):
        # Fork exposes the original Qwen3TTSModel under .model; use it so
        # the prompt handle stays compatible with our cache contract.
        return engine.model.create_voice_clone_prompt(
            ref_audio=voice_path,
            ref_text=ref_text,
            x_vector_only_mode=not bool(ref_text),
        )

    def generate(self, engine, text, language, prompt, gen_kwargs):
        # Strip sub-talker kwargs the fork can't accept.  Talker-level
        # narration tuning (temperature, top_p, top_k, repetition_penalty)
        # still flows through unchanged — that's the dominant drift control.
        filtered = {
            k: v for k, v in gen_kwargs.items()
            if not k.startswith('subtalker_')
        }
        filtered.setdefault('do_sample', True)
        return engine.generate_voice_clone(
            text=text,
            language=language,
            voice_clone_prompt=prompt,
            **filtered,
        )


def _resolve_backend(name: str) -> _Backend:
    if name == _DEFAULT_BACKEND:
        return _QwenTtsBackend()
    if name == _FAST_BACKEND:
        return _FasterQwenTtsBackend()
    raise ValueError(
        f"Unknown qwen3tts_backend {name!r}. "
        f"Supported: {_DEFAULT_BACKEND!r}, {_FAST_BACKEND!r}."
    )


class Qwen3TTS(TTSUtils, TTSRegistry, name='qwen3tts'):

    def __init__(self, session: DictProxy):
        try:
            self.session = session
            self.cache_dir = tts_dir
            self.tts_key = self.session['model_cache']
            self.resampler_cache = {}
            self.audio_segments = []
            self.params = {}
            self.models = load_engine_presets(self.session['tts_engine'])
            fine_tuned = self.session.get('fine_tuned')
            if fine_tuned not in self.models:
                error = f'Invalid fine_tuned model {fine_tuned}. Available: {list(self.models.keys())}'
                raise ValueError(error)
            model_cfg = self.models[fine_tuned]
            for required_key in ('repo', 'samplerate'):
                if required_key not in model_cfg:
                    error = f'fine_tuned model {fine_tuned} missing required key {required_key}.'
                    raise ValueError(error)
            self.params['samplerate'] = model_cfg['samplerate']
            enough_vram = self.session['free_vram_gb'] > 4.0
            self.amp_dtype = self._apply_gpu_policy(enough_vram=enough_vram, seed=0)
            # Voice-clone prompt cache: (voice_path, ref_text) -> prompt items.
            # Built lazily; survives the lifetime of the engine instance.
            self._voice_prompt_cache = {}
            self._gen_kwargs = self._resolve_gen_kwargs()
            self._seed = int(self.session.get('qwen3tts_seed', _NARRATION_SEED_DEFAULT) or 0)
            backend_override = (self.session.get('qwen3tts_backend') or '').strip()
            backend_name = backend_override or _backend_from_engine_mode()
            self._backend = _resolve_backend(backend_name)
            self.engine = self.load_engine()
        except Exception as e:
            raise ValueError(f'Qwen3TTS.__init__() error: {e}') from e

    def load_engine(self) -> Any:
        try:
            engine = loaded_tts.get(self.tts_key)
            if engine is not None:
                print(f'TTS {self.tts_key} model already loaded, reusing cached engine.')
                return engine

            print(f'Loading TTS {self.tts_key} model (backend={self._backend.name}), it takes a while, please be patient…')
            self.cleanup_memory()

            import torch

            fine_tuned = self.session.get('fine_tuned', 'internal')
            repo = self.models[fine_tuned]['repo']

            is_cuda = self.session['device'] in [
                devices['CUDA']['proc'],
                devices['ROCM']['proc'],
                devices['JETSON']['proc'],
            ]

            # Perf knobs applied before the first weight load.  TF32 unlocks
            # Ada/Ampere tensor-core matmuls at fp32 precision (negligible
            # quality impact on TTS); cudnn.benchmark autotunes conv kernels
            # for the fixed shapes the AR decode loop sees every step.  Both
            # are global torch settings — fine for the qwen3tts profile,
            # which uninstalls every other engine.
            if is_cuda:
                torch.set_float32_matmul_precision('high')
                torch.backends.cudnn.benchmark = True

            device_map = 'cuda:0' if is_cuda else 'cpu'
            dtype = torch.bfloat16 if is_cuda else torch.float32

            try:
                import flash_attn  # noqa: F401
                attn_impl = 'flash_attention_2'
            except ImportError:
                attn_impl = 'eager'

            engine = self._backend.load(
                repo=repo,
                dtype=dtype,
                device_map=device_map,
                attn_impl=attn_impl,
                max_seq_len=int(self.session.get('qwen3tts_max_seq_len', 2048) or 2048),
            )

            loaded_tts[self.tts_key] = engine
            print(f'TTS {self.tts_key} Loaded!')
            return engine
        except Exception as e:
            raise RuntimeError(f'Qwen3TTS.load_engine() error: {e}') from e

    def _resolve_gen_kwargs(self) -> dict:
        """Build the generate() kwargs from tuned defaults + optional session overrides.

        Each key may be overridden via session['qwen3tts_<key>'].  An empty
        string or None falls back to the tuned default.  We never pass None
        through to the upstream `_merge_generate_kwargs` because that would
        re-resurrect the package's permissive defaults (temperature=0.9 etc).
        """
        out = {}
        for key, default in _NARRATION_GEN_DEFAULTS.items():
            session_val = self.session.get(f'qwen3tts_{key}', None)
            if session_val is None or session_val == '':
                out[key] = default
                continue
            try:
                out[key] = type(default)(session_val)
            except (TypeError, ValueError):
                out[key] = default
        return out

    def _seed_torch(self) -> None:
        """Reset the RNG before each generate call.

        Using a fixed seed at the start of every sentence keeps the sampler
        from drifting across sentences: each generate_voice_clone call starts
        from the same RNG state, so timbre/prosody stays consistent over the
        course of an audiobook.  Different texts still produce different
        outputs because input_ids differ — the seed only fixes the sampling
        noise, not the content.
        """
        try:
            import torch
            torch.manual_seed(self._seed)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(self._seed)
        except Exception:
            pass

    def _set_voice(self, voice):
        """Override the XTTS-flavored builtin-speaker path in TTSUtils.

        Qwen3-TTS is zero-shot across all supported languages, so there is no
        cross-language "convert builtin voice" step.  The qwen3tts install
        profile also uninstalls Coqui-TTS, which would make the parent
        implementation crash with `No module named 'TTS'`.  Just pass the
        voice path through unchanged.
        """
        return voice, None

    def _resolve_ref_text(self, voice_path: str) -> str:
        """Return the best available transcript for this voice.

        Lookup order:
          1. session['qwen3tts_ref_text'] — user-supplied via the WebUI.
          2. <voice_path>.transcript.txt — sidecar file (manual or cached
             auto-transcription from a previous run).
          3. faster-whisper auto-transcribe → cache to sidecar → return.
          4. Empty string → caller falls back to x_vector_only_mode.
        """
        # 1. Session override
        user_supplied = (self.session.get('qwen3tts_ref_text') or '').strip()
        if user_supplied:
            return user_supplied

        # 2. Sidecar file
        sidecar = voice_path + '.transcript.txt'
        if os.path.exists(sidecar):
            try:
                with open(sidecar, 'r', encoding='utf-8') as f:
                    cached = f.read().strip()
                if cached:
                    return cached
            except Exception:
                pass

        # 3. faster-whisper auto-transcribe
        model = _get_whisper_model()
        if model is None:
            return ''
        try:
            print(f'[qwen3tts] auto-transcribing {os.path.basename(voice_path)} for voice-clone prompt…')
            segments, _info = model.transcribe(voice_path, beam_size=1)
            text = ' '.join(seg.text.strip() for seg in segments).strip()
            if not text:
                return ''
            try:
                with open(sidecar, 'w', encoding='utf-8') as f:
                    f.write(text)
            except Exception as e:
                print(f'[qwen3tts] could not write sidecar transcript: {e}')
            return text
        except Exception as e:
            print(f'[qwen3tts] auto-transcribe failed: {e}')
            return ''

    def _get_voice_clone_prompt(self, voice_path: str, ref_text: str):
        """Build the voice-clone prompt once per (voice, ref_text) pair.

        Reusing the prompt across every sentence:
          - skips the per-call x-vector + token-feature recomputation
          - removes a source of timbre drift between sentences
        """
        key = (voice_path, ref_text)
        if key in self._voice_prompt_cache:
            return self._voice_prompt_cache[key]
        # x_vector_only_mode is decided inside the backend (off when ref_text
        # is non-empty for full-fidelity ICL, on when empty as a fallback).
        prompt = self._backend.build_prompt(self.engine, voice_path, ref_text)
        self._voice_prompt_cache[key] = prompt
        return prompt

    def convert(self, sentence_file: str, sentence: str, **kwargs) -> tuple:
        try:
            import torch
            import torchaudio
            import numpy as np
            from lib.classes.tts_engines.common.audio import trim_audio, is_audio_data_valid

            if self.engine is None:
                return False, f"TTS engine {self.session['tts_engine']} failed to load!"

            samplerate = self.params['samplerate']
            sentence_parts = self._split_sentence_on_sml(sentence)

            self.params['block_voice'] = kwargs.get('block_voice', self.session['voice'])
            if self.params.get('inline_voice'):
                self.params['current_voice'] = self.params['inline_voice']
            else:
                # Qwen3-TTS is zero-shot: it has no builtin speakers and the
                # qwen3tts install profile uninstalls Coqui-TTS, so the XTTS
                # builtin-speaker fallback in _set_voice() cannot work.
                # Require an explicit voice file up front with a clear error.
                if not (self.params['block_voice'] and os.path.isfile(self.params['block_voice'])):
                    return False, (
                        'Qwen3-TTS requires a reference voice file for zero-shot cloning. '
                        'Please upload a 30–60s WAV in the settings before starting conversion.'
                    )
                self.params['current_voice'] = self.params['block_voice']

            self.audio_segments = []

            # Map iso639-3 language code to Qwen3-TTS language string.
            lang_code = self.session.get('language', 'eng')
            qwen_lang = _LANG_MAP.get(lang_code, 'English')

            current_voice = self.params.get('current_voice') or ''
            if not (current_voice and os.path.isfile(current_voice)):
                return False, (
                    'Qwen3-TTS requires a reference voice file for zero-shot cloning. '
                    'Please select a voice WAV in the settings.'
                )

            # Resolve transcript + build the voice-clone prompt once for the
            # entire convert() call.  Both are cached, so subsequent
            # convert() invocations with the same voice/transcript are free.
            ref_text = self._resolve_ref_text(current_voice)
            voice_clone_prompt = self._get_voice_clone_prompt(current_voice, ref_text)

            for part in sentence_parts:
                part = part.strip()
                if not part:
                    continue
                if SML_TAG_PATTERN.fullmatch(part):
                    success, error = self._convert_sml(part)
                    if not success:
                        return False, error
                    continue
                if not any(c.isalnum() for c in part):
                    continue

                self._seed_torch()
                wavs, sr = self._backend.generate(
                    self.engine,
                    part,
                    qwen_lang,
                    voice_clone_prompt,
                    self._gen_kwargs,
                )

                if not wavs or len(wavs) == 0:
                    return False, 'Qwen3-TTS returned no audio output'

                audio_np = wavs[0]  # numpy array, shape (samples,)

                if not is_audio_data_valid(audio_np):
                    return False, 'Qwen3-TTS audio output is invalid'

                audio_tensor = torch.from_numpy(audio_np).float()  # (samples,)

                part_tensor = audio_tensor.unsqueeze(0)  # → (1, samples)

                # Resample if engine sample rate differs from expected.
                # Kaiser-windowed sinc with a wide lowpass keeps the high-frequency
                # detail that the codec actually produces; torchaudio's defaults
                # use a much narrower kernel that audibly softens sibilants.
                if sr != samplerate:
                    resampler = self.resampler_cache.get((sr, samplerate))
                    if resampler is None:
                        resampler = torchaudio.transforms.Resample(
                            orig_freq=sr,
                            new_freq=samplerate,
                            lowpass_filter_width=64,
                            rolloff=0.945,
                            resampling_method='sinc_interp_kaiser',
                            beta=14.769656459379492,
                        )
                        self.resampler_cache[(sr, samplerate)] = resampler
                    part_tensor = resampler(part_tensor)

                # Trim trailing silence on word-ending parts.
                if part[-1].isalnum() or part[-1] == '—':
                    part_tensor = trim_audio(part_tensor.squeeze(), samplerate, 0.001, 0.006).unsqueeze(0)

                self.audio_segments.append(part_tensor)
                del part_tensor, audio_tensor, audio_np

                # Insert a short silence break after punctuation-terminated parts.
                if not part[-1].isalnum() and part[-1] != '—':
                    silence_time = int(np.random.uniform(0.3, 0.6) * 100) / 100
                    silence_samples = int(samplerate * silence_time)
                    self.audio_segments.append(torch.zeros(1, silence_samples))

            if self.audio_segments:
                import torch as _torch
                segment_tensor = _torch.cat(self.audio_segments, dim=-1)
                torchaudio.save(sentence_file, segment_tensor, samplerate)
                del segment_tensor
                self.audio_segments = []

            return True, None

        except Exception as e:
            self.cleanup_memory()
            return False, f'Qwen3TTS.convert(): {e}'
