#!/usr/bin/env python3
"""Unit tests for scripts/atomic_write.py (CF-WO-P0-003).

Direct tests of the secure atomic-write helper: planted symlinks are
never followed, failure paths clean up, and file modes are preserved.
Exit 0 = PASS, 1 = FAIL. Test IDs: CF-P0-ATOMIC-001..006.
"""
import os
import stat
import sys
import tempfile

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from atomic_write import atomic_write, atomic_write_json  # noqa: E402

failures = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


def main():
    tmp = tempfile.mkdtemp()
    try:
        # --- CF-P0-ATOMIC-001: basic write, regular file, right bytes --
        target = os.path.join(tmp, "target.txt")
        atomic_write(target, b"hello\n")
        check("CF-P0-ATOMIC-001: basic write produces correct bytes",
              open(target, "rb").read() == b"hello\n")
        check("CF-P0-ATOMIC-001: result is a regular file, not a symlink",
              os.path.isfile(target) and not os.path.islink(target))

        # --- CF-P0-ATOMIC-002: existing target keeps its mode -----------
        os.chmod(target, 0o640)
        atomic_write(target, b"again\n")
        check("CF-P0-ATOMIC-002: existing target keeps its mode",
              stat.S_IMODE(os.stat(target).st_mode) == 0o640,
              oct(stat.S_IMODE(os.stat(target).st_mode)))
        check("CF-P0-ATOMIC-002: rewritten content is correct",
              open(target, "rb").read() == b"again\n")

        # --- CF-P0-ATOMIC-003: planted sibling .tmp symlink is ignored --
        canary = os.path.join(tmp, "canary.txt")
        open(canary, "wb").write(b"CANARY-ORIGINAL\n")
        link = os.path.join(tmp, "target.txt.tmp")
        os.symlink(canary, link)
        atomic_write(target, b"safe\n")
        check("CF-P0-ATOMIC-003: planted .tmp symlink is never followed",
              open(canary, "rb").read() == b"CANARY-ORIGINAL\n")
        check("CF-P0-ATOMIC-003: target has the new content",
              open(target, "rb").read() == b"safe\n")
        check("CF-P0-ATOMIC-003: planted symlink left untouched",
              os.path.islink(link) and os.readlink(link) == canary)
        check("CF-P0-ATOMIC-003: no stale .cf-atomic-* temp remains",
              not [n for n in os.listdir(tmp) if n.startswith(".cf-atomic-")])

        # --- CF-P0-ATOMIC-004: planted symlink AT the target -----------
        victim = os.path.join(tmp, "victim.txt")
        open(victim, "wb").write(b"VICTIM-ORIGINAL\n")
        target2 = os.path.join(tmp, "target2.txt")
        os.symlink(victim, target2)
        atomic_write(target2, b"replaced\n")
        check("CF-P0-ATOMIC-004: symlink at target is replaced, not followed",
              open(victim, "rb").read() == b"VICTIM-ORIGINAL\n")
        check("CF-P0-ATOMIC-004: target is now a regular file",
              os.path.isfile(target2) and not os.path.islink(target2))
        check("CF-P0-ATOMIC-004: replaced content is correct",
              open(target2, "rb").read() == b"replaced\n")

        # --- CF-P0-ATOMIC-005: failure cleans up, target unchanged ------
        target3 = os.path.join(tmp, "target3.txt")
        atomic_write(target3, b"before\n")
        real_replace = os.replace

        def boom(src, dst):
            raise OSError("simulated replace failure")

        import atomic_write as mod
        mod.os.replace = boom
        try:
            atomic_write(target3, b"after\n")
            raised = False
        except OSError:
            raised = True
        finally:
            mod.os.replace = real_replace
        check("CF-P0-ATOMIC-005: replace failure propagates",
              raised)
        check("CF-P0-ATOMIC-005: target unchanged after failure",
              open(target3, "rb").read() == b"before\n")
        check("CF-P0-ATOMIC-005: no temp file left behind after failure",
              not [n for n in os.listdir(tmp) if n.startswith(".cf-atomic-")])

        # --- CF-P0-ATOMIC-006: bad input creates nothing ----------------
        try:
            atomic_write(target3, "not-bytes")
            raised = False
        except TypeError:
            raised = True
        check("CF-P0-ATOMIC-006: non-bytes data raises TypeError",
              raised)
        check("CF-P0-ATOMIC-006: no temp file left behind after bad input",
              not [n for n in os.listdir(tmp) if n.startswith(".cf-atomic-")])
        check("CF-P0-ATOMIC-006: target unchanged after bad input",
              open(target3, "rb").read() == b"before\n")

        # --- JSON round-trip (used by all installer metadata writers) ---
        jtarget = os.path.join(tmp, "data.json")
        atomic_write_json(jtarget, {"b": 1, "a": [2, 3]})
        import json
        check("CF-P0-ATOMIC-006: atomic_write_json round-trips",
              json.load(open(jtarget, encoding="utf-8")) == {"a": [2, 3], "b": 1})
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"test_atomic_write: {'PASS' if not failures else 'FAIL'} "
          f"({len(failures)} failure(s))")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
