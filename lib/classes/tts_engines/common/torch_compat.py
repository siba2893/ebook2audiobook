"""
Compatibility shim — auto-CPU on Tensor → numpy conversion.

Newer PyTorch (>= 2.x) made `Tensor.__array__` raise when called on a CUDA
tensor instead of silently moving it to CPU.  coqui-tts 0.27.x has several
code paths that pass GPU tensors to librosa / numpy without an explicit
`.cpu()` (e.g. xtts.py:367 librosa.effects.trim, similar in Bark's HuBERT
speaker extraction).  This shim restores the auto-CPU behavior so those
code paths keep working without patching site-packages.

Imported once via `lib.classes.tts_engines.common.headers` so every engine
module benefits without explicit opt-in.
"""
import torch as _torch

_orig_array = _torch.Tensor.__array__


def _array_with_auto_cpu(self, dtype=None):
    if self.device.type != 'cpu':
        return _orig_array(self.detach().cpu(), dtype)
    return _orig_array(self, dtype)


if not getattr(_torch.Tensor.__array__, '_omc_auto_cpu', False):
    _torch.Tensor.__array__ = _array_with_auto_cpu
    _torch.Tensor.__array__._omc_auto_cpu = True


# torch >= 2.6 made `torch.load(weights_only=True)` the default.  Older
# checkpoints (Tacotron2, GlowTTS, etc.) embed `collections.defaultdict` and
# similar non-tensor types in their metadata, which the safe-pickler rejects.
# All checkpoints loaded here come from HuggingFace via project-pinned repos
# (trusted), so default weights_only=False to restore the pre-2.6 behavior.
_orig_load = _torch.load


def _load_with_weights_only_false(*args, **kwargs):
    # Force False even when callers (e.g. trainer.io.load_fsspec) pass
    # weights_only=True explicitly — they do so because torch >= 2.6
    # changed the default and they uncritically pinned the new value.
    kwargs['weights_only'] = False
    return _orig_load(*args, **kwargs)


if not getattr(_torch.load, '_omc_weights_only_default_false', False):
    _torch.load = _load_with_weights_only_false
    _torch.load._omc_weights_only_default_false = True
