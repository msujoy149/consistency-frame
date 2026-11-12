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
    voice-reference.mp3     # voice reference audio
```

`character.yaml` example:

```yaml
id: char-riya-001
name: Riya
age: 8
gender: female
look: >
  8-year-old Bengali girl, round cheerful face, big dark eyes,
  shoulder-length black hair, same face in every shot
voice:
  tags: "child, female, high pitch"
  seed: 11
  language: bn
  ref_audio: voice-reference.mp3
```

## Registration rules

Registering a character takes all three of these, in one go:

1. **Reference image(s)** — 3–4 photos (front, 3/4, full body,
   expressions). Clear, well-lit, face to camera, neutral expression.
   A name written on the image is **not** mandatory: if you give photos
   and say in your message whose they are ("these are Serena's
   pictures"), that binds them. A name on the image is required only
   when several characters' images are uploaded together in one batch.
2. **Name + unique ID** in the message. A duplicate name with a
   different ID stops the registration and asks you first.
3. **Explicit authorisation** — e.g. "Register this character
   permanently." Uploading an image alone does not register a character.

## How identity is resolved

A name in a script resolves to that character's ID + reference image +
voice + prompt block. Each character is resolved separately, so faces
never merge in multi-character scenes. The character is built 100% from
the reference image(s); face and height matter most. On request, the
system shows the character exactly as stored, so you can check face,
height, and structure.

Identity structure is fixed — eyes, nose, mouth, face, hands, feet stay
the same in every scene — while clothing and props change with the scene.

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
