"""
test_engines_e2e.py — in-process voice-preview tests, one per TTS engine.

Calls the same `_synthesize()` function the WebUI's `/api/preview` route
uses, but **directly in this Python process** — no HTTP round-trip, no
running server.  When an engine breaks you see the real Python traceback,
not an opaque HTTP 500 string.

For each engine in `lib.conf_models.TTS_ENGINES` this:
  1. Builds a PreviewRequest exactly like the UI sends.
  2. Calls _synthesize() — loads the model (cached after first call),
     runs convert(), produces a temp WAV.
  3. Copies the WAV to tmp/engine_previews/<engine>.wav for manual audit.
  4. Validates the WAV with soundfile (frames > 0, duration > 0.1s).

Each engine is its own test method, so a failure in one doesn't abort the
others — you get a complete pass/fail matrix per run.

Prerequisites:
  - ffmpeg-shared on PATH (for torchaudio I/O on Windows).
  - Reference voices present in voices/eng/adult/.../*.wav and
    voices/spa/Raul Llorenz Sample 60 sec.wav (cloning-engine tests
    skip cleanly when the file is absent).

Run:
    python tools/test_engines_e2e.py            # all engines, verbose
    python tools/test_engines_e2e.py xtts bark  # subset, by engine name

Exit code is 0 only if every selected engine passed.
"""

import os
import shutil
import sys
import time
import traceback
import unittest
from typing import Optional

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND = os.path.join(ROOT, "webui", "backend")

# Mirror webui/backend/main.py's path setup so `from routers.preview ...`
# resolves the same way as when the FastAPI app starts.  Without this,
# the router module's own `from lib.conf import ...` would still work
# (lib lives at repo root) but the import line below wouldn't.
for _p in (ROOT, BACKEND):
    if _p not in sys.path:
        sys.path.insert(0, _p)
# preview.py reads VERSION.txt relative to cwd; main.py chdir's to the repo
# root for that reason. Replicate.
os.chdir(ROOT)

# Now safe to import the router module directly.
from routers.preview import PreviewRequest, _synthesize  # noqa: E402

OUTPUT_DIR = os.path.join(ROOT, "tmp", "engine_previews")
os.makedirs(OUTPUT_DIR, exist_ok=True)

TEXT_SPA = "Hola, esto es una prueba de la voz."
TEXT_ENG = "Hello, this is a short voice test."
# CosyVoice 3's hift/f0_predictor crashes on very short utterances
# (flow output mel is fewer frames than the F0 conv kernel needs).
# A longer phrase gives enough tokens.
TEXT_SPA_LONG = (
    "Hola, esto es una prueba de la voz. "
    "El sistema convierte texto en audio para producir un audiolibro. "
    "Esperamos que la calidad de la síntesis sea satisfactoria."
)

VOICE_ENG_FEMALE = os.path.join(ROOT, "voices", "eng", "adult", "female", "AnaFlorence.wav")
VOICE_ENG_MALE = os.path.join(ROOT, "voices", "eng", "adult", "male", "AaronDreschner.wav")
VOICE_SPA = os.path.join(ROOT, "voices", "spa", "Raul Llorenz Sample 60 sec.wav")


# ---------------------------------------------------------------------------
# Engine matrix — language + reference voice + expected sample rate per engine
# ---------------------------------------------------------------------------
# `voice` is None for engines that don't do voice cloning (they synthesise
# with a built-in or default speaker).  `language` is the iso639-3 code that
# the engine actually supports; for engines without spa support we fall back
# to eng so the test exercises a real code path.
# `requires` is an optional list of external Python packages that must
# import successfully or the test for that engine is skipped (rather than
# failing) — used for engines whose backend libs ship outside our pinned
# requirements.txt (fish_speech, cosyvoice).
ENGINE_MATRIX = {
    "xtts":       {"language": "spa", "voice": "spa",   "text": TEXT_SPA, "samplerate": 24000},
    # Bark on GPU is broken upstream on torch 2.x + coqui-tts 0.27.5
    # — HuBERT/prompt-cache produce CPU tensors that get cat'd with CUDA
    # tensors from the model.  Run Bark on CPU; slow but functional.
    "bark":       {"language": "eng", "voice": "bark_builtin", "text": TEXT_ENG, "samplerate": 24000, "device": "cpu"},
    "tortoise":   {"language": "eng", "voice": "eng_f", "text": TEXT_ENG, "samplerate": 24000},
    "vits":       {"language": "spa", "voice": None,    "text": TEXT_SPA, "samplerate": 22050},
    "fairseq":    {"language": "spa", "voice": None,    "text": TEXT_SPA, "samplerate": 16000},
    "glowtts":    {"language": "eng", "voice": None,    "text": TEXT_ENG, "samplerate": 22050},
    "tacotron":   {"language": "spa", "voice": None,    "text": TEXT_SPA, "samplerate": 22050},
    "yourtts":    {"language": "eng", "voice": "eng_f", "text": TEXT_ENG, "samplerate": 16000},
    "fishspeech": {"language": "spa", "voice": "spa",   "text": TEXT_SPA, "samplerate": 24000,
                   "requires": ["fish_speech.models.text2semantic.inference"]},
    # CosyVoice 3 has a runtime incompatibility with torch >= 2.7 even on its
    # own bundled Chinese prompt+text example: hift's f0_predictor conv
    # (kernel=4) gets a 3-frame mel from upstream's flow output and crashes.
    # Skip until upstream supports modern torch; engine code fixes remain.
    "cosyvoice":  {"language": "spa", "voice": "spa",   "text": TEXT_SPA_LONG, "samplerate": 24000,
                   "requires": ["hyperpyyaml", "cosyvoice.cli.cosyvoice"],
                   "known_broken": "CosyVoice3 hift/f0_predictor crashes on torch>=2.7 (upstream bug)"},
}


def _resolve_voice(key: Optional[str]) -> Optional[str]:
    if key is None:
        return None
    return {
        "eng_f": VOICE_ENG_FEMALE,
        "eng_m": VOICE_ENG_MALE,
        "spa":   VOICE_SPA,
        # Bark builtin speaker — file doesn't need to exist; the engine
        # only reads Path(...).stem to look up its prompt-cache.
        "bark_builtin": os.path.join(ROOT, "voices", "eng", "en_speaker_6.wav"),
    }[key]


def _validate_wav(path: str, expected_samplerate: int) -> tuple[bool, str]:
    """Return (ok, message). Inspects WAV with soundfile."""
    try:
        import soundfile as sf
    except ImportError:
        return False, "soundfile not installed"
    try:
        info = sf.info(path)
    except Exception as e:
        return False, f"soundfile.info() failed: {e}"
    duration = info.frames / info.samplerate if info.samplerate else 0.0
    if info.frames == 0:
        return False, "WAV has zero frames"
    if duration < 0.1:
        return False, f"WAV duration {duration:.3f}s is suspiciously short"
    note = ""
    if abs(info.samplerate - expected_samplerate) > 1:
        note = f" (note: expected sr={expected_samplerate})"
    return True, f"OK ({duration:.2f}s, sr={info.samplerate}, ch={info.channels}){note}"


# ---------------------------------------------------------------------------
# Base TestCase
# ---------------------------------------------------------------------------
class _EnginePreviewBase(unittest.TestCase):
    """Common per-engine driver. Subclasses set `engine_name`."""

    engine_name: str = ""

    def setUp(self) -> None:
        cfg = ENGINE_MATRIX[self.engine_name]
        if "known_broken" in cfg:
            self.skipTest(f"{self.engine_name} known broken: {cfg['known_broken']}")
        voice_path = _resolve_voice(cfg["voice"])
        # Bark builtin paths are synthetic (only the basename is read).
        skip_existence = cfg["voice"] == "bark_builtin"
        if voice_path is not None and not skip_existence and not os.path.exists(voice_path):
            self.skipTest(f"Reference voice missing: {voice_path}")
        # Skip cleanly when an engine's external Python lib isn't importable.
        # CosyVoice ships its package under third_party/CosyVoice/, so add
        # that to sys.path before probing.
        if self.engine_name == "cosyvoice":
            for p in (
                os.path.join(ROOT, "third_party", "CosyVoice"),
                os.path.join(ROOT, "third_party", "CosyVoice", "third_party", "Matcha-TTS"),
            ):
                if os.path.isdir(p) and p not in sys.path:
                    sys.path.insert(0, p)
        for mod_name in cfg.get("requires", []):
            try:
                __import__(mod_name)
            except ImportError as e:
                self.skipTest(
                    f"{self.engine_name} backend lib not installed "
                    f"(import {mod_name} failed: {e})"
                )

    def _do_preview(self) -> None:
        cfg = ENGINE_MATRIX[self.engine_name]
        voice_path = _resolve_voice(cfg["voice"])

        req = PreviewRequest(
            text=cfg["text"],
            voice_path=voice_path,
            language=cfg["language"],
            tts_engine=self.engine_name,
            device=cfg.get("device", "cuda"),
        )

        out_path = os.path.join(OUTPUT_DIR, f"{self.engine_name}.wav")
        try:
            os.unlink(out_path)
        except FileNotFoundError:
            pass

        start = time.time()
        try:
            tmp_wav = _synthesize(req, req.text)
        except Exception:
            self.fail(
                f"[{self.engine_name}] _synthesize raised:\n"
                f"  request: text={req.text!r} voice={req.voice_path!r} "
                f"lang={req.language!r} engine={req.tts_engine!r}\n"
                f"{traceback.format_exc()}"
            )

        elapsed = time.time() - start

        if not os.path.isfile(tmp_wav):
            self.fail(f"[{self.engine_name}] _synthesize returned non-existent path: {tmp_wav}")

        # Copy to the stable output dir so it can be auditioned later, then
        # try to remove the per-call temp dir to avoid clutter.
        shutil.copyfile(tmp_wav, out_path)
        try:
            shutil.rmtree(os.path.dirname(tmp_wav), ignore_errors=True)
        except Exception:
            pass

        size_kb = os.path.getsize(out_path) >> 10
        ok, msg = _validate_wav(out_path, cfg["samplerate"])
        if not ok:
            self.fail(
                f"[{self.engine_name}] WAV validation failed: {msg}\n"
                f"  saved to: {out_path} ({size_kb} KB)\n"
                f"  elapsed: {elapsed:.1f}s"
            )

        print(
            f"  [PASS] {self.engine_name:<11} {elapsed:6.1f}s  "
            f"{size_kb:5d} KB  {msg}  -> {out_path}"
        )


# ---------------------------------------------------------------------------
# Generate one TestCase subclass per engine.
# ---------------------------------------------------------------------------
def _make_test_class(engine: str) -> type:
    return type(
        f"TestPreview_{engine}",
        (_EnginePreviewBase,),
        {
            "engine_name": engine,
            "test_preview": lambda self: self._do_preview(),
        },
    )


for _engine_name in ENGINE_MATRIX:
    _cls = _make_test_class(_engine_name)
    globals()[_cls.__name__] = _cls


# ---------------------------------------------------------------------------
# main() — supports `python tools/test_engines_e2e.py xtts bark` for subsets,
# prints a clean summary at the end.
# ---------------------------------------------------------------------------
def main():
    argv = sys.argv[1:]
    selected = [a for a in argv if not a.startswith("-")]

    if selected:
        bad = [s for s in selected if s not in ENGINE_MATRIX]
        if bad:
            print(f"Unknown engine(s): {bad}", file=sys.stderr)
            print(f"Available: {list(ENGINE_MATRIX)}", file=sys.stderr)
            sys.exit(2)
    else:
        selected = list(ENGINE_MATRIX)

    print("=" * 78)
    print("TTS-engine end-to-end preview tests (in-process)")
    print(f"  Repo:    {ROOT}")
    print(f"  Output:  {OUTPUT_DIR}")
    print(f"  Engines: {', '.join(selected)}")
    print("=" * 78)

    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    for engine in selected:
        cls = globals()[f"TestPreview_{engine}"]
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2, failfast=False)
    result = runner.run(suite)

    print()
    print("=" * 78)
    print("Summary")
    print("=" * 78)
    failed = {f"{tc}".split(".")[-2].replace("TestPreview_", "")
              for tc, _ in result.failures}
    errored = {f"{tc}".split(".")[-2].replace("TestPreview_", "")
               for tc, _ in result.errors}
    skipped = {f"{tc}".split(".")[-2].replace("TestPreview_", "")
               for tc, _ in result.skipped}
    for engine in selected:
        if engine in failed:
            mark = "FAIL "
        elif engine in errored:
            mark = "ERROR"
        elif engine in skipped:
            mark = "SKIP "
        else:
            mark = "PASS "
        print(f"  [{mark}] {engine}")
    print()

    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
