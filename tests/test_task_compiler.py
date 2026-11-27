#!/usr/bin/env python3
"""Task compiler tests (CF-WO-P1-004).

Covers: task-packet and task-package schema validation;
provider-record validation against the real registry;
evidence-based provider matching (including the commercial
voice rule and the clone-voice requirement); end-to-end
compile_task_package against a real S2P bundle (packet counts
by type, verbatim dialogue, provider matching, determinism,
input immutability, stills-first); task-local proposals;
voice consent; commercial jobs; regeneration packets; and
registry loading.

Conventions follow tests/test_script_to_performance_runtime.py:
check(name, cond, detail="") prints PASS/FAIL lines, failures
are collected, and the process exits 0 only when every check
passes. No test here weakens any P0 or P1 check, and no test
invents a provider capability (video/image/sound/reference
work has no verified provider and must compile as a handoff).
"""

import copy
import json
import os
import sys
import tempfile
from collections import Counter

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
    root = tempfile.mkdtemp(prefix="cf-p1-004-test-")
    profile = load_or_create_profile(root)
    session = start_session(profile, profile.workspace_id)
    _sessions.append(session)
    return session


def load_fixture(name):
    with open(os.path.join(
            ROOT, "tests", "fixtures", name), encoding="utf-8") as f:
        return json.load(f)


def short_analysis():
    return load_fixture("production-analysis-short.json")


def voice_kinds():
    return load_fixture("voice-kinds-test.json")


def expect_error(label, fn):
    """fn must raise TaskCompilerError; anything else (including
    success) fails the check."""
    try:
        fn()
    except tc.TaskCompilerError as exc:
        check(label, True)
        return exc.errors
    except Exception as exc:  # noqa: BLE001 - the test asserts no raise
        check(label, False, f"raised {type(exc).__name__}: {exc}")
        return []
    check(label, False, "operation succeeded instead of refusing")
    return []


def job(job_id="job-short-001", **flags):
    value = {"job_id": job_id, "project_id": "proj-test-001"}
    value.update(flags)
    return value


def bundle(session, draft=None):
    return T.build(session=session, drf=draft) if draft is not None \
        else T.build(session=session)


def compile_short(session, job_value=None, analysis=None, **kwargs):
    return tc.compile_task_package(
        session,
        job_value if job_value is not None else job(),
        bundle(session),
        analysis if analysis is not None else short_analysis(),
        voice_kinds=voice_kinds(), **kwargs)


def packet_counts(package):
    return Counter(p["task_type"] for p in package["packets"])


def rehash_packet(packet):
    probe = clone(packet)
    probe["packet_hash"] = tc.task_packet_hash(probe)
    return probe


def rehash_package(package):
    probe = clone(package)
    probe["package_hash"] = tc.sha256_hex(
        tc.canonical_json(
            {k: v for k, v in probe.items() if k != "package_hash"}))
    return probe


# ---------------------------------------------------------------------------
# CF-P1-004-COMPILER: packet and package schema validation
# ---------------------------------------------------------------------------

def _packet_schema_group():
    session = fresh_session()
    package = compile_short(session)
    check("CF-P1-004-COMPILER: a compiled package validates",
          tc.validate_task_package(package) == [],
          f"errors={tc.validate_task_package(package)}")
    check("CF-P1-004-COMPILER: the compiled package has the "
          "expected id and hash",
          package["package_id"] == "pkg-job-short-001"
          and package["job_id"] == "job-short-001"
          and package["project_id"] == "proj-test-001"
          and len(package["package_hash"]) == 64)
    packet = package["packets"][0]
    check("CF-P1-004-COMPILER: a valid packet passes validation",
          tc.validate_task_packet(packet) == [])
    check("CF-P1-004-COMPILER: every compiled packet passes "
          "validation",
          all(tc.validate_task_packet(p) == []
              for p in package["packets"]))

    bad = rehash_packet(clone(packet))
    bad["schema_version"] = "2.4"
    bad = rehash_packet(bad)
    check("CF-P1-004-COMPILER: bad schema_version fails (even "
          "with a recomputed hash)",
          tc.validate_task_packet(bad) != [])
    bad = clone(packet)
    bad["packet_hash"] = "0" * 64
    check("CF-P1-004-COMPILER: tampered packet_hash is detected",
          tc.validate_task_packet(bad) != [])
    bad = clone(packet)
    bad["canonical_instruction"] = "Do something else entirely."
    check("CF-P1-004-COMPILER: tampered packet content is detected "
          "(hash mismatch)",
          tc.validate_task_packet(bad) != [])
    bad = clone(packet)
    bad["task_type"] = "teleportation"
    bad = rehash_packet(bad)
    check("CF-P1-004-COMPILER: unknown task_type fails",
          tc.validate_task_packet(bad) != [])
    video = [p for p in package["packets"]
             if p["task_type"] == "video-generation"][0]
    check("CF-P1-004-COMPILER: setup packet is an unavailable "
          "handoff",
          video["provider_status"]
          == "unavailable-no-verified-provider"
          and "provider_translation" not in video)
    bad = rehash_packet(clone(video))
    bad["provider_translation"] = {
        "provider_id": "provider-veo-video",
        "translated_instruction": "Generate the video."}
    check("CF-P1-004-COMPILER: provider_translation present with "
          "unavailable status is refused",
          tc.validate_task_packet(bad) != [])
    bad = clone(package)
    bad["packets"].append(clone(bad["packets"][0]))
    bad = rehash_package(bad)
    check("CF-P1-004-COMPILER: duplicate task_id in a package is "
          "refused",
          tc.validate_task_package(bad) != [])
    bad = clone(package)
    bad["package_hash"] = "0" * 64
    check("CF-P1-004-COMPILER: package hash tamper is detected",
          tc.validate_task_package(bad) != [])
    bad = clone(package)
    bad["packets"][0]["packet_hash"] = "0" * 64
    bad = rehash_package(bad)
    check("CF-P1-004-COMPILER: a tampered packet inside a package "
          "is refused",
          tc.validate_task_package(bad) != [])
    check("CF-P1-004-COMPILER: a non-object package is refused",
          tc.validate_task_package(["not", "a", "package"]) != [])
    check("CF-P1-004-COMPILER: a non-object packet is refused",
          tc.validate_task_packet(None) != [])


# ---------------------------------------------------------------------------
# CF-P1-004-COMPILER: provider records and matching
# ---------------------------------------------------------------------------

def _provider_records_group():
    records = tc.load_provider_registry()
    check("CF-P1-004-COMPILER: the default registry loads 13 "
          "records",
          len(records) == 13, f"got {len(records)}")
    check("CF-P1-004-COMPILER: every registry record validates",
          all(tc.validate_provider_record(r) == [] for r in records),
          "a registry record failed validation")
    by_id = {r["provider_id"]: r for r in records}
    check("CF-P1-004-COMPILER: the registry carries the expected "
          "exercised providers",
          by_id["provider-voicestudio-omnivoice"]["conformance"]
          ["status"] == "EXERCISED"
          and by_id["provider-ffmpeg"]["conformance"]["status"]
          == "EXERCISED"
          and by_id["provider-ffmpeg"]["commercial_use_approved"]
          is True
          and by_id["provider-voicestudio-omnivoice"]
          ["commercial_use_approved"] is False)

    base = clone(records[0])
    bad = clone(base)
    bad["conformance"]["status"] = "MAYBE"
    check("CF-P1-004-COMPILER: a bad conformance status is "
          "rejected",
          tc.validate_provider_record(bad) != [])
    bad = clone(base)
    bad["schema_version"] = "2.4"
    check("CF-P1-004-COMPILER: a bad provider schema_version is "
          "rejected",
          tc.validate_provider_record(bad) != [])
    bad = clone(base)
    del bad["evidence"]
    check("CF-P1-004-COMPILER: a record missing evidence is "
          "rejected",
          tc.validate_provider_record(bad) != [])
    bad = clone(base)
    del bad["provider_id"]
    check("CF-P1-004-COMPILER: a record missing provider_id is "
          "rejected",
          tc.validate_provider_record(bad) != [])
    bad = clone(base)
    bad["conformance"]["status"] = "FAILED"
    check("CF-P1-004-COMPILER: a FAILED record is schema-valid "
          "but never matched (see the matching group)",
          tc.validate_provider_record(bad) == [])


def _synthetic_voice_provider(with_clone):
    operations = ["generate-speech"]
    if with_clone:
        operations.append("clone-voice")
    return {
        "schema_version": "2.5",
        "provider_id": "provider-test-voice",
        "provider_type": "voice-tts",
        "operations": operations,
        "commercial_use_approved": True,
        "audio_capability": True,
        "conformance": {"status": "EXERCISED", "evidence": "test",
                        "last_verified": "2026-11-26"},
        "evidence": "synthetic test record",
    }


def _matching_group():
    records = tc.load_provider_registry()
    provider, reason = tc.match_provider_for_task(
        "voice-generation", records)
    check("CF-P1-004-COMPILER: voice (non-commercial) matches "
          "provider-voicestudio-omnivoice",
          provider == "provider-voicestudio-omnivoice",
          f"got {provider!r} ({reason})")
    provider, reason = tc.match_provider_for_task(
        "voice-generation", records, commercial_use=True)
    check("CF-P1-004-COMPILER: voice (commercial) matches nothing "
          "(OmniVoice is CC-BY-NC) and the reason says commercial",
          provider is None and "commercial" in reason,
          f"got {provider!r} ({reason})")
    provider, reason = tc.match_provider_for_task(
        "video-generation", records)
    check("CF-P1-004-COMPILER: video matches nothing (no verified "
          "video provider)",
          provider is None, f"got {provider!r} ({reason})")
    provider, reason = tc.match_provider_for_task(
        "image-generation", records)
    check("CF-P1-004-COMPILER: image matches nothing (no verified "
          "image provider)",
          provider is None, f"got {provider!r} ({reason})")
    provider, reason = tc.match_provider_for_task(
        "sound-generation", records)
    check("CF-P1-004-COMPILER: sound matches nothing (no verified "
          "sound provider)",
          provider is None, f"got {provider!r} ({reason})")
    # B4: the old single editing-finishing / qc-review tasks
    # bundled technical operations with creative work and matched
    # FFmpeg on one technical operation alone. They now require
    # the creative / semantic operations, which no provider
    # evidences — so they match nothing, and only the split
    # media-technical task matches FFmpeg.
    provider, reason = tc.match_provider_for_task(
        "editing-finishing", records)
    check("CF-P1-004-R1-B4: editing-finishing matches nothing — "
          "it requires creative-picture-editing, which FFmpeg "
          "does not evidence",
          provider is None, f"got {provider!r} ({reason})")
    provider, reason = tc.match_provider_for_task(
        "qc-review", records)
    check("CF-P1-004-R1-B4: qc-review matches nothing — it "
          "requires semantic-qc-review, which FFmpeg does not "
          "evidence",
          provider is None, f"got {provider!r} ({reason})")
    provider, reason = tc.match_provider_for_task(
        "media-technical", records)
    check("CF-P1-004-R1-B4: media-technical matches "
          "provider-ffmpeg (probe / assemble / transcode are "
          "evidenced technical operations)",
          provider == "provider-ffmpeg",
          f"got {provider!r} ({reason})")
    provider, reason = tc.match_provider_for_task(
        "creative-editing", records)
    check("CF-P1-004-R1-B4: creative-editing matches nothing — "
          "no provider evidences creative picture editing, "
          "creative colour review or narrative pacing review",
          provider is None, f"got {provider!r} ({reason})")
    provider, reason = tc.match_provider_for_task(
        "semantic-qc-review", records)
    check("CF-P1-004-R1-B4: semantic-qc-review matches nothing — "
          "no provider evidences semantic QC, character-continuity "
          "assessment or physical-realism assessment",
          provider is None, f"got {provider!r} ({reason})")
    provider, reason = tc.match_provider_for_task(
        "teleportation", records)
    check("CF-P1-004-COMPILER: unknown task type matches nothing",
          provider is None, f"got {provider!r} ({reason})")
    provider, reason = tc.match_provider_for_task(
        "reference-sheet", records)
    check("CF-P1-004-COMPILER: reference-sheet matches nothing "
          "(no verified image provider)",
          provider is None, f"got {provider!r} ({reason})")

    # Clone-voice: a provider without the operation never matches
    # a clone task, even when it matches the plain voice task.
    no_clone = _synthetic_voice_provider(with_clone=False)
    provider, reason = tc.match_provider_for_task(
        "voice-generation", [no_clone], needs_clone=True)
    check("CF-P1-004-COMPILER: needs_clone requires clone-voice — "
          "a provider without it does not match",
          provider is None, f"got {provider!r} ({reason})")
    provider, reason = tc.match_provider_for_task(
        "voice-generation", [no_clone], needs_clone=False)
    check("CF-P1-004-COMPILER: the same provider matches a "
          "non-clone voice task",
          provider == "provider-test-voice",
          f"got {provider!r} ({reason})")
    with_clone = _synthetic_voice_provider(with_clone=True)
    provider, reason = tc.match_provider_for_task(
        "voice-generation", [with_clone], needs_clone=True)
    check("CF-P1-004-COMPILER: a provider with clone-voice "
          "matches a clone task",
          provider == "provider-test-voice",
          f"got {provider!r} ({reason})")

    # NOT_TESTED never matches, even with the right operations.
    untested = clone(with_clone)
    untested["provider_id"] = "provider-test-untested"
    untested["conformance"]["status"] = "NOT_TESTED"
    provider, reason = tc.match_provider_for_task(
        "voice-generation", [untested], needs_clone=True)
    check("CF-P1-004-COMPILER: a NOT_TESTED provider never matches "
          "even with the right operations",
          provider is None, f"got {provider!r} ({reason})")
    failed = clone(with_clone)
    failed["provider_id"] = "provider-test-failed"
    failed["conformance"]["status"] = "FAILED"
    provider, reason = tc.match_provider_for_task(
        "voice-generation", [failed])
    check("CF-P1-004-COMPILER: a FAILED provider never matches",
          provider is None, f"got {provider!r} ({reason})")
    # VERIFIED outranks EXERCISED, deterministically.
    verified = clone(with_clone)
    verified["provider_id"] = "provider-test-verified"
    verified["conformance"]["status"] = "VERIFIED"
    provider, reason = tc.match_provider_for_task(
        "voice-generation", [with_clone, verified])
    check("CF-P1-004-COMPILER: VERIFIED outranks EXERCISED",
          provider == "provider-test-verified",
          f"got {provider!r} ({reason})")


# ---------------------------------------------------------------------------
# CF-P1-004-COMPILER: end-to-end compile_task_package
# ---------------------------------------------------------------------------

def _compile_e2e_group():
    session = fresh_session()
    b = bundle(session)
    package = tc.compile_task_package(
        session, job(), b, short_analysis(),
        voice_kinds=voice_kinds())
    counts = packet_counts(package)
    check("CF-P1-004-R1-B4: end-to-end packet counts by type "
          "are 1 environment-reference, 2 video, 2 voice, 3 sound, "
          "2 media-technical, 1 creative-editing, 1 "
          "semantic-qc-review (12 packets)",
          len(package["packets"]) == 12
          and counts == {"environment-reference": 1,
                         "video-generation": 2,
                         "voice-generation": 2,
                         "sound-generation": 3,
                         "media-technical": 2,
                         "creative-editing": 1,
                         "semantic-qc-review": 1},
          f"counts={dict(counts)}")
    check("CF-P1-004-COMPILER: the intentional-silence cue is "
          "skipped (3 sound packets, not 4)",
          counts["sound-generation"] == 3)
    check("CF-P1-004-COMPILER: the compiled package validates",
          tc.validate_task_package(package) == [])
    voice = [p for p in package["packets"]
             if p["task_type"] == "voice-generation"]
    check("CF-P1-004-COMPILER: voice packet instructions contain "
          "the exact script text, byte-identical",
          "I will help. Let us go together." in
          voice[0]["canonical_instruction"]
          and "Hello, Mira! I heard you coming." in
          voice[1]["canonical_instruction"])
    check("CF-P1-004-COMPILER: voice packets are matched to "
          "provider-voicestudio-omnivoice",
          all(p.get("provider_translation", {}).get("provider_id")
              == "provider-voicestudio-omnivoice" for p in voice)
          and all(p["provider_status"] == "not-executed"
                  for p in voice))
    video = [p for p in package["packets"]
             if p["task_type"] == "video-generation"]
    check("CF-P1-004-COMPILER: video packets are unmatched "
          "handoffs with reasons recorded in unmatched_tasks",
          all(p["provider_status"]
              == "unavailable-no-verified-provider" for p in video)
          and all(p["task_id"] in
                  {u["task_id"] for u in package["unmatched_tasks"]}
                  for p in video)
          and all(u["reason"] for u in package["unmatched_tasks"]))
    check("CF-P1-004-R1-B4: 8 tasks are unmatched (1 env, 2 "
          "video, 3 sound, 1 creative-editing, 1 "
          "semantic-qc-review)",
          len(package["unmatched_tasks"]) == 8,
          f"got {len(package['unmatched_tasks'])}")
    media_tech = [p for p in package["packets"]
                  if p["task_type"] == "media-technical"]
    creative = [p for p in package["packets"]
                if p["task_type"] == "creative-editing"]
    semantic = [p for p in package["packets"]
                if p["task_type"] == "semantic-qc-review"]
    check("CF-P1-004-R1-B4: both media-technical packets are "
          "matched to provider-ffmpeg",
          len(media_tech) == 2
          and all(p.get("provider_translation", {}).get("provider_id")
                  == "provider-ffmpeg" for p in media_tech)
          and all(p["provider_status"] == "not-executed"
                  for p in media_tech))
    check("CF-P1-004-R1-B4: the creative-editing packet is an "
          "unmatched handoff — no verified creative editor",
          len(creative) == 1
          and creative[0]["provider_status"]
          == "unavailable-no-verified-provider"
          and creative[0]["task_id"] in
          {u["task_id"] for u in package["unmatched_tasks"]})
    check("CF-P1-004-R1-B4: the semantic-qc-review packet is an "
          "unmatched handoff — no verified semantic reviewer",
          len(semantic) == 1
          and semantic[0]["provider_status"]
          == "unavailable-no-verified-provider"
          and semantic[0]["task_id"] in
          {u["task_id"] for u in package["unmatched_tasks"]})
    check("CF-P1-004-R1-B4: no editing-finishing or qc-review "
          "packet is compiled any more",
          not [p for p in package["packets"]
               if p["task_type"]
               in ("editing-finishing", "qc-review")])

    # Determinism and input immutability.
    job_in, bundle_in, analysis_in = job(), bundle(session), \
        short_analysis()
    snapshots = {"job": clone(job_in), "bundle": clone(bundle_in),
                 "analysis": clone(analysis_in)}
    first = tc.compile_task_package(
        session, job_in, bundle_in, analysis_in,
        voice_kinds=voice_kinds())
    second = tc.compile_task_package(
        session, job_in, bundle_in, analysis_in,
        voice_kinds=voice_kinds())
    check("CF-P1-004-COMPILER: compiling twice gives an identical "
          "package_hash",
          first["package_hash"] == second["package_hash"]
          and first == second,
          f"first={first['package_hash']} "
          f"second={second['package_hash']}")
    check("CF-P1-004-COMPILER: compile_task_package never mutates "
          "its inputs",
          job_in == snapshots["job"]
          and bundle_in == snapshots["bundle"]
          and analysis_in == snapshots["analysis"])

    # A speaking line with no voice profile id is an error.
    no_voice_draft = T.draft()
    del no_voice_draft["character_voice_binding"]["voice_profile_id"]
    del no_voice_draft["character_voice_bindings"][0] \
        ["voice_profile_id"]
    expect_error(
        "CF-P1-004-COMPILER: a speaking line with no voice profile "
        "id is an error",
        lambda: tc.compile_task_package(
            session, job(), bundle(session, no_voice_draft),
            short_analysis(), voice_kinds=voice_kinds()))
    expect_error(
        "CF-P1-004-COMPILER: non-boolean voice_consent is an error",
        lambda: tc.compile_task_package(
            session, job(), bundle(session), short_analysis(),
            voice_kinds=voice_kinds(), voice_consent="true"))

    # stills_first adds image packets and video depends on them.
    stills = tc.compile_task_package(
        session, job(stills_first=True), bundle(session),
        short_analysis(), voice_kinds=voice_kinds())
    stills_counts = packet_counts(stills)
    check("CF-P1-004-COMPILER: stills_first adds 2 "
          "image-generation packets (14 packets total)",
          len(stills["packets"]) == 14
          and stills_counts["image-generation"] == 2
          and stills_counts["video-generation"] == 2,
          f"counts={dict(stills_counts)}")
    images = {p["shot_id"]: p["task_id"]
              for p in stills["packets"]
              if p["task_type"] == "image-generation"}
    check("CF-P1-004-COMPILER: video packets require their still "
          "as prior-output",
          all({"input_ref": images[p["shot_id"]],
               "kind": "prior-output", "required": True}
              in p["required_inputs"]
              for p in stills["packets"]
              if p["task_type"] == "video-generation"))
    check("CF-P1-004-COMPILER: image packets are unmatched "
          "handoffs (no verified image provider)",
          all(p["provider_status"]
              == "unavailable-no-verified-provider"
              for p in stills["packets"]
              if p["task_type"] == "image-generation"))
    # Without stills_first, video packets take an approved asset.
    plain_video = [p for p in package["packets"]
                   if p["task_type"] == "video-generation"]
    check("CF-P1-004-COMPILER: without stills_first, video packets "
          "take an approved starting reference instead",
          all(any(i.get("input_ref")
                  == "approved-starting-reference"
                  for i in p["required_inputs"])
              for p in plain_video))


# ---------------------------------------------------------------------------
# CF-P1-004-COMPILER: task-local proposals
# ---------------------------------------------------------------------------

def _proposals_group():
    session = fresh_session()
    missing = load_fixture("production-analysis-missing-character.json")
    proposed = load_fixture(
        "character-design-proposal-fisherman.json")
    approved = load_fixture(
        "character-design-proposal-fisherman-approved.json")
    package = tc.compile_task_package(
        session, job(), bundle(session), missing, proposals=[proposed],
        voice_kinds=voice_kinds())
    counts = packet_counts(package)
    check("CF-P1-004-COMPILER: a proposed character gets a "
          "character-design packet",
          counts["character-design"] == 1)
    check("CF-P1-004-COMPILER: no reference-sheet packet while the "
          "proposal status is proposed",
          counts.get("reference-sheet", 0) == 0)
    design = [p for p in package["packets"]
              if p["task_type"] == "character-design"][0]
    check("CF-P1-004-COMPILER: the character-design packet is a "
          "host handoff (never a provider match)",
          design["provider_status"] == "handed-off"
          and "provider_translation" not in design)
    check("CF-P1-004-COMPILER: the character-design instruction "
          "says the design is for this job only",
          "for this job only" in design["canonical_instruction"]
          or "never be registered permanently" in
          design["canonical_instruction"])

    package = tc.compile_task_package(
        session, job(), bundle(session), missing, proposals=[approved],
        voice_kinds=voice_kinds())
    counts = packet_counts(package)
    check("CF-P1-004-COMPILER: an approved-for-job proposal also "
          "gets a reference-sheet packet",
          counts["character-design"] == 1
          and counts["reference-sheet"] == 1)
    sheet = [p for p in package["packets"]
             if p["task_type"] == "reference-sheet"][0]
    check("CF-P1-004-COMPILER: the reference-sheet instruction "
          "names the approved references",
          "ref-fisherman-front" in sheet["canonical_instruction"]
          and "ref-fisherman-side" in sheet["canonical_instruction"])
    expect_error(
        "CF-P1-004-COMPILER: analysis referencing a proposal with "
        "no record supplied is an error",
        lambda: tc.compile_task_package(
            session, job(), bundle(session), missing,
            voice_kinds=voice_kinds()))
    rejected = clone(approved)
    rejected["status"] = "rejected"
    expect_error(
        "CF-P1-004-COMPILER: a rejected proposal is an error",
        lambda: tc.compile_task_package(
            session, job(), bundle(session), missing,
            proposals=[rejected], voice_kinds=voice_kinds()))


# ---------------------------------------------------------------------------
# CF-P1-004-COMPILER: voice consent and commercial jobs
# ---------------------------------------------------------------------------

def _clone_bundle(session):
    draft = T.draft()
    draft["character_voice_binding"]["voice_profile_id"] = \
        "voice-clone-001"
    draft["character_voice_bindings"][0]["voice_profile_id"] = \
        "voice-clone-001"
    return bundle(session, draft)


def _voice_consent_group():
    session = fresh_session()
    expect_error(
        "CF-P1-004-COMPILER: clone kind without consent is an "
        "error",
        lambda: tc.compile_task_package(
            session, job(), _clone_bundle(session), short_analysis(),
            voice_kinds=voice_kinds()))
    expect_error(
        "CF-P1-004-COMPILER: clone kind with a non-boolean consent "
        "is an error",
        lambda: tc.compile_task_package(
            session, job(), _clone_bundle(session), short_analysis(),
            voice_kinds=voice_kinds(), voice_consent="yes"))
    package = tc.compile_task_package(
        session, job(), _clone_bundle(session), short_analysis(),
        voice_kinds=voice_kinds(), voice_consent=True)
    voice = [p for p in package["packets"]
             if p["task_type"] == "voice-generation"]
    check("CF-P1-004-COMPILER: clone kind with voice_consent=True "
          "compiles",
          len(voice) == 2)
    check("CF-P1-004-COMPILER: clone voice packets require "
          "clone-voice and match provider-voicestudio-omnivoice "
          "(it evidences clone-voice)",
          all("clone-voice" in
              [c["capability"] for c in
               p["provider_capability_requirements"]]
              for p in voice)
          and all(p.get("provider_translation", {}).get("provider_id")
                  == "provider-voicestudio-omnivoice"
                  for p in voice))
    check("CF-P1-004-COMPILER: the voice-kinds fixture declares "
          "the clone kind",
          voice_kinds()["voice-clone-001"] == "clone"
          and voice_kinds()["voice-aria-001"] == "user-recording"
          and voice_kinds()["voice-kiki-001"] == "existing-profile")


def _commercial_group():
    session = fresh_session()
    package = tc.compile_task_package(
        session, job(commercial_use=True), bundle(session),
        short_analysis(), voice_kinds=voice_kinds())
    voice = [p for p in package["packets"]
             if p["task_type"] == "voice-generation"]
    check("CF-P1-004-COMPILER: commercial voice packets are "
          "unavailable handoffs",
          all(p["provider_status"]
              == "unavailable-no-verified-provider" for p in voice))
    reasons = {u["task_id"]: u["reason"]
               for u in package["unmatched_tasks"]}
    check("CF-P1-004-COMPILER: commercial voice unmatched reasons "
          "record the commercial restriction",
          all("commercial" in reasons[p["task_id"]] for p in voice))
    media_tech = [p for p in package["packets"]
                  if p["task_type"] == "media-technical"]
    check("CF-P1-004-R1-B4: other packets are unaffected by the "
          "commercial flag (media-technical still matches ffmpeg, "
          "creative-editing and semantic-qc-review stay unmatched)",
          len(media_tech) == 2
          and all(p.get("provider_translation", {}).get("provider_id")
                  == "provider-ffmpeg" for p in media_tech)
          and all(p["provider_status"]
                  == "unavailable-no-verified-provider"
                  for p in package["packets"]
                  if p["task_type"]
                  in ("creative-editing", "semantic-qc-review")))
    check("CF-P1-004-COMPILER: the commercial package still "
          "validates",
          tc.validate_task_package(package) == [])


# ---------------------------------------------------------------------------
# CF-P1-004-COMPILER: regeneration packets
# ---------------------------------------------------------------------------

def _compiled_job_package(session):
    package = compile_short(session)
    return package, {**job(), "task_package": package}


def _regeneration_group():
    session = fresh_session()
    qc = load_fixture("qc-report-test.json")
    package, job_with_package = _compiled_job_package(session)
    regen = tc.compile_regeneration_packets(
        session, job_with_package, qc)
    check("CF-P1-004-COMPILER: regeneration compiles 1 packet for "
          "the Critical defect on sh-01",
          len(regen["packets"]) == 1
          and regen["packets"][0].get("shot_id") == "sh-01"
          and regen["packets"][0]["task_type"] == "regeneration")
    check("CF-P1-004-COMPILER: the regeneration package id marks "
          "round 01",
          regen["package_id"] == "pkg-job-short-001-regen-01")
    skipped = {entry["defect_id"]: entry["reason"]
               for entry in regen["skipped_defects"]}
    check("CF-P1-004-COMPILER: Minor without authorisation is "
          "skipped with a reason",
          "qc-002" in skipped
          and "authorisation" in skipped["qc-002"])
    check("CF-P1-004-COMPILER: Polish is skipped with a reason",
          "qc-003" in skipped and "Polish" in skipped["qc-003"])
    check("CF-P1-004-COMPILER: the regeneration package validates",
          tc.validate_task_package(regen) == [])
    regen_packet = regen["packets"][0]
    check("CF-P1-004-COMPILER: the regeneration packet re-matches "
          "as the original type — a video defect with no verified "
          "video provider stays unavailable",
          regen_packet["provider_status"]
          == "unavailable-no-verified-provider"
          and regen_packet["task_id"] in
          {u["task_id"] for u in regen["unmatched_tasks"]})
    check("CF-P1-004-COMPILER: the regeneration packet references "
          "the original task as prior-output and names the defect",
          any(i.get("kind") == "prior-output"
              for i in regen_packet["required_inputs"])
          and "qc-001" in regen_packet["canonical_instruction"]
          and "Neighbouring approved shots must not change" in
          regen_packet["canonical_instruction"])
    check("CF-P1-004-COMPILER: the regeneration packet never "
          "claims execution",
          regen_packet["provider_status"] != "executed")

    # A Minor defect WITH repair authorisation does get a packet.
    authorised = clone(qc)
    authorised["defects"] = [{
        "defect_id": "qc-002", "severity": "Minor",
        "shot_id": "sh-02", "repair_authorised": True,
        "description": "A small continuity slip."}]
    regen_minor = tc.compile_regeneration_packets(
        session, job_with_package, authorised)
    check("CF-P1-004-COMPILER: a Minor defect with repair "
          "authorisation gets a packet",
          len(regen_minor["packets"]) == 1
          and regen_minor["packets"][0].get("shot_id") == "sh-02")

    # Second round: a distinct package id.
    round_two_job = {**job_with_package, "correction_round": 1}
    regen2 = tc.compile_regeneration_packets(
        session, round_two_job, qc)
    check("CF-P1-004-COMPILER: a second regeneration round gets a "
          "distinct package id",
          regen2["package_id"] == "pkg-job-short-001-regen-02"
          and regen2["package_id"] != regen["package_id"]
          and regen2["package_hash"] != regen["package_hash"])

    bad_shot = clone(qc)
    bad_shot["defects"] = [{
        "defect_id": "qc-999", "severity": "Critical",
        "shot_id": "sh-99", "description": "No such shot."}]
    expect_error(
        "CF-P1-004-COMPILER: a defect with an unknown shot is "
        "refused",
        lambda: tc.compile_regeneration_packets(
            session, job_with_package, bad_shot))
    bad_severity = clone(qc)
    bad_severity["defects"] = [{
        "defect_id": "qc-998", "severity": "Trivial",
        "shot_id": "sh-01", "description": "No such severity."}]
    expect_error(
        "CF-P1-004-COMPILER: a defect with an unknown severity is "
        "refused",
        lambda: tc.compile_regeneration_packets(
            session, job_with_package, bad_severity))
    expect_error(
        "CF-P1-004-COMPILER: regeneration without a compiled task "
        "package is refused",
        lambda: tc.compile_regeneration_packets(session, job(), qc))
    wrong_job = clone(qc)
    wrong_job["job_id"] = "job-other-001"
    expect_error(
        "CF-P1-004-COMPILER: a QC report for another job is "
        "refused",
        lambda: tc.compile_regeneration_packets(
            session, job_with_package, wrong_job))


# ---------------------------------------------------------------------------
# CF-P1-004-COMPILER: registry loading
# ---------------------------------------------------------------------------

def _registry_group():
    records = tc.load_provider_registry()
    check("CF-P1-004-COMPILER: load_provider_registry() with the "
          "default path returns 13 records",
          len(records) == 13)
    expect_error(
        "CF-P1-004-COMPILER: a missing registry file raises "
        "TaskCompilerError",
        lambda: tc.load_provider_registry(
            "/nonexistent/providers.json"))
    bad_path = os.path.join(tempfile.mkdtemp(prefix="cf-p1-004-test-"),
                            "providers.json")
    with open(bad_path, "w", encoding="utf-8") as f:
        f.write("{not json")
    expect_error(
        "CF-P1-004-COMPILER: a malformed registry file raises "
        "TaskCompilerError",
        lambda: tc.load_provider_registry(bad_path))
    with open(bad_path, "w", encoding="utf-8") as f:
        json.dump({"records": "not-a-list"}, f)
    expect_error(
        "CF-P1-004-COMPILER: a registry without a records array "
        "raises TaskCompilerError",
        lambda: tc.load_provider_registry(bad_path))
    with open(bad_path, "w", encoding="utf-8") as f:
        json.dump({"records": [clone(records[0]),
                               {**clone(records[1]),
                                "schema_version": "2.4"}]}, f)
    expect_error(
        "CF-P1-004-COMPILER: a registry with an invalid record "
        "raises TaskCompilerError",
        lambda: tc.load_provider_registry(bad_path))


# ---------------------------------------------------------------------------
# CF-P1-004-R1-B1-B2-B3: environment / prop / time-aware sound packets
# ---------------------------------------------------------------------------

def _approved_prop(prop_id="prop-boat-001", status="approved"):
    return {"schema_version": "2.3", "id": prop_id,
            "project_id": "proj-test-001", "name": "wooden boat",
            "version": 1, "status": status,
            "description": "A small wooden fishing boat."}


def _env_analysis():
    analysis = short_analysis()
    scene = analysis["scenes"][0]
    scene["weather"] = "clear evening"
    scene["atmosphere"] = "warm evening air"
    scene["background_design"] = "riverbank with moored boats"
    scene["foreground_requirements"] = "reeds in the near foreground"
    scene["midground_requirements"] = "the river midground"
    scene["background_requirements"] = "boats moored along the bank"
    scene["environment_continuity"] = "the river stays on the left"
    scene["asset_references"] = [{
        "asset_id": "asset-river-001", "kind": "reference-image",
        "reference_id": "ref-river-001",
        "provenance": "EXPLICIT_FROM_USER"}]
    return analysis


def _prop_analysis():
    analysis = short_analysis()
    analysis["scenes"][0]["important_props"] = [{
        "prop_id": "prop-boat-001", "name": "wooden boat",
        "provenance": "EXPLICIT_FROM_USER",
        "design_brief": "a small wooden fishing boat",
        "visual_requirements": "weathered wood, red trim",
        "physical_requirements": "wooden, seats two",
        "continuity_restrictions": "the boat stays moored"}]
    return analysis


def _timed_cue_analysis():
    analysis = short_analysis()
    cue = analysis["sound_direction"][0]
    cue["cue_id"] = "cue-sc01-amb-001"
    cue["shot_id"] = "sh-01"
    cue["beat_id"] = "b-01"
    cue["start_anchor"] = "SCENE_START"
    cue["start_offset_seconds"] = 0.5
    cue["duration_seconds"] = 3.0
    cue["distance"] = "near"
    cue["perspective"] = "on-screen"
    cue["intensity"] = 5
    cue["sync_target"] = "the oar stroke"
    cue["mixing_priority"] = "dialogue-first"
    return analysis


def _r1_env_prop_sound_group():
    session = fresh_session()

    # B1: the environment packet carries every validated
    # scene-environment detail plus approved reference ids.
    package = compile_short(session, analysis=_env_analysis())
    env = [p for p in package["packets"]
           if p["task_type"] == "environment-reference"]
    check("CF-P1-004-R1-B1: exactly one environment-reference "
          "packet is compiled",
          len(env) == 1, f"got {len(env)}")
    instruction = env[0]["canonical_instruction"]
    check("CF-P1-004-R1-B1: the environment instruction carries "
          "weather, atmosphere, background design, foreground, "
          "midground, background requirements and continuity",
          all(text in instruction for text in (
              "clear evening", "warm evening air",
              "riverbank with moored boats",
              "reeds in the near foreground", "the river midground",
              "boats moored along the bank",
              "the river stays on the left")))
    check("CF-P1-004-R1-B1: the approved asset id is a "
          "required approved-asset input",
          any(i.get("input_ref") == "asset-river-001"
              and i.get("kind") == "approved-asset"
              and i.get("required") is True
              for i in env[0]["required_inputs"]),
          f"inputs={env[0]['required_inputs']}")
    check("CF-P1-004-R1-B1: the environment instruction lists "
          "the approved reference asset",
          "Approved references: asset-river-001." in instruction)

    # B2: a task-local prop compiles one prop-reference packet
    # with the design brief and requirements; nothing is
    # permanently registered (no provider executes it).
    package = compile_short(session, analysis=_prop_analysis())
    props = [p for p in package["packets"]
             if p["task_type"] == "prop-reference"]
    check("CF-P1-004-R1-B2: a task-local prop compiles exactly "
          "one prop-reference packet",
          len(props) == 1, f"got {len(props)}")
    instruction = props[0]["canonical_instruction"]
    check("CF-P1-004-R1-B2: the prop instruction carries the "
          "design brief, visual and physical requirements and "
          "continuity restrictions",
          all(text in instruction for text in (
              "a small wooden fishing boat",
              "weathered wood, red trim", "wooden, seats two",
              "the boat stays moored")))
    check("CF-P1-004-R1-B2: the task-local prop packet is an "
          "unmatched handoff (no verified image provider)",
          props[0]["provider_status"]
          == "unavailable-no-verified-provider"
          and props[0]["task_id"] in
          {u["task_id"] for u in package["unmatched_tasks"]})
    check("CF-P1-004-R1-B2: the compiled package with a prop "
          "packet validates",
          tc.validate_task_package(package) == [])

    # B2: the same prop in two scenes compiles one packet only.
    two_scenes = _prop_analysis()
    second = {"scene_id": "sc-02",
              "important_props": clone(
                  two_scenes["scenes"][0]["important_props"])}
    two_scenes["scenes"].append(second)
    package = compile_short(session, analysis=two_scenes)
    props = [p for p in package["packets"]
             if p["task_type"] == "prop-reference"]
    check("CF-P1-004-R1-B2: no duplicate task for the same "
          "recurring prop across scenes",
          len(props) == 1, f"got {len(props)}")

    # B2: an approved prop is prepared, never redesigned, as a
    # handed-off packet.
    approved_analysis = _prop_analysis()
    approved_analysis["scenes"][0]["important_props"][0][
        "approved_prop_id"] = "prop-boat-001"
    package = compile_short(
        session, analysis=approved_analysis,
        approved_props=[_approved_prop()])
    props = [p for p in package["packets"]
             if p["task_type"] == "prop-reference"]
    check("CF-P1-004-R1-B2: an approved prop compiles one "
          "prop-reference packet",
          len(props) == 1, f"got {len(props)}")
    check("CF-P1-004-R1-B2: the approved prop packet is handed "
          "off (never matched to a provider) and says the "
          "existing record is prepared, never redesigned",
          props[0]["provider_status"] == "handed-off"
          and "do not redesign it" in
          props[0]["canonical_instruction"]
          and "prop-boat-001" in props[0]["canonical_instruction"])

    # B2: approved-prop failures fail closed.
    expect_error(
        "CF-P1-004-R1-B2: an approved prop with no matching "
        "approved record is refused",
        lambda: compile_short(session, analysis=approved_analysis))
    expect_error(
        "CF-P1-004-R1-B2: an approved record with a non-approved "
        "status is refused",
        lambda: compile_short(
            session, analysis=approved_analysis,
            approved_props=[_approved_prop(status="draft")]))
    bad_record = _approved_prop()
    del bad_record["name"]
    expect_error(
        "CF-P1-004-R1-B2: an approved record that fails the prop "
        "schema is refused",
        lambda: compile_short(
            session, analysis=approved_analysis,
            approved_props=[bad_record]))
    no_brief = _prop_analysis()
    del no_brief["scenes"][0]["important_props"][0]["design_brief"]
    expect_error(
        "CF-P1-004-R1-B2: a task-local prop with no design brief "
        "and no approved id is refused",
        lambda: compile_short(session, analysis=no_brief))

    # B3: a timed sound cue keeps its full structured timing.
    package = compile_short(session, analysis=_timed_cue_analysis())
    sound = [p for p in package["packets"]
             if p["task_type"] == "sound-generation"]
    ambience = [p for p in sound
                if "ambience" in p["canonical_instruction"]]
    check("CF-P1-004-R1-B3: the timed ambience cue compiles one "
          "sound packet",
          len(ambience) == 1, f"got {len(ambience)}")
    packet = ambience[0]
    check("CF-P1-004-R1-B3: the sound packet carries the shot "
          "and beat ids",
          packet.get("shot_id") == "sh-01"
          and packet.get("beat_id") == "b-01")
    timing = packet.get("cue_timing") or {}
    check("CF-P1-004-R1-B3: cue_timing preserves the full "
          "structured timing with timing_status planned",
          timing.get("timing_status") == "planned"
          and timing.get("cue_id") == "cue-sc01-amb-001"
          and timing.get("start_anchor") == "SCENE_START"
          and timing.get("start_offset_seconds") == 0.5
          and timing.get("duration_seconds") == 3.0
          and timing.get("distance") == "near"
          and timing.get("perspective") == "on-screen"
          and timing.get("intensity") == 5
          and timing.get("sync_target") == "the oar stroke"
          and timing.get("mixing_priority") == "dialogue-first",
          f"cue_timing={timing}")
    check("CF-P1-004-R1-B3: the sound instruction names the "
          "anchor and says the timing is planned, never a "
          "rendered clip",
          "SCENE_START" in packet["canonical_instruction"]
          and "planned timing" in packet["canonical_instruction"])
    check("CF-P1-004-R1-B3: intentional silence still generates "
          "no sound packet (3 sound packets)",
          len(sound) == 3)
    check("CF-P1-004-R1-B3: the package with timed cues "
          "validates",
          tc.validate_task_package(package) == [])

    # B3: fallback S2P audio-plan cues get planned timing only.
    package = tc.compile_task_package(
        session, job(), bundle(session), None,
        voice_kinds=voice_kinds())
    sound = [p for p in package["packets"]
             if p["task_type"] == "sound-generation"]
    check("CF-P1-004-R1-B3: fallback audio-plan cues carry "
          "cue_timing with timing_status planned only",
          len(sound) >= 1
          and all(p.get("cue_timing") == {"timing_status": "planned"}
                  for p in sound),
          f"cue_timings={[p.get('cue_timing') for p in sound]}")


def main():
    _packet_schema_group()
    _provider_records_group()
    _matching_group()
    _compile_e2e_group()
    _proposals_group()
    _voice_consent_group()
    _commercial_group()
    _r1_env_prop_sound_group()
    _regeneration_group()
    _registry_group()
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
        print(f"test_task_compiler: FAIL ({total} checks)")
        return 1
    print(f"test_task_compiler: PASS ({total} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
