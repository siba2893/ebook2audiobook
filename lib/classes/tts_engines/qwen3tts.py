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
            self.engine = self.load_engine()
        except Exception as e:
            raise ValueError(f'Qwen3TTS.__init__() error: {e}') from e

    def load_engine(self) -> Any:
        try:
            engine = loaded_tts.get(self.tts_key)
            if engine is not None:
                print(f'TTS {self.tts_key} model already loaded, reusing cached engine.')
                return engine

            print(f'Loading TTS {self.tts_key} model, it takes a while, please be patient…')
            self.cleanup_memory()

            try:
                from qwen_tts import Qwen3TTSModel
            except ImportError as e:
                raise RuntimeError(
                    f'Qwen3-TTS Python package could not be imported. '
                    f'Install with:\n'
                    f'  pip install -U qwen-tts\n'
                    f'Original error: {e}'
                ) from e

            import torch

            fine_tuned = self.session.get('fine_tuned', 'internal')
            repo = self.models[fine_tuned]['repo']

            is_cuda = self.session['device'] in [
                devices['CUDA']['proc'],
                devices['ROCM']['proc'],
                devices['JETSON']['proc'],
            ]

            device_map = 'cuda:0' if is_cuda else 'cpu'
            dtype = torch.bfloat16 if is_cuda else torch.float32

            try:
                import flash_attn  # noqa: F401
                attn_impl = 'flash_attention_2'
            except ImportError:
                attn_impl = 'eager'

            engine = Qwen3TTSModel.from_pretrained(
                repo,
                device_map=device_map,
                dtype=dtype,
                attn_implementation=attn_impl,
            )

            loaded_tts[self.tts_key] = engine
            print(f'TTS {self.tts_key} Loaded!')
            return engine
        except Exception as e:
            raise RuntimeError(f'Qwen3TTS.load_engine() error: {e}') from e

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
        prompt = self.engine.create_voice_clone_prompt(
            ref_audio=voice_path,
            ref_text=ref_text,
            # x_vector_only_mode=False (full mode) when we have a transcript;
            # x_vector_only_mode=True when we don't (worse fidelity per upstream).
            x_vector_only_mode=not bool(ref_text),
        )
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
                self.params['current_voice'], error = self._set_voice(self.params['block_voice'])
                if self.params['current_voice'] is None and error is not None:
                    return False, error
                if self.session['voice'] == self.params['block_voice']:
                    self.session['voice'] = self.params['current_voice']
                self.params['block_voice'] = self.params['current_voice']

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

                wavs, sr = self.engine.generate_voice_clone(
                    text=part,
                    language=qwen_lang,
                    voice_clone_prompt=voice_clone_prompt,
                )

                if not wavs or len(wavs) == 0:
                    return False, 'Qwen3-TTS returned no audio output'

                audio_np = wavs[0]  # numpy array, shape (samples,)

                if not is_audio_data_valid(audio_np):
                    return False, 'Qwen3-TTS audio output is invalid'

                audio_tensor = torch.from_numpy(audio_np).float()  # (samples,)

                part_tensor = audio_tensor.unsqueeze(0)  # → (1, samples)

                # Resample if engine sample rate differs from expected.
                if sr != samplerate:
                    resampler = self.resampler_cache.get((sr, samplerate))
                    if resampler is None:
                        resampler = torchaudio.transforms.Resample(
                            orig_freq=sr, new_freq=samplerate
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
