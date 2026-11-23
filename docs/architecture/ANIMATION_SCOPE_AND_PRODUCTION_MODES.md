# Animation Scope and Production Modes

**Status:** P0-006 canonical reference (work order CF-WO-P0-006,
branch `feat/cf-p0-safe-foundations`, 2026-11-22).
**Authority:** this document is the authoritative reference for what
"animation" means in Consistency Frame and how a production is
described, routed, and checked. Where an older document disagrees
with this one about scope — for example by calling the product
cartoon-only, or by saying a realistic-person video is "not
animation" — this document governs, and the older wording is to be
corrected, not followed. Skill files themselves are not rewritten by
this document; routing, schema, and registry changes that implement
it live in the files named in §10–§11 and are owned by their
respective P0-006 parts.
**Scope of this document:** P0 contracts, definitions, and routing
rules only. It does not execute anything. The runtime that executes
these contracts is P1 work (§15).

## Canonical vocabularies

The strings below are fixed. Use them exactly as written, everywhere
— in this document, in schemas, in routing data, in skills, and in
production records. Never invent a synonym, never shorten a value,
and never collapse the dimensions into one giant `animation_type`
enum. The dimensions are independent: a production picks one value
(or, for motion method, several values) from each dimension, and the
combination is what describes it.

### VISUAL_STYLE

`flat-2d-vector`, `hand-drawn-2d`, `illustrated-2d`, `anime`,
`cartoon-2d`, `stylized-3d`, `semi-realistic-3d`,
`photorealistic-3d-cgi`, `photorealistic-digital-human`,
`photorealistic-digital-animal-creature`, `mixed`,
`captured-live-action`

`captured-live-action` is the as-captured look of real footage —
the visual style of a production whose images were captured by a
camera, not rendered or generated. It is what makes unmanipulated
captured footage (for example a real animal, filmed) expressible
as a production profile at all.

### PRODUCTION_MEDIUM

`2d-drawn-vector`, `3d-cgi-rigged`, `ai-digital-human`,
`ai-digital-creature`, `live-action-footage`, `hybrid-live-action-cgi`

### SOURCE_MEDIA

`script-only`, `reference-image`, `reference-video`,
`captured-footage`, `generated-image`, `generated-video`, `mixed`

### MOTION_METHOD (array — a production may use several)

`rig-2d-keyframe`, `rig-3d-keyframe`, `ai-image-to-video`,
`ai-video-to-video`, `motion-capture`, `performance-transfer`,
`face-animation`, `body-animation`, `pose-gesture-transfer`,
`lip-sync-phoneme-viseme`, `creature-articulation`,
`rotoscoping-compositing`, `captured-motion`

`captured-motion` is motion as captured by the camera — the method
for unmanipulated captured footage, where no generation method
applies. A production whose motion is captured, not generated,
lists `captured-motion` and nothing else.

### SUBJECT_KIND

`human`, `digital-human`, `real-animal`, `cgi-animal`,
`fictional-creature`, `anthropomorphic`, `mixed`, `non-character`

### INTERACTION_PATTERN

`single-performance`, `two-person-conversation`,
`multi-person-conversation`, `human-animal`, `human-creature`,
`multiple-animals-creatures`, `group-scene`, `silent-reaction`,
`physical-contact-object`

### ARTICULATION_TARGET

`human-mouth-lips`, `bird-beak`, `animal-muzzle`,
`creature-jaw-mandibles`, `other`

A value of `mixed` (where the vocabulary allows it) means the
production genuinely combines more than one value of that dimension
in different shots or subjects — it is never a shortcut for "not
decided". If the style, medium, or subject is not decided yet, record
that as undecided in the production record; do not write `mixed` to
hide the gap.

## 1. Product purpose and animation-first positioning

Consistency Frame is an animation-first, style-agnostic AI video
production Brain / orchestrator. It directs consistent, expressive,
physically believable animated videos across 2D, 3D, stylized,
semi-realistic, and photorealistic styles, for humans, digital
humans, animals, creatures, multi-character interactions,
image-to-video, video-to-video, and hybrid live-action/VFX work.

"Animation-first" means: movement, performance, and acting are the
product's centre, not an afterthought. A video in which a character
does not move, does not speak with a moving mouth, or does not react
is not a finished Consistency Frame video — it is a still with sound
over it, and the QC gates in §13 reject it as such. "Style-agnostic"
means: no single visual style is the product. A flat 2D explainer, a
stylized 3D short, and a photorealistic digital-human video are all
first-class productions of the same system, described with the same
dimensions (§3–§6), routed through the same composable model (§10),
and checked against the same gates (§13).

Consistency Frame is NOT a standalone video-generation server, API
backend, cloud database, hosting platform, VoiceStudio/OpenMontage
replacement, or cartoon-only toolkit. It is the Brain that directs
the work; the companions (VoiceStudio for voice, OpenMontage for
video assembly) and the providers they call do the execution. See
§15 for what P0 documents versus what P1 will execute.

## 2. What animation means within Consistency Frame

Animation here is NOT cartoon-only. It covers all of the following,
and a production may combine several of them:

- **2D animation** — flat vector, hand-drawn, illustrated, anime,
  and cartoon 2D, whether drawn frame by frame, rigged and
  keyframed, or generated.
- **Stylized 3D** — stylized CGI with designed proportions,
  squash-and-stretch, and non-photoreal proportions.
- **Semi-realistic 3D** — 3D CGI that aims at believable human and
  animal form and movement without claiming to be footage.
- **Photorealistic CGI** — 3D CGI that aims at the closest
  achievable match to real appearance and motion.
- **Photorealistic digital humans** — a generated, moving, speaking
  person built from a real person's photo (or generated reference),
  with natural movement, speech, and lip-sync. This IS animation:
  the person on screen is a generated digital human, not footage of
  a real shoot. The older wording "Realism, not animation" and "This
  is not 2D/3D animation" is withdrawn. What remains true, and is
  kept, is the distinction that matters: a digital human is not
  live-action footage, and its realism is verified shot by shot
  against the approved reference with a human-review gate — no
  absolute percentage is guaranteed.
- **Photorealistic digital animals and creatures** — generated
  animals and fictional creatures that move, act, and (where the
  subject allows) vocalise, with articulation matched to their own
  anatomy (§7).
- **Image-to-video** — a still reference image brought to motion:
  performance, camera movement, and lip-sync generated from the
  image.
- **Video-to-video** — an existing video transformed into a new
  video (restyle, regeneration, performance transfer) that preserves
  the reference's core story and direction while producing new,
  original footage.
- **Hybrid live-action/VFX** — real captured footage combined with
  generated humans, creatures, animals, or environments (§9).
- **Animals, creatures, and human–animal / human–creature
  interaction** — as subjects in their own right, not as props.
- **Multi-character dialogue and interaction** — two or more
  characters speaking, listening, reacting, and sharing space (§8).

What animation is not: a slideshow of stills with a voiceover, a
single still with a slow zoom, or a talking head whose mouth does
not move. Those are failure modes the QC gates catch, not
productions this system claims as finished work.

## 3. Visual style versus production medium

Visual style and production medium are separate dimensions. They
are chosen independently, and neither one implies the other.

- **Visual style** (`VISUAL_STYLE`) is what the finished video
  looks like: its drawing or rendering style, proportions, line,
  colour, and surface treatment. It is locked first for a project
  and held in every shot (style lock), and it is project-scoped:
  the same character may appear in different styles in different
  projects, but never in two styles inside one project unless the
  story explicitly requires a transformation (§2 of the
  cinematic-power skill) and the change is registered.
- **Production medium** (`PRODUCTION_MEDIUM`) is how the moving
  image is made: drawn vector and rigged 2D, rigged 3D CGI,
  AI-generated digital human, AI-generated digital creature,
  captured live-action footage, or a hybrid of live action and CGI.

Examples of lawful combinations (not an exhaustive list):

| Visual style | Production medium | What it is |
| --- | --- | --- |
| `flat-2d-vector` | `2d-drawn-vector` | Flat 2D explainer (one optional profile, §3.1) |
| `anime` | `2d-drawn-vector` | Anime-style 2D short |
| `stylized-3d` | `3d-cgi-rigged` | Stylized 3D short |
| `semi-realistic-3d` | `3d-cgi-rigged` | Semi-realistic 3D drama |
| `photorealistic-3d-cgi` | `3d-cgi-rigged` | Photorealistic CGI |
| `photorealistic-digital-human` | `ai-digital-human` | Realistic moving/speaking person from a photo |
| `photorealistic-digital-animal-creature` | `ai-digital-creature` | Generated realistic animal or creature |
| `captured-live-action` | `live-action-footage` | Unmanipulated captured footage (real animal / real person, as filmed) |
| `mixed` | `hybrid-live-action-cgi` | Live footage with CG creatures / set extension |

A combination is invalid only when the two dimensions genuinely
contradict each other for the same shot (for example, claiming a
shot is both drawn 2D vector and captured live-action footage).
Style and medium do not contradict each other merely because they
come from different skills: that is exactly what the composable
routing model in §10 is for.

### 3.1 The 2D explainer is one optional profile

The flat 2D cartoon / stick-figure explainer (flat 2D vector, thick
black outlines, flat colour fills, small palette, one idea per scene,
almost no on-screen text) is ONE optional profile of the system —
`VISUAL_STYLE: flat-2d-vector` with `PRODUCTION_MEDIUM:
2d-drawn-vector` and a teaching purpose. It is not the product's
animation model, and describing the product as a 2D explainer tool,
or describing explainer rules as if they applied to every video,
is wrong. The same character registry, voice profiles, performance
direction, cinematography, and QC apply across profiles; only the
profile's own style rules (line, palette, metaphor system, scene
structure) are profile-specific.

## 4. Source-media types

`SOURCE_MEDIA` records what the production starts from. It is
independent of style and medium: the same script can be produced
from a reference image, from a reference video, or from nothing but
the script.

- `script-only` — the script (and any direction in it) is the sole
  source. Nothing is invented beyond the script except the light
  details the repo explicitly delegates (§1, command authority).
- `reference-image` — one or more still images: character
  references, a location photo, a storyboard frame. A registered
  character's reference images are reference assets (§C4); using
  one does not change the character's identity.
- `reference-video` — a video supplied by the user as a reference.
  Optional, never required (§C1). When supplied, it is analysed
  first and a NEW original video is produced from it; the output is
  never a frame-for-frame copy.
- `captured-footage` — footage captured with a camera (live-action
  plates, a real performance driving video, real-animal footage).
- `generated-image` — an AI-generated still used as a source for
  motion or as a scene element.
- `generated-video` — an AI-generated clip used as a source for
  further transformation (video-to-video) or assembly.
- `mixed` — more than one of the above in the same production
  (for example, a script plus a character reference image plus a
  captured live-action plate). Record which source feeds which shot;
  do not leave the mix unspecified.

Provenance is recorded per source asset: who supplied it, when, and
under what rights (§12). A source asset is not a permission slip:
supplying a photo or video does not by itself authorise permanent
registration, commercial use, or use of a real person's likeness or
voice.

## 5. Motion-generation methods

`MOTION_METHOD` is an array. A production lists every method it
uses, per shot where the method differs between shots. The methods
are:

- `rig-2d-keyframe` — a rigged 2D character posed and keyframed.
- `rig-3d-keyframe` — a rigged 3D character posed and keyframed.
- `ai-image-to-video` — motion generated from a still image.
- `ai-video-to-video` — motion / appearance transformed from an
  existing video.
- `motion-capture` — movement captured from a real performer.
- `performance-transfer` — a real human performance (phone/webcam)
  driving the pixels of a generated character.
- `face-animation` — facial performance: expressions,
  micro-expressions, eye movement, gaze, blinking, breathing.
- `body-animation` — body performance: posture, gesture, walk,
  weight, physical behaviour.
- `pose-gesture-transfer` — a pose or gesture sequence transferred
  onto a character.
- `lip-sync-phoneme-viseme` — mouth movement matched to the
  phonemes / visemes of the spoken audio, in the language actually
  spoken. A talking character with a still mouth is a defect, never
  a delivery — for humans, animals, and creatures alike, each with
  its own articulation target (§7).
- `creature-articulation` — movement of a non-human mouth, jaw,
  beak, or muzzle, matched to the creature's anatomy and to its
  vocalisation, if any.
- `rotoscoping-compositing` — traced / composited motion, used for
  hybrid and VFX integration.
- `captured-motion` — motion as captured by the camera; the method
  for unmanipulated captured footage, where no generation method
  applies.

Method honesty: a production records the methods actually used.
"AI animation" without a method is not a record. A method is never
marked exercised or production-verified without actual evidence
(a run, a render, a check) — see §14.

## 6. Character and subject categories

`SUBJECT_KIND` records what kind of subject appears in a shot or a
production. It is per subject, not per production: one production
may contain a `human`, a `cgi-animal`, and a `fictional-creature`,
and each is recorded separately with its own identity, references,
voice (if any), and articulation target.

- `human` — a real person appearing as themselves in captured
  footage (live action). A real person's face and voice may be used
  only with that person's permission (§12).
- `digital-human` — a generated person: from a real person's photo
  (with permission), or AI-generated from an approved reference.
  The face, structure, hands, and feet are fixed from the approved
  reference; only movement and speech are added.
- `real-animal` — a real animal in captured footage. It does what it
  does; performance is made in the edit, and CG touch-up is used
  only where the animal cannot perform, preserving its real body.
  A real animal is never automatically given fictional dialogue or
  a speaking voice — a speaking animal is a `cgi-animal` (or
  `anthropomorphic`) subject, not captured footage.
- `cgi-animal` — a generated animal, rigged or AI-generated, whose
  movement follows the animal's real body and anatomy.
- `fictional-creature` — a generated creature with no real-world
  counterpart (monster, elemental force, invented being). Movement
  follows the creature's designed body; menace may live in
  stillness, and an elemental force may itself act as a character.
- `anthropomorphic` — an animal or creature given human-like
  posture, speech, or behaviour (a talking animal, a creature that
  gestures). Record both the base anatomy and the human-like
  behaviour; articulation follows the base anatomy, not a human
  mouth pasted onto it (§7).
- `mixed` — a production whose subjects genuinely span more than
  one kind (record each subject's kind separately as well).
- `non-character` — a shot with no character subject (a location
  establishing shot, an object, a title card). Title and end cards
  are general video devices, not a trailer-only device.

Every subject that recurs — human, digital human, animal, creature
— is registered like a character, each distinct, with its own
identity record (§C3). A subject is never merged into another
subject: bodies stay separate and solid, and one character or object
must never go inside another.

## 7. Human, animal, and creature distinctions

### 7.1 The five-way distinction

Five things are easily confused. They are different, and every
production record names which one each shot is:

1. **Live-action footage of a real person** — a real body, captured
   by a camera. Micro-expressions, breath, fatigue, and weight are
   the performer's own. The face in the close-up matches the body
   in the wide shot because it is the same person.
2. **Photorealistic digital human (generated)** — a generated
   person built from a photo or generated reference. It moves and
   speaks like a real person, but it is not footage of a shoot.
   Consent, likeness, and voice-permission rules apply exactly as
   for a real person (§12), because the likeness is a real person's
   or is presented as one.
3. **Photorealistic CGI human** — a 3D CGI human rendered to look
   real. It is a rigged CGI subject, not a photo-derived digital
   human; its identity is a designed character, and its movement
   follows rig-3D keyframe, motion capture, or performance transfer.
4. **Generated animal / creature** — a CGI or AI-generated animal or
   fictional creature. Its movement follows its own body and
   anatomy; its articulation target is its own mouth, beak, muzzle,
   or jaw (§7.2).
5. **Real animal in captured footage** — a real animal, filmed. It
   is directed by patience and editing, not by a rig: many takes,
   cut around its real behaviour, comic timing made in the edit.

A production that claims one of these while delivering another has
failed QC (§13). In particular: a photorealistic digital human is
never described as live-action footage, and live-action footage is
never described as generated.

### 7.2 Articulation targets

`ARTICULATION_TARGET` is per subject, per speaking or vocalising
shot:

- `human-mouth-lips` — human and digital-human subjects. Lips,
  jaw, and tongue follow the phonemes / visemes of the language
  spoken.
- `bird-beak` — a bird subject. The beak opens, closes, and shapes
  sound the way a beak does. No human lips on a bird, ever.
- `animal-muzzle` — a mammal or other animal subject. The muzzle
  and jaw move as that animal's muzzle moves.
- `creature-jaw-mandibles` — a fictional creature. The jaw,
  mandibles, or equivalent move as that creature's anatomy allows.
- `other` — any anatomy not covered above. Record what it is in the
  performance plan; "other" without a description is incomplete.

A subject that does not speak has no lip-sync requirement — but it
still has a performance requirement: it listens, reacts, breathes,
and moves, or the shot is a still (§8, §C8).

### 7.3 Real-animal handling

A real animal is a subject, not a prop and not a rig. Rules:

- Register the animal like a character (name + unique ID +
  references) when it recurs.
- Direct by takes and editing: many takes, cut around real
  behaviour. Never claim a real animal performed a movement it did
  not perform.
- CG touch-up only where the animal cannot perform, preserving its
  real body and identity.
- The animal's welfare and the owner's permission are recorded in
  the production record; no production invents them.
- A generated animal double used for a shot the real animal cannot
  do is recorded as a `cgi-animal` subject for that shot, not
  passed off as the real animal.

## 8. Character interactions and conversations

`INTERACTION_PATTERN` records how subjects share a scene. It is per
scene (or per beat, where the pattern changes inside a scene):

- `single-performance` — one subject performs alone.
- `two-person-conversation` — two subjects in dialogue.
- `multi-person-conversation` — three or more subjects in dialogue.
- `human-animal` — a human and an animal interacting.
- `human-creature` — a human and a creature interacting.
- `multiple-animals-creatures` — animals and/or creatures
  interacting with each other.
- `group-scene` — a crowd or group acting as a living character
  (reactions spreading in waves, distinct individuals, never
  copy-paste).
- `silent-reaction` — a subject reacts without speaking (a look, a
  gasp, a turn). Silence with a visible reaction is a performance;
  silence with a frozen face is a defect.
- `physical-contact-object` — subjects in physical contact with each
  other or with an object (a hand on a shoulder, holding hands,
  passing an object). Contact is real: hands meet, weight transfers,
  and a handover is physically correct. One character or object must
  never go inside another.

Dialogue blocking rules (apply to every conversation pattern):

- **Speaker and listener are always both directed.** When one
  character speaks, the other visibly listens — and never moves
  their mouth. Two mouths moving at once is a defect.
- **Eyelines.** Each character's gaze hits the other character's
  eyes (or, for a creature, the place its eyes are). An actor's
  eyeline to a CG creature hits the creature's eyes, not the empty
  space beside it.
- **180-degree rule.** The camera stays on one side of the line
  between the speakers for a conversation unless a motivated,
  scripted crossing is planned and the crossing itself is shown.
- **Turn timing.** Turns are timed from the dialogue: a real gap
  between speakers (not stitched lines), reaction holds after a
  line lands, and no speaker starting before the previous line's
  meaning has registered on the listener's face.
- **Positions.** Where each subject stands or sits, who is closer
  to camera, and who moves when, are recorded in the shot plan
  before generation — not improvised afterwards.
- **Shot types.** The conversation's shot list (wide, over-the-
  shoulder, close-up, reaction shot) is chosen from the emotional
  beats, and reaction shots cut between the speaker and individual
  listener faces.

## 9. Hybrid live-action/VFX workflows

A hybrid production (`PRODUCTION_MEDIUM: hybrid-live-action-cgi`)
combines captured footage with generated elements in the same shot
or scene. Rules:

- **One light, one world.** The generated element shares the live
  plate's light, casts shadows and reflections in it, and gets wet
  when the scene is wet. The seam between built set and extension
  never shows: one light, one haze, one water line.
- **Scale is fixed.** A creature's size relative to the actor and
  the set is fixed before generation and held across cuts.
- **Contact is real.** Where a generated element touches a real
  actor or object, the contact is planned and the handover is
  physically correct.
- **Eyelines and performance match.** The actor's eyeline hits the
  generated subject's eyes; the actor's performance (effort,
  weight, fatigue) matches the action the generated element
  implies.
- **Wetness and state continuity.** The wet state (hair, skin,
  clothes, salt, sand) is tracked across cuts and changes only when
  the story changes it. Underwater shots hold a fixed look with
  water-driven movement.
- **Set extension.** The real place is extended with CG, and the
  actor walks from the built set into the extension without the
  join ever being noticed.
- **Stunt and action.** Action is planned beat by beat and shot to
  look unplanned; the camera hides the safety, never the impact;
  the character stays readable through the fastest action.
- **Source honesty.** Every shot records which elements are
  captured footage and which are generated. A generated element is
  never passed off as captured, and captured footage is never
  described as generated.

## 10. Skill routing and compatibility

Routing is composable, not mutually exclusive. The old model — one
video-type skill per video, with the video-type skills as mutually
exclusive alternatives — is withdrawn. It is replaced by the model
below. (The routing data files that implement it —
`architecture/SKILL_ROUTING_MATRIX.yaml` and
`architecture/WORKFLOW_GRAPH.yaml` — are owned by the P0-006
architecture part; this document states the model they must encode.
Until those files are updated, no routing claim in them that
contradicts this section is to be relied on.)

- **Primary pathway.** Each production has one primary pathway,
  chosen from the production's dominant medium and purpose — for
  example, a stylized 3D short's primary pathway is the
  kids-family-animation / cinematic-power pathway, a photorealistic
  digital-human video's is the realistic-person pathway, and a
  live-action-plus-creature video's is the live-action-vfx pathway.
  The primary pathway supplies the production's main rules; it does
  not own the production exclusively.
- **Style profiles.** A style profile (for example, the flat 2D
  explainer profile, or an anime profile) layers onto the primary
  pathway. A profile contributes its style lock, palette, and
  craft rules; it never vetoes an unrelated layer.
- **Subject capabilities.** Subject capabilities layer per subject:
  animal and creature performance, real-animal handling, age
  performance, instrument performance, and similar capabilities
  apply to the subjects they describe, in the shots those subjects
  appear in.
- **Compatible layers.** Layers that do not conflict combine
  freely: voice consistency, humanized production, language
  authenticity, production systems, emotional performance, and
  resource management combine with any primary pathway. A
  production routinely runs many layers at once.
- **True conflicts only.** A conflict exists only when two rules
  genuinely cannot both hold for the same shot — for example, a
  shot cannot be both flat 2D vector and captured live-action
  footage, and a character cannot hold two visual styles in one
  shot. A conflict is resolved by choosing per shot (or per
  subject), recording the choice, and never by silently dropping a
  rule. The absence of a stated conflict is not a conflict: skills
  that merely do not mention each other are compatible unless a
  real contradiction is shown.
- **Precedence is tie-breaking, not exclusion.** Where two layers
  both speak to the same decision, the routing matrix's precedence
  order decides which one speaks first; the other still applies
  where it does not contradict. Command authority remains the
  router (precedence 1): it routes, it does not generate.
- **No global video-type mutual exclusion.** There is no rule of
  the form "a video is either X or Y". A video may be a stylized
  3D short with a musical performance, a crowd, and a CG creature;
  a video may be a photorealistic digital-human dialogue with an
  animal; a video may be a live-action plate with a generated
  creature and a title card. Each combination is described by its
  dimensions (§3–§6), routed by this model, and checked by §13.

Routing examples (illustrative, not the test scenarios — the
routing scenarios and their tests are owned by the P0-006
architecture part):

| Production | Primary pathway | Layers that also apply |
| --- | --- | --- |
| Flat 2D explainer short | explainer-animation profile | character + voice consistency, humanized production (sound, editing) |
| Stylized 3D kids short with a talking animal | kids-family-animation | cinematic-power (animal performance, music-beat), voice consistency, language authenticity |
| Photorealistic digital-human dialogue (2 people) | realistic-person | voice consistency, humanized production (listener reactions, lip-sync), emotional performance |
| Live-action plate + CG creature | live-action-vfx | cinematic-power (scale, colour), humanized production, voice consistency |
| Music video / stage performance | emotional-performance | cinematic-power (music-beat, ensemble), voice consistency, humanized production |

## 11. Schema responsibilities

Schemas are contracts, not code. Each contract below names the file
that carries it and what the contract must carry. Files marked
**existing (v2.4)** already exist in `schemas/`; files marked **new
in P0-006** are defined here and created by the P0-006 schema part —
this document does not create them, and no production may claim a
new contract exists until its file is present and validated.
Schema versions are additive: v2.5 adds fields; it never removes or
redefines a v2.4 field, and a v2.4 record stays valid under v2.5
(see the corrections record for the migration rule).

| Contract | File | What it carries |
| --- | --- | --- |
| Production profile | `schemas/production-profile.json` — **new in P0-006** | One record per production: `visual_style` (VISUAL_STYLE), `production_medium` (PRODUCTION_MEDIUM), `source_media` (SOURCE_MEDIA), `motion_method` (MOTION_METHOD array), `subject_kind` per subject, `interaction_pattern` per scene, and the primary pathway + layers chosen under §10. This is the record that makes a production describable, routable, and checkable. |
| Character | `schemas/character.json` — **existing (v2.4), extended in P0-006** | Character identity: name + unique ID (required), `subject_kind`, species / anatomy where relevant, style, reference-asset IDs, voice-profile ID, consent / rights record, and history. Structure is the fixed anchor; clothing and props are variable per scene. Media binaries stay in the private overlay; only relative pointers + hashes are stored. |
| Character registration | `schemas/character-registration.json` — **new in P0-006** | The registration act itself: the data-model fields of §C3 (name, unique ID, type/species/style, references, voice profiles, consent, history), the registration mode (permanent vs temporary, §C2), who authorised it and when, and the ID-generation / uniqueness-validation result. Registration is an explicit act; this record is its evidence. |
| Voice profile | `schemas/voice-profile.json` — **existing (v2.4), extended in P0-006, conditional v2.5 rules in P0-007** | Voice Profile data (§C5): tone, apparent age, language(s), fixed tags, fixed seed, reference-audio pointer, provider, provider limitations recorded, and the structured owner/workspace binding. Separate from character identity and from sound assets. Requires explicit authorisation + rights/consent. v2.5 conditional validation (user-recorded vs AI-generated, approval states, consent rules) is enforced by the Python validators — see §C5. |
| Scene plan | `schemas/scene-plan.json` — **existing (v2.4)** | Scenes, beats, dramatic intent, primary/secondary emotion, intensity (0–10), transitions. |
| Shot plan | `schemas/shot-plan.json` — **existing (v2.4)** | Shots: framing, camera angle/movement, lighting, duration (strictly positive), beat link — extended in P0-006 with the per-shot cinematography fields of §C10 (lens, height, focus / depth of field, transition) where the schema part adds them additively. |
| Performance plan | `schemas/performance-plan.json` — **existing (v2.4)** | Per dialogue line: facial + micro-expressions, eye movement/gaze, posture, gesture, breathing, physical behaviour, voice (emotion, pitch, pace, pauses), speaker identity, lip-sync required — extended in P0-006 with subject-specific articulation targets (§C8) and speaking/listening state. |
| Script-to-performance | `schemas/script-to-performance.json` — **existing (v2.4)** | The combined contract binding Scene + Shot + Performance Plans with audio (music/ambience/SFX) and editing (rhythm + reaction holds) plans. Dialogue is VERBATIM unless a rewrite was explicitly requested. |
| Timeline manifest | `schemas/timeline-manifest.json` — **existing (v2.4), extended in P0-007 to v2.5** | The one shared audio-visual timeline (§C11): video-clip + shot bindings, audio-clip + dialogue bindings, synchronization groups, and real cross-reference validation (shot / dialogue / character / voice / audio IDs must resolve to the records they name). It is NOT a renderer and contains no rendered media. |
| Episode / project state | `schemas/episode-state.json`, `schemas/project.json` — **existing (v2.4)** | Series, episode list, characters in use, and continuity notes (events, outfits, injuries, objects, end states) written after each episode and read before the next. |
| Visual style profile | `schemas/visual-style-profile.json` — **existing (v2.4)** | A locked visual style for a project/series. Identity stays fixed; style is project-scoped. |

Rules that apply to every schema in this table:

- **Additive evolution only.** A new version adds optional fields;
  it never renames, removes, or narrows an existing field. Old
  records validate under the new version.
- **No invented values.** Enum values come from the canonical
  vocabularies at the top of this document. A schema that needs a
  value not listed there is incomplete, not free to invent one —
  the vocabulary is extended only by a reviewed P0-006 change, and
  the extension is recorded in this document.
- **IDs are stable and recorded.** Character ID, reference-asset
  IDs, Voice Profile ID, Dialogue Line ID, Audio Asset ID, scene
  ID, and shot ID are stable across tools and episodes, and the
  production manifest records the IDs actually used (§C4, §C7).
- **Private data stays out.** No schema in the public repo carries
  image or audio binaries, or personal data. Pointers and hashes
  only; the media lives in the private overlay (§12).

## 12. Consent, rights, and private-reference handling

- **Upload is not registration.** Uploading an image, a voice
  recording, or a video does not register a character, a voice, or
  a sound asset. Registration is a separate, explicit act (§C2,
  §C3), and a temporary use is a separate mode from a permanent
  registration. An upload is never silently converted into a
  permanent registration.
- **Temporary versus permanent.** Temporary use means: the asset is
  used for this production only, no permanent record is created,
  and nothing is carried into a future project. Permanent
  registration means: the character / voice / asset is stored for
  consistent reuse across scenes, episodes, and projects. The
  choice is the user's, per asset, and the record says which one
  was chosen.
- **Real-person face and voice only with permission.** A real
  person's photo may be turned into a moving, speaking digital
  human, and a real person's voice may be cloned, only with that
  person's permission. Uploading someone else's voice or photo is
  NOT proof of authorisation. Permission is recorded (who gave it,
  for what use, when); where it cannot be recorded, the work does
  not proceed.
- **No inferred consent from public images.** That a photo is
  public, famous, or easy to find does not authorise its use as a
  character reference, a likeness, or a voice source. Public
  availability is not consent.
- **Provenance and licensing.** Every source asset records its
  provenance (who supplied it, where it came from) and its licence
  or rights basis. Stock, licensed, and user-supplied assets are
  distinguished. Watermarks and provenance are never removed.
- **Private media outside public GitHub.** Character reference
  images, voice recordings, and personal data are private by
  default and are never committed to this public repository. They
  live in a separate private overlay (see `characters/README.md`
  and `docs/07-character-registry.md`). No public shared library
  of private characters or voices exists by default; sharing or
  export needs an explicit user action.
- **Local-first, serverless Brain.** Consistency Frame has no
  central server, API backend, or cloud database. Work is
  local-first and serverless. That does not mean data never leaves
  the machine: when a provider is used (a voice provider, an image
  or video provider), the data sent to that provider is disclosed —
  what is sent, to whom, and for what — and no unsupported "never
  leaves the device" promise is made.
- **Permanent canonical Skill updates need explicit user
  authorisation and a reviewable process.** A lesson learned from a
  reference becomes a permanent rule only through the propose/apply
  split: propose in `REFERENCE_LEARN_AND_UPDATE` mode with an
  explicit instruction, as a reviewable patch; apply only with a
  full authorisation (`granted_by` + scope + branch +
  `explicit_authorisation`). Intake alone never applies anything,
  and a trend becomes a permanent rule only after verification —
  never from a title, thumbnail, description, or a video that did
  not play.
- **Child safety.** Content for children follows the kids & family
  rules: funny, warm, curious, or exciting — never frightening,
  crude, or age-inappropriate. "Made for Kids" is set only when the
  content is for children or the user asks for it.

## 13. Quality gates

Every production passes the same five gates before delivery. Each
gate is measurable or human-reviewable; none of them is a promise of
a perfect result, and no gate carries an invented numeric fidelity
guarantee (no "100%" and no percentage that was never measured).

1. **Identity gate.** The character / subject in each shot matches
   the approved reference: face and structure first, then height,
   hands, and feet. Checked shot by shot against the approved
   reference (and, for face-critical shots, against the
   matching-angle view). Drift means regenerate — fresh, never an
   edit of a drifted face — and re-check. A human-review gate
   applies: a person looks at the shot against the reference.
2. **Voice gate.** The voice in each line matches the character's
   Voice Profile: recognisably the same character, in the right
   language, with the script's emotion. Speaker-embedding
   similarity and a prosody fingerprint are measured where the
   tooling supports it; where it does not, a human listening check
   is the gate. A different voice is never silently substituted —
   a limitation is reported (§C7).
3. **Performance gate.** The performance is a performance: the
   speaker speaks with a moving mouth matched to the audio and the
   language; the listener visibly listens and never moves their
   mouth; expressions, micro-expressions, gaze, posture, gesture,
   and breathing follow the script's beats; animals and creatures
   move and articulate as their own anatomy allows (§7, §C8). A
   talking character with a still mouth, a frozen face, or dead
   eyes is a defect, never a delivery.
4. **Cinematography gate.** The camera is motivated and continuous:
   angle, size, framing, lens, height, movement, focus, depth of
   field, lighting, and transitions follow the shot plan (§C10);
   the 180-degree rule holds across each conversation; focus and
   depth behave as planned (shallow / deep / rack); continuity
   (outfits, injuries, objects, wetness, light direction) holds
   across cuts. Unmotivated movement, a random grade change inside
   a scene, or a broken eyeline fails the gate.
5. **Audio-visual gate.** Sound and picture agree on one shared
   timeline (§C11): dialogue, ambience, foley, and music are
   present where the plan requires them (silence in an interior is
   a defect); cuts land on the beat or the phrase where the plan
   says they do; lip-sync matches its own audio track per line;
   levels follow the delivery profile for the target platform
   (loudness is a delivery profile, never one universal target);
   captions, where requested, match the spoken words.

A production that fails a gate is not delivered as finished. It is
repaired, regenerated, or reported as limited — with the limitation
stated plainly.

## 14. Honest capability limitations

This section states what is NOT executable yet. Nothing in this
document makes a capability real by describing it.

- **P1 runtime.** The runtime skill-routing engine (intake →
  route → run → QC) and the script-to-performance runtime (script
  → Scene/Shot/Performance Plans) are P1 work. P0 defines the
  contracts; it does not execute them. Until P1 exists, the routing
  matrix and the schemas are human/agent-readable contracts, and a
  production is carried out by the assistant following them by
  hand.
- **Provider execution.** Image, video, and voice generation run
  through providers (including the companions' providers). A
  provider route is claimed as working only when it has been
  exercised and recorded — in the companion capability registry,
  with an honest evidence level. Paid provider routes are never
  called live without the user's explicit approval and keys, and
  unvalidated routes are recorded as not verified, not as working.
- **Rendering engine.** Consistency Frame has no rendering engine
  of its own. Rendering happens in the companions and providers.
  No claim is made that a described motion method renders on this
  machine, on any machine, or at any quality, until a render has
  actually been produced and checked.
- **No exercised / production-verified marking without evidence.**
  A capability, a method, a skill, or a production is never marked
  exercised, tested, or production-verified on the strength of
  this document. Evidence is a run, a render, a check, or a test —
  recorded with its result. The companion capability registry and
  the agent compatibility matrix record only Muse as verified, and
  only for the path actually used.
- **Voice reproduction limits.** A voice profile does not promise
  perfect cross-provider reproduction. Provider limitations are
  recorded in the Voice Profile (§C5), and a voice that a provider
  cannot reproduce is reported as a limitation, not papered over
  with a different voice.

## 15. What P0 documents versus what P1 will execute

| Area | P0 (this work order) | P1 (later) |
| --- | --- | --- |
| Animation scope | This document: definitions, vocabularies, routing model, consent and QC rules | — (scope is defined in P0; P1 implements it) |
| Production profile + character registration + voice-profile contracts | Schema contracts defined (§11); schema files created/updated additively (schema_version 2.5) | Runtime that reads the contracts and enforces them during a production |
| Routing | Composable routing model (§10) encoded in the routing matrix and workflow graph as canonical data | Runtime skill-routing engine that executes the matrix and graph |
| Script-to-performance | Schemas as contracts (§11); dialogue verbatim rule | Runtime that produces Scene/Shot/Performance Plans from a script |
| Character / voice binding | Binding record defined (§C7); manifest records the IDs used | Runtime that resolves IDs, fetches references, and passes them to providers automatically |
| Performance + cinematography | Direction models defined (§C8, §C10) | Runtime direction: per-shot generation driven by the plans |
| Companion handoffs | Handoff contracts defined (§C11); stable IDs for VoiceStudio / OpenMontage | Executed handoffs; adapter conformance tests |
| Quality gates | Gates defined (§13, §C12) as measurable or human-reviewable checks | Automated QC where tooling supports it; human-review gates remain human |

P0 adds no server, API backend, database, or rendering engine, and
modifies no VoiceStudio or OpenMontage internals. P1 is not started
in P0, and nothing in P0 is to be read as a promise that P1 exists.

---

# Addendum C

The sections below are Addendum C to CF-WO-P0-006. They are part of
this canonical document, not an appendix to be read separately: a
production that ignores them is not a P0-006 production.

## C1. Reference video is OPTIONAL

A reference video is never required. There are exactly two paths,
and the production record names which one was taken:

- **Path A — reference-video-assisted.** The user supplies a
  reference video. The system analyses it in full first (story,
  scenes in order, characters, objects, camera, light, sound),
  then creates a NEW original video that preserves the reference's
  core story, emotional impact, narrative structure, and creative
  direction — with only minor or explicitly requested changes.
  The output is an alternative version, never a frame-for-frame
  copy. A storyboard is made before generation, audio is original,
  and a mandatory QC pass runs before delivery.
- **Path B — script-and-image-driven.** No reference video is
  supplied. The production is driven by the script and by images
  (character references, generated images, or none at all —
  `SOURCE_MEDIA: script-only`). Nothing about a reference video is
  claimed, described, or "analysed" on this path.

Rules that apply to both paths:

- **Never invent a reference video.** If no reference video was
  supplied, no text, plan, or report may claim one was analysed,
  watched, or used — not even in passing, and not even as a
  hypothetical ("as seen in the reference video").
- **Never claim analysis that did not happen.** A reference video
  that was supplied but not watched in full is not "analysed".
  Analysis means the full video, scene by scene; a title,
  thumbnail, or description is not analysis.
- **Training clips are training clips.** User-uploaded videos used
  to learn technique are training video clips. They are not
  trailers, and technique learned from them is recorded as
  technique — never as a trailer structure — unless the user
  explicitly asks for a trailer.

## C2. First-run Character Registration invitation

On first run — the first time a user introduces a character, or the
first time a production involves a person, animal, or creature that
could recur — the assistant invites the user to register the
character. Registration is optional, and the invitation says so.
The invitation asks, in the user's language:

> "Would you like to register this character for consistent use in
> future projects?"

And it offers three honest choices:

1. **Register now** — permanent registration (§C3). The character
   is stored for consistent reuse across scenes, episodes, and
   projects.
2. **Skip, and use temporarily** — temporary use. The character's
   images and voice are used for this production only; no permanent
   record is created; nothing is carried into a future project.
   Skipping must not prevent creating a video: a user who skips
   still gets their video, with the character used temporarily.
3. **Register later** — the character is used temporarily now, and
   the user is asked again when it next recurs (or when they ask
   to register it). "Later" is a real choice, not a disguised "no".

Rules:

- **Temporary Asset Use versus Permanent Character Registration
  are different modes, and the record says which one applies.**
  The modes are the v2.4 asset modes: one-off use
  (`TEMPORARY_ASSET_USE`, `UPLOAD_ONLY`) versus recurring
  registration (`REGISTER_CHARACTER`, `REGISTER_VOICE_PROFILE`).
- **Never silently convert an upload into a permanent
  registration.** Uploading images, or saying whose they are,
  binds images to a name for this production; it does not
  register the character permanently. Permanent registration
  needs the explicit authorisation in §C3.
- **The invitation is asked once, not nagged.** If the user picks
  temporary use or "later", the assistant does not re-ask in the
  same production, and does not ask the same question twice.
- **Registration is never a precondition for a video.** No
  production is refused, delayed, or degraded because a character
  is unregistered. Temporary subjects get the same identity,
  voice, performance, and QC treatment inside their production;
  only their persistence differs.

## C3. Character registration data model

A registration record carries all of the following. Character Name
and Unique Character ID are required; the rest are required where
the subject has them, and recorded as not-applicable where it does
not (a creature has no human age; a non-speaking subject has no
voice profile).

| Field | Required | Notes |
| --- | --- | --- |
| Character Name | Yes | The name the user gives. A duplicate name with a different ID stops the registration and asks the user first. |
| Unique Character ID | Yes | Stable, unique across the workspace. The user may supply one (for example `char-001`), or ask the system to generate one. A generated ID is shown to the user as the visible final ID, and uniqueness is validated before the registration is accepted — a colliding ID is rejected, never silently reused or overwritten. |
| Subject kind | Yes | `SUBJECT_KIND` value (§6). |
| Species / anatomy | Where relevant | Species, body plan, and anatomy notes for animals, creatures, and anthropomorphic subjects — including the articulation target (§7.2). |
| Visual style | Yes | `VISUAL_STYLE` value for the project the character is registered in; style is project-scoped. |
| Reference assets | Yes | Reference-asset IDs (images, model sheet, expression library) — see §C4. At least one approved reference is required for a permanent registration. |
| Voice profile(s) | Where the subject speaks | Voice Profile ID(s) (§C5). A character may have more than one voice profile (for example, per language or per age variant); each is a separate record, and the binding in each production names which one is used (§C7). |
| Consent / rights | Yes | Who authorised the registration, for what use, and when — including likeness and voice permission where a real person, a real animal's owner, or a rights-holder is involved (§12). |
| Ownership | Yes (permanent) | Structured ownership (`schemas/character-registration.json` `ownership`): `owner_id` + `workspace_id` — stable, opaque, randomly generated local identifiers, never a real name, email, or account detail — plus `visibility` (`private` by default) and `sharing` (`none` by default; shared access needs an explicit future sharing permission). A character never becomes public merely because an image was uploaded. |
| History | System-kept | When the character was registered, what changed since (outfit changes, new expressions, new voice variants), and which productions used it. |

Registration also records the mode (permanent vs temporary, §C2)
and the authorisation itself: the user's explicit words (for
example, "Register this character permanently"), not an inference
from the upload. A name written on the image is NOT mandatory: if
the user gives photos and says in their message whose they are,
that binds them for this production. A name on the image is required
only when several characters' images are uploaded together in one
batch.

## C4. Character–image binding and reference management

- **Resolve by ID, or by unambiguous name.** A name in a script
  resolves to a character's ID first. If the name is unambiguous
  (exactly one registered character has it), the name resolves to
  that character. If the name is ambiguous (two or more characters
  share it, or a name matches a temporary subject and a registered
  one), the assistant asks the user — it never guesses.
- **Retrieve the correct references.** The resolved character's
  reference images, model sheet, and expression library are the
  references for that character's shots. A different character's
  references are never substituted, and references are never mixed
  between characters in one shot.
- **Pick shot-relevant references.** For each shot, the reference
  closest to the shot's needs is used: the matching-angle view for
  a face-critical shot, the matching expression where one exists,
  the full-body view where the body matters. Where no matching
  reference exists, the definitive reference is used and the gap is
  noted — a missing expression is generated from the definitive
  reference, saved to the expression library, and reused, never
  generated twice.
- **Pass to the supported provider.** The chosen references are
  passed to the provider that supports them, in the form that
  provider accepts, with the fixed prompt block and the seed that
  lock the identity. References are not silently dropped because a
  provider prefers fewer inputs; if a provider cannot accept a
  reference, that limitation is recorded and reported.
- **Preserve identity.** A registered image is a reference asset,
  NOT permission to alter identity. The face, structure, hands,
  and feet stay as the approved reference shows them; only
  movement, speech, clothing, and props change — clothing and
  props only on the user's word or a clear script need, and the new
  outfit then holds in that context.
- **Record IDs in the production manifest.** Every production's
  manifest records the Character ID and the reference-asset IDs
  actually used, per shot. If the manifest cannot name them, the
  production record is incomplete.
- **No suitable character.** If no registered character matches
  what the script needs, the assistant asks the user: use an
  existing character, create a new one temporarily, or register a
  new one permanently (§C2). It never invents a character, and
  never quietly reuses a different character's identity to fill
  the gap.

## C5. Private character-specific voice registration

A voice is registered per character, privately, by one of two
paths. Both paths produce the same record — a Voice Profile — and
both require the authorisation in §12.

- **User-recorded path.** The user supplies a voice reference:
  a recording of the character's voice (their own voice, or a
  voice they have permission to use). The recording is stored in
  the private overlay, never in the public repo, and is the
  reference audio for the Voice Profile.
- **AI-generated path.** The user asks the assistant to generate
  a voice for the character; the assistant generates candidates,
  plays / presents them, and only the candidate the user approves
  becomes the character's voice. From then on it is reused as the
  reference to lock the voice — generate once, save the output,
  reuse it as the reference.

Voice Profile data fields: tone, apparent age, language(s), fixed
tags, fixed seed, reference-audio pointer, provider, provider
limitations recorded, and owner/workspace scope. The profile is
separate from the character identity record and from sound assets;
it is linked by ID, never embedded.

Conditional validation (v2.5, P0-007): the JSON Schema alone cannot
express conditional requirements (the repo validator supports only a
restricted subset), so the v2.5 rules are enforced by the Python
validators in `scripts/asset_policy.py` and the tests, and the schema
and the validators must agree on every record. A v2.5 profile must
carry `voice_profile_id`, `character_id`, `source`, the structured
`ownership` binding, appropriate voice asset references, an approval
state, and a consent state. The rules differ by source: a
user-recorded voice needs at least one approved audio reference
asset and explicitly granted consent, and its owner/workspace must
match its character's; an AI-generated voice needs provider
identification (and model identification when available) and an
approval state, must never become approved automatically before the
required user review, and records `human_voice_donor` (true when a
real person's voice was used — then explicit permission and consent
are required; false when no human donor was involved — then
`consent_status` `not-required` is legitimate and must never be used
to bypass an actual permission requirement). Approval states are
distinct: a generated or recorded sample is not an approval; only an
approved, correctly owned profile may be selected for production
when approval is required. `consent_status` governs consent and must
agree with the `consent` record; `approval_status` must agree with
`status`. A v2.3 profile remains valid under the legacy contract.

Honesty rules:

- **No claim of perfect cross-provider reproduction.** A voice
  profile does not promise that every provider reproduces the
  voice identically. What is promised is that the same profile —
  same tags, same seed, same reference audio — is used every time,
  and that drift is measured where the tooling supports it and
  heard by a human where it does not.
- **Provider limitations are recorded.** If a provider cannot
  reproduce a quality of the voice (a language, an age, a
  non-verbal sound), the limitation is written in the Voice Profile
  and reported to the user — not hidden, and not worked around by
  substituting a different voice (§C7).
- **One voice per character, per profile.** A character's voice
  stays recognisably the same character across episodes. Variants
  (age, illness, whisper/shout, tiredness, cold) are recorded as
  variants of the profile, not as new voices.

## C6. Strict voice isolation and privacy

- **Owner / workspace scoped.** A voice profile belongs to one
  owner and one workspace. It is usable only in that owner's
  productions, in that workspace. Ownership is a structured record
  (`ownership`: `owner_id`, `workspace_id`, `visibility`,
  `sharing`), not a free-text scope string. Resolving a voice
  profile requires BOTH conditions to match: (1) the Character ID
  + Voice Profile binding, and (2) the character's ownership and
  the voice profile's ownership. Same Character ID with a different
  owner or workspace is REJECTED — a voice is never resolvable
  merely because its Character ID matches. P0-008 makes this
  fail-closed: for a private v2.5 voice the production resolver
  (`scripts/asset_policy.py` `resolve_voice_for_production`)
  REQUIRES the requester owner + workspace identity, and a
  private voice export requires a trusted, owner-bound
  authorization context (`TrustedAuthorizationContext`) — a
  caller-created dictionary never authorizes anything — with
  provider transmission as a separate permission; strict v2.5
  timeline validation (`scripts/timeline_policy.py`,
  `strict=True`) enforces the same ownership rules on every
  referenced character, voice, and dialogue-bound audio asset.
  See `docs/implementation/CF-WO-P0-008-corrections.md`.
- **No cross-character inheritance.** A voice never transfers from
  one character to another. Two characters never share a voice
  profile unless the user explicitly registers the same voice for
  both — and that explicit act is recorded per character.
- **No cross-user leakage.** One user's voices, characters, and
  reference media never appear in another user's productions,
  and never in a shared library.
- **No private media in public GitHub.** Voice recordings,
  reference images, and personal data are never committed to this
  public repository. They live in the private overlay.
- **No public shared library by default.** There is no public
  library of characters or voices. Exporting or sharing a character
  or a voice needs an explicit user action, per asset, naming what
  is shared and with whom.
- **Local-first, serverless Brain — disclosed transmission.** The
  Brain has no central server, API backend, or cloud database.
  When a provider is used, the data sent to that provider (audio,
  images, text) is disclosed — what is sent, to whom, and for
  what. No unsupported "never leaves the device" promise is made:
  a voice sent to a voice provider has left the device, and the
  record says so.
- **Real-person voice cloning needs permission.** Cloning a real
  person's voice needs that person's permission, recorded (§12).
  Uploading someone else's voice or photo is NOT proof of
  authorisation.
- **Client isolation.** In agency work, per-client workspaces
  apply: a client's voice, character, and brand kit are checked
  against that client's workspace before every generation, and one
  client's assets never appear in another client's production.

## C7. Character–voice binding in every production

Every production binds character and voice explicitly, per shot and
per dialogue segment. The binding record carries, for each shot /
dialogue segment:

| Field | Notes |
| --- | --- |
| Character ID | The registered (or temporary) character's unique ID. |
| Reference Asset IDs | The reference images / model sheet actually used for this shot. |
| Voice Profile ID | The voice profile used for this character in this segment. |
| Dialogue Line ID | The stable ID of the dialogue line (from the script-to-performance contract). |
| Audio Asset ID | The audio asset produced for this line, once generated. |
| Speaking / listening state | Whether this character is speaking or listening in this segment. A listener never moves their mouth. |
| Emotion / delivery | The emotion, pitch, pace, and pauses for the line, from the script. |
| Lip-sync / articulation | The articulation target (§7.2) and the lip-sync method used (`lip-sync-phoneme-viseme` or `creature-articulation`), matched to the language actually spoken. |

Rules:

- **Reuse approved identity + voice across scenes.** The same
  approved reference and the same voice profile are reused in every
  scene and episode. Identity is never rebuilt from a fresh
  interpretation.
- **Never silently substitute a different voice.** If the bound
  voice cannot be produced (a provider limitation, a missing
  reference, a drift beyond the gate), the production reports the
  limitation — which line, which character, and why — and asks the
  user what to do. A different voice is never slipped in quietly,
  and a failure is never delivered as if it succeeded.
- **Per-character language.** In one video each character may speak
  a different language; dialogue, voice, and lip-sync follow that
  character's language — never force all characters into one
  language.

## C8. Performance direction

Performance direction covers face, mouth, body, and movement, and
is recorded in the performance plan per dialogue line and per beat.
It has three sections, each with subject-specific articulation:

- **Facial performance.** Expressions, micro-expressions, eye
  movement, gaze, blinking, breathing. The face follows the
  script's emotional beats: a slow turn (no response, a flicker,
  recognition, tears, joy) is planned beat by beat. Dead eyes and
  a frozen face are defects. For animals and creatures, facial
  performance follows their anatomy: ears, brow, muzzle, and gaze
  as that subject has them.
- **Speaking performance.** Mouth movement matched to the audio
  and the language (§7.2); voice emotion, pitch, pace, and pauses
  from the script; non-verbal voice (sighs, laughs, whispers,
  breaths, hesitations) where the script calls for it. A talking
  character with a still mouth is a defect, never a delivery. No
  human lips on birds: a bird's beak articulates as a beak; an
  animal's muzzle as a muzzle; a creature's jaw or mandibles as
  its own anatomy allows.
- **Body performance.** Posture, gesture, walk, weight, physical
  behaviour, and effort. A real body (or a believable generated
  one) shows effort where the action is hard; movement is slow,
  trembling, or frail where age or condition requires it; hands
  play the instrument the music requires. Hands are directed, not
  left to chance: frame hands out, keep hand shots to short
  segments, and check hand close-ups against the audio where the
  hands must match sound.

Involuntary motion is part of the direction, not decoration: blink
cadence, eye movements, breathing, and head micro-drift are
specified per shot. The performance plan also records reaction
holds (the listener's visible reaction after a line lands) and
non-verbal events (a gasp, a laugh, a silence) as first-class
entries — a line with no spoken text and no non-verbal event is
invalid.

## C9. Multi-character interaction and dialogue blocking

Blocking is planned before generation, in the scene and shot plans,
and covers:

- **Who speaks, listens, looks, and reacts** — per line, per
  character. The speaker, the listener(s), and any reacting
  bystander are each named; nobody's state is left unspecified.
- **Positions.** Where each subject stands or sits, who is closer
  to camera, who moves and when, and how contact happens (a hand
  on a shoulder, holding hands, a handover). Positions are
  recorded; bodies stay separate and solid.
- **Eyelines.** Each subject's gaze direction, hitting the other
  subject's eyes (or the place its eyes are). Eyelines are checked
  across cuts: a character looking left in the wide shot looks
  left in the close-up.
- **Shot types.** The conversation's shot list — wide, over-the-
  shoulder, close-up, reaction shot — chosen from the emotional
  beats, with reaction shots cutting between the speaker and
  individual listener faces.
- **180-degree rule.** The camera stays on one side of the line
  between the speakers unless a motivated, scripted crossing is
  planned and the crossing itself is shown.
- **Turn timing.** Turns are timed from the dialogue, with real
  gaps between speakers, reaction holds after a line lands, and no
  overlap of mouths. Single-pass multi-speaker dialogue (up to 10
  voices in one call, with real gaps) is used where the voice
  provider supports it; otherwise lines are sequenced with the
  same gaps, never stitched without them.

For human–animal and human–creature interaction, blocking also
records the animal's / creature's real behaviour: what it can do,
what must be made in the edit, and where a generated double stands
in (§7.3).

## C10. Intelligent cinematography

Camera work is motivated: every camera decision follows the story,
the emotion, or the physical action — never movement for its own
sake. Per shot, the shot plan records: angle, size, framing, lens,
height, movement, focus / depth of field, lighting, and transition.

- **Angle, size, framing.** Chosen from the scene's beats and the
  8-question camera system (what the shot must show, whose
  emotion it carries, what the physical action needs). The camera
  follows the story, the emotion, and the physical action.
- **Lens and height.** Lens (and the perspective it implies) and
  camera height are recorded per shot, not left to a default.
- **Movement.** Slow continuous push-ins inside scenes, slow pans
  between ideas, handheld breathing where the scene calls for it —
  and stillness where stillness carries the emotion (an intimate
  drama holds close and still and lets the faces do the work).
  Unmotivated movement fails the cinematography gate (§13).
- **Focus and depth.** Focus behaviour is planned per shot:
  shallow depth of field (one subject sharp, the rest soft), deep
  focus (everything sharp), or a rack focus (focus travelling
  from one subject to another as the story's attention moves).
  Focus pulls are timed to the beats, and eye and gaze continuity
  holds across them.
- **Lighting.** Shadow direction, colour temperature, and light
  position are locked per scene. Colour follows the script: the
  grade follows the time of day and light source, and a colour
  palette is assigned to each emotional beat with planned
  transitions — colour follows emotion, not only time of day, and
  never changes randomly inside one scene.
- **Transitions.** The transition into and out of each shot is
  recorded (cut, cut on action, cut on the phrase, J-cut, L-cut,
  flash-frame where the story calls for it). Scenes flow by camera
  movement or by a chosen transition, never by accident.
- **Continuity.** Outfits, injuries, objects, wetness, light
  direction, and the state of every hero prop are tracked across
  cuts and change only when the story changes them.

## C11. One shared audio-visual timeline

All sound and picture share one timeline, carried by the timeline
manifest (`schemas/timeline-manifest.json` — v2.5 since P0-007:
video-clip + shot bindings, audio-clip + dialogue bindings,
synchronization groups, and cross-reference validation; it is NOT a
renderer and contains no rendered media).
The timeline is the handoff contract between the Brain and the
companions:

- **Stable IDs.** Dialogue Line IDs and Shot IDs are stable across
  tools and episodes. VoiceStudio receives dialogue lines by ID
  with their character, voice profile, emotion, and delivery; it
  returns audio assets by ID. OpenMontage receives shots by ID
  with their media, timing, and transitions; it returns the
  assembled timeline. Neither companion renumbers, reorders, or
  re-interprets the IDs.
- **Four sound layers.** Ambience, foley, dialogue, and music are
  spotted per shot on a sound spotting sheet. Room tone is present
  in every interior. Silence is a defect.
- **Music as direction.** Cuts and movements land on the musical
  beat where the plan says they do; a synchronized movement shares
  one timing reference for every character and animal, with no
  drift. Where a song is the plot, the song's arc drives the
  staging.
- **Dialogue-first mixing.** Dialogue is mixed first; music and
  effects sit under it and never bury a line.
- **Delivery profiles.** Loudness and delivery follow the named
  delivery profile for the target platform — never one universal
  target.

## C12. Quality control

QC runs the five gates of §13 (identity, voice, performance,
cinematography, audio-visual) before delivery, shot by shot, and is
recorded per shot: which gate, what was checked, and the result.
The rules:

- **Measurable or human-reviewable, never a promised percentage.**
  Where a measurement exists (face-embedding similarity, speaker-
  embedding similarity, prosody fingerprint), it is measured and
  the threshold is recorded. Where no measurement exists, a human
  looks and listens. No gate carries an invented numeric fidelity
  guarantee.
- **Provider-limitation honesty.** Where a provider cannot do what
  a gate requires, the QC record says so: which gate, which shot,
  which limitation — and the production is reported as limited,
  repaired, or regenerated. A limitation is never recorded as a
  pass, and a failed gate is never delivered as finished work.
- **Regenerate, don't patch a drifted identity.** A face that has
  drifted is regenerated fresh from the definitive reference; it
  is never edited or inpainted into correctness. A merged face is
  never inpainted — regenerate fresh.
- **Blind-test gates.** Where the plan calls for a blind test (a
  viewer who does not know which version is which), the test is
  run and its result recorded; a gate is not passed by assertion.
- **QC before delivery, every time.** No production skips QC
  because it is short, simple, or a re-run. A re-run is re-checked:
  the checks are cheap and the drift they catch is not.

---

## Document control

- **Canonical vocabularies:** § "Canonical vocabularies" above.
  Extensions need a reviewed P0-006 change and are recorded here.
- **Supersedes:** the "Realism, not animation" wording in the
  README's realistic-person section; the flat-2D-explainer-only
  framing wherever it appears; the one-video-type-per-video mutual
  exclusion in `architecture/WORKFLOW_GRAPH.yaml` (exclusive
  groups) and in `docs/implementation/P0_UPDATED_IMPLEMENTATION_PLAN.md`
  §6 (precedence 11–14 "never run together") — replaced by the
  composable model of §10.
- **Does not change:** any skill file, any Master Prompt file, any
  companion internals, or the P0 vs P1 boundary (§15).
- **Related records:** `docs/implementation/CF-WO-P0-006-corrections.md`
  (what existed, what contradicted, what changed);
  `docs/implementation/P0_UPDATED_IMPLEMENTATION_PLAN.md` §9
  (P0-006 in the implementation plan).
