"""bench_qwen3tts.py - per-sentence RTF benchmark for both Qwen3-TTS backends.

Runs the same N-sentence script through `qwen-tts` (upstream) and
`faster-qwen-tts` (CUDA-graph fork) in two separate processes (one
process per backend so model-caches and CUDA graphs don't bleed).

Reports per-sentence wall-clock + audio duration, with cold-start vs
steady-state breakdown.

Usage:
    python tools/bench_qwen3tts.py            # both backends sequentially
    python tools/bench_qwen3tts.py qwen-tts   # only upstream
    python tools/bench_qwen3tts.py faster-qwen-tts
"""

import argparse
import os
import subprocess
import sys
import time
from multiprocessing import Manager

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
SENTENCES = [
    "Hola, esto es la primera oracion del libro.",
    "El protagonista camina por la calle pensando en el futuro.",
    "La ciudad esta en silencio mientras el sol se esconde.",
    "De repente, un sonido distante interrumpe sus pensamientos.",
    "Decide acercarse, sin imaginar lo que esta a punto de descubrir.",
]
VOICE = os.path.join(ROOT, "voices", "spa", "Raul Llorenz Sample 60 sec.wav")


def _run_one(backend_name: str) -> dict:
    sys.path.insert(0, ROOT)
    os.chdir(ROOT)
    from lib.classes.tts_engines.qwen3tts import Qwen3TTS
    import soundfile as sf

    session = Manager().dict({
        'model_cache': f'qwen3tts_bench_{backend_name}',
        'tts_engine': 'qwen3tts',
        'fine_tuned': 'internal',
        'free_vram_gb': 7.0,
        'device': 'cuda',
        'language': 'spa',
        'voice': VOICE,
        'voice_dir': os.path.join(ROOT, 'voices'),
        'is_gui_process': False,
        'qwen3tts_backend': backend_name,  # explicit override
    })

    print(f'\n=== {backend_name} ===', flush=True)
    load_start = time.time()
    tts = Qwen3TTS(session)
    load_elapsed = time.time() - load_start
    print(f'  load: {load_elapsed:.2f}s', flush=True)
    out_dir = os.path.join(ROOT, 'tmp', 'qwen3tts_bench')
    os.makedirs(out_dir, exist_ok=True)

    per_sentence = []
    for i, sentence in enumerate(SENTENCES, 1):
        out_wav = os.path.join(out_dir, f'{backend_name}_{i:02d}.wav')
        if os.path.exists(out_wav):
            os.remove(out_wav)
        t0 = time.time()
        ok, err = tts.convert(sentence_file=out_wav, sentence=sentence)
        elapsed = time.time() - t0
        if not ok:
            print(f'  s{i}: FAIL after {elapsed:.2f}s -- {err}', flush=True)
            return {'backend': backend_name, 'load_s': load_elapsed, 'sentences': per_sentence, 'failed': True}
        info = sf.info(out_wav)
        audio_s = info.frames / info.samplerate
        rtf = elapsed / audio_s if audio_s > 0 else float('inf')
        per_sentence.append({'idx': i, 'wall_s': elapsed, 'audio_s': audio_s, 'rtf': rtf})
        print(f'  s{i}: {elapsed:5.2f}s  audio={audio_s:4.2f}s  rtf={rtf:4.2f}', flush=True)

    return {'backend': backend_name, 'load_s': load_elapsed, 'sentences': per_sentence, 'failed': False}


def _summary(result: dict) -> None:
    if result['failed']:
        print(f"\n[{result['backend']}] FAILED")
        return
    sents = result['sentences']
    cold = sents[0]
    steady = sents[1:]
    steady_wall = sum(s['wall_s'] for s in steady)
    steady_audio = sum(s['audio_s'] for s in steady)
    steady_rtf = steady_wall / steady_audio if steady_audio > 0 else float('inf')
    total_wall = sum(s['wall_s'] for s in sents)
    total_audio = sum(s['audio_s'] for s in sents)
    total_rtf = total_wall / total_audio if total_audio > 0 else float('inf')
    print(f"\n[{result['backend']}] summary")
    print(f"  load:            {result['load_s']:5.2f}s")
    print(f"  s1 (cold):       {cold['wall_s']:5.2f}s -> {cold['audio_s']:.2f}s audio (rtf {cold['rtf']:.2f})")
    print(f"  s2..N (steady):  {steady_wall:5.2f}s -> {steady_audio:.2f}s audio (rtf {steady_rtf:.2f})")
    print(f"  all sentences:   {total_wall:5.2f}s -> {total_audio:.2f}s audio (rtf {total_rtf:.2f})")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('backends', nargs='*', default=['qwen-tts', 'faster-qwen-tts'])
    parser.add_argument('--in-process', action='store_true',
                        help='Run both backends in the same Python process '
                             '(model cache and CUDA graphs may leak across).')
    args = parser.parse_args()

    if args.in_process:
        results = [_run_one(b) for b in args.backends]
    else:
        # Fresh subprocess per backend so the previous backend's model and
        # CUDA graphs don't pollute the next measurement.
        results = []
        for b in args.backends:
            r = subprocess.run(
                [sys.executable, __file__, b, '--in-process'],
                cwd=ROOT,
            )
            print(f'  (subprocess for {b} exited rc={r.returncode})', flush=True)

    if args.in_process:
        for r in results:
            _summary(r)
    return 0


if __name__ == '__main__':
    sys.exit(main())
