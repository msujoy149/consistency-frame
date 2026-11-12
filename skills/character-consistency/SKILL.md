---
name: character-consistency
description: Keeps every registered character visually identical across all videos and episodes. Covers the character registry and registration rules, identity resolution from script names, the fixed prompt block and seed per character, 100% reference fidelity with character recall, fixed identity structure with scene-variable clothing, multi-character scenes with no overlap, and private per-character data separation.
---

# Character Consistency

This skill makes one promise and keeps it: a registered character must look like the same person in every video, every episode, every scene, and every camera angle. Clothing, lighting, location, activity, and expression may change. The face, body, height, and defining physical features must not.

## 1. Character Registry

Every permanently registered character lives in its own folder under the character registry (for example `characters/<character-id>/`).

Each character folder contains:

- `character.yaml` — the character record, with at least: name, unique ID, age, gender, a written description of the look (face shape, facial proportions, eye shape and colour, nose and lip structure, jawline and cheek structure, skin appearance, hair characteristics, body structure and proportions, distinctive physical features), and a voice profile (voice ID, language, tone, apparent age — see the `voice-consistency` skill).
- `seed` — one fixed generation seed for the character, recorded in `character.yaml` and used in every generation of that character.
- Reference images — 3–4 images as a minimum: front view, three-quarter view, full body, and an expressions sheet. More angles make the stored character more reliable; a single front photo is the weakest reference set. Keep the original reference image as the primary identity reference and never replace it with a newly generated interpretation.
- Voice reference audio — a clean reference recording of the character's voice (see the `voice-consistency` skill).
- A fixed prompt block — a short, stable text block describing the character's fixed identity (face, height, proportions, defining features). It is injected into every generation of that character.

Never modify or delete an existing character record without the user's explicit authorization. Never reset the whole registry when adding a character. Never overwrite one character's information with another character's information.

## 2. Registration Rules — All Three Conditions Required

A character is permanently registered only when ALL three conditions are met. Uploading an image alone does NOT register a character.

1. **Reference image(s).** The user provides one or more reference images of the character.
2. **Name and unique ID.** The user's message explicitly provides the character's matching name and a unique character ID.
3. **Explicit authorization.** The user clearly authorizes permanent registration, for example with "Register this character permanently" or "Save this character in my permanent Character Database."

If even one condition is missing: do not register the character, do not silently add it to the registry, do not invent the missing details — ask the user for the missing information or authorization.

**Name on the image.** A character name visibly written ON the reference image is NOT mandatory. It is sufficient for the user to state in the message which character the image(s) belong to (for example, "these are Serena's pictures" or "this is Robin's character picture"). A name written on the image is recommended, because it makes identification more reliable. It IS required only when several characters' images are uploaded together in one batch — in that case the name on each image (or a clear per-image statement of whose it is) is needed so the character images can be told apart.

**Duplicates.** When a new character is added, check whether the name or ID already exists. If a name belongs to exactly one registered character, the name alone is sufficient to identify it. If multiple registered characters share the same name, the user must provide the unique ID; if the ID is missing, ask which character is intended. A valid unique ID alone is sufficient. If the user provides both a name and an ID, verify that they refer to the same record; if they conflict, stop and request clarification. If an ID is already assigned to another character, request a new unique ID. A duplicate name with a different ID is not an error by itself — it is a prompt to stop and ask.

An uploaded image may be used temporarily for a current video task without becoming a permanent character. Permanent registration and temporary image usage must always remain separate.

**Reference photo quality.** A good reference photo makes registration succeed: the face must be clear and well lit, facing the camera, with a neutral expression, without sunglasses, masks, heavy shadows, or blur. If a provided photo is unclear, dark, or cropped so the face is cut off, tell the user and ask for a better photo instead of registering a weak reference.

## 3. Identity Resolution

The user may identify a registered character in a script using its name, its unique ID, or both. Recognize character names naturally within sentences, scripts, and dialogue — for example, "Robin is walking through a beautiful garden" or "Robin meets Daniel near the railway station" — without requiring the user to repeat technical identification instructions.

When a name appears in a script, resolve it to that character's full record: unique ID, reference image(s), voice profile, and fixed prompt block. In a multi-character scene, resolve each character separately, so that each character keeps its own face, voice, and prompt block and the characters do not merge into each other. Never confuse two characters or substitute one character for another.

## 4. Prompt Builder

For every generation involving a registered character, inject that character's fixed prompt block and fixed seed. The prompt block is the same in every generation; only the scene-specific text (location, action, camera, emotion, clothing for the scene) changes around it. Record the model and version used, the prompt, the seed, the reference image, the voice profile, and the date for every shot, so any shot is reproducible and any drift can be traced to what changed.

## 5. 100% Reference Fidelity — Face and Height Matter Most

Build the character 100% from the reference image(s) provided. The face and the height are the most important identity features and must match the reference as closely as the platform allows.

- One reference photo is enough to register a character; several photos (for example five, from different angles) make the stored structure more reliable. In either case, the stored character is defined by the reference image(s) given.
- The stored structure — face, height, proportions, and all preserved features — is fixed. It must stay consistent in every later video, and the user must be able to verify it.
- Preserve in every scene: face shape, facial proportions, eyes and eye placement, nose and mouth structure, jawline and cheek structure, skin appearance and natural characteristics, hair identity and distinctive features, body structure, height proportions, and overall physical build.
- The character must remain visually recognizable even when the location, lighting, camera angle, activity, clothing, environment, or facial expression changes. Do not generate a different-looking person simply because the scene or clothing has changed. Do not unnecessarily redesign the face, body, or defining physical features. Character identity takes priority over stylistic variation.

## 6. Character Recall — Show the Stored Character on Request

When the user asks how a character is stored, what its structure looks like, or to see the character again, generate and show a picture of the character exactly as stored — a character sheet / reference render — so the user can check that the face, height, and structure are the ones they gave. Do this from the stored reference data, not from a fresh reinterpretation.

Keep a model sheet for each registered character — front view, three-quarter view, full body, and expression sheet — built from the reference image(s). Check every new scene against the model sheet, not only against a single photo, so the face, height, and body stay the same from every angle.

## 7. Identity Structure Fixed, Clothing Variable

The reference image's identity structure — eyes, nose, mouth, face, hands, feet — stays the same in every scene. Clothing, footwear, accessories, hairstyle (where appropriate), makeup (where appropriate), posture, and facial expression change with the scene.

The character's outfit must match the scene, activity, weather, environment, and social context:

- Climbing a tree — one outfit, suitable for climbing.
- Swimming — appropriate swimwear.
- Teaching in a classroom — suitable professional clothing.
- Attending a formal event — suitable formal clothing.
- Exercising — appropriate sportswear.
- Walking in cold weather — weather-appropriate clothing.

Never force the original reference-image outfit into every new scene. The permanent physical identity stays consistent while appearance and attire adapt naturally to the story.

## 8. Multi-Character Scenes and No Overlap

Several characters may appear together in one scene — for example three, four, or five friends at a party. That is fully supported, provided each character is resolved separately (Section 3) and each keeps its own identity.

Natural physical contact is allowed: one character may put a hand on another's shoulder, hold another's hand, or touch another's hair. Contact is on the surface; bodies stay separate and solid.

But one character or object must NEVER go inside another character or object: no overlapping, no merged bodies, no merged faces, no hand passing through a body, no head inside another head. During handshakes, conversations, walking together, hugging, dancing, or other interactions, maintain accurate physical positioning, realistic distances, appropriate personal space, and anatomically believable contact. Never allow one character to unintentionally transform into another. Check every multi-character shot for overlap before delivery.

## 9. Private Character Data Separation

Each character's data — reference images, character file, voice reference audio, prompt block — is stored separately, in that character's own folder, private by default. Character data is never published, shared, or committed to a public place without the user's explicit permission.

In a public repository, character data lives in a separate private overlay, never inside the public files. A character is used alone or together with other characters only as the user requests.

## 10. Quality Control for Characters

Before delivering any episode, check: character faces and heights are correct against the model sheet; no character has drifted, been substituted, or merged with another; no extra fingers, missing fingers, distorted hands, deformed faces, or unnatural eyes; clothing is correct for the scene; no contradiction with the story bible or the episode continuity tracker. Do not deliver an episode that fails a check without telling the user what failed.

Measure face similarity between the reference image and each generated frame or clip (a face-embedding similarity score) and keep it above the project's threshold. If the score falls below the threshold, regenerate. Record the score in the shot's provenance log. Do not judge character consistency by eye alone.
