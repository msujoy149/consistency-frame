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

**Name on the image.** A character name visibly written ON the reference image is NOT mandatory. It is sufficient for the user to state in the message which character the image(s) belong to (for example, "these are <character-name>'s pictures" or "this is <character-name>'s character picture"). A name written on the image is recommended, because it makes identification more reliable. It IS required only when several characters' images are uploaded together in one batch — in that case the name on each image (or a clear per-image statement of whose it is) is needed so the character images can be told apart.

**Duplicates.** When a new character is added, check whether the name or ID already exists. If a name belongs to exactly one registered character, the name alone is sufficient to identify it. If multiple registered characters share the same name, the user must provide the unique ID; if the ID is missing, ask which character is intended. A valid unique ID alone is sufficient. If the user provides both a name and an ID, verify that they refer to the same record; if they conflict, stop and request clarification. If an ID is already assigned to another character, request a new unique ID. A duplicate name with a different ID is not an error by itself — it is a prompt to stop and ask.

An uploaded image may be used temporarily for a current video task without becoming a permanent character. Permanent registration and temporary image usage must always remain separate.

**Reference photo quality.** A good reference photo makes registration succeed: the face must be clear and well lit, facing the camera, with a neutral expression, without sunglasses, masks, heavy shadows, or blur. If a provided photo is unclear, dark, or cropped so the face is cut off, tell the user and ask for a better photo instead of registering a weak reference.

## 3. Identity Resolution

The user may identify a registered character in a script using its name, its unique ID, or both. Recognize character names naturally within sentences, scripts, and dialogue — for example, "<character-name> is walking through a beautiful garden" or "<character-name> meets <another-character-name> near the railway station" — without requiring the user to repeat technical identification instructions.

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

Keep a turnaround + detail sheet for each registered character — head-turn views (front, 3/4 left, left profile, back, right profile, 3/4 right), an expression sheet (Neutral, Smile, Laugh, Excited, Curious, Surprised, Worried, Determined, Sad, Tearful, Angry, Thinking), plus close-up detail panels of the face, hands, and feet — built from the reference image(s) and stored in the character's folder as `model-sheet.jpg`. It is the identity anchor for every scene: check every new scene against the sheet, not only against a single photo, so the face, height, and body stay the same from every angle. If a render does not match the sheet, the render is wrong — fix it before any video uses that character.

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

## 11. Identity Anchoring — Same Reference, Every Generation

Every generation of a registered character reuses the same approved reference: the same reference images, the same turnaround + detail sheet (`model-sheet.jpg`), the same fixed prompt block, and the same seed. The identity is never rebuilt from a fresh interpretation, and a new render is never treated as the reference.

The structure must stay 100% identical across scenes and episodes — face, eyes, nose, mouth, hands, feet, proportions, height. If a render drifts from the sheet, regenerate against the sheet; do not accept the drift and do not quietly update the stored identity to match it. Re-anchor at every scene change: re-inject the reference, the sheet, and the prompt block before generating the next scene.

## 12. Character Generator — Two Ways to Create a Character

A character is created in one of two ways. Both end in the same registry entry: name + unique ID + approved reference + authorization.

### 12.1 User-supplied reference

When the user gives a picture and says "use this as my character", use exactly that picture — that character — as the reference. Do not reinterpret, redraw, or replace it with a generated look. The supplied picture IS the character.

### 12.2 AI-generated on request

The user does not have to supply all reference pictures. When asked, generate the character from the user's description and SHOW it to the user first ("this is how the character looks now") for review. Offer revisions; show each revised version again.

Only when the user says "done — use this one" does the generated character become the registered character under that name and ID. From then on, forever, that character keeps the same structure in every scene and episode — structure locked from the approved version; clothing and props still vary per scene (Sections 7 and 11).

### 12.3 Approval gate

No generated character becomes permanent without the user's explicit "done" approval. A generated character shown for review is a draft, not a registration. After approval it enters the registry like any registered character. Never silently substitute a generated character for an approved one, and never quietly replace an approved character with a new generation.

## 13. Outfit Consistency — Script-Driven

Clothing is scene-variable, but it is never random. Outfits follow the
script and the user's instruction — nothing else.

1. **Selected outfit stays consistent.** The outfit the user selects
   or gives for a character is used exactly as-is in every scene,
   until the user says to change it. Do not restyle it, recolour it,
   or swap it for a "better" outfit on your own.
2. **Scene-driven change allowed.** When the script clearly needs it,
   the outfit may change for that scene — for example, the character
   goes swimming, so the outfit changes for the swimming scene. The
   change follows the scene need, not a whim.
3. **After a change, the new outfit holds.** The changed outfit then
   stays consistent in that context — it does not change randomly
   again. A swimming outfit stays the swimming outfit for the whole
   swimming sequence; a formal outfit stays formal for the whole
   formal event.
4. **Script-driven only.** An outfit changes only on the user's word
   or a clear scene need — never randomly, never by the AI's own
   choice. Record the current outfit per character per scene in the
   wardrobe registry (see the `production-systems` skill) so every
   later shot can be checked against it.

## 14. Face-Consistency Correction Method

When a face drifts, fix it with this loop — it is the method that works. Use it for every generation, not only after a drift is noticed.

1. **Definitive reference.** One user-approved image per character is the anchor. EVERY generation re-uses it as an identity reference — never generate a character without it.
2. **Front-facing for face-critical shots.** For shots where the face matters, the face is toward the camera, looking directly at it. A fully visible face anchors identity; profile and three-quarter angles drift the face more, so use them only when the script needs them.
3. **Explicit no-change instruction in every prompt.** Every prompt states it: face and structure 100% identical; do not change the face.
4. **Fresh generation, never edit, when the face drifts.** Never continue from a drifted image — never edit, inpaint, or "fix" the drifted render. Regenerate from the approved reference.
5. **Verify before delivering.** Compare the new face against the definitive reference before delivering; if it drifted, repeat the loop.

## 15. Reference Matching and Angle-Matched Verification

### 15.1 Reference matching is mandatory

Every generation is matched against the approved reference FIRST, then made. No exceptions. Before generating a shot, re-inject the reference images, the turnaround + detail sheet, the fixed prompt block, and the seed (Section 11), and check the planned shot against them.

### 15.2 Script-driven angle and expression

The angle (front, back, profile) and the expression (laughing, sad, determined, and so on) follow the script and the prompt — whoever instructs decides. The script chooses the angle and the expression; the reference anchors the identity inside that choice. This is explicit: the angle and expression are never chosen at random, and never defaulted to a "safe" front view when the script asks for something else.

### 15.3 Angle-matched verification

When verifying a generated shot, compare it against the reference sheet's MATCHING-angle view — not against the front view only. The character sheet carries head-turn views: front, 3/4 left, left profile, back, right profile, 3/4 right. A left-profile shot is verified against the left-profile view; a back shot against the back view.

Compare an expression against the sheet's MATCHING expression panel. The expression sheet carries twelve expressions: Neutral, Smile, Laugh, Excited, Curious, Surprised, Worried, Determined, Sad, Tearful, Angry, Thinking. A laughing shot is verified against the Laugh panel; a sad shot against the Sad panel.

This complements the front-facing anchor rule (Section 14): the front view anchors the identity, the script chooses the angle and expression, and the matching reference panel anchors the identity inside that angle and expression. If the matching panel does not exist yet, build it from the approved reference before verifying against it.

## 16. Expression Auto-Generation and Library

Not every expression is in the supplied references — the system handles that gap automatically.

1. **Generate the missing ones.** If the user does not supply all expressions, generate the missing ones yourself — from the character's definitive reference, keeping face and structure 100% identical, changing only the expression. Verify each generated expression against the definitive reference before saving it (Sections 14 and 15).
2. **Save each one into the expression library.** Each generated expression is saved into that character's expression library in the character's folder: `characters/<character-id>/expressions/<expression-name>.jpg` — using the canonical expression names (neutral, smile, laugh, excited, curious, surprised, worried, determined, sad, tearful, angry, thinking). The library lives with the character's data, in the private overlay — never in the public repository.
3. **Reuse, never regenerate twice.** Next time the same expression is needed, REUSE the saved one — never regenerate it. Check the library first; generate only what is missing.
4. **The library grows on demand.** The library grows one expression at a time, as scripts need them. A new expression is generated, verified, and saved the first time a script asks for it; after that it is part of the character's stored set.
5. **The library persists across sessions.** The saved library is what later work draws from. It must stay in the character's folder, visible and available to the assistant in later sessions, and it must survive across sessions — it is part of the character record, backed up with it (see the `production-systems` skill, backup/versioning).
