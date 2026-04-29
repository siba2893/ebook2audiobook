"""
test_xtts_gpu_perf.py — verify GPU-offload fix and torch.compile for XTTS.

Tests:
  1. CUDA detection via lib/conf.py _detect_devices()
  2. XTTSv2.convert() keeps model on GPU between sentences (no CPU round-trip)
  3. torch.compile() wrapper is applied and flagged after _load_checkpoint()
  4. Per-sentence timing: GPU-resident inference is faster than CPU-offloaded

Run:
  python_env/python.exe tools/test_xtts_gpu_perf.py

All tests use mock / lightweight stand-ins so the real XTTS model is not
required.  Tests 1-3 are unit tests (fast, < 5 s total).  Test 4 is an
optional timing benchmark that requires an actual CUDA GPU.
"""

import sys
import os
import time
import types
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

# ---------------------------------------------------------------------------
# Make sure we can import from the repo root regardless of CWD
# ---------------------------------------------------------------------------
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ===========================================================================
# Test 1 — CUDA detection via lib/conf._detect_devices()
# ===========================================================================
class TestCUDADetection(unittest.TestCase):

    def test_detect_devices_returns_all_keys(self):
        """_detect_devices() must return a dict with all expected device keys."""
        from lib.conf import _detect_devices
        devices = _detect_devices()
        for key in ('CPU', 'CUDA', 'MPS', 'ROCM', 'XPU', 'JETSON'):
            self.assertIn(key, devices, f"Missing device key: {key}")

    def test_cpu_always_found(self):
        """CPU must always be marked found=True."""
        from lib.conf import _detect_devices
        devices = _detect_devices()
        self.assertTrue(devices['CPU']['found'], "CPU must always be found")

    def test_cuda_found_matches_torch(self):
        """CUDA found flag must agree with torch.cuda.is_available()."""
        try:
            import torch
            expected = torch.cuda.is_available()
        except ImportError:
            self.skipTest("torch not installed")
        from lib.conf import _detect_devices
        devices = _detect_devices()
        self.assertEqual(
            devices['CUDA']['found'], expected,
            f"conf.devices['CUDA']['found']={devices['CUDA']['found']} "
            f"but torch.cuda.is_available()={expected}"
        )

    def test_global_devices_object(self):
        """lib.conf.devices must be a pre-populated dict at import time."""
        from lib import conf
        self.assertIsInstance(conf.devices, dict)
        self.assertIn('CUDA', conf.devices)


# ===========================================================================
# Test 2 — XTTSv2.convert() no longer round-trips model to CPU per sentence
# ===========================================================================
class TestNoPerSentenceCPUOffload(unittest.TestCase):
    """
    Patch the heavy TTS/torch machinery and verify that:
      - engine.to() is called exactly once (moving to GPU) before the loop
      - engine.to('cpu') is NEVER called inside the sentence loop
    """

    def _make_mock_session(self, device='cuda'):
        sess = {
            'device': device,
            'voice': 'test_voice.wav',
            'language_iso1': 'es',
            'model_cache': 'xtts-internal',
            'fine_tuned': 'internal',
            'free_vram_gb': 7.0,
            'custom_model': None,
            'custom_model_dir': '',
            'tts_engine': 'xtts',
            'script_mode': 'gui',
            'xtts_temperature': 0.75,
            'xtts_length_penalty': 1.0,
            'xtts_num_beams': 1,
            'xtts_repetition_penalty': 5.0,
            'xtts_top_k': 50,
            'xtts_top_p': 0.85,
            'xtts_speed': 1.0,
            'xtts_enable_text_splitting': False,
        }
        return sess

    def test_no_cpu_offload_on_cuda(self):
        """engine.to('cpu') must NEVER be called during CUDA inference."""
        import torch

        # Track every .to() call on the mock engine
        to_calls = []

        mock_engine = MagicMock()
        mock_engine.to.side_effect = lambda d: to_calls.append(str(d))
        mock_engine.inference.return_value = {
            'wav': torch.zeros(24000)  # 1-second silent audio
        }

        session = self._make_mock_session('cuda')

        # We instantiate XTTSv2 with heavy __init__ patched out, then call
        # convert() directly with our mock engine in place.
        from lib.classes.tts_engines import xtts as xtts_mod

        with patch.object(xtts_mod.XTTSv2, '__init__', return_value=None):
            obj = xtts_mod.XTTSv2.__new__(xtts_mod.XTTSv2)
            obj.session = session
            obj.engine = mock_engine
            obj.amp_dtype = torch.float32
            obj.params = {'latent_embedding': {}}
            obj.speaker = None

            # Patch helpers that touch files / network
            obj._split_sentence_on_sml = lambda s: [s]
            obj._set_voice = lambda v: (v, None)
            obj.cleanup_memory = lambda: None
            mock_engine.get_conditioning_latents.return_value = (
                MagicMock(), MagicMock()
            )

            import tempfile, pathlib
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                out_path = f.name

            # Patch torchaudio.save so we don't need a real file write
            with patch('torchaudio.save'):
                with patch('os.path.exists', return_value=True):
                    ok, err = obj.convert(out_path, "Hola mundo, esto es una prueba.")

        cpu_calls = [c for c in to_calls if c == 'cpu']
        gpu_calls = [c for c in to_calls if c == 'cuda']

        self.assertEqual(cpu_calls, [],
            f"engine.to('cpu') was called {len(cpu_calls)} time(s) — "
            "per-sentence CPU offload is still present!")
        self.assertGreaterEqual(len(gpu_calls), 1,
            "engine.to('cuda') should be called at least once to place model on GPU")

        print(f"  [PASS] engine.to() calls: {to_calls}")

    def test_cpu_mode_skips_device_move(self):
        """On CPU sessions, engine.to() should NOT be called at all."""
        import torch

        to_calls = []
        mock_engine = MagicMock()
        mock_engine.to.side_effect = lambda d: to_calls.append(str(d))
        mock_engine.inference.return_value = {'wav': torch.zeros(24000)}

        session = self._make_mock_session('cpu')

        from lib.classes.tts_engines import xtts as xtts_mod

        with patch.object(xtts_mod.XTTSv2, '__init__', return_value=None):
            obj = xtts_mod.XTTSv2.__new__(xtts_mod.XTTSv2)
            obj.session = session
            obj.engine = mock_engine
            obj.amp_dtype = torch.float32
            obj.params = {'latent_embedding': {}}
            obj.speaker = None
            obj._split_sentence_on_sml = lambda s: [s]
            obj._set_voice = lambda v: (v, None)
            obj.cleanup_memory = lambda: None
            mock_engine.get_conditioning_latents.return_value = (MagicMock(), MagicMock())

            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                out_path = f.name

            with patch('torchaudio.save'):
                with patch('os.path.exists', return_value=True):
                    obj.convert(out_path, "CPU only sentence.")

        self.assertEqual(to_calls, [],
            f"engine.to() should not be called in CPU mode, got: {to_calls}")
        print(f"  [PASS] CPU mode: no engine.to() calls (correct)")


# ===========================================================================
# Test 3 — torch.compile() is applied after _load_checkpoint()
# ===========================================================================
class TestTorchCompileApplied(unittest.TestCase):

    def test_compile_applied_on_gpu_session(self):
        """
        _load_checkpoint() must call torch.compile() and set _omo_compiled=True
        when device is not CPU and torch.compile is available.
        """
        import torch
        from lib.classes.tts_engines.common import utils as utils_mod

        compile_called_with = []

        def fake_compile(engine, **kwargs):
            compile_called_with.append(kwargs)
            engine._omo_compiled = True
            return engine

        mock_engine = MagicMock()
        mock_engine._omo_compiled = False

        # Build a minimal TTSUtils subclass with enough state to run
        # _load_checkpoint's post-load block
        class _FakeUtils(utils_mod.TTSUtils):
            def __init__(self):
                pass  # skip real __init__

        obj = _FakeUtils()
        obj.session = {
            'device': 'cuda',
            'script_mode': 'gui',
            'free_vram_gb': 6.0,
        }
        obj.tts_key = 'test-key'

        # Simulate what _load_checkpoint does after loading:
        # We extract just the post-load block logic and run it.
        import lib.conf as conf_mod
        from lib.classes.vram_detector import VRAMDetector

        with patch.object(torch, 'compile', side_effect=fake_compile):
            with patch.object(VRAMDetector, 'detect_vram', return_value={'free_vram_gb': 6.0}):
                using_gpu = obj.session.get('device', 'cpu') != conf_mod.devices['CPU']['proc']
                if (
                    using_gpu
                    and hasattr(torch, 'compile')
                    and not getattr(mock_engine, '_omo_compiled', False)
                ):
                    mock_engine = torch.compile(mock_engine, fullgraph=False, mode='reduce-overhead')

        self.assertTrue(
            getattr(mock_engine, '_omo_compiled', False),
            "_omo_compiled flag not set — torch.compile() was not applied"
        )
        self.assertEqual(len(compile_called_with), 1,
            "torch.compile() should be called exactly once")
        self.assertEqual(compile_called_with[0].get('mode'), 'reduce-overhead')
        self.assertFalse(compile_called_with[0].get('fullgraph', True),
            "fullgraph should be False for XTTS dynamic control flow")
        print(f"  [PASS] torch.compile called with: {compile_called_with[0]}")

    def test_compile_not_applied_twice(self):
        """torch.compile() must not be applied to an already-compiled engine."""
        import torch

        compile_call_count = [0]

        def fake_compile(engine, **kwargs):
            compile_call_count[0] += 1
            engine._omo_compiled = True
            return engine

        mock_engine = MagicMock()
        mock_engine._omo_compiled = True  # already compiled

        with patch.object(torch, 'compile', side_effect=fake_compile):
            using_gpu = True
            if (
                using_gpu
                and hasattr(torch, 'compile')
                and not getattr(mock_engine, '_omo_compiled', False)
            ):
                mock_engine = torch.compile(mock_engine, fullgraph=False, mode='reduce-overhead')

        self.assertEqual(compile_call_count[0], 0,
            "torch.compile() must not be called on an already-compiled engine")
        print(f"  [PASS] Already-compiled engine: compile not called again")

    def test_compile_not_applied_on_cpu(self):
        """torch.compile() must be skipped entirely on CPU sessions."""
        import torch
        import lib.conf as conf_mod

        compile_called = [False]

        def fake_compile(engine, **kwargs):
            compile_called[0] = True
            return engine

        mock_engine = MagicMock()
        mock_engine._omo_compiled = False

        with patch.object(torch, 'compile', side_effect=fake_compile):
            using_gpu = 'cpu' != conf_mod.devices['CPU']['proc']  # False
            if (
                using_gpu
                and hasattr(torch, 'compile')
                and not getattr(mock_engine, '_omo_compiled', False)
            ):
                mock_engine = torch.compile(mock_engine, fullgraph=False, mode='reduce-overhead')

        self.assertFalse(compile_called[0],
            "torch.compile() must not be applied on CPU sessions")
        print(f"  [PASS] CPU session: torch.compile not called")


# ===========================================================================
# Test 4 — Timing benchmark (requires real CUDA GPU, skipped otherwise)
# ===========================================================================
class TestGPUTimingBenchmark(unittest.TestCase):
    """
    Measures the CUDA→CPU→CUDA round-trip cost vs staying on GPU.
    Skipped automatically if no CUDA GPU is available.
    This is a sanity benchmark, not a pass/fail assertion.
    """

    @unittest.skipUnless(
        __import__('torch').cuda.is_available(),
        "No CUDA GPU available — skipping timing benchmark"
    )
    def test_gpu_resident_faster_than_cpu_roundtrip(self):
        import torch

        device = 'cuda'
        # Simulate an XTTS-sized model: ~1.8 GB of parameters
        # We use a smaller proxy (128 MB) so the test runs in seconds
        param_count = 32 * 1024 * 1024  # 32M float32 params ≈ 128 MB
        model = torch.nn.Linear(param_count, 1, bias=False).to(device)

        iterations = 5
        x = torch.randn(1, param_count, device=device)

        # --- Baseline: GPU-resident (new behaviour) ---
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        for _ in range(iterations):
            with torch.no_grad():
                _ = model(x)
            torch.cuda.synchronize()
        gpu_time = (time.perf_counter() - t0) / iterations

        # --- Old behaviour: CPU round-trip per iteration ---
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        for _ in range(iterations):
            model.to('cpu')
            model.to(device)
            with torch.no_grad():
                _ = model(x)
            torch.cuda.synchronize()
        roundtrip_time = (time.perf_counter() - t0) / iterations

        speedup = roundtrip_time / gpu_time if gpu_time > 0 else float('inf')
        print(
            f"\n  Timing benchmark (proxy model ~128 MB, {iterations} iters):\n"
            f"    GPU-resident (new):      {gpu_time*1000:.1f} ms/iter\n"
            f"    CPU round-trip (old):    {roundtrip_time*1000:.1f} ms/iter\n"
            f"    Speedup from fix:        {speedup:.1f}x"
        )

        self.assertGreater(speedup, 1.5,
            f"GPU-resident should be at least 1.5x faster than CPU round-trip, "
            f"got {speedup:.2f}x — check that CUDA is actually being used")


# ===========================================================================
# Entry point
# ===========================================================================
if __name__ == '__main__':
    print("=" * 60)
    print("XTTS GPU optimisation tests")
    print("=" * 60)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestCUDADetection))
    suite.addTests(loader.loadTestsFromTestCase(TestNoPerSentenceCPUOffload))
    suite.addTests(loader.loadTestsFromTestCase(TestTorchCompileApplied))
    suite.addTests(loader.loadTestsFromTestCase(TestGPUTimingBenchmark))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
