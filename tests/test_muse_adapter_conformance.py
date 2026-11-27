#!/usr/bin/env python3
"""Muse formal conformance test (CF-P0-ADAPTER-001).

Runs the outstanding formal conformance test for the Muse
knowledge-pack route, in this environment (this account uses
it daily). The nine checks, in the work order's words:

1. Access the knowledge pack (the repo itself, cloned into the
   workspace; skills read from there).
2. Identify the required skill for the production task (via the
   P1-002 router).
3. Read the canonical contract (schemas/production-analysis.json).
4. Analyse the short-form fixture (the short production
   analysis).
5. Preserve the source dialogue (verbatim, byte-identical).
6. Produce structured production-analysis output.
7. The output passes real schema + runtime validation.
8. Correctly identify unsupported media-provider operations
   (no verified video/image/sound provider; FFmpeg only for
   technical media operations; creative editing and semantic QC
   have no verified provider).
9. Does NOT claim native Meta custom-skill installation support
   (native install stays UNSUPPORTED in the matrix and the
   adapters registry).

This test records the FACTS. It does not assert the recorded
formal_conformance_status — that record is updated by the
generator step after this test passes, and is verified by
validate-repo.py and generate-registries.py --check. No claim
is made here about ChatGPT, Claude or Gemini conformance.

Conventions follow tests/test_script_to_performance_runtime.py:
check(name, cond, detail="") prints PASS/FAIL lines, failures
are collected, and the process exits 0 only when every check
passes.
"""

import json
import os
import sys
import tempfile

ROOT = os.path.join(os.path.dirname(__file__), "..")
ROOT_ABS = os.path.abspath(ROOT)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import test_script_to_performance_runtime as T  # noqa: E402
from runtime import local_session  # noqa: E402
from runtime.local_session import (  # noqa: E402
    close_session, is_active_session, load_or_create_profile,
    start_session)
from runtime import task_compiler as tc  # noqa: E402
from runtime.production_orchestrator import (  # noqa: E402
    validate_production_analysis)
from runtime.task_compiler import schema_errors  # noqa: E402

failures = []
_checks = [0]
_sessions = []


def check(name, cond, detail=""):
    _checks[0] += 1
    if cond:
        print(f"PASS {name}")
    else:
        print(f"FAIL {name} {detail}")
        failures.append(name)


def clone(value):
    return json.loads(json.dumps(value))


def fresh_session():
    root = tempfile.mkdtemp(prefix="cf-p1-004-r1-adapter-")
    profile = load_or_create_profile(root)
    session = start_session(profile, profile.workspace_id)
    _sessions.append(session)
    return session


def load_fixture(name):
    with open(os.path.join(
            ROOT, "tests", "fixtures", name), encoding="utf-8") as f:
        return json.load(f)


def load_json(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as handle:
        return json.load(handle)


def load_yaml(path):
    import yaml
    with open(os.path.join(ROOT, path), encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _knowledge_pack_group():
    # 1. The knowledge pack is accessible: the repo's skills are
    # readable from the workspace, and the install script that
    # syncs them exists.
    skills_dir = os.path.join(ROOT, "skills")
    skill_names = sorted(
        name for name in os.listdir(skills_dir)
        if os.path.isdir(os.path.join(skills_dir, name)))
    check("CF-P0-ADAPTER-001: the knowledge pack is accessible — "
          "15 skill directories with SKILL.md files",
          len(skill_names) == 15
          and all(os.path.isfile(os.path.join(
              skills_dir, name, "SKILL.md")) for name in skill_names),
          f"skills={skill_names}")
    with open(os.path.join(
            skills_dir, "command-authority", "SKILL.md"),
            encoding="utf-8") as handle:
        skill_text = handle.read()
    check("CF-P0-ADAPTER-001: the command-authority skill reads "
          "as the canonical command master",
          "command master" in skill_text.lower()
          and len(skill_text) > 1000)
    check("CF-P0-ADAPTER-001: the knowledge-pack install script "
          "exists (bash setup.sh)",
          os.path.isfile(os.path.join(ROOT, "setup.sh")))

    # 2. The required skills for the production task are
    # identified through the P1-002 router.
    session = fresh_session()
    plan = T.fresh_routing_plan(session)
    selected = {entry.get("skill") for entry in
                (plan.get("selected_skills") or [])
                if isinstance(entry, dict)}
    check("CF-P0-ADAPTER-001: the router identifies the required "
          "skills for script-to-production (command-authority, "
          "character-consistency, voice-consistency)",
          {"command-authority", "character-consistency",
           "voice-consistency"} <= selected,
          f"selected={sorted(selected)}")
    check("CF-P0-ADAPTER-001: the routing plan is for "
          "GENERATE_FROM_SCRIPT",
          plan.get("intent_mode") == "GENERATE_FROM_SCRIPT")


def _contract_group():
    # 3. The canonical contract reads: production-analysis v2.5.
    schema = load_json(os.path.join(
        "schemas", "production-analysis.json"))
    schema_text = json.dumps(schema)
    check("CF-P0-ADAPTER-001: the canonical production-analysis "
          "contract reads (records carry schema_version 2.5, "
          "provenance labels present)",
          schema.get("title") == "Production Analysis"
          and schema.get("properties", {}).get(
              "schema_version", {}).get("enum") == ["2.5"]
          and "EXPLICIT_FROM_USER" in schema_text
          and "NEEDS_USER_DECISION" in schema_text)

    # 4 + 6. The short-form fixture is a structured
    # production-analysis output: premise, scenes, character
    # resolutions, shot and sound direction.
    analysis = load_fixture("production-analysis-short.json")
    check("CF-P0-ADAPTER-001: the short-form analysis is "
          "structured production-analysis output",
          isinstance(analysis, dict)
          and isinstance(analysis.get("premise"), str)
          and len(analysis.get("scenes") or []) == 1
          and len(analysis.get("character_resolutions") or []) == 2
          and isinstance(analysis.get("sound_direction"), list)
          and analysis.get("script_contract_id") == "script-test-001")

    # 7. The output passes real schema + runtime validation.
    check("CF-P0-ADAPTER-001: the short-form analysis passes the "
          "real production-analysis schema",
          schema_errors("production-analysis", analysis,
                        "production_analysis") == [])
    check("CF-P0-ADAPTER-001: the short-form analysis passes the "
          "real runtime validator with 0 errors",
          validate_production_analysis(analysis, T.script()) == [],
          f"errors={validate_production_analysis(analysis, T.script())}")

    # 5. Source dialogue is preserved verbatim.
    script = T.script()
    check("CF-P0-ADAPTER-001: the analysis dialogue counts match "
          "the source script (2 lines, no rewrite)",
          analysis["dialogue_preservation"][
              "source_dialogue_line_count"] == len(script["dialogue"])
          and analysis["dialogue_preservation"][
              "mapped_line_count"] == len(script["dialogue"])
          and analysis["dialogue_preservation"].get(
              "rewrite_requested") is False)
    session = fresh_session()
    package = tc.compile_task_package(
        session, {"job_id": "job-short-001",
                  "project_id": "proj-test-001"},
        T.build(session=session), analysis,
        voice_kinds=load_fixture("voice-kinds-test.json"))
    voice = [p for p in package["packets"]
             if p["task_type"] == "voice-generation"]
    check("CF-P0-ADAPTER-001: the compiled voice packets carry "
          "the source dialogue byte-identical",
          len(voice) == 2
          and "I will help. Let us go together." in
          voice[0]["canonical_instruction"]
          and "Hello, Mira! I heard you coming." in
          voice[1]["canonical_instruction"])


def _unsupported_operations_group():
    # 8. Unsupported media-provider operations are correctly
    # identified: video / image / sound generation have no
    # verified provider; FFmpeg matches only technical media
    # operations; creative editing and semantic QC have none.
    session = fresh_session()
    package = tc.compile_task_package(
        session, {"job_id": "job-short-001",
                  "project_id": "proj-test-001"},
        T.build(session=session),
        load_fixture("production-analysis-short.json"),
        voice_kinds=load_fixture("voice-kinds-test.json"))
    by_type = {}
    for packet in package["packets"]:
        by_type.setdefault(packet["task_type"], []).append(packet)
    unmatched = {u["task_id"] for u in package["unmatched_tasks"]}
    check("CF-P0-ADAPTER-001: video, image and sound generation "
          "are correctly identified as unsupported (unmatched "
          "handoffs, no provider claimed)",
          all(p["provider_status"]
              == "unavailable-no-verified-provider"
              and p["task_id"] in unmatched
              for p in by_type.get("video-generation", [])
              + by_type.get("sound-generation", []))
          and by_type.get("video-generation")
          and by_type.get("sound-generation"))
    check("CF-P0-ADAPTER-001: FFmpeg matches only technical "
          "media operations (both media-technical packets)",
          len(by_type.get("media-technical", [])) == 2
          and all(p.get("provider_translation", {}).get("provider_id")
                  == "provider-ffmpeg"
                  for p in by_type["media-technical"]))
    check("CF-P0-ADAPTER-001: creative editing and semantic QC "
          "are correctly identified as unsupported (no verified "
          "provider, unmatched handoffs)",
          len(by_type.get("creative-editing", [])) == 1
          and len(by_type.get("semantic-qc-review", [])) == 1
          and all(p["provider_status"]
                  == "unavailable-no-verified-provider"
                  and p["task_id"] in unmatched
                  for p in by_type["creative-editing"]
                  + by_type["semantic-qc-review"]))
    check("CF-P0-ADAPTER-001: no compiled packet claims "
          "execution",
          all(p["provider_status"] != "executed"
              for p in package["packets"]))
    records = tc.load_provider_registry()
    openmontage = [r for r in records
                   if r["provider_id"]
                   == "provider-openmontage-assembly"]
    # P1-005 (2026-11-27): the demo-render entry was exercised with
    # a real output (animated-reel-20s, ffprobe-validated), so the
    # provider is EXERCISED for that entry only. The intent of this
    # check is unchanged — no verified PRODUCTION assembly provider
    # is claimed: the evidence must still say production pipeline
    # assembly is NOT exercised, and the provider must not match a
    # media-technical task (it evidences only assemble-timeline,
    # not probe-media or transcode-media).
    check("CF-P0-ADAPTER-001: OpenMontage is EXERCISED for the "
          "demo-render entry only — no verified production "
          "assembly provider is claimed",
          len(openmontage) == 1
          and openmontage[0]["conformance"]["status"] == "EXERCISED"
          and "production pipeline assembly is NOT exercised"
          in openmontage[0]["conformance"]["evidence"])
    check("CF-P0-ADAPTER-001: OpenMontage does not match a "
          "media-technical task",
          tc.match_provider_for_task(
              "media-technical", records)[0] == "provider-ffmpeg")


def _no_native_install_group():
    # 9. Native Meta custom-skill installation is NOT claimed:
    # the matrix and the adapters registry both record Muse
    # native install as UNSUPPORTED, and the documented route is
    # the versioned knowledge pack.
    matrix = load_yaml(
        "architecture/AGENT_COMPATIBILITY_MATRIX.yaml")
    muse_entry = next(
        (a for a in matrix.get("agents") or []
         if a.get("name") == "Muse"), None)
    check("CF-P0-ADAPTER-001: the matrix records Muse native "
          "skill install as UNSUPPORTED (no native-install claim)",
          muse_entry is not None
          and muse_entry.get("native_skill_install") == "UNSUPPORTED",
          f"entry={muse_entry}")
    check("CF-P0-ADAPTER-001: the matrix documents the "
          "knowledge-pack path as the Muse route",
          muse_entry is not None
          and isinstance(muse_entry.get("knowledge_pack_path"), str)
          and "Clone the repo" in
          muse_entry.get("knowledge_pack_path", ""))
    adapters = load_json("registry/adapters.json")
    muse_adapter = next(
        (r for r in adapters.get("records") or []
         if r.get("adapter_id") == "adapter-muse"), None)
    check("CF-P0-ADAPTER-001: the adapters registry records Muse "
          "native skill install as UNSUPPORTED",
          muse_adapter is not None
          and muse_adapter.get("native_skill_install")
          == "UNSUPPORTED")
    check("CF-P0-ADAPTER-001: no other host is claimed verified "
          "here (only Muse)",
          all(a.get("verified") is True
              for a in matrix.get("agents") or []
              if a.get("name") == "Muse")
          and not any(a.get("verified")
                      for a in matrix.get("agents") or []
                      if a.get("name") != "Muse"))


def main():
    _knowledge_pack_group()
    _contract_group()
    _unsupported_operations_group()
    _no_native_install_group()
    for session in list(_sessions):
        try:
            if is_active_session(session):
                close_session(session)
        except Exception:  # noqa: BLE001 - best-effort cleanup
            pass
    total = _checks[0]
    if failures:
        print(f"\n{len(failures)} FAILURES:")
        for name in failures:
            print(f"  FAIL {name}")
        print(f"test_muse_adapter_conformance: FAIL ({total} checks)")
        sys.exit(1)
    print(f"test_muse_adapter_conformance: PASS ({total} checks)")


if __name__ == "__main__":
    main()
