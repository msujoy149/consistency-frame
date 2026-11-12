# Additional Systems

These systems cover privacy, multi-character scenes, intake, the demo,
scripts, contributions, and script-driven realism and colour grading.

---

## 1. Private Character Data Separation

Each character's data — reference images, character file, voice reference
audio, prompt block — is stored separately, in that character's own
folder, private by default.

- Character data is never published, shared, or committed to a public
  place without the user's explicit permission.
- In a public repository, character data lives in a separate private
  overlay, never inside the public files. The public repo contains the
  system, the skills, and the documentation; it contains no character
  images, no voice references, and no prompt blocks.
- A character is used alone or together with other characters only as
  the user requests.
- The private overlay design is described in full in "Character Registry"
  in this documentation set.

## 2. Multi-Character Scenes and No Overlap

Several characters may appear together in one scene — for example three,
four, or five friends at a party. Multi-character scenes are fully
supported; the rule below is about physics, not about cast size.

- Natural physical contact is allowed: one character may put a hand on
  another's shoulder, hold another's hand, or touch another's hair.
- But one character or object must NEVER go inside another character or
  object: no overlapping, no merged bodies, no merged faces, no hand
  passing through a body, no head inside another head.
- Contact is on the surface; bodies stay separate and solid.
- Check every multi-character shot for overlap before delivery. Overlap
  is a defect and is caught by the episode QC checklist (see
  "Professional Production Systems"), not tolerated as a minor flaw.

## 3. Episode Intake Checklist

Before generating an episode, go through one checklist and ask the user
everything that is still open, in one go:

- Which characters are in the episode.
- Each character's language.
- Whether captions are wanted, and in which language.
- The aspect ratio and platform.
- Short or long video.
- The script.

Rules for the checklist:

- Do not ask the same question twice. If the user has already answered
  something, it is recorded and not asked again.
- Do not start generating while a needed answer is missing.
- Ask only for what is still open; if the script already answers
  everything, there is nothing to ask.

## 4. Demo Project

Keep a small demo ready — one sample character and one sample episode
script — so a new user can see how the system works.

- If the user wants a demo video, generate the demo so they can see the
  system working.
- If they do not want a demo, work directly on their real project.
- A demo is offered, never forced.
- **No demo content is shipped in this repository.** The demo is an
  on-demand system only: the sample character and sample episode exist
  when the user asks for a demo, and are not bundled into the public
  repo.

## 5. Script Template and Script Enhancement

Scripts are written in a fixed format:

- Scene
- Characters present
- Dialogue per character
- Camera
- Emotion per line

Script enhancement is automatic: if the user's script is weak — flat
dialogue with no feeling — improve it automatically. Add emotion, natural
pauses, reactions, and lively expression so the video has feeling, while
keeping the story, the meaning, and the user's dialogue intact.

- Never change the story to add emotion; add the feeling to the story the
  user gave.
- The enhancement keeps the user's lines recognizable. It adds the
  pauses, the reactions, and the emotional colour that make a line
  performable; it does not rewrite the story into a different one.
- A video with no feeling is a failed video. Feeling is not decoration —
  it is the point of the scene.

## 6. Contribution Guide

This project is open source, so contributors are welcome. Contributors
must follow these rules:

- Keep the character consistency rules intact.
- Never weaken the safety rules — including the child-safety rules and the
  real-person safeguards.
- Describe every change.
- Test before submitting.
- Keep the licence and attribution intact.

Changes that break characters, voices, or safety are not accepted. A
contribution that makes a video look better but makes a character less
recognizable is a regression, not an improvement.

## 7. Script-Driven Realism and Colour Grading

Characters must look realistic in every scene — real skin, real light on
the face, real shadows — never flat or cartoon-like unless the user asked
for a cartoon style.

Colour grading is professional and follows the script, not a random look.
The grade is decided by the time of day and the light source in the
scene:

- **Full-moon night** — cool blue moonlight grade.
- **Bright sunlight** — warm daylight grade.
- **Evening** — soft warm evening grade.
- **Morning** — fresh morning light grade.
- **Dusk** — orange-purple twilight grade.
- **Midnight** — deep dark grade.
- **Torch or flashlight at night** — warm torch light with real shadows
  on the character and the surroundings.

Rules that hold for every scene:

- The grade never changes randomly from one shot to the next inside the
  same scene.
- The character's skin and clothes always match the light of the scene
  they are in.
- Every scene must look believable, as if it was really filmed in that
  light.
- The grading rule works together with the lighting-continuity lock in
  "Humanization Systems": grading sets the look of the light, the lock
  fixes where the light comes from in every shot.
