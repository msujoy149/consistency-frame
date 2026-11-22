#!/usr/bin/env python3
"""P0-002 §7 report/provenance tests. Run via tests/run-tests.sh or
directly: python3 tests/test_reports.py
Exit 0 = PASS, 1 = FAIL. Test IDs: CF-P0-REPORT-001/002/003/004.

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
# Latest verified remote CI (P0-005): push run #37 + PR run #38 on the
# P0-004 final PR head 8879123, both SUCCESS, 2/2 checks. The parent
# verified both runs live on 2026-11-22. The push run URL is the one
# recorded in build-report.json's ci object; the PR run URL is cited
# in BUILD_REPORT_P0.md and the living report alongside it.
CI_RUN_URL = ("https://github.com/msujoy149/consistency-frame/actions/"
              "runs/45055643056")
CI_PR_RUN_URL = ("https://github.com/msujoy149/consistency-frame/actions/"
                 "runs/45055649820")
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
    # 8879123, push run #37). It must NOT be forced to equal the
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

    print(f"test_reports: {'PASS' if not failures else 'FAIL'} "
          f"({len(failures)} failure(s))")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
