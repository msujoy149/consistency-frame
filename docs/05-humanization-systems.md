# Humanization Systems — Realism in Every Frame

These systems make every video feel human-made. A video that is
technically consistent but feels robotic has failed. Apply them to every
project.

## A note on figures and caveats

Some figures in this document are ranges to test per project, not fixed
values — for example the creative LUT strength and the 8–15% film-grain
range in item 30.11. Where the underlying research marks a figure as a
test range or an inference rather than a measured standard — for example
the voice-drift measurement approach in item 30.12, and per-model
reference limits in item 30.27 — that is noted in the item itself. Do not
treat a test range as a specification, and do not present an inference as
a verified measurement.

---

## 30.1 Performance-Driven Acting (optional lane)

When the user can act a line, record it on a phone or webcam and transfer
the real head, face, body, and hand motion onto the registered character
(performance / motion transfer). A real take contains micro-expressions,
timing, and weight that no prompt reliably invents.

- Tools in this lane include Runway Act-Two, Kling Motion Control 3.0,
  and Wan-Animate-2; the lane is defined by what it does (a real
  performance drives the pixels), not by any one tool.
- This lane is optional. When it is not available, use the script-driven
  emotion rules: the character performs like a human actor, with the
  emotion coming from the script and matching each line.
- A performance take is recorded per line or per beat, not per episode,
  so the acting stays specific to the dialogue.

## 30.2 Single-Pass Multi-Speaker Dialogue

Generate a whole conversation in one call (multi-speaker dialogue, up to
10 voices where the tool supports it — for example ElevenLabs Text to
Dialogue) instead of generating one line at a time and stitching.

- Real conversation has ~200 ms gaps, rare overlaps, and handoffs timed
  by the speakers. Stitched lines with clean, identical gaps sound
  edited, not spoken.
- One call keeps the timing, the pacing, and the turn-taking natural,
  because the model times the exchange as a conversation rather than as a
  list of isolated lines.
- Each character's voice profile is still fixed per character; the
  single-pass call uses the registered voices, it does not invent new
  ones.

## 30.3 Involuntary Micro-Motion

Every shot carries a micro-motion specification: blink cadence, tiny eye
movements (saccades), breathing and chest rise, head micro-drift, weight
shifts.

- Subtle motion beats dramatic motion. The motion must be small enough
  that the viewer feels it rather than notices it.
- QC check: "dead eyes / frozen face" is a defect — the eyes are the
  first thing viewers notice. A character who does not blink, breathe,
  or shift weight reads as a photograph, not a person.
- Micro-motion is specified per shot, not left to chance: a shot without
  a micro-motion plan is an incomplete shot.

## 30.4 Listener-Reaction Rule

When one character speaks, the other character must be visibly listening
— micro-nods, brow movement, breath, gaze — and must NOT move their mouth.

- Two mouths moving at once is the commonest AI dialogue failure.
- Listening is an active performance: the listener reacts to what is
  being said, in time with the speaker's words, without speaking.
- The speaker talks; the listener reacts. Never both at once.

## 30.5 Room Tone / Never-Silence + 4-Layer Sound

Continuous ambience under every scene; room tone in every interior.
Silence is a defect — even a quiet room has a low hum.

Four sound layers, in this order:

1. **Ambience / room tone** — the continuous sound of the place.
2. **Foley** — on visible beats, matched to the surface (stone, wood,
   grass).
3. **Dialogue** — the spoken lines.
4. **Music** — the scene's music, under the dialogue.

Reverb matches the room; a studio-clean voice outdoors is an instant
tell. A scene with no ambience layer is incomplete, however good the
picture is.

## 30.6 Non-Verbal Voice Layer

Every dialogue line may carry performance tags — sighs, laughs, whispers,
gasps, clearing the throat — plus breaths, hesitations (um/uh), stutters,
trailing off, and ellipsis pauses.

- Never deliver a clean, pause-free take. Real speech is messy; overly
  smooth synthetic speech is the audio uncanny valley.
- Non-verbal sounds are part of the dialogue, written into the line's
  performance, not added as an afterthought.
- The non-verbal layer follows the script's emotion for that line: a sad
  line sighs, a funny line laughs, a nervous line hesitates.

## 30.7 Eye / Gaze Continuity Across Cuts

Per-shot gaze target, eye-movement direction, pupil response to light,
and eye-line match across cuts — who looks at whom, and where.

- Gaze that does not follow head movement, or does not match the other
  character across a cut, breaks the scene even when the face is perfect.
- The gaze plan is part of the shot plan: for every shot, record who the
  character is looking at and in which direction.
- Pupil response follows the scene's light: a character in bright light
  does not have the wide pupils of a character in the dark.

## 30.8 Hands and Physics Avoidance + Repair

Hands and physics are the most recognizable artifacts. Avoid the failure,
and repair it when avoidance is not possible:

- Frame hands out of shot where the scene allows it.
- Give the hands a simple object to hold.
- Use slow motion for hand shots.
- Keep hand shots to short 3–5 second segments.
- Scrub hands frame by frame in QC.
- Repair warped hands with masked inpainting.
- Never generate pouring, grasping, or tying as a hero action — film it
  or cut around it.

A warped hand on screen is a defect that no amount of good acting
elsewhere can undo.

## 30.9 Anti-Plastic Skin

Name skin texture explicitly — visible pores, fine lines, freckles,
uneven tone, under-eye texture, peach fuzz, slight asymmetry. Use
side / skimming light to bring the texture out.

- Ban the words "flawless", "perfect", and "airbrushed" from prompts.
- Too-perfect skin is a primary tell: real skin has texture, and a face
  without it reads as plastic.
- Texture is specified in the prompt for every close-up, not assumed.

## 30.10 Editing Rhythm

J-cut (audio 4–12 frames early), L-cut (audio trailing), cut mid-movement,
cut on the phrase not on every beat, hard cut as the default.

- Stitched clips with simultaneous audio and video cuts feel stitched;
  J/L cuts are what make an edit feel continuous and human.
- Cut on action: the cut happens while something is moving, so the eye
  follows the movement across the cut instead of noticing the cut.
- Cut on the phrase, not on every beat: cutting on every beat is
  metronomic and mechanical.

## 30.11 Film-Finish Pipeline

After grading, in this fixed order:

1. Correct.
2. Creative LUT at reduced strength.
3. 35 mm grain (8–15%).
4. Light blur.

Highlight rolloff, halation, bloom, and gate weave are separate
adjustable ingredients.

- AI footage is too clean — ultra-sharp, plasticky, baked contrast. The
  film finish is what takes the digital edge off.
- A LUT alone on unstable footage makes drift more visible, so
  foundations come first: fix consistency and stability before applying
  the finish.
- The LUT strength and the 8–15% grain range are ranges to test per
  project, not fixed values.

## 30.12 Voice-Drift Measurement

The audio twin of face-drift measurement (see item 6 in "Extended
Production Systems"). Measure speaker-embedding similarity per line and
per episode, plus a prosody fingerprint (pace and pitch range) per
character.

- A cloned voice can drift in timbre and pace across episodes unnoticed
  — measure it, and regenerate below threshold.
- The measurement approach (speaker-embedding similarity plus a prosody
  fingerprint) is an inference from the research, not a verified vendor
  standard: the principle is established (measure the voice the way the
  face is measured), but the specific thresholds and tooling are to be
  validated per project.
- Voice-drift scores are recorded in the provenance log next to the
  face-drift scores.

## 30.13 Temporal-Artifact QC

Scrub every take for texture swimming, flicker, object drift, cadence
stutter, missing motion blur, and morphing. Reject or regenerate; do not
patch in grading.

- The problem lives in time, not resolution — a 4K clip can look faker
  than 720p phone footage.
- Temporal artifacts are checked by watching the take in motion, frame
  by frame where needed, not by looking at still frames.
- A take that fails temporal QC is regenerated or cut around, never
  shipped with the artifact hidden under grading.

## 30.14 Camera Imperfection

Handheld breathing and micro-drift, focus breathing, focus pulls, subtle
lens flare, natural motion blur, and a 24 fps shutter feel, plus
reframing drift.

- A perfectly locked, perfectly smooth camera reads as CGI; real cameras
  breathe and hunt focus.
- Imperfection is subtle and deliberate: the camera moves like a human
  operator's hands, not like a machine on rails.
- The imperfection level is set per scene in the shot plan, so a calm
  dialogue scene and a chase scene do not get the same camera treatment.

## 30.15 Lighting-Continuity Lock

Shadow direction, colour temperature, and light-source position are fixed
per scene and locked across every shot in that scene.

- Grading follows time of day (see the script-driven realism and colour
  grading rules in "Additional Systems"); this lock fixes where the light
  comes from in every shot.
- A shadow that points left in one shot and right in the next is a
  continuity failure, however good each shot looks alone.
- The lock is recorded in the scene plan and checked in QC.

## 30.16 Background Life

Secondary motion in every shot — a curtain, leaves, distant people,
steam, dust in light — at low amplitude.

- An empty, overly smooth background is a tell: real places are never
  perfectly still.
- Background motion is secondary and low-amplitude; it must never
  compete with the characters.
- Background life is planned per shot, at the same time as the character
  action, so the background is alive from the first frame rather than
  added later.

## 30.17 Cloth / Hair Physics

Hair and fabric follow wind, gravity, and momentum; they never float.

- Keep hair and cloth motion small in dialogue shots — a small, correct
  movement reads as real; a large, wrong one reads as a physics failure.
- Cloth and hair respond to the same wind, gravity, and movement as the
  character and the scene around them.
- A scarf that hangs still in a gale, or hair that floats in still air,
  is a defect.

## 30.18 Distance and Space in Voice

Voice level, reverb, and muffling change with camera distance and room:
close is dry and intimate, far is quieter with more reverb; off-screen
voices are muffled.

- A crisp studio voice in outdoor footage is a named tell.
- The voice treatment follows the shot: when the camera moves closer, the
  voice gets closer; when the character walks away, the voice recedes.
- Distance treatment is part of the sound plan for the scene, not a
  mastering decision.

## 30.19 Sound Spotting Sheet

Before generating sound, write a spotting sheet per shot — timecode,
sound class, sync or not, distance.

- Ambience loops crossfade 0.5–1 s and change only at cuts.
- Ad-hoc sound-effect generation produces mismatched, unsynced sound;
  the spotting sheet is what keeps every sound deliberate and placed.
- The sheet is written before sound generation, and the generated sound
  is checked against it in QC.

## 30.20 AI Disclosure and Provenance Pack

Per-video disclosure checklist: the platform's AI-use disclosure (for
example YouTube Studio), the EU AI Act deployer disclosure (Article 50)
where it applies, and C2PA Content Credentials / SynthID where the tool
supports it, with on-screen label wording when required.

- Follow the platform's rules; never hide a required disclosure.
- The pack is assembled per video at delivery time, alongside the
  distribution package.
- This is a checklist, not legal advice. When a disclosure question is a
  legal question, the user should get legal advice; the system only makes
  sure the checklist is completed.

## 30.21 Detector Self-QC

Run finished episodes through provenance-first checks (C2PA Verify,
SynthID Detector) and a classifier ensemble as a triage score, never a
verdict.

- Detectors are used to find your own tells before viewers do.
- A detector score is triage: it tells you where to look. It is never a
  verdict that a video is "real" or "fake", and it never replaces the
  human blind-test gate (item 30.28) or the episode QC checklist.
- Record detector results in the provenance log with the episode.

## 30.22 Audio Description Track

Beyond captions, provide a narration of visual action in dialogue pauses
(WCAG 2.1 Success Criterion 1.2.5), plus a descriptive transcript, so
blind and low-vision viewers are not left out.

- The description narrates what is visible — actions, expressions,
  scene changes — in the gaps between dialogue, without talking over
  the dialogue.
- The descriptive transcript is a text version of the same description,
  kept with the episode's assets.
- Audio description is produced per episode on request, like captions:
  it is part of the delivery package, not baked in by default.

## 30.23 Voice Ageing / State Variants

Per-character voice variants for age, illness, whisper/shout, tiredness,
cold — the voice parallel of visual ageing variants (see item 8 in
"Extended Production Systems").

- A variant is a named, recorded version of the same character's voice,
  with the change listed, so the voice stays recognizable while the state
  changes.
- Variants are used only when the story calls for them, and the change is
  recorded in the continuity tracker.
- The character's base voice never changes silently; ageing or illness is
  a deliberate variant, not drift.

## 30.24 Code-Switching and Dialect Rule

Handle mid-sentence language switching (for example Bengali↔English) and
regional accent explicitly.

- Test per language and per dialect; do not assume a multilingual model
  is equally good in all of them.
- Bengali and code-switched lines especially need a separate listening
  test — a line must be heard and judged in each language it uses, not
  judged once for the whole video.
- A character's dialect and code-switching habits are part of their voice
  profile and stay consistent across episodes.

## 30.25 Model-Version Pinning + Golden Regression

Pin the exact model version per project. Re-test a golden set of shots
whenever a provider updates a model. Keep a fallback model per lane.

- Providers silently update or shut down models; unpinned pipelines
  drift without anyone changing a prompt.
- The golden set is a fixed set of reference shots, re-generated and
  compared after every model change, so a regression is caught before it
  reaches an episode.
- The pinned versions are recorded in the provenance log for every shot.

## 30.26 Re-Anchor Every ~8–16 s

Re-inject reference images and first-frame anchoring every ~8–16 seconds
and at every scene change, because consistency degrades sharply past
~16 seconds and with time since last appearance.

- Long takes are built as a chain of anchored segments, not as one
  unanchored run.
- Every scene change is a re-anchor point, even if the previous segment
  was short.
- Re-anchoring is what makes the clip-boundary seam rule (see item 5 in
  "Extended Production Systems") work in practice.

## 30.27 Reference-Count Strategy per Model

Document per-model reference limits, and use a multi-angle reference set
(front, three-quarter, profile, expression) per character.

- A single front photo is the weakest reference set.
- Per-model reference limits (how many reference images a given model
  accepts or uses effectively) are documented per model in the project
  notes; the research notes that these limits vary by model and are
  subject to change, so they are recorded from the vendor's current
  documentation and re-checked when a model is updated, not treated as
  permanent constants.
- The reference set for a character is the model sheet (see item 3 in
  "Extended Production Systems"), and the model sheet is what is
  re-injected at each re-anchor.

## 30.28 Human Blind-Test Gate

Before release, show episodes to viewers who do not know it is AI and
record "what felt off" in their own words.

- Vendor scores saturate and miss long-form failures; unaided human
  "off" notes are the only signal that tracks the uncanny valley.
- The gate is a release gate: an episode is not released until the
  blind test has been run and its findings addressed or recorded.
- Blind-test notes are recorded with the episode, in the viewers' own
  words, not paraphrased into a score.

## 30.29 Mouth-Interior QC in Lip-Sync

Check mouth interior sharpness, teeth stability, and tongue on close-ups.

- Prefer diffusion-class lip-sync for hero shots and a faster model for
  speed where the shot allows it.
- Blurry teeth and lips are where cheap lip-sync fails, and they are
  most visible in close-up — which is exactly where the audience looks.
- Mouth-interior QC is part of the lip-sync check in the episode QC
  checklist, with its own line so it is not skipped.

## 30.30 Wardrobe Wear and Continuity Detail

Wrinkles, stains, wear, fit, and layering persist across shots; fabric
creases change with pose, not randomly per shot.

- A crease that appears, vanishes, and reappears between shots is a
  continuity failure.
- Wear is part of the wardrobe registry (see item 4 in "Extended
  Production Systems"): the state of each garment is recorded, not just
  its identity.
- New wear appears only when the story causes it — a stain after a spill,
  a tear after a fall — and is then recorded as the garment's new state.

## 30.31 Imperfection Budget

Deliberate, counted imperfections per shot — asymmetry, flyaway hairs,
dust, a crooked prop — instead of "add imperfections" as a vague prompt
line.

- A budget makes it checkable in QC: the shot plan lists the imperfections
  for that shot, and QC checks that they are present and that no
  unplanned defect has appeared in their place.
- Imperfections are small and deliberate. A counted imperfection is a
  realism choice; an uncounted defect is a failure.
- The budget is set per shot, not per episode, so each shot gets the
  imperfections that fit its framing and distance.

## 30.32 Music-Ducking / Dialogue-First Mix

Music and sound effects duck under dialogue and never compete; dialogue
carries ~60% of attention.

- Mastering sets loudness (see item 14 in "Extended Production Systems");
  this sets the balance that keeps dialogue intelligible and human.
- Ducking is automatic in the mix: when dialogue starts, music and
  effects drop; when dialogue ends, they return.
- A mix where music competes with dialogue fails QC, however good the
  music is.

## 30.33 Failure and Fallback Playbook

For each artifact type, document what to do when a shot fails —
regenerate, inpaint, re-anchor, film it, or cut around it.

- Never silently ship a failed shot.
- Never repeat the same failed generation unchanged: a failed generation
  is information — change the prompt, the seed, the reference, or the
  approach, and record what was changed.
- The playbook is a living document: when a new failure mode appears, its
  fallback is added to the playbook.

## 30.34 Real-Person Safeguards

For videos built from a real adult's photo or voice: the likeness is used
only with that person's consent, for the agreed use, and the person can
withdraw it; never make a real person say or do something they never did
without a clear label.

- Consent is recorded (who gave it, for what use, when) under the
  rights, consent, and provenance records (see item 17 in "Extended
  Production Systems").
- Withdrawal ends the use: when consent is withdrawn, the likeness is no
  longer used, and the character record reflects that.
- Child characters follow the child-safety rules (see item 13 in
  "Extended Production Systems"), which are absolute.

## 30.35 Realism Budget

Track which humanizing steps (performance take, extra takes, grain pass,
foley) are worth their credits and minutes per shot type.

- Spend realism where the viewer will feel it — faces, voices, hands,
  and sound — not everywhere equally.
- The budget is a planning tool: before an episode, decide where the
  realism spend goes, and record the spend alongside the cost tracking
  (see item 10 in "Extended Production Systems").
- A step that costs credits and delivers no visible or audible difference
  is spend that should move to a shot where it will be felt.

## 30.36 Cinematic Backgrounds

The background is what the eye rests on most in a video, so every
background is cinematic and realistic — detailed, layered, with depth,
atmosphere, and life, matching the scene's place, time, and light.

- Never an empty, flat, or generic background. A background that looks
  painted or empty breaks the scene even when the character is perfect.
- Every background is described in the scene plan with the same care as
  the character action: what is in the foreground, midground, and
  background; what the light is doing; what is moving.
- Every video is cinematic. A background that is merely "a room" or "a
  street" is an unfinished background.
