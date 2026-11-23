# Schemas (v2.3, v2.4, v2.5 — P0 + P0-006)

Versioned JSON Schemas for every canonical record type. All schemas are
JSON Schema draft 2020-12, but they deliberately use only the subset that
`scripts/validate-repo.py` (Python standard library only) can check:
`type`, `properties`, `required`, `enum`, `pattern`, `minLength`,
`minimum`, `maximum`, `exclusiveMinimum`, `minItems`, `items`, `additionalProperties: false`, and local
`$ref` to `#/$defs` is NOT used — nested objects are written inline so
the stdlib validator stays small and auditable. If a future schema needs
`allOf`/`oneOf`/`$ref`, the validator must be extended first and the
change tested.

## Files

| File | Record |
|---|---|
| `character.json` | Registered character identity (fixed traits + private reference pointers) |
| `voice-profile.json` | Per-character voice profile (separate from character and sound) |
| `sound-asset.json` | Recurring theme / motif / sonic logo / ambience / Foley / SFX / transition |
| `visual-style-profile.json` | Locked visual style for a project/series |
| `wardrobe.json` | Scene-variable wardrobe state |
| `prop.json` | Prop record |
| `location.json` | Location record |
| `project.json` | Project / series record (links by stable ID) |
| `story-bible.json` | Story bible |
| `episode-state.json` | Episode continuity state |
| `intake-job.json` | Upload / intake + job state (modes incl. `UPLOAD_ONLY`) |
| `reference-review.json` | Reference review (analysis only; never mutates skills) |
| `reference-learning.json` | Learning-candidate lifecycle (`OBSERVED → … → ACCEPTED → DEPRECATED`) |
| `script-contract.json` | Script / scene / shot / performance contract (`VERBATIM_SCRIPT` default) |
| `timeline-manifest.json` | **v2.3/v2.5** Editor-neutral timeline manifest — v2.5 (P0-007) adds video-clip + shot bindings, audio-clip + dialogue bindings, synchronization groups, and cross-reference validation; not a renderer |
| `scene-plan.json` | **v2.4/v2.5** Scene plan — scenes, beats, dramatic intent, emotion + intensity + transitions |
| `shot-plan.json` | **v2.4/v2.5** Shot plan — framing, camera angle/movement, lighting per shot |
| `performance-plan.json` | **v2.4/v2.5** Performance plan — per dialogue line: face, micro-expressions, gaze, posture, gesture, breathing, voice, lip-sync |
| `script-to-performance.json` | **v2.4/v2.5** Script-to-Performance contract (headline deliverable `SCRIPT_TO_PERFORMANCE_SCHEMA.json`) — binds Scene + Shot + Performance Plans with audio and editing plans; dialogue VERBATIM unless a rewrite was explicitly requested |
| `production-profile.json` | **v2.5 (new, P0-006)** Production profile — the composable dimensions for one production: visual style, production medium, source-media type, motion methods, subject types, interaction pattern, per-subject/per-shot overrides |
| `character-registration.json` | **v2.5 (new, P0-006)** Character registration — name + unique ID, type/species, style profile, reference images, voice profile IDs, consent/permissions, registration history |
| `evidence.json` | One evidence record (fact vs interpretation) |
| `approval.json` | Approval / rights / consent / retention record |
| `installer-result.json` | Installer / sync result (one status per component) |
| `build-report.json` | Machine-readable build report |
| `release-manifest.json` | Release manifest (files + hashes + test results) |

## Rules

- Media binaries are NEVER stored in a schema record. A record holds a
  private asset pointer: a relative path (no leading `/`, no `..`) plus
  an optional SHA-256 hash. The file itself lives in the private overlay
  (see `characters/README.md` and `scripts/validate-private-overlay.py`
  via `tests/test_private_overlay.py`).
- Character, voice profile and sound asset are three separate types.
  A character record must not embed voice tags/seed/audio or sound
  files; it links them by ID (`voice_profile_id`, `sound_asset_ids`
  on the project).
- Every schema carries `schema_version: "2.3"` (v2.3 P0), `"2.4"`
  (v2.4 Brain Architecture Amendment — the four script-to-performance
  schemas), or `"2.5"` (v2.5 P0-006 animation-first additive
  migration). Dual-version enums `["2.3", "2.5"]` / `["2.4", "2.5"]`
  are allowed: a schema may accept records written against its
  earlier version as well as 2.5. The migration is additive only —
  no existing required field was removed or retyped, so every valid
  v2.3/v2.4 record remains valid. A breaking change requires a new
  version and a migration note in `CHANGELOG.md`.
- The v2.5 schemas are the P0-006 animation-first contracts:
  `production-profile.json` and `character-registration.json` are
  new; `character.json`, `voice-profile.json`,
  `visual-style-profile.json`, `scene-plan.json`, `shot-plan.json`,
  `performance-plan.json`, and `script-to-performance.json` are
  extended additively (subject kind / species / anatomy /
  articulation, per-subject shot details, character–voice binding,
  production dimensions). Captured footage uses
  `visual_style: "captured-live-action"` and motion method
  `"captured-motion"` (motion as captured by the camera, not
  generated).
- P0-007 (final completion) extends the v2.5 contracts: the timeline
  manifest is v2.5 with clip/shot/audio bindings, synchronization
  groups, and cross-reference validation (the production validator
  `validate_timeline_cross_references` in
  `scripts/timeline_policy.py`, imported by
  `tests/test_timeline_manifest.py`); character registration and
  voice profiles carry a structured `ownership` record
  (`owner_id`, `workspace_id`, `visibility`, `sharing` — opaque
  local IDs, private by default) that replaces the old free-text
  `ownership_scope` (kept only as a deprecated legacy field); and
  v2.5 voice profiles follow conditional validation rules that
  differ by `source` (user-recorded vs AI-generated) and by
  approval state, enforced by the Python validators in
  `scripts/asset_policy.py` because the restricted schema subset
  cannot express conditional requirements — the schema and the
  validators must agree on every record (see the P0-007
  corrections record).
- P0-008 (fail-closed private voice security) hardens the P0-007
  contracts without changing any schema: the production voice
  resolver now REQUIRES requester owner + workspace identity for
  a private v2.5 voice (a missing requester is never an
  authorized internal request); a private voice export requires a
  `TrustedAuthorizationContext` issued by
  `issue_trusted_authorization_context` in
  `scripts/asset_policy.py` — a caller-created authorization
  dictionary (including a forged `granted_by`) never authorizes
  anything, and provider transmission is a separate permission
  from export; timeline validation has a strict v2.5 production
  mode (`strict=True` in `scripts/timeline_policy.py`) that
  fails closed on missing registry data, missing requester
  identity, missing ownership, unauthorized access, and
  unapproved voices, while narration/music/ambience/SFX timelines
  stay valid without a requester; every production access
  decision goes through the centralized `authorize_action`
  (`use_in_project`, `use_in_production`,
  `export_private_asset`, `transmit_to_provider`,
  `share_with_workspace`). The trusted context is a structural
  (type) boundary, not cryptographic proof of identity — the P1
  app/session runtime must supply the actor identity at the
  boundary. Regression suite: `tests/test_private_voice_security.py`
  (`CF-P0-008-SEC`, 74 checks). See the P0-008 corrections
  record.
- The four v2.4 schemas are the Script-to-Performance Intelligence
  contracts: `scene-plan.json`, `shot-plan.json`,
  `performance-plan.json`, and the combined `script-to-performance.json`.
  They use only the validator's restricted subset (no `$ref`/`allOf`/
  `oneOf`), and their valid fixtures live in `tests/fixtures/`
  (`scene-plan-valid.json`, `shot-plan-valid.json`,
  `performance-plan-valid.json`, `script-to-performance-valid.json`).
- Examples that must validate live in `tests/fixtures/` (valid) and
  the negative cases in `tests/test_schemas.py` (invalid).

Validate everything with:

```bash
python3 scripts/validate-repo.py
```
