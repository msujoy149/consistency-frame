# Professional Production Systems

These eleven systems are what turn an acceptable generated video into a
professional series. They apply to every project unless the user says
otherwise. Nothing here is optional decoration: each system exists because
skipping it is visible on screen.

Counting note: these 11 systems also appear as Part A of the
production-systems skill. Together with the 18 extended, 3
language/captions/format, 7 additional, 36 humanization, and 7 agency
advertising systems, the repo holds 82 distinct systems, presented as
93 numbered entries.

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
