from lib.classes.tts_engines.common.headers import *
from lib.classes.tts_engines.common.preset_loader import load_engine_presets

# F5-TTS — flow-matching TTS with zero-shot voice cloning.
# Model weights: SWivid/F5-TTS (CC-BY-NC-4.0, non-commercial use only).
# Codebase: MIT.  https://github.com/SWivid/F5-TTS
#
# Quality levers tuned here, in order of fidelity impact:
#   1. ref_text (transcript of the reference audio).  F5-TTS REQUIRES a
#      transcript — unlike qwen3tts there is no x_vector_only_mode fallback.
#      We resolve ref_text from, in order: session override → sidecar
#      `<voice>.transcript.txt` → faster-whisper auto-transcribe (cached to
#      sidecar on first use).  Empty transcript = engine returns a clear
#      error before launching the model.
#   2. nfe_step (number of function evaluations) is upstream-default 32.
#      Lower (16) = ~2x faster but audibly less stable across an audiobook;
#      higher (>32) gives diminishing returns and the upstream README says
#      32 is well-tuned for the released checkpoint.
#   3. cfg_strength (classifier-free guidance) at 2.0 is the upstream default
#      and behaves well for narration.  Higher values over-emphasise the
#      reference and can introduce metallic timbre.
#   4. torch.manual_seed is set before each infer call so the sampler starts
#      from the same RNG state every sentence — same input, same output, with
#      no cross-sentence randomness leaking through.

# Tuned generation defaults for narration.  Each may be overridden via
# session['f5tts_<key>'] (no UI exposure today; mirror qwen3tts wiring if
# you ever surface them).
#
# `speed` is dropped from the package default 1.0 to 0.85: F5-TTS calibrates
# its output speech rate to the reference clip, and the upstream-trimmed clip
# tends to land on the fast end of the source's pacing — narration sounds
# rushed at speed=1.0.  0.85 is steady, audiobook-paced.
_NARRATION_GEN_DEFAULTS = {
    'nfe_step': 32,
    'cfg_strength': 2.0,
    'speed': 0.85,
}
_NARRATION_SEED_DEFAULT = 0

# F5-TTS supports English + Chinese out of the box (Emilia ZH-EN training).
# For Spanish we swap in jpgallegoar/F5-Spanish — a community fine-tune
# trained on Voxpopuli/TEDx (218h, cc0-1.0).  It uses the older F5TTS_Base
# architecture (NOT v1), needs explicit ckpt_file + vocab_file, and ships
# its own Spanish phoneme vocab.
_LANG_MAP = {
    'eng': 'en',
    'zho': 'zh',
    'spa': 'es',
}

# Spanish fine-tune from https://huggingface.co/jpgallegoar/F5-Spanish.
# Architecture: F5TTS_Base (v0), NOT F5TTS_v1_Base.  Use latest checkpoint
# (model_1250000.safetensors) — same iteration count as the SWivid base.
_SPANISH_HF_REPO = 'jpgallegoar/F5-Spanish'
_SPANISH_CKPT = 'model_1250000.safetensors'
_SPANISH_VOCAB = 'vocab.txt'
_SPANISH_MODEL_PRESET = 'F5TTS_Base'


class F5TTS(TTSUtils, TTSRegistry, name='f5tts'):

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
            enough_vram = self.session['free_vram_gb'] > 3.0
            self.amp_dtype = self._apply_gpu_policy(enough_vram=enough_vram, seed=0)
            self._gen_kwargs = self._resolve_gen_kwargs()
            self._seed = int(self.session.get('f5tts_seed', _NARRATION_SEED_DEFAULT) or 0)
            self._ref_cache = {}
            self.engine = self.load_engine()
        except Exception as e:
            raise ValueError(f'F5TTS.__init__() error: {e}') from e

    def load_engine(self) -> Any:
        try:
            # F5-TTS picks a different checkpoint per language (the SWivid
            # base is en+zh only; Spanish needs the jpgallegoar fine-tune
            # built on the older F5TTS_Base arch).  Bake language into the
            # cache key so a session that switches language gets a fresh
            # model, instead of reusing whichever loaded first.
            lang = (self.session.get('language') or 'eng').lower()
            cache_key = f'{self.tts_key}-{lang}'

            engine = loaded_tts.get(cache_key)
            if engine is not None:
                print(f'TTS {cache_key} model already loaded, reusing cached engine.')
                return engine

            print(f'Loading TTS {cache_key} model, it takes a while, please be patient…')
            self.cleanup_memory()

            try:
                from f5_tts.api import F5TTS as _F5TTSModel
            except ImportError as e:
                raise RuntimeError(
                    f'F5-TTS Python package could not be imported. '
                    f'Install with:\n'
                    f'  pip install -U f5-tts\n'
                    f'Original error: {e}'
                ) from e

            import torch

            is_cuda = self.session['device'] in [
                devices['CUDA']['proc'],
                devices['ROCM']['proc'],
                devices['JETSON']['proc'],
            ]
            device = 'cuda' if is_cuda and torch.cuda.is_available() else 'cpu'

            if lang == 'spa':
                # Spanish: load the jpgallegoar/F5-Spanish community fine-tune.
                # Built on the F5TTS_Base (v0) arch with a Spanish vocab,
                # so we MUST pass model='F5TTS_Base' AND explicit ckpt+vocab.
                from huggingface_hub import hf_hub_download
                ckpt_path = hf_hub_download(repo_id=_SPANISH_HF_REPO, filename=_SPANISH_CKPT)
                vocab_path = hf_hub_download(repo_id=_SPANISH_HF_REPO, filename=_SPANISH_VOCAB)
                engine = _F5TTSModel(
                    model=_SPANISH_MODEL_PRESET,
                    ckpt_file=ckpt_path,
                    vocab_file=vocab_path,
                    device=device,
                )
            else:
                engine = _F5TTSModel(
                    model=self.models[self.session.get('fine_tuned', 'internal')]['repo'],
                    device=device,
                )

            loaded_tts[cache_key] = engine
            print(f'TTS {cache_key} Loaded!')
            return engine
        except Exception as e:
            raise RuntimeError(f'F5TTS.load_engine() error: {e}') from e

    def _resolve_gen_kwargs(self) -> dict:
        """Build the infer() kwargs from tuned defaults + optional session overrides."""
        out = {}
        for key, default in _NARRATION_GEN_DEFAULTS.items():
            session_val = self.session.get(f'f5tts_{key}', None)
            if session_val is None or session_val == '':
                out[key] = default
                continue
            try:
                out[key] = type(default)(session_val)
            except (TypeError, ValueError):
                out[key] = default
        return out

    def _seed_torch(self) -> None:
        try:
            import torch
            torch.manual_seed(self._seed)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(self._seed)
        except Exception:
            pass

    def _set_voice(self, voice):
        """Override the XTTS-flavored builtin-speaker path in TTSUtils.

        F5-TTS is zero-shot and has no builtin speakers; the f5tts install
        profile also uninstalls Coqui-TTS, which would make the parent
        implementation crash with `No module named 'TTS'`.  Pass through.
        """
        return voice, None

    def _resolve_ref_audio_and_text(self, voice_path: str) -> tuple:
        """Return a (preprocessed_audio_path, transcript) pair via F5-TTS's
        canonical preprocessing helper, cached per-voice on the instance so
        the per-sentence loop pays the cost only once per conversion job.

        Why use upstream's helper instead of our own faster-whisper call:
          - F5-TTS bundles `whisper-large-v3-turbo` for ASR, much more
            accurate than the `small` model qwen3tts uses; transcript errors
            cascade into phoneme misalignment and gibberish output.
          - It also runs VAD-based silence trimming so the audio is clipped
            to <12s using natural speech boundaries — matching what the
            model was trained on.  Our 11.9s ref clips are borderline and
            the trim point matters for prosody/pacing alignment.
          - Returning both halves of the pair from one call guarantees the
            transcript matches the *trimmed* audio, not the original.

        Lookup order:
          1. session['f5tts_ref_text'] — user-supplied via the WebUI.
          2. <voice_path>.transcript.txt — sidecar (manual or cached from
             a prior preprocess call).
          3. F5-TTS preprocess_ref_audio_text(ref_text='') — auto-transcribes
             via whisper-large-v3-turbo, caches result to sidecar.
          4. Empty string → caller returns an error.

        The returned audio path may be a temp file produced by the upstream
        VAD trim step; passing it back into `infer()` hits F5-TTS's internal
        hash cache and avoids re-preprocessing on every sentence.
        """
        user_supplied = (self.session.get('f5tts_ref_text') or '').strip()
        cache_key = (voice_path, user_supplied)
        cached = self._ref_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            from f5_tts.infer.utils_infer import preprocess_ref_audio_text
        except ImportError:
            return voice_path, ''

        sidecar = voice_path + '.transcript.txt'
        if not user_supplied and os.path.exists(sidecar):
            try:
                with open(sidecar, 'r', encoding='utf-8') as f:
                    user_supplied = f.read().strip()
            except Exception:
                pass

        try:
            processed_path, processed_text = preprocess_ref_audio_text(
                voice_path,
                user_supplied,
                show_info=lambda *_a, **_kw: None,
            )
        except Exception as e:
            print(f'[f5tts] preprocess_ref_audio_text failed: {e}')
            return voice_path, user_supplied

        processed_text = (processed_text or '').strip()

        # Cache the high-quality transcript next to the source WAV so
        # subsequent runs skip the whisper-large-v3-turbo call entirely.
        if processed_text and not user_supplied:
            try:
                with open(sidecar, 'w', encoding='utf-8') as f:
                    f.write(processed_text)
            except Exception as e:
                print(f'[f5tts] could not write sidecar transcript: {e}')

        result = (processed_path, processed_text)
        self._ref_cache[cache_key] = result
        return result

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
                if not (self.params['block_voice'] and os.path.isfile(self.params['block_voice'])):
                    return False, (
                        'F5-TTS requires a reference voice file for zero-shot cloning. '
                        'Please upload a 10–30s WAV in the settings before starting conversion.'
                    )
                self.params['current_voice'] = self.params['block_voice']

            self.audio_segments = []

            current_voice = self.params.get('current_voice') or ''
            if not (current_voice and os.path.isfile(current_voice)):
                return False, (
                    'F5-TTS requires a reference voice file for zero-shot cloning. '
                    'Please select a voice WAV in the settings.'
                )

            ref_audio_path, ref_text = self._resolve_ref_audio_and_text(current_voice)
            if not ref_text:
                return False, (
                    'F5-TTS requires a transcript of the reference voice. '
                    'Auto-transcription failed and no transcript was provided. '
                    'Add one in the settings or place a <voice>.transcript.txt sidecar.'
                )

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
                wav, sr, _spec = self.engine.infer(
                    ref_file=ref_audio_path,
                    ref_text=ref_text,
                    gen_text=part,
                    seed=self._seed,
                    **self._gen_kwargs,
                )

                if wav is None or len(wav) == 0:
                    return False, 'F5-TTS returned no audio output'

                audio_np = wav

                if not is_audio_data_valid(audio_np):
                    return False, 'F5-TTS audio output is invalid'

                audio_tensor = torch.from_numpy(audio_np).float()
                part_tensor = audio_tensor.unsqueeze(0)

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

                if part[-1].isalnum() or part[-1] == '—':
                    part_tensor = trim_audio(part_tensor.squeeze(), samplerate, 0.001, 0.006).unsqueeze(0)

                self.audio_segments.append(part_tensor)
                del part_tensor, audio_tensor, audio_np

                if not part[-1].isalnum() and part[-1] != '—':
                    silence_time = int(np.random.uniform(0.3, 0.6) * 100) / 100
                    silence_samples = int(samplerate * silence_time)
                    self.audio_segments.append(torch.zeros(1, silence_samples))

            if self.audio_segments:
                segment_tensor = torch.cat(self.audio_segments, dim=-1)
                torchaudio.save(sentence_file, segment_tensor, samplerate)
                del segment_tensor
                self.audio_segments = []

            return True, None

        except Exception as e:
            self.cleanup_memory()
            return False, f'F5TTS.convert(): {e}'
