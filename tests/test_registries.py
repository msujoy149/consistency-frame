#!/usr/bin/env python3
"""P0 registry tests. Run via tests/run-tests.sh or directly:
  python3 tests/test_registries.py
Exit 0 = PASS, 1 = FAIL. Test IDs: CF-INT-023, CF-P0-ADAPTER-001.
"""
import json
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
failures = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


def load(name):
    with open(os.path.join(ROOT, "registry", name), encoding="utf-8") as f:
        return json.load(f)


def main():
    skills = load("skills.json")
    features = load("features.json")
    workflows = load("workflows.json")
    adapters = load("adapters.json")

    # Counts are derived and self-consistent.
    check("skills count matches records", skills["count"] == len(skills["records"]))
    check("features count matches records", features["count"] == len(features["records"]))
    check("workflows count matches records", workflows["count"] == len(workflows["records"]))
    check("adapters count matches records", adapters["count"] == len(adapters["records"]))

    # Skills registry matches the filesystem.
    fs_skills = sorted(d for d in os.listdir(os.path.join(ROOT, "skills"))
                       if os.path.isdir(os.path.join(ROOT, "skills", d)))
    reg_skills = sorted(r["name"] for r in skills["records"])
    check("registry skills match filesystem (15)", fs_skills == reg_skills == sorted(fs_skills)
          and len(fs_skills) == 15, f"fs={fs_skills} reg={reg_skills}")
    for rec in skills["records"]:
        check(f"skill {rec['skill_id']} path exists",
              os.path.exists(os.path.join(ROOT, rec["path"])))
        check(f"skill {rec['skill_id']} maturity is DOCUMENTED",
              rec["maturity"] == "DOCUMENTED")

    # No duplicate IDs anywhere.
    seen = {}
    for fname, data, field in (("skills.json", skills, "skill_id"),
                               ("features.json", features, "feature_id"),
                               ("workflows.json", workflows, "workflow_id"),
                               ("adapters.json", adapters, "adapter_id")):
        for rec in data["records"]:
            rid = rec[field]
            check(f"id {rid} is unique", rid not in seen,
                  f"duplicate of {seen.get(rid)}")
            seen[rid] = fname

    # Every feature has a real owner skill + evidence path.
    skill_ids = {r["skill_id"] for r in skills["records"]}
    for feat in features["records"]:
        if feat["owner_skill"] not in skill_ids:
            check(f"feature {feat['feature_id']} owner exists", False)
            break
    else:
        check("every feature owner skill exists", True)
    check("every feature evidence path exists",
          all(os.path.exists(os.path.join(ROOT, f["owner_path"]))
              for f in features["records"]))

    # Legacy counts are labelled historical, not presented as derived.
    legacy = features.get("legacy_counts", {})
    check("legacy 109/120 claim is labelled historical, not machine-derived",
          legacy.get("status") == "historical-claim-not-machine-derived"
          and legacy.get("distinct_systems_claimed") == 109
          and legacy.get("numbered_entries_claimed") == 120)

    # Workflows cover all 13 modes.
    modes = {r["mode"] for r in workflows["records"]}
    expected = {"UPLOAD_ONLY", "TEMPORARY_ASSET_USE", "PROJECT_CONSISTENCY",
                "REGISTER_CHARACTER", "REGISTER_VOICE_PROFILE", "REGISTER_SOUND_ASSET",
                "GENERATE_FROM_SCRIPT", "EDIT_EXISTING_MEDIA", "REFERENCE_REVIEW",
                "REFERENCE_LEARN_AND_UPDATE", "VIDEO_QC", "REMAKE_OR_TRANSFORM",
                "REPORT_UPDATE_ONLY"}
    check("workflows cover all 13 intent modes", modes == expected,
          f"missing={expected - modes} extra={modes - expected}")

    # CF-P0-ADAPTER-001: untested adapters are never marked supported.
    # A VERIFIED adapter records status "verified" — never
    # "supported", which is a stronger product claim than a passed
    # conformance test (see the adapters registry note).
    for ad in adapters["records"]:
        if ad["conformance"]["status"] in ("NOT_TESTED", "NOT RUN"):
            check(f"CF-P0-ADAPTER-001: {ad['adapter_id']} not marked supported",
                  ad["status"] not in ("supported", "implemented"))
        elif ad["conformance"]["status"] == "VERIFIED":
            check(f"CF-P0-ADAPTER-001: {ad['adapter_id']} verified records status verified",
                  ad["status"] == "verified")
        else:
            check(f"CF-P0-ADAPTER-001: {ad['adapter_id']} has a known conformance status",
                  False,
                  f"status={ad['conformance']['status']!r}")
    muse = [a for a in adapters["records"] if a["adapter_id"] == "adapter-muse"][0]
    check("Muse native skill install is UNSUPPORTED, not claimed",
          muse["native_skill_install"] == "UNSUPPORTED")

    # Registry files are deterministic (sorted keys) — generator check.
    for fname in ("skills.json", "features.json", "workflows.json", "adapters.json"):
        raw = open(os.path.join(ROOT, "registry", fname), encoding="utf-8").read()
        data = json.loads(raw)
        check(f"{fname} is canonically formatted (sorted keys)",
              raw == json.dumps(data, indent=2, sort_keys=True) + "\n")

    print(f"test_registries: {'PASS' if not failures else 'FAIL'} "
          f"({len(failures)} failure(s))")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
