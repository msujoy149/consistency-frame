---
name: realistic-person
description: Turns a real person's photo into a realistic video of that person moving and speaking naturally — the face never changes, only movement and speech are added. Real skin, hair, and cloth; natural light; lip-sync matched to the language's sounds; never a still mouth.
---

# Realistic Person Video — From a Photo to a Real Moving Person

A real person's photo becomes a realistic video of that person moving and speaking naturally, like a normal real person. The photo is used exactly as given — the face, structure, hands, and feet never change. Only movement and speech are added. This is not 2D or 3D animation, and not live-action footage of a real shoot: it is a realistic video generated from a still photo of a real person.

## 1. Intake — A Real Person's Photo

The user supplies a real person's photo: clear, well-lit, face to camera. The photo is used exactly as given (see the `character-consistency` skill — the Character Generator's user-supplied picture rule). One clear photo is enough; several angles are more reliable. A real person's photo and voice need consent: clone or animate a real person only with that person's permission, for the agreed use, with a consent record (see the `voice-consistency` skill, §13). Never animate a real person without permission.

## 2. Identity — The Face Never Changes

The person in the photo stays that person. Face, structure, hands, and feet are unchanged in every shot. Never beautify, reshape, slim, age, or redesign the face. Never swap the face onto another body. Verify every shot against the supplied photo before delivery — if the face has drifted, regenerate the shot, never deliver it.

## 3. Natural Movement — Like a Normal Real Person

The person moves the way a normal real person moves: walks, gestures, head turns, blinks, posture shifts, weight shifting from one foot to the other. Movement is motivated by what the person is doing and saying, never posed for the camera. Never stiff, never frozen between lines, never cartoonish — no squash-and-stretch, no exaggerated expressions, no floating. The body has weight: steps land, clothes settle, hair follows the head.

## 4. Natural Speech — In the Person's Own Language

The person speaks in their own language, following that language's native pattern (see the `language-authenticity` skill): US English carries the American tone, Bengali the Bengali tone, Hindi the Hindi tone — never stiff textbook speech. The voice belongs to that person (a supplied voice recording, or the voice the user approved for them — see the `voice-consistency` skill, §13). Lip-sync follows the sounds of the language being spoken: English, Bengali, and Hindi move the mouth differently. Verify every line's mouth movement against its own audio track. A talking person with a still mouth is a defect — never deliver it.

## 5. Realism — Real Skin, Real Light, Real Cloth

Real skin with texture, real hair that moves with the head, cloth that folds and settles with the body. Natural light that matches the scene's time of day and light source. No plastic skin, no airbrushed face, no cartoon look, no glossy sheen. Realism target 100%, with 99.9% as the floor: no detail skipped, no defect accepted. Backgrounds are detailed, deep, and alive, like the rest of the video (see the `humanized-production` skill).

## 6. What It Is Not

- **Not 2D/3D animation.** The person is not a cartoon, a stylized CG character, or an anime figure. If the user asks for animation, use the `cinematic-power` skill's style lock (2D anime, 3D stylized CG) instead.
- **Not live-action footage of a real shoot.** No camera crew, no set, no filmed performance. If the user supplies real footage, use the `live-action-vfx` skill instead.
- **Not a new person.** The video shows the person in the supplied photo — never a lookalike, never a redesigned version of them.

## 7. QC — Face, Movement, Lip-Sync, No Defects

Before delivering any realistic person video, run all four checks:

- **Face vs the supplied photo** — the face, structure, hands, and feet match the photo in every shot.
- **Movement naturalness** — the person moves like a normal real person: no stiffness, no freezing, no cartoon motion.
- **Lip-sync per line** — the mouth matches the audio of that line, in that line's language. A still mouth, a mistimed line, or mouth shapes from another language fails the check; regenerate the line, do not accept the defect.
- **No defects** — no extra fingers, no merged faces, no bent limbs, no broken objects, no warped hands.

Do not deliver a video that fails any check without telling the user what failed.

## 8. Honest Limits — Say Plainly What Cannot Be Done

If the platform cannot generate realistic video from a still photo, say so plainly instead of promising it — and say what it can do instead (for example, a still image with voice, or a stylized version). Never claim a video is a realistic moving person when it is a slideshow with a voiceover. Never claim the face is unchanged without the face-vs-photo check to back it.
