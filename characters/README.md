# Character Registry

This directory holds the character registry — one folder per character.
It ships **empty on purpose**: character data is private by default and
is never committed to this public repository.

## Per-character folder layout

```
characters/
  <character-id>/
    character.yaml          # name, unique ID, age, gender, look,
                            # voice profile, seed
    reference-front.jpg     # front view
    reference-three-quarter.jpg
    reference-full-body.jpg
    reference-expressions.jpg
    expressions/              # expression library — one file per expression
                            # (<expression-name>.jpg); grows on demand
    model-sheet.jpg           # turnaround (front/side/back) + detail panels
                            # (face, hands, feet) — the identity anchor
    voice-reference.mp3     # voice reference audio
```

`character.yaml` example:

```yaml
id: char-001
name: <character-name>
age: <age>
gender: <gender>
look: >
  <fixed identity description: face, eyes, nose, mouth, hair,
  build, height, distinctive features — the same in every shot>
voice:
  tags: "<voice tags>"
  seed: <seed>
  language: <language-code>
  ref_audio: voice-reference.mp3
```

## Turnaround and detail reference sheet

Every registered character gets one turnaround + detail sheet, built
from the reference images — the identity anchor for every scene:

- **Turnaround:** head-turn views — front, 3/4 left, left profile,
  back, right profile, 3/4 right.
- **Expression sheet:** twelve expressions — Neutral, Smile, Laugh,
  Excited, Curious, Surprised, Worried, Determined, Sad, Tearful,
  Angry, Thinking.
- **Detail panels:** close-ups of the face, hands, and feet.

Check every new scene against this sheet, not only against a single
photo, so the face, height, and body stay the same from every angle.
The sheet is stored in the character's folder as `model-sheet.jpg`. If
a new render does not match the sheet, the registration or the render
is wrong — fix it before any video uses that character.

Expressions the user did not supply are generated from the definitive
reference (face and structure unchanged), saved per character under
`expressions/<expression-name>.jpg`, and reused from then on — never
generated twice. See "Expression Auto-Generation and Library" in
`docs/07-character-registry.md`.

## Registration rules

Registering a character takes all three of these, in one go:

1. **Reference image(s)** — 3–4 photos (front, 3/4, full body,
   expressions). Clear, well-lit, face to camera, neutral expression.
   A name written on the image is **not** mandatory: if you give photos
   and say in your message whose they are ("these are
   <character-name>'s pictures"), that binds them. A name on the image is required only
   when several characters' images are uploaded together in one batch.
2. **Name + unique ID** in the message. A duplicate name with a
   different ID stops the registration and asks you first.
3. **Explicit authorisation** — e.g. "Register this character
   permanently." Uploading an image alone does not register a character.

A character can also be created the other way round: ask the AI to
generate one and show it to you first — it only becomes permanent
when you say "done — use this one". See "Character Generator" in
`docs/07-character-registry.md`.

## How identity is resolved

A name in a script resolves to that character's ID + reference image +
voice + prompt block. Each character is resolved separately, so faces
never merge in multi-character scenes. The character is built 100% from
the reference image(s); face and height matter most. On request, the
system shows the character exactly as stored, so you can check face,
height, and structure.

Identity structure is fixed — eyes, nose, mouth, face, hands, feet stay
the same in every scene — while clothing and props change with the scene.

Identity anchoring: every generation reuses the same approved
reference — the same reference images, the same turnaround + detail
sheet, the same fixed prompt block, and the same seed. The identity is
never rebuilt from a fresh interpretation. The structure must stay 100%
identical across scenes and episodes; if it drifts, regenerate against
the sheet.

## Private overlay (read this before adding a character)

Character data is **private by default**. Never publish, share, or
commit a character's images, voice, or prompt block to a public place
without that character owner's explicit permission.

In this public repo, character data lives in a **separate private
overlay**, not in this directory:

- Keep your characters in a private repository (or a local folder)
  with the same layout as above.
- Point the installer at it with `CONSISTENCY_FRAME_CHARACTERS` (a path
  to your private characters directory). The assistant reads registry
  entries from the overlay first, and from `characters/` only as a
  fallback.
- The `.gitignore` in this repo already ignores everything under
  `characters/*/` except this README and `.gitkeep`, so an accidental
  `git add` cannot publish your characters. Do not weaken that rule.

See `docs/07-character-registry.md` for the full registry design.
