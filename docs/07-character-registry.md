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
"these are Serena's pictures"), that binds the images to that character.

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

## Identity Resolution

A name in a script resolves to that character's ID + reference image +
voice + prompt block. Each character is resolved separately, so faces
don't merge.

- Recognize character names naturally within sentences, scripts, and
  dialogue — for example, "Robin is walking through a beautiful garden"
  or "Robin meets Daniel near the railway station." The intended
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
