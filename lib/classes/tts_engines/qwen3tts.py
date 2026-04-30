from lib.classes.tts_engines.common.headers import *
from lib.classes.tts_engines.common.preset_loader import load_engine_presets

# Qwen3-TTS — zero-shot voice cloning via transformer-based TTS.
# Model weights: Apache 2.0 (commercial use allowed).
# Codebase: Apache 2.0.  https://github.com/QwenLM/Qwen3-TTS
#
# Installation (one-time):
#   pip install -U qwen-tts

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

            # attn_implementation: flash_attention_2 requires separate install;
            # fall back to 'eager' so it works out-of-the-box.
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

                current_voice = self.params.get('current_voice') or ''

                if current_voice and os.path.isfile(current_voice):
                    # Voice clone mode: provide reference audio + empty ref_text
                    # (x-vector-only mode avoids needing a transcript).
                    wavs, sr = self.engine.generate_voice_clone(
                        text=part,
                        language=qwen_lang,
                        ref_audio=current_voice,
                        ref_text='',
                        x_vector_only_mode=True,
                    )
                else:
                    return False, (
                        'Qwen3-TTS requires a reference voice file for zero-shot cloning. '
                        'Please select a voice WAV in the settings.'
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
