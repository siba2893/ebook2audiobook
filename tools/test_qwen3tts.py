"""
Static-source and smoke tests for the Qwen3-TTS engine integration.

Tests are split into two groups:
  - Static source checks (always run): verify code structure, registry, conf changes.
  - Live inference test (skipped unless qwen-tts is installed and models cached).

Run:
    python tools/test_qwen3tts.py
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestQwen3TTSRegistration(unittest.TestCase):
    """Qwen3-TTS is correctly wired into the engine registry and conf."""

    def test_qwen3tts_in_tts_engines(self):
        from lib.conf_models import TTS_ENGINES
        self.assertIn('QWEN3TTS', TTS_ENGINES, "QWEN3TTS key missing from TTS_ENGINES")
        self.assertEqual(TTS_ENGINES['QWEN3TTS'], 'qwen3tts')

    def test_qwen3tts_in_default_engine_settings(self):
        from lib.conf_models import TTS_ENGINES, default_engine_settings
        key = TTS_ENGINES['QWEN3TTS']
        self.assertIn(key, default_engine_settings, "qwen3tts missing from default_engine_settings")

    def test_qwen3tts_settings_required_keys(self):
        from lib.conf_models import TTS_ENGINES, default_engine_settings
        settings = default_engine_settings[TTS_ENGINES['QWEN3TTS']]
        for required in ('repo', 'samplerate', 'voice'):
            self.assertIn(required, settings, f"Missing key '{required}' in qwen3tts settings")

    def test_qwen3tts_samplerate(self):
        from lib.conf_models import TTS_ENGINES, default_engine_settings
        sr = default_engine_settings[TTS_ENGINES['QWEN3TTS']]['samplerate']
        self.assertEqual(sr, 24000, f"Expected samplerate 24000, got {sr}")

    def test_qwen3tts_repo(self):
        from lib.conf_models import TTS_ENGINES, default_engine_settings
        repo = default_engine_settings[TTS_ENGINES['QWEN3TTS']]['repo']
        self.assertIn('Qwen3-TTS', repo, f"Unexpected repo: {repo}")

    def test_qwen3tts_languages_english(self):
        from lib.conf_models import TTS_ENGINES, default_engine_settings
        langs = default_engine_settings[TTS_ENGINES['QWEN3TTS']]['languages']
        self.assertIn('eng', langs)

    def test_qwen3tts_languages_spanish(self):
        from lib.conf_models import TTS_ENGINES, default_engine_settings
        langs = default_engine_settings[TTS_ENGINES['QWEN3TTS']]['languages']
        self.assertIn('spa', langs)

    def test_qwen3tts_rating_keys(self):
        from lib.conf_models import TTS_ENGINES, default_engine_settings
        rating = default_engine_settings[TTS_ENGINES['QWEN3TTS']]['rating']
        for k in ('VRAM', 'CPU', 'RAM', 'Realism'):
            self.assertIn(k, rating)

    def test_qwen3tts_registry_class_importable(self):
        from lib.classes.tts_engines.qwen3tts import Qwen3TTS
        from lib.classes.tts_registry import TTSRegistry
        self.assertIn('qwen3tts', TTSRegistry.ENGINES,
                      "Qwen3TTS not registered in TTSRegistry.ENGINES after import")
        self.assertIs(TTSRegistry.ENGINES['qwen3tts'], Qwen3TTS)

    def test_qwen3tts_in_engines_init(self):
        import lib.classes.tts_engines  # noqa: F401
        from lib.classes.tts_registry import TTSRegistry
        self.assertIn('qwen3tts', TTSRegistry.ENGINES)

    def test_qwen3tts_inherits_ttsutils(self):
        from lib.classes.tts_engines.qwen3tts import Qwen3TTS
        from lib.classes.tts_engines.common.utils import TTSUtils
        self.assertTrue(issubclass(Qwen3TTS, TTSUtils))

    def test_qwen3tts_inherits_ttsregistry(self):
        from lib.classes.tts_engines.qwen3tts import Qwen3TTS
        from lib.classes.tts_registry import TTSRegistry
        self.assertTrue(issubclass(Qwen3TTS, TTSRegistry))

    def test_qwen3tts_convert_method_signature(self):
        import inspect
        from lib.classes.tts_engines.qwen3tts import Qwen3TTS
        sig = inspect.signature(Qwen3TTS.convert)
        params = list(sig.parameters.keys())
        self.assertIn('sentence_file', params)
        self.assertIn('sentence', params)

    def test_qwen3tts_load_engine_method_exists(self):
        from lib.classes.tts_engines.qwen3tts import Qwen3TTS
        self.assertTrue(callable(getattr(Qwen3TTS, 'load_engine', None)))

    def test_engine_count_is_eleven(self):
        from lib.conf_models import TTS_ENGINES
        self.assertEqual(len(TTS_ENGINES), 11, f"Expected 11 engines, got {len(TTS_ENGINES)}")


class TestQwen3TTSPresets(unittest.TestCase):
    """qwen3tts_presets.py exposes the internal preset."""

    def test_presets_importable(self):
        from lib.classes.tts_engines.presets.qwen3tts_presets import models
        self.assertIn('internal', models)

    def test_internal_preset_has_repo(self):
        from lib.classes.tts_engines.presets.qwen3tts_presets import models
        self.assertIn('repo', models['internal'])

    def test_internal_preset_repo_matches_conf(self):
        from lib.classes.tts_engines.presets.qwen3tts_presets import models
        from lib.conf_models import TTS_ENGINES, default_engine_settings
        expected = default_engine_settings[TTS_ENGINES['QWEN3TTS']]['repo']
        self.assertEqual(models['internal']['repo'], expected)

    def test_internal_preset_samplerate(self):
        from lib.classes.tts_engines.presets.qwen3tts_presets import models
        self.assertEqual(models['internal']['samplerate'], 24000)


class TestEnginesRouterQwen3TTS(unittest.TestCase):
    """engines.py router knows about qwen3tts mode."""

    def test_qwen3tts_label_defined(self):
        import importlib
        import sys
        # Ensure the module can be imported even outside FastAPI context
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'webui', 'backend'))
        mod = importlib.import_module('routers.engines')
        self.assertIn('qwen3tts', mod._LABELS)
        self.assertEqual(mod._LABELS['qwen3tts'], 'Qwen3-TTS')

    def test_qwen3tts_only_list_defined(self):
        import importlib
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'webui', 'backend'))
        mod = importlib.import_module('routers.engines')
        self.assertIn('qwen3tts', mod._QWEN3TTS_ONLY)


@unittest.skipUnless(
    os.environ.get('QWEN3TTS_LIVE_TEST') == '1',
    "Set QWEN3TTS_LIVE_TEST=1 to run live inference test (requires qwen-tts installed + model cached)"
)
class TestQwen3TTSLiveInference(unittest.TestCase):
    """End-to-end inference smoke test — requires qwen-tts + cached weights."""

    def setUp(self):
        try:
            import qwen_tts  # noqa: F401
        except ImportError:
            self.skipTest("qwen-tts not installed")

    def test_synthesize_short_sentence(self):
        import tempfile
        import soundfile as sf
        from multiprocessing import Manager

        voice_path = os.path.join(
            os.path.dirname(__file__), '..', 'voices', 'eng', 'adult', 'male', 'KumarDahl.wav'
        )
        if not os.path.isfile(voice_path):
            self.skipTest(f"Reference voice missing: {voice_path}")

        with Manager() as mgr:
            session = mgr.dict({
                'device': 'cuda',
                'tts_engine': 'qwen3tts',
                'fine_tuned': 'internal',
                'model_cache': 'qwen3tts-internal',
                'custom_model': None,
                'custom_model_dir': '',
                'voice': voice_path,
                'language': 'eng',
                'language_iso1': 'en',
                'free_vram_gb': 6.0,
                'script_mode': 'native',
                'is_gui_process': False,
                'process_dir': tempfile.gettempdir(),
            })

            from lib.classes.tts_engines.qwen3tts import Qwen3TTS
            engine = Qwen3TTS(session)

            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                out_path = f.name

            try:
                ok, err = engine.convert(out_path, 'Hello, this is a Qwen3-TTS test.', block_voice=None)
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
