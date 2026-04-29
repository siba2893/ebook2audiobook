"""
Static-source and smoke tests for the Fish Speech 1.5 engine integration.

Tests are split into two groups:
  - Static source checks (always run): verify code structure, registry, conf changes.
  - Live inference test (skipped unless fish-speech is installed and models cached).

Run:
    python tools/test_fishspeech.py
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestFishSpeechRegistration(unittest.TestCase):
    """Fish Speech is correctly wired into the engine registry and conf."""

    def test_fishspeech_in_tts_engines(self):
        from lib.conf_models import TTS_ENGINES
        self.assertIn('FISHSPEECH', TTS_ENGINES, "FISHSPEECH key missing from TTS_ENGINES")
        self.assertEqual(TTS_ENGINES['FISHSPEECH'], 'fishspeech')

    def test_fishspeech_in_default_engine_settings(self):
        from lib.conf_models import TTS_ENGINES, default_engine_settings
        key = TTS_ENGINES['FISHSPEECH']
        self.assertIn(key, default_engine_settings, "fishspeech missing from default_engine_settings")

    def test_fishspeech_settings_required_keys(self):
        from lib.conf_models import TTS_ENGINES, default_engine_settings
        settings = default_engine_settings[TTS_ENGINES['FISHSPEECH']]
        for required in ('repo', 'samplerate', 'files', 'voice', 'temperature', 'top_p', 'repetition_penalty', 'max_new_tokens'):
            self.assertIn(required, settings, f"Missing key '{required}' in fishspeech settings")

    def test_fishspeech_samplerate(self):
        from lib.conf_models import TTS_ENGINES, default_engine_settings
        sr = default_engine_settings[TTS_ENGINES['FISHSPEECH']]['samplerate']
        self.assertEqual(sr, 24000, f"Expected samplerate 24000, got {sr}")

    def test_fishspeech_files_count(self):
        from lib.conf_models import TTS_ENGINES, default_engine_settings
        files = default_engine_settings[TTS_ENGINES['FISHSPEECH']]['files']
        self.assertEqual(len(files), 2, f"Expected 2 files (model.pth + decoder), got {len(files)}")

    def test_fishspeech_registry_class_importable(self):
        from lib.classes.tts_engines.fishspeech import FishSpeech
        from lib.classes.tts_registry import TTSRegistry
        self.assertIn('fishspeech', TTSRegistry.ENGINES,
                      "FishSpeech not registered in TTSRegistry.ENGINES after import")
        self.assertIs(TTSRegistry.ENGINES['fishspeech'], FishSpeech)

    def test_fishspeech_in_engines_init(self):
        # Importing the engines package should register fishspeech automatically.
        import lib.classes.tts_engines  # noqa: F401
        from lib.classes.tts_registry import TTSRegistry
        self.assertIn('fishspeech', TTSRegistry.ENGINES)

    def test_fishspeech_preset_file_has_internal_model(self):
        from lib.classes.tts_engines.presets.fishspeech_presets import models
        self.assertIn('internal', models)
        internal = models['internal']
        for key in ('repo', 'samplerate', 'files', 'voice'):
            self.assertIn(key, internal, f"fishspeech_presets.internal missing '{key}'")

    def test_fishspeech_inherits_ttsutils(self):
        from lib.classes.tts_engines.fishspeech import FishSpeech
        from lib.classes.tts_engines.common.utils import TTSUtils
        self.assertTrue(issubclass(FishSpeech, TTSUtils))

    def test_fishspeech_inherits_ttsregistry(self):
        from lib.classes.tts_engines.fishspeech import FishSpeech
        from lib.classes.tts_registry import TTSRegistry
        self.assertTrue(issubclass(FishSpeech, TTSRegistry))

    def test_fishspeech_convert_method_signature(self):
        import inspect
        from lib.classes.tts_engines.fishspeech import FishSpeech
        sig = inspect.signature(FishSpeech.convert)
        params = list(sig.parameters.keys())
        self.assertIn('sentence_file', params)
        self.assertIn('sentence', params)
        self.assertIn('kwargs', params)

    def test_no_engine_cpu_shuffle_in_fishspeech(self):
        """FishSpeech must NOT call .to('cpu') per sentence (GPU-resident pattern)."""
        import ast
        engine_path = os.path.join(
            os.path.dirname(__file__), '..', 'lib', 'classes', 'tts_engines', 'fishspeech.py'
        )
        src = open(engine_path, encoding='utf-8').read()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr == 'to':
                    for arg in node.args:
                        if isinstance(arg, ast.Constant) and arg.value == 'cpu':
                            self.fail(
                                f"fishspeech.py line {node.lineno}: found .to('cpu') — "
                                "model must stay GPU-resident"
                            )


@unittest.skipUnless(
    os.environ.get('FISHSPEECH_LIVE_TEST') == '1',
    "Set FISHSPEECH_LIVE_TEST=1 to run live inference test (requires fish-speech installed + model cached)"
)
class TestFishSpeechLiveInference(unittest.TestCase):
    """End-to-end inference smoke test — requires fish-speech + cached weights."""

    def setUp(self):
        try:
            import fish_speech  # noqa: F401
        except ImportError:
            self.skipTest("fish-speech not installed")

    def test_synthesize_short_sentence(self):
        import tempfile
        import soundfile as sf
        from multiprocessing.managers import DictProxy
        from multiprocessing import Manager

        # Minimal session dict mirroring what the app builds.
        with Manager() as mgr:
            session = mgr.dict({
                'device': 'cpu',
                'tts_engine': 'fishspeech',
                'fine_tuned': 'internal',
                'model_cache': 'fishspeech-internal',
                'custom_model': None,
                'custom_model_dir': '',
                'voice': None,
                'language': 'eng',
                'language_iso1': 'en',
                'free_vram_gb': 0.0,
                'script_mode': 'native',
                'is_gui_process': False,
                'process_dir': tempfile.gettempdir(),
            })

            from lib.classes.tts_engines.fishspeech import FishSpeech
            engine = FishSpeech(session)

            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                out_path = f.name

            try:
                ok, err = engine.convert(out_path, 'Hello, this is a Fish Speech test.', block_voice=None)
                self.assertTrue(ok, f"convert() returned False: {err}")
                self.assertTrue(os.path.isfile(out_path), "Output WAV not created")
                info = sf.info(out_path)
                self.assertGreater(info.duration, 0.1, "Output audio too short")
                self.assertEqual(info.samplerate, 24000)
            finally:
                try:
                    os.unlink(out_path)
                except FileNotFoundError:
                    pass


if __name__ == '__main__':
    unittest.main(verbosity=2)
