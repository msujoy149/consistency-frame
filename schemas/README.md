# Schemas (v2.3, P0)

Versioned JSON Schemas for every canonical record type. All schemas are
JSON Schema draft 2020-12, but they deliberately use only the subset that
`scripts/validate-repo.py` (Python standard library only) can check:
`type`, `properties`, `required`, `enum`, `pattern`, `minLength`,
`minimum`, `minItems`, `items`, `additionalProperties: false`, and local
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
| `timeline-manifest.json` | Editor-neutral timeline manifest (media references only; not a renderer) |
| `scene-plan.json` | **v2.4** Scene plan — scenes, beats, dramatic intent, emotion + intensity + transitions |
| `shot-plan.json` | **v2.4** Shot plan — framing, camera angle/movement, lighting per shot |
| `performance-plan.json` | **v2.4** Performance plan — per dialogue line: face, micro-expressions, gaze, posture, gesture, breathing, voice, lip-sync |
| `script-to-performance.json` | **v2.4** Script-to-Performance contract (headline deliverable `SCRIPT_TO_PERFORMANCE_SCHEMA.json`) — binds Scene + Shot + Performance Plans with audio and editing plans; dialogue VERBATIM unless a rewrite was explicitly requested |
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
- Every schema carries `schema_version: "2.3"` (v2.3 P0) or `"2.4"`
  (v2.4 Brain Architecture Amendment — the four script-to-performance
  schemas). A breaking change requires a new version and a migration
  note in `CHANGELOG.md`.
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
