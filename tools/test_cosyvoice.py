"""
Static unit tests for the CosyVoice engine integration.
No GPU or model weights required — all tests exercise configuration,
module structure, and import behaviour without loading the actual model.

Run with:
    python tools/test_cosyvoice.py
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestCosyVoiceRegistration(unittest.TestCase):
    """CosyVoice is correctly wired into the engine registry and conf."""

    def test_cosyvoice_in_tts_engines(self):
        from lib.conf_models import TTS_ENGINES
        self.assertIn('COSYVOICE', TTS_ENGINES)
        self.assertEqual(TTS_ENGINES['COSYVOICE'], 'cosyvoice')

    def test_cosyvoice_in_default_engine_settings(self):
        from lib.conf_models import TTS_ENGINES, default_engine_settings
        key = TTS_ENGINES['COSYVOICE']
        self.assertIn(key, default_engine_settings)

    def test_cosyvoice_settings_required_keys(self):
        from lib.conf_models import TTS_ENGINES, default_engine_settings
        s = default_engine_settings[TTS_ENGINES['COSYVOICE']]
        for required in ('repo', 'samplerate', 'speed', 'instruct_text', 'languages', 'rating'):
            self.assertIn(required, s, f"Missing key '{required}' in cosyvoice settings")

    def test_cosyvoice_repo(self):
        from lib.conf_models import TTS_ENGINES, default_engine_settings
        repo = default_engine_settings[TTS_ENGINES['COSYVOICE']]['repo']
        self.assertEqual(repo, 'FunAudioLLM/Fun-CosyVoice3-0.5B')

    def test_cosyvoice_samplerate(self):
        from lib.conf_models import TTS_ENGINES, default_engine_settings
        sr = default_engine_settings[TTS_ENGINES['COSYVOICE']]['samplerate']
        self.assertEqual(sr, 24000)

    def test_cosyvoice_default_speed(self):
        from lib.conf_models import TTS_ENGINES, default_engine_settings
        speed = default_engine_settings[TTS_ENGINES['COSYVOICE']]['speed']
        self.assertEqual(speed, 1.0)

    def test_cosyvoice_instruct_text_default_empty(self):
        from lib.conf_models import TTS_ENGINES, default_engine_settings
        instruct = default_engine_settings[TTS_ENGINES['COSYVOICE']]['instruct_text']
        self.assertEqual(instruct, '')

    def test_cosyvoice_languages_english(self):
        from lib.conf_models import TTS_ENGINES, default_engine_settings
        langs = default_engine_settings[TTS_ENGINES['COSYVOICE']]['languages']
        self.assertIn('eng', langs)

    def test_cosyvoice_languages_spanish(self):
        from lib.conf_models import TTS_ENGINES, default_engine_settings
        langs = default_engine_settings[TTS_ENGINES['COSYVOICE']]['languages']
        self.assertIn('spa', langs)

    def test_cosyvoice_languages_chinese(self):
        from lib.conf_models import TTS_ENGINES, default_engine_settings
        langs = default_engine_settings[TTS_ENGINES['COSYVOICE']]['languages']
        self.assertIn('zho', langs)

    def test_cosyvoice_rating_keys(self):
        from lib.conf_models import TTS_ENGINES, default_engine_settings
        rating = default_engine_settings[TTS_ENGINES['COSYVOICE']]['rating']
        for k in ('VRAM', 'CPU', 'RAM', 'Realism'):
            self.assertIn(k, rating)

    def test_engine_count_is_ten(self):
        from lib.conf_models import TTS_ENGINES
        self.assertEqual(len(TTS_ENGINES), 10, f"Expected 10 engines, got {len(TTS_ENGINES)}")

    def test_cosyvoice_registry_class_importable(self):
        from lib.classes.tts_engines.cosyvoice import CosyVoice
        from lib.classes.tts_registry import TTSRegistry
        self.assertIn('cosyvoice', TTSRegistry.ENGINES)
        self.assertIs(TTSRegistry.ENGINES['cosyvoice'], CosyVoice)

    def test_cosyvoice_in_engines_init(self):
        import lib.classes.tts_engines  # noqa: F401
        from lib.classes.tts_registry import TTSRegistry
        self.assertIn('cosyvoice', TTSRegistry.ENGINES)

    def test_cosyvoice_inherits_ttsutils(self):
        from lib.classes.tts_engines.cosyvoice import CosyVoice
        from lib.classes.tts_engines.common.utils import TTSUtils
        self.assertTrue(issubclass(CosyVoice, TTSUtils))

    def test_cosyvoice_inherits_ttsregistry(self):
        from lib.classes.tts_engines.cosyvoice import CosyVoice
        from lib.classes.tts_registry import TTSRegistry
        self.assertTrue(issubclass(CosyVoice, TTSRegistry))

    def test_cosyvoice_convert_method_signature(self):
        import inspect
        from lib.classes.tts_engines.cosyvoice import CosyVoice
        sig = inspect.signature(CosyVoice.convert)
        params = list(sig.parameters.keys())
        self.assertIn('sentence_file', params)
        self.assertIn('sentence', params)

    def test_cosyvoice_load_engine_method_exists(self):
        from lib.classes.tts_engines.cosyvoice import CosyVoice
        self.assertTrue(callable(getattr(CosyVoice, 'load_engine', None)))


class TestCosyVoicePresets(unittest.TestCase):
    """cosyvoice_presets.py exposes the internal preset."""

    def test_presets_importable(self):
        from lib.classes.tts_engines.presets.cosyvoice_presets import models
        self.assertIn('internal', models)

    def test_internal_preset_has_repo(self):
        from lib.classes.tts_engines.presets.cosyvoice_presets import models
        self.assertIn('repo', models['internal'])

    def test_internal_preset_repo_matches_conf(self):
        from lib.classes.tts_engines.presets.cosyvoice_presets import models
        from lib.conf_models import TTS_ENGINES, default_engine_settings
        expected = default_engine_settings[TTS_ENGINES['COSYVOICE']]['repo']
        self.assertEqual(models['internal']['repo'], expected)

    def test_internal_preset_samplerate(self):
        from lib.classes.tts_engines.presets.cosyvoice_presets import models
        self.assertEqual(models['internal']['samplerate'], 24000)


class TestCosyVoicePaths(unittest.TestCase):
    """cosyvoice.py exports correct third_party path constants."""

    def test_cosyvoice_path_points_to_third_party(self):
        from lib.classes.tts_engines.cosyvoice import _COSYVOICE_PATH
        normalised = _COSYVOICE_PATH.replace('\\', '/')
        self.assertTrue(normalised.endswith('third_party/CosyVoice'))

    def test_matcha_path_inside_cosyvoice(self):
        from lib.classes.tts_engines.cosyvoice import _COSYVOICE_PATH, _MATCHA_PATH
        self.assertTrue(_MATCHA_PATH.startswith(_COSYVOICE_PATH))

    def test_matcha_path_ends_correctly(self):
        from lib.classes.tts_engines.cosyvoice import _MATCHA_PATH
        normalised = _MATCHA_PATH.replace('\\', '/')
        self.assertTrue(normalised.endswith('third_party/CosyVoice/third_party/Matcha-TTS'))


class TestCosyVoiceMissingInstall(unittest.TestCase):
    """load_engine raises RuntimeError with clear message when CosyVoice is not cloned."""

    def test_missing_dir_raises_runtime_error(self):
        """When third_party/CosyVoice doesn't exist, load_engine must fail with RuntimeError."""
        from lib.classes.tts_engines.cosyvoice import CosyVoice, _COSYVOICE_PATH
        from lib.conf_models import TTS_ENGINES, default_engine_settings
        from lib.conf_models import loaded_tts

        # Only run this test if CosyVoice is actually absent (expected in CI / dev machines).
        if os.path.isdir(_COSYVOICE_PATH):
            self.skipTest('third_party/CosyVoice is present; skipping missing-install test')

        loaded_tts.clear()

        session = {
            'model_cache': 'cosyvoice-test-missing',
            'fine_tuned': 'internal',
            'device': 'cpu',
            'free_vram_gb': 0.0,
            'voice': None,
        }

        engine_obj = object.__new__(CosyVoice)
        engine_obj.session = session
        engine_obj.cache_dir = '/tmp/tts'
        engine_obj.tts_key = 'cosyvoice-test-missing'
        engine_obj.params = {'samplerate': 24000}
        engine_obj.models = {
            'internal': {
                'repo': default_engine_settings[TTS_ENGINES['COSYVOICE']]['repo'],
                'samplerate': 24000,
            }
        }

        with self.assertRaises(RuntimeError) as ctx:
            engine_obj.load_engine()

        self.assertIn('third_party/CosyVoice', str(ctx.exception).replace('\\', '/'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
