import os
from lib.conf import voices_dir
from lib.conf_models import TTS_ENGINES, default_engine_settings

models = {
    "internal": {
        "lang": "multi",
        "repo": default_engine_settings[TTS_ENGINES['FISHSPEECH']]['repo'],
        "sub": "",
        "voice": default_engine_settings[TTS_ENGINES['FISHSPEECH']]['voice'],
        "files": default_engine_settings[TTS_ENGINES['FISHSPEECH']]['files'],
        "samplerate": default_engine_settings[TTS_ENGINES['FISHSPEECH']]['samplerate']
    }
}
