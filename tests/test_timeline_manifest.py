#!/usr/bin/env python3
"""CF-WO-P0-007 Correction A — audio-visual timeline contract (v2.5).

Tests the additive v2.5 migration of schemas/timeline-manifest.json and
the reference cross-reference validator defined in this file.

PRODUCTION IMPLEMENTATION — validate_timeline_cross_references()
lives in scripts/timeline_policy.py (CF-WO-P0-008, Correction C: moved
out of this test file, where a validator cannot be called by the
production planning and handoff pipeline). This file imports the
production function and keeps only the fixtures and cases; the
structural validation code here is gone, not duplicated. Strict v2.5
production validation (ownership + requester + approval) is the
`strict=True` mode of the same production function.

Registry shape (mini-registries are built inline in this file; no other
worker's fixtures are depended on):
    {
      "shots":          {shot_id: {"shot_id", "scene_id", "character_ids"[...]}},
      "scenes":         {scene_id: {"scene_id"}},
      "dialogue_lines": {dialogue_line_id: {"dialogue_line_id", "character_id",
                                             "voice_profile_id", "audio_asset_id"}},
      "characters":     {character_id: {"id", "status", "temporary": bool}},
      "voice_profiles": {voice_profile_id: {"id", "character_id",
                                             "approval_status"}},
      "audio_assets":   {audio_asset_id: {"id", "approved": bool, "status"}},
    }
A registry section that is ABSENT is skipped (partial registries are
allowed); a section that is PRESENT is authoritative, so an ID it does
not contain is an error. A character resolves when present in
"characters" and not deprecated; a record with "temporary": true is an
approved-temporary character. A voice profile must belong to exactly
one character, and an audio clip must never silently switch to another
character's voice. Music, ambience, SFX and foley need NO Character ID,
Voice Profile ID or Dialogue Line ID; an intentional narration track
needs no character voice binding.

Validator-subset gap: scripts/validate-repo.py supports only the
restricted JSON-Schema subset (type/properties/required/enum/pattern/
minLength/minimum/maximum/exclusiveMinimum/minItems/items/
additionalProperties). It has NO if/then/else, allOf/oneOf/anyOf,
$ref, dependentRequired or uniqueItems, so NO conditional rule lives in
schemas/timeline-manifest.json: format-dependent requirements (e.g.
frame_rate with timebase frames/timecode) stay optional with a
description, and every cross-field / cross-record rule (shot exists,
line exists, voice belongs to the character, sync-group members exist)
is enforced semantically by validate_timeline_cross_references() in scripts/timeline_policy.py
— the same pattern test_schemas.py uses for the dialogue-rewrite,
non-verbal-line and articulation rules.

Run: python3 tests/test_timeline_manifest.py
Exit 0 = PASS, 1 = FAIL. Test IDs: CF-P0-007-A (cases 1-14).
"""
import importlib.util
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
_spec = importlib.util.spec_from_file_location(
    "validate_repo", os.path.join(ROOT, "scripts", "validate-repo.py"))
_validate_repo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_validate_repo)
validate_instance = _validate_repo.validate_instance

# Production implementation (CF-WO-P0-008 C): the validator moved to
# scripts/timeline_policy.py. This name IS the production function —
# there is no second implementation in this file.
import timeline_policy  # noqa: E402
validate_timeline_cross_references = (
    timeline_policy.validate_timeline_cross_references)

failures = []

NON_DIALOGUE_AUDIO_TYPES = ("music", "ambience", "sound-effect", "foley")


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


def load_schema(name):
    with open(os.path.join(ROOT, "schemas", name), encoding="utf-8") as f:
        return json.load(f)


def load_fixture(name):
    with open(os.path.join(ROOT, "tests", "fixtures", name), encoding="utf-8") as f:
        return json.load(f)


def schema_errors(value):
    errs = []
    validate_instance(load_schema("timeline-manifest.json"), value, "$", errs)
    return errs


def full_errors(manifest, registry):
    """Schema errors + cross-reference errors for one manifest."""
    return schema_errors(manifest) + \
        validate_timeline_cross_references(manifest, registry)


# ---------------------------------------------------------------------------
# Inline mini-registries (no other worker's fixtures are depended on)
# ---------------------------------------------------------------------------

def mini_registry():
    """Shot/performance/character/voice/audio records for the 14 cases."""
    return {
        "shots": {
            "shot-a-01": {"shot_id": "shot-a-01", "scene_id": "sc-01",
                          "character_ids": ["char-ana-001"]},
            "shot-a-02": {"shot_id": "shot-a-02", "scene_id": "sc-01",
                          "character_ids": ["char-ana-001", "char-ben-002"]},
            "shot-ab-01": {"shot_id": "shot-ab-01", "scene_id": "sc-02",
                           "character_ids": ["char-ana-001", "char-kiki-003"]},
            "shot-n-01": {"shot_id": "shot-n-01", "scene_id": "sc-03",
                          "character_ids": []},
            "shot-t-01": {"shot_id": "shot-t-01", "scene_id": "sc-01",
                          "character_ids": ["char-temp-004"]},
        },
        "scenes": {
            "sc-01": {"scene_id": "sc-01"},
            "sc-02": {"scene_id": "sc-02"},
            "sc-03": {"scene_id": "sc-03"},
        },
        "dialogue_lines": {
            "l-ana-01": {"dialogue_line_id": "l-ana-01",
                         "character_id": "char-ana-001",
                         "voice_profile_id": "vp-ana-001",
                         "audio_asset_id": "aud-ana-01"},
            "l-ben-01": {"dialogue_line_id": "l-ben-01",
                         "character_id": "char-ben-002",
                         "voice_profile_id": "vp-ben-001",
                         "audio_asset_id": "aud-ben-01"},
            "l-kiki-01": {"dialogue_line_id": "l-kiki-01",
                          "character_id": "char-kiki-003",
                          "voice_profile_id": "vp-kiki-001",
                          "audio_asset_id": "aud-kiki-01"},
        },
        "characters": {
            "char-ana-001": {"id": "char-ana-001", "status": "approved",
                             "subject_kind": "human"},
            "char-ben-002": {"id": "char-ben-002", "status": "approved",
                             "subject_kind": "human"},
            "char-kiki-003": {"id": "char-kiki-003", "status": "approved",
                              "subject_kind": "cgi-animal",
                              "species": "African grey parrot"},
            "char-temp-004": {"id": "char-temp-004", "status": "approved",
                              "temporary": True},
        },
        "voice_profiles": {
            "vp-ana-001": {"id": "vp-ana-001",
                           "character_id": "char-ana-001",
                           "approval_status": "approved"},
            "vp-ben-001": {"id": "vp-ben-001",
                           "character_id": "char-ben-002",
                           "approval_status": "approved"},
            "vp-kiki-001": {"id": "vp-kiki-001",
                            "character_id": "char-kiki-003",
                            "approval_status": "approved"},
        },
        "audio_assets": {
            "aud-ana-01": {"id": "aud-ana-01", "approved": True},
            "aud-ben-01": {"id": "aud-ben-01", "approved": True},
            "aud-kiki-01": {"id": "aud-kiki-01", "approved": True},
            "aud-music-01": {"id": "aud-music-01", "approved": True},
            "aud-amb-01": {"id": "aud-amb-01", "approved": True},
        },
    }


def video_clip(clip_id, shot_id, scene_id, character_ids, **kw):
    clip = {"clip_id": clip_id,
            "media": {"path": f"media/{clip_id}.mp4",
                      "sha256": "a" * 64, "media_type": "video/mp4"},
            "in_seconds": 0, "out_seconds": 4,
            "shot_id": shot_id, "scene_id": scene_id,
            "character_ids": character_ids}
    clip.update(kw)
    return clip


def audio_clip(clip_id, audio_type="dialogue", **kw):
    clip = {"clip_id": clip_id,
            "media": {"path": f"media/{clip_id}.wav",
                      "sha256": "b" * 64, "media_type": "audio/wav"},
            "in_seconds": 0, "out_seconds": 4, "audio_type": audio_type}
    clip.update(kw)
    return clip


def track(track_id, kind, clips, **kw):
    t = {"track_id": track_id, "kind": kind, "clips": clips}
    t.update(kw)
    return t


def manifest(tracks, version="2.5", **kw):
    m = {"schema_version": version, "id": "timeline-test-001",
         "format": "editor_neutral_v1", "tracks": tracks}
    m.update(kw)
    return m


def dialogue_audio(clip_id, line_id, char_id, voice_id, audio_id, shot_ids,
                   **kw):
    """One fully-bound dialogue audio clip."""
    clip = audio_clip(clip_id, "dialogue",
                      dialogue_line_id=line_id, character_id=char_id,
                      voice_profile_id=voice_id, audio_asset_id=audio_id,
                      shot_ids=shot_ids, role="speaker", language="bn",
                      timeline_start_seconds=0, timeline_end_seconds=4,
                      duration_seconds=4)
    clip.update(kw)
    return clip


def sync_group(gid, video_ids, audio_ids, line_ids=(), shot_ids=()):
    return {"sync_group_id": gid, "video_clip_ids": list(video_ids),
            "audio_clip_ids": list(audio_ids),
            "dialogue_line_ids": list(line_ids),
            "shot_ids": list(shot_ids)}


# ---------------------------------------------------------------------------
# The 14 cases (CF-P0-007-A)
# ---------------------------------------------------------------------------

def main():
    reg = mini_registry()

    # (1) Single human speaker, synchronized dialogue + video.
    m = manifest([
        track("v1", "video", [video_clip(
            "clip-v-01", "shot-a-01", "sc-01", ["char-ana-001"],
            timeline_start_seconds=0, timeline_end_seconds=4,
            duration_seconds=4)]),
        track("a1", "audio", [dialogue_audio(
            "clip-a-01", "l-ana-01", "char-ana-001", "vp-ana-001",
            "aud-ana-01", ["shot-a-01"])]),
    ], synchronization_groups=[sync_group(
        "sync-01", ["clip-v-01"], ["clip-a-01"], ["l-ana-01"],
        ["shot-a-01"])])
    check("CF-P0-007-A(1): single human speaker, dialogue + video in sync",
          full_errors(m, reg) == [], "; ".join(full_errors(m, reg)))

    # (2) Two characters with separate voice profiles.
    m = manifest([
        track("v1", "video", [video_clip(
            "clip-v-02", "shot-a-02", "sc-01",
            ["char-ana-001", "char-ben-002"],
            timeline_start_seconds=0, timeline_end_seconds=8,
            duration_seconds=8)]),
        track("a1", "audio", [
            dialogue_audio("clip-a-02a", "l-ana-01", "char-ana-001",
                           "vp-ana-001", "aud-ana-01", ["shot-a-02"]),
            dialogue_audio("clip-a-02b", "l-ben-01", "char-ben-002",
                           "vp-ben-001", "aud-ben-01", ["shot-a-02"],
                           timeline_start_seconds=4, timeline_end_seconds=8),
        ]),
    ], synchronization_groups=[sync_group(
        "sync-02", ["clip-v-02"], ["clip-a-02a", "clip-a-02b"],
        ["l-ana-01", "l-ben-01"], ["shot-a-02"])])
    check("CF-P0-007-A(2): two characters, separate voice profiles",
          full_errors(m, reg) == [], "; ".join(full_errors(m, reg)))

    # (3) Human + CGI bird in one scene.
    m = manifest([
        track("v1", "video", [video_clip(
            "clip-v-03", "shot-ab-01", "sc-02",
            ["char-ana-001", "char-kiki-003"],
            timeline_start_seconds=0, timeline_end_seconds=8,
            duration_seconds=8)]),
        track("a1", "audio", [
            dialogue_audio("clip-a-03a", "l-ana-01", "char-ana-001",
                           "vp-ana-001", "aud-ana-01", ["shot-ab-01"]),
            dialogue_audio("clip-a-03b", "l-kiki-01", "char-kiki-003",
                           "vp-kiki-001", "aud-kiki-01", ["shot-ab-01"],
                           timeline_start_seconds=4, timeline_end_seconds=8),
        ]),
    ])
    check("CF-P0-007-A(3): human + CGI bird in one scene",
          full_errors(m, reg) == [], "; ".join(full_errors(m, reg)))

    # (4) Narrator with no visible character.
    m = manifest([
        track("v1", "video", [video_clip(
            "clip-v-04", "shot-n-01", "sc-03", [],
            timeline_start_seconds=0, timeline_end_seconds=4,
            duration_seconds=4)]),
        track("a1", "audio", [audio_clip(
            "clip-a-04", "narration", language="en", role="narrator",
            timeline_start_seconds=0, timeline_end_seconds=4,
            duration_seconds=4)]),
    ])
    check("CF-P0-007-A(4): narrator with no visible character",
          full_errors(m, reg) == [], "; ".join(full_errors(m, reg)))

    # (5) Music + ambience without character bindings.
    m = manifest([
        track("v1", "video", [video_clip(
            "clip-v-05", "shot-a-01", "sc-01", ["char-ana-001"],
            timeline_start_seconds=0, timeline_end_seconds=4,
            duration_seconds=4)]),
        track("a1", "audio", [
            audio_clip("clip-a-05m", "music", audio_asset_id="aud-music-01",
                       timeline_start_seconds=0, timeline_end_seconds=4,
                       duration_seconds=4),
            audio_clip("clip-a-05b", "ambience",
                       audio_asset_id="aud-amb-01",
                       timeline_start_seconds=0, timeline_end_seconds=4,
                       duration_seconds=4),
        ]),
    ])
    check("CF-P0-007-A(5): music + ambience without character bindings",
          full_errors(m, reg) == [], "; ".join(full_errors(m, reg)))

    # (6) One dialogue line spread across several shots.
    m = manifest([
        track("v1", "video", [
            video_clip("clip-v-06a", "shot-a-01", "sc-01", ["char-ana-001"],
                       timeline_start_seconds=0, timeline_end_seconds=4,
                       duration_seconds=4),
            video_clip("clip-v-06b", "shot-a-02", "sc-01",
                       ["char-ana-001", "char-ben-002"],
                       timeline_start_seconds=4, timeline_end_seconds=8,
                       duration_seconds=4),
        ]),
        track("a1", "audio", [dialogue_audio(
            "clip-a-06", "l-ana-01", "char-ana-001", "vp-ana-001",
            "aud-ana-01", ["shot-a-01", "shot-a-02"],
            timeline_start_seconds=0, timeline_end_seconds=8,
            duration_seconds=8)]),
    ])
    check("CF-P0-007-A(6): one dialogue line across several shots",
          full_errors(m, reg) == [], "; ".join(full_errors(m, reg)))

    # (7) Several visual shots associated with one audio asset.
    m = manifest([
        track("v1", "video", [
            video_clip("clip-v-07a", "shot-a-01", "sc-01", ["char-ana-001"],
                       timeline_start_seconds=0, timeline_end_seconds=4,
                       duration_seconds=4),
            video_clip("clip-v-07b", "shot-a-02", "sc-01",
                       ["char-ana-001", "char-ben-002"],
                       timeline_start_seconds=4, timeline_end_seconds=8,
                       duration_seconds=4),
        ]),
        track("a1", "audio", [audio_clip(
            "clip-a-07", "dialogue", character_id="char-ana-001",
            voice_profile_id="vp-ana-001", audio_asset_id="aud-ana-01",
            shot_ids=["shot-a-01", "shot-a-02"], role="speaker",
            language="bn", timeline_start_seconds=0, timeline_end_seconds=8,
            duration_seconds=8)]),
    ])
    check("CF-P0-007-A(7): several visual shots, one audio asset",
          full_errors(m, reg) == [], "; ".join(full_errors(m, reg)))

    # (8) Missing Shot ID — must FAIL validation.
    m = manifest([
        track("v1", "video", [video_clip(
            "clip-v-08", "shot-missing-99", "sc-01", ["char-ana-001"])]),
    ])
    errs = full_errors(m, reg)
    check("CF-P0-007-A(8): missing Shot ID fails validation",
          bool(errs) and not schema_errors(m),
          "; ".join(errs) or "no error reported")

    # (9) Missing Dialogue Line ID — must FAIL validation.
    m = manifest([
        track("a1", "audio", [dialogue_audio(
            "clip-a-09", "l-missing-99", "char-ana-001", "vp-ana-001",
            "aud-ana-01", ["shot-a-01"])]),
    ])
    errs = full_errors(m, reg)
    check("CF-P0-007-A(9): missing Dialogue Line ID fails validation",
          bool(errs) and not schema_errors(m),
          "; ".join(errs) or "no error reported")

    # (10) Voice Profile belonging to the wrong Character ID — must FAIL.
    m = manifest([
        track("a1", "audio", [dialogue_audio(
            "clip-a-10", "l-ana-01", "char-ana-001", "vp-ben-001",
            "aud-ana-01", ["shot-a-01"])]),
    ])
    errs = full_errors(m, reg)
    check("CF-P0-007-A(10): voice profile of the wrong character fails",
          bool(errs) and not schema_errors(m),
          "; ".join(errs) or "no error reported")

    # (11) Invalid Audio Asset ID — must FAIL validation.
    m = manifest([
        track("a1", "audio", [dialogue_audio(
            "clip-a-11", "l-ana-01", "char-ana-001", "vp-ana-001",
            "aud-missing-99", ["shot-a-01"])]),
    ])
    errs = full_errors(m, reg)
    check("CF-P0-007-A(11): invalid Audio Asset ID fails validation",
          bool(errs) and not schema_errors(m),
          "; ".join(errs) or "no error reported")

    # (12) Inconsistent sync-group references — must FAIL validation.
    m = manifest([
        track("v1", "video", [video_clip(
            "clip-v-12", "shot-a-01", "sc-01", ["char-ana-001"])]),
        track("a1", "audio", [dialogue_audio(
            "clip-a-12", "l-ana-01", "char-ana-001", "vp-ana-001",
            "aud-ana-01", ["shot-a-01"])]),
    ], synchronization_groups=[sync_group(
        "sync-12", ["clip-nope"], ["clip-a-12"], ["l-ana-01"],
        ["shot-a-01"])])
    errs = full_errors(m, reg)
    check("CF-P0-007-A(12): inconsistent sync-group references fail",
          bool(errs) and not schema_errors(m),
          "; ".join(errs) or "no error reported")

    # (13) Valid legacy v2.3 timeline.
    legacy = load_fixture("timeline-valid-v23.json")
    check("CF-P0-007-A(13): valid legacy v2.3 timeline still passes",
          full_errors(legacy, {}) == [],
          "; ".join(full_errors(legacy, {})))
    check("CF-P0-007-A(13): legacy fixture really is v2.3 with no v2.5 field",
          legacy["schema_version"] == "2.3"
          and "frame_rate" not in legacy
          and "synchronization_groups" not in legacy)

    # (14) Valid v2.5 non-dialogue video timeline.
    m = manifest([
        track("v1", "video", [
            video_clip("clip-v-14a", "shot-a-01", "sc-01", ["char-ana-001"],
                       timeline_start_seconds=0, timeline_end_seconds=4,
                       duration_seconds=4, transition_out="dissolve"),
            video_clip("clip-v-14b", "shot-a-02", "sc-01",
                       ["char-ana-001", "char-ben-002"],
                       timeline_start_seconds=4, timeline_end_seconds=8,
                       duration_seconds=4, transition_in="dissolve"),
        ]),
    ], frame_rate=24, resolution={"width": 1920, "height": 1080},
        aspect_ratio="16:9", timebase="seconds",
        sequence_id="seq-test-014", scene_plan_id="scene-plan-test-001",
        shot_plan_id="shot-plan-test-001")
    check("CF-P0-007-A(14): valid v2.5 non-dialogue video timeline",
          full_errors(m, reg) == [], "; ".join(full_errors(m, reg)))

    # --- Fixtures ----------------------------------------------------------
    v25 = load_fixture("timeline-valid-v25-multicharacter.json")
    check("CF-P0-007-A: v2.5 multi-character fixture validates (schema)",
          schema_errors(v25) == [], "; ".join(schema_errors(v25)))
    check("CF-P0-007-A: v2.5 multi-character fixture validates (cross-refs)",
          validate_timeline_cross_references(v25, reg) == [],
          "; ".join(validate_timeline_cross_references(v25, reg)))
    check("CF-P0-007-A: v2.5 fixture is multi-character (2 speakers)",
          {c.get("character_id") for t in v25["tracks"] for c in t["clips"]
           if t["kind"] == "audio" and c.get("character_id")}
          == {"char-ana-001", "char-ben-002"})

    # --- Schema shape (migration contract) ---------------------------------
    schema = load_schema("timeline-manifest.json")
    check("CF-P0-007-A: schema_version enum is ['2.3', '2.5']",
          schema["properties"]["schema_version"]["enum"] == ["2.3", "2.5"])
    check("CF-P0-007-A: $id moved to the v2.5 path",
          schema["$id"].endswith("/schemas/v2.5/timeline-manifest.json"))
    check("CF-P0-007-A: required fields unchanged "
          "(schema_version, id, format, tracks)",
          schema["required"] == ["schema_version", "id", "format", "tracks"])
    check("CF-P0-007-A: all v2.5 additions are optional at the top level",
          all(f not in schema["required"]
              for f in ("sequence_id", "frame_rate", "resolution",
                        "aspect_ratio", "timebase", "hierarchy",
                        "synchronization_groups", "scene_plan_id",
                        "shot_plan_id", "performance_plan_id",
                        "script_to_performance_id")))
    clip_props = schema["properties"]["tracks"]["items"]["properties"][
        "clips"]["items"]["properties"]
    check("CF-P0-007-A: clip keeps clip_id + media required, nothing else",
          schema["properties"]["tracks"]["items"]["properties"]["clips"]
          ["items"]["required"] == ["clip_id", "media"])
    check("CF-P0-007-A: clip carries multi-character character_ids array",
          clip_props["character_ids"]["type"] == "array")
    check("CF-P0-007-A: audio clip carries multi-shot shot_ids array",
          clip_props["shot_ids"]["type"] == "array")
    check("CF-P0-007-A: audio_type enum covers dialogue/narration/music/"
          "ambience/SFX",
          set(clip_props["audio_type"]["enum"]) >= {
              "dialogue", "narration", "sound-effect", "foley",
              "ambience", "music", "other"})

    # --- Extra pins (rules the 14 cases rely on) ---------------------------
    # An approved-temporary character resolves.
    m = manifest([
        track("v1", "video", [video_clip(
            "clip-v-t", "shot-t-01", "sc-01", ["char-temp-004"])]),
    ])
    check("CF-P0-007-A: approved-temporary character resolves",
          full_errors(m, reg) == [], "; ".join(full_errors(m, reg)))
    # A character narrating (bound narration) is permitted.
    m = manifest([
        track("a1", "audio", [audio_clip(
            "clip-a-n", "narration", character_id="char-ana-001",
            voice_profile_id="vp-ana-001", language="bn",
            role="narrator")]),
    ])
    check("CF-P0-007-A: narration with a character voice binding is valid",
          full_errors(m, reg) == [], "; ".join(full_errors(m, reg)))
    # A music clip must not bind a dialogue line.
    m = manifest([
        track("a1", "audio", [audio_clip(
            "clip-a-m", "music", dialogue_line_id="l-ana-01",
            audio_asset_id="aud-music-01")]),
    ])
    check("CF-P0-007-A: music clip binding a dialogue line fails",
          bool(full_errors(m, reg)), "no error reported")
    # A dialogue clip identifying neither line nor speaker fails.
    m = manifest([
        track("a1", "audio", [audio_clip("clip-a-d", "dialogue")]),
    ])
    check("CF-P0-007-A: dialogue clip with no line and no speaker fails",
          bool(full_errors(m, reg)), "no error reported")
    # A video clip picturing a character its shot does not contain fails.
    m = manifest([
        track("v1", "video", [video_clip(
            "clip-v-u", "shot-a-01", "sc-01",
            ["char-ana-001", "char-ben-002"])]),
    ])
    check("CF-P0-007-A: video clip with a character outside its shot fails",
          bool(full_errors(m, reg)), "no error reported")
    # Schema negatives: unknown audio_type / unknown field are rejected.
    bad = manifest([track("a1", "audio", [audio_clip(
        "clip-a-x", "voiceover")])])
    check("CF-P0-007-A: unknown audio_type is rejected by the schema",
          bool(schema_errors(bad)))
    bad = manifest([track("v1", "video", [video_clip(
        "clip-v-x", "shot-a-01", "sc-01", ["char-ana-001"],
        surprise_field="nope")])])
    check("CF-P0-007-A: unknown clip field is rejected (additionalProperties)",
          bool(schema_errors(bad)))
    # A v2.3 record may carry a v2.5-only field and still validate
    # (additive migration: new fields are optional, not version-gated).
    legacy = load_fixture("timeline-valid-v23.json")
    legacy["frame_rate"] = 25
    check("CF-P0-007-A: v2.3 record with a v2.5-only field still validates",
          schema_errors(legacy) == [], "; ".join(schema_errors(legacy)))

    print(f"test_timeline_manifest: {'PASS' if not failures else 'FAIL'} "
          f"({len(failures)} failure(s))")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
