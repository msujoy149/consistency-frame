# Professional Production Systems

These eleven systems are what turn an acceptable generated video into a
professional series. They apply to every project unless the user says
otherwise. Nothing here is optional decoration: each system exists because
skipping it is visible on screen. A twelfth professional system —
script-driven automatic camera angles — is numbered in the
production-systems skill (A12) and cross-referenced from §2 below.

Counting note: eleven of the twelve systems in Part A of the
production-systems skill also appear here. The twelfth — script-driven
automatic camera angles (A12) — is numbered in the skill only and
cross-referenced from §2 below. Together with the 18 extended, 3
language/captions/format, 7 additional, 36 humanization, 7 agency
advertising, 1 video regeneration, 5 cinematic power, 6 live-action & VFX, 7 emotional performance, 1 user-supplied voice cloning, and 1 on-demand resource management, and 1 language authenticity, and 1 realistic person video, 1 2D explainer animation, 1 command authority, and 1 kids & family animation systems, the repo holds 109 distinct systems, presented as 120 numbered entries.

How the count is made: production-systems lists 40 numbered entries (12 + 18 + 7 + 3); humanized-production 36; agency-advertising 7; cinematic-power 5; live-action-vfx 6; emotional-performance 7; and video-regeneration, user-supplied voice cloning (voice-consistency §13), resource-management, language-authenticity, realistic-person, explainer-animation, command-authority, and kids-family-animation each count as 1 whole system — 12+18+3+7+36+7+1+5+6+7+1+1+1+1+1+1+1 = 109 distinct systems. The 120 numbered entries are those 109 plus the 11 Part A systems listed twice (in the production-systems skill and here). The character-consistency skill and the other sections of voice-consistency are the working detail of those systems — registry, generator, verification, voice profiles, dialogue — not additional numbered entries.

## Production Priority Hierarchy

When different instructions compete, follow this order. A lower priority
never overrides a higher one.

1. **User's explicit instructions / script** — the user's direct
   instructions, script, and authorized changes take precedence over
   assumptions.
2. **Character identity consistency** — registered characters must keep
   their recognizable physical identity in every scene.
3. **Story and action accuracy** — the video must accurately represent the
   intended story and actions.
4. **Physical realism and continuity** — human movement, object handling,
   scene geometry, and transitions must remain believable.
5. **Professional cinematography** — suitable professional camera work,
   lighting, composition, and visual storytelling.
6. **Visual and audio quality** — the highest practical quality the
   platform supports.

Never sacrifice character identity or story accuracy merely for visual
decoration.

---

## 1. Visual Style Bible

Every project has one fixed visual style: a colour palette, a lighting
mood, and a level of realism. Record it in the project and use the same
style in every episode, so all episodes look like one series and not like
separate videos.

- Define the palette (dominant colours, skin-tone handling, saturation
  range), the lighting mood (soft daylight, high-contrast drama, warm
  interiors), and the realism level (photorealistic, stylised, animated)
  before the first episode is generated.
- A bright comedy scene and a sad night scene may differ in mood, but the
  underlying look — colour, light, texture — must stay recognizable as the
  same series.
- Any change to the style bible is a deliberate, recorded decision, never
  an accident of a new generation. If the user asks for a different look,
  record the change and apply it from that point forward.

## 2. Camera Language and Shot List

Decide the camera language before generating: when to use a close-up
(emotion, dialogue), a medium shot (conversation), and a wide shot (place,
action). Use the same language across episodes so the series has a
consistent visual grammar.

For each scene, follow a simple shot plan:

- **Establishing shot** — shows the place and orients the viewer.
- **Main action** — the core of the scene, in the framing the action
  needs.
- **Reaction shot** — the other character's (or the audience surrogate's)
  response, which carries the emotion.
- **Closing shot** — ends the scene cleanly and hands the viewer to the
  next scene.

Do not rely on a single framing for everything. A scene shot entirely in
one framing feels flat, no matter how good the characters look.

Which angle each shot uses is not chosen here by habit. The
script-driven automatic camera angles system (production-systems skill,
A12) reads the script beat first — story function, emotion, relationship
between the characters, and what the viewer must notice — and lets that
decide the angle; the angle plan is written into the shot list before
generation. A12 gives the full shot grammar, the beat-to-angle mapping,
lens language, and the continuity rules. It also covers the case
where the user gives no script: the system first writes the story
as beats, then directs the angles from those beats, so the angle
decision is mandatory whether the script is supplied or generated —
never skipped, never left to chance, never decided after generation.

### Director's breakdown, blocking and coverage

Before choosing any shot, read the scene in five steps — Observe →
Describe → Infer → Recreate → Compare — and keep four things separate:
what is objectively visible, what is inferred, what is a creative
hypothesis, and what still needs verification. A hypothesis is never
written into the shot list as a fact.

For each scene, record a breakdown before shooting: scene purpose;
one-line summary; emotional tone; each character's objective; character
relationships; scene geography; main actions; important props;
environment; required coverage; sound requirements; transition into the
next scene. Record the blocking too: character positions; screen
direction; foreground, midground, and background; entry and exit points;
movement paths; marks and interactions; camera relationship. Characters
and objects must not drift between shots without a story reason.

Coverage is selective, never exhaustive. The twelve types are extreme
wide / establishing, wide shot, full shot, medium wide, medium shot,
medium close-up, close-up, extreme close-up, two-shot, over-the-shoulder,
insert, and cutaway — each with its purpose (master wide for geography;
two-shot for relationship; over-the-shoulder for conversation and eyeline;
single / medium close-up for dialogue and performance; close-up for
emotional reaction; insert / cutaway for important action or detail).
The scene breakdown decides which types the scene needs; do not force
every type into every scene.

Continuity holds, in addition to the 180-degree rule: the 30-degree
guideline (a cut between two shots of the same subject should change the
camera angle by at least 30 degrees, or it reads as a jump); eyeline
matching; screen-direction consistency; action matching; spatial
continuity; shot-reverse-shot consistency. The 180-degree rule and the
30-degree guideline are creative guidelines, not absolute restrictions —
an intentional violation is permitted when the reason is clear and
recorded; an accidental violation is a defect.

Direct performance with playable actions, not emotion labels alone.
Instead of just `angry`, direct: tightened jaw, shorter breathing,
delayed response, avoided eye contact, restrained hand movement. The
playable action is written into the shot list next to the line. The
words stay the user's, the face stays the character's, and the body
plays what the words mean.

## 3. Negative Prompt Library

Maintain a standing list of defects to prevent in every generation:

- Extra or missing fingers
- Distorted hands
- Merged or duplicated faces
- Warped limbs
- Extra characters appearing uninvited
- Unreadable or garbled text
- Broken objects
- Sudden outfit changes inside one scene

Apply this list as negative prompts or generation constraints wherever the
platform supports them, in addition to the scene-specific negative prompts
for that shot. The library is cumulative: when a new recurring defect is
found, add it to the list so it is prevented in every future generation,
not just the one where it appeared.

## 4. Sound Design System

Sound is half of realism. For every scene, plan the sound, not only the
picture: footsteps, water, birds, wind, room tone, doors, crowd sounds —
whatever the place would really sound like.

- Sound effects must match the action on screen in timing and in
  character. A footstep must land when the foot lands; a door must sound
  like the door on screen.
- A silent action scene or a mismatched sound breaks the human feeling
  immediately. Silence where sound is expected is a defect, not a neutral
  choice.
- Plan sound at the scene level, before generation, so the sound list is
  part of the scene plan rather than an afterthought.

## 5. Music and Theme

Each series has one fixed theme music and a consistent musical mood. Use
the same theme across episodes so the audience recognizes the series by
sound alone.

- Scene music must follow the scene's emotion: light for comedy, tense
  for danger, soft for sadness.
- Music must support the scene, never fight it. If the music draws
  attention away from the dialogue or the emotion, it is wrong for that
  scene.
- Keep the theme, the instrumentation, and the mood consistent across
  episodes; vary the arrangement to fit the scene, not the identity of
  the music.

## 6. Story Bible

Keep a story bible for each series: the rules of its world, its places,
its timeline, and what has happened so far. Character faces are only half
of consistency — the story must also stay consistent.

- Never contradict the story bible: a place destroyed in episode 2 must
  not appear intact in episode 5, and a fact established earlier must not
  be silently changed later.
- When the user deliberately changes a story fact, record the change in
  the story bible with the episode it changed in, so the change is
  intentional and traceable rather than an accident.
- The story bible is read before every new episode is planned.

## 7. Episode Continuity Tracker

After each episode, record what happened: key events, what each character
wore, injuries, gained or lost objects, and where each character ended up.
Read this record before starting the next episode.

- The next episode must continue from the recorded state.
- If the user changes something deliberately, record the change; never let
  an episode contradict an earlier one by accident.
- The tracker is the series memory. Without it, long series drift: outfits
  change, injuries vanish, objects appear and disappear for no reason.
- The tracker and the story bible are checked together before delivery
  (see item 11).

## 8. Dialogue Writing Rules

Dialogue must be natural spoken language, not bookish language.

- An 8-year-old speaks like an 8-year-old; an adult speaks like an adult;
  an elderly character speaks like an elderly person. Never give a child
  adult words.
- Keep lines short enough to speak naturally, with pauses where a human
  would pause.
- If a line sounds robotic when read aloud, rewrite it.
- Dialogue is written in the character's own language (see "Language,
  Captions, and Format Rules" in this documentation set), and each line
  carries its emotion so the performance follows the words.

## 9. Reference Photo Quality Rules

A good reference photo makes registration succeed. A good reference photo
is:

- Clear and sharp, with the face well lit.
- Face to camera, with a neutral expression.
- No sunglasses, masks, heavy shadows, or blur.
- The face fully in frame, not cropped off.

If a provided photo is unclear, dark, or cropped so the face is cut off,
tell the user and ask for a better photo instead of registering a weak
reference. A weak reference poisons every video that character appears in;
it is always better to ask for a better photo than to build a character on
a bad one.

## 10. Lip-Sync and Dubbing Workflow

Decide the order for each project before starting, and follow one order
consistently inside a project:

- **Voice first, then video** — record or generate the voice, then match
  the video to the voice; or
- **Video first, then voice** — generate the video, then match the voice
  to the video.

Dialogue timing must match the mouth: a line must not finish long before
or after the character stops speaking. If lip-sync is not supported on the
platform, say so honestly instead of promising it.

## 11. Episode QC Checklist

Before delivering any episode, check it against the full list. Do not
deliver an episode that fails a check without telling the user what failed.

- Character faces correct for every registered character.
- Character heights correct.
- Voices correct for each character.
- Emotions match the script, line by line.
- Dialogue exact — no dropped, added, or changed lines.
- No defects: no extra fingers, merged faces, warped limbs, or broken
  objects.
- Clothing correct for the scene.
- Sound and music present and matched to the action.
- No contradiction with the story bible or the episode continuity
  tracker.

Every failed check is either fixed before delivery or reported to the user
with the failure named plainly.

### QC severity

Every defect is graded on four levels, which decide whether the video
can be delivered:

- **Critical — release blocker.** Missing scene; corrupted video; wrong
  dialogue; wrong person or character; wrong action; broken export.
- **Major — release blocker unless explicitly waived.** Face morphing;
  broken physics; serious continuity defect; unusable lip-sync; serious
  VFX integration problem. A Major defect blocks delivery unless the
  authorised user explicitly waives it, with the waiver recorded (what
  was waived, why, and who authorised it).
- **Minor — repair where practical or document.** Small shot-matching
  issue; small graphic-alignment defect; minor colour inconsistency.
- **Polish — optional finishing enhancement.** Small timing improvement;
  minor typography refinement; optional finishing enhancement.

A defect with no severity assigned is a defect that has not been
triaged. The severity system applies here and, by reference, to the
video-regeneration QC pass, which reuses this checklist.

### Final delivery checklist

Before the master is handed over, verify every item: story completeness;
character consistency; action and physical realism; camera and lighting
continuity; dialogue and lip-sync; sound and music; colour consistency;
frame rate and resolution; codec and file integrity; full playback (the
whole video watched through, not sampled); backup and archive. A delivery
that has not had a full playback is not a delivery — it is a hope.

### Post-mortem

After a project with repeated generation failures, write a short
post-mortem and keep it with the project: what failed repeatedly; which
model or tool performed how; the common defects and their causes as far
as they could be determined; what was tried and what worked; what to do
differently next time. The next project should not pay for the same
failure twice.

## 12. Production Stage-Gate Workflow (G1–G6)

Every project runs through six stages in order. A stage is not finished
until its acceptance is met, and a failed stage must not silently advance
to the next one — the failure is fixed at that stage, or the stage is
explicitly waived, never quietly skipped.

- **G1 — Visual Planning.** Creative and technical brief; script and
  story breakdown; scene and shot list; Visual Style Bible; character
  and environment references; camera and composition plan; lighting
  plan where applicable; sound plan where applicable; continuity
  requirements; production restrictions. Acceptance: the production plan
  is sufficiently complete to start representative test shots.
- **G2 — Test Production.** Generate representative test shots; test
  character identity, camera framing and movement, lighting and
  composition, physical interactions, performance and lip-sync where
  applicable, visual quality and consistency. Acceptance: representative
  outputs are reviewed and approved. If a representative test fails,
  correct the production instructions before batch generation.
- **G3 — Editorial Review.** Select usable takes; build scene assembly;
  create rough cut; evaluate narrative clarity, pacing and shot coverage;
  check visual and audio continuity. Acceptance: the scene and story
  communicate the intended meaning.
- **G4 — Picture Lock.** Final shot order; final duration; dialogue
  timing; scene transitions; approved editorial changes; final timeline
  version. Acceptance: the picture is locked. Changes after picture
  lock require a revision record and another affected-stage review.
- **G5 — Finishing.** VFX and repair; colour correction; creative
  grading; sound design; audio mixing; graphics and typography; final
  audiovisual review. Acceptance: the master is ready for delivery QC.
- **G6 — Delivery.** Full playback; visual QC; audio QC; technical
  export verification; file integrity; project backup; archive; delivery
  approval. Acceptance: all Critical and Major defects are resolved or
  explicitly waived by the authorised user.

Every stage carries one status: NOT STARTED, IN PROGRESS, PASS, BLOCKED,
or WAIVED. A BLOCKED stage names what blocks it; a WAIVED stage names
the reason and who authorised it. A waiver requires explicit user
authorisation and a recorded reason — a waiver without a recorded reason
is not a waiver, it is a skipped stage, and it is not permitted.

Complexity-aware operation: simple shorts run a compact G1–G6 checklist
(one line per gate, no separate documents); regular episodes run the
complete production plan and test shots; complex cinematic projects run
detailed planning, multiple test shots, editorial review and finishing in
full. The gates are the same at every scale — only the paperwork shrinks.
Never omit essential quality checks merely to save time.

## 13. Production Complexity Tiers (P0–P3)

This is a production scope hierarchy — how much production craft a
project carries. It is NOT a replacement for the instruction-precedence
hierarchy in the "Production Priority Hierarchy" section above (user >
identity > story > realism > cinematography > quality), which still
governs whenever instructions compete. The tiers decide scope; the
hierarchy decides precedence.

- **P0 — Essential (required for every project).** Story clarity;
  correct scene and action; visual readability; character and object
  continuity; dialogue correctness; basic exposure and focus quality,
  where applicable; file integrity; backup; final QC.
- **P1 — Strongly Recommended (normal professional productions).**
  Composition; deliberate lighting; character performance; editing
  rhythm; shot matching; colour consistency; sound design; professional
  audio mixing.
- **P2 — Advanced (when the project requires and tools support them).**
  Advanced colour grading; complex VFX; simulation; detailed
  compositing; advanced motion control; complex camera setups.
- **P3 — Specialized (only appropriate productions).** Drone
  photography; specialty lenses; high-speed camera work; virtual
  production; advanced motion-control rigs; specialized compositing and
  simulation.

The tier is selected from the project scope, quality target, tools,
budget, and user requirements, and recorded in the project record. Do
not force P2/P3 work into every ordinary project. Never claim a
capability exists merely because it appears in a production plan — a
capability is claimed only when it has been verified.

## 14. Lighting Plan Template

Every scene that needs deliberate light carries a lighting plan, written
before generation and checked at every cut. Required fields: project ID;
scene ID; shot IDs; scene location; time of day; motivated light source;
light direction; key light; fill or negative fill; backlight / rim light;
hard or soft quality; intensity; colour temperature; contrast; shadow
depth; practical light sources; exposure intent; background separation;
visual reference; continuity notes.

Cover these situations with the template, each with its motivated source
and its look: natural daylight; window light; night interior; practical
lighting; thriller lighting; documentary lighting; stylized animation
lighting. Three-point lighting (key + fill + rim) is an available setup,
not a universal requirement. The lighting-continuity lock still applies
(see `docs/05-humanization-systems.md` §30.15): shadow direction, colour
temperature, and light-source position are fixed per scene and locked
across every shot. Do not force photographic equipment settings into AI
models that cannot control them: the plan records creative intent, and
only records a camera or light setting where the tool actually exposes
that control (see §15).

## 15. Camera Technical Profile

The camera system (§2) decides what the camera does creatively. The
technical profile records HOW it is done, and it is capability-aware: a
setting is recorded only where the tool that produces the footage actually
exposes it.

For footage captured with a real camera, the profile may record any of
these optional fields: camera; lens; focal length; aperture; shutter
speed or shutter angle; ISO or gain; white balance; focus; frame rate;
resolution; codec; colour profile; bit depth; exposure settings; backup
camera settings. Optional means optional — never invent a value after
the fact.

For AI-generated footage, keep three things strictly separate: (1)
creative camera intent — what the shot should look like; (2) native
provider controls — the controls the provider actually exposes for this
model; (3) post-production controls — what is done after generation
(crop, reframing, stabilisation, speed ramping, colour work). Never
pretend unsupported AI model parameters are real controls: a focal
length, an aperture value, or a shutter speed written into a prompt for
a model that does not expose it is a wish, not a setting.

## 16. Master Shot Tracker

One row per shot, all shots in the project, kept current through every
stage gate (§12). Required fields: project; scene; shot ID; shot purpose;
story beat; shot size and angle; camera movement; character references;
environment and prop references; lighting; audio requirements; prompt or
reference version; AI model and version; generation take; continuity
notes; production status; QC status; approval.

Production status vocabulary: PLANNED, TEST, APPROVED, GENERATING,
SELECTED, REJECTED, LOCKED. A shot is LOCKED only after picture lock
(G4); a REJECTED take stays in the tracker with its reason recorded.

A project workspace uses this folder template, adapted to the project —
it is a working-folder template, NOT a mandatory public Git folder
structure, and it never carries private data into the public repo:
`01_script/` (script, breakdown, shot list); `02_references/` (style,
environment and prop references); `03_characters/` (character reference
material — private data stays private, never committed to the public
repo); `04_tests/` (test shots and G2 results); `05_shots/` (generated
takes); `06_edit/` (assembly, rough cut, fine cut, picture lock);
`07_finish/` (colour, sound, graphics, masters); `08_delivery/` (final
exports, delivery checklist, post-mortem); `99_records/` (Master Shot
Tracker, cost log, provenance log, backup log).

Generated files and takes are named
`PROJECT_S03_SH012_TK02_V003_YYYYMMDD.ext` — project code, season, shot
number, take number, version, date.

## 17. Genre-Specific Skill Selection

Do not create duplicate genre skills — there is one skill per craft, and
the genre decides which crafts are brought in. This matrix is optional:
it suggests which existing skills a genre normally needs. The user's
chosen style and script always take precedence over the matrix.

| Genre | Skills usually brought in |
|---|---|
| Documentary | cinematic-power, production-systems, voice-consistency |
| Geopolitics / investigative explainer | explainer-animation, cinematic-power, production-systems |
| Informative explainer | explainer-animation, production-systems, voice-consistency |
| Drama | emotional-performance, production-systems, humanized-production |
| Thriller | cinematic-power, emotional-performance, production-systems, live-action-vfx |
| Action | live-action-vfx, cinematic-power, production-systems |
| 2D animation | kids-family-animation, explainer-animation, production-systems |
| 3D animation | kids-family-animation, cinematic-power, production-systems |
| Commercial | agency-advertising, production-systems, cinematic-power |

Do not force a thriller visual style into a documentary, and do not
force cartoon exaggeration into photorealistic footage: the genre sets
the palette, but the script and the locked style set the rules. When
the matrix and the user's instruction disagree, the user's instruction
wins.

Production Addendum 01 (2026-11-26) deepens the systems above with
workflow and template extensions (§§12–17, the §2 director's extension,
the §11 severity extension); it adds no new numbered entries, so the
repo's 109 distinct systems / 120 numbered entries are unchanged.
