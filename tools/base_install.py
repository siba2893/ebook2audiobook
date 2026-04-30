"""
Idempotent base-package installer used by base_installation.cmd.

Without args:
    Checks every package in BASE_PACKAGES against importlib.metadata.
    If all are installed and satisfy their version specifier, exits 0
    without touching pip.  Otherwise installs whatever's missing or
    outdated (does NOT wipe other packages).

With --force:
    Snapshots `pip freeze`, uninstalls everything except pip/setuptools/
    wheel, then installs the full BASE_PACKAGES set.

This file is the single source of truth for the engine-agnostic base
package list.  The three engine installers
(1_regular_engines_install.cmd / 2_cosy_voice_engine_install.cmd /
3_qwen3tts_engine_install.cmd) layer their torch + engine-specific
deps on top of whatever this script installs.
"""
from __future__ import annotations

import importlib.metadata as md
import os
import subprocess
import sys
import tempfile
from typing import Optional

# (distribution_name, optional version specifier per PEP 440).
# Distribution names match what pip / importlib.metadata expects, which
# may differ from the import name (e.g. soundfile uses "soundfile" both
# in install and import; PyOpenGL distributes as "PyOpenGL").
BASE_PACKAGES: list[tuple[str, Optional[str]]] = [
    ("cryptography", None),
    ("py-cpuinfo", None),
    ("tqdm", None),
    ("regex", None),
    ("docker", None),
    ("ebooklib", None),
    ("python-pptx", None),
    ("python-docx", None),
    ("fastapi", None),
    ("uvicorn", None),
    ("hf_xet", None),
    ("beautifulsoup4", None),
    ("nagisa", None),
    ("pymupdf", None),
    ("pymupdf-layout", None),
    ("pytesseract", None),
    ("unidic", None),
    ("hangul-romanize", None),
    ("iso639-lang", None),
    ("soynlp", None),
    ("jieba", None),
    ("pycantonese", None),
    ("pypinyin", None),
    ("pythainlp", None),
    ("mutagen", None),
    ("PyOpenGL", None),
    ("phonemizer-fork", None),
    ("pydub", None),
    ("unidecode", None),
    ("langdetect", None),
    ("phonemizer", None),
    ("indic-nlp-library", None),
    ("stanza", "==1.10.1"),
    ("argostranslate", "==1.11.0"),
    ("pandas", ">=1.0,<4.0"),
    ("gradio", ">=5.49.1"),
    ("huggingface_hub", ">=0.36.2"),
    ("basedpyright", None),
    ("requests", None),
    ("soundfile", None),
    # num2words ships under ext/py/num2words and is installed separately.
    ("num2words", None),
]

# Specs handed to `pip install`. uvicorn needs the [standard] extras for
# the WebSocket / file-watcher deps; the metadata check above only
# confirms that uvicorn itself is present, which is fine — `pip install
# uvicorn[standard]` is a no-op when uvicorn is current.
PIP_SPECS = [
    "cryptography", "py-cpuinfo", "tqdm", "regex", "docker", "ebooklib",
    "python-pptx", "python-docx", "fastapi", "uvicorn[standard]", "hf_xet",
    "beautifulsoup4", "nagisa", "pymupdf", "pymupdf-layout", "pytesseract",
    "unidic", "hangul-romanize", "iso639-lang", "soynlp", "jieba",
    "pycantonese", "pypinyin", "pythainlp", "mutagen", "PyOpenGL",
    "phonemizer-fork", "pydub", "unidecode", "langdetect", "phonemizer",
    "indic-nlp-library", "stanza==1.10.1", "argostranslate==1.11.0",
    "pandas>=1.0,<4.0", "gradio>=5.49.1", "huggingface_hub>=0.36.2",
    "basedpyright", "requests", "soundfile",
]


def _installed_version(name: str) -> Optional[str]:
    try:
        return md.version(name)
    except md.PackageNotFoundError:
        return None


def _satisfies(spec: Optional[str], version: Optional[str]) -> bool:
    if version is None:
        return False
    if spec is None:
        return True
    try:
        from packaging.specifiers import SpecifierSet
        return version in SpecifierSet(spec)
    except Exception:
        # Malformed specifier → fail open so we don't reinstall on a typo.
        return True


def check_all() -> list[tuple[str, Optional[str], Optional[str]]]:
    """Returns [(name, required_spec, installed_version_or_None), …] for unsatisfied packages."""
    out = []
    for name, spec in BASE_PACKAGES:
        version = _installed_version(name)
        if not _satisfies(spec, version):
            out.append((name, spec, version))
    return out


def pip(*args: str) -> int:
    return subprocess.call([sys.executable, "-m", "pip", *args])


def wipe() -> None:
    print("=== Wiping python_env/ packages ===", flush=True)
    freeze = subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True)
    keep = {"pip", "setuptools", "wheel"}
    targets: list[str] = []
    for line in freeze.splitlines():
        if "==" not in line:
            continue
        pkg = line.split("==", 1)[0].strip()
        if pkg.lower() not in keep:
            targets.append(line.strip())
    if not targets:
        print("  (nothing to remove)")
        return
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        for line in targets:
            f.write(line + "\n")
        path = f.name
    try:
        rc = pip("uninstall", "-y", "-r", path)
        if rc != 0:
            print(f"[WARN] pip uninstall reported errors (rc={rc}); continuing.")
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def install_base() -> int:
    print("=== Installing engine-agnostic base packages ===", flush=True)
    rc = pip("install", "--no-cache-dir", *PIP_SPECS)
    if rc != 0:
        return rc
    print("=== Installing ext/py/num2words ===", flush=True)
    return pip("install", "--no-cache-dir", "ext/py/num2words")


def main() -> int:
    force = "--force" in sys.argv[1:]
    if force:
        wipe()
        return install_base()

    missing = check_all()
    if not missing:
        print("=== Base packages already installed and current — nothing to do ===")
        print("    (re-run with --force to wipe and reinstall)")
        return 0

    print("=== Base packages missing or outdated ===")
    for name, spec, version in missing:
        need = spec or "any"
        have = version or "<not installed>"
        print(f"    {name:24s}  need {need:14s}  have {have}")
    print()
    return install_base()


if __name__ == "__main__":
    sys.exit(main())
