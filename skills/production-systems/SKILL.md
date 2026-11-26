---
name: production-systems
description: The professional production layer for series video-making. Covers the 12 professional production systems, the 18 extended systems, the 7 additional systems, the language, captions and format rules, and the production priority hierarchy — described in enough detail that an AI following this skill alone can apply them.
---

# Production Systems

These systems make the difference between an acceptable video and a professional series. Apply them in every project unless the user says otherwise. They sit alongside the `character-consistency`, `voice-consistency`, and `humanized-production` skills: characters and voices stay fixed, humanization makes each frame feel real, and these systems make the whole series hold together.

Counting note: this skill lists 40 numbered entries (12 + 18 + 7 + 3). Together with the 36 humanization systems, the 7 agency advertising systems, the 1 video regeneration system, the 5 cinematic power systems, the 6 live-action & VFX systems, the 7 emotional performance systems, and the 1 user-supplied voice cloning system, the 1 on-demand resource management system, and the 1 language authenticity system, the 1 realistic person video system, the 1 2D explainer animation system, the 1 command authority system, and the 1 kids & family animation system, the repo holds 109 distinct systems, presented as 120 numbered entries — eleven of the 12 professional systems in Part A below are also listed in docs/01-production-systems.md; the camera-angles system (A12) is numbered here only, and docs/01 §2 cross-references it. Production Addendum 01 (2026-11-26) deepens the systems below with workflow and template extensions (Parts F–L, the A2 director's extension, the A11 severity extension); it adds no new numbered entries, so the 40-entry count and the repo's 109/120 counts are unchanged.

## Part A — 12 Professional Production Systems

### A1. Visual Style Bible

Every project has one fixed visual style: a colour palette, a lighting mood, and a level of realism. Record it in the project and use the same style in every episode, so all episodes look like one series and not like separate videos. A bright comedy scene and a sad night scene may differ in mood, but the underlying look — colour, light, texture — must stay recognizable as the same series.

The visual style is one dimension of the production profile, not the whole profile: visual_style, production_medium, motion_method, subject_kind, and interaction_pattern are separate, composable dimensions — never one single `animation_type`. A change in one dimension (for example the visual_style) does not silently change the others, and never silently changes a character's identity (see the `character-consistency` skill).

### A2. Camera Language and Shot List

Decide the camera language before generating: when to use a close-up (emotion, dialogue), a medium shot (conversation), and a wide shot (place, action). Use the same language across episodes. For each scene, follow a simple shot plan: establishing shot, main action, reaction shot, closing shot. Do not rely on a single framing for everything. Choose camera movements and shot compositions according to the actual scene; every shot must have a visual purpose. Use wide shots, medium shots, close-ups, over-the-shoulder shots, tracking shots, establishing shots, appropriate angles, balanced framing, natural perspective, realistic depth of field, proper subject focus, professional lighting, natural shadows, accurate reflections, and realistic environmental details. Which angle each shot uses is decided by the script beat — see A12. For the cinematic-power layer — style lock, animal and creature performance, music-beat editing, trailer structure, and scale and colour scripting — see the `cinematic-power` skill. For the live-action and VFX layer — real human performance, CG creatures in live footage, water and wetness continuity, set extension, stunts, and real-animal performance — see the `live-action-vfx` skill. For the emotional-performance layer — stage performance, crowd, intimate drama, age performance, instrument sync, music as story, and cultural authenticity and object storytelling — see the `emotional-performance` skill.

#### A2.1 Visual literacy — read before directing

Before choosing any shot, read the scene in five steps: **Observe → Describe → Infer → Recreate → Compare.** Observe what is actually there; describe it in plain words; infer what it means; recreate the intent in the shot plan; compare the result against the intent. Keep four things separate at every step: what is objectively visible, what is inferred, what is a creative hypothesis, and what still needs verification. A hypothesis is never written into the shot list as a fact — it is marked as needing verification, and the shot is checked against the verified fact, not the guess.

#### A2.2 Scene breakdown

For each scene, record before shooting: scene purpose; one-line scene summary; emotional tone; each character's objective; character relationships; scene geography; main actions; important props; environment; required coverage; sound requirements; transition into the next scene. The breakdown is written once per scene and read before every shot in that scene is planned — a shot that does not serve the breakdown's purpose is a shot that does not belong.

#### A2.3 Blocking

Record the blocking for each scene: character positions; screen direction; foreground, midground, and background; entry and exit points; movement paths; marks and interactions; camera relationship. Characters and objects must not drift between shots without a story reason — a character who stands left in the master stands left in the coverage, unless the story moves them and the move is shown. Blocking is part of the shot list, not an afterthought: the camera is placed for the blocking, never the blocking for the camera.

#### A2.4 Coverage system — selective, never exhaustive

Use coverage selectively: the twelve types are (1) extreme wide / establishing, (2) wide shot, (3) full shot, (4) medium wide, (5) medium shot, (6) medium close-up, (7) close-up, (8) extreme close-up, (9) two-shot, (10) over-the-shoulder, (11) insert, (12) cutaway. Each has a purpose: master wide for geography; two-shot for relationship; over-the-shoulder for conversation and eyeline; single / medium close-up for dialogue and performance; close-up for emotional reaction; insert / cutaway for important action or detail. Do NOT force every coverage type into every scene — the scene breakdown (A2.2) decides which types the scene needs, and a scene that needs three types gets three, not twelve. A missing coverage type is a defect only when the breakdown required it.

#### A2.5 Continuity rules

In addition to the 180-degree rule (A12 §6), hold: the **30-degree guideline** — a cut between two shots of the same subject should change the camera angle by at least 30 degrees, or the cut reads as a jump rather than a new shot; **eyeline matching** — eyelines match across shot-reverse-shot (see A12 §6 and `humanized-production` 30.7); **screen-direction consistency** — movement direction holds across cuts; **action matching** — an action begun in one shot continues from the same point in the next (see A12 §6); **spatial continuity** — the geography of the scene (where the door is, where the table stands) holds across every shot; **shot-reverse-shot consistency** — the two sides of a conversation match in framing, eyeline, and background. The 180-degree rule and the 30-degree guideline are both creative continuity guidelines, not absolute restrictions: an intentional violation is permitted when the reason is clear and recorded (for example a deliberate disorientation), but an accidental violation is a defect.

#### A2.6 Performance direction — playable actions, not labels

Do not direct acting with emotion labels alone. Translate every emotion into playable actions the character can do. Instead of just `angry`, direct: tightened jaw, shorter breathing, delayed response, avoided eye contact, restrained hand movement. Instead of just `sad`, direct: lowered gaze, slower steps, shoulders dropping, a hand that starts to reach and stops. Instead of just `afraid`, direct: held breath, a step back, eyes fixed on the threat, hands clutching. The playable action is written into the shot list next to the line, so the performance is directed, not hoped for. This extends — never replaces — the dialogue and character identity rules (A8, `character-consistency`): the words stay the user's, the face stays the character's, and the body plays what the words mean.

### A3. Negative Prompt Library

Maintain a standing list of defects to prevent in every generation: extra or missing fingers, distorted hands, merged or duplicated faces, warped limbs, extra characters, unreadable text, broken objects, sudden outfit changes inside one scene. Apply this list as negative prompts or generation constraints wherever the platform supports them, in addition to scene-specific negative prompts. Also guard against motion defects (flickering, jerky movement, sudden teleportation, unnatural walking, broken transitions), object defects (floating, disappearing, duplicated objects, objects passing through hands or bodies, incorrect ownership), identity defects (face changes, unintended substitutions, identity mixing between characters), and visual defects (plastic skin, blurry faces, unnatural shadows, incorrect reflections, pixelation, inconsistent styles, scene blending, unnatural lighting). Negative prompting reduces defects but does not guarantee their elimination — never claim all defects have been prevented unless the actual output has been inspected.

### A4. Sound Design System

Sound is half of realism. For every scene, plan the sound, not only the picture: footsteps, water, birds, wind, room tone, doors, crowd sounds — whatever the place would really sound like. Sound effects must match the action on screen in timing and in character; a silent action scene or a mismatched sound breaks the human feeling immediately. Keep four sound layers in order: ambience / room tone, foley on visible beats matched to the surface, dialogue, music. Unplanned silence is a defect — even a quiet room has a low hum — but intentional silence is a creative decision: a silence marked in the sound spotting sheet and held for a reason (see `humanized-production` §30.19). Missing or accidentally muted audio is a defect; a deliberate silence is not. Write a sound spotting sheet per shot before generating sound (see the `humanized-production` skill).

### A5. Music and Theme

Each series has one fixed theme music and a consistent musical mood. Use the same theme across episodes so the audience recognizes the series by sound. Scene music must follow the scene's emotion: light for comedy, tense for danger, soft for sadness. Music must support the scene, never fight it. Music and sound effects duck under dialogue and never compete; dialogue carries ~60% of attention.

### A6. Story Bible

Keep a story bible for each series: the rules of its world, its places, its timeline, and what has happened so far. Character faces are only half of consistency — the story must also stay consistent. Never contradict the story bible: a place destroyed in episode 2 must not appear intact in episode 5, and a fact established earlier must not be silently changed later.

### A7. Episode Continuity Tracker

After each episode, record what happened: key events, what each character wore, injuries, gained or lost objects, and where each character ended up. Read this record before starting the next episode. The next episode must continue from the recorded state. If the user changes something deliberately, record the change; never let an episode contradict an earlier one by accident. Maintain continuity within every scene as well: character position, clothing within a continuous scene, object location and ownership, environmental geometry, lighting direction, camera perspective, movement direction, action progression, and scene timing. If a character holds a phone in the right hand at the end of one shot, the phone must not suddenly appear in the left hand in the next continuous shot without an actual transfer.

### A8. Dialogue Writing Rules

Dialogue must be natural spoken language, not bookish language. An 8-year-old speaks like an 8-year-old; an adult speaks like an adult; an elderly character speaks like an elderly person. Never give a child adult words. Keep lines short enough to speak naturally, with pauses where a human would pause. If a line sounds robotic when read aloud, improve its delivery (performance tags, pauses) — preserve the user's dialogue verbatim unless the user explicitly requests rewriting. Write each character's dialogue in that character's language (see Part D).

### A9. Reference Photo Quality Rules

A good reference photo makes registration succeed: the face must be clear and well lit, facing the camera, with a neutral expression, without sunglasses, masks, heavy shadows, or blur. If a provided photo is unclear, dark, or cropped so the face is cut off, tell the user and ask for a better photo instead of registering a weak reference. See the `character-consistency` skill for the registration rules.

### A10. Lip-Sync and Dubbing Workflow

Decide the order for each project before starting: voice first, then video matched to the voice; or video first, then voice matched to the video. Follow one order consistently inside a project. Dialogue timing must match the mouth: a line must not finish long before or after the character stops speaking. If lip-sync is not supported on the platform, say so honestly instead of promising it. Check mouth interior sharpness, teeth stability, and tongue on close-ups (see the `humanized-production` skill). Lip-sync here means `lip-sync-phoneme-viseme` through articulation_target `human-mouth-lips` for human and digital-human subjects; a fictional speaking animal or creature is articulated through its own articulation_target (`bird-beak`, `animal-muzzle`, `creature-jaw-mandibles`, or `other`) — never human lips on a bird, animal, or creature. A real animal is not assumed to speak.

### A11. Episode QC Checklist

Before delivering any episode, check it against the list: character faces and heights correct; voices correct for each character; emotions match the script; dialogue exact; no extra fingers, merged faces, or broken objects; clothing correct for the scene; sound and music present and matched; no contradiction with the story bible or the continuity tracker. Do not deliver an episode that fails a check without telling the user what failed. Inspect the beginning, middle, and ending, plus character appearances, facial identity consistency, important actions, hand-object interactions, character-to-character interactions, scene transitions, and audio and lip-sync where inspectable. Do not claim frame-by-frame inspection unless it was actually performed, and do not claim a video is completely defect-free without sufficient verification. Video regeneration has its own QC pass (see the `video-regeneration` skill, Section 8), which reuses this checklist plus the regeneration-specific checks — handovers, object transfers, and frame-by-frame comparison against the reference.

#### A11.1 QC severity — every defect gets a level

Every defect found in QC is graded on four severity levels. The level decides whether the video can be delivered.

- **Critical — release blocker.** Missing scene; corrupted video; wrong dialogue; wrong person or character; wrong action; broken export. A Critical defect blocks delivery, no exceptions — fix it before the video goes out.
- **Major — release blocker unless explicitly waived.** Face morphing; broken physics; serious continuity defect; unusable lip-sync; serious VFX integration problem. A Major defect blocks delivery unless the authorised user explicitly waives it, with the waiver recorded (what was waived, why, and who authorised it) — see the stage-gate waiver rule in Part F.
- **Minor — repair where practical or document.** Small shot-matching issue; small graphic-alignment defect; minor colour inconsistency. Fix it if it costs little; otherwise record it in the delivery notes so the user knows it is there.
- **Polish — optional finishing enhancement.** Small timing improvement; minor typography refinement; optional finishing enhancement. Do it only when time allows; never hold a delivery for a Polish item.

A defect with no severity assigned is a defect that has not been triaged — assign the level before deciding anything about delivery. The severity system applies to the episode QC checklist above and, by reference, to the video-regeneration QC pass, which reuses this checklist.

#### A11.2 Final delivery checklist

Before the master is handed over, verify every item: story completeness; character consistency; action and physical realism; camera and lighting continuity; dialogue and lip-sync; sound and music; colour consistency; frame rate and resolution; codec and file integrity; full playback (the whole video watched through, not sampled); backup and archive. A delivery that has not had a full playback is not a delivery — it is a hope.

#### A11.3 Post-mortem — learn from repeated failures

After a project with repeated generation failures, write a short post-mortem and keep it with the project: what failed repeatedly; which model or tool performed how; the common defects and their causes as far as they could be determined; what was tried and what worked; what to do differently next time. The post-mortem is a project record, not a blame record — its purpose is that the next project does not pay for the same failure twice.

### A12. Script-Driven Automatic Camera Angles

The camera angle is never random and never decorative. For every shot, read the script beat first — what is happening, what the character feels, what the story needs the viewer to feel — and let that decide the angle automatically. The user may override any choice, but the AI never picks an angle by habit, by rotation, or because it is a favourite shot.

**1. Read the beat before choosing the angle.** For each shot, identify (a) the story function — establish, reveal, confront, comfort, decide; (b) the feeling character's emotion; (c) the relationship between the characters in frame; (d) what the viewer must notice. The angle follows from those four — never from a fixed rotation or a favourite shot.

**2. Shot grammar.** The vocabulary: wide / establishing (place, scale, isolation); medium (action, body language); close-up (emotion, reaction); extreme close-up (a meaningful detail — eyes, hands, an object); over-the-shoulder (conversation, point of view); POV; low angle (power, threat, awe); high angle (vulnerability, smallness, loss of control); bird's-eye (fate, pattern); worm's-eye (overwhelm); Dutch tilt (unease — use sparingly); two-shot (relationship); group wide (dynamics).

**3. Beat-to-angle mapping.** Automatic defaults; emotion always wins over the table. Power / dominance / threat → low angle, slow push-in. Vulnerability / fear / defeat → high angle, slightly wider. Intimacy / confession / tenderness → close-up, eye-level, still. Isolation / loneliness → wide shot, character small in frame. Tension / something wrong → slow push-in or a small Dutch tilt, brief. Revelation / realisation → dolly-in to close-up as it lands. Conversation → shot-reverse-shot with matched eyelines, over-the-shoulder for the listener. Action / urgency → tracking shot, handheld energy, shorter cuts. Memory / dream / wonder → slow crane or gentle float. Comedy / lightness → wider, eye-level.

**4. Motivated movement only.** The camera moves only when the story moves — following a character, revealing something, or matching a change in emotion. No movement for its own sake; a static shot is right whenever nothing in the beat asks for movement.

**5. Lens language.** The lens follows the beat too: wider lens (35mm) for place and togetherness, normal (50mm) for honest human presence, longer lens (85mm) for intimacy and isolating the face from the background. Never change lens character inside one continuous moment without a story reason.

**6. Continuity across cuts.** Hold the 180-degree rule — never cross the line of action without a clear establishing re-set. Match eyelines in shot-reverse-shot; match on action; keep screen direction consistent so the viewer never has to re-find where anyone is.

**7. Realism — human camera, not perfect camera.** Allow the small human imperfections that make footage feel shot rather than rendered: a faint handheld sway in intimate scenes, a breath of focus hunting when reframing, slightly imperfect framing corrected mid-shot. Subtle: noticeable enough to feel human, never enough to distract. See the `humanized-production` skill (30.14 Camera Imperfection). This serves the repo's overall realism target: aim for the closest achievable realistic, human-generated feeling — never leave any part visibly artificial when a better choice exists; fidelity is verified shot by shot, not guaranteed by a percentage.

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

### B14. Audio Mastering — Delivery Profiles

Master the final audio of every video to the project's named delivery profile (`architecture/audio-delivery-profiles.json`): the profile's integrated loudness and true-peak limits, so dialogue, music, and sound effects are the same volume across episodes and platforms. A character's voice must not be louder in one episode and barely audible in the next. If no profile is named, ask which destination the video is for — there is no universal default.

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

Scripts are written in a fixed format: scene, characters present, dialogue per character, camera, emotion per line. If the user's script is weak — flat dialogue with no feeling — improve its delivery automatically: add emotion, natural pauses, reactions, and lively expression so the video has feeling, while keeping the story, the meaning, and the user's dialogue intact. Preserve the user's dialogue verbatim unless the user explicitly requests rewriting; emotion is added through performance, never by changing the words the user wrote. Never change the story to add emotion; add the feeling to the story the user gave. A video with no feeling is a failed video.

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

## Part F — Production Stage-Gate Workflow (G1–G6)

Every project runs through six stages in order. A stage is not finished until its acceptance is met, and a failed stage must not silently advance to the next one — the failure is fixed at that stage, or the stage is explicitly waived (see the gate status model below), never quietly skipped.

### G1 — Visual Planning

Before production: creative and technical brief; script and story breakdown; scene and shot list; Visual Style Bible; character and environment references; camera and composition plan; lighting plan where applicable; sound plan where applicable; continuity requirements; production restrictions. **Acceptance:** the production plan is sufficiently complete to start representative test shots.

### G2 — Test Production

Before expensive batch generation: generate representative test shots; test character identity; test camera framing and movement; test lighting and composition; test physical interactions; test performance and lip-sync where applicable; test visual quality and consistency. **Acceptance:** representative outputs are reviewed and approved. If a representative test fails, correct the production instructions before batch generation — never generate the whole project on top of a failing test.

### G3 — Editorial Review

Select usable takes; build scene assembly; create rough cut; evaluate narrative clarity; evaluate pacing and shot coverage; check visual continuity; check audio continuity. **Acceptance:** the scene and story communicate the intended meaning.

### G4 — Picture Lock

Final shot order; final duration; dialogue timing; scene transitions; approved editorial changes; final timeline version. **Acceptance:** the picture is locked. Changes after picture lock require a revision record and another affected-stage review — a locked picture is not re-opened casually.

### G5 — Finishing

VFX and repair; colour correction; creative grading; sound design; audio mixing; graphics and typography; final audiovisual review. **Acceptance:** the master is ready for delivery QC.

### G6 — Delivery

Full playback; visual QC; audio QC; technical export verification; file integrity; project backup; archive; delivery approval. **Acceptance:** all Critical and Major defects are resolved or explicitly waived by the authorised user (see A11.1).

### Gate status model

Every stage carries one status: **NOT STARTED**, **IN PROGRESS**, **PASS**, **BLOCKED**, or **WAIVED**. A stage marked BLOCKED names what blocks it; a stage marked WAIVED names the reason and who authorised it. A waiver requires explicit user authorisation and a recorded reason — a waiver without a recorded reason is not a waiver, it is a skipped stage, and it is not permitted. The gate statuses are recorded in the project record alongside the Master Shot Tracker (Part K), so the state of every stage is visible at a glance.

### Complexity-aware operation

Do not impose a full cinema-production bureaucracy on every short video. Use a proportionate workflow: **simple shorts** run a compact G1–G6 checklist (one line per gate, no separate documents); **regular episodes** run the complete production plan and test shots; **complex cinematic projects** run detailed planning, multiple test shots, editorial review and finishing in full. The gates are the same at every scale — only the paperwork shrinks. Never omit essential quality checks merely to save time: a short video with a wrong face is a failed video, however fast it was made.

## Part G — Production Complexity Tiers (P0–P3)

This is a production scope hierarchy — how much production craft a project carries. It is NOT a replacement for the Part E instruction-precedence hierarchy (user > identity > story > realism > cinematography > quality), which still governs whenever instructions compete. The tiers decide scope; Part E decides precedence. Never confuse the two.

### P0 — Essential (required for every project)

Story clarity; correct scene and action; visual readability; character and object continuity; dialogue correctness; basic exposure and focus quality, where applicable; file integrity; backup; final QC. A project that cannot meet P0 is not ready for delivery at any scale.

### P1 — Strongly Recommended (normal professional productions)

Composition; deliberate lighting; character performance; editing rhythm; shot matching; colour consistency; sound design; professional audio mixing. A normal professional production carries P0 + P1.

### P2 — Advanced (when the project requires and tools support them)

Advanced colour grading; complex VFX; simulation; detailed compositing; advanced motion control; complex camera setups. Apply P2 only where the project genuinely needs it and the tools genuinely support it.

### P3 — Specialized (only appropriate productions)

Drone photography; specialty lenses; high-speed camera work; virtual production; advanced motion-control rigs; specialized compositing and simulation. Apply P3 only to productions that call for it.

The production system selects the relevant tier from the project scope, quality target, tools, budget, and user requirements — and records the tier in the project record. Do not force P2/P3 work into every ordinary project: a simple short does not need a virtual-production rig. Never claim a capability exists merely because it appears in a production plan — a tier lists what the project aims for, not what the tools can already do; a capability is claimed only when it has been verified (see the honest-limits rules in the `kids-family-animation` skill, §16).

## Part H — Lighting Plan Template

Every scene that needs deliberate light carries a lighting plan, written before generation and checked at every cut. The plan is a template, filled per scene — not a separate file, and not a new system: it records the light the scene needs so the light stays the same light in every shot.

Required fields: project ID; scene ID; shot IDs; scene location; time of day; motivated light source; light direction; key light; fill or negative fill; backlight / rim light; hard or soft quality; intensity; colour temperature; contrast; shadow depth; practical light sources; exposure intent; background separation; visual reference; continuity notes.

Cover these lighting situations with the template — each one states its motivated source and its look, so the same situation is lit the same way every time it appears:

- **Natural daylight** — the sun is the key; shadows are short and hard at noon, long and warm at golden hour.
- **Window light** — the window is the motivated source; soft directional light from one side, the far side falls off.
- **Night interior** — practicals (lamps, screens, candles) motivate the light; pools of warm light in a dark room, never flat bright.
- **Practical lighting** — every visible lamp, screen, or flame in the shot is a light source the plan must account for; a practical that is on but lights nothing is a defect.
- **Thriller lighting** — hard, low, or single-source light; deep shadows; the threat is in what the light does not show.
- **Documentary lighting** — the available light is the light; no staged look is imposed on a real place.
- **Stylized animation lighting** — the light follows the locked style (see `cinematic-power` §1): a stylised world is lit for readability and mood, not for photographic realism.

Three-point lighting (key + fill + rim) is an available setup, not a universal requirement — use it where it serves the scene, never as a default every scene must carry. The lighting-continuity lock still applies (`humanized-production` 30.15): shadow direction, colour temperature, and light-source position are fixed per scene and locked across every shot. Do not force photographic equipment settings into AI models that cannot control them: the plan records creative intent (direction, quality, colour, contrast), and only records a camera or light setting where the tool actually exposes that control (see Part I).

## Part I — Camera Technical Profile

The camera system (A2, A12) already decides what the camera does creatively — angle, size, movement, motivation. The technical profile records HOW it is done, and it is capability-aware: a setting is recorded only where the tool that produces the footage actually exposes it.

### Captured footage (camera footage, live-action)

For footage captured with a real camera, the profile may record any of these optional fields: camera; lens; focal length; aperture; shutter speed or shutter angle; ISO or gain; white balance; focus; frame rate; resolution; codec; colour profile; bit depth; exposure settings; backup camera settings. Optional means optional — record what matters to the project and what the shoot actually used; never invent a value after the fact.

### AI-generated footage

For AI-generated footage, keep three things strictly separate, and never pretend a control is real when it is not:

1. **Creative camera intent** — what the shot should look like (angle, size, movement, depth, motivation). This is always part of the prompt and the shot list.
2. **Native provider controls** — the controls the provider actually exposes for this model (for example a documented camera-movement parameter or an aspect-ratio setting). Record only controls the provider documents for the model in use.
3. **Post-production controls** — what is done after generation (crop, reframing, stabilisation, speed ramping, colour work). These are real controls, but they happen after the model, not inside it.

Never pretend unsupported AI model parameters are real controls: a focal length, an aperture value, or a shutter speed written into a prompt for a model that does not expose it is a wish, not a setting — and it must be recorded as intent (item 1), never as a technical fact. The existing camera-language, lens and motivated-movement rules (A2, A12, `kids-family-animation` §5) still govern what the camera does; this profile only records how it was achieved.

## Part J — Emotional Visual Storytelling

Emotion in a scene is told with the whole picture, not with a single expression. For an important emotional beat, coordinate the shot on all of these together: camera framing; camera movement; lighting; expression; body performance; shot duration; sound; music; editing rhythm. A close-up on a face with flat light, still camera, and cheerful music tells no emotion at all — the systems must agree, or the beat fails. See `emotional-performance` §3 for the beat-by-beat arc this builds on.

### Emotional beat progression (optional)

For an important beat, the progression may be mapped in six steps: **Baseline → Stimulus → Recognition → Reaction → Peak → Aftermath.** Baseline is the emotional state before anything happens; Stimulus is what arrives; Recognition is the character understanding it; Reaction is the first visible response; Peak is the strongest moment; Aftermath is what remains. This is an optional planning tool, not a formula — use it where it helps the beat, and never force a scene through all six steps when the scene needs three. The script and the user's explicit direction always remain authoritative over this progression.

### Supported emotions

The coordination rules above apply to any emotion, and these seven are the ones that recur most and are most often mistold: loneliness; fear; shock; intimacy; power; confusion; awe. Each is directed as playable actions (A2.6) and coordinated across the systems above — loneliness, for example, is told with wide space, a small figure, stillness, and silence as much as with a face. Do not reduce any of these to a single facial expression, and never let one system contradict the others on the same beat.

## Part K — Production Management and Version Control

The existing records are preserved and still apply: shot-level provenance (B9), cost tracking (B10), backup and versioning (B11), multi-project namespaces (B12), rights and consent records (B17), character asset protection (C1). This part adds one unified tracker that connects them, so a shot's state is visible in one place instead of scattered across five records.

### Master Shot Tracker

One row per shot, all shots in the project, kept current through every stage gate (Part F). Required fields: project; scene; shot ID; shot purpose; story beat; shot size and angle; camera movement; character references; environment and prop references; lighting; audio requirements; prompt or reference version; AI model and version; generation take; continuity notes; production status; QC status; approval.

Status vocabulary for the tracker (production status): **PLANNED**, **TEST**, **APPROVED**, **GENERATING**, **SELECTED**, **REJECTED**, **LOCKED**. A shot is LOCKED only after picture lock (G4); a REJECTED take stays in the tracker with its reason recorded — rejected work is not deleted work, it is evidence of what was tried.

### Project workspace folder template

A project workspace uses this structure, adapted to the project — it is a working-folder template, NOT a mandatory public Git folder structure, and it never carries private data into the public repo:

- `01_script/` — script, breakdown, shot list.
- `02_references/` — style references, environment and prop references.
- `03_characters/` — character reference material (private data stays private — see C1; never commit private character photographs, voice references, consent documents, or user-private assets into the public repo).
- `04_tests/` — test shots and G2 results.
- `05_shots/` — generated takes, named by the convention below.
- `06_edit/` — assembly, rough cut, fine cut, picture lock.
- `07_finish/` — colour, sound, graphics, masters.
- `08_delivery/` — final exports, delivery checklist, post-mortem.
- `99_records/` — Master Shot Tracker, cost log, provenance log, backup log.

### Naming convention

Generated files and takes are named `PROJECT_S03_SH012_TK02_V003_YYYYMMDD.ext` — project code, season, shot number, take number, version, date. The name alone must identify the file: no `final_v2_REAL.mp4`, no undated `shot1.mp4`.

## Part L — Genre-Specific Skill Selection

Do not create duplicate genre skills — there is one skill per craft, and the genre decides which crafts are brought in, not which new skill is invented. This matrix is optional: it suggests which existing skills a genre normally needs. The user's chosen style and script always take precedence over the matrix.

| Genre | Skills usually brought in |
|---|---|
| Documentary | `cinematic-power` (narrated film structure), `production-systems` (this skill), `voice-consistency` |
| Geopolitics / investigative explainer | `explainer-animation`, `cinematic-power`, `production-systems` |
| Informative explainer | `explainer-animation`, `production-systems`, `voice-consistency` |
| Drama | `emotional-performance`, `production-systems`, `humanized-production` |
| Thriller | `cinematic-power`, `emotional-performance`, `production-systems`, `live-action-vfx` |
| Action | `live-action-vfx`, `cinematic-power`, `production-systems` |
| 2D animation | `kids-family-animation` (for its animation principles), `explainer-animation`, `production-systems` |
| 3D animation | `kids-family-animation`, `cinematic-power`, `production-systems` |
| Commercial | `agency-advertising`, `production-systems`, `cinematic-power` |

Do not force a thriller visual style into a documentary, and do not force cartoon exaggeration into photorealistic footage: the genre sets the palette, but the script and the locked style set the rules. When the matrix and the user's instruction disagree, the user's instruction wins.
