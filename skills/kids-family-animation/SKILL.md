---
name: kids-family-animation
description: Professional kids & family animation — short-form videos for children and young audiences across 14 animation methods, with one locked visual style, a full camera decision system, 3D and 2D craft, story templates, and animation QC. Builds on character-consistency, voice-consistency, humanized-production, cinematic-power, and command-authority — it adds only the kids & family animation layer on top.
---

# Kids & Family Animation — Professional Short-Form Animation for Children

Professional, visually convincing, engaging, and commercially responsible short-form animated videos for children and young audiences. One project, one locked visual style, original stories, and the same character and voice consistency as every other video in this repo. This skill builds on the `character-consistency`, `voice-consistency`, `humanized-production`, `cinematic-power`, and `command-authority` skills — it adds only the kids & family animation layer on top. For the command rule that governs every video, see the `command-authority` skill: read and use the repo's skills first, and generate a missing system only after checking the repo's notes.

## 1. What It Is — And What It Is Not

- A short-form animated video for children and young audiences: funny, warm, curious, or exciting — never frightening, crude, or age-inappropriate. Age-appropriate content is a hard rule, not a preference (see the child-safety rules in the `production-systems` skill and the Made for Kids rule in the language, captions, and format rules: Made for Kids applies only to kids content or on request — a kids video is kids content, so the rule applies).
- Original stories, original characters, original dialogue, original music. Reference videos teach technique only — never copy a reference creator's characters, scripts, dialogue, music, logos, or unique protected visual assets.
- Never guarantee virality, monetisation, or recommendation placement. Never make repetitive, mass-produced videos with no meaningful creative variation.
- The production method of a reference video and the production method used for generation are separate decisions. A reference made in Blender, Maya, or Unreal Engine is studied for its camera language, character performance, lighting, animation, composition, and rendering — then its relevant visual qualities are reproduced with the available AI video-generation workflow.

## 2. Style Selection — Fourteen Methods, One Locked Style

Choose ONE method for the project, lock it, and hold it across every scene. Never mix incompatible styles accidentally.

1. AI-generated animation.
2. AI-assisted 3D animation.
3. Traditional 3D CGI animation.
4. Stylised 3D animation.
5. Photorealistic 3D animation.
6. Traditional 2D animation.
7. 2D digital animation.
8. 2D/3D hybrid animation.
9. Anime-inspired animation.
10. Cartoon character animation.
11. Stop-motion-inspired animation.
12. Game-engine-generated animation.
13. Real-world footage combined with animated characters.
14. Other professional animation techniques.

- Choose by the script and the audience: a funny animal story wants cartoon character animation or stylised 3D; a gentle moral story wants soft 2D; a fantasy adventure wants stylised 3D or 2D/3D hybrid. The method serves the story, never the other way round.
- Every project has a locked visual style (see the `cinematic-power` skill's style lock): one palette, one lighting mood, one level of realism, one character design language. Record it in the project and use it in every scene.
- For real footage combined with animated characters, see the `live-action-vfx` skill (CG creatures in live footage, shared light and shadow, eyelines). For a real person's photo turned into a realistic moving person, see the `realistic-person` skill — that is a different type from animation.

## 3. 2D Production Guidance

- **Line weight.** Thick, confident outlines for main characters; thinner lines for background details. Line weight stays consistent across scenes — a character's outline never changes thickness from shot to shot.
- **Shape language.** Every character is built from a few simple, readable shapes. Round shapes read friendly and safe; sharp shapes read energetic or mischievous. The shape language matches the character's personality.
- **Colour palette.** A small, warm palette for kids content: a few strong colours, soft backgrounds, clear separation between character and background. Never a cluttered frame.
- **Background art.** Simple, readable backgrounds with depth: a foreground, a midground, a background. Backgrounds stay consistent across scenes in the same location.
- **Posing and expressions.** Clear silhouettes — a pose must read at a glance. Faces change with the emotion; bodies stay simple. Expression changes with the story beat, not at random.
- **Limited animation.** Not every frame needs full movement: hold a pose, move only what the beat needs (a head turn, a blink, a pointing arm). Limited animation is a craft choice, not a defect — but a held pose must be intentional, never frozen by accident.
- **Frame-by-frame movement and motion cycles.** Walk and run cycles repeat cleanly; a cycle that drifts or changes shape mid-loop is a defect. Smear frames (a stretched in-between that sells fast motion) are used sparingly, only where the motion is fast.
- **Timing.** Comedy is timing: a pause before the surprise, a fast reaction after it. Timing follows the story beat — see §5.
- **Transitions, pans, and zooms.** Slow pans and zooms carry the camera between ideas; hard cuts mark a new scene. Never cut in the middle of a movement.
- **Visual metaphors.** Abstract ideas become characters or places (see the `explainer-animation` skill): an obstacle is a mountain with a face; a worry is a heavy backpack. A metaphor must be readable with the sound off.
- **Layered parallax.** Foreground, midground, and background move at different speeds when the camera moves — that is what makes a flat scene feel deep. Parallax speeds stay consistent across shots in the same scene.
- **Compositing.** Characters sit IN the scene: feet touch the ground, shadows fall the right way, scale matches the environment. A floating character is a defect (see §12).
- **Anime-inspired content.** Distinct composition, expressive framing, impact frames (a single held frame that sells a hit or a surprise), action timing, and visual language of its own. If the project is anime-inspired, the whole project is anime-inspired — never mix anime framing into a cartoon style by accident.

## 4. 3D CGI Production Guidance — And How AI Reproduces It

### 4.1 Character modelling

- **Silhouette.** The character must read from its silhouette alone — a clear, simple outline that a child can recognise. Test every character as a black silhouette before anything else.
- **Proportions.** Proportions match the audience and the tone: big heads and short bodies read cute and young; realistic proportions read older and more serious. Proportions stay fixed across every scene.
- **Facial and body structure, topology, clothing, accessories, surface details, material appearance.** Build the face for expression (big readable eyes, a mouth that can shape sounds); clothes and accessories follow the character's personality and stay consistent; materials look like what they are (soft fur, smooth plastic, rough wood).
- **Model sheets.** A character model sheet (front, side, back, face close-ups, hands, feet) is the identity anchor — see the `character-consistency` skill. A 3D-looking character without a model sheet will drift.

### 4.2 Rigging

- Skeleton structure, bone hierarchy, facial rigging, eye controls, mouth controls, body controls, hand and finger controls, IK/FK concepts, deformation quality. A rig that deforms badly (a bent elbow that collapses, a face that warps) is a defect — fix the rig, never ship the deformation.
- **Honest distinction.** An AI video model does NOT perform real 3D rigging or geometry operations. Never claim it does. When this skill talks about rigging, it describes the craft that the reference was built with — the AI reproduction strategy in §4.6 is how those visual qualities are approximated, not how rigging is performed.

### 4.3 Animation principles

- **Keyframe animation and pose-to-pose.** Block the key poses first (blocking), then fill the in-betweens. A scene with no blocked poses drifts.
- **Timing and spacing.** Timing is how long a movement takes; spacing is how the poses are distributed. Slow in, slow out: movements ease at the start and end, never at constant speed.
- **Squash and stretch.** A bouncing ball squashes on impact and stretches in flight; a character's body does the same, subtly. Never squash a face — faces stretch only in broad comedy, and only as far as the style allows.
- **Anticipation.** Before a big action, a small opposite movement (crouch before a jump, wind up before a throw). Without anticipation, actions feel sudden and unreadable.
- **Follow-through and overlapping action.** After the main action stops, loose parts keep moving (hair, clothes, ears, tails) and settle after the body. Different body parts move at different times — the arm follows the body, the hand follows the arm.
- **Secondary motion.** Hair, clothes, and props move because the character moves — never on their own.
- **Weight and balance.** A character has weight: steps land, the body shifts over the supporting foot, a heavy object is carried with effort. A character that glides without weight is a defect.
- **Walk and run cycles.** Cycles repeat cleanly, feet touch the ground, the body bobs with the step. A foot that slides on the ground is a defect.
- **Facial animation and lip-sync.** The face follows the dialogue: the mouth shapes the sounds being spoken (see the `voice-consistency` skill and §8); the eyes look where the character is thinking. A talking character with a still mouth is a defect.
- **Physical interactions and reactions.** A character that touches an object moves it; a character that is surprised reacts with the whole body, not just the face. Every important movement has a reason — never move a character randomly.

### 4.4 Lighting and rendering

- **Key light, fill light, rim light.** One main light (key), a softer light that lifts the shadows (fill), and a light from behind that separates the character from the background (rim). The three lights stay consistent in direction and colour across cuts in the same scene.
- **Environment lighting, global illumination, ambient occlusion, soft and hard shadows.** Shadows fall the same way in every shot of a scene; a shadow that jumps between cuts is a defect.
- **Subsurface scattering, material response, reflections, volumetric effects.** Skin glows softly, fur is soft, metal reflects, light in fog is visible. Materials respond to the light the way the real material would.
- **Render quality and colour management.** Clean edges, no flicker between frames, colours graded to the script's time of day and light source (see the script-driven colour grading rule in the `production-systems` skill).

### 4.5 Environment and scene construction

- Background geometry, props, environment depth, atmospheric perspective (distant things are paler and softer), world continuity (the world stays the same world from scene to scene), scene layout, character-to-environment scale, object interaction. A character must be the right size for its world — a child at a table sits at the table, not above it.

### 4.6 AI reproduction strategy

For each traditional 3D technique, this is how an AI-based video-generation workflow approximates its visual outcome:

- **Consistent 3D character references.** The same approved reference images (front, side, back, model sheet) are reused in every generation — see the `character-consistency` skill.
- **Multi-view character sheets.** Generate the character from several angles first; use the matching-angle view as the reference for each shot.
- **Image-to-video animation.** A still frame becomes the first frame of a moving shot; the motion follows the script beat.
- **Controlled camera movement.** Slow push-ins, pans, and tracking that follow the camera decision system (§5) — never random movement.
- **First-frame and last-frame conditioning.** The first and last frames of a shot are fixed, so the movement between them is intentional.
- **Motion references.** A reference movement (a walk, a wave, a jump) guides the generated motion; the generated motion is checked against it.
- **Scene continuation.** The next shot starts from the previous shot's last frame, so the world does not reset between cuts.
- **Inpainting and repair.** A defect in one area (a warped hand, a torn prop) is repaired in that area only — never by regenerating the whole scene and losing the good parts. A face is never inpainted: a merged or drifted face is a drifted face — regenerate fresh from the approved reference, as the `character-consistency` skill (§14) requires.
- **Multi-clip continuity.** Characters, voices, clothes, props, light, and the world stay the same across clips — see §11 and the `character-consistency` skill.
- **AI stills + slow movement (verified 2026-11-13).** The dominant small-channel method observed in the reference library: photoreal or 3D-style AI still images, slow Ken Burns zooms and pans, narration over stills — NOT true motion animation. The camera is static or near-static; cuts do the work. Use it for narration-driven stories (a rescue, a saga, a moral tale) where the story is told by the voice and the images, not by animated motion — and say plainly that the result is animated stills, not full motion animation. See §17 and library records R-06 to R-11, R-14, R-15.
- Never pretend an AI model performs actual 3D rigging or geometry. Say plainly what the workflow can and cannot do, and deliver only what was actually checked.

## 5. Camera Decision System — The Camera Follows the Story

Never choose an angle merely to look complicated. Every shot answers the 8 questions in §5.6 first. For the script-driven angle rule, see the `production-systems` skill (A12): the angle is chosen from the script beat — story function, emotion, character relationship, what the viewer must notice. This section is the full camera language that rule draws on.

### 5.1 Camera angles

- **Eye-level.** The camera at the character's eye height — neutral, honest, the default for conversation and everyday scenes.
- **Low-angle.** The camera below the subject looking up — the subject feels big, powerful, or scary. Use for a villain, a mountain, a moment of triumph.
- **High-angle.** The camera above the subject looking down — the subject feels small, weak, or lost. Use for a character in trouble or a first look at a new place.
- **Bird's-eye / top-down.** The camera directly above — the layout of a place, a chase, a pattern. Use sparingly; it stops the story to show geography.
- **Worm's-eye.** The camera on the ground looking straight up — the world towers over the character. Use for a small character facing something huge.
- **Dutch-angle.** The camera tilted — something is wrong, funny, or off-balance. Use briefly; a whole scene tilted is tiring.
- **Over-the-shoulder.** The camera behind one character's shoulder, looking at the other — a conversation, a secret, a decision. The shoulder in the foreground anchors the viewer in the scene.
- **Point-of-view.** The camera IS the character's eyes — the viewer discovers what the character discovers. Use for a surprise or a first look.
- **Three-quarter view.** The character turned three-quarters to the camera — the most common, most readable angle for dialogue and action.
- **Profile view.** The character in full side view — a walk, a journey, a standoff. Two characters in profile facing each other is a confrontation.
- **Front-facing.** The character looking straight at the camera — a greeting, a lesson, a direct address to the child viewer. Use for moments that speak TO the audience.
- **Rear-facing.** The camera behind the character, looking where the character looks — the viewer shares the character's view of what's ahead.
- **Ground-level.** The camera at the ground — a small animal's world, a rolling ball, a race. The ground itself becomes the stage.
- **Subject-relative angles.** The angle is chosen relative to what the subject is doing, not to the room — a climbing character is shot from below, a falling character from above.

### 5.2 Shot sizes

- **Extreme wide shot.** The whole world — where the story happens.
- **Wide shot.** The place and the characters in it — the scene's geography.
- **Full-body shot.** The whole character, head to feet — a new character, a costume, a walk.
- **Medium-wide shot.** The character from the knees up — action with room to move.
- **Medium shot.** The character from the waist up — conversation and everyday action.
- **Medium close-up.** The character from the chest up — a reaction, a decision.
- **Close-up.** The face — the emotion. The most important shot size in kids animation: a child reads a face before a line of dialogue.
- **Extreme close-up.** One detail — an eye, a hand, a key, a smile. Use for the one thing the viewer must not miss.
- **Insert shot.** An object, a note, a button — the clue the story needs.
- **Reaction shot.** A face responding to what just happened — the joke lands here, not in the action itself.
- **Establishing shot.** The first shot of a scene — where we are, when it is, what the mood is. Every new location gets one.

### 5.3 Camera movement

- **Static camera.** The camera does not move — the action happens inside the frame. Use for comedy timing and for moments the viewer must study.
- **Static-camera Shorts grammar (verified 2026-11-13).** Viral Shorts often use NO camera movement at all: static shots, hard cuts only, one location, one gag. Observed across the 4-video watch, the channel research, and the Cocomelon video in the reference library — no pans or push-ins in the sampled frames. When the script is a Short, a static camera with hard cuts is a legitimate choice, not a missing movement: choose movement only when a beat needs it. See §17 and library records R-01 to R-05.
- **Slow push-in.** The camera moves slowly toward the subject — attention tightens, emotion grows. The default movement of this system.
- **Pull-out.** The camera moves back — the world opens up, the scene ends, a surprise is revealed by the wider view.
- **Dolly-in / dolly-out.** The camera moves forward or back on a track — smooth, intentional, motivated by the story.
- **Tracking shot / side tracking / follow shot.** The camera moves with the character — a walk, a run, a journey. The character stays in frame while the world passes.
- **Pan.** The camera turns left or right — from one character to another, from a face to what it sees.
- **Tilt.** The camera turns up or down — from feet to face, from ground to sky.
- **Crane movement.** The camera rises or falls — a grand reveal, a goodbye, a world seen from above.
- **Orbit / arc movement.** The camera circles the subject — a moment of wonder, a decision, a transformation.
- **Pedestal movement.** The camera rises or falls straight up or down without tilting — a character growing taller, a fall.
- **Handheld-style movement.** Slight, imperfect shake — excitement, running, a chase. Use lightly in kids content; too much shake is uncomfortable.
- **Subject-following camera.** The camera stays with the moving subject — the viewer travels with the character.
- **Virtual camera movement.** In AI-generated video, the camera is a choice made at generation: the same movements above, described as instructions, held steady across the shot.

### 5.4 Lens and perspective

- **Wide-angle perspective.** More of the world in frame, close things look bigger — a small room feels big, a character near the camera feels huge.
- **Normal perspective.** The world as the eye sees it — the default.
- **Telephoto perspective.** Distant things look close and compressed — a character far away feels near, the background flattens.
- **Focal-length choices, depth of field, perspective distortion, subject separation, foreground and background depth, focus pulls, lens compression, camera-to-subject distance.** These are the tools that separate the subject from the background and tell the viewer where to look. A shallow depth of field (subject sharp, background soft) puts the face first; a deep depth of field (everything sharp) shows the world.
- **Estimated visual equivalents only.** Never invent exact focal lengths or camera settings from appearance alone. If the actual lens or camera configuration is unknown, label it as an estimated visual equivalent — say what it LOOKS like, not what it WAS.

### 5.5 Composition

- **Rule of thirds.** The frame in nine parts; the subject sits on a line or a crossing, not dead centre — unless the moment wants the centre.
- **Central composition.** The subject dead centre — a greeting, a hero moment, a direct address.
- **Symmetry.** Both sides mirror — order, calm, a grand place.
- **Leading lines.** Roads, fences, rivers, and arms that point the eye to the subject.
- **Foreground framing.** Something in the near foreground (a branch, a doorway, a shoulder) frames the subject and adds depth.
- **Negative space.** Empty space around the subject — calm, loneliness, or room for a big emotion.
- **Character placement and visual hierarchy.** The most important thing in the frame is the biggest, brightest, or sharpest — never two things competing.
- **Screen direction.** Characters move left-to-right on a journey, right-to-left when returning. A character that crosses the screen the wrong way confuses the viewer — hold screen direction across cuts.
- **Headroom and look room.** Space above the head, space in the direction the character looks. A character pressed against the frame edge feels trapped; a character with room to look into feels free.
- **Safe zones for vertical video.** In 9:16, keep faces, text, and the main action inside the central safe area — the top and bottom edges are where platform buttons and captions cover the frame.

### 5.6 The 8-question decision system

For every scene, answer these eight questions before choosing anything:

1. What is the main story beat?
2. Which character or object should attract attention?
3. Which camera angle communicates that beat most effectively?
4. What shot size is appropriate?
5. Should the camera move — and if so, how?
6. What lens perspective is suitable?
7. What should remain visible in the background?
8. How should the shot transition into the next scene?

The camera follows the story, the emotion, and the physical action. Do not randomly select cinematic angles merely to make a video look complicated.

## 6. Character Performance

- **Personality first.** A character's personality decides how it moves: a brave character walks fast with its chest out; a shy character walks slowly and looks down. Movement without personality is random movement.
- **Facial reactions and eye direction.** The eyes look where the character is thinking. A character that looks at the wrong thing confuses the viewer — the eyes lead the audience.
- **Body language.** Posture, gesture, and walk carry the emotion: slumped shoulders are sad, bouncing steps are happy, frozen stillness is fear. The body says what the dialogue does not.
- **Comedy timing.** A pause before the surprise, a fast reaction after it, a slow realisation. The reaction shot (§5.2) is where the joke lands.
- **Surprise, suspense, curiosity.** A held shot builds suspense; a sudden cut delivers surprise; a slow push-in builds curiosity. The camera and the performance work together — never one without the other.
- **Friendship, conflict, emotional development.** Characters change across the video: a friendship forms, a fear is faced, a mistake is fixed. The ending must show the change — a character that ends exactly where it started learned nothing.
- **Character interaction and physical comedy.** Characters react to each other, not past each other: one speaks, the other listens (see §8). Physical comedy comes from weight, timing, and surprise — a slip, a bump, a mistimed jump — never from pain or cruelty.
- **Visual storytelling.** The story must be understandable with the sound off wherever practical. If a scene needs its sound to be understood, the visual storytelling is wrong — fix it before delivery.

## 7. Story Structures — Ten Reusable Templates

Each template is a structure for ORIGINAL scripts. Never copy a reference creator's story — use the structure, write your own story.

1. **Funny animal stories.** An animal with a human problem (a cat that wants to be a chef, a dog that loses its favourite ball). One funny problem, three failed attempts, one clever solution.
2. **Cute animal adventures.** A small animal on a big journey — the world is large, the animal is small, the kindness of others helps it home.
3. **Friendship stories.** Two different characters (different sizes, different habits, different wishes) learn to help each other. The friendship is tested once, then proven.
4. **Family stories.** A family at home: a small problem (a lost toy, a burnt cake, a rainy day) becomes a warm day together. The ending is togetherness, not victory.
5. **Mystery and surprise.** Something small is missing or strange; clues appear one by one; the answer is simple and kind — never frightening.
6. **Cartoon vehicle adventures.** A vehicle with a personality (a brave little train, a curious boat) goes somewhere new, meets a problem on the road, and solves it with help.
7. **Fantasy adventures.** A door, a map, or a dream opens a magical place. One clear goal, one friendly guide, one obstacle, one return home.
8. **Moral stories.** A character makes a mistake (lies, takes, gives up) and learns why it matters — the lesson is shown in the story, never lectured at the viewer.
9. **Funny character interactions.** Two characters who misunderstand each other, again and again, until the misunderstanding itself becomes the joke — and the resolution.
10. **Educational entertainment.** One idea, taught through a story: a number, a word, a colour, a habit. The idea is shown, not told — the character discovers it, the viewer discovers it with them. See the `explainer-animation` skill for the one-idea-per-scene structure.

Verified series formats (recurring hero, multi-part saga, absurd-premise Short) are in §17 — they are formats for original scripts, never templates to copy.

## 8. Voice and Dialogue

Reuse the `voice-consistency`, `language-authenticity`, `humanized-production`, and `emotional-performance` skills — do not rebuild them here.

- **Natural human delivery.** The voice sounds like natural human communication: real rhythm, real pauses, real breath. No robotic narration, no unnatural sentence rhythm, no overly polished artificial delivery, no unnecessary exaggerated emotion, no flat dialogue, no inconsistent character voices.
- **Mouth movement matches spoken sounds.** The mouth shapes the sounds of the language being spoken (see the `language-authenticity` skill). A talking character with a still mouth is a defect.
- **Facial expressions support the dialogue.** The face shows what the line means — a happy line on a sad face is a defect.
- **The listener reacts naturally.** While one character speaks, the other listens: nods, blinks, smiles, frowns. A listener frozen like a statue is a defect.
- **Only the intended speaker moves their mouth.** In multi-speaker dialogue, the silent character's mouth stays closed — see the single-pass multi-speaker rule in the `voice-consistency` skill.
- **Breathing, pauses, laughter, and reactions are appropriate.** A laugh after a joke, a breath before a long line, a pause before a surprise.
- **Preserve the user's preferred language and requested voice style.** Each character keeps their own voice and language across episodes (see the `voice-consistency` and `language-authenticity` skills).

## 9. Sound Design — A Shot-Level Sound Plan

Reuse the existing professional sound systems (see the `production-systems` skill's sound design system and the `humanized-production` skill's never-silence sound and sound-spotting rules) and extend them for animation. Build a shot-level sound plan: for every shot, list the sounds that shot needs. Every sound must correspond to the visible action.

- **Character-specific dialogue and narration.** Each character's dialogue in that character's voice; narration only where the story needs it — a story told by visuals needs little narration.
- **Voice acting.** Performed, not read: the actor plays the emotion of the line.
- **Foley.** Footsteps, cloth rustles, doors, hands on objects — the small sounds that make a world real.
- **Animal sounds, vehicle sounds, environmental ambience.** A cat meows like a cat; a train sounds like a train; a forest sounds like a forest. Ambience never stops — a silent world is a dead world.
- **Music.** Music follows the emotion: light for play, tense for suspense, warm for the ending. Music ducks under dialogue — the words always win.
- **Action effects, transitions, emotional sound cues, audio perspective.** A jump has a whoosh, a landing has a thud, a surprise has a sting. Sounds get quieter with distance — audio perspective matches the camera distance.
- **Lip-sync timing.** Sound and picture agree on every line — see §8.
- **Original or properly licensed audio only.** Never copy audio from reference videos without permission. Credit alone is not a licence: a reference creator who animates over borrowed audio and credits the audio's creator does not make that audio licensed for our use — our productions use original audio or audio licensed to us.

## 10. Short-Form Structure — Built for Vertical Shorts

The main target is vertical short-form content, especially YouTube Shorts. Build the story for the format:

- **Opening visual.** The first frame is already interesting — a face, a question, a strange object. No black screen, no slow fade-in.
- **First-second hook.** The first second communicates something visually interesting — the viewer decides in one second whether to stay.
- **Story setup.** Who, where, what is wanted — in seconds, not minutes.
- **Character introduction.** The main character arrives with a clear wish or problem.
- **Main action.** The character tries; something goes wrong or right.
- **Escalation.** The problem grows — a second try, a bigger obstacle, a funnier failure.
- **Surprise or emotional payoff.** The turn: the clever solution, the kind act, the funny reveal.
- **Ending.** The wish is met or the lesson is learned — a satisfying, complete ending.
- **Replay potential.** The ending invites a second watch: a joke that is funnier the second time, a detail the viewer missed, a loop that flows back to the start.
- **Different durations, different templates.** Analyse different durations rather than forcing every video into one fixed duration — a 15-second joke and a 60-second adventure are different structures, not the same structure stretched.
- **No slow openings.** Avoid unnecessary intros, logos, and slow openings. The story starts at once.
- **Understandable without sound.** The story must remain understandable even when the viewer watches without sound, wherever practical.

## 11. Continuity

- Characters, voices, clothes, props, light, and the world stay the same across scenes and episodes — see the `character-consistency` and `voice-consistency` skills.
- The world stays the same world: a house keeps its rooms, a forest keeps its trees, a vehicle keeps its colour. A background that changes between cuts is a defect.
- Time of day and weather stay consistent inside a scene; a change is a story beat, never an accident.
- Every scene's last frame connects to the next scene's first frame — see the scene-continuation rule in §4.6.

## 12. QC Checklist — Animation

Run every group before delivery. Never claim a video passed a QC check unless the actual output was inspected.

**Character QC** — correct identity; correct proportions; consistent face; consistent body; correct clothing; correct voice; correct character count.

**Camera QC** — appropriate angle; correct shot size; correct screen direction; stable composition; natural perspective; appropriate camera movement; correct subject focus.

**Animation QC** — natural movement; correct weight; proper contact (feet on the ground, hands on objects); no floating; no clipping; no object penetration; no teleportation; no accidental deformation; no flickering; no inconsistent movement.

**Visual QC** — style consistency (the locked style holds in every scene); lighting continuity; shadow continuity; background consistency; correct materials; appropriate colours; no unwanted visual artefacts.

**Audio QC** — natural dialogue; correct lip-sync; appropriate sound effects; consistent voices; balanced music; no clipping or unintended silence.

**Story QC** — clear opening; understandable story; appropriate pacing; emotional engagement; satisfying ending; age-appropriate content.

Do not deliver a video that fails any check without telling the user what failed.

## 13. Reference-Analysis Methodology

Study every useful reference, regardless of whether it was made with AI, traditional 3D CGI, 2D animation, or a hybrid pipeline. Learn the underlying craft. For every analysed video, create a structured record:

1. Reference URL. 2. Channel name. 3. Video title. 4. Publication date. 5. Duration. 6. Aspect ratio. 7. Animation category. 8. Probable production method. 9. Character design. 10. Environment design. 11. Camera angles. 12. Shot sizes. 13. Camera movements. 14. Lens and perspective observations. 15. Lighting. 16. Animation and motion. 17. Facial performance. 18. Dialogue and voice style. 19. Sound design. 20. Editing rhythm. 21. Story structure. 22. Audience appeal. 23. Distinctive production techniques. 24. Techniques reusable in our system. 25. Technical limitations and uncertain observations.

- Where possible, create a timestamped shot breakdown (for example: 00:00–00:02 — opening close-up; character discovers an unexpected object). Do not fabricate timestamps, camera settings, or observations.
- Open and watch the actual video if access allows. Analyse the entire video, not just its thumbnail. Record the URL and publication date. Separate verified facts from visual inference. Do not claim to have watched a video if only its title, thumbnail, description, or transcript was available. When direct access is unavailable, request an uploaded video or another accessible reference.
- Do not automatically assume that all videos from one channel use the same production method — classify the production method separately for each video whenever possible. Study Shorts separately from long-form uploads.
- **Status: records exist for fully watched videos only (2026-11-13).** Real records live in `docs/research/kids-animation-reference-library.md` (records R-01 to R-17) — the 4-video watch, the one popular-channel video that played, and the videos actually watched in the 7-channel research. Videos that could not be played are NOT recorded: their technique stays out until the user supplies the video files and they are watched in full (see the library's "Pending research" note). Never invent a channel, a video, a title, a date, or an observation. See `docs/research/kids-animation-reference-analysis.md` for the method and `docs/research/kids-animation-reference-library.md` for the permanent library.

## 14. Permanent Reference Library & Continuous Research

The repo keeps a permanent reference library of verified production knowledge — not just links. The library lives in `docs/research/kids-animation-reference-library.md`.

- **Ten knowledge areas.** Every discovery is classified into one of: (1) camera and cinematography, (2) 3D CGI production, (3) 2D animation, (4) AI animation production, (5) character performance, (6) storytelling, (7) dialogue and voice, (8) audio and sound design, (9) editing and retention, (10) kids Shorts trend intelligence.
- **Check before adding.** Before adding anything, check whether the knowledge already exists in another skill — extend that skill instead of duplicating it. Preserve all previous capabilities; never delete, replace, or weaken an existing skill.
- **New reference links are accepted continuously.** When the user sends new links, inspect them, compare with the library, identify new techniques and improvements, and record what is new.
- **Verify before making it permanent.** Verify a technique BEFORE making it a permanent rule. A new trend is not automatically a permanent rule — a trend becomes a rule only after it is observed, checked against the existing skills, and confirmed to work. Never treat every new trend as a permanent rule.
- **Update the appropriate skill.** When a verified technique belongs in a skill, update that skill (or this one), preserve previous knowledge, and record the date and source of each discovery.
- **The library decides with the script.** When the user later supplies a script, the system consults the library and decides visual style, animation method, camera angles, shot sizes, character actions, dialogue style, sound design, scene timing, and editing structure automatically — the user gives only the script, and the system does the rest (see §15).

## 15. Script-Only Workflow

After this skill is integrated, the user gives only a script — and the system does the rest. The user provides: a story script; optional character names or registered character references; optional special instructions. The system automatically:

1. Reads the script.
2. Identifies the content category.
3. Loads this kids & family animation skill.
4. Loads the `character-consistency` skill when needed.
5. Loads the `voice-consistency` skill when needed.
6. Loads the relevant 2D, 3D, cinematic, or AI-animation guidance.
7. Loads the camera decision system (§5).
8. Loads the `humanized-production` system.
9. Loads the appropriate sound and editing systems.
10. Prepares a complete storyboard and shot list.
11. Selects camera angles according to the story.
12. Creates the required visual and audio assets.
13. Generates and assembles the video.
14. Runs the QC checklist (§12).
15. Delivers the finished video and a concise production summary.

If the script lacks an essential detail, ask the smallest necessary clarification. Do not repeatedly ask questions whose answers are already stored in the project.

## 16. Honest Limits — Say Plainly What Cannot Be Done

- If the platform cannot hold the locked style, a character, or a camera movement across scenes, say so plainly instead of promising it — and say what it can do instead.
- If a language version's quality or a lip-sync cannot be verified, say so plainly.
- Never claim a video is native-perfect, lip-synced, or QC-passed without the checks to back it.
- Never claim a reference was watched when only its title, thumbnail, or description was seen. Never present an invented observation as a verified fact.
- Rights and safety: use reference videos to learn techniques, not to reproduce protected creative expression. Respect child safety, privacy, consent, and platform requirements. Use licensed tools and commercially permitted assets. The core target stays realistic and humanized video generation — this skill adds animation craft to that target, never replaces it.

## 17. Verified Techniques from Observed References (2026-11-13)

Every technique below was observed in videos actually watched on 2026-11-13 and recorded in the permanent reference library (`docs/research/kids-animation-reference-library.md`, records R-01 to R-17). Each item names its knowledge area and its library records. Nothing here comes from a video that could not be played — those stay out until they are watched in full.

### 17.1 AI stills + slow movement (area 4 — AI animation production)

The dominant small-channel method observed: photoreal or 3D-style AI still images, slow Ken Burns zooms and pans, narration over stills — NOT true motion animation. The camera is static or near-static; cuts do the work. Use it for narration-driven stories (a rescue, a saga, a moral tale) where the story is told by the voice and the images, not by animated motion — and say plainly that the result is animated stills, not full motion animation. See §4.6 and library records R-06 to R-11, R-14, R-15.

### 17.2 Recurring hero + rescue/emotion-of-the-day (areas 5, 6 — character performance, storytelling)

One fixed character, a new crisis each video, an emotional payoff, a Part 2 or vote hook at the end. Observed: a recurring heroine who rescues a different person from a different danger each time (family member kidnapped, villagers stranded in a flood), and a recurring pair of rival characters whose moral/emotional saga continues across videos (exam cheating, wrongful arrest, a showdown). The hero is the same every time; only the crisis changes. The payoff is emotional (a reunion, gratitude) as often as it is a victory. See library records R-08 to R-11.

### 17.3 Multi-part saga + Part 2 hook, and vote-prompt endings (areas 6, 9 — storytelling, editing and retention)

The ending is a promise, not a resolution: the video stops at the crisis and asks the viewer to subscribe for Part 2. Observed in multi-part sagas (an atomic-bomb saga, a dog saga, a rotating-cast format). A vote prompt is the same idea in one video: the ending asks the audience to choose the winner (like/subscribe for one side, comment for the other) instead of resolving the showdown. Use either only when the next part genuinely exists or the vote genuinely decides something — never promise a Part 2 that will never be made. See library records R-06, R-10, R-11, R-14.

### 17.4 Static-camera Shorts grammar (area 1 — camera and cinematography)

Viral Shorts often use NO camera movement at all: static shots, hard cuts only, one location, one gag. Observed across the 4-video watch, the channel research, and the Cocomelon video — no pans or push-ins in the sampled frames. When the script is a Short, a static camera with hard cuts is a legitimate choice, not a missing movement: choose movement only when a beat needs it. See §5.3 and library records R-01 to R-05.

### 17.5 Game-engine animation — observed detail (area 2 — 3D CGI production, as observed detail)

Method 12 (game-engine-generated animation) is a real viral category, confirmed by search results on 2026-11-13: physics-sandbox driving (BeamNG.drive, 23M and 24M views), sandbox chase animation (Garry's Mod, 112K views), and block-world animation (Minecraft, 2.1M views) — all in the cartoon car / monster truck Shorts searches. The observed detail: the game engine supplies the physics, the vehicles, and the crashes; the video adds the framing, the cuts, and the joke. The engine is the production method; the comedy is in the edit. Recorded in the library's trend-intelligence section (search results, 2026-11-13).

### 17.6 Nursery-rhyme structure (areas 6, 9 — storytelling, editing and retention)

Observed in the Cocomelon video watched in full: song first — the song and the on-screen lyrics start within the first seconds, with no spoken intro; the action repeats per lyric line; cuts land on song lines; a pretend game ends with a real payoff (mud play pretending to bake, finished by a real cake). Big readable lyrics on screen, bright colour, repetition, tactile play, a real object finishing a pretend game. See library record R-05.

### 17.7 Absurd-premise Short format (area 6 — storytelling)

"The [animal/object] Who [did something absurd or heroic]": a watermelon that trains to be a superhero, a noodle that fights a raccoon, an egg that does not want to be breakfast. The premise is absurd and played straight; the training montage or the chase is the middle; the payoff is a visual gag (a karate chop, a spin like a tornado). No fixed cast is needed — the format carries the video. See library records R-14, R-15.

### 17.8 Multi-language dubbing of one story (area 7 — dialogue and voice; a distribution note, not a production technique)

One story, dubbed into many languages, each language in its own playlist (observed: English, Spanish, French, Swedish, Portuguese, Hindi, Arabic for the same two stories). This is distribution, not production: the video is made once and re-voiced. It is recorded here because the skill's script-only workflow must know it exists — when the user asks for the same video in several languages, the language-authenticity skill (separate versions, same voice profile, lip-sync per language) already governs how it is done; this note only records that the format is observed in the wild. The observed channel's audience was tiny, so this is a verified format, not a verified success. See library records R-12, R-13.

### 17.9 Live-action costume-play Shorts — trend intelligence ONLY (area 10)

The biggest kids Shorts in the research set (774M, 596M, 515M views) are live-action costume-play: a child in a furry monster costume jumping into a hula hoop, a girl choosing costume shirts with a red X for wrong choices — music only, static camera, 10–30 seconds, one visual gag. They are NOT animation and they do not enter this skill as a method. They are recorded in the library as trend intelligence because their Shorts grammar (instant gag, static camera, music only, a choosing game the viewer plays along with) matches the animation Shorts — the grammar is reusable, the footage is not. See library records R-16, R-17.

### 17.10 Rights — borrowed audio (area 8 — audio and sound design)

A reference creator who animates over borrowed comedy audio and credits the audio's creator in the title or description does not make that audio licensed for our use. Credit alone is not a licence. Our productions use original audio or audio licensed to us — see §9. This is recorded here because the pattern (animate over viral audio, credit the creator) was observed repeatedly in the research, and the repo's rights rule (B17 in the `production-systems` skill) must be applied to it explicitly: observing the method is not permission to copy it.
