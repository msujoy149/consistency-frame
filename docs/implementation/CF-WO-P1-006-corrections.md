# CF-WO-P1-006 — Corrections, decisions and honest limitations

First Complete Vertical Video Production & Delivery. This record
contains NO generated values anywhere: no SHA-256 hashes, no byte
counts, no CI run numbers, no file sizes. Those belong in the
delivery report, never here.

## 1. Defects found and fixed

### 1.1 Voice lines did not have to match the script verbatim

`_validate_voice_config` in `runtime/vertical_production.py`
checked only that a voice line's `line_id` resolved to a script
line. A tampered voice line (same id, different text) passed
validation, so dialogue could silently drift from the approved
script. Fixed: the validator now takes the script lines and
compares each voice line's text byte-for-byte, refusing on any
difference. Regression check `script-text-mismatch-refused` in
`tests/test_p1006_project.py`.

### 1.2 drawbox width expressions must use `iw`, not `w`

The `gradient-split` visual recipe used `w='w/2-6'` for a
drawbox width. FFmpeg rejects it: inside a drawbox `w`/`h`
expression, `w` is the box's own width being defined (circular),
not the input width. The input width is `iw` (and `ih` for
height); `w`/`h` work only in the `x`/`y` expressions. Fixed by
using `iw`/`ih` in the `w`/`h` fields. The `gradient-rings`
recipe never used `w` in a `w`/`h` field (its widths are plain
arithmetic on `t`), so it was unaffected. Regression: the
assets suite generates every recipe kind for real.

### 1.3 `assemble_timeline` read geometry from the wrong shape

`geometry_from_probe` (in `runtime/timeline_delivery.py`)
returns `{"aspect_ratio": ..., "resolution": {"width": ...,
"height": ...}, "frame_rate": ...}` — the dimensions live under
`resolution`, not at the top level. `assemble_timeline` read
`geometry["width"]` directly and crashed with a raw `KeyError`
after a successful render, instead of validating the output.
Fixed to read the nested `resolution` object. Regression:
`tests/test_p1006_assembly.py` (successful render).

### 1.4 drawtext `alpha` expression renders no text at all

Found by visual inspection of the rendered contact sheet (the
agent looked at the keyframes; the technical QC cannot see
missing text). The visual recipes set
`alpha='<fade-in/fade-out expression>'` on both drawtext
filters. In the installed FFmpeg, that makes drawtext render
nothing — not even at the midpoint, where the expression
evaluates to full opacity. A frame rendered without the `alpha`
option shows the keyword correctly, so the option itself is the
cause. Fixed by removing the `alpha` option from both drawtext
filters: the keyword and subtext are present for the whole shot,
and the shot boundaries are already faded by the `xfade`
transitions between clips, so nothing is lost visually.
Regression: `visual-<kind>-keyword-visible` in
`tests/test_p1006_assets.py` — one check per recipe kind, which
extracts the midpoint frame, crops the centre band where the
text sits, and requires near-white pixels. The check fails on
the old code (the band stays mid-blue) and passes on the fix.

### 1.5 Shot keyword never reached the visual recipe

In the shot list the keyword and subtext live at the shot level
(`shot.keyword`, `shot.subtext`) while the gradient is in the
nested `shot.visual` object — but the reference driver passed
only `shot.visual` to `generate_visual_asset`. `visual_argv`
reads the keyword from the recipe, so it saw an empty keyword
and appended no `drawtext` at all: every visual in the
reference render was textless, while every unit test passed
(because the test fixtures put the keyword inside the recipe
directly). Fixed in the driver, which now merges the
shot-level keyword and subtext into the recipe before
generation. Regression: `e2e-keyword-visible` in
`tests/test_p1006_e2e.py` (extracts the shot-1 midpoint frame
from the assembled MP4 and requires near-white pixels in the
centre band — a unit test alone cannot catch a driver
composition bug).

### 1.6 Visuals were not deterministic across runs

The `gradients` source seeds its geometry randomly by default
(`seed=-1`), so the same recipe rendered twice produced
different files (different SHA-256). The "deterministic FFmpeg
motion graphics" claim was therefore false until the seed was
fixed: `visual_argv` now passes a fixed seed (42 unless the
recipe carries one) to the gradients source, and two renders
of the same recipe are byte-identical. Regression:
`visual-byte-deterministic` in `tests/test_p1006_assets.py`
(the existing `visual-argv-deterministic` check only compared
argument arrays, which were already equal — it could not catch
a random source inside FFmpeg).

### 1.7 Rebuilding into the same delivery directory failed verification

`build_delivery_package` collected the delivery directory's file
list before writing the manifest, without excluding the manifest
itself or `SHA256SUMS`. On a fresh directory that is harmless
(neither file exists yet); on a rebuild, the STALE manifest and
`SHA256SUMS` from the previous build were listed with stale
hashes, and verification then failed on the fresh files. Fixed by
excluding `delivery-manifest.json` and `SHA256SUMS` from the
manifest's file list (both are written after the list is
collected; a manifest cannot carry its own hash). `SHA256SUMS`
still covers every file including the manifest — it is written
last. Regression: `CF-P1-006-DEL-rebuild-same-dir` and
`CF-P1-006-DEL-rebuild-verifies` in `tests/test_p1006_delivery.py`.

### 1.8 Longest keyword overflowed the frame

With the text restored, the contact sheet showed shot 6's
keyword `CONSISTENCY FRAME` clipped at both frame edges: at
the default fontsize 96 the 17-character keyword is wider
than 1080 px. Fixed in the data, not the renderer: shot 6's
visual recipe now carries `"fontsize": 64` (the recipe field
already existed and flows through). Regression:
`visual-argv-recipe-fontsize` in `tests/test_p1006_assets.py`,
plus the contact-sheet inspection of the re-render.

### 1.9 Test-only defects (no production code changed)

Three asset-suite failures were wrong test fixtures, not module
defects: `make_record` overrides land on the record's top level,
but `license.class`, `privacy.classification` and
`privacy.transmit_to_provider` are nested fields, so the tests
were checking the wrong values. Fixed the fixtures to set the
nested fields. The assembly suite's first failed-render fixture
(truncating an MP4) failed at re-registration (ffprobe cannot
probe a file without its moov atom), not at render time; it was
replaced with an unwritable-output-path render failure. A
10-bit/8-bit pixel-format mismatch was tried first as the
failed-render case: FFmpeg auto-converts formats, so the render
succeeds and it is not a failure case. The end-to-end fixture
wrote a `production-analysis.json` without an `id`, so the
driver's project validation refused it on the test's first
ever run (`project.analysis is missing or carries no id`); the
fixture now carries `analysis-p1006-e2e-test`.

## 2. Decisions

### 2.1 Asset policy: no media binaries in the repo

The repo's `.gitignore` forbids generated media. No MP4, WAV or
PNG produced by this round is committed. Generated media lives
only in the delivery archive, with hashes. The narration WAVs
are NOT committed. The reference project in
`examples/p1006-vertical-explainer/` is source only (project
config, script, analysis, shot list, voice config, sound plan,
assembly config, README).

### 2.2 Render path: FFmpeg only

The single proven rendering path is FFmpeg. OpenMontage
production assembly stays NOT_TESTED (its earlier short demo
proves nothing about production assembly) and is not used; the
assembly config refuses `render_path: openmontage`. The
reference project's assembly config records this explicitly.

### 2.3 Visuals: locally generated FFmpeg motion graphics

The reference visuals are deterministic FFmpeg motion graphics
(animated gradients, moving accents, keyword text), labelled
`ffmpeg-local` / EXERCISED in every record. Deterministic is
now literal: the gradients source is seeded (fixed seed 42
unless a recipe carries one), so the same recipe renders
byte-identically. They are NOT AI image or video generation,
and no record claims otherwise. All eight P1-005 provider
contracts stay NOT_TESTED. Music, room tone and whoosh are
synthesized locally with FFmpeg and labelled `synthesized`.

### 2.4 Voice: real VoiceStudio/OmniVoice locally, non-commercial

The narration was generated with VoiceStudio/OmniVoice locally
(seed fixed, fixed instruct tag), line by line, each WAV
verified. Only `instruct` / `speed` / `seed` are forwarded.
Unsupported emotion/pitch/pace controls are refused, never
silently dropped. Commercial delivery is refused for this voice
(CC-BY-NC default weights).

### 2.5 The instruct tag `narrator` is not a valid OmniVoice tag

The reference project was first written with instruct tag
`narrator`. The live VoiceStudio backend rejects it with HTTP
400: `narrator` is not in OmniVoice's fixed English instruct
vocabulary. The reference project now uses
`middle-aged, moderate pitch` — a valid tag, neutral (no gender,
no accent), appropriate for an explainer narrator. The voice
config and README record it. The voice/audio unit tests keep
`narrator` as a fixture value only (stub adapter, never a live
call).

### 2.6 Voice language: `en-US` falls back to language-agnostic

The backend warns that language `en-US` is not a recognized
OmniVoice language ID (it wants `en` or `English`) and falls
back to language-agnostic mode. Generation still succeeds with
HTTP 200 and the WAVs verify. The project keeps `en-US` (the
correct project language tag); the adapter forwards it
unchanged. The warning is recorded here, not hidden. Mapping
BCP-47 tags to backend language IDs is P1-005 adapter work and
was not changed in this round.

### 2.7 CI render: same pipeline, tone narration, honest label

CI has no VoiceStudio model and no GPU, so it cannot generate
the narration. The CI render runs the same driver, the same
pipeline, geometry and QC — but synthesizes deterministic tone
narration at the planned line durations (recorded per line in
`voice-config.json` as `planned_duration_seconds`, measured
from the reference generation). The delivery manifest records
`voice_source: synthesized-tone` for the CI render and
`voicestudio-omnivoice` for the local delivery render. The CI
render is a real render, not a mock: every asset is generated
and every check runs for real.

### 2.8 Review package vs final delivery

The QC gate requires a named human reviewer for
`DELIVERY_READY`; `automated` is refused and a missing approval
blocks. A reference render ordered for review cannot honestly
claim that approval before any human has watched the video, so
the delivery module gained a narrow, additive review-package
path (`review_package=True` on `build_delivery_package`): it
builds the package only when technical QC passed, audio QC has
no critical finding, and the ONLY block is the missing editorial
approval. The manifest then records the true decision
(`BLOCKED`), the blocking reasons, and
`package_purpose: review` — it never claims `DELIVERY_READY`.
A technical failure or an audio critical finding still refuses,
even as a review package. Default behaviour is unchanged (the
existing refusal tests pass unmodified). The reference delivery
is a review package; the final manifest is rebuilt with
`DELIVERY_READY` once a named human reviewer approves the
visual QC evidence.

### 2.9 Deterministic synthesis: no `anoisesrc`

FFmpeg's `anoisesrc` has no seed option and produces different
bytes on every run, so it is never used as a source. Room tone
and whoosh noise are generated in-process with a fixed seed
(brown leaky-integrator, Kellet pink) and FFmpeg lavfi does the
filtering and envelopes. Determinism is asserted by
byte-identical re-synthesis tests.

### 2.10 Mid-render cancellation is not supported

The assembler runs FFmpeg as a subprocess to completion; there
is no cancel hook mid-render. A closed session refuses to START
assembly. This is recorded, not claimed otherwise. Resume is
stage-level: the Phase F checkpoint keyed by input hash
(`stage_checkpoint` / `stage_is_done`) — a completed stage with
unchanged inputs is done and is not re-run. A second assemble
call re-renders but must produce a valid MP4 with identical
probe facts (pinned by the assembly suite).

## 3. Honest limitations

- No video provider is VERIFIED/EXERCISED; no external live
  conformance run exists. All eight P1-005 provider contracts
  stay NOT_TESTED.
- OpenMontage production assembly stays NOT_TESTED.
- The media factory is NOT finished.
- The handbook PDF cross-check (P1-003 Addendum-01) is still
  open — the PDF never arrived.
- Kling/LTX result-URL hosts are unconfirmed; all hosts except
  Muse are NOT_TESTED.
- No AI visual-quality review is claimed: visual QC is a
  contact sheet, keyframes and measured reports, and human
  review is always required. The agent inspected the contact
  sheet and keyframes itself (see §1.4) — that inspection is
  recorded here, not as an editorial approval.
- The reference video's narration is a single narrator voice;
  no character voice consistency is exercised here (no
  registered character appears).
- The CI render's narration is tones, not speech: its voice
  track proves timing and mixing, not voice quality. The local
  delivery render is the one with real narration.
- The VoiceStudio backend is stopped when voice work ends; it
  was started only for the narration generation in this round.
