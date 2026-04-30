"""
Performance & Tier 2 Optimization Test Suite
=============================================
Tests WAV format default, DeepSpeed fallback safety, and I/O integrity.
Designed to be resilient to missing/broken torch/torchaudio installs:
  - Tests that need torch/torchaudio are skipped if unavailable.
  - Engine instantiation tests are skipped if models aren't downloaded.
"""

import os
import sys
import time
import unittest
from multiprocessing import Manager

# ---------------------------------------------------------------------------
# Optional dependency guards — import once, used by skipUnless decorators
# ---------------------------------------------------------------------------
try:
    import torch
    _TORCH_AVAILABLE = True
except Exception:
    _TORCH_AVAILABLE = False

try:
    import torchaudio
    _TORCHAUDIO_AVAILABLE = True
except Exception:
    _TORCHAUDIO_AVAILABLE = False

_TORCH_AND_AUDIO = _TORCH_AVAILABLE and _TORCHAUDIO_AVAILABLE

# ---------------------------------------------------------------------------
# Minimal session fixture (no model download triggered at class level)
# ---------------------------------------------------------------------------
def _make_session():
    manager = Manager()
    return manager.dict({
        'model_cache': 'xtts_v2',
        'tts_engine': 'xtts',
        'fine_tuned': 'internal',
        'free_vram_gb': 8.0,
        'device': 'cuda:0',
        'script_mode': 'native',
        'language': 'en',
        'language_iso1': 'en',
        'voice': 'default_voice',
        'custom_model': None,
        'custom_model_dir': '',
        'voice_dir': 'tmp/voices',
        'is_gui_process': False,
        'xtts_temperature': 0.75,
        'xtts_length_penalty': 1.0,
        'xtts_repetition_penalty': 5.0,
        'xtts_top_k': 50,
        'xtts_top_p': 0.85,
        'xtts_speed': 1.0,
        'xtts_enable_text_splitting': True,
    })


class TestPerformanceOptimizations(unittest.TestCase):

    # ------------------------------------------------------------------
    # Tier 2 — WAV default format
    # ------------------------------------------------------------------
    def test_audio_proc_format_is_wav(self):
        """Tier 2: WAV must be the default intermediate audio format."""
        from lib.conf import default_audio_proc_format
        self.assertEqual(
            default_audio_proc_format, 'wav',
            "Intermediate format should be 'wav' for optimal synthesis speed on Windows."
        )

    # ------------------------------------------------------------------
    # Tier 2 — I/O integrity (requires torch + torchaudio)
    # ------------------------------------------------------------------
    @unittest.skipUnless(_TORCH_AVAILABLE, "torch required")
    def test_synthesis_io_integrity(self):
        """
        Verify WAV I/O round-trip is fast after Tier 2 changes.
        Uses torchaudio if available; falls back to soundfile (always present)
        to handle broken torchaudio installations gracefully.
        """
        import numpy as np
        os.makedirs('tmp/perf_tests', exist_ok=True)
        test_file = 'tmp/perf_tests/integrity_test.wav'
        try:
            os.unlink(test_file)
        except FileNotFoundError:
            pass

        sample_rate = 24000
        dummy_audio = torch.randn(1, sample_rate)  # 1 second of noise

        # Prefer torchaudio; fall back to soundfile if torchaudio.save is broken.
        if _TORCHAUDIO_AVAILABLE and hasattr(torchaudio, 'save'):
            # Warm-up call: first save loads torchcodec native libs (~500 ms one-time
            # cost on Windows). Subsequent saves measure steady-state I/O speed.
            torchaudio.save(test_file, dummy_audio, sample_rate)
            start = time.time()
            torchaudio.save(test_file, dummy_audio, sample_rate)
            elapsed = time.time() - start
            self.assertTrue(os.path.exists(test_file), "torchaudio.save failed to create file")
            self.assertLess(elapsed, 0.5, f"WAV save too slow ({elapsed:.3f}s); check I/O contention")
            # torchaudio 2.11 removed torchaudio.info — use soundfile (always available).
            import soundfile as sf
            self.assertEqual(sf.info(test_file).samplerate, sample_rate)
        else:
            import soundfile as sf
            audio_np = dummy_audio.squeeze().numpy().astype(np.float32)
            start = time.time()
            sf.write(test_file, audio_np, sample_rate)
            elapsed = time.time() - start
            self.assertTrue(os.path.exists(test_file), "soundfile.write failed to create file")
            self.assertLess(elapsed, 0.5, f"WAV save too slow ({elapsed:.3f}s); check I/O contention")
            info = sf.info(test_file)
            self.assertEqual(info.samplerate, sample_rate)
            print("Note: Used soundfile fallback — torchaudio.save not available in this environment.")

    # ------------------------------------------------------------------
    # Tier 2 — DeepSpeed: fallback logic present in source
    # ------------------------------------------------------------------
    def test_deepspeed_fallback_logic_in_xtts_source(self):
        """
        Verify DeepSpeed try/except fallback is present in xtts.py without
        actually loading the model.  Uses static source inspection so it
        works even when torch/TTS are unavailable.
        """
        engine_path = os.path.join('lib', 'classes', 'tts_engines', 'xtts.py')
        with open(engine_path, 'r', encoding='utf-8') as f:
            source = f.read()

        self.assertIn('import deepspeed', source,
                      "deepspeed import should be present in xtts.py")
        self.assertIn('deepspeed.init_inference', source,
                      "deepspeed.init_inference call should be present in xtts.py")
        self.assertIn('except ImportError', source,
                      "ImportError fallback for deepspeed should exist in xtts.py")
        self.assertIn('except Exception', source,
                      "General Exception fallback for deepspeed should exist in xtts.py")

    def test_deepspeed_fallback_logic_in_bark_source(self):
        """
        Verify DeepSpeed try/except fallback is present in bark.py without
        actually loading the model.
        Bark catches (ImportError, AttributeError) together since the sub-model
        attribute may not exist on all Bark variants.
        """
        engine_path = os.path.join('lib', 'classes', 'tts_engines', 'bark.py')
        with open(engine_path, 'r', encoding='utf-8') as f:
            source = f.read()

        self.assertIn('import deepspeed', source,
                      "deepspeed import should be present in bark.py")
        self.assertIn('deepspeed.init_inference', source,
                      "deepspeed.init_inference call should be present in bark.py")
        # Bark uses a combined except clause: (ImportError, AttributeError)
        self.assertTrue(
            'except ImportError' in source or 'except (ImportError' in source,
            "ImportError fallback for deepspeed should exist in bark.py"
        )

    # ------------------------------------------------------------------
    # Tier 3 — XTTSv2 hot-path regression guards (static source checks)
    # ------------------------------------------------------------------
    def _read_xtts_source(self):
        engine_path = os.path.join('lib', 'classes', 'tts_engines', 'xtts.py')
        with open(engine_path, 'r', encoding='utf-8') as f:
            return f.read()

    def _read_utils_source(self):
        utils_path = os.path.join('lib', 'classes', 'tts_engines', 'common', 'utils.py')
        with open(utils_path, 'r', encoding='utf-8') as f:
            return f.read()

    def test_xtts_fine_tuned_params_hoisted_out_of_part_loop(self):
        """
        fine_tuned_params is built from session config and is identical for every
        sentence-part.  Building it inside the per-part loop wastes a dict
        comprehension + 8 dict lookups thousands of times per audiobook.
        The dict must come from the shared TTSUtils helper, called exactly once.
        """
        source = self._read_xtts_source()
        self.assertNotIn(
            'fine_tuned_params = {', source,
            "fine_tuned_params dict-comp should not appear inline in xtts.py — "
            "use TTSUtils._build_xtts_fine_tuned_params() instead."
        )
        helper_calls = source.count('self._build_xtts_fine_tuned_params()')
        self.assertEqual(
            helper_calls, 1,
            f"xtts.py should call self._build_xtts_fine_tuned_params() exactly once "
            f"per convert() (found {helper_calls})."
        )

    def test_build_xtts_fine_tuned_params_helper_exists(self):
        """
        The shared helper on TTSUtils replaces the dict-comp duplicated between
        xtts.py and _check_xtts_builtin_speakers.
        """
        utils_source = self._read_utils_source()
        self.assertIn(
            'def _build_xtts_fine_tuned_params(self)', utils_source,
            "TTSUtils must expose a shared _build_xtts_fine_tuned_params helper."
        )
        # _check_xtts_builtin_speakers should also use the helper, not inline a copy.
        helper_calls = utils_source.count('self._build_xtts_fine_tuned_params()')
        self.assertGreaterEqual(
            helper_calls, 1,
            "_check_xtts_builtin_speakers should call _build_xtts_fine_tuned_params()."
        )

    def test_no_engine_cpu_shuffle_in_any_engine(self):
        """
        Across the GPU-resident engines, self.engine[_zs].to(devices['CPU']['proc'])
        must not appear — that pattern is what triggered per-sentence GPU↔CPU
        shuffling.

        Bark is the documented exception: its upstream voice-cloning pipeline
        runs HuBERT on CPU and feeds CPU tensors to GPU sub-models, so the
        model has to be shuffled around each call to avoid
        "Input type FloatTensor and weight type cuda.FloatTensor" mismatches.
        """
        engine_files = [
            'xtts.py', 'vits.py', 'yourtts.py', 'tacotron.py',
            'tortoise.py', 'glowtts.py', 'fairseq.py',
        ]
        offenders = []
        for fname in engine_files:
            path = os.path.join('lib', 'classes', 'tts_engines', fname)
            with open(path, 'r', encoding='utf-8') as f:
                source = f.read()
            if "self.engine.to(devices['CPU']['proc'])" in source:
                offenders.append(f'{fname}: self.engine.to(CPU)')
            if "self.engine_zs.to(devices['CPU']['proc'])" in source:
                offenders.append(f'{fname}: self.engine_zs.to(CPU)')
        self.assertEqual(
            offenders, [],
            f"Per-sentence GPU↔CPU model shuffle reintroduced: {offenders}"
        )

    def test_no_keys_membership_in_engine_hot_paths(self):
        """
        `x in some_dict.keys()` is O(n) on the keys view; `x in some_dict` is
        O(1).  In the per-part hot path of every engine, the latter form must
        be used for the semitones / latent_embedding caches.
        """
        engine_files = [
            'xtts.py', 'vits.py', 'glowtts.py', 'tacotron.py', 'fairseq.py',
        ]
        offenders = []
        for fname in engine_files:
            path = os.path.join('lib', 'classes', 'tts_engines', fname)
            with open(path, 'r', encoding='utf-8') as f:
                source = f.read()
            for needle in (
                "self.params['semitones'].keys()",
                "self.params['latent_embedding'].keys()",
            ):
                if needle in source:
                    offenders.append(f'{fname}: {needle}')
        self.assertEqual(
            offenders, [],
            f"O(n) .keys() membership in engine hot path: {offenders}"
        )

    def test_xtts_engine_to_device_hoisted(self):
        """
        engine.to(device) must NOT appear inside the per-part inference block.
        It should be hoisted once per convert() call, before the for-loop.
        """
        source = self._read_xtts_source()
        # Find the for-part loop body — between 'for part in sentence_parts' and
        # the final 'if self.audio_segments' concat block.
        loop_start = source.find('for part in sentence_parts:')
        save_block = source.find('if self.audio_segments:', loop_start if loop_start > 0 else 0)
        self.assertGreater(loop_start, 0, "Could not locate per-part loop")
        self.assertGreater(save_block, loop_start, "Could not locate save block")
        loop_body = source[loop_start:save_block]
        self.assertNotIn(
            'self.engine.to(device)', loop_body,
            "engine.to(device) leaked back into the per-part loop."
        )
        self.assertNotIn(
            "self.engine.to(devices['CPU']['proc'])", loop_body,
            "engine.to(CPU) leaked back into the per-part loop — this triggers "
            "a per-sentence GPU↔CPU shuffle."
        )

    def test_xtts_amp_enabled_flag_cached(self):
        """
        amp_enabled = (amp_dtype != torch.float32) must be hoisted; the autocast
        line in the per-part block uses the cached flag, not a fresh comparison.
        """
        source = self._read_xtts_source()
        self.assertIn('amp_enabled = (self.amp_dtype != torch.float32)', source,
                      "amp_enabled flag should be hoisted out of the per-part loop")
        self.assertIn('enabled=amp_enabled', source,
                      "autocast() in xtts.py should use the cached amp_enabled flag")

    def test_xtts_inference_mode_used_everywhere(self):
        """
        inference_mode should fully replace no_grad in TTSUtils — no_grad keeps
        version-counter tracking which costs a measurable amount on the hot path.
        """
        utils_source = self._read_utils_source()
        # Allow no_grad references inside comments/docstrings, but no live calls.
        # Strip comments before checking.
        live_lines = [
            line for line in utils_source.splitlines()
            if 'torch.no_grad' in line and not line.strip().startswith('#')
        ]
        self.assertEqual(
            live_lines, [],
            f"torch.no_grad() should be replaced by torch.inference_mode() "
            f"in TTSUtils. Found: {live_lines}"
        )

    def test_split_sentence_on_sml_fast_path(self):
        """
        _split_sentence_on_sml must short-circuit for sentences with no SML
        bracket — the regex finditer is the slowest part of this helper and
        99% of book sentences have no SML at all.
        """
        utils_source = self._read_utils_source()
        # Look for the fast-path guard.
        self.assertIn(
            "'[' not in sentence", utils_source,
            "Missing '[' not in sentence fast-path in _split_sentence_on_sml."
        )

    def test_xtts_silence_cache_present(self):
        """
        Per-sentence allocation of the silence break tensor was ~10-30 KB.  For a
        10000-sentence book that's ~300 MB of churn for tensors that take ~30
        unique values.  Verify the cache exists in the source.
        """
        source = self._read_xtts_source()
        self.assertIn('self._silence_cache', source,
                      "_silence_cache attribute should exist on XTTSv2")
        self.assertIn('self._silence_cache.get(silence_samples)', source,
                      "Per-sentence break tensor should be looked up in _silence_cache")

    def test_xtts_word_end_pattern_module_level(self):
        """
        The trailing-word regex should be compiled once at module load, not on
        every sentence-part.
        """
        source = self._read_xtts_source()
        self.assertIn("_WORD_END_PATTERN = re.compile(r'\\w$')", source,
                      "Module-level _WORD_END_PATTERN should be defined in xtts.py")
        self.assertIn('_WORD_END_PATTERN.search(part)', source,
                      "xtts.py should use the module-level _WORD_END_PATTERN")

    def test_split_sentence_on_sml_behaviour(self):
        """
        Functional check that the fast-path returns the original sentence
        intact and that bracketed input still gets split correctly.
        Uses a stub class so no torch / TTS imports are required.
        """
        # Re-import lightly: TTSUtils only needs SML_TAG_PATTERN at call time.
        from lib.classes.tts_engines.common.utils import TTSUtils
        utils = TTSUtils.__new__(TTSUtils)  # bypass __init__
        # Plain sentence — fast-path
        self.assertEqual(
            utils._split_sentence_on_sml("Hello, world."),
            ["Hello, world."]
        )
        self.assertEqual(utils._split_sentence_on_sml(""), [])
        # SML present — slow path still works
        parts = utils._split_sentence_on_sml("Hello [break] world.")
        self.assertEqual(parts, ["Hello ", "[break]", " world."])

    # ------------------------------------------------------------------
    # Tier 2 — DeepSpeed: runtime instantiation (requires models)
    # ------------------------------------------------------------------
    @unittest.skipUnless(_TORCH_AVAILABLE, "torch required for engine instantiation")
    def test_deepspeed_fallback_safety_xtts(self):
        """
        XTTSv2 must not raise an exception during instantiation even when
        DeepSpeed is missing or misconfigured.  Skipped if model weights
        are not cached locally or if required dependencies (transformers/
        torchvision) are version-mismatched.
        """
        from huggingface_hub import try_to_load_from_cache
        cached = try_to_load_from_cache(
            repo_id='coqui/XTTS-v2',
            filename='config.json',
        )
        if not cached:
            self.skipTest("XTTS-v2 model weights not cached locally — skipping live instantiation test.")

        # Pre-flight: verify TTS can import cleanly (guards against
        # transformers/torchvision version mismatches in the test environment).
        try:
            from TTS.tts.configs.xtts_config import XttsConfig  # noqa: F401
        except Exception as e:
            self.skipTest(f"TTS import failed due to environment mismatch: {e}")

        from lib.classes.tts_engines.xtts import XTTSv2
        session = _make_session()
        try:
            xtts = XTTSv2(session)
            self.assertIsInstance(xtts, XTTSv2)
            print("XTTSv2 instantiated successfully (DeepSpeed fallback path exercised).")
        except Exception as e:
            self.fail(f"XTTSv2 instantiation raised unexpected exception: {e}")

    @unittest.skipUnless(_TORCH_AVAILABLE, "torch required for engine instantiation")
    def test_deepspeed_fallback_safety_bark(self):
        """
        Bark must not raise an exception during instantiation even when
        DeepSpeed is missing or misconfigured.  Skipped if model weights
        are not cached locally.
        """
        from huggingface_hub import try_to_load_from_cache
        cached = try_to_load_from_cache(
            repo_id='suno/bark',
            filename='config.json',
        )
        if not cached:
            self.skipTest("Bark model weights not cached locally — skipping live instantiation test.")

        from lib.classes.tts_engines.bark import Bark
        session = _make_session()
        session['tts_engine'] = 'bark'
        session['model_cache'] = 'bark'
        try:
            bark = Bark(session)
            self.assertIsInstance(bark, Bark)
            print("Bark instantiated successfully (DeepSpeed fallback path exercised).")
        except Exception as e:
            self.fail(f"Bark instantiation raised unexpected exception: {e}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
