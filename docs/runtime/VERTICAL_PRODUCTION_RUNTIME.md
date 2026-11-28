# Vertical production runtime (CF-WO-P1-006)

The vertical production runtime is the eighth production runtime
component of Consistency Frame, built on the P1-001 trusted local
session, the P1-004 production orchestrator and task compiler, the
P1-004-R1 persistent production store, the P1-004-R1-F1 unified
identity workflow, and the P1-005 media execution runtime. It
answers the question the earlier runtimes left open: *the packets
are compiled and the execution adapters exist — how does one
complete production run, from an approved script to a QC'd
playable video with a delivery manifest?*

P1-005 proved a single media execution end to end (one FFmpeg
render, one VoiceStudio generation, one OpenMontage demo) but
never connected the stages: project validation, visual assets,
voice, sound design, canonical timeline, assembly, QC and
delivery lived in separate modules with no shared job. This
runtime connects them into one reproducible workflow — the
reference driver `scripts/run-p1006-reference-render.py` runs it
for the example project — without duplicating anything that
already exists: job state rides on the production job record and
is persisted by the existing production store; media execution
still goes through the P1-005 adapters and state machine; the
timeline contract is still the P1-004 `editor_neutral_v1`
manifest. There is no second job database, and a compiled packet
is still never proof of execution.

## What it guarantees

1. **One complete project model.** `runtime/vertical_production.py`
   connects script, analysis, identities, visual assets, voice
   assets, music, SFX, timeline, output profile, execution state,
   QC and delivery artifacts into one validated project. Every
   material decision carries provenance (`EXPLICIT_FROM_USER`,
   `FROM_APPROVED_PROJECT_CANON`, `INFERRED_FOR_PRODUCTION`,
   `NEEDS_USER_DECISION`). A project must not enter execution
   while required user decisions are unresolved, and inferred
   choices never become canon.
2. **Dialogue is verbatim.** Voice lines must match the script
   lines exactly — same ids, same text, same order — unless a
   rewrite was explicitly requested. A tampered line is refused
   at validation, not discovered at QC.
3. **A strict linear state machine.** `INTAKE → PROJECT_VALIDATED
   → ASSETS_PENDING → ASSETS_READY → VOICE_PENDING → VOICE_READY
   → SOUND_PENDING → SOUND_READY → TIMELINE_READY →
   ASSEMBLY_RUNNING → ASSEMBLY_COMPLETED → QC_RUNNING → QC_PASSED
   → DELIVERY_READY → DELIVERED`, plus `FAILED`, `CANCELLED`,
   `NEEDS_USER_DECISION` and `BLOCKED`. Each state transitions
   only from its immediate predecessor (plus an idempotent
   re-run from the next state). `FAILED` requires a failure
   `{code, message, recovery}` with a P1-005 `FAILURE_CODES`
   code; `BLOCKED` resumes only to the previous state;
   terminal states never transition.
4. **Idempotent stages.** `stage_checkpoint` records a stage, its
   input SHA-256 and its outputs on the project;
   `stage_is_done` answers whether that stage is done for those
   inputs. A completed stage with unchanged inputs is not
   re-run. Checkpoints persist through the production store.
5. **One proven rendering path.** `runtime/production_timeline.py`
   builds the canonical timeline (project profile, duration, fps,
   W/H, video/audio tracks, shot/scene ids, clip refs, in/out,
   positions, transitions, gain, fades, layer order, asset ids,
   identity refs, provenance) and assembles it with FFmpeg only.
   The assembler validates every source asset, resolves every
   path, verifies hashes, validates durations/trims/profile,
   rejects invalid overlaps, handles gaps/transitions, syncs
   voice/SFX, renders deterministically, and produces execution
   and delivery records. OpenMontage production assembly is
   NOT_TESTED and is refused here.
6. **Geometry from the profile, never hardcoded.** The output
   profile (9:16, 1080x1920, 30 FPS, H.264/AAC for the reference
   project) is explicit and validated; the renderer never invents
   geometry independently of it. The rendered output is probed
   and must match the profile exactly (rational frame-rate
   comparison), or assembly fails.
7. **Voice is real and verified.** `runtime/production_voice.py`
   maps dialogue to voice assets line by line, generates with the
   VoiceStudio adapter (only `instruct` / `speed` / `seed`
   forwarded; unsupported controls refused), retries exactly once
   on failure with diagnostics recorded, then stops — never fake
   audio. `verify_voice_assets` checks coverage, decodability,
   duration, sample rate, channels, non-emptiness and hash.
8. **Sound is mixed, not just placed.** `runtime/production_audio.py`
   validates mix inputs (dialogue coverage exactly once per shot,
   mandatory music/SFX, intentional silences recorded with a
   reason, no clip past the timeline end), synthesizes the music
   bed, room tone and whoosh deterministically (fixed-seed noise
   generated in-process; FFmpeg's `anoisesrc` is never used),
   builds the voice track, and mixes with voice priority, music
   ducked beneath speech (sidechain compression), fades, and
   exactly one measured volume correction when the peak exceeds
   the profile's true-peak target. Loudness and true peak come
   from `ebur128` when available, and are honestly `None` when
   the filter is not.
9. **QC blocks delivery.** `runtime/production_qc.py` runs
   technical QC (ffprobe: existence, MP4, streams, exact
   1080x1920, 9:16, 30 FPS rational, 30–60 s, H.264/AAC, full
   decode, blackdetect/freeze detection — intentional silence and
   black are recorded, never flagged), visual QC (contact sheet,
   keyframes, shot summary, black-frame and aspect/crop reports;
   human review always required, editorial approval always starts
   as `None`) and audio QC (loudness, true peak, clipping,
   silence, dialogue duration, track alignment, asset hashes).
   `qc_decision` returns `DELIVERY_READY` only when technical QC
   passes AND audio QC has no critical finding AND a named human
   reviewer approved; `automated` is refused and a missing
   approval blocks.
10. **Delivery is a package, not a file.**
    `runtime/production_delivery.py` builds the delivery package
    (final MP4 copied, never moved; project config, script,
    analysis, canonical timeline manifest, asset manifest, voice
    mapping, sound plan, execution summary, technical/visual/audio
    QC reports, SHA-256 checksums, delivery manifest) and
    verifies it independently (re-hash, re-probe, SHA256SUMS).
    A review package (`review_package=True`) is the same package
    built while the human editorial approval is still missing:
    it is allowed only when technical QC passed, audio QC has no
    critical finding, and the ONLY block is the missing approval;
    its manifest records the true decision (`BLOCKED`), the
    blocking reasons, and `package_purpose: review`, and never
    claims `DELIVERY_READY`.

## Modules

- `runtime/vertical_production.py` — Phase A project model,
  validation gate, state machine, checkpoints.
- `runtime/production_assets.py` — Phase B asset records,
  registration/resolution/verification, local FFmpeg visual
  generation.
- `runtime/production_voice.py` — Phase C dialogue-to-voice
  mapping, generation, verification, voice mapping report.
- `runtime/production_audio.py` — Phase D sound design, mixing,
  measurement, audio QC findings.
- `runtime/production_timeline.py` — Phase E canonical timeline
  and FFmpeg assembly.
- `runtime/production_qc.py` — Phase G technical, visual and
  audio QC, delivery decision.
- `runtime/production_delivery.py` — Phase H delivery package,
  manifest, checksums, independent verification.
- `scripts/run-p1006-reference-render.py` — the reference driver:
  intake → QC → delivery for
  `examples/p1006-vertical-explainer`. `--voice-dir` supplies
  real VoiceStudio WAVs; without it, deterministic tone
  narration is synthesized (the CI render). `--editorial-approval
  "<name>"` builds a final delivery package; without it, a
  review package.

## Reference project

`examples/p1006-vertical-explainer/` (source only, no binaries):
a narrator-only, original, non-copyrighted explainer about how
Consistency Frame keeps one character the same across scenes —
six lines, six shots, 9:16, 1080x1920, 30 FPS, H.264/AAC, MP4,
stereo 48 kHz, 30–60 s. Narration: VoiceStudio/OmniVoice,
seed 42, instruct `middle-aged, moderate pitch` (a valid
OmniVoice tag; `narrator` is not one — see the corrections
record). Visuals: deterministic FFmpeg motion graphics (the gradients
source is seeded — fixed seed 42 unless a recipe carries one —
so the same recipe renders byte-identically).
Music/room tone/SFX: synthesized locally. The CI render uses
tone narration at the planned line durations and records
`voice_source: synthesized-tone`; the local delivery render
records `voicestudio-omnivoice`.

## Tests

- `tests/test_p1006_project.py` — project validation, provenance,
  script preservation, identity consistency, missing decisions,
  invalid profiles, state machine, checkpoints.
- `tests/test_p1006_assets.py` — registration, resolution,
  missing/corrupt/wrong-hash assets, invalid paths, private
  policy, commercial restriction, visual generation (every
  recipe kind, with a midpoint-frame keyword-visibility check).
- `tests/test_p1006_voice.py` — coverage, identity mapping,
  missing output, invalid audio, duplicate dialogue, unsupported
  controls.
- `tests/test_p1006_audio.py` — ordering, gain, ducking, timing,
  missing music/SFX, clipping, silence.
- `tests/test_p1006_timeline.py` — canonical generation,
  multi-clip/track, transitions, trims, overlap/gap, 9:16,
  wrong-geometry rejection.
- `tests/test_p1006_assembly.py` — successful render (real MP4),
  invalid source, failed render, resume, idempotency,
  cancellation (closed session refuses; mid-render cancellation
  is not supported).
- `tests/test_p1006_delivery.py` — QC (technical/visual/audio/
  decision) and delivery (manifest, hash, size, probe agreement,
  missing artifact, QC blocking, review package).
- `tests/test_p1006_e2e.py` — one complete reproducible job
  intake → QC → delivery through the real driver, producing an
  actual playable video (two-shot cut, tone narration).

## Honest limitations

No video provider is VERIFIED/EXERCISED; no external live
conformance run exists. OpenMontage production assembly stays
NOT_TESTED. The media factory is not finished. No AI
visual-quality review is claimed — visual QC is evidence for a
human reviewer. The CI render's narration is tones, not speech.
See `docs/implementation/CF-WO-P1-006-corrections.md` for the
full record.
