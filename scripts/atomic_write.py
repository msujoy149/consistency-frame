#!/usr/bin/env python3
"""Consistency Frame — secure atomic file write (P0-003).

One reusable helper for every installer metadata write
(scripts/sync-skills.sh: manifest, last-sync record, run-owner
marker). All of them must use this helper; none may write through a
predictable temporary file of its own.

Root cause (P0-002, independently reproduced): the installer wrote
the manifest to a predictable temporary name,
``<target>.tmp``, with an ordinary ``open(tmp, "w")`` and then
``os.replace(tmp, target)``. An attacker who can plant a symlink at
``.consistency-frame-manifest.json.tmp`` pointing outside the
destination makes the write follow the symlink, overwriting the
external target. Renaming ``.tmp`` to another predictable name does
not fix this — the name must be unguessable and the creation
exclusive.

This helper instead creates the temporary file with
``tempfile.mkstemp()`` — exclusive creation (O_CREAT | O_EXCL), a
unique random name, in the same directory as the target — writes
through the returned file descriptor, flushes + fsyncs, closes, and
then atomically replaces the target with ``os.replace()``.
``os.replace()`` never follows a symlink at the target path: a
planted symlink at the target itself is replaced by the new regular
file, and the symlink's outside target is untouched.

On any failure the temporary file is removed (best effort) and the
error propagates; the caller must never report SUCCESS after a failed
write. The temporary file keeps the target's existing mode when the
target is a regular file, else 0o666 & ~umask — matching what a plain
``open()`` would have produced, so installs do not change file
permissions unexpectedly.
"""

import json
import os
import stat
import tempfile


def _default_mode(target):
    """Mode for the new file: the target's mode if it is a regular
    file, else 0o666 & ~umask (what open() would have produced). A
    symlink at the target does not donate its mode."""
    try:
        st = os.lstat(target)
    except OSError:
        pass
    else:
        if stat.S_ISREG(st.st_mode):
            return st.st_mode & 0o777
    umask = os.umask(0)
    os.umask(umask)
    return 0o666 & ~umask


def atomic_write(path, data, mode=None):
    """Atomically write bytes ``data`` to ``path``.

    Returns None. Raises OSError (or TypeError/ValueError for bad
    input) on failure; on failure no temporary file is left behind
    and ``path`` is unchanged (the previous content, if any, is
    untouched). The temporary file lives in the same directory as
    ``path`` so the replace stays on one filesystem.
    """
    if not isinstance(path, str) or not path:
        raise ValueError("atomic_write: path must be a non-empty string")
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("atomic_write: data must be bytes")
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    if mode is None:
        mode = _default_mode(path)
    fd, tmp = tempfile.mkstemp(dir=parent, prefix=".cf-atomic-",
                               suffix=".tmp")
    try:
        os.fchmod(fd, mode)
        try:
            f = os.fdopen(fd, "wb")
        except BaseException:
            os.close(fd)
            raise
        with f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def atomic_write_json(path, obj, mode=None):
    """Atomically write ``obj`` as JSON (indent 2, sorted keys,
    trailing newline) to ``path``. Same failure guarantees as
    :func:`atomic_write`."""
    blob = (json.dumps(obj, indent=2, sort_keys=True) + "\n").encode("utf-8")
    atomic_write(path, blob, mode=mode)
