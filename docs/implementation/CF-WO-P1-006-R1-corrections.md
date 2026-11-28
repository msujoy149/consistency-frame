# CF-WO-P1-006-R1 corrections — Character Consistency, Real Visual Production & Human-Gated Delivery

Work order CF-WO-P1-006-R1, on branch
`feat/cf-p1-004-universal-production-brain`, PR #5 (base
`feat/cf-p1-003-script-to-performance-runtime`). This document
records what was corrected, decided and found during R1. It
contains NO generated values: SHAs, byte counts, durations and
per-file hashes live in the R1 final report and in the delivery
package manifests, never here.

P1-006 evidence stays immutable. R1 produces NEW evidence in
`~/workspace/consistency-frame-p1-delivery/p1006-r1/` and in this
document; it never silently changes earlier evidence. Where R1
changes shared P1-006 code, the change is recorded here in full.

## §0 Phase 0 — P1-006 revalidation

The P1-006 reference project, its runtime modules
(`production_assets.py`, `production_voice.py`,
`production_audio.py`, `production_timeline.py`,
`production_qc.py`, `production_delivery.py`,
`vertical_production.py`), the reference driver and the CI
artifact manifests were audited before any R1 build work.

- All six VoiceStudio WAVs in the P1-006 delivery folder were
  re-verified: SHA-256 and byte size recomputed, ffprobe
  duration/codec/sample rate/channels probed, and each file fully
  decoded to null. All six decode cleanly and match the recorded
  asset metadata, the voice-mapping and the voice-config. Every
  dialogue line maps to the correct audio file, and every line
  text appears verbatim in the P1-006 script. Voice ID
  `p1006-narrator`, seed 42, instruct tag `middle-aged, moderate
  pitch`, language `en-US`.
- The P1-006 asset manifest was rechecked against the delivery
  work folder: all records match. The delivery SHA256SUMS file
  verifies.
- Commercial-use audit of P1-006 assets: the voice is CC-BY-NC
  (non-commercial only); visuals, music bed, room tone and
  whoosh are original, locally generated/synthesised, with no
  third-party material.
- **New finding (see §12): the delivered P1-006 MP4 has a real
  audio defect — narration is audible only for line 1; lines
  2–6 are missing/inaudible. Its audio QC reported no findings.
  The defect is recorded here, not hidden, and the P1-006
  evidence itself is not altered.**

## §1 Capability inspection — what image generation is genuinely available

Established from the environment, not from memory:

- This VM has NO GPU. The old GPU tools (IP-Adapter,
  InstantID, PuLID, StoryDiffusion, ConsisID) were uninstalled
  and are not available.
- OpenMontage is present only as a demo renderer. Production
  assembly stays NOT_TESTED and is refused by the runtime.
- The platform's built-in image generation tool IS available in
  this environment. It was used before for reference images; it
  is the platform's built-in generation — no paid call, no
  credentials. A probe generation succeeded, so it was judged a
  genuinely usable capability for six distinct character scenes
  and was exercised for stills.

Decision recorded honestly:

- Image generation: `platform-builtin-image`, EXERCISED for
  stills (five character references + six scene stills, all
  visually inspected against the bible).
- Image-to-video generation: NOT_TESTED — no such provider was
  used. Motion in the R1 video is deterministic FFmpeg zoompan
  on stills, labelled `ai-generated-still, locally animated`,
  never AI-generated video.
- OpenMontage production assembly: NOT_TESTED.
- All eight P1-005 provider contracts stay NOT_TESTED; no paid
  provider call was made.
- Commercial-use permission for the built-in image generation
  output is UNCONFIRMED — no licence text was verified in this
  environment — so the R1 deliverable is a non-commercial
  demonstration review package, and the report says so.

## §2 Character — Mara, DEMO-CHAR-001

One fictional, project-local ADULT demonstration character.
She is NOT Sarena and NOT any existing canonical user
character; her registry data is private and never enters the
repo, and she is a child, so she is never used here. Mara is
age 28 (range 25–30), a fictional demonstration identity, NOT
registered in the global character registry, never to be merged
into it.

The bible (`examples/p1006-r1-character-consistency/
character-bible.json`, schema 2.5) is designed for
reproducibility: one signature colour defined ONCE (deep teal),
one outfit, one hairstyle, one recognizable accessory (brass
compass pendant), a stylized 3D look (chosen over photorealism
for reproducibility). It contains: stable character ID, front /
three-quarter / side / full-body references, facial expression
references (six expressions), outfit, hair, body proportions,
skin and face appearance, signature colour, accessories, age
range, visual constraints, NEGATIVE constraints, asset
provenance, approval state (`project-level-approved`,
approved by `project-bible`).

CONFIRMED design details are distinguished from production
inferences in the bible: environments, lighting and camera are
shot-list inferences, not bible canon, and no inferred detail
silently becomes approved canon.

Reference images are media: NO image/video/audio binaries are
committed to the repo (`.gitignore` forbids generated media).
The five references live ONLY in the delivery folder
(`work/references/`), referenced from the repo by path +
SHA-256 + byte size. All five were generated with the
platform built-in image tool, the front reference chained as
the identity reference for each subsequent generation, and
verified by direct visual inspection plus the
`verify_reference_assets` check (all VERIFIED). Framing
notes recorded at generation time: the side reference is
effectively full-body rather than the requested upper-body
crop (framing variation, not character drift); the pendant is
not visible in the expressions sheet portraits (cropped at
chest — reference-sheet framing, not a scene); the "relief"
expression shows eyes fully closed rather than half-closed
(minor expression nuance, not drift).

Project-local identity isolation is enforced by
`runtime/character_consistency.py::check_project_local_isolation`
and covered by tests: the demo id must be absent from the
authorized global character registry, and the function never
registers anything.

## §3 Six scenes — "Mara and the Compass Garden"

One coherent original short story with beginning, development
and ending, six distinct scenes (establishing, medium action,
close-up expression, side/three-quarter composition, movement/
action, closing emotional resolution):

- S1 attic studio (establishing), S2 forest path (medium
  action), S3 close-up wonder (same forest as S2 — a close-up
  in the same environment, so the project has five distinct
  environments across six scenes, by design), S4 stream
  (three-quarter), S5 meadow run (movement), S6 hidden garden
  (closing emotional resolution).

Each scene carries scene ID, shot ID, character ID, character
reference IDs, environment ID, prop IDs, composition, camera
framing, lighting, colour direction, action, expression, motion
instructions, asset-generation provenance and output asset
metadata. Every scene still is a distinct, genuine visual
asset — the same reference image is never reused six times.
Each still was generated with the front reference chained as
the identity reference and inspected against the bible.

## §4 Consistency evaluation

`runtime/character_consistency.py` implements the evaluation:

- `validate_character_bible` — schema, adult age range,
  signature colour defined once, all five reference views
  inventoried, provenance CONFIRMED or INFERRED with recorded
  inferences.
- `validate_scene_binding` — shot character id == bible id,
  reference ids resolve, expression resolves, motion is a
  supported still motion, environment/prop ids non-empty.
- `verify_reference_assets` — existence, readability, size and
  SHA-256 against the bible; missing/unreadable/escaping paths
  are errors, never substitutions.
- `evaluate_consistency` — per-scene findings for face
  identity, hair, eyes, outfit, body proportions, signature
  colour and accessories. Rule-based verdict, NEVER a numeric
  score: any fail or any unexplained change → `drift-found`;
  else any review → `needs-human-review`; else `consistent`.
  Missing attributes default to `review`, never silently
  `pass`. Automated evaluation is not editorial approval;
  `human_approval` stays empty.
- Reference sheet and identity comparison sheet builders
  (FFmpeg hstack), with path/size/SHA-256 recorded.

Result for R1: verdict `consistent` across all six scenes,
from direct visual inspection by the build coordinator (no
numeric score, no embedding similarity used). Prop-continuity
observations recorded in the evaluation (NOT character drift —
the pendant itself is present and correct in every scene): in
three scenes the compass appears twice, once as the worn
pendant and once as a separate object; in one scene the satchel
listed in the shot props is not visible in frame (its strap is
visible in another); in one scene the pendant is held up by
its cord as the scene action, rather than worn.

## §5 Voice

Real speech, NOT tones. The local VoiceStudio/OmniVoice
backend was used as a NON-COMMERCIAL internal test voice,
clearly marked non-commercial and blocked from commercial
delivery; the CC-BY-NC restriction is recorded in the voice
config, the delivery manifest and the report. The backend was
started only for the generation (the documented working start
command; `scripts/run.sh` is broken) and stopped immediately
after. Same narrator voice configuration across all six
scenes (seed 42, instruct `middle-aged, moderate pitch`,
language `en-US` — the backend does not recognise `en-US`
and falls back to language-agnostic mode, as in P1-006).
One narrator only: no character-specific voice consistency is
claimed. All six WAVs were verified (hash, decodability,
sample rate, channels, duration) and the dialogue coverage
validated (see §13).

## §6 Sound

Genuine sound assets or locally produced SFX only: narration,
synthesised music bed, room tone and whoosh cues (in-process,
fixed seed, as in P1-006), intentional tail-out silence with a
recorded reason. No licensed music/SFX; no fabricated
music-generation provider execution. Ambience beyond room tone
and whoosh is NOT fabricated. Per-asset source, timing,
duration, gain, fades and hashes are recorded in the sound
design report in the delivery package.

## §7 Animation / video — honest labelling

Scene assets are labelled exactly as produced:

- Scene visuals: `ai-generated-still, locally animated` —
  platform-built-in-image stills animated with deterministic
  FFmpeg zoompan (`runtime/production_assets.py::
  generate_still_clip`, motion zoom-in / zoom-out / pan-left /
  pan-right / static). They are NOT AI-generated video and are
  never reported as such.
- Image-to-video: NOT_TESTED.
- OpenMontage production assembly: NOT_TESTED.
- FFmpeg is the assembly path.

Continuity was checked per scene: no impossible body
movement, no inconsistent object geometry, no unexplained
scale changes, no discontinuous clothing/accessories, no
uncontrolled camera movement, no unexplained
lighting-direction changes, no scene-to-scene identity
changes. Motion is purposeful (slow zoom/pan matched to the
scene action).

## §8 Assembly

The R1 driver
(`scripts/run-p1006-r1-character-render.py`) runs the P1-006
pipeline extended with character work: project intake →
character bible validation → reference verification → scene
binding → isolation check → six still clips (SHA-checked
against the stills manifest) → voice verification → sound
design → canonical timeline → FFmpeg assembly → technical /
visual / audio QC → consistency evaluation + reference sheet +
identity comparison sheet → review delivery package (BLOCKED
by default). It reuses/extends the P1-006 runtime modules;
where P1-006 code conflicted with R1 needs, the earlier code
was updated, never duplicated (see §12 for the audio fix and
§13 for the dialogue-coverage check).

Two driver bugs found and fixed during R1: the delivery root
was computed one level too high, and the still path was joined
against the work directory instead of the delivery root (the
stills manifest stores delivery-root-relative paths).

## §9 Human gate

The review package (playable MP4, character reference sheet,
six-scene contact sheet, timeline overview, narration preview,
sound design summary, technical QC, visual drift report, asset
provenance and licence report, review instruction) is delivered
with the manifest `qc_status: BLOCKED` and `package_purpose:
review`. Approval state stays EMPTY. No reviewer name was
invented, no approval metadata was filled, and BLOCKED was
never flipped to DELIVERY_READY to satisfy a test. Technical
QC is not editorial approval.

## §10 Technical QC

The P1-006 technical QC implementation is retained
unchanged in scope: MP4 container, H.264, AAC, 1080×1920,
9:16, 30 FPS, 30–60 s, all streams decode, no corruption, no
black gaps, no frozen sections, no missing assets, no bad
timestamps, no clipping/audio critical findings. The QC report
refers to the ACTUAL rendered MP4. No automated AI
visual-quality claim is made — no tested visual-analysis tool
was used.

## §11 Tests + CI

The new suite `tests/test_p1006_r1_character.py` is registered
in `tests/run-tests.sh` as `CF-P1-006-R1-CHARACTER`, after
`CF-P1-006-E2E`. It covers: bible validation, reference asset
integrity, project-local identity isolation, six-shot binding,
character attribute consistency, character drift detection,
scene-specific asset provenance, image-generation status
honesty, voice commercial restriction, dialogue mapping,
six-scene timeline, dialogue-coverage validation, asset
tampering, still-clip generation, the audio-mix regression,
contact sheet output, review package integrity, human approval
blocking, the final delivery approval transition, and an
end-to-end fixture render through the R1 driver (two-shot cut,
FFmpeg solid-pattern fixture stills/references — NOT character
images — tone narration). No existing test was weakened.

Five failures found in the first standalone run were all test
or assertion defects, fixed without weakening any assertion:

1. The isolation-collision fixture used a file name the
   registry loader never reads and a record that fails schema
   validation. Fixed with a valid v2.5 character-registration
   record under the loader's file name, asserting the loader
   sees it first.
2. & 5. Two fixtures built reference file names from view keys
   (underscores) while the bible uses hyphens. Fixed by writing
   fixture files from the bible entry's `file` path.
3. The environment assertion demanded six distinct
   environments; S2 and S3 legitimately share the forest
   environment. Fixed to five distinct environments.
4. The timeline suite expected `compute_shot_schedule` to
   reject a 5-of-6 subset; it tolerates subsets. The real gap
   was that no stage validated shot↔line dialogue coverage
   (work-order Phase 5 requirement). Fixed by adding
   `validate_dialogue_coverage` to `runtime/production_timeline.py`
   and calling it from the R1 driver (see §13).

One further fixture defect: solid-colour and smooth-gradient
fixture stills were flagged as frozen segments by the QC
freezedetect check (a slow zoom over a uniform image changes
no pixels). Fixed with detail-rich deterministic Mandelbrot
fixture stills; the QC check itself was not weakened.

CI: the existing Linux FFmpeg jobs (`p0-validate`,
`p1-006-execution`) and Windows Python 3.10/3.12 jobs are
unchanged; the workflow file was NOT changed in R1. CI uses
deterministic local fixtures, never paid calls. No provider is
marked EXERCISED merely because its request was mocked.

## §12 Audio-mix bug — found, fixed, and its effect on the delivered P1-006 MP4

**Symptom.** The R1 tone-mode trial render's final mix
contained audio only in the first ~8 seconds (line 1); lines
2–6, music and room tone were digital silence after that
point. Audio QC flagged it as a major `unexpected-long-silence`
finding.

**Root cause (proven by bisection).** In
`runtime/production_audio.py::_mix_argv`, the voice bus label
was consumed TWICE — once as the `sidechaincompress`
sidechain input (music ducking) and once in the final `amix`.
FFmpeg's implicit split of a doubly-referenced audio label
starves the final mix after the first voice clip. Evidence: a
voice-bus-only mix was correct in every window; the full graph
with sidechaincompress lost lines 2–6; the same graph without
sidechaincompress was correct; three repeated full-graph runs
were deterministic. The music bed and room-tone source files
were verified good throughout. The driver's mix record (peak
and LUFS) did NOT reveal the defect because ebur128 gates out
silence.

**Fix.** When ducking is on, the voice bus is split explicitly
with `asplit=2[voice_duck][voice_mix]` before the
sidechaincompress; the music is ducked from `[voice_duck]`
and the final amix uses `[voice_mix]`. An operations entry
records the explicit split and why. (A first attempt used the
video `split` filter and failed with a media-type mismatch —
`asplit` is the correct audio filter.) The fix changes shared
P1-006 code; it corrects the earlier code rather than
duplicating it.

**Verification.** `mix_audio` on the R1 timeline now measures
audible levels in every 1-second slice, and the full real-voice
driver re-run produced zero audio findings with narration
audible throughout every line window.

**Effect on the delivered P1-006 MP4 (disclosure, not a silent
change).** The same defect is present in the delivered P1-006
video: narration is audible only for line 1; lines 2–6 are
missing/inaudible (measured per-second loudness confirms it).
Its audio QC reported NO findings because the music bed keeps
the level hovering at the silence threshold. This is a genuine
defect in the delivered P1-006 video. The P1-006 evidence
itself is NOT re-rendered or altered in R1; the defect is
recorded here and in the R1 final report so it is disclosed,
not hidden.

## §13 Dialogue-coverage validation (added in R1)

`runtime/production_timeline.py::validate_dialogue_coverage`
returns errors (empty list = fully covered): every voice line
must map to exactly one shot, and every shot must carry
exactly one voice line. A line with no shot would be narration
without a scene; a shot with no line would be a scene without
narration; a line mapped to two shots is an error. The R1
driver calls it after the verbatim script/voice-config check
and refuses to render on any error. The P1-006 driver does not
call it, so P1-006 behaviour is unchanged.

## §14 Provider readiness (summary)

Per-provider status lives in
`docs/runtime/PROVIDER_ADAPTERS.md`. R1 adds one row:
`platform-builtin-image` — EXERCISED for stills (five
references + six scene stills, all inspected); image-to-video
NOT_TESTED; commercial-use permission UNCONFIRMED (no licence
text verified here). All eight P1-005 external providers stay
NOT_TESTED. No OmniVoice CC-BY-NC asset is used for commercial
output. No silent substitution, no unavailable/discontinued
model IDs.

## §15 Honest verdict (work-order §16)

- Genuine AI still generation WAS available and exercised
  (platform built-in image generation, five references + six
  scene stills, all visually inspected against the bible).
- Image-to-video was NOT available/tested — motion is
  deterministic FFmpeg zoompan on stills, labelled honestly.
- The character-consistency test as specified (the same
  approved character across six independently produced scenes,
  evaluated against the bible with actual visual inspection)
  was carried out; the verdict is `consistent`, with the
  prop-continuity observations of §4 recorded.
- The audio-mix defect that would have broken narration was
  found and fixed in R1, and the fix is verified in the
  delivered R1 MP4. The same defect remains in the
  already-delivered P1-006 MP4 and is disclosed in §12 — it
  must not be hidden.
- The complete AI film factory is NOT claimed finished.
  Open limitations carried forward: no video provider
  VERIFIED/EXERCISED; no external live conformance run;
  OpenMontage production assembly NOT_TESTED; the P1-003
  handbook PDF cross-check is still open.
