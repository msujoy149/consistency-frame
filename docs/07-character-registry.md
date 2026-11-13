# Character Registry

The Character Registry is how Consistency Frame knows who a character
is — their face, their height, their voice, and the exact prompt block
that rebuilds them in every scene. A character that is not registered
cannot be kept consistent, and a character that is registered wrongly
will be wrong in every video that uses them.

## Per-Character Folder Layout

Each character lives in their own folder inside the private overlay (see
"Private Overlay Design" below). The layout is:

```
characters/<character-id>/
  character.yaml        # name, unique ID, age, gender, look, voice profile, seed
  reference-front.jpg   # front view
  reference-three-quarter.jpg
  reference-full-body.jpg
  reference-expressions.jpg  # expression sheet
  expressions/              # expression library — one file per expression
                            # (<expression-name>.jpg); grows on demand, see
                            # "Expression Auto-Generation and Library"
  model-sheet.jpg           # turnaround (front/side/back) + detail panels
                            # (face, hands, feet) — the identity anchor
  voice-reference.mp3   # voice reference audio
```

`character.yaml` records, at minimum:

- `name` — the character's name.
- `id` — the unique character ID.
- `age` — the character's age.
- `gender` — the character's gender.
- `look` — the fixed identity description (face, eyes, nose, mouth,
  hair, build, height, distinctive features).
- `voice_profile` — the voice profile name, tags, seed, and reference
  audio file.
- `seed` — the generation seed used for the character.

3–4 reference images are kept per character: front, three-quarter, full
body, and expressions. One photo is enough to register a character;
several photos (for example five, from different angles) make the stored
structure more reliable. The model sheet (front, three-quarter, full
body, expression sheet) built from these images is the working reference
for generation.

## Registration Rules

A character can be permanently registered only when ALL of the following
are present:

1. **Reference image(s)** — one or more reference images of the
   character.
2. **Name and unique ID** — the user's message explicitly provides the
   character's matching name and a unique ID.
3. **Explicit authorization** — the user clearly authorizes permanent
   registration, for example "Register this character permanently."

If even one condition is missing: do not register the character, do not
silently add the character to the registry, do not invent missing
registration details — ask the user for the missing information or
authorization.

Uploading an image alone does NOT register a character. An uploaded image
may be used temporarily for a current video task without becoming a
permanent character. Permanent registration and temporary image use must
always remain separate.

### Name on the image

A character name visibly written ON the image is NOT mandatory. If the
user gives photos and says in the message whose they are (for example,
"these are <character-name>'s pictures"), that binds the images to that character.

- A name written on the image is recommended, because it makes
  identification more reliable.
- A name on the image is REQUIRED only when several characters' images
  are uploaded together in one batch — in that case the name on each
  image (or a clear per-image statement of whose it is) is needed so the
  system can tell which image belongs to which character.

### Duplicate names

- If a name belongs to exactly one registered character, the name alone
  is sufficient to identify them.
- If multiple registered characters share the same name, the user must
  provide the unique ID. If the ID is missing, ask which character is
  intended.
- A valid unique ID alone is sufficient to identify its character.
- If the user provides both a name and an ID, verify that they refer to
  the same record. If they conflict, stop and request clarification.
- **Duplicate name with a different ID → stop and ask.** If an ID is
  already assigned to another character, request a new unique ID. Never
  overwrite one character's record with another's, and never reset the
  whole registry when adding a new character.

## Character Generator — Two Ways to Create a Character

A character enters the registry in one of two ways. Both end in the
same place: a registered character with a name, a unique ID, an
approved reference, and explicit authorization (see "Registration
Rules").

### 1. User-supplied reference

When the user gives a picture and says "use this as my character",
use exactly that picture — that character — as the reference. Do not
reinterpret it, redraw it, or replace it with a generated look. The
supplied picture IS the character; the registration rules then apply
(name + unique ID + explicit authorization) before it becomes
permanent.

### 2. AI-generated on request

The user does NOT have to supply all reference pictures. When asked,
the AI generates a character itself — from the user's description —
and SHOWS it to the user first ("this is how the character looks
now") for review. The user may ask for changes, and the AI shows the
revised version again.

Only if the user likes it and says "done — use this one" (explicit
approval to use that generated version) does it become the registered
character under that name and ID. From then on, forever, that
character keeps the same structure in every scene and episode —
structure locked from the approved version; clothing and props still
vary per scene (see "Identity Structure: Fixed vs. Scene-Variable"
and "Identity Anchoring").

### Approval gate

No generated character becomes permanent without the user's explicit
"done" approval. A generated character shown for review is a draft,
not a registration. After approval it enters the Character Registry
like any registered character: name + unique ID + approved reference
image + authorization. A generated character is never silently
substituted for an approved one, and an approved character is never
quietly replaced by a new generation.

## Identity Resolution

A name in a script resolves to that character's ID + reference image +
voice + prompt block. Each character is resolved separately, so faces
don't merge.

- Recognize character names naturally within sentences, scripts, and
  dialogue — for example, "<character-name> is walking through a beautiful garden"
  or "<character-name> meets <another-character-name> near the railway station." The intended
  registered character is identified without requiring the user to repeat
  technical identification instructions.
- Never confuse two characters or substitute one character for another.
- When a scene has several characters, resolve each one separately from
  its own folder, its own reference images, and its own voice profile,
  before any generation starts. Merged faces and swapped voices come
  from resolving characters together; separate resolution is what
  prevents them.

## Identity Structure: Fixed vs. Scene-Variable

The character's identity structure is FIXED — it stays the same in every
scene:

- Face, eyes, nose, mouth, hands, feet — and the face shape, facial
  proportions, jawline, cheek structure, skin appearance, hair identity,
  body structure, and height proportions.

Clothing and props CHANGE with the scene:

- Outfit, footwear, accessories, hairstyle where appropriate, makeup
  where appropriate, posture, and facial expression follow the scene,
  activity, weather, environment, and social context.
- A character swimming wears swimwear; a character at a formal event
  wears formal clothing; a character in cold weather wears
  weather-appropriate clothing. The outfit always matches the scene — it
  never changes the identity underneath it.

The character must remain visually recognizable even when the location,
lighting, camera angle, activity, clothing, environment, or expression
changes. Do not generate a different-looking person simply because the
scene or clothing has changed. Character identity takes priority over
stylistic variation.

## Outfit Consistency — Script-Driven

Clothing is scene-variable, but it is never random. Outfits follow the
script and the user's instruction — nothing else.

1. **Selected outfit stays consistent.** The outfit the user selects
   or gives for a character is used exactly as-is in every scene,
   until the user says to change it.
2. **Scene-driven change allowed.** When the script clearly needs it
   (for example, the character goes swimming, so the outfit changes
   for that scene), the outfit may change for that scene.
3. **After a change, the new outfit holds.** The changed outfit then
   stays consistent in that context — it does not change randomly
   again.
4. **Script-driven only.** An outfit changes only on the user's word
   or a clear scene need — never randomly, never by the AI's own
   choice.

The current outfit per character per scene is recorded in the wardrobe
registry (docs/02-extended-systems.md, item 4); the continuity tracker
and the QC check verify clothing against it in every shot.

## 100% Reference Fidelity

The character is built 100% from the reference image(s) provided.

- Face and height are the most important identity features and must match
  the reference as closely as the platform allows.
- One reference photo is enough to register a character; several photos
  (for example five, from different angles) make the stored structure
  more reliable.
- The stored structure — face, height, proportions, and all preserved
  features — is fixed. It must stay consistent in every later video, and
  the user must be able to verify it.
- Never replace an existing character's original identity with a newly
  generated interpretation.
- Never modify or delete an existing character record without the user's
  explicit authorization.

## Identity Anchoring

Every generation of a registered character reuses the same approved
reference: the same reference images, the same turnaround + detail
sheet, the same fixed prompt block, and the same seed. The identity is
never rebuilt from a fresh interpretation, and a new render is never
treated as the reference.

The structure must stay 100% identical across scenes and episodes —
face, eyes, nose, mouth, hands, feet, proportions, height. If a render
drifts from the sheet, regenerate against the sheet; do not accept the
drift and do not quietly update the stored identity to match it.

## Turnaround and Detail Reference Sheet

Every registered character gets one turnaround + detail sheet, built
from the reference images and stored in the character's folder as
`model-sheet.jpg`. It is the identity anchor for every scene:

- **Turnaround:** head-turn views — front, 3/4 left, left profile,
  back, right profile, 3/4 right.
- **Expression sheet:** twelve expressions — Neutral, Smile, Laugh,
  Excited, Curious, Surprised, Worried, Determined, Sad, Tearful,
  Angry, Thinking.
- **Detail panels:** close-ups of the face, hands, and feet.

Check every new scene against this sheet, not only against a single
photo, so the face, height, and body stay the same from every angle.
The sheet is built once from the approved references; it is updated
only when the user explicitly authorizes a change to the stored
identity, and the change is recorded.

## Face-Consistency Correction Method

When a face drifts, fix it with this loop — it is the method that
works. Use it for every generation, not only after a drift is noticed.

1. **Definitive reference.** One user-approved image per character is
   the anchor. EVERY generation re-uses it as an identity reference —
   never generate a character without it.
2. **Front-facing for face-critical shots.** For shots where the face
   matters, the face is toward the camera, looking directly at it. A
   fully visible face anchors identity; profile and three-quarter
   angles drift the face more, so use them only when the script needs
   them.
3. **Explicit no-change instruction in every prompt.** Every prompt
   states it: face and structure 100% identical; do not change the
   face.
4. **Fresh generation, never edit, when the face drifts.** Never
   continue from a drifted image — never edit, inpaint, or "fix" the
   drifted render. Regenerate from the approved reference.
5. **Verify before delivering.** Compare the new face against the
   definitive reference before delivering; if it drifted, repeat the
   loop.

## Reference Matching and Angle-Matched Verification

### Reference matching is mandatory

Every generation is matched against the approved reference FIRST,
then made. No exceptions. Before generating a shot, re-inject the
reference images, the turnaround + detail sheet, the fixed prompt
block, and the seed (see "Identity Anchoring"), and check the planned
shot against them.

### Script-driven angle and expression

The angle (front, back, profile) and the expression (laughing, sad,
determined, and so on) follow the script and the prompt — whoever
instructs decides. The script chooses the angle and the expression;
the reference anchors the identity inside that choice. This is
explicit: the angle and expression are never chosen at random, and
never defaulted to a "safe" front view when the script asks for
something else.

### Angle-matched verification

When verifying a generated shot, compare it against the reference
sheet's MATCHING-angle view — not against the front view only. The
character sheet carries head-turn views: front, 3/4 left, left
profile, back, right profile, 3/4 right. A left-profile shot is
verified against the left-profile view; a back shot against the back
view.

Compare an expression against the sheet's MATCHING expression panel.
The expression sheet carries twelve expressions: Neutral, Smile,
Laugh, Excited, Curious, Surprised, Worried, Determined, Sad,
Tearful, Angry, Thinking. A laughing shot is verified against the
Laugh panel; a sad shot against the Sad panel.

This complements the front-facing anchor rule ("Face-Consistency
Correction Method"): the front view anchors the identity, the script
chooses the angle and expression, and the matching reference panel
anchors the identity inside that angle and expression. If the matching
panel does not exist yet, build it from the approved reference before
verifying against it.

## Expression Auto-Generation and Library

Not every expression is in the supplied references — the system
handles that gap automatically.

1. **Generate the missing ones.** If the user does not supply all
   expressions, the assistant generates the missing ones itself —
   from the character's definitive reference, keeping face and
   structure 100% identical, changing only the expression. Each
   generated expression is verified against the definitive reference
   before it is saved (see "Face-Consistency Correction Method" and
   "Reference Matching and Angle-Matched Verification").
2. **Save each one into the expression library.** Each generated
   expression is saved into that character's expression library in
   the character's folder:
   `characters/<character-id>/expressions/<expression-name>.jpg` —
   using the canonical expression names (neutral, smile, laugh,
   excited, curious, surprised, worried, determined, sad, tearful,
   angry, thinking). The library lives with the character's data, in
   the private overlay — never in the public repository.
3. **Reuse, never regenerate twice.** Next time the same expression
   is needed, the assistant REUSES the saved one — never regenerates
   it. Check the library first; generate only what is missing.
4. **The library grows on demand.** The library grows one expression
   at a time, as scripts need them. A new expression is generated,
   verified, and saved the first time a script asks for it; after
   that it is part of the character's stored set.
5. **The library persists across sessions.** The saved library is
   what later work draws from. It must stay in the character's
   folder, visible and available to the assistant in later sessions,
   and it must survive across sessions — it is part of the character
   record, backed up with it.

## Character Recall

On request, the system shows the character exactly as stored so the user
can check face, height, and structure.

- When the user asks how a character is stored, what its structure looks
  like, or to see the character again, generate and show a picture of the
  character exactly as stored (a character sheet / reference render).
- The recall render is built from the stored reference images and the
  stored character file — it shows the character as registered, not a new
  interpretation.
- Recall is a verification tool: if the render does not match what the
  user gave, the registration is wrong and must be fixed before any
  video uses that character.

## Private Overlay Design

Character data is private by default and is NEVER committed to this
public repository.

- Each character's images, voice reference audio, and prompt block stay
  in that character's own folder.
- The private overlay is a separate private repository or a local folder.
  The installer links it in; the public repository never contains it.
- Character data is never published, shared, or committed to a public
  place without the user's explicit permission.
- Consent records for real people's photos and voices live in the private
  overlay with the character data, not in the public repository.
- Backups and versioning of character data (see item 11 in "Extended
  Production Systems") live in the private overlay as well. A change
  creates a new version; the old version is kept; a lost or corrupted
  character file is recoverable from the backup.

The public repository contains the system, the skills, and the
documentation. The private overlay contains the characters. That
separation is what makes the repository safe to publish.
