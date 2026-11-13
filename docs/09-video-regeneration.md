# Video Regeneration

This document describes the video regeneration workflow of Consistency Frame: how an uploaded reference video is analysed in full and remade as a new, original video that preserves the reference's core story, emotional impact, narrative structure, and creative direction — with only minor or explicitly requested changes. The full rules are in the `video-regeneration` skill (`skills/video-regeneration/SKILL.md`); this document explains each part in full.

The reference is the user's own uploaded video, used as the analysis source. The output is a professionally produced alternative version of it — never a frame-for-frame copy, and never a copy of copyrighted footage. Working order, always: first analyse, then plan, then generate, finally inspect and correct.

Nothing in this workflow replaces the existing systems. Characters in the regenerated video are registered characters: identity anchoring, 100% reference fidelity, face-consistency correction, angle-matched verification, and the expression library (`docs/07-character-registry.md`) all still apply, unchanged. Outfits follow the outfit-consistency rules. Camera angles follow the script-driven automatic camera angles system (A12 in the `production-systems` skill): each shot's angle is chosen from its beat, whether the script is supplied or generated. Voices follow the voice-consistency rules. This document adds only the regeneration workflow on top of that foundation.

Counting note: this 1 system is part of the repo total. Together with the 12 professional, 18 extended, 3 language/captions/format, 7 additional, 36 humanization, 7 agency advertising, 5 cinematic power, 6 live-action & VFX, 7 emotional performance, 1 user-supplied voice cloning, and 1 on-demand resource management, and 1 language authenticity, and 1 realistic person video, 1 2D explainer animation, and 1 command authority systems, the repo holds 108 distinct systems, presented as 119 numbered entries.

## Folder layout

Regeneration work is recorded per regeneration, in the private overlay — never in the public repository:

```text
regenerations/
  <regeneration-id>/            # one folder per regeneration request
    reference.md                # what was uploaded (filename, duration,
                                # aspect ratio, platform) — no video file
    analysis.md                 # the full reference analysis (Section 1):
                                # story, scenes in order, characters,
                                # objects, camera, light, sound
    changes.md                  # what the user asked to change, and the
                                # small creative improvements planned —
                                # nothing else changes
    storyboard.md               # the chronological storyboard (Section 6):
                                # one entry per shot
    qc.md                       # the quality-control record (Section 8):
                                # what was checked, what failed, what was
                                # corrected or regenerated
```

The uploaded reference video itself is never committed to the public repository. Neither are generated clips, voice recordings, or any character data. The record above holds words only: the analysis, the change list, the storyboard, and the QC record.

## 1. Complete Reference Video Analysis — First, Before Anything Else

Before generating anything, analyse the entire uploaded video from beginning to end. Do not skip any scene, transition, action, or important visual detail. If possible, inspect the video frame by frame; otherwise, analyse all available frames and important motion sequences.

Analyse all of the following:

- Overall story, narrative structure, and central message.
- Every scene and its exact chronological order.
- Character identities, facial features, approximate ages, body proportions, hairstyles, clothing, and accessories.
- Character expressions, emotions, gestures, movements, and interactions.
- Objects, props, their locations, and how characters interact with them.
- Camera angles, framing, shot composition, camera movements, zooms, and focus.
- Lighting, shadows, colours, environment, background, and atmosphere.
- Scene transitions, editing rhythm, pacing, and visual continuity.
- Audio, dialogue, background ambience, sound effects, and music mood.
- Opening hook, emotional development, climax, and ending.

Never invent visual details that cannot be verified from the reference. If something cannot be seen or heard in the reference, say so — do not fill the gap with an invention and then build on it. The analysis is written down (`analysis.md`) before any generation starts, so it can be checked against the delivered video.

## 2. Create a New Video, Not a Duplicate

Create a fresh video inspired by the reference. Do not reproduce every frame identically. The new video must feel like a professionally produced alternative version of the reference.

Preserve the original story's central idea, the emotional journey and intended audience reaction, the overall narrative progression, the important visual storytelling elements, and the realism and professional cinematic quality.

Creative improvements are allowed only in: minor scene arrangements; background details and environmental elements; small character gestures and natural expressions; camera composition and cinematic movement; minor transitions and storytelling details; visual details that make the new version more engaging.

Do not introduce changes that damage the original story, character motivations, emotional meaning, or logical sequence of events. Any change the user explicitly requests wins over the defaults above — but a requested change never licenses a change to something the user did not ask about. Requested changes are recorded in `changes.md` before generation, so the delivered video can be checked against exactly what was asked.

## 3. Character and Object Continuity

Maintain strict visual continuity throughout the entire video.

Every recurring character must retain the same facial identity and facial structure, skin appearance and natural facial details, hairstyle and hair colour, body proportions and physical appearance, and clothing, accessories, and footwear unless a change is explicitly required by the story.

Every important object must maintain consistent shape, size, colour, and material, physical location and orientation, and ownership and interaction history.

A character must never randomly change identity, age, clothing, or physical appearance between shots. Verify each character and each important object against the reference before delivery (character-consistency, identity anchoring and angle-matched verification).

## 4. Realistic Physical Interactions — Critical

All physical interactions must follow believable real-world physics and anatomy. This is the most common place a regenerated video fails — check it shot by shot.

Hand-to-hand interactions: when one character hands money, a gift, a phone, or any object to another character, show a physically correct transfer. The receiving hand must visibly approach and make contact with the object. The object must remain between the fingers and palm, not pass through the hand. The original holder must release the object only after the receiving character has secured it. Never allow two characters' hands to merge, overlap unnaturally, or intersect.

Object interactions: objects must never pass through hands, bodies, clothing, tables, walls, or other objects. Maintain correct object weight, gravity, balance, and contact. Objects must not disappear, duplicate, teleport, or randomly change shape. Maintain correct object ownership before, during, and after every interaction.

Body and character interactions: no intersecting bodies, fused limbs, distorted fingers, extra fingers, missing limbs, or unnatural anatomy. No facial merging or identity blending between characters. Maintain realistic walking, sitting, standing, reaching, turning, and movement. Ensure that characters occupy physically separate and believable positions.

Every action must have a clear beginning, middle, and completion. A transfer that starts but never visibly finishes is a failed shot.

## 5. Cinematography and Visual Realism

Use professional live-action filmmaking principles: photorealistic human characters, natural skin texture and realistic facial expressions, physically accurate lighting and shadows, natural depth of field, consistent perspective and spatial relationships, realistic environmental details, smooth and purposeful camera movements, and cinematic but believable composition.

Camera angles follow the script-driven automatic camera angles system (A12): each shot's angle is chosen from its beat — story function, emotion, character relationship, what the viewer must notice — never randomly, and never by habit. In no-script regenerations, the beats come from the analysis (Section 1) and the storyboard (Section 6).

Avoid excessive artificial sharpness, plastic-looking skin, exaggerated facial features, unnatural movement, artificial lighting, and synthetic-looking textures. The final result should look like professionally filmed live-action footage, not an obvious AI-generated video. Do not imitate a specific filmmaker or copy copyrighted footage.

## 6. Storyboard and Shot Planning — Before Generation

Before generation, internally organise the new video into a chronological storyboard, recorded in `storyboard.md`. Do not generate before the storyboard exists.

For each shot, determine: shot number and approximate duration; characters present; location and background; main action; facial expression and emotional state; camera angle and movement; important objects and interactions; transition to the next shot.

Preserve logical continuity between consecutive shots. Do not create unnecessary random cuts or repetitive shots.

## 7. Audio and Sound Design

Analyse the original audio and understand its emotional purpose before creating new audio. Create suitable audio for the new video: natural environmental ambience, appropriate sound effects, realistic interaction sounds, emotionally appropriate background music, and proper synchronisation between visual actions and sound.

Do not reproduce copyrighted songs or exact recordings from the reference. Use original music with a similar emotional atmosphere when appropriate. Avoid unnecessary dialogue, narration, or captions unless they are required by the story.

## 8. Final Quality Control — Before Delivery

Before considering the video complete, review the generated result. This QC pass is mandatory — it is not optional, and it is not skipped when time is short. The record goes in `qc.md`: what was checked, what failed, and what was corrected or regenerated.

Check for: character identity consistency; facial and body distortions; hand and finger abnormalities; object intersections and incorrect transfers; floating, disappearing, or duplicated objects; clothing and accessory changes; background inconsistencies; lighting and shadow inconsistencies; unnatural camera movement; audio synchronisation errors; broken scene transitions; storytelling and chronological errors.

If any defect is detected, correct or regenerate the affected shot whenever the available tools support it. Never intentionally accept a visibly defective shot as a finished professional result. Do not deliver a video that fails a check without telling the user what failed.

## 9. Final Output Requirements

Match the reference video's aspect ratio, general pacing, and intended platform unless the user specifies otherwise. Preserve the original video's approximate duration when technically possible. If the generation model has a shorter duration limit, divide the story into coherent, sequential clips. Maintain consistent visual quality across all clips. Do not sacrifice realism, continuity, or physical accuracy merely to produce the video faster.

Working order, restated: first analyse, then plan, then generate, finally inspect and correct.
