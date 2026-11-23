#!/usr/bin/env python3
"""P0 private-overlay tests. Run via tests/run-tests.sh or directly:
  python3 tests/test_private_overlay.py
Exit 0 = PASS, 1 = FAIL. Test ID: P0-PRIVACY.
"""
import copy
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import asset_policy  # noqa: E402
failures = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


def git_ls_files():
    out = subprocess.run(["git", "-C", ROOT, "ls-files"], capture_output=True,
                         text=True, check=True).stdout
    return out.splitlines()


def main():
    tracked = git_ls_files()

    # Only .gitkeep + README.md may be tracked under characters/.
    char_tracked = sorted(p for p in tracked if p.startswith("characters/"))
    check("only .gitkeep + README.md tracked under characters/",
          char_tracked == ["characters/.gitkeep", "characters/README.md"],
          f"tracked={char_tracked}")

    # No media files tracked anywhere (docs images are not in this repo).
    media = [p for p in tracked
             if p.lower().endswith((".mp3", ".mp4", ".wav", ".webm", ".mov",
                                    ".png", ".jpg", ".jpeg"))]
    check("no media files tracked in git", not media, f"tracked media={media}")

    # .gitignore covers the private paths.
    gi = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
    for needle in ("characters/*", "*.mp3", "*.mp4", "*.wav", ".env",
                   "components/", ".agents/skills/"):
        check(f".gitignore covers '{needle}'", needle in gi)

    # A hypothetical private character path is ignored by git (each path checked).
    ignored = []
    for p in ("characters/someone-0001/character.yaml",
              "characters/someone-0001/reference-front.jpg",
              "private-data/voice-reference.mp3"):
        r = subprocess.run(["git", "-C", ROOT, "check-ignore", "-q", p],
                           capture_output=True)
        ignored.append(r.returncode == 0)
    check("private character/media paths are git-ignored", all(ignored),
          f"ignored={ignored}")

    # No private media on disk under characters/ (only the two safe files).
    on_disk = sorted(os.listdir(os.path.join(ROOT, "characters")))
    check("characters/ on disk holds only .gitkeep + README.md",
          on_disk == [".gitkeep", "README.md"], f"on disk={on_disk}")

    # The private overlay is documented.
    check("characters/README.md documents the private overlay",
          os.path.exists(os.path.join(ROOT, "characters", "README.md")))

    # --- CF-WO-P0-007 (B): private ownership + export + path safety --
    # A full valid v2.5 private voice profile (owner-a / workspace-a).
    with open(os.path.join(
            ROOT, "tests", "fixtures",
            "voice-profile-valid-user-recorded.json"),
            encoding="utf-8") as f:
        voice = json.load(f)

    # Private voice export (CF-WO-P0-008 B): a caller-created dict is
    # an untrusted request, never authority. Only a trusted context
    # issued by the application boundary authorizes an export.
    check("B: private voice export blocked without any authorization "
          "context",
          bool(asset_policy.validate_private_voice_export(voice)))
    check("B: private voice export blocked with a caller-created "
          "authorization dict",
          bool(asset_policy.validate_private_voice_export(
              voice, {"granted_by": "owner-a",
                      "scope": "export voice-nila-001 for backup",
                      "explicit_authorisation": True})))
    _export_ctx = asset_policy.issue_trusted_authorization_context(
        actor_owner_id="owner-a", actor_workspace_id="workspace-a",
        granted_by="owner-a",
        scope="export voice-nila-001 for backup",
        action="export_private_asset", character_id="char-nila-001",
        voice_profile_id="voice-nila-001")
    check("B: private voice export allowed under a trusted "
          "authorization context",
          not asset_policy.validate_private_voice_export(
              voice, trusted_context=_export_ctx))

    # Private media is never in a public release manifest.
    check("B: release manifest check rejects private media paths",
          bool(asset_policy.validate_release_manifest_paths(
              ["characters/char-nila-001/voice-reference.mp3"]))
          and bool(asset_policy.validate_release_manifest_paths(
              ["private-data/voice-reference.mp3"]))
          and bool(asset_policy.validate_release_manifest_paths(
              ["docs/guide.mp3"]))
          and not asset_policy.validate_release_manifest_paths(
              ["characters/README.md", "docs/07-character-registry.md"]))
    check("B: a manifest that smuggles one private path is rejected "
          "as a whole",
          bool(asset_policy.validate_release_manifest_paths(
              ["docs/07-character-registry.md",
               "characters/char-nila-001/reference-front.jpg"])))

    # Private data path traversal is rejected.
    for bad_path in ("../outside/secret.jpg", "/etc/passwd",
                     "char-nila-001/../../etc/passwd", "",
                     "char-nila-001//voice.mp3"):
        _, errs = asset_policy.resolve_private_path("characters", bad_path)
        check(f"B: private path traversal rejected: {bad_path!r}",
              bool(errs), "; ".join(errs))
    resolved, errs = asset_policy.resolve_private_path(
        "characters", "char-nila-001/voice-reference.mp3")
    check("B: a safe private path inside the base resolves",
          not errs and resolved is not None
          and resolved.startswith(os.path.realpath(
              os.path.join(ROOT, "characters"))),
          "; ".join(errs))

    # Symlink / path escape attempts are rejected where relevant.
    with tempfile.TemporaryDirectory() as tmp:
        base = os.path.join(tmp, "characters")
        outside = os.path.join(tmp, "outside")
        os.makedirs(os.path.join(base, "char-nila-001"))
        os.makedirs(outside)
        with open(os.path.join(outside, "secret.mp3"), "w") as f:
            f.write("not yours")
        os.symlink(outside, os.path.join(base, "escape"))
        _, errs = asset_policy.resolve_private_path(
            base, "escape/secret.mp3")
        check("B: symlink escape out of the private base is rejected",
              bool(errs), "; ".join(errs))
        os.symlink(os.path.join(base, "char-nila-001"),
                   os.path.join(base, "alias"))
        resolved, errs = asset_policy.resolve_private_path(
            base, "alias/voice-reference.mp3")
        check("B: a symlink staying inside the private base resolves",
              not errs and resolved is not None, "; ".join(errs))

    # Privateness is decided by ownership, never by a folder being
    # named "private": a record pointing under a folder literally
    # named "private" is still rejected for another owner, and a
    # public document under such a folder is still releasable.
    other_owner_voice = copy.deepcopy(voice)
    check("B: a 'private'-named folder does not decide access — "
          "ownership does (other owner rejected)",
          not asset_policy.ownership_allows_access(
              other_owner_voice["ownership"], "owner-b", "workspace-b"))
    check("B: a 'private'-named folder does not make a public doc "
          "private",
          not asset_policy.validate_release_manifest_paths(
              ["private/notes.md"]))
    check("B: media under a 'private'-named folder is still not "
          "releasable (media rule, not folder name)",
          bool(asset_policy.validate_release_manifest_paths(
              ["private/voice-reference.mp3"])))

    print(f"test_private_overlay: {'PASS' if not failures else 'FAIL'} "
          f"({len(failures)} failure(s))")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
