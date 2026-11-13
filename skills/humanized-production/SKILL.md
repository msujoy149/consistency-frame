---
name: humanized-production
description: Makes every video feel human-made, not AI-made. Covers all 36 humanization systems — performance-driven acting, single-pass dialogue, micro-motion, listener reactions, never-silence sound, non-verbal voice, gaze continuity, hands and physics, anti-plastic skin, editing rhythm, the film-finish pipeline, drift and artifact QC, camera and lighting imperfection, background life, cloth and hair physics, sound spotting, disclosure and provenance, detector self-QC, audio description, voice variants, code-switching, model pinning, re-anchoring, reference strategy, the human blind-test gate, and the realism budget.
---

# Humanized Production

A video that is technically consistent but feels robotic has failed. These 36 systems make every video feel human-made. Apply them to every project. Figures such as LUT strength and grain percentage are ranges to test per project, not fixed values. For the cinematic-power layer — music-beat editing, synchronized ensembles, trailer structure, and scale and colour scripting — see the `cinematic-power` skill. For the live-action and VFX layer — real human performance, CG creatures in live footage, water and wetness continuity, set extension, stunts, and real-animal performance — see the `live-action-vfx` skill. For the emotional-performance layer — stage performance, crowd, intimate drama, age performance, instrument sync, music as story, and cultural authenticity and object storytelling — see the `emotional-performance` skill.

## 30.1 Performance-Driven Acting (Optional Lane)

When the user can act a line, record it on a phone or webcam and transfer the real head, face, body, and hand motion onto the registered character (performance / motion transfer). A real take contains micro-expressions, timing, and weight that no prompt reliably invents. This lane is optional; when it is not available, use the script-driven emotion rules: emotion comes from the script and matches each line, the character feels the dialogue like a human actor, and a generic "AI smile" or flat fixed expression is never acceptable.

## 30.2 Single-Pass Multi-Speaker Dialogue

Generate a whole conversation in one call (multi-speaker dialogue, up to 10 voices where the tool supports it) instead of generating one line at a time and stitching. Real conversation has ~200 ms gaps, rare overlaps, and handoffs timed by the model. Stitched lines with clean identical gaps sound edited, not spoken. See the `voice-consistency` skill for the full dialogue rules.

## 30.3 Involuntary Micro-Motion

Every shot carries a micro-motion spec: blink cadence, tiny eye movements (saccades), breathing and chest rise, head micro-drift, and weight shifts. Subtle motion beats dramatic motion — the movements should be small enough to feel unconscious, not performed. Quality-control check: "dead eyes / frozen face" is a defect. The eyes are the first thing viewers notice, and a face that does not blink, breathe, or drift reads as dead even when the face itself is perfect.

## 30.4 Listener-Reaction Rule

When one character speaks, the other character must be visibly listening — micro-nods, brow movement, breath, gaze — and must NOT move their mouth. Two mouths moving at once is the commonest AI dialogue failure. In every dialogue shot, specify the listener's reaction explicitly: what they do while the other character speaks, and that their mouth stays still.

## 30.5 Room Tone / Never-Silence + 4-Layer Sound

Continuous ambience under every scene; room tone in every interior. Four sound layers, in order: (1) ambience / room tone, (2) foley on visible beats matched to the surface (stone, wood, grass), (3) dialogue, (4) music. Silence is a defect — even a quiet room has a low hum. Reverb matches the room; a studio-clean voice outdoors is an instant tell. Sound effects must match the action on screen in timing and in character; a silent action scene or a mismatched sound breaks the human feeling immediately.

## 30.6 Non-Verbal Voice Layer

Every dialogue line may carry performance tags — sighs, laughs, whispers, gasps, clearing the throat — plus breaths, hesitations (um/uh), stutters, trailing off, and ellipsis pauses. Never deliver a clean, pause-free take. Real speech is messy; overly smooth text-to-speech is the audio uncanny valley. See the `voice-consistency` skill for the full non-verbal voice rules.

## 30.7 Eye / Gaze Continuity

Specify per shot: the gaze target, the eye-movement direction, the pupil response to light, and the eye-line match across cuts — who looks at whom, and where. Gaze that does not follow head movement, or that does not match the other character across a cut, breaks the scene even when the face is perfect. Check eye-line continuity at every cut in a dialogue scene.

## 30.8 Hands & Physics Avoidance + Repair

Hands and physics are the most recognizable artifacts in generated video, so treat them as a first-class risk, not an afterthought:

- Frame hands out of the shot when they are not needed, give the character a simple object to hold, or use slow motion for hand shots.
- Keep hand shots to short 3–5 second segments.
- Scrub hands frame by frame in quality control: correct finger count, natural finger positioning, proper gripping, realistic hand-object contact, no fingers passing through objects.
- Repair warped hands with masked inpainting where the platform supports it.
- Never generate pouring, grasping, or tying as a hero action — film it or cut around it.

The same physics rules apply to every object a character touches, holds, picks up, carries, transfers, drops, or releases: the object must remain physically present, must not disappear, float, merge with hands or bodies, or teleport, and ownership must remain clear. If one character hands money to another, the first character must visibly hold it, the hand must approach, the receiver must make believable contact and grasp it, the giver must release it naturally, and the money must remain in the receiver's possession.

## 30.9 Anti-Plastic Skin

Name skin texture explicitly in prompts: visible pores, fine lines, freckles, uneven tone, under-eye texture, peach fuzz, slight asymmetry. Use side / skimming light to bring texture out. Ban the words "flawless", "perfect", and "airbrushed" from prompts. Too-perfect skin is a primary tell — real skin is never flawless, and plastic-looking skin, artificial facial textures, and excessive smoothing are defects. Characters must look realistic in every scene: real skin, real light on the face, real shadows — never flat or cartoon-like unless the user asked for a cartoon style.

## 30.10 Editing Rhythm

Edit like a human editor, not like a clip-stitcher:

- J-cut: the audio of the next shot starts 4–12 frames early.
- L-cut: the audio of the current shot trails past the picture cut.
- Cut mid-movement and cut on the action, not on every beat.
- Cut on the phrase, not on every beat of the music.
- Hard cut is the default transition.

Stitched clips with simultaneous audio and video cuts feel stitched; J/L cuts are what make an edit feel continuous and human. Do not compress multiple complicated physical actions into one visually confusing shot, and do not use unnecessary cuts.

## 30.11 Film-Finish Pipeline

After grading, apply the finish in this fixed order: correct, then creative LUT at reduced strength, then 35 mm grain (8–15%), then light blur. Highlight rolloff, halation, bloom, and gate weave are separate adjustable ingredients.

Caveat — LUT strength is a range to test, not a fixed value: sources disagree (a creative LUT at 20–40% mix per one guide, versus 50–70% for print emulations per another). Treat the strength as a per-project test range. Generated footage is too clean — ultra-sharp, plasticky, baked contrast — and a LUT alone on unstable footage makes drift more visible, so foundations (exposure, skin hue, shot-to-shot continuity) come first; never patch temporal problems in grading.

## 30.12 Voice-Drift Measurement

The audio twin of face-drift measurement. Measure speaker-embedding similarity per line and per episode, plus a prosody fingerprint (pace and pitch range) per character. A cloned voice can drift in timbre and pace across episodes unnoticed — measure it, and regenerate below threshold.

Caveat: this measurement is an inference drawn from face-embedding drift measurement — no source directly proposes voice-embedding quality control for this system — so treat thresholds as project settings to calibrate, not as settled industry values, and always confirm with a human listening check. See the `voice-consistency` skill for the full voice-drift rules.

## 30.13 Temporal-Artifact QC

Scrub every take for texture swimming, flicker, object drift, cadence stutter, missing motion blur, and morphing. Reject or regenerate; do not patch in grading. The problem lives in time, not resolution — a 4K clip can look faker than 720p phone footage. Check the beginning, middle, and end of every clip, plus every clip-boundary join: the last frame of one clip must match the first frame of the next — same character position, expression, outfit, background, and lighting.

## 30.14 Camera Imperfection

A perfectly locked, perfectly smooth camera reads as CGI. Real cameras breathe and hunt focus, so include: handheld breathing and micro-drift, focus breathing, focus pulls, subtle lens flare, natural motion blur and a 24 fps shutter feel, and reframing drift. Keep the imperfection subtle — it should feel like a camera operator, not like a shaky-cam effect. Choose camera movements and shot compositions according to the actual scene; never use unnecessary camera movement, excessive zooming, random angles, or distracting transitions.

## 30.15 Lighting-Continuity Lock

Shadow direction, colour temperature, and light-source position are fixed per scene and locked across every shot in that scene. Colour grading follows the script's time of day and light source (see the `production-systems` skill: full-moon night is cool blue moonlight, bright sunlight is warm daylight, evening is soft warm, morning is fresh morning light, dusk is orange-purple twilight, midnight is deep dark, and torch or flashlight light at night is warm torch light with real shadows). This system locks where the light comes from in every shot, so the grade and the light position never contradict each other across cuts. The grade never changes randomly from one shot to the next inside the same scene, and the character's skin and clothes always match the light of the scene they are in.

## 30.16 Background Life

Secondary motion in every shot — a curtain moving, leaves, distant people, steam, dust in light — at low amplitude. An empty, overly smooth background is a tell. Backgrounds are covered in full in 30.36; this system is the motion half of that rule: the background must not only look alive, it must move, slightly, all the time.

## 30.17 Cloth / Hair Physics

Hair and fabric follow wind, gravity, and momentum; they never float. Keep hair and cloth motion small in dialogue shots — large motion draws the eye away from the face and exposes physics errors. Fabric behaviour must be realistic: wrinkles, weight, and drape follow the pose and the movement, and creases change with pose, not randomly per shot.

## 30.18 Distance & Space in Voice

Voice level, reverb, and muffling change with camera distance and room — close is dry and intimate, far is quieter with more reverb; off-screen voices are muffled. A crisp studio voice in outdoor footage is a named tell. See the `voice-consistency` skill for the full rules. Note: this is an inference from the observation that ambient and echo mismatch gives generated video away; treat the exact treatment values as per-project settings.

## 30.19 Sound Spotting Sheet

Before generating sound, write a spotting sheet per shot: timecode, sound class, whether it is in sync or not, and distance. Ambience loops crossfade 0.5–1 s and change only at cuts. Ad-hoc sound-effect generation produces mismatched, unsynced sound — plan the sound first, then generate to the plan. Sound is half of realism: footsteps, water, birds, wind, room tone, doors, crowd sounds — whatever the place would really sound like.

## 30.20 AI Disclosure & Provenance Pack

Per-video disclosure checklist:

- The platform's AI-use disclosure (for example YouTube Studio's AI disclosure setting).
- The EU AI Act deployer disclosure (Article 50) where it applies.
- C2PA Content Credentials / SynthID where the tool supports them, with on-screen label wording when required.
- Keep provenance information (for example C2PA metadata) with generated media where the platform supports it, and keep a record of consent for every real person's photo and every voice used — who gave it, for what use, and when.

Follow the platform's rules; never hide a required disclosure. This is a checklist, not legal advice. Never use a real person's photo or voice without that person's permission.

## 30.21 Detector Self-QC

Run finished episodes through provenance-first checks (C2PA Verify, SynthID Detector) and a classifier ensemble as a triage score, never a verdict. Use them to find your own tells before viewers do. A detector score is a pointer to where to look, not proof that a video is or is not AI-generated — treat it as one input to human quality control, and never present it as a verdict.

## 30.22 Audio Description Track

Beyond captions, provide a narration of visual action in dialogue pauses (WCAG 2.1 Success Criterion 1.2.5), plus a descriptive transcript, so blind and low-vision viewers are not left out. The description track narrates what is happening on screen — who enters, what they do, where they are — in the gaps between dialogue, without talking over the dialogue itself.

## 30.23 Voice Ageing / State Variants

Per-character voice variants for age, illness, whisper/shout, tiredness, and cold — the voice parallel of visual ageing variants. When the story jumps in time or a character's state changes, the voice changes only in the ways time or state would change it, deliberately and consistently, and the change is recorded in the continuity tracker. See the `voice-consistency` skill for the full rules.

## 30.24 Code-Switching & Dialect Rule

Handle mid-sentence language switching (for example Bengali↔English) and regional accent explicitly. Test per language and per dialect with a separate listening test; do not assume a multilingual model is equally good in all of them — especially Bengali and code-switched lines need a separate listening test. See the `voice-consistency` skill for the full rules.

## 30.25 Model-Version Pinning + Golden Regression

Pin the exact model version per project and record it in the provenance log. Re-test a golden set of shots whenever a provider updates a model. Keep a fallback model per lane (video, voice, lip-sync). Providers silently update or shut down models; unpinned pipelines drift without anyone changing a prompt. If a pinned model is retired, record the change, re-run the golden set on the replacement, and tell the user what changed.

## 30.26 Re-Anchor Every ~8–16 s

Re-inject reference images and first-frame anchoring every ~8–16 seconds and at every scene change, because consistency degrades sharply past ~16 seconds and with time since last appearance. Long videos are built in clips; every clip starts anchored to the reference, not to the previous clip's drifted output. Check every clip-boundary join before delivery.

## 30.27 Reference-Count Strategy per Model

Document per-model reference limits, and use a multi-angle reference set (front, three-quarter, profile, expression) per character. A single front photo is the weakest reference set.

Caveat — reference limits differ between sources and must be verified on the vendor's own pages before they are relied on: one guide reports some models accepting up to 30 reference images while another reports up to 50 reference inputs for the same model family, and limits differ sharply between models (some accept only a few). Do not hard-code a limit from a secondary source; record the limit you actually verified for the model version you pinned (30.25), and re-check it when the model updates.

## 30.28 Human Blind-Test Gate

Before release, show episodes to viewers who do not know the video is AI-generated and record "what felt off" in their own words. Vendor scores saturate and miss long-form failures; unaided human "off" notes are the only signal that tracks the uncanny valley. Act on the notes: each "felt off" comment maps to a system in this skill (dead eyes, plastic skin, silent room, wrong hands) — fix the system, not just the shot.

## 30.29 Mouth-Interior QC in Lip-Sync

Check mouth interior sharpness, teeth stability, and tongue on close-ups. Prefer diffusion-class lip-sync for hero shots and a faster model for speed. Blurry teeth and lips are where cheap lip-sync fails. Dialogue timing must match the mouth: a line must not finish long before or after the character stops speaking. Check mouth interiors as part of the episode QC checklist, especially on close-ups where the defect is most visible.

## 30.30 Wardrobe Wear & Continuity Detail

Wrinkles, stains, wear, fit, and layering persist across shots; fabric creases change with pose, not randomly per shot. The wardrobe registry (see the `production-systems` skill) records what is worn; this system records how it wears. A jacket that is creased in one shot must not be smooth in the next without a reason, and a stain gained in one scene must still be there later in the same scene unless the story removes it.

## 30.31 Imperfection Budget

Deliberate, counted imperfections per shot — asymmetry, flyaway hairs, dust, a crooked prop — instead of "add imperfections" as a vague prompt line. A budget makes it checkable in quality control: each shot lists how many imperfections it carries and what they are, and QC verifies them. Too-perfect is a tell; uncounted imperfection is unverifiable. Note: this is an inference from the consensus that imperfections increase realism most — the counting mechanism, not the principle, is the inferred part.

## 30.32 Music-Ducking / Dialogue-First Mix

Music and sound effects duck under dialogue and never compete; dialogue carries ~60% of attention. Mastering sets loudness (target −14 LUFS, true peak below −1 dBTP); this system sets the balance that keeps dialogue intelligible and human. See the `voice-consistency` skill for the full mix rules.

## 30.33 Failure & Fallback Playbook

For each artifact type, document what to do when a shot fails — regenerate, inpaint, re-anchor, film it, or cut around it. Never silently ship a failed shot, and never repeat the same failed generation unchanged: if a regeneration fails the same way, change the approach (change the framing, shorten the shot, re-anchor, or cut around the problem) and record what was tried in the provenance log. If a defect is found and correction or regeneration is supported, identify the affected section, determine the cause as far as possible, correct the relevant instruction or parameters, regenerate the affected section, and recheck the output.

## 30.34 Real-Person Safeguards

For videos built from a real adult's photo or voice: the likeness is used only with that person's consent, for the agreed use, and the person can withdraw it; never make a real person say or do something they never did without a clear label. Child characters follow the stricter child-safety rules (see the `production-systems` skill: every scene, outfit, dialogue, and camera angle must be appropriate for a child, and nothing sexualised or unsafe involving a child is ever generated — that rule is absolute and overrides any script line that conflicts with it). Consent records (who gave consent, for what use, and when) are kept with the character's data and in the rights and provenance records.

## 30.35 Realism Budget

Track which humanizing steps (performance take, extra takes, grain pass, foley) are worth their credits and minutes per shot type. Spend realism where the viewer will feel it — faces, voices, hands, and sound — not everywhere equally. Record cost and credits per episode and per shot (generation calls, voice minutes, training), tell the user the running total when asked, and warn before starting work the user has not budgeted for. Never spend the user's credits silently.

## 30.36 Cinematic Backgrounds

The background is what the eye rests on most in a video, so every background is cinematic and realistic — detailed, layered, with depth, atmosphere, and life, matching the scene's place, time, and light. Never an empty, flat, or generic background. A background that looks painted or empty breaks the scene even when the character is perfect.

For every background, specify: the place and its layers (foreground, midground, background), the depth and atmosphere (haze, light shafts, dust, weather), the time of day and light source, and the life in it (secondary motion per 30.16 — a curtain, leaves, distant people, steam). The background must look believable, as if it was really filmed in that light, and must stay consistent in geometry and lighting across the shots of a scene.

## Applying the 36 Systems Together

No single system here makes a video feel human. The systems work as a stack: performance and emotion (30.1, 30.2, 30.6) give the acting, micro-motion and gaze (30.3, 30.4, 30.7) give the face life, hands and skin (30.8, 30.9) remove the commonest visual tells, sound and editing (30.5, 30.10, 30.19) remove the commonest audio and pacing tells, the finish pipeline (30.11) removes the clean digital look, QC and pinning (30.12, 30.13, 30.21, 30.25, 30.28, 30.29) catch what is left, and the budgets and playbooks (30.31, 30.33, 30.35) keep the work affordable and repeatable. Check the episode QC checklist (see the `production-systems` skill) before delivery, and do not deliver an episode that fails a check without telling the user what failed.
