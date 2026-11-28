# Character consistency runtime (CF-WO-P1-006-R1)

The character consistency runtime
(`runtime/character_consistency.py`) is the ninth P1 runtime
component. It proves that one approved character stays the
same character across several independently produced scenes,
and it does so without ever claiming a machine check is a human
one. It sits on the P1-006 vertical production runtime
(`docs/runtime/VERTICAL_PRODUCTION_RUNTIME.md`): the R1 driver
(`scripts/run-p1006-r1-character-render.py`) runs the P1-006
pipeline with character validation, still-clip generation,
consistency evaluation and the review sheets added.

## What it is for

One project-local character, six distinct scenes, one verdict
that a human can review. The runtime answers four questions:

1. Is the character bible well-formed and honestly marked
   (confirmed design vs production inference)?
2. Does every shot bind to that bible (right character, known
   references, known expression, supported motion)?
3. Are the reference assets the bible claims, byte for byte?
4. Did any scene change the character without explanation?

It never answers a fifth question — "is this good enough to
ship?" — that is the named human reviewer's decision, and the
runtime keeps the approval empty until one is supplied.

## The character bible

`examples/p1006-r1-character-consistency/character-bible.json`
(schema 2.5) is the single source of truth for the demo
character. Required contents:

- Stable character ID, name, age range (adult, 18+, for a
  demonstration character), and the explicit statement that the
  identity is fictional and project-local.
- `is_canonical_user_character: false` and
  `is_registered_in_global_registry: false` — always.
- Front / three-quarter / side / full-body references plus a
  facial-expression reference sheet, each with asset id, file,
  status and (once generated) SHA-256 + byte size.
- Outfit, hair, body proportions, skin and face appearance,
  signature colour, accessories.
- Visual constraints and NEGATIVE constraints.
- Asset provenance, including the image-generation status.
- Approval state (`project-level-approved`, approved by
  `project-bible`).

The signature colour is defined ONCE as a single 6-digit hex
value and must be present on the character in every scene.
CONFIRMED design details are distinguished from production
inferences (environments, lighting, camera are shot-list
inferences, not bible canon); an inferred detail with no
record is an error, never silently promoted to canon.

Reference images are media and are NEVER committed:
`.gitignore` forbids generated media. References and scene
assets live ONLY in the delivery folder, referenced from the
repo by path + SHA-256 + byte size.

## Functions

### `validate_character_bible(bible) -> list[str]`

Schema 2.5, valid id, `is_canonical_user_character: false`,
`is_registered_in_global_registry: false`, all required fields
present, age range valid and adult (18+), signature colour
defined once (one 6-digit hex), all five reference views
inventoried with asset ids + files, provenance.design
CONFIRMED or INFERRED with recorded inferences. Returns a list
of error strings; empty means valid.

### `validate_scene_binding(bible, shot) -> list[str]`

Shot character id == bible id; every reference id resolves
to a bible reference; the expression resolves to a bible
expression; the motion is one of the supported still motions;
environment and prop ids are non-empty. Returns errors; empty
means bound.

### `verify_reference_assets(bible, delivery_root) -> dict`

Bible `file` entries are relative to the DELIVERY root (for
example `work/references/mara-front-ref.png`). Verifies
existence, readability (probe width/height), and records size +
SHA-256 + status `VERIFIED` per reference. Missing,
unreadable or path-escaping entries are errors, never
substitutions.

### `check_project_local_isolation(character_id, *, overlay_root=None) -> list[str]`

The id must be absent from the authorized global character
registry (via `identity_resolution.
load_authorized_character_registry`). The function never
registers anything. A missing/unconfigured registry means
isolated by construction (the loader raises, caught, registry
treated as empty).

### `evaluate_consistency(bible, scene_evaluations) -> dict`

Per-scene findings `{attribute: pass|fail|review}` for the
seven attributes: face identity, hair, eyes, outfit, body
proportions, signature colour, accessories. Rule-based
verdict, NEVER a numeric score:

- any `fail`, or any unexplained change → `drift-found`;
- else any `review` → `needs-human-review`;
- else `consistent`.

Missing attributes default to `review`, never silently `pass`.
Returns per-scene verdicts, an attribute summary,
`human_approval: None`, and a note that automated evaluation
is not editorial approval. An embedding similarity score may
be attached only as documented supporting evidence; it never
decides the verdict.

### `build_reference_sheet(reference_paths, output_path) -> dict`

FFmpeg hstack of the four reference views at 1400 px height.
Returns path/size/SHA-256; raises `CharacterConsistencyError`
on failure.

### `build_identity_comparison_sheet(front_reference, keyframe_paths, output_path) -> dict`

Front reference + one keyframe per scene, in scene order.
Returns path/size/SHA-256; raises `CharacterConsistencyError`
on failure.

## Still clips — AI stills, locally animated

`runtime/production_assets.py` adds the `ai-still` visual
recipe kind (`VISUAL_RECIPE_KINDS`) and two functions:

- `still_animation_argv(still_path, motion, motion_rate,
  duration_seconds, width, height, fps)` — pure function; the
  still is scaled to cover 1080x1920 centre-cropped, then
  animated with a deterministic zoompan move at 30 fps.
- `generate_still_clip(*, still_path, expected_sha256,
  motion, motion_rate, duration_seconds, output_path,
  asset_id, project_id, shot_id, ...)` — refuses a missing
  still, refuses a SHA-256 mismatch, probes the still for
  readability, requires exact 1080x1920 / 30 FPS / duration,
  and records generation `method: ai-generated-still, locally
  animated`, `still_provider: platform-builtin-image`, still
  SHA/dimensions, motion and argv. Returns a VERIFIED record.

Supported motions (`STILL_MOTIONS`): `zoom-in`, `zoom-out`,
`pan-left`, `pan-right`, `static`.

Labelling rule, enforced by the runtime and the tests: a
locally animated still is NEVER reported as AI-generated
video. Image-to-video is NOT_TESTED unless a provider was
actually exercised and its execution recorded.

## Dialogue coverage

`runtime/production_timeline.py::validate_dialogue_coverage
(voice_lines, shots) -> list[str]` returns errors (empty =
fully covered): every voice line must map to exactly one
shot, and every shot must carry exactly one voice line. A
missing scene is an error, never a silent omission. The R1
driver calls it after the verbatim script/voice-config check
and refuses to render on any error.

## The audio-mix fix (shared P1-006 code)

`runtime/production_audio.py::_mix_argv` had a defect: the
voice bus label was consumed twice — once as the
`sidechaincompress` sidechain input (music ducking) and once
in the final `amix` — which starved the final mix after the
first voice clip. The fix splits the voice bus explicitly
with `asplit=2[voice_duck][voice_mix]` before the
sidechaincompress; the music is ducked from `[voice_duck]`
and the final amix uses `[voice_mix]`. Full record:
`docs/implementation/CF-WO-P1-006-R1-corrections.md` §12,
including the disclosure that the same defect is present in
the already-delivered P1-006 MP4.

## Review package and the human gate

The R1 driver builds the review package with the manifest
`qc_status: BLOCKED` and `package_purpose: review` while
editorial approval is missing. `DELIVERY_READY` needs a named
human reviewer; `automated` is refused. The consistency
report carries `human_approval: None`. The delivery package
contains: the playable MP4, the character reference sheet,
the six-scene contact sheet, scene-by-scene keyframes, the
identity comparison sheet, the character drift report, the
scene asset manifest, the visual provenance report, the
timeline overview, the narration preview, the sound design
summary, technical QC, and the asset provenance and licence
report, plus a review instruction for the project owner.

## Tests

`tests/test_p1006_r1_character.py` (registered in
`tests/run-tests.sh` as `CF-P1-006-R1-CHARACTER`) covers bible
validation, reference integrity, project-local identity
isolation, six-shot binding, attribute consistency, drift
detection, scene provenance, image-generation status honesty,
voice commercial restriction, dialogue mapping, the six-scene
timeline, dialogue coverage, asset tampering, still-clip
generation, the audio-mix regression, the human gate, and an
end-to-end fixture render through the R1 driver.
