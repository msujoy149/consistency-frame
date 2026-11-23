#!/usr/bin/env python3
"""CF-WO-P1-001 — local session runtime regression suite.

Tests the production code in runtime/local_session.py (first-run
installation identity, process-bound sessions, local storage
safety). Every check executes production code against isolated
temporary directories and synthetic IDs; no real character data,
voice data, credentials, or network use.

Test IDs: CF-P1-001-PROF (profile lifecycle), CF-P1-001-SESS
(session integrity), CF-P1-001-FS (filesystem security).

Run: python3 tests/test_local_session_runtime.py
Exit 0 = PASS, 1 = FAIL.
"""

import copy
import json
import os
import pickle
import platform
import shutil
import stat
import sys
import tempfile
import time
import unittest.mock as mock
from types import SimpleNamespace

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, ROOT)
import asset_policy  # noqa: E402
from runtime import local_session  # noqa: E402
from runtime.local_session import (  # noqa: E402
    InstallationProfile, LocalSession, ProfileError, SessionError,
    close_session, is_active_session, load_or_create_profile,
    resolve_data_root, start_session, validate_session)

failures = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


def _fresh_root():
    return tempfile.mkdtemp(prefix="cf-p1-001-")


def _write_profile_bytes(root, raw: bytes):
    path = os.path.join(root, "profile.json")
    with open(path, "wb") as f:
        f.write(raw)
    return path


def _valid_profile_dict(owner_id, workspace_id, **extra):
    data = {"schema_version": 1, "owner_id": owner_id,
            "workspace_id": workspace_id}
    data.update(extra)
    return data


def _define_spoof_subclass(name):
    """Test-only fixture (same pattern as P0-011): define a
    LocalSession subclass while the __init_subclass__ prohibition
    is temporarily neutralized, then restore it. This proves the
    VERIFIER rejects subclass instances on its own."""
    original = LocalSession.__init_subclass__
    try:
        LocalSession.__init_subclass__ = classmethod(
            lambda cls, **kwargs: None)
        return type(name, (LocalSession,), {})
    finally:
        LocalSession.__init_subclass__ = original


def main():
    tmp_roots = []

    def new_root():
        root = _fresh_root()
        tmp_roots.append(root)
        return root

    try:
        # ----------------------------------------------------------
        # Profile lifecycle (CF-P1-001-PROF)
        # ----------------------------------------------------------
        root_a = new_root()
        profile_a = load_or_create_profile(root_a)
        check("CF-P1-001-PROF-01: first launch creates valid stable IDs",
              local_session._is_valid_opaque_id(profile_a.owner_id)
              and local_session._is_valid_opaque_id(
                  profile_a.workspace_id)
              and profile_a.owner_id != profile_a.workspace_id,
              f"owner={profile_a.owner_id!r} "
              f"workspace={profile_a.workspace_id!r}")
        check("CF-P1-001-PROF-01b: profile file lives under the data root",
              profile_a.profile_path == os.path.join(
                  root_a, "profile.json"))

        profile_a2 = load_or_create_profile(root_a)
        check("CF-P1-001-PROF-02: restart preserves the same IDs",
              profile_a2.owner_id == profile_a.owner_id
              and profile_a2.workspace_id == profile_a.workspace_id)

        session_a = start_session(profile_a, profile_a.workspace_id)
        session_a2 = start_session(profile_a2, profile_a2.workspace_id)
        check("CF-P1-001-PROF-03: a new session receives a new session ID",
              session_a.session_id != session_a2.session_id
              and session_a.owner_id == session_a2.owner_id
              and session_a.workspace_id == session_a2.workspace_id)

        # Corrupt / invalid profiles fail closed, untouched.
        root_corrupt = new_root()
        corrupt_path = _write_profile_bytes(root_corrupt, b"not json {")
        before = open(corrupt_path, "rb").read()
        try:
            load_or_create_profile(root_corrupt)
            raised = False
        except ProfileError:
            raised = True
        check("CF-P1-001-PROF-04: corrupt profile fails closed",
              raised)
        check("CF-P1-001-PROF-04b: corrupt profile bytes are untouched",
              open(corrupt_path, "rb").read() == before)

        root_trunc = new_root()
        trunc_path = _write_profile_bytes(
            root_trunc, b'{"schema_version": 1, "owner_id": "abc')
        try:
            load_or_create_profile(root_trunc)
            raised = False
        except ProfileError:
            raised = True
        check("CF-P1-001-PROF-05: truncated JSON fails closed", raised)

        root_missing = new_root()
        _write_profile_bytes(
            root_missing,
            json.dumps({"schema_version": 1,
                        "owner_id": "owner-aaaa0001"}).encode())
        try:
            load_or_create_profile(root_missing)
            raised = False
        except ProfileError:
            raised = True
        check("CF-P1-001-PROF-06: missing identity field is rejected",
              raised)

        root_bad_id = new_root()
        _write_profile_bytes(
            root_bad_id,
            json.dumps(_valid_profile_dict(
                "Owner A!", "workspace-aaaa0001")).encode())
        try:
            load_or_create_profile(root_bad_id)
            raised = False
        except ProfileError:
            raised = True
        check("CF-P1-001-PROF-07: malformed identity field is rejected",
              raised)

        root_extra = new_root()
        _write_profile_bytes(
            root_extra,
            json.dumps(_valid_profile_dict(
                "owner-aaaa0001", "workspace-aaaa0001",
                notes="tampered")).encode())
        try:
            load_or_create_profile(root_extra)
            raised = False
        except ProfileError:
            raised = True
        check("CF-P1-001-PROF-08: unexpected extra field is rejected",
              raised)

        root_version = new_root()
        _write_profile_bytes(
            root_version,
            json.dumps({"schema_version": 2,
                        "owner_id": "owner-aaaa0001",
                        "workspace_id": "workspace-aaaa0001"}).encode())
        try:
            load_or_create_profile(root_version)
            raised = False
        except ProfileError:
            raised = True
        check("CF-P1-001-PROF-09: wrong schema version is rejected",
              raised)

        root_bool = new_root()
        _write_profile_bytes(
            root_bool,
            json.dumps({"schema_version": True,
                        "owner_id": "owner-aaaa0001",
                        "workspace_id": "workspace-aaaa0001"}).encode())
        try:
            load_or_create_profile(root_bool)
            raised = False
        except ProfileError:
            raised = True
        check("CF-P1-001-PROF-10: boolean schema version is rejected",
              raised)

        root_b = new_root()
        profile_b = load_or_create_profile(root_b)
        check("CF-P1-001-PROF-11: two data roots never share identity",
              profile_b.owner_id != profile_a.owner_id
              and profile_b.workspace_id != profile_a.workspace_id)

        # Data-root resolution.
        root_override = new_root()
        resolved = resolve_data_root(root_override)
        check("CF-P1-001-PROF-12: explicit data-root override is used",
              resolved == os.path.abspath(root_override))
        check("CF-P1-001-PROF-12b: profile lands under the override",
              load_or_create_profile(
                  root_override).profile_path == os.path.join(
                      os.path.abspath(root_override), "profile.json"))

        home_tmp = new_root()
        old_env = dict(os.environ)
        try:
            os.environ["XDG_DATA_HOME"] = os.path.join(home_tmp, "xdg")
            os.environ.pop("HOME", None)
            check("CF-P1-001-PROF-13: XDG_DATA_HOME is respected",
                  resolve_data_root() == os.path.join(
                      home_tmp, "xdg", "consistency-frame"))
            os.environ.pop("XDG_DATA_HOME", None)
            os.environ["HOME"] = home_tmp
            check("CF-P1-001-PROF-14: default is ~/.local/share",
                  resolve_data_root() == os.path.join(
                      home_tmp, ".local", "share", "consistency-frame"))
            check("CF-P1-001-PROF-15: no repository-local fallback",
                  not resolve_data_root().startswith(
                      os.path.abspath(ROOT) + os.sep))
        finally:
            os.environ.clear()
            os.environ.update(old_env)

        # Platform branches (monkeypatched platform.system — the
        # code under test reads it at call time).
        try:
            os.environ["HOME"] = home_tmp
            with mock.patch.object(platform, "system",
                                   return_value="Darwin"):
                check("CF-P1-001-PROF-16: macOS uses Application Support",
                      resolve_data_root() == os.path.join(
                          home_tmp, "Library", "Application Support",
                          "consistency-frame"))
            with mock.patch.object(platform, "system",
                                   return_value="Windows"):
                os.environ["LOCALAPPDATA"] = os.path.join(
                    home_tmp, "localappdata")
                check("CF-P1-001-PROF-17: Windows uses LOCALAPPDATA",
                      resolve_data_root() == os.path.join(
                          home_tmp, "localappdata", "consistency-frame"))
                del os.environ["LOCALAPPDATA"]
                try:
                    resolve_data_root()
                    raised = False
                except ProfileError:
                    raised = True
                check("CF-P1-001-PROF-18: missing LOCALAPPDATA fails "
                      "closed (no silent fallback)", raised)
        finally:
            os.environ.clear()
            os.environ.update(old_env)

        # POSIX permissions on created state.
        mode_dir = stat.S_IMODE(os.stat(root_a).st_mode)
        mode_file = stat.S_IMODE(
            os.stat(profile_a.profile_path).st_mode)
        check("CF-P1-001-PROF-19: data directory is 0700, profile is 0600",
              mode_dir == 0o700 and mode_file == 0o600,
              f"dir={oct(mode_dir)} file={oct(mode_file)}")

        # ----------------------------------------------------------
        # Session integrity (CF-P1-001-SESS)
        # ----------------------------------------------------------
        check("CF-P1-001-SESS-01: genuine active session is accepted",
              is_active_session(session_a))
        check("CF-P1-001-SESS-02: validate_session accepts an active session",
              validate_session(session_a) == [])

        check("CF-P1-001-SESS-03: close returns True, then False",
              close_session(session_a) is True
              and close_session(session_a) is False)
        check("CF-P1-001-SESS-04: closed session is rejected",
              not is_active_session(session_a)
              and validate_session(session_a) == ["session is closed"])
        try:
            close_session(None)
            raised = False
        except SessionError:
            raised = True
        check("CF-P1-001-SESS-05: closing a non-session raises",
              raised)
        try:
            close_session(SimpleNamespace(session_id="x"))
            raised = False
        except SessionError:
            raised = True
        check("CF-P1-001-SESS-06: closing a forged object raises",
              raised)

        short = start_session(profile_a, profile_a.workspace_id,
                              lifetime_seconds=1)
        time.sleep(2.0)
        check("CF-P1-001-SESS-07: expired session is rejected",
              not is_active_session(short)
              and len(validate_session(short)) == 1
              and "expired" in validate_session(short)[0])

        try:
            LocalSession(session_id="x", owner_id="owner-a",
                         workspace_id="workspace-a",
                         created_at="2026-01-01T00:00:00Z",
                         expires_at="2026-01-02T00:00:00Z")
            raised = False
        except TypeError:
            raised = True
        check("CF-P1-001-SESS-08: direct construction is rejected",
              raised)
        try:
            LocalSession(_boundary="fake", session_id="x",
                         owner_id="owner-a", workspace_id="workspace-a",
                         created_at="2026-01-01T00:00:00Z",
                         expires_at="2026-01-02T00:00:00Z")
            raised = False
        except TypeError:
            raised = True
        check("CF-P1-001-SESS-09: forged boundary sentinel is rejected",
              raised)

        try:
            class _Evil(LocalSession):
                pass
            raised = False
        except TypeError:
            raised = True
        check("CF-P1-001-SESS-10: subclass definition raises TypeError",
              raised)
        Spoof = _define_spoof_subclass("_SpoofSession")
        spoof = object.__new__(Spoof)
        for slot, value in (
                ("session_id", session_a2.session_id),
                ("owner_id", session_a2.owner_id),
                ("workspace_id", session_a2.workspace_id),
                ("created_at", session_a2.created_at),
                ("expires_at", session_a2.expires_at),
                ("_frozen", True)):
            object.__setattr__(spoof, slot, value)
        check("CF-P1-001-SESS-11: subclass spoofing is rejected",
              not is_active_session(spoof)
              and validate_session(spoof) == [
                  "not a LocalSession issued by start_session()"])

        forged_ns = SimpleNamespace(
            session_id=session_a2.session_id,
            owner_id=session_a2.owner_id,
            workspace_id=session_a2.workspace_id,
            created_at=session_a2.created_at,
            expires_at=session_a2.expires_at)
        check("CF-P1-001-SESS-12: forged lookalike object is rejected",
              not is_active_session(forged_ns))

        built = object.__new__(LocalSession)
        for slot, value in (
                ("session_id", session_a2.session_id),
                ("owner_id", session_a2.owner_id),
                ("workspace_id", session_a2.workspace_id),
                ("created_at", session_a2.created_at),
                ("expires_at", session_a2.expires_at),
                ("_frozen", True)):
            object.__setattr__(built, slot, value)
        check("CF-P1-001-SESS-13: __new__-built object is rejected",
              not is_active_session(built)
              and validate_session(built) == [
                  "session was not issued by start_session()"])

        shallow = copy.copy(session_a2)
        deep = copy.deepcopy(session_a2)
        check("CF-P1-001-SESS-14: shallow copy cannot create an accepted "
              "session",
              shallow is not session_a2
              and not is_active_session(shallow))
        check("CF-P1-001-SESS-15: deep copy cannot create an accepted "
              "session",
              deep is not session_a2
              and not is_active_session(deep))

        try:
            pickle.dumps(session_a2)
            raised = False
        except TypeError:
            raised = True
        check("CF-P1-001-SESS-16: pickling a session raises TypeError",
              raised)
        try:
            session_a2.__setstate__({})
            raised = False
        except TypeError:
            raised = True
        check("CF-P1-001-SESS-17: __setstate__ raises TypeError", raised)

        data_root_files = []
        for dirpath, _dirnames, filenames in os.walk(root_a):
            for fn in filenames:
                data_root_files.append(os.path.join(dirpath, fn))
        session_leaked = False
        for path in data_root_files:
            with open(path, "rb") as f:
                if session_a2.session_id.encode() in f.read():
                    session_leaked = True
        check("CF-P1-001-SESS-18: sessions are never persisted to disk",
              not session_leaked
              and data_root_files == [profile_a.profile_path])

        try:
            session_a2.owner_id = "owner-evil"
            raised = False
        except AttributeError:
            raised = True
        check("CF-P1-001-SESS-19: session fields are immutable", raised)

        seen = []
        local_session.register_session_close_handler(
            lambda s: seen.append(s.session_id))
        check("CF-P1-001-SESS-20: close handler runs on close",
              close_session(session_a2) is True
              and seen == [session_a2.session_id])

        def _boom(session):
            raise RuntimeError("handler boom")

        local_session.register_session_close_handler(_boom)
        victim = start_session(profile_a, profile_a.workspace_id)
        try:
            close_session(victim)
            raised = False
        except RuntimeError:
            raised = True
        check("CF-P1-001-SESS-21: a failing handler cannot leave the "
              "session active",
              raised and not is_active_session(victim))

        # Restart: new session, same stable IDs.
        profile_a3 = load_or_create_profile(root_a)
        session_a3 = start_session(profile_a3, profile_a3.workspace_id)
        check("CF-P1-001-SESS-22: restart keeps IDs, mints a new session",
              profile_a3.owner_id == profile_a.owner_id
              and profile_a3.workspace_id == profile_a.workspace_id
              and session_a3.session_id != session_a2.session_id
              and is_active_session(session_a3))

        try:
            start_session(profile_a, profile_b.workspace_id)
            raised = False
        except SessionError:
            raised = True
        check("CF-P1-001-SESS-23: a workspace the profile does not hold "
              "is refused", raised)
        try:
            start_session(profile_a, "Not A Workspace!")
            raised = False
        except SessionError:
            raised = True
        check("CF-P1-001-SESS-24: a malformed workspace ID is refused",
              raised)
        bad_lifetimes = (0, -5, 999999, "3600", True)
        all_refused = True
        for bad_lifetime in bad_lifetimes:
            try:
                start_session(profile_a, profile_a.workspace_id,
                              lifetime_seconds=bad_lifetime)
                all_refused = False
            except SessionError:
                pass
        check("CF-P1-001-SESS-25: bad lifetimes are refused",
              all_refused)
        try:
            start_session({"owner_id": profile_a.owner_id},
                          profile_a.workspace_id)
            raised = False
        except SessionError:
            raised = True
        check("CF-P1-001-SESS-26: a dict is not a profile", raised)

        # ----------------------------------------------------------
        # Filesystem security (CF-P1-001-FS)
        # ----------------------------------------------------------
        _path, errors = asset_policy.resolve_private_path(
            root_a, "../escape.json")
        check("CF-P1-001-FS-01: path traversal is rejected",
              bool(errors) and _path is None)
        _path, errors = asset_policy.resolve_private_path(
            root_a, "/etc/passwd")
        check("CF-P1-001-FS-02: absolute paths are rejected",
              bool(errors) and _path is None)
        outside = new_root()
        outside_file = os.path.join(outside, "secret.json")
        with open(outside_file, "w", encoding="utf-8") as f:
            f.write("{}")
        os.symlink(outside_file, os.path.join(root_a, "link.json"))
        _path, errors = asset_policy.resolve_private_path(
            root_a, "link.json")
        check("CF-P1-001-FS-03: symlink escape is rejected",
              bool(errors) and _path is None)

        root_link = new_root()
        target = os.path.join(new_root(), "real-profile.json")
        with open(target, "w", encoding="utf-8") as f:
            json.dump(_valid_profile_dict(
                "owner-aaaa0001", "workspace-aaaa0001"), f)
        os.symlink(target, os.path.join(root_link, "profile.json"))
        try:
            load_or_create_profile(root_link)
            raised = False
        except ProfileError:
            raised = True
        check("CF-P1-001-FS-04: a symlinked profile is refused",
              raised)
        check("CF-P1-001-FS-04b: the symlink target is untouched",
              json.load(open(target, encoding="utf-8"))[
                  "owner_id"] == "owner-aaaa0001")

        root_keep = new_root()
        keep_path = _write_profile_bytes(
            root_keep,
            json.dumps(_valid_profile_dict(
                "owner-keep0001", "workspace-keep0001")).encode())
        keep_before = open(keep_path, "rb").read()
        try:
            load_or_create_profile(root_keep)
        except ProfileError:
            pass
        check("CF-P1-001-FS-05: a valid profile survives a load",
              open(keep_path, "rb").read() == keep_before)

        # Atomic-write failure must not destroy the previous profile.
        root_atomic = new_root()
        atomic_path = _write_profile_bytes(
            root_atomic,
            json.dumps(_valid_profile_dict(
                "owner-atom0001", "workspace-atom0001")).encode())
        atomic_before = open(atomic_path, "rb").read()
        import atomic_write
        with mock.patch.object(
                atomic_write.tempfile, "mkstemp",
                side_effect=OSError("injected mkstemp failure")):
            try:
                atomic_write.atomic_write_json(
                    atomic_path, {"schema_version": 1}, mode=0o600)
                raised = False
            except OSError:
                raised = True
        check("CF-P1-001-FS-06: atomic-write failure leaves the previous "
              "profile intact",
              raised and open(atomic_path, "rb").read() == atomic_before)

        # First-use write failure leaves no half-written profile.
        root_nowrite = new_root()
        with mock.patch.object(
                local_session, "atomic_write_json",
                side_effect=OSError("injected write failure")):
            try:
                load_or_create_profile(root_nowrite)
                raised = False
            except ProfileError:
                raised = True
        check("CF-P1-001-FS-07: first-use write failure leaves no profile",
              raised
              and not os.path.exists(
                  os.path.join(root_nowrite, "profile.json")))
    finally:
        for root in tmp_roots:
            shutil.rmtree(root, ignore_errors=True)

    print()
    if failures:
        print(f"test_local_session_runtime: FAIL "
              f"({len(failures)} failure(s))")
        for name in failures:
            print(f"  FAIL {name}")
        return 1
    print("test_local_session_runtime: PASS (0 failure(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
