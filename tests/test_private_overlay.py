#!/usr/bin/env python3
"""P0 private-overlay tests. Run via tests/run-tests.sh or directly:
  python3 tests/test_private_overlay.py
Exit 0 = PASS, 1 = FAIL. Test ID: P0-PRIVACY.
"""
import os
import subprocess
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
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

    print(f"test_private_overlay: {'PASS' if not failures else 'FAIL'} "
          f"({len(failures)} failure(s))")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
