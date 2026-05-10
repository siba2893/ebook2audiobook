"""Salvage a session whose TTS completed but FFmpeg concat failed.

Looks under tmp/proc-<session_id>/<hash>/chapters/sentences/<block_id>/{i}.wav
and concatenates them into a single output audio file using `ffmpeg -c:a copy`
(the same fix we just applied in lib/core.py).

Usage:
    python_env\\python.exe tools\\salvage_session.py <session_id> [out_path]

Example:
    python_env\\python.exe tools\\salvage_session.py ccd14a86-92aa-4e45-af57-106a958c65c7 salvaged.m4a
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TMP = REPO / "tmp"


def find_proc_dir(session_id: str) -> Path:
    parent = TMP / f"proc-{session_id}"
    if not parent.is_dir():
        sys.exit(f"[salvage] No process dir for session {session_id} at {parent}")
    subdirs = [p for p in parent.iterdir() if p.is_dir()]
    if not subdirs:
        sys.exit(f"[salvage] {parent} has no hash subdir")
    if len(subdirs) > 1:
        print(f"[salvage] Warning: multiple hash subdirs in {parent}; using {subdirs[0].name}")
    return subdirs[0]


def find_block_dirs(proc_dir: Path) -> list[Path]:
    sentences_root = proc_dir / "chapters" / "sentences"
    if not sentences_root.is_dir():
        sys.exit(f"[salvage] No sentences dir at {sentences_root}")
    blocks = sorted(p for p in sentences_root.iterdir() if p.is_dir())
    if not blocks:
        sys.exit(f"[salvage] No block dirs under {sentences_root}")
    return blocks


def collect_wavs(block_dir: Path) -> list[Path]:
    wavs = list(block_dir.glob("*.wav"))
    if not wavs:
        sys.exit(f"[salvage] No .wav files in {block_dir}")
    # Sort by integer stem so '2.wav' < '10.wav'
    wavs.sort(key=lambda p: int(p.stem) if p.stem.isdigit() else 0)
    return wavs


def write_concat_list(wavs: list[Path], list_path: Path) -> None:
    with open(list_path, "w", encoding="utf-8") as f:
        for w in wavs:
            f.write(f"file '{w.as_posix()}'\n")


def codec_args_for(out_file: Path) -> list[str]:
    """Pick codec args based on output extension. .wav copies losslessly;
    .m4b/.m4a encodes to AAC; .mp3 uses libmp3lame; .opus/.ogg uses libopus."""
    ext = out_file.suffix.lower()
    if ext == ".wav":
        return ["-c:a", "copy"]
    if ext in (".m4b", ".m4a", ".mp4"):
        return ["-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart"]
    if ext == ".mp3":
        return ["-c:a", "libmp3lame", "-b:a", "64k"]
    if ext in (".opus", ".ogg"):
        return ["-c:a", "libopus", "-b:a", "48k"]
    return ["-c:a", "copy"]


def ffmpeg_concat(list_file: Path, out_file: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        sys.exit("[salvage] ffmpeg not on PATH")
    cmd = [
        ffmpeg, "-hide_banner", "-y",
        "-safe", "0", "-f", "concat", "-i", str(list_file),
        *codec_args_for(out_file),
        str(out_file),
    ]
    print("[salvage] Running:", " ".join(cmd))
    rc = subprocess.call(cmd)
    if rc != 0:
        sys.exit(f"[salvage] ffmpeg concat failed (rc={rc})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("session_id")
    ap.add_argument("out_path", nargs="?", default=None,
                    help="Output file (defaults to <session_id>.wav next to repo root)")
    args = ap.parse_args()

    proc_dir = find_proc_dir(args.session_id)
    blocks = find_block_dirs(proc_dir)
    print(f"[salvage] Found {len(blocks)} block(s): {[b.name for b in blocks]}")

    out = Path(args.out_path) if args.out_path else REPO / f"{args.session_id}.wav"
    out = out.resolve()
    print(f"[salvage] Output: {out}")

    if len(blocks) == 1:
        wavs = collect_wavs(blocks[0])
        print(f"[salvage] Concatenating {len(wavs)} sentence WAVs from block {blocks[0].name}")
        list_path = proc_dir / "salvage_concat.txt"
        write_concat_list(wavs, list_path)
        ffmpeg_concat(list_path, out)
    else:
        # Multi-block: build per-block chapter wavs, then concat them.
        chapter_wavs = []
        for blk in blocks:
            wavs = collect_wavs(blk)
            chap_out = proc_dir / f"chapter_{blk.name}.wav"
            list_path = proc_dir / f"salvage_concat_{blk.name}.txt"
            write_concat_list(wavs, list_path)
            ffmpeg_concat(list_path, chap_out)
            chapter_wavs.append(chap_out)
        # Final concat across chapters
        final_list = proc_dir / "salvage_concat_final.txt"
        write_concat_list(chapter_wavs, final_list)
        ffmpeg_concat(final_list, out)

    print(f"[salvage] Done -> {out} ({out.stat().st_size/1024/1024:.1f} MB)")


if __name__ == "__main__":
    main()
