from lib.classes.tts_engines.common.headers import *
from lib.classes.tts_engines.common.preset_loader import load_engine_presets

# Fish Speech 1.5 — zero-shot voice cloning via in-context learning.
# Model weights licensed under CC-BY-NC-SA-4.0 (non-commercial use only).
# Codebase: Apache 2.0.  https://github.com/fishaudio/fish-speech


class FishSpeech(TTSUtils, TTSRegistry, name='fishspeech'):

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
            raise ValueError(f'FishSpeech.__init__() error: {e}') from e

    def load_engine(self) -> Any:
        try:
            engine = loaded_tts.get(self.tts_key)
            if engine is not None:
                print(f'TTS {self.tts_key} model already loaded, reusing cached engine.')
                return engine

            print(f'Loading TTS {self.tts_key} model, it takes a while, please be patient…')
            self.cleanup_memory()

            try:
                from fish_speech.models.dac.inference import load_model as load_decoder_model
                from fish_speech.models.text2semantic.inference import launch_thread_safe_queue
                from fish_speech.inference_engine import TTSInferenceEngine
            except ImportError as e:
                raise RuntimeError(
                    f'Fish Speech is not installed. '
                    f'Install with: pip install git+https://github.com/fishaudio/fish-speech.git@v1.5.1\n'
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

            device = (
                devices['CUDA']['proc']
                if self.session['device'] in [
                    devices['CUDA']['proc'],
                    devices['ROCM']['proc'],
                    devices['JETSON']['proc'],
                ]
                else self.session['device']
            )

            # Use bfloat16 on CUDA where supported, float16 elsewhere, float32 on CPU.
            precision = self.amp_dtype if self.amp_dtype != torch.float32 else torch.float16
            if device == devices['CPU']['proc']:
                precision = torch.float32

            # compile=True gives ~10x throughput but adds ~30 s warmup on first call.
            # Triton (required by torch.compile) is not available on Windows or macOS.
            use_compile = (
                device != devices['CPU']['proc']
                and sys.platform not in ('win32', 'darwin')
            )

            llama_queue = launch_thread_safe_queue(
                checkpoint_path=model_dir,
                device=device,
                precision=precision,
                compile=use_compile,
            )

            decoder_checkpoint = os.path.join(
                model_dir,
                self.models[fine_tuned]['files'][1],
            )
            decoder_model = load_decoder_model(
                config_name='firefly_gan_vq',
                checkpoint_path=decoder_checkpoint,
                device=device,
            )

            engine = TTSInferenceEngine(
                llama_queue=llama_queue,
                decoder_model=decoder_model,
                precision=precision,
                compile=use_compile,
            )

            loaded_tts[self.tts_key] = engine
            print(f'TTS {self.tts_key} Loaded!')
            return engine
        except Exception as e:
            raise RuntimeError(f'FishSpeech.load_engine() error: {e}') from e

    def convert(self, sentence_file: str, sentence: str, **kwargs) -> tuple:
        try:
            import torch
            import torchaudio
            import numpy as np
            from fish_speech.utils.schema import ServeTTSRequest, ServeReferenceAudio
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

                # Build reference audio bytes for in-context voice cloning.
                references = []
                current_voice = self.params.get('current_voice')
                if current_voice and os.path.isfile(current_voice):
                    with open(current_voice, 'rb') as f:
                        ref_bytes = f.read()
                    references = [ServeReferenceAudio(audio=ref_bytes, text='')]

                request = ServeTTSRequest(
                    text=part,
                    references=references,
                    reference_id=None,
                    max_new_tokens=default_engine_settings[TTS_ENGINES['FISHSPEECH']]['max_new_tokens'],
                    top_p=default_engine_settings[TTS_ENGINES['FISHSPEECH']]['top_p'],
                    temperature=default_engine_settings[TTS_ENGINES['FISHSPEECH']]['temperature'],
                    repetition_penalty=default_engine_settings[TTS_ENGINES['FISHSPEECH']]['repetition_penalty'],
                    seed=None,
                    format='wav',
                    streaming=False,
                )

                audio_chunks = []
                with torch.inference_mode():
                    for result in self.engine.inference(request):
                        if result.code == 'header':
                            continue
                        elif result.code == 'data':
                            # result.audio is (sample_rate, np.ndarray)
                            _, chunk = result.audio
                            audio_chunks.append(chunk)
                        elif result.code == 'error':
                            return False, f'FishSpeech inference error: {result.error}'

                if not audio_chunks:
                    return False, 'FishSpeech returned no audio chunks'

                audio_np = np.concatenate(audio_chunks).astype(np.float32)

                if not is_audio_data_valid(audio_np):
                    return False, 'FishSpeech audio output is invalid'

                part_tensor = self._tensor_type(audio_np).unsqueeze(0)
                if part_tensor is None or part_tensor.numel() == 0:
                    return False, 'FishSpeech part_tensor is empty'

                # Trim trailing silence on word-ending parts (mirrors XTTS behaviour).
                if part[-1].isalnum() or part[-1] == '—':
                    part_tensor = trim_audio(part_tensor.squeeze(), samplerate, 0.001, 0.006).unsqueeze(0)

                self.audio_segments.append(part_tensor)
                del part_tensor

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
            return False, f'FishSpeech.convert(): {e}'
