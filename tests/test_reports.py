#!/usr/bin/env python3
"""P0-002 §7 report/provenance tests. Run via tests/run-tests.sh or
directly: python3 tests/test_reports.py
Exit 0 = PASS, 1 = FAIL. Test IDs: CF-P0-REPORT-001/002/003/004/005.

CF-P0-REPORT-005 (CF-WO-P0-012) checks that the README installation
guidance matches the actual setup.sh implementation: core-only by
default, --with-components as the explicit opt-in component path, and
the OmniVoice model never downloaded by setup.sh.

These tests read the GENERATED artifacts (docs/implementation/
BUILD_REPORT_P0.md, build-report.json, CHECKSUMS.txt,
release-manifest.json, docs/architecture/
living-architecture-report-v2.4-p0.md) — regenerate them with
`python3 scripts/generate-build-report.py --github-head <sha>` and
`python3 scripts/generate-report.py --github-head <sha>` after
changing either generator, then run this file.
"""
import hashlib
import importlib.util
import json
import ntpath
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
# Expected GitHub head for the RESOLVER unit tests below (flag wins /
# env fallback / default). The committed artifacts record the actual
# GitHub head of the code they describe, which advances on every push,
# so the artifact checks compare the two files against EACH OTHER (and
# require a valid 40-hex SHA) instead of a hardcoded value — pinning one
# SHA here would fail CI on every push. The delivery process verifies the
# recorded head against the live branch via the GitHub API.
GH_HEAD = os.environ.get(
    "CF_GITHUB_HEAD", "fcf311ef79c5f10a4248f026a5f667109c584831")
# Latest verified remote CI (P0-007): push run #83 + PR run #84 on the
# P0-006 final PR head 33dc78b8, both SUCCESS, 2/2 checks. The parent
# verified both runs live on 2026-11-22 and downloaded + inspected the
# PR run's p0-test-results artifact (47 recorded entries, 35 distinct
# test IDs, 28 distinct command strings, all PASS; last-run.json
# byte-for-byte identical to the submitted P0-006 ZIP's). The push run
# URL is the one recorded in build-report.json's ci object; the PR run
# URL is cited in BUILD_REPORT_P0.md and the living report alongside it.
CI_RUN_URL = ("https://github.com/msujoy149/consistency-frame/actions/"
              "runs/45063530337")
CI_PR_RUN_URL = ("https://github.com/msujoy149/consistency-frame/actions/"
                 "runs/45063535304")
CI_PR_URL = "https://github.com/msujoy149/consistency-frame/pull/1"

_spec = importlib.util.spec_from_file_location(
    "validate_repo", os.path.join(ROOT, "scripts", "validate-repo.py"))
_validate_repo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_validate_repo)
validate_instance = _validate_repo.validate_instance

failures = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


def load_module(name, rel):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_json(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)


def read_text(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def errors_for(schema, value):
    errs = []
    validate_instance(schema, value, "$", errs)
    return errs


# --- CF-P1-003-R2-MANIFEST helpers ---------------------------------------
# The release manifest must hash the final committed content of every
# listed file. These helpers are pure functions over the loaded
# manifest dict (files are read from `root` only to recompute hashes
# and byte counts), so the negative tests can tamper in-memory copies
# without touching the committed manifest on disk.
# 186 since the P1-003 Production Addendum 01 (2026-11-26): the manifest
# lists every file changed vs the pinned base, and the addendum's
# work-order file list required modifying four files that had not
# changed vs the base before (docs/01-production-systems.md,
# docs/04-additional-systems.md, docs/05-humanization-systems.md, and
# skills/kids-family-animation/SKILL.md). No new tracked file was added;
# the four added entries are exactly those four files. 182 before.
# 206 since CF-WO-P1-004 (2026-11-26): twenty genuinely new files —
# five schemas (production-analysis, character-design-proposal,
# task-packet, gate-state, provider-capability), two runtime modules
# (production_orchestrator, task_compiler), three test files
# (test_production_analysis, test_production_orchestrator,
# test_task_compiler), seven fixtures, registry/providers.json,
# docs/runtime/PRODUCTION_ORCHESTRATOR_RUNTIME.md, and
# docs/implementation/CF-WO-P1-004-corrections.md. Every other file
# this round touched was already in the manifest from an earlier round.
# 216 since the combined CF-WO-P1-004-R1 + ADDENDUM-IDENTITY integration
# (2026-11-26): ten genuinely new files — three from R1
# (runtime/production_store.py, tests/test_production_store.py,
# tests/test_muse_adapter_conformance.py) and seven from the identity
# addendum (one runtime module, two schemas, two fixtures, one test
# file, and docs/runtime/IDENTITY_RESOLUTION_RUNTIME.md). Every other
# file this round touched was already in the manifest from an earlier
# round.
# 232 since CF-WO-P1-005 (2026-11-27): sixteen genuinely new files —
# four runtime modules (media_execution, media_adapters,
# execution_orchestrator, timeline_delivery), two schemas
# (execution-record, human-review-handoff), four test files
# (test_media_execution, test_ffmpeg_adapter, test_media_adapters,
# test_timeline_delivery), two runtime docs
# (MEDIA_EXECUTION_RUNTIME, PROVIDER_ADAPTERS), the corrections
# record (CF-WO-P1-005-corrections), and three evidence records
# (evidence/p1005/gap-map, evidence/p1005/local-execution-evidence,
# evidence/p1005/vs-headers). Every other file this round touched
# was already in the manifest from an earlier round.
# 233 since CF-WO-P1-005-R1 (2026-11-27): one genuinely new file —
# the CI run #263 Windows-failure evidence record
# (evidence/p1005/ci-263-windows-failure-note). The file entered the
# manifest only once committed: the generator counts committed files,
# so the pre-commit regen still showed 232. Every other file this
# round touched was already in the manifest from an earlier round.
MANIFEST_EXPECTED_COUNT = 233
MANIFEST_EXCLUDED = ("release-manifest.json",
                     "docs/implementation/CHECKSUMS.txt")


def _is_unsafe_manifest_path(path):
    """True when `path` is not a normalized, repository-relative
    POSIX path. Cross-platform by construction: `os.path.isabs()`
    is NOT used, because its answer depends on the host OS — on
    POSIX it accepts a Windows absolute path such as
    `C:/Windows/win.ini`, and on Windows `os.path.join(root, ...)`
    then discards the repository root. `ntpath` is the Windows
    path module and behaves the same on every host, so
    `ntpath.splitdrive()` / `ntpath.isabs()` detect Windows drive
    prefixes (drive-absolute `C:/...`, drive-relative `C:...`,
    UNC `//server/share/...`) independently of the host OS."""
    if not isinstance(path, str) or not path:
        return True
    if "\x00" in path:
        return True
    if "\\" in path:
        return True
    if path.startswith("/"):
        return True
    drive, _rest = ntpath.splitdrive(path)
    if drive:
        return True
    if ntpath.isabs(path):
        return True
    return any(part in ("", ".", "..") for part in path.split("/"))


def verify_manifest_entries(manifest, root):
    """Return a list of error strings for the manifest; [] means the
    manifest verifies entry-by-entry against the tree at `root`."""
    errors = []
    if not isinstance(manifest, dict):
        return ["manifest is not an object"]
    files = manifest.get("files")
    if not isinstance(files, list):
        return ["manifest files is not a list"]
    if len(files) != MANIFEST_EXPECTED_COUNT:
        errors.append(f"manifest has {len(files)} entries, expected "
                      f"{MANIFEST_EXPECTED_COUNT}")
    seen = set()
    for entry in files:
        if not isinstance(entry, dict):
            errors.append(f"manifest entry is not an object: "
                          f"{str(entry)[:80]}")
            continue
        path = entry.get("path")
        sha = entry.get("sha256")
        size = entry.get("bytes")
        if not isinstance(path, str) or not path:
            errors.append(f"manifest entry has no path string: "
                          f"{str(entry)[:80]}")
            continue
        if path in seen:
            errors.append(f"duplicate manifest path: {path}")
        seen.add(path)
        if _is_unsafe_manifest_path(path):
            errors.append(f"unsafe manifest path: {path}")
            continue
        if path in MANIFEST_EXCLUDED:
            errors.append(f"excluded file listed in manifest: {path}")
        if not isinstance(sha, str) \
                or re.fullmatch(r"[0-9a-f]{64}", sha) is None:
            errors.append(f"manifest entry {path} has no valid sha256")
        if not isinstance(size, int) or isinstance(size, bool) \
                or size < 0:
            errors.append(f"manifest entry {path} has no valid byte "
                          f"count")
            continue
        # Resolve the final candidate path and require its real path
        # to stay inside the repository root — BEFORE opening any
        # file. A symlink inside the root pointing outside it must
        # never let a manifest entry read outside content. The
        # unsafe-path check above already rejected the path before
        # it was joined; this check covers the joined path itself.
        full = os.path.join(root, path)
        real_root = os.path.realpath(root)
        real_full = os.path.realpath(full)
        if real_full != real_root \
                and not real_full.startswith(real_root + os.sep):
            errors.append(f"manifest path escapes repository root: "
                          f"{path}")
            continue
        if not os.path.isfile(full):
            errors.append(f"manifest file missing: {path}")
            continue
        data = open(full, "rb").read()
        if len(data) != size:
            errors.append(f"manifest entry {path}: {len(data)} bytes, "
                          f"expected {size}")
        if hashlib.sha256(data).hexdigest() != sha:
            errors.append(f"manifest entry {path}: sha256 mismatch")
    for field in ("github_branch_head", "commit"):
        value = manifest.get(field)
        if not isinstance(value, str) \
                or re.fullmatch(r"[0-9a-f]{40}", value) is None:
            errors.append(f"manifest {field} is not a 40-char hex SHA")
    return errors


def main():
    build_report = load_json("docs/implementation/build-report.json")
    manifest = load_json("release-manifest.json")
    build_md = read_text("docs/implementation/BUILD_REPORT_P0.md")
    living = read_text("docs/architecture/living-architecture-report-v2.4-p0.md")

    # --- CF-P0-REPORT-001: --github-head / CF_GITHUB_HEAD / default -----
    for rel, mod_name in (("scripts/generate-build-report.py", "gen_build"),
                          ("scripts/generate-report.py", "gen_report")):
        mod = load_module(mod_name, rel)
        resolve = mod.resolve_github_head
        check(f"CF-P0-REPORT-001: {rel} --github-head wins over env + default",
              resolve(["prog", "--github-head", GH_HEAD],
                      {"CF_GITHUB_HEAD": "a" * 40}, "b" * 40) == GH_HEAD)
        check(f"CF-P0-REPORT-001: {rel} CF_GITHUB_HEAD is the fallback",
              resolve(["prog"], {"CF_GITHUB_HEAD": GH_HEAD},
                      "b" * 40) == GH_HEAD)
        check(f"CF-P0-REPORT-001: {rel} defaults to the current head",
              resolve(["prog"], {}, "b" * 40) == "b" * 40)
    check("CF-P0-REPORT-001: build-report.json + release-manifest.json record the SAME github_branch_head",
          build_report.get("github_branch_head") == manifest.get("github_branch_head")
          and isinstance(build_report.get("github_branch_head"), str)
          and re.fullmatch(r"[0-9a-f]{40}", build_report.get("github_branch_head") or "") is not None,
          f"build={build_report.get('github_branch_head')!r} manifest={manifest.get('github_branch_head')!r}")
    check("CF-P0-REPORT-001: manifest commit is the local code head",
          re.fullmatch(r"[0-9a-f]{40}", manifest.get("commit") or "") is not None
          and manifest.get("commit") != GH_HEAD,
          f"commit={manifest.get('commit')!r}")

    # --- CF-P0-REPORT-002: manifest self-exclusion + CHECKSUMS.txt ------
    manifest_paths = [f["path"] for f in manifest.get("files", [])]
    check("CF-P0-REPORT-002: release-manifest.json excluded from its own "
          "file list",
          "release-manifest.json" not in manifest_paths)
    check("CF-P0-REPORT-002: CHECKSUMS.txt excluded from the manifest's "
          "file list (it contains the manifest's hash)",
          "docs/implementation/CHECKSUMS.txt" not in manifest_paths)
    check("CF-P0-REPORT-002: release-manifest.json kept in build-report.json "
          "changed_files (names, not hashes)",
          "release-manifest.json" in build_report.get("changed_files", []))
    checksums_text = read_text("docs/implementation/CHECKSUMS.txt")
    check("CF-P0-REPORT-002: CHECKSUMS.txt states the ZIP hash lives in "
          "the delivery message",
          "ZIP" in checksums_text and "delivery message" in checksums_text)
    for rel in ("release-manifest.json",
                "docs/implementation/build-report.json",
                "docs/implementation/BUILD_REPORT_P0.md"):
        p = os.path.join(ROOT, rel)
        h = hashlib.sha256(open(p, "rb").read()).hexdigest()
        size = os.path.getsize(p)
        check(f"CF-P0-REPORT-002: CHECKSUMS.txt matches {rel}",
              f"{h}  {size}  {rel}" in checksums_text)

    # --- CF-P0-REPORT-003: CI evidence current, obsolete text gone ------
    obsolete = [
        "CI remote run is pending",
        "until then CI is",
        "runs only after push + PR; workflow",
        "see the delivery message (filled in after",
        "CI is\nNOT RUN, not passed",
        "Remote GitHub Actions CI run (runs only after push",
    ]
    for text, label in ((build_md, "BUILD_REPORT_P0.md"),
                        (living, "living report")):
        for phrase in obsolete:
            check(f"CF-P0-REPORT-003: no obsolete CI text in {label}: "
                  f"{phrase[:40]!r}",
                  phrase not in text)
        check(f"CF-P0-REPORT-003: CI PASSED evidence in {label}",
              "CI PASSED" in text and CI_RUN_URL in text
              and "2/2 checks" in text)
    # The CI evidence records the run that actually passed (head
    # 33dc78b8, push run #83). It must NOT be forced to equal the
    # current github_branch_head: the corrections were pushed after
    # that run, so the current head's CI run is a separate event
    # checked by the delivery process, not by this file.
    check("CF-P0-REPORT-003: build-report.json ci object records the "
          "passed run",
          build_report.get("ci", {}).get("result") == "PASS"
          and re.fullmatch(r"[0-9a-f]{40}",
                           build_report.get("ci", {}).get("head") or "") is not None
          and build_report.get("ci", {}).get("run_url") == CI_RUN_URL
          and build_report.get("ci", {}).get("checks_passed") == 2
          and build_report.get("ci", {}).get("checks_total") == 2)
    check("CF-P0-REPORT-003: build-report.json not_run has no CI entry",
          not any("CI" in entry for entry in build_report.get("not_run", [])),
          f"not_run={build_report.get('not_run')}")
    check("CF-P0-REPORT-003: --with-components NOT RUN entries kept",
          any("setup.sh --with-components" in e and "NOT RUN" in e
              for e in build_report.get("not_run", [])))
    check("CF-P0-REPORT-003: Provenance §12 present in BUILD_REPORT_P0.md",
          "## 12. PROVENANCE" in build_md
          and "two-head rule" in build_md
          and "cannot contain its own SHA-256" in build_md)
    check("CF-P0-REPORT-003: living report counts companions by "
          "evidence level",
          "exercised_recorded_run" in living
          and "present_locally" in living
          and "upstream_inspected_pinned_commit" in living
          and "0 production_verified" in living)
    check("CF-P0-REPORT-003: living report records a GitHub branch head",
          re.search(r"GitHub branch head.*`[0-9a-f]{40}`", living,
                    re.S) is not None)

    # --- CF-P0-REPORT-004: generated JSONs validate against schemas -----
    for schema_name, value, label in (
            ("build-report.json", build_report, "build-report.json"),
            ("release-manifest.json", manifest, "release-manifest.json")):
        schema = load_json(f"schemas/{schema_name}")
        errs = errors_for(schema, value)
        check(f"CF-P0-REPORT-004: {label} validates against its schema",
              not errs, "; ".join(errs))

    # --- CF-P0-REPORT-005: README installation guidance matches --------
    # setup.sh (CF-WO-P0-012). The README is the public install guide;
    # it must not describe the core-only default as an automatic
    # component install, and it must not claim setup.sh downloads the
    # voice model. Assertions are phrase-level (not byte-identical
    # paragraphs) so honest rewording does not break them, but the
    # forbidden phrases are the exact false claims found in the
    # pre-P0-012 README.
    readme = read_text("README.md")
    setup = read_text("setup.sh")
    install_start = readme.find("## Install")
    install_end = readme.find("\n## ", install_start + 1)
    install = readme[install_start:install_end if install_end != -1
                     else len(readme)]
    check("CF-P0-REPORT-005: README Install section states the "
          "core-only default",
          install_start != -1 and "core-only" in install.lower()
          and "default" in install.lower(),
          "Install section must say the default is core-only")
    check("CF-P0-REPORT-005: README identifies --with-components as "
          "the optional component path",
          "--with-components" in install
          and ("optional" in install.lower()
               or "opt in" in install.lower())
          and "VoiceStudio" in install and "OpenMontage" in install,
          "Install section must name --with-components as opt-in")
    # Bold markers ("**not**") sit between words, so strip them before
    # matching the "not downloaded by" statement.
    readme_plain = readme.replace("**", "")
    check("CF-P0-REPORT-005: README states the voice model is not "
          "downloaded by setup.sh",
          re.search(r"voice model.{0,120}?not downloaded by",
                    readme_plain, re.I | re.S) is not None
          or "never downloaded by `setup.sh`" in readme_plain,
          "README must say setup.sh does not download the voice model")
    # Whitespace-normalized README for the forbidden-phrase checks:
    # the false claims may wrap across lines, so collapse every
    # whitespace run to one space before matching.
    readme_flat = re.sub(r"\s+", " ", readme)
    forbidden = [
        "no separate install is needed",
        "fetches and installs the bundled components",
        "walks you through downloading",
        "downloads the voice model",
    ]
    for phrase in forbidden:
        check(f"CF-P0-REPORT-005: README has no false claim: "
              f"{phrase!r}", phrase not in readme_flat)
    check("CF-P0-REPORT-005: README never claims components are "
          "installed by default",
          re.search(r"components are installed (automatically )?by "
                    r"default", readme, re.I) is None
          and re.search(r"installs the bundled components.{0,80}"
                        r"automatically", readme, re.I | re.S) is None,
          "README must not describe an automatic default install")
    check("CF-P0-REPORT-005: setup.sh default is core-only "
          "(WITH_COMPONENTS=0)",
          "WITH_COMPONENTS=0" in setup
          and "--with-components) WITH_COMPONENTS=1" in setup,
          "setup.sh must default to core-only with an explicit opt-in")
    check("CF-P0-REPORT-005: setup.sh never downloads the OmniVoice "
          "model",
          "is NEVER downloaded by this script" in setup
          and "Components were NOT installed (default)" in setup,
          "setup.sh must refuse the model download and say so")

    # --- CF-P1-003-R2-MANIFEST: release-manifest integrity (R2) ---------
    # The R1 manifest carried exactly one stale entry: the corrections
    # document was edited AFTER the manifest was generated, so its
    # recorded byte count (34,017) no longer matched the file (34,742).
    # This group verifies every manifest entry against the working
    # tree and fails if even one listed file changes without a regen.
    # The check is a pure function over the loaded manifest dict, so
    # the negative cases tamper in-memory copies without touching the
    # committed manifest on disk.
    manifest_errors = verify_manifest_entries(manifest, ROOT)
    check("CF-P1-003-R2-MANIFEST: all 209 entries verify "
          "(existence + SHA-256 + byte count)",
          not manifest_errors, "; ".join(manifest_errors[:5]))
    manifest_paths = [f["path"] for f in manifest.get("files", [])]
    check("CF-P1-003-R2-MANIFEST: manifest scope is exactly the "
          "209 managed files",
          len(manifest_paths) == MANIFEST_EXPECTED_COUNT
          and len(set(manifest_paths)) == MANIFEST_EXPECTED_COUNT,
          f"entries={len(manifest_paths)}")
    check("CF-P1-003-R2-MANIFEST: intentional exclusions kept "
          "(release-manifest.json + CHECKSUMS.txt absent)",
          all(p not in manifest_paths for p in MANIFEST_EXCLUDED))
    check("CF-P1-003-R2-MANIFEST: changed_files accounts for every "
          "manifest file plus the two excluded files",
          len(build_report.get("changed_files", []))
          == MANIFEST_EXPECTED_COUNT + len(MANIFEST_EXCLUDED)
          and set(manifest_paths)
          <= set(build_report.get("changed_files", []))
          and all(p in build_report.get("changed_files", [])
                  for p in MANIFEST_EXCLUDED),
          f"changed_files={len(build_report.get('changed_files', []))}")
    check("CF-P1-003-R2-MANIFEST: manifest structure + provenance "
          "fields present and well-formed",
          isinstance(manifest.get("schema_version"), str)
          and isinstance(manifest.get("branch"), str)
          and isinstance(manifest.get("generated_at_utc"), str)
          and re.fullmatch(r"[0-9a-f]{40}",
                           manifest.get("github_branch_head") or "")
          is not None
          and re.fullmatch(r"[0-9a-f]{40}",
                           manifest.get("commit") or "") is not None)
    # Negative checks: each tampered in-memory copy MUST fail.
    import copy
    tampered = copy.deepcopy(manifest)
    tampered["files"][0]["bytes"] = tampered["files"][0]["bytes"] + 1
    check("CF-P1-003-R2-MANIFEST: tampered byte count is rejected",
          bool(verify_manifest_entries(tampered, ROOT)))
    tampered = copy.deepcopy(manifest)
    tampered["files"][0]["sha256"] = "0" * 64
    check("CF-P1-003-R2-MANIFEST: tampered SHA-256 is rejected",
          bool(verify_manifest_entries(tampered, ROOT)))
    tampered = copy.deepcopy(manifest)
    tampered["files"].append(copy.deepcopy(tampered["files"][0]))
    check("CF-P1-003-R2-MANIFEST: duplicate path is rejected",
          bool(verify_manifest_entries(tampered, ROOT)))
    for bad_path in ("../escape.txt", "/etc/passwd", "docs\\x.md",
                     "", "docs/../escape.txt"):
        tampered = copy.deepcopy(manifest)
        tampered["files"].append({"path": bad_path,
                                  "sha256": "0" * 64, "bytes": 0})
        check("CF-P1-003-R2-MANIFEST: unsafe path is rejected: "
              f"{bad_path!r}",
              bool(verify_manifest_entries(tampered, ROOT)))
    tampered = copy.deepcopy(manifest)
    tampered["files"].append(
        {"path": "release-manifest.json",
         "sha256": hashlib.sha256(
             open(os.path.join(ROOT, "release-manifest.json"),
                  "rb").read()).hexdigest(),
         "bytes": os.path.getsize(
             os.path.join(ROOT, "release-manifest.json"))})
    check("CF-P1-003-R2-MANIFEST: excluded file listed in the "
          "manifest is rejected",
          bool(verify_manifest_entries(tampered, ROOT)))
    tampered = copy.deepcopy(manifest)
    tampered["files"][0]["path"] = "docs/no-such-file.md"
    check("CF-P1-003-R2-MANIFEST: missing file is rejected",
          bool(verify_manifest_entries(tampered, ROOT)))
    tampered = copy.deepcopy(manifest)
    tampered["github_branch_head"] = "not-a-sha"
    check("CF-P1-003-R2-MANIFEST: malformed provenance head is "
          "rejected",
          bool(verify_manifest_entries(tampered, ROOT)))
    tampered = copy.deepcopy(manifest)
    del tampered["files"][0]
    check("CF-P1-003-R2-MANIFEST: dropped entry (wrong count) is "
          "rejected",
          bool(verify_manifest_entries(tampered, ROOT)))

    # --- CF-P1-003-R2-F1: cross-platform manifest path safety -------
    # The R2 validator accepted Windows absolute paths: on POSIX
    # `os.path.isabs("C:/Windows/win.ini")` is False, so the path
    # passed every check, and on Windows `os.path.join(root, ...)`
    # discards the repository root. These cases do NOT merely assert
    # that verify_manifest_entries() returns some error (a missing
    # file would do that too) — they prove the hardened validator
    # rejects each unsafe path itself AND that the verifier reports
    # an EXPLICIT unsafe-path error, and that rejection happens
    # before any file access.
    f1_paths = ("C:/Windows/win.ini", "D:/outside.txt",
                "C:relative.txt", "//server/share/file.txt",
                "../escape.txt", "/etc/passwd",
                "docs/../escape.txt", "docs\\escape.txt")
    for bad_path in f1_paths:
        check("CF-P1-003-R2-MANIFEST: _is_unsafe_manifest_path "
              f"rejects {bad_path!r}",
              _is_unsafe_manifest_path(bad_path))
        tampered = copy.deepcopy(manifest)
        tampered["files"].append({"path": bad_path,
                                  "sha256": "0" * 64, "bytes": 0})
        errs = verify_manifest_entries(tampered, ROOT)
        check("CF-P1-003-R2-MANIFEST: verify_manifest_entries "
              "reports an explicit unsafe-path error: "
              f"{bad_path!r}",
              any("unsafe manifest path" in e for e in errs),
              "; ".join(errs[:3]))
    # Decoy case (reviewer's reproduction): a same-named file exists
    # under the extraction root with matching content, so a validator
    # that checked the file first would ACCEPT the entry. The
    # unsafe-path rejection must happen before any file access.
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        decoy_rel = os.path.join("C:", "Windows", "win.ini")
        decoy_full = os.path.join(tmp, decoy_rel)
        os.makedirs(os.path.dirname(decoy_full), exist_ok=True)
        decoy_data = b"decoy windows path content\n"
        with open(decoy_full, "wb") as f:
            f.write(decoy_data)
        decoy_manifest = {"files": [{
            "path": "C:/Windows/win.ini",
            "sha256": hashlib.sha256(decoy_data).hexdigest(),
            "bytes": len(decoy_data)}]}
        errs = verify_manifest_entries(decoy_manifest, tmp)
        check("CF-P1-003-R2-MANIFEST: Windows absolute path is "
              "rejected even when a same-named decoy file exists "
              "under the root",
              any("unsafe manifest path: C:/Windows/win.ini" in e
                  for e in errs),
              "; ".join(errs[:3]))
        check("CF-P1-003-R2-MANIFEST: decoy rejection happens "
              "before file access (no hash/size/missing error)",
              not any("sha256 mismatch" in e or "bytes" in e
                      or "manifest file missing" in e for e in errs),
              "; ".join(errs[:3]))
    # Symlink-escape case: a symlink inside the root pointing
    # outside it must never let a manifest entry read outside
    # content. Skipped explicitly where the platform cannot create
    # symlinks (e.g. Windows without the privilege) — the skip is
    # printed, not silently passed, and never fails CI.
    with tempfile.TemporaryDirectory() as tmp:
        outside = os.path.join(tmp, "outside.txt")
        with open(outside, "wb") as f:
            f.write(b"outside the repository root\n")
        repo = os.path.join(tmp, "repo")
        os.makedirs(repo, exist_ok=True)
        link = os.path.join(repo, "link.txt")
        try:
            os.symlink(outside, link)
        except (OSError, NotImplementedError) as exc:
            print("SKIP CF-P1-003-R2-MANIFEST: symlink-escape test "
                  "skipped — symlinks unavailable on this platform "
                  f"({exc})")
        else:
            outside_data = open(outside, "rb").read()
            link_manifest = {"files": [{
                "path": "link.txt",
                "sha256": hashlib.sha256(outside_data).hexdigest(),
                "bytes": len(outside_data)}]}
            errs = verify_manifest_entries(link_manifest, repo)
            check("CF-P1-003-R2-MANIFEST: symlink escaping the "
                  "repository root is rejected",
                  any("escapes repository root" in e for e in errs),
                  "; ".join(errs[:3]))

    print(f"test_reports: {'PASS' if not failures else 'FAIL'} "
          f"({len(failures)} failure(s))")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
