from lib.classes.tts_engines.common.headers import *
from lib.classes.tts_engines.common.preset_loader import load_engine_presets

# CosyVoice 2 / 3 — zero-shot voice cloning with optional instruct mode.
# Model weights: Apache 2.0 (commercial use allowed).
# Codebase: Apache 2.0.  https://github.com/FunAudioLLM/CosyVoice
#
# Installation (one-time):
#   cd C:\ebook2audiobook
#   git clone --recursive https://github.com/FunAudioLLM/CosyVoice third_party/CosyVoice
#   pip install -r third_party/CosyVoice/requirements.txt
#   # Then restore pinned project deps:
#   pip install "numpy>=2.0" "pydantic>=2.10" "fsspec>=2024.6"

_COSYVOICE_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', 'third_party', 'CosyVoice')
)
_MATCHA_PATH = os.path.join(_COSYVOICE_PATH, 'third_party', 'Matcha-TTS')


class CosyVoice(TTSUtils, TTSRegistry, name='cosyvoice'):

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
            raise ValueError(f'CosyVoice.__init__() error: {e}') from e

    def load_engine(self) -> Any:
        try:
            engine = loaded_tts.get(self.tts_key)
            if engine is not None:
                print(f'TTS {self.tts_key} model already loaded, reusing cached engine.')
                return engine

            print(f'Loading TTS {self.tts_key} model, it takes a while, please be patient…')
            self.cleanup_memory()

            # Inject CosyVoice repo and its Matcha-TTS submodule onto sys.path.
            # Both paths must be present before any cosyvoice import is attempted.
            if not os.path.isdir(_COSYVOICE_PATH):
                raise RuntimeError(
                    f'CosyVoice is not installed at {_COSYVOICE_PATH}. '
                    f'Clone with:\n'
                    f'  git clone --recursive https://github.com/FunAudioLLM/CosyVoice '
                    f'third_party/CosyVoice\n'
                    f'  pip install -r third_party/CosyVoice/requirements.txt'
                )
            if not os.path.isdir(_MATCHA_PATH):
                raise RuntimeError(
                    f'Matcha-TTS submodule missing at {_MATCHA_PATH}. '
                    f'Run: git submodule update --init --recursive inside third_party/CosyVoice'
                )

            for p in (_COSYVOICE_PATH, _MATCHA_PATH):
                if p not in sys.path:
                    sys.path.insert(0, p)

            try:
                from cosyvoice.cli.cosyvoice import AutoModel
            except ImportError as e:
                raise RuntimeError(
                    f'CosyVoice Python package could not be imported. '
                    f'Install requirements with:\n'
                    f'  pip install -r third_party/CosyVoice/requirements.txt\n'
                    f'Original error: {e}'
                ) from e

            from huggingface_hub import snapshot_download
            import torch

            fine_tuned = self.session.get('fine_tuned', 'internal')
            repo = self.models[fine_tuned]['repo']

            model_dir = snapshot_download(
                repo_id=repo,
                cache_dir=self.cache_dir,
                ignore_patterns=['*.md', '*.txt', 'LICENSE'],
            )

            is_cuda = self.session['device'] in [
                devices['CUDA']['proc'],
                devices['ROCM']['proc'],
                devices['JETSON']['proc'],
            ]

            # fp16 on GPU saves ~30-40 % VRAM with minimal quality loss.
            # vLLM acceleration requires a separate vLLM install; skip by default
            # so the engine works out-of-the-box without extra setup.
            engine = AutoModel(
                model_dir=model_dir,
                fp16=is_cuda,
                load_vllm=False,
                load_trt=False,
            )

            loaded_tts[self.tts_key] = engine
            print(f'TTS {self.tts_key} Loaded!')
            return engine
        except Exception as e:
            raise RuntimeError(f'CosyVoice.load_engine() error: {e}') from e

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

            # Pull CosyVoice-specific params from session (fall back to defaults).
            cv_speed = float(
                self.session.get('cosyvoice_speed',
                                 default_engine_settings[TTS_ENGINES['COSYVOICE']]['speed'])
            )
            cv_instruct = str(
                self.session.get('cosyvoice_instruct_text',
                                 default_engine_settings[TTS_ENGINES['COSYVOICE']]['instruct_text'])
            ).strip()

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

                # Choose inference mode:
                #   instruct2 when instruct_text is set (CosyVoice2/3 only)
                #   zero_shot  otherwise (all models)
                if cv_instruct and current_voice and os.path.isfile(current_voice):
                    outputs = list(self.engine.inference_instruct2(
                        tts_text=part,
                        instruct_text=cv_instruct,
                        prompt_wav=current_voice,
                        stream=False,
                        speed=cv_speed,
                    ))
                elif current_voice and os.path.isfile(current_voice):
                    outputs = list(self.engine.inference_zero_shot(
                        tts_text=part,
                        prompt_text='',
                        prompt_wav=current_voice,
                        stream=False,
                        speed=cv_speed,
                    ))
                else:
                    # No reference audio — fall back to first available SFT speaker if any,
                    # otherwise inference_zero_shot will error; surface a clear message.
                    spks = self.engine.list_available_spks() if hasattr(self.engine, 'list_available_spks') else []
                    if spks:
                        outputs = list(self.engine.inference_sft(
                            tts_text=part,
                            spk_id=spks[0],
                            stream=False,
                            speed=cv_speed,
                        ))
                    else:
                        return False, (
                            'CosyVoice requires a reference voice file for zero-shot cloning. '
                            'Please select a voice WAV in the settings.'
                        )

                if not outputs:
                    return False, 'CosyVoice returned no audio output'

                # Concatenate all output chunks (usually one for non-streaming).
                chunks = [o['tts_speech'].squeeze(0) for o in outputs]
                audio_tensor = torch.cat(chunks, dim=-1).float()  # shape: (samples,)

                if not is_audio_data_valid(audio_tensor.numpy()):
                    return False, 'CosyVoice audio output is invalid'

                part_tensor = audio_tensor.unsqueeze(0)  # → (1, samples)

                # Trim trailing silence on word-ending parts (mirrors XTTS behaviour).
                if part[-1].isalnum() or part[-1] == '—':
                    part_tensor = trim_audio(part_tensor.squeeze(), samplerate, 0.001, 0.006).unsqueeze(0)

                self.audio_segments.append(part_tensor)
                del part_tensor, audio_tensor, chunks

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
            return False, f'CosyVoice.convert(): {e}'
