---
name: production-systems
description: The professional production layer for series video-making. Covers the 12 professional production systems, the 18 extended systems, the 7 additional systems, the language, captions and format rules, and the production priority hierarchy — described in enough detail that an AI following this skill alone can apply them.
---

# Production Systems

These systems make the difference between an acceptable video and a professional series. Apply them in every project unless the user says otherwise. They sit alongside the `character-consistency`, `voice-consistency`, and `humanized-production` skills: characters and voices stay fixed, humanization makes each frame feel real, and these systems make the whole series hold together.

Counting note: this skill lists 40 numbered entries (12 + 18 + 7 + 3). Together with the 36 humanization systems, the 7 agency advertising systems, the 1 video regeneration system, the 5 cinematic power systems, the 6 live-action & VFX systems, the 7 emotional performance systems, and the 1 user-supplied voice cloning system, and the 1 on-demand resource management system, the repo holds 104 distinct systems, presented as 115 numbered entries — eleven of the 12 professional systems in Part A below are also listed in docs/01-production-systems.md; the camera-angles system (A12) is numbered here only, and docs/01 §2 cross-references it.

## Part A — 12 Professional Production Systems

### A1. Visual Style Bible

Every project has one fixed visual style: a colour palette, a lighting mood, and a level of realism. Record it in the project and use the same style in every episode, so all episodes look like one series and not like separate videos. A bright comedy scene and a sad night scene may differ in mood, but the underlying look — colour, light, texture — must stay recognizable as the same series.

### A2. Camera Language and Shot List

Decide the camera language before generating: when to use a close-up (emotion, dialogue), a medium shot (conversation), and a wide shot (place, action). Use the same language across episodes. For each scene, follow a simple shot plan: establishing shot, main action, reaction shot, closing shot. Do not rely on a single framing for everything. Choose camera movements and shot compositions according to the actual scene; every shot must have a visual purpose. Use wide shots, medium shots, close-ups, over-the-shoulder shots, tracking shots, establishing shots, appropriate angles, balanced framing, natural perspective, realistic depth of field, proper subject focus, professional lighting, natural shadows, accurate reflections, and realistic environmental details. Which angle each shot uses is decided by the script beat — see A12. For the cinematic-power layer — style lock, animal and creature performance, music-beat editing, trailer structure, and scale and colour scripting — see the `cinematic-power` skill. For the live-action and VFX layer — real human performance, CG creatures in live footage, water and wetness continuity, set extension, stunts, and real-animal performance — see the `live-action-vfx` skill. For the emotional-performance layer — stage performance, crowd, intimate drama, age performance, instrument sync, music as story, and cultural authenticity and object storytelling — see the `emotional-performance` skill.

### A3. Negative Prompt Library

Maintain a standing list of defects to prevent in every generation: extra or missing fingers, distorted hands, merged or duplicated faces, warped limbs, extra characters, unreadable text, broken objects, sudden outfit changes inside one scene. Apply this list as negative prompts or generation constraints wherever the platform supports them, in addition to scene-specific negative prompts. Also guard against motion defects (flickering, jerky movement, sudden teleportation, unnatural walking, broken transitions), object defects (floating, disappearing, duplicated objects, objects passing through hands or bodies, incorrect ownership), identity defects (face changes, unintended substitutions, identity mixing between characters), and visual defects (plastic skin, blurry faces, unnatural shadows, incorrect reflections, pixelation, inconsistent styles, scene blending, unnatural lighting). Negative prompting reduces defects but does not guarantee their elimination — never claim all defects have been prevented unless the actual output has been inspected.

### A4. Sound Design System

Sound is half of realism. For every scene, plan the sound, not only the picture: footsteps, water, birds, wind, room tone, doors, crowd sounds — whatever the place would really sound like. Sound effects must match the action on screen in timing and in character; a silent action scene or a mismatched sound breaks the human feeling immediately. Keep four sound layers in order: ambience / room tone, foley on visible beats matched to the surface, dialogue, music. Silence is a defect — even a quiet room has a low hum. Write a sound spotting sheet per shot before generating sound (see the `humanized-production` skill).

### A5. Music and Theme

Each series has one fixed theme music and a consistent musical mood. Use the same theme across episodes so the audience recognizes the series by sound. Scene music must follow the scene's emotion: light for comedy, tense for danger, soft for sadness. Music must support the scene, never fight it. Music and sound effects duck under dialogue and never compete; dialogue carries ~60% of attention.

### A6. Story Bible

Keep a story bible for each series: the rules of its world, its places, its timeline, and what has happened so far. Character faces are only half of consistency — the story must also stay consistent. Never contradict the story bible: a place destroyed in episode 2 must not appear intact in episode 5, and a fact established earlier must not be silently changed later.

### A7. Episode Continuity Tracker

After each episode, record what happened: key events, what each character wore, injuries, gained or lost objects, and where each character ended up. Read this record before starting the next episode. The next episode must continue from the recorded state. If the user changes something deliberately, record the change; never let an episode contradict an earlier one by accident. Maintain continuity within every scene as well: character position, clothing within a continuous scene, object location and ownership, environmental geometry, lighting direction, camera perspective, movement direction, action progression, and scene timing. If a character holds a phone in the right hand at the end of one shot, the phone must not suddenly appear in the left hand in the next continuous shot without an actual transfer.

### A8. Dialogue Writing Rules

Dialogue must be natural spoken language, not bookish language. An 8-year-old speaks like an 8-year-old; an adult speaks like an adult; an elderly character speaks like an elderly person. Never give a child adult words. Keep lines short enough to speak naturally, with pauses where a human would pause. If a line sounds robotic when read aloud, rewrite it. Write each character's dialogue in that character's language (see Part D).

### A9. Reference Photo Quality Rules

A good reference photo makes registration succeed: the face must be clear and well lit, facing the camera, with a neutral expression, without sunglasses, masks, heavy shadows, or blur. If a provided photo is unclear, dark, or cropped so the face is cut off, tell the user and ask for a better photo instead of registering a weak reference. See the `character-consistency` skill for the registration rules.

### A10. Lip-Sync and Dubbing Workflow

Decide the order for each project before starting: voice first, then video matched to the voice; or video first, then voice matched to the video. Follow one order consistently inside a project. Dialogue timing must match the mouth: a line must not finish long before or after the character stops speaking. If lip-sync is not supported on the platform, say so honestly instead of promising it. Check mouth interior sharpness, teeth stability, and tongue on close-ups (see the `humanized-production` skill).

### A11. Episode QC Checklist

Before delivering any episode, check it against the list: character faces and heights correct; voices correct for each character; emotions match the script; dialogue exact; no extra fingers, merged faces, or broken objects; clothing correct for the scene; sound and music present and matched; no contradiction with the story bible or the continuity tracker. Do not deliver an episode that fails a check without telling the user what failed. Inspect the beginning, middle, and ending, plus character appearances, facial identity consistency, important actions, hand-object interactions, character-to-character interactions, scene transitions, and audio and lip-sync where inspectable. Do not claim frame-by-frame inspection unless it was actually performed, and do not claim a video is completely defect-free without sufficient verification. Video regeneration has its own QC pass (see the `video-regeneration` skill, Section 8), which reuses this checklist plus the regeneration-specific checks — handovers, object transfers, and frame-by-frame comparison against the reference.

### A12. Script-Driven Automatic Camera Angles

The camera angle is never random and never decorative. For every shot, read the script beat first — what is happening, what the character feels, what the story needs the viewer to feel — and let that decide the angle automatically. The user may override any choice, but the AI never picks an angle by habit, by rotation, or because it is a favourite shot.

**1. Read the beat before choosing the angle.** For each shot, identify (a) the story function — establish, reveal, confront, comfort, decide; (b) the feeling character's emotion; (c) the relationship between the characters in frame; (d) what the viewer must notice. The angle follows from those four — never from a fixed rotation or a favourite shot.

**2. Shot grammar.** The vocabulary: wide / establishing (place, scale, isolation); medium (action, body language); close-up (emotion, reaction); extreme close-up (a meaningful detail — eyes, hands, an object); over-the-shoulder (conversation, point of view); POV; low angle (power, threat, awe); high angle (vulnerability, smallness, loss of control); bird's-eye (fate, pattern); worm's-eye (overwhelm); Dutch tilt (unease — use sparingly); two-shot (relationship); group wide (dynamics).

**3. Beat-to-angle mapping.** Automatic defaults; emotion always wins over the table. Power / dominance / threat → low angle, slow push-in. Vulnerability / fear / defeat → high angle, slightly wider. Intimacy / confession / tenderness → close-up, eye-level, still. Isolation / loneliness → wide shot, character small in frame. Tension / something wrong → slow push-in or a small Dutch tilt, brief. Revelation / realisation → dolly-in to close-up as it lands. Conversation → shot-reverse-shot with matched eyelines, over-the-shoulder for the listener. Action / urgency → tracking shot, handheld energy, shorter cuts. Memory / dream / wonder → slow crane or gentle float. Comedy / lightness → wider, eye-level.

**4. Motivated movement only.** The camera moves only when the story moves — following a character, revealing something, or matching a change in emotion. No movement for its own sake; a static shot is right whenever nothing in the beat asks for movement.

**5. Lens language.** The lens follows the beat too: wider lens (35mm) for place and togetherness, normal (50mm) for honest human presence, longer lens (85mm) for intimacy and isolating the face from the background. Never change lens character inside one continuous moment without a story reason.

**6. Continuity across cuts.** Hold the 180-degree rule — never cross the line of action without a clear establishing re-set. Match eyelines in shot-reverse-shot; match on action; keep screen direction consistent so the viewer never has to re-find where anyone is.

**7. Realism — human camera, not perfect camera.** Allow the small human imperfections that make footage feel shot rather than rendered: a faint handheld sway in intimate scenes, a breath of focus hunting when reframing, slightly imperfect framing corrected mid-shot. Subtle: noticeable enough to feel human, never enough to distract. See the `humanized-production` skill (30.14 Camera Imperfection). This serves the repo's overall realism target: aim for 100% realistic, human-generated feeling; 99.9% is the floor — never leave any part visibly artificial when a better choice exists.

**8. Angle holds within a beat, changes with the beat.** One beat, one angle logic — no new angle mid-beat without a story reason. The angle plan is written into the shot list before generation, so every angle is decided from the script, not during generation. See A2 and docs/01 §2.

**9. User override.** Any angle the user names for any shot wins. When the user gives no angle, this system decides — automatically, from the script, every time.

**10. No-script mode — the system writes, then directs.** When the user gives no script and asks the system to generate the story itself, this system still applies — in full, without exception. The system must FIRST write the story as beats, each beat carrying its story function, emotion, character relationship, and what the viewer must notice, and THEN choose the angle for each beat from those beats, exactly as in the normal script-driven flow. The angle decision is mandatory in both modes — user-supplied script AND system-generated story. It is never skipped, never left to chance, never decided after generation. When the system writes the script, the shot list with angles is part of the script it delivers — the story and its camera direction are generated together, beat by beat. If the system cannot identify a beat's emotion or function, it must ask the user or state its assumption explicitly — it must not silently default to a generic angle.

For live-action and VFX hybrid shots — real actors with CG creatures, water continuity, stunts — the angles chosen here work together with the `live-action-vfx` skill, which covers the performance, the VFX integration, and the action the camera is framing. For intimate scenes, the angles work together with the `emotional-performance` skill, which plans the emotional arc beat by beat and holds the camera close and still while the faces do the work.

**Check:** every shot in the shot list has an angle justified by its beat (story function, emotion, relationship, what the viewer must notice); no angle chosen by rotation or habit; no unmotivated camera movement; the 180-degree rule and eyelines hold across cuts; in no-script mode the beats are written before the angles and the shot list with angles is part of the delivered script.

## Part B — 18 Extended Production Systems

### B1. Subtitles / Captions Pipeline

Produce captions as timed subtitle text (for example SRT) in the language the user requests, matched to the spoken dialogue line by line. Captions are optional — ask the user first whether they want captions at all (see Part D). Never bake captions into a video unless the user asked for them.

### B2. Thumbnail / Poster Generator

Create one strong thumbnail or poster per episode from a real frame or a generated still, with the episode's characters, readable title text, and the series style from the Visual Style Bible. Do not use a misleading thumbnail that shows something that does not happen in the video.

### B3. Character Turnaround / Model Sheets

For each registered character, keep a model sheet — front view, three-quarter view, full body, and expression sheet — built from the reference image(s). Check every new scene against the model sheet, not only against a single photo, so the face, height, and body stay the same from every angle. See the `character-consistency` skill.

### B4. Wardrobe, Prop, and Location Registry

Record every outfit, prop, and location a character uses, with the episode and scene where it appeared. A character wears the outfit the scene requires, and an outfit, prop, or location never changes by accident between shots. Wrinkles, stains, wear, fit, and layering persist across shots; fabric creases change with pose, not randomly per shot. Outfit consistency is script-driven (see the `character-consistency` skill): the outfit the user selects or gives stays exactly as-is until the user says to change it; when the script clearly needs a change (for example, swimming), the outfit changes for that scene and the new outfit then holds in that context. An outfit changes only on the user's word or a clear scene need — never randomly.

### B5. Clip-Boundary Seam Continuity

Videos are built in clips. The last frame of one clip must match the first frame of the next clip — same character position, same expression, same outfit, same background, same lighting. Check every join before delivery; a visible jump at a clip boundary is a defect. Re-inject reference images and first-frame anchoring every ~8–16 seconds and at every scene change, because consistency degrades sharply past ~16 seconds.

### B6. Quantitative Drift Measurement

Do not judge character consistency by eye alone. Measure face similarity between the reference image and each generated frame or clip (a face-embedding similarity score) and keep it above the project's threshold. If the score falls below the threshold, regenerate. Record the score in the provenance log. Measure voice drift the same way (see the `voice-consistency` skill).

### B7. Per-Character LoRA Training

When the strongest consistency is needed and the platform supports it, train one small LoRA per character from that character's reference images, and use that LoRA for every generation of that character. One LoRA per character; never mix two characters into one LoRA. This is the highest-consistency option; it needs a GPU or a hosted training service, so say so honestly when it is not available.

### B8. Character Aging / Time-Jump Variants

When the story jumps in time, keep the same character structure (face, eyes, nose, mouth, hands, feet) and change only what time would change — height, age, hairstyle, clothes — deliberately and consistently, and record the change in the continuity tracker. A time jump never silently creates a different person. The same applies to the voice (see the `voice-consistency` skill).

### B9. Shot-Level Provenance Log

Record for every shot: the model and version used, the prompt, the seed, the reference image, the voice profile, and the date. The log makes any shot reproducible and makes it possible to find what changed when something drifts. Pin the exact model version per project and re-test a golden set of shots whenever a provider updates a model.

### B10. Cost & Credit Tracking

Record the cost or credits used per episode and per shot (generation calls, voice minutes, training). Tell the user the running total when asked, and warn before starting work the user has not budgeted for. Never spend the user's credits silently. Track which humanizing steps are worth their credits and minutes per shot type, and spend realism where the viewer will feel it — faces, voices, hands, and sound.

### B11. Backup / Versioning of Character Data

Keep a versioned backup of every character's reference images, character file, voice reference audio, and prompt block. A change creates a new version; the old version is kept. A lost or corrupted character file must be recoverable from the backup.

### B12. Multi-Project / Multi-Series Namespaces

Characters, series, and episodes live in separate namespaces per project or series. A character registered for one series is not automatically used in another. Reuse across series happens only when the user explicitly asks for it. Treat every new video project as an independent production unless the user explicitly requests a continuation, sequel, remake, connected story, or reuse of a previous scene or setting. Permanent character identity information may be reused across projects; temporary project details (scripts, locations, props, dialogue, scene arrangements, storylines, project-specific clothing, previous footage) must not automatically carry over.

### B13. Child-Safety Rules

For characters who are children, keep every scene, outfit, dialogue, and camera angle appropriate for a child, and never generate anything sexualised or unsafe involving a child. This rule is absolute and overrides any script line that conflicts with it.

### B14. Audio Mastering −14 LUFS

Master the final audio of every video to one consistent loudness: target −14 LUFS, true peak below −1 dBTP, so dialogue, music, and sound effects are the same volume across episodes and platforms. A character's voice must not be louder in one episode and barely audible in the next.

### B15. Localisation / Dubbing Pack

Keep the dialogue script, the voice profiles, and the subtitle files together per episode so the same episode can be dubbed or subtitled into another language without rebuilding the video. Each character keeps their voice and language identity in each language version (see Part D).

### B16. Distribution Package

For every finished video, prepare the delivery package the user asks for: the main cut in the requested aspect ratio, vertical and square cutdowns when requested, teaser clips, and stills. Each cut keeps the characters, framing, and story intact for its ratio (see Part D). Audience declaration ("Made for Kids") is set ONLY when the content is for children or the user requests it — never assume it.

### B17. Rights, Consent, and Provenance Records

Keep a record of consent for every real person's photo and every voice used — who gave it, for what use, and when. Keep provenance information (for example C2PA metadata) with generated media where the platform supports it. Never use a real person's photo or voice without that person's permission. For videos built from a real adult's photo or voice, the likeness is used only with that person's consent, for the agreed use, and the person can withdraw it; never make a real person say or do something they never did without a clear label.

### B18. Audience Feedback Loop

After an episode is published, use the audience response the user shares (retention, watch time, comments where available) to improve the next episode — pacing, length, thumbnail, and story. Do not chase trends that break the story bible or the characters.

## Part C — 7 Additional Systems

### C1. Private Character Data Separation

Each character's data — reference images, character file, voice reference audio, prompt block — is stored separately, in that character's own folder, private by default. Character data is never published, shared, or committed to a public place without the user's explicit permission. In a public repository, character data lives in a separate private overlay, never inside the public files. A character is used alone or together with other characters only as the user requests. See the `character-consistency` skill.

### C2. Multi-Character Scenes and No Overlap

Several characters may appear together in one scene — for example three, four, or five friends at a party. Natural physical contact is allowed: one character may put a hand on another's shoulder, hold another's hand, or touch another's hair. But one character or object must never go inside another character or object: no overlapping, no merged bodies, no merged faces, no hand passing through a body, no head inside another head. Contact is on the surface; bodies stay separate and solid. Check every multi-character shot for overlap before delivery. See the `character-consistency` skill.

### C3. Episode Intake Checklist

Before generating an episode, go through one checklist and ask the user everything that is still open, in one go: which characters are in the episode; each character's language; whether captions are wanted and in which language; the aspect ratio and platform; short or long video; the script. Do not ask the same question twice, and do not start generating while a needed answer is missing. Do not ask unnecessary questions when the script is already clear; ask only for essential clarification when proceeding without it could produce the wrong character, wrong story, or materially incorrect video.

### C4. Demo Project (On-Demand System)

Keep a small demo ready — one sample character and one sample episode script. If the user wants a demo video, generate the demo so they can see how the system works. If they do not want a demo, work directly on their real project. A demo is offered, never forced.

### C5. Script Template + Automatic Script Enhancement

Scripts are written in a fixed format: scene, characters present, dialogue per character, camera, emotion per line. If the user's script is weak — flat dialogue with no feeling — improve it automatically: add emotion, natural pauses, reactions, and lively expression so the video has feeling, while keeping the story, the meaning, and the user's dialogue intact. Never change the story to add emotion; add the feeling to the story the user gave. A video with no feeling is a failed video.

### C6. Contribution Guide

This system is open source, so contributors are welcome. Contributors must follow these rules: keep the character consistency rules intact; never weaken the safety rules; describe every change; test before submitting; keep the licence and attribution intact. Changes that break characters, voices, or safety are not accepted.

### C7. Script-Driven Realism and Colour Grading

Characters must look realistic in every scene — real skin, real light on the face, real shadows — never flat or cartoon-like unless the user asked for a cartoon style. Colour grading is professional and follows the script, not a random look: the grade is decided by the time of day and the light source in the scene.

- Full-moon night — cool blue moonlight grade.
- Bright sunlight — warm daylight grade.
- Evening — soft warm evening grade.
- Morning — fresh morning light grade.
- Dusk — orange-purple twilight grade.
- Midnight — deep dark grade.
- Torch or flashlight at night — warm torch light with real shadows on the character and the surroundings.

The grade never changes randomly from one shot to the next inside the same scene, and the character's skin and clothes always match the light of the scene they are in. Every scene must look believable, as if it was really filmed in that light. Shadow direction, colour temperature, and light-source position are fixed per scene and locked across every shot in that scene (see the `humanized-production` skill).

## Part D — Language, Captions, and Format Rules

### D1. Captions and Subtitles Are OPT-IN — Ask First

Never add captions or subtitles to a video automatically. When the user asks for a video, ask whether they want captions. If they say no, deliver the video clean, with no baked-in captions, so the platform's own automatic captions (for example YouTube or Facebook) can be used if they wish. If they say yes, ask which language — or use the language they name — and produce the captions in exactly that language: Bengali, English, Hindi, French, or any other language the user requests. The caption language follows the user's choice, not a default. Beyond captions, provide a narration of visual action in dialogue pauses (audio description, WCAG 2.1 Success Criterion 1.2.5) plus a descriptive transcript, so blind and low-vision viewers are not left out.

### D2. Per-Character Language

A video may have several characters, and each character may speak a different language. For example, in one video one character speaks Bengali, another speaks English, and another speaks Hindi. Write each character's dialogue in that character's language, generate each character's voice in that language, and match the lip-sync to that language. Captions follow the same rule: a caption track per language the user requests. Never force all characters into one language unless the user asks for it. Handle mid-sentence language switching (for example Bengali↔English) and regional accent explicitly, with a separate listening test per language and per dialect.

### D3. Format / Aspect Ratio on Demand

Short videos and long videos are both supported, for YouTube and for any other platform. The video is made in the aspect ratio the user requests — 16:9, 9:16, 1:1, 4:5, or any other ratio. Compose the framing, camera, and safe areas for that ratio from the start; do not crop a finished video into a new ratio as an afterthought. If the user does not state a ratio, ask which platform and ratio they want before generating.

## Part E — Production Priority Hierarchy

When different instructions compete, follow this priority order:

1. **User's explicit instructions / script.** The user's direct instructions, script, and authorized changes take precedence over assumptions.
2. **Character identity consistency.** Registered characters must retain their recognizable physical identity.
3. **Story and action accuracy.** The generated video must accurately represent the intended story and actions.
4. **Physical realism and continuity.** Human movement, object handling, scene geometry, and transitions must remain believable.
5. **Professional cinematography.** Use suitable professional camera work, lighting, composition, and visual storytelling.
6. **Visual and audio quality.** Maintain the highest practical quality supported by the platform.

Never sacrifice character identity or story accuracy merely for visual decoration. Never treat character consistency as a minor visual preference — it is a fundamental requirement. Never treat professional video production as merely generating attractive images that move: every video must have coherent storytelling, believable physical behaviour, consistent characters, deliberate camera direction, and polished execution.
