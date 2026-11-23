#!/usr/bin/env python3
"""Consistency Frame P0 — production timeline policy.

The production home of timeline cross-reference validation
(CF-WO-P0-008, Correction C). Previously the reference
implementation of validate_timeline_cross_references() lived only
in tests/test_timeline_manifest.py (CF-WO-P0-007 Correction A) —
a validator that exists only in a test file cannot be called by
the actual Consistency Frame production planning and handoff
pipeline, and a test proving a test-file helper works is not proof
that the production system enforces the same rules. The
implementation moved here verbatim; the test file now imports it
and keeps only fixtures and cases.

Two validation modes (CF-WO-P0-009, Task C — strict by default):

- Production (validate_timeline_cross_references, the normal entry
  point): FAIL CLOSED by default. A call with no `strict` argument
  runs the FULL strict v2.5 production contract (ownership +
  requester + approval, via _strict_v25_errors) on every v2.5
  manifest — omitting a keyword argument can never downgrade a
  v2.5 Timeline to structural-only validation. Only a manifest
  whose schema_version is exactly "2.3" keeps its historical
  legacy structural contract by default; any other version is
  validated strictly (a non-2.5 version under an explicit
  strict=True call is itself an error). Passing strict=False for
  a v2.5 manifest is REFUSED (an error is returned): structural-
  only validation of a v2.5 Timeline is available ONLY through
  the explicitly named validate_timeline_structural() below.
- Structural / legacy (validate_timeline_structural): the P0-007
  relationship contract ONLY. Every cross-reference rule
  (shot/scene/dialogue-line/character/voice/audio/clip/track/
  sync-group existence, timing, speaker/listener agreement, no
  silent character/voice/audio switch) is enforced against the
  registry. A registry section that is ABSENT is skipped (partial
  registries allowed); a section that is PRESENT is authoritative.
  Valid v2.3 timelines still pass under this contract. This entry
  point performs NO ownership, requester, authorization or
  approval check: a structurally clean result ([]) is NOT an
  authorization, is NOT proof a Timeline may be used in
  production, and MUST NEVER be used to authorize or export a
  v2.5 Timeline. It exists for legacy v2.3 workflows and for
  structural diagnosis only.

The timeline registry holds MINIMAL reference records (id,
character_id, approval_status, ownership) — not full voice
profiles — so the full production voice resolver
(asset_policy.resolve_voice_for_production, which validates the
complete v2.5 voice record) is not applicable here. The
ownership/access decision is centralized in
asset_policy.authorize_action, which the resolver also uses, so
no second ownership algorithm exists.

Registry shape (mini-registries are built inline in the test
file; no other module's fixtures are depended on):
    {
      "shots":          {shot_id: {"shot_id", "scene_id", "character_ids"[...]}},
      "scenes":         {scene_id: {"scene_id"}},
      "dialogue_lines": {dialogue_line_id: {"dialogue_line_id", "character_id",
                                             "voice_profile_id", "audio_asset_id"}},
      "characters":     {character_id: {"id", "status", "temporary": bool,
                                        "ownership": {...}}},
      "voice_profiles": {voice_profile_id: {"id", "character_id",
                                             "approval_status", "ownership": {...}}},
      "audio_assets":   {audio_asset_id: {"id", "approved": bool, "status",
                                          "ownership": {...},
                                          "character_id": ...}},
    }

Validator-subset gap: scripts/validate-repo.py supports only the
restricted JSON-Schema subset (type/properties/required/enum/pattern/
minLength/minimum/maximum/exclusiveMinimum/minItems/items/
additionalProperties). It has NO if/then/else, allOf/oneOf/anyOf,
$ref, dependentRequired or uniqueItems, so NO conditional rule lives
in schemas/timeline-manifest.json: format-dependent requirements
(e.g. frame_rate with timebase frames/timecode) stay optional with a
description, and every cross-field / cross-record rule (shot exists,
line exists, voice belongs to the character, sync-group members exist)
is enforced semantically by validate_timeline_cross_references() here
— the same pattern test_schemas.py uses for the dialogue-rewrite,
non-verbal-line and articulation rules.
"""
import os
import sys

try:
    from asset_policy import (authorize_action, ownerships_match,
                              validate_ownership)
except ImportError:  # pragma: no cover - direct execution
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from asset_policy import (authorize_action, ownerships_match,
                              validate_ownership)

NON_DIALOGUE_AUDIO_TYPES = ("music", "ambience", "sound-effect", "foley")


def _structural_errors(manifest, registry):
    """Structural cross-reference validation only (P0-007 contract).

    Internal implementation shared by validate_timeline_structural()
    and validate_timeline_cross_references(). Performs NO ownership,
    requester, authorization or approval check: its result must
    NEVER be treated as production authorization for a v2.5
    Timeline. Returns a list of error strings; empty means the
    manifest's relationships are structurally valid.
    """
    errors = []
    if not isinstance(manifest, dict):
        return ["timeline manifest is not an object"]
    if not isinstance(registry, dict):
        return ["registry is not an object"]

    shots = registry.get("shots")
    scenes = registry.get("scenes")
    lines = registry.get("dialogue_lines")
    characters = registry.get("characters")
    voices = registry.get("voice_profiles")
    audio_assets = registry.get("audio_assets")

    def check_character(cid, where):
        if characters is None:
            return
        rec = characters.get(cid)
        if rec is None:
            errors.append(f"{where}: character_id '{cid}' does not resolve "
                          "to a registered or approved-temporary character "
                          "record")
        elif isinstance(rec, dict) and rec.get("status") == "deprecated":
            errors.append(f"{where}: character_id '{cid}' is deprecated")

    def check_voice(vpid, expect_character_id, where):
        """Resolve a voice profile; return its owning character_id or None."""
        if voices is None:
            return None
        rec = voices.get(vpid)
        if rec is None:
            errors.append(f"{where}: voice_profile_id '{vpid}' does not "
                          "resolve to a voice profile record")
            return None
        if not isinstance(rec, dict):
            return None
        if rec.get("approval_status") == "rejected":
            errors.append(f"{where}: voice_profile_id '{vpid}' is rejected")
        owner = rec.get("character_id")
        if not owner:
            errors.append(f"{where}: voice_profile_id '{vpid}' has no "
                          "character_id — a voice profile must belong to "
                          "exactly one character")
        elif expect_character_id and owner != expect_character_id:
            errors.append(f"{where}: voice_profile_id '{vpid}' belongs to "
                          f"character '{owner}', not '{expect_character_id}' "
                          "— an audio clip must not silently switch to "
                          "another character's voice")
        return owner

    def check_audio_asset(aid, where):
        if audio_assets is None:
            return
        rec = audio_assets.get(aid)
        if rec is None:
            errors.append(f"{where}: audio_asset_id '{aid}' does not "
                          "resolve to a private/approved audio asset record")
        elif isinstance(rec, dict):
            if rec.get("approved") is False:
                errors.append(f"{where}: audio_asset_id '{aid}' is not "
                              "approved")
            if rec.get("status") in ("rejected", "deprecated"):
                errors.append(f"{where}: audio_asset_id '{aid}' has status "
                              f"'{rec.get('status')}'")

    def check_shot(sid, where):
        if shots is None:
            return None
        rec = shots.get(sid)
        if rec is None:
            errors.append(f"{where}: shot_id '{sid}' does not exist in the "
                          "referenced shot plan")
            return None
        return rec if isinstance(rec, dict) else {}

    def check_scene(scid, where):
        if scenes is None:
            return
        if scid not in scenes:
            errors.append(f"{where}: scene_id '{scid}' does not exist in "
                          "the referenced scene plan")

    def check_line(lid, where):
        if lines is None:
            return None
        rec = lines.get(lid)
        if rec is None:
            errors.append(f"{where}: dialogue_line_id '{lid}' does not "
                          "exist in the referenced performance plan")
            return None
        return rec if isinstance(rec, dict) else {}

    # --- Collect clips (clip_id -> (clip, track kind, track_id)) ----------
    clips = {}
    for ti, track in enumerate(manifest.get("tracks") or []):
        if not isinstance(track, dict):
            continue
        kind = track.get("kind")
        tid = track.get("track_id")
        for clip in track.get("clips") or []:
            if not isinstance(clip, dict):
                continue
            cid = clip.get("clip_id")
            where = f"tracks[{ti}].clips[{cid or '?'}]"
            if cid is None:
                errors.append(f"{where}: clip without clip_id")
                continue
            if cid in clips:
                errors.append(f"duplicate clip_id '{cid}' — clip IDs must "
                              "be unique across the timeline")
            clips[cid] = (clip, kind, tid)
            if clip.get("track_id") is not None and tid is not None \
                    and clip["track_id"] != tid:
                errors.append(f"{where}: track_id '{clip['track_id']}' does "
                              f"not match enclosing track '{tid}'")
            # Timing sanity: the schema can bound each field, not relate them.
            if isinstance(clip.get("in_seconds"), (int, float)) \
                    and isinstance(clip.get("out_seconds"), (int, float)) \
                    and clip["out_seconds"] < clip["in_seconds"]:
                errors.append(f"{where}: out_seconds {clip['out_seconds']} "
                              f"is before in_seconds {clip['in_seconds']}")
            if isinstance(clip.get("timeline_start_seconds"), (int, float)) \
                    and isinstance(clip.get("timeline_end_seconds"), (int, float)) \
                    and clip["timeline_end_seconds"] < clip["timeline_start_seconds"]:
                errors.append(f"{where}: timeline_end_seconds "
                              f"{clip['timeline_end_seconds']} is before "
                              f"timeline_start_seconds "
                              f"{clip['timeline_start_seconds']}")

    # --- Per-clip references ----------------------------------------------
    for cid, (clip, kind, _tid) in clips.items():
        where = f"clip '{cid}'"
        if clip.get("scene_id") is not None:
            check_scene(clip["scene_id"], where)
        shot_rec = None
        if clip.get("shot_id") is not None:
            shot_rec = check_shot(clip["shot_id"], where)
            if shot_rec is not None and clip.get("scene_id") is not None \
                    and shot_rec.get("scene_id") is not None \
                    and shot_rec["scene_id"] != clip["scene_id"]:
                errors.append(f"{where}: scene_id '{clip['scene_id']}' does "
                              f"not match shot '{clip['shot_id']}' scene "
                              f"'{shot_rec['scene_id']}'")
        for sid in clip.get("shot_ids") or []:
            check_shot(sid, where)
        for char_id in clip.get("character_ids") or []:
            check_character(char_id, where)
        if clip.get("character_id") is not None:
            check_character(clip["character_id"], where)
        # A clip must not show a character the shot plan does not place
        # in that shot.
        if shot_rec is not None \
                and isinstance(shot_rec.get("character_ids"), list) \
                and clip.get("character_ids"):
            for char_id in clip["character_ids"]:
                if char_id not in shot_rec["character_ids"]:
                    errors.append(f"{where}: character_id '{char_id}' is "
                                  f"not in shot '{clip['shot_id']}' — a "
                                  "video clip must not reference an "
                                  "unrelated character")
        line_rec = None
        if clip.get("dialogue_line_id") is not None:
            line_rec = check_line(clip["dialogue_line_id"], where)
        if clip.get("audio_asset_id") is not None:
            check_audio_asset(clip["audio_asset_id"], where)
        # Voice: the expected owner is the clip's character, else the
        # dialogue line's speaker.
        expect_char = clip.get("character_id")
        if expect_char is None and line_rec is not None:
            expect_char = line_rec.get("character_id")
        if clip.get("voice_profile_id") is not None:
            check_voice(clip["voice_profile_id"], expect_char, where)
        # Dialogue-line agreement: no silent character/voice/audio switch.
        if line_rec is not None:
            line_char = line_rec.get("character_id")
            if line_char:
                if clip.get("character_id") is not None \
                        and clip["character_id"] != line_char:
                    errors.append(f"{where}: character_id "
                                  f"'{clip['character_id']}' does not match "
                                  f"the speaker '{line_char}' of "
                                  f"dialogue_line_id "
                                  f"'{clip['dialogue_line_id']}'")
                if clip.get("character_ids") \
                        and line_char not in clip["character_ids"]:
                    errors.append(f"{where}: dialogue_line_id "
                                  f"'{clip['dialogue_line_id']}' is spoken "
                                  f"by '{line_char}', who is not among this "
                                  "clip's character_ids — a video clip must "
                                  "not reference an unrelated dialogue")
            line_voice = line_rec.get("voice_profile_id")
            if line_voice and clip.get("voice_profile_id") is not None \
                    and clip["voice_profile_id"] != line_voice:
                errors.append(f"{where}: voice_profile_id "
                              f"'{clip['voice_profile_id']}' does not match "
                              f"the voice '{line_voice}' bound to "
                              f"dialogue_line_id "
                              f"'{clip['dialogue_line_id']}' — an audio "
                              "clip must not silently switch to another "
                              "character's voice")
            line_audio = line_rec.get("audio_asset_id")
            if line_audio and clip.get("audio_asset_id") is not None \
                    and clip["audio_asset_id"] != line_audio:
                errors.append(f"{where}: audio_asset_id "
                              f"'{clip['audio_asset_id']}' does not match "
                              f"the audio asset '{line_audio}' bound to "
                              f"dialogue_line_id "
                              f"'{clip['dialogue_line_id']}'")
        # Audio-type rules (audio tracks only).
        if kind == "audio":
            atype = clip.get("audio_type")
            if atype in NON_DIALOGUE_AUDIO_TYPES \
                    and clip.get("dialogue_line_id") is not None:
                errors.append(f"{where}: audio_type '{atype}' must not bind "
                              f"dialogue_line_id "
                              f"'{clip['dialogue_line_id']}' — music, "
                              "ambience and SFX carry no dialogue")
            if atype == "dialogue" \
                    and clip.get("dialogue_line_id") is None \
                    and clip.get("character_id") is None:
                errors.append(f"{where}: audio_type 'dialogue' with no "
                              "dialogue_line_id and no character_id — a "
                              "dialogue clip must identify its line or its "
                              "speaker")
            # Narration needs no character voice binding; music/ambience/
            # SFX/foley need no character, voice or dialogue binding.

    # --- Synchronization groups -------------------------------------------
    seen_groups = set()
    for gi, group in enumerate(manifest.get("synchronization_groups") or []):
        if not isinstance(group, dict):
            continue
        gid = group.get("sync_group_id")
        where = f"synchronization_groups[{gi}] ({gid or '?'})"
        if gid is None:
            errors.append(f"{where}: sync group without sync_group_id")
            continue
        if gid in seen_groups:
            errors.append(f"duplicate sync_group_id '{gid}'")
        seen_groups.add(gid)
        vids = group.get("video_clip_ids") or []
        aids = group.get("audio_clip_ids") or []
        if not vids and not aids:
            errors.append(f"{where}: sync group references no clips")
        for vcid in vids:
            if vcid not in clips:
                errors.append(f"{where}: video_clip_id '{vcid}' does not "
                              "exist in the timeline")
            elif clips[vcid][1] not in ("video", "title"):
                errors.append(f"{where}: video_clip_id '{vcid}' is on a "
                              f"'{clips[vcid][1]}' track, not a video track")
        for acid in aids:
            if acid not in clips:
                errors.append(f"{where}: audio_clip_id '{acid}' does not "
                              "exist in the timeline")
            elif clips[acid][1] != "audio":
                errors.append(f"{where}: audio_clip_id '{acid}' is on a "
                              f"'{clips[acid][1]}' track, not an audio track")
        for lid in group.get("dialogue_line_ids") or []:
            check_line(lid, where)
        for sid in group.get("shot_ids") or []:
            check_shot(sid, where)

    # --- Explicit hierarchy map -------------------------------------------
    hier = manifest.get("hierarchy")
    if isinstance(hier, dict):
        if hier.get("timeline_id") is not None \
                and manifest.get("id") is not None \
                and hier["timeline_id"] != manifest["id"]:
            errors.append(f"hierarchy.timeline_id '{hier['timeline_id']}' "
                          f"does not match manifest id '{manifest['id']}'")
        if hier.get("project_id") is not None \
                and manifest.get("project_id") is not None \
                and hier["project_id"] != manifest["project_id"]:
            errors.append(f"hierarchy.project_id '{hier['project_id']}' "
                          "does not match manifest project_id "
                          f"'{manifest['project_id']}'")
        for si, scene in enumerate(hier.get("scenes") or []):
            if not isinstance(scene, dict):
                continue
            where = f"hierarchy.scenes[{si}] ({scene.get('scene_id') or '?'})"
            if scene.get("scene_id") is not None:
                check_scene(scene["scene_id"], where)
            for shot in scene.get("shots") or []:
                if not isinstance(shot, dict):
                    continue
                sw = f"{where}.shots[{shot.get('shot_id') or '?'}]"
                if shot.get("shot_id") is not None:
                    check_shot(shot["shot_id"], sw)
                s_chars = shot.get("character_ids") or []
                for char_id in s_chars:
                    check_character(char_id, sw)
                for lid in shot.get("dialogue_line_ids") or []:
                    check_line(lid, sw)
                for vpid in shot.get("voice_profile_ids") or []:
                    owner = check_voice(vpid, None, sw)
                    if owner is not None and s_chars \
                            and owner not in s_chars:
                        errors.append(f"{sw}: voice_profile_id '{vpid}' "
                                      f"belongs to character '{owner}', who "
                                      "is not among this shot's "
                                      "character_ids")
                for aid in shot.get("audio_asset_ids") or []:
                    check_audio_asset(aid, sw)
                for vcid in shot.get("video_clip_ids") or []:
                    if vcid not in clips:
                        errors.append(f"{sw}: video_clip_id '{vcid}' does "
                                      "not exist in the timeline")
                for acid in shot.get("audio_clip_ids") or []:
                    if acid not in clips:
                        errors.append(f"{sw}: audio_clip_id '{acid}' does "
                                      "not exist in the timeline")
    return errors


def validate_timeline_structural(manifest, registry):
    """Structural / legacy timeline validation ONLY — NOT authorization.

    Runs the P0-007 structural relationship contract and nothing
    else: cross-reference existence, timing, speaker/listener
    agreement, no silent character/voice/audio switch. It performs
    NO ownership, requester, authorization or approval check.

    Use ONLY for legacy v2.3 workflows and for structural
    diagnosis. A structurally clean result ([]) is NOT an
    authorization, is NOT proof a Timeline may be used in
    production, and MUST NEVER be used to authorize or export a
    v2.5 Timeline — for that, call
    validate_timeline_cross_references(), which is strict by
    default on v2.5 manifests.

    Args:
        manifest: a timeline-manifest record (dict).
        registry: a dict of reference records, keyed as documented
            in the module docstring. A section that is absent is
            skipped; a section that is present is authoritative.
    Returns:
        A list of structural error strings; empty means the
        manifest's relationships are structurally valid.
    """
    return _structural_errors(manifest, registry)


def validate_timeline_cross_references(manifest, registry,
                                       requesting_owner_id=None,
                                       requesting_workspace_id=None,
                                       *, strict=None):
    """Validate a timeline manifest — PRODUCTION entry point.

    This is the entry point suitable for production,
    authorization-sensitive validation. It ALWAYS runs the
    structural contract, and — by default, with no `strict`
    argument — it ALSO runs the full strict v2.5 production
    contract (fail-closed ownership enforcement, via
    _strict_v25_errors) on every v2.5 manifest. Omitting the
    `strict` keyword can never downgrade a v2.5 Timeline to
    structural-only validation.

    Strict v2.5 contract (applies only to schema_version "2.5"
    manifests): every kind of asset the manifest references must
    have its registry section present (missing registry data
    fails closed); requester owner + workspace identity is
    required whenever the timeline references a character, voice
    or dialogue line (legitimate non-character tracks —
    narration, music, ambience, SFX, foley — reference none of
    these and remain valid without a requester); every referenced
    character, voice and dialogue-bound audio asset must carry a
    valid ownership binding and must be accessible to the
    requester (asset_policy.authorize_action, action
    "use_in_project"); every referenced voice must be approved;
    and every referenced voice profile's ownership must match
    the ownership of the character it claims to represent
    (asset_policy.ownerships_match — the same binding the
    production voice resolver enforces). A voice audio reference
    from another user/character is never silently attached to a
    private character's production.

    Args:
        manifest: a timeline-manifest record (dict).
        registry: a dict of reference records, keyed as documented
            in the module docstring. A section that is absent is
            skipped in structural mode; a section that is present
            is authoritative.
        requesting_owner_id / requesting_workspace_id: the
            requester identity. Required in strict mode whenever
            the timeline references a character, voice or dialogue
            line; ignored (not consulted) in structural mode.
        strict: None (default) — production default: strict v2.5
            checks run for a v2.5 manifest; a manifest whose
            schema_version is exactly "2.3" keeps its historical
            legacy structural contract; any other/missing version
            is validated strictly (fail closed). True — force the
            strict v2.5 contract (a strict call on a v2.3 file is
            an error: a v2.3 file is valid only under the legacy
            structural contract, never as an authorized private
            v2.5 production). False — request structural-only
            validation; REFUSED for a v2.5 manifest (an error is
            returned) — use the explicitly named
            validate_timeline_structural() for legacy structural
            work instead, and never to authorize or export.
    Returns:
        A list of error strings; empty means the manifest is
        valid against the registry under the contract that
        applies (structural + strict v2.5 for a v2.5 manifest by
        default).
    """
    errors = _structural_errors(manifest, registry)
    if not isinstance(manifest, dict) or not isinstance(registry, dict):
        return errors
    version = manifest.get("schema_version")
    if strict is True:
        errors.extend(_strict_v25_errors(
            manifest, registry, requesting_owner_id,
            requesting_workspace_id))
    elif strict is False:
        if version == "2.5":
            errors.append(
                "strict=False refused for a v2.5 timeline manifest — "
                "structural-only validation must never silently "
                "downgrade v2.5 production validation; use the "
                "explicitly named validate_timeline_structural() "
                "for legacy structural work only, and never to "
                "authorize or export a v2.5 Timeline")
    elif strict is None:
        # Production default: strict for v2.5 (and for any
        # unknown/missing version — fail closed); only an explicit
        # "2.3" keeps the historical legacy structural contract.
        if version != "2.3":
            errors.extend(_strict_v25_errors(
                manifest, registry, requesting_owner_id,
                requesting_workspace_id))
    else:
        errors.append(
            f"strict must be True, False or None, got {strict!r}")
    return errors


# ---------------------------------------------------------------------------
# Strict v2.5 production validation (CF-WO-P0-008 §4B/§4C)
# ---------------------------------------------------------------------------

def _collect_references(manifest, registry):
    """Collect every ID a manifest references, by kind.

    Returns a dict of sets: characters, voices, dialogue_lines,
    audio_assets, bound_audio_assets (audio bound to a character /
    voice / dialogue line — music, ambience, SFX and foley are
    unbound), shots, scenes, plus audio_characters (audio_asset_id
    -> set of character_ids using it). A dialogue line's own
    character / voice / audio bindings are included, so a line
    naming a speaker also counts as referencing that speaker.
    """
    refs = {"characters": set(), "voices": set(),
            "dialogue_lines": set(), "audio_assets": set(),
            "bound_audio_assets": set(), "shots": set(),
            "scenes": set(), "audio_characters": {}}
    if not isinstance(manifest, dict):
        return refs

    def _bind_audio(aid, char_ids):
        refs["audio_assets"].add(aid)
        if char_ids:
            refs["bound_audio_assets"].add(aid)
            refs["audio_characters"].setdefault(aid, set()).update(
                char_ids)

    for track in manifest.get("tracks") or []:
        if not isinstance(track, dict):
            continue
        for clip in track.get("clips") or []:
            if not isinstance(clip, dict):
                continue
            if clip.get("scene_id") is not None:
                refs["scenes"].add(clip["scene_id"])
            if clip.get("shot_id") is not None:
                refs["shots"].add(clip["shot_id"])
            refs["shots"].update(clip.get("shot_ids") or [])
            clip_chars = set(clip.get("character_ids") or [])
            if clip.get("character_id") is not None:
                clip_chars.add(clip["character_id"])
            refs["characters"].update(clip_chars)
            if clip.get("dialogue_line_id") is not None:
                refs["dialogue_lines"].add(clip["dialogue_line_id"])
            if clip.get("voice_profile_id") is not None:
                refs["voices"].add(clip["voice_profile_id"])
            if clip.get("audio_asset_id") is not None:
                bound = bool(clip.get("dialogue_line_id") is not None
                             or clip_chars
                             or clip.get("voice_profile_id") is not None)
                _bind_audio(clip["audio_asset_id"],
                            clip_chars if bound else set())
    for group in manifest.get("synchronization_groups") or []:
        if not isinstance(group, dict):
            continue
        refs["dialogue_lines"].update(
            group.get("dialogue_line_ids") or [])
        refs["shots"].update(group.get("shot_ids") or [])
    hier = manifest.get("hierarchy")
    if isinstance(hier, dict):
        for scene in hier.get("scenes") or []:
            if not isinstance(scene, dict):
                continue
            if scene.get("scene_id") is not None:
                refs["scenes"].add(scene["scene_id"])
            for shot in scene.get("shots") or []:
                if not isinstance(shot, dict):
                    continue
                if shot.get("shot_id") is not None:
                    refs["shots"].add(shot["shot_id"])
                s_chars = set(shot.get("character_ids") or [])
                refs["characters"].update(s_chars)
                refs["dialogue_lines"].update(
                    shot.get("dialogue_line_ids") or [])
                refs["voices"].update(
                    shot.get("voice_profile_ids") or [])
                for aid in shot.get("audio_asset_ids") or []:
                    _bind_audio(aid, s_chars)
    # A dialogue line's own bindings count as references too.
    lines = registry.get("dialogue_lines") \
        if isinstance(registry, dict) else None
    if isinstance(lines, dict):
        for lid in list(refs["dialogue_lines"]):
            rec = lines.get(lid)
            if not isinstance(rec, dict):
                continue
            line_chars = set()
            if rec.get("character_id"):
                line_chars.add(rec["character_id"])
                refs["characters"].add(rec["character_id"])
            if rec.get("voice_profile_id"):
                refs["voices"].add(rec["voice_profile_id"])
            if rec.get("audio_asset_id"):
                _bind_audio(rec["audio_asset_id"], line_chars)
    return refs


def _strict_v25_errors(manifest, registry, requesting_owner_id,
                       requesting_workspace_id):
    """Strict v2.5 production validation. Returns error strings.

    Applies ONLY to schema_version "2.5" manifests. A strict call
    on any other version is itself an error: a v2.3 file is valid
    only under the legacy structural contract, never as an
    authorized private v2.5 production. Fail closed throughout:
    missing registry data, missing requester identity, missing
    ownership, unauthorized access and unapproved voices are all
    rejections. Narration, music, ambience, SFX and foley tracks
    carry no character/voice/dialogue binding and stay valid.
    """
    errors = []
    if not isinstance(manifest, dict):
        return ["timeline manifest is not an object"]
    if manifest.get("schema_version") != "2.5":
        return ["strict v2.5 production validation requires a v2.5 "
                "timeline manifest (schema_version '2.5'), got "
                f"{manifest.get('schema_version')!r} — a v2.3 file is "
                "valid only under the legacy structural contract, "
                "never as an authorized private v2.5 production"]
    if not isinstance(registry, dict):
        return ["registry is not an object"]
    refs = _collect_references(manifest, registry)
    # Required registry sections: a v2.5 production timeline must
    # resolve every kind of asset it references. A referenced
    # private asset is never accepted merely because its registry
    # section was omitted.
    section_for = {"characters": "characters",
                   "voices": "voice_profiles",
                   "dialogue_lines": "dialogue_lines",
                   "audio_assets": "audio_assets",
                   "shots": "shots", "scenes": "scenes"}
    for kind, section in section_for.items():
        if refs[kind] and registry.get(section) is None:
            errors.append(f"strict v2.5: registry section '{section}' "
                          "is required — the timeline references "
                          f"{sorted(refs[kind])} but the registry "
                          "section was omitted (missing registry data "
                          "fails closed for v2.5 production)")
    # Requester identity is required when the timeline references
    # any private asset (character / voice / dialogue line).
    # Legitimate non-character tracks reference none of these.
    needs_requester = bool(refs["characters"] or refs["voices"]
                           or refs["dialogue_lines"])
    if needs_requester:
        if not requesting_owner_id or \
                not isinstance(requesting_owner_id, str):
            errors.append("strict v2.5: requesting owner identity is "
                          "required — a missing requester identity is "
                          "never an authorized internal request")
        if not requesting_workspace_id or \
                not isinstance(requesting_workspace_id, str):
            errors.append("strict v2.5: requesting workspace identity "
                          "is required — a missing requester identity "
                          "is never an authorized internal request")
    if errors:
        return errors
    characters = registry.get("characters") or {}
    voices = registry.get("voice_profiles") or {}
    audio_assets = registry.get("audio_assets") or {}

    def _access_errors(where, ownership):
        return [f"strict v2.5: {where}: {e}" for e in authorize_action(
            "use_in_project", ownership, requesting_owner_id,
            requesting_workspace_id)]

    for cid in sorted(refs["characters"]):
        rec = characters.get(cid) if isinstance(characters, dict) \
            else None
        if rec is None or not isinstance(rec, dict):
            continue  # structural validation already reported it
        ownership = rec.get("ownership")
        if validate_ownership(ownership):
            errors.append(f"strict v2.5: character_id '{cid}' has no "
                          "valid ownership binding — a character "
                          "without ownership cannot be used in "
                          "private v2.5 production")
            continue
        errors.extend(_access_errors(f"character_id '{cid}'", ownership))
    for vpid in sorted(refs["voices"]):
        rec = voices.get(vpid) if isinstance(voices, dict) else None
        if rec is None or not isinstance(rec, dict):
            continue  # structural validation already reported it
        ownership = rec.get("ownership")
        if validate_ownership(ownership):
            errors.append(f"strict v2.5: voice_profile_id '{vpid}' "
                          "has no valid ownership binding — a voice "
                          "without ownership cannot be used in "
                          "private v2.5 production")
            continue
        errors.extend(_access_errors(f"voice_profile_id '{vpid}'",
                                     ownership))
        if rec.get("approval_status") != "approved":
            errors.append(f"strict v2.5: voice_profile_id '{vpid}' is "
                          "not approved (approval_status "
                          f"{rec.get('approval_status')!r}) — only an "
                          "approved voice may be selected for "
                          "production")
        # CF-WO-P0-009 D: the voice profile's ownership must match
        # the ownership of the character it claims to represent —
        # the same ownership-binding rule the production voice
        # resolver (asset_policy.resolve_voice_for_production /
        # check_voice_binding) enforces, via the shared
        # asset_policy.ownerships_match helper (never a second
        # comparison algorithm). This applies EVEN when both
        # records are individually accessible to the requester
        # (e.g. both shared in the same workspace): shared-
        # workspace access to each asset separately never
        # authorizes linking a voice to another owner's
        # character. Ownership is never silently repaired,
        # replaced or reassigned — a mismatch is a rejection.
        char_id = rec.get("character_id")
        if not char_id or not isinstance(char_id, str):
            errors.append(f"strict v2.5: voice_profile_id '{vpid}' "
                          "has no valid character_id link — a voice "
                          "profile must belong to exactly one "
                          "character")
        else:
            char_rec = characters.get(char_id) \
                if isinstance(characters, dict) else None
            if char_rec is None or not isinstance(char_rec, dict):
                errors.append(f"strict v2.5: voice_profile_id "
                              f"'{vpid}' belongs to character "
                              f"'{char_id}', which does not resolve "
                              "to a registered character record — a "
                              "voice profile must not be linked to "
                              "an unknown character")
            else:
                char_ownership = char_rec.get("ownership")
                if validate_ownership(char_ownership):
                    errors.append(f"strict v2.5: voice_profile_id "
                                  f"'{vpid}' belongs to character "
                                  f"'{char_id}', which has no valid "
                                  "ownership binding — a voice "
                                  "profile must not be linked to a "
                                  "character without ownership")
                elif not ownerships_match(ownership, char_ownership):
                    errors.append(f"strict v2.5: voice_profile_id "
                                  f"'{vpid}' ownership does not match "
                                  f"character '{char_id}' ownership "
                                  "(owner/workspace must match) — a "
                                  "voice profile must not be linked "
                                  "to a character with different "
                                  "ownership, even when both are "
                                  "shared in the same workspace")
    for aid in sorted(refs["bound_audio_assets"]):
        rec = audio_assets.get(aid) if isinstance(audio_assets, dict) \
            else None
        if rec is None or not isinstance(rec, dict):
            continue  # structural validation already reported it
        ownership = rec.get("ownership")
        if validate_ownership(ownership):
            errors.append(f"strict v2.5: audio_asset_id '{aid}' is "
                          "bound to a character/voice but has no "
                          "valid ownership binding — a voice audio "
                          "reference from another user must not be "
                          "silently attached to a private character's "
                          "production")
            continue
        errors.extend(_access_errors(f"audio_asset_id '{aid}'",
                                     ownership))
        # A bound audio asset must belong to the character using it,
        # with matching ownership — never another character's voice.
        rec_char = rec.get("character_id")
        using = refs["audio_characters"].get(aid, set())
        if rec_char and using and rec_char not in using:
            errors.append(f"strict v2.5: audio_asset_id '{aid}' "
                          f"belongs to character '{rec_char}', not the "
                          f"character(s) using it ({sorted(using)}) — "
                          "a voice audio reference from another "
                          "character must not be silently attached")
        for uc in sorted(using):
            urec = characters.get(uc) \
                if isinstance(characters, dict) else None
            if isinstance(urec, dict) \
                    and isinstance(urec.get("ownership"), dict) \
                    and isinstance(ownership, dict) \
                    and not ownerships_match(ownership,
                                             urec.get("ownership")):
                errors.append(f"strict v2.5: audio_asset_id '{aid}' "
                              "ownership does not match character "
                              f"'{uc}' ownership (owner/workspace "
                              "must match)")
    return errors
