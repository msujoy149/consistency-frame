# Consistency Frame — What Is Still Missing to Feel Human (research vs the earlier baseline)

**Date researched:** 12 November 2026. **Method:** web index (`browser_search`) only — no live page opens, no hands-on tool tests. Every claim below is therefore **index-sourced**, not `verified live`, unless marked otherwise. Prices are quoted only where a source stated them, with the source's check-date; verify on the vendor page before budgeting — several sources disagree with each other on current prices.
**Baseline assumed:** the baseline system as described in the mission (character registration/recall, face+height fidelity, script-driven emotion, 11 + 18 systems, script-driven colour grading by time-of-day/light, VoiceStudio/OmniVoice, OpenMontage stitching, private overlay, multi-character contact without overlap, auto script enhancement, opt-in captions, any aspect ratio/language). Gaps below are items **not** in that list, or where the existing system is only partial. Where a gap is my inference from a sourced fact (no source directly proposing it for this system), it is flagged **[INFERENCE]**.

## Summary

The single biggest missing leap is **not a better prompt — it is a real human performance driving the pixels and the voice**. The 2025–2026 state of the art that the baseline system does not yet use is: (1) performance/motion transfer (record a real take on a phone/webcam and transfer face+body+hands onto the character — Runway Act‑Two, Kling Motion Control, Wan‑Animate); (2) **single-pass multi-speaker dialogue** (ElevenLabs Text to Dialogue, up to 10 voices, with overlaps/interruptions timed by the model, instead of stitching one line at a time); (3) an **involuntary-motion system** (blinks, saccades/eye-tracking, breathing, weight shifts — the eye is now the #1 giveaway); (4) a **never-silence sound layer** (room tone + surface-matched foley + reverb that matches the room); and (5) a **film-finish + editing-rhythm layer** (J/L cuts, cut-on-action, correct → LUT at reduced strength → grain 8–15% → blur). Everything else in §2 is smaller, addable, and mostly cheap. The system already covers identity, emotion scripting, grading-by-script and QC checklists — the gaps are concentrated in **motion, ears, eyes, hands/physics, editing, disclosure and maintenance**.

---

## 1. Prioritised NEW gaps / improvements (not already in the baseline system)

### P0 — do first (largest human-feel gain)

| # | Headline | Why (one line) | Source |
|---|---|---|---|
| 1 | **Performance-driven acting system (driving-video → character)** — add an optional "act it yourself" lane: record the line on phone/webcam, transfer head/face/body/hands onto the registered character | Prompted emotion can describe a feeling; a real take *contains* micro-expressions, timing and weight that no prompt reliably invents | https://stacksheriff.com/ai-tools/runway-act-two-tutorial/ ; https://hackernoon.com/ai-motion-capture-turns-your-phone-into-a-mocap-studio-heres-the-workflow-i-run |
| 2 | **Single-pass multi-speaker dialogue** — generate a whole conversation in one Text-to-Dialogue call (up to 10 voices, overlaps/interruptions timed by the model) instead of per-line TTS stitched in the editor | Stitched lines have clean, identical gaps; real conversation has ~200 ms gaps, overlaps <5% of the time, and handoffs the model times better than an editor | https://www.kukarella.com/resources/text-to-speech/how-to-create-realistic-multi-speaker-dialogues-with-ai ; https://aiwiki.ai/wiki/elevenlabs_v3 |
| 3 | **Involuntary micro-motion system** — mandatory per-shot micro-motion spec: blink cadence, saccades (tiny eye movements), breathing/chest rise, head micro-drift, weight shifts; plus a QC check for "dead eyes / frozen face" | Eyes are now the dead giveaway (locked gaze, robotic blink, gaze not following head); subtle motion beats dramatic motion for realism | https://www.tomsguide.com/ai/this-is-a-dead-giveaway-that-youre-watching-an-ai-generated-video ; https://pict.ai/blog/how-to-animate-your-photo-with-ai/ ; https://adreelo.growduct.com/blog/realistic-people-ai-video |
| 4 | **Listener-reaction rule for dialogue** — "speaker talks, listener reacts": the non-speaking character must be visibly listening (micro-nods, brow, breath, gaze) and must NOT move their mouth | The commonest AI dialogue failure is both mouths moving / both characters speaking at once | https://www.facebook.com/reel/1069258062111840/ (creator demo contrasting both-speaking vs one-at-a-time — secondary/social source, treat as illustrative not authoritative) |
| 5 | **Room-tone / never-silence rule + 4-layer sound** — continuous ambience under every scene, room tone in every interior, foley only on visible beats matched to surface (stone vs wood vs grass), reverb matched to room size | Silent AI footage + studio-clean voice outdoors is an instant tell; sound "actively compensates for visual artifacts" | https://fruitloveisland.ai/blog/ai-sound-design-video-creators/ ; https://hackernoon.com/ai-video-comes-out-silent-here-is-the-sound-design-workflow-i-run-on-every-shot |
| 6 | **Non-verbal voice layer** — inline performance tags per line: `[sighs] [laughs] [whispers] [gasps] [clears throat]`, breaths, hesitations (`um/uh`), stutters, trailing off, ellipsis-pauses; never a clean take | Real speech is messy; overly smooth, pause-free TTS is the audio uncanny valley — prosody/breath/disfluency is the main 2026 quality separator | https://www.blurstudio.ai/knowledge/elevenlabs-audio-tags-and-v3 ; https://www.codesota.com/tasks/text-to-speech ; https://micdrop.dev/blog/elevenlabs-audio-tags-voice-agent |
| 7 | **Eye/gaze continuity system** — per-shot gaze target, saccade direction, pupil/light response, eye-line match across cuts (who looks at whom, where) | Gaze that doesn't follow head movement or match the other character across a cut breaks the scene even when the face is perfect | https://www.tomsguide.com/ai/this-is-a-dead-giveaway-that-youre-watching-an-ai-generated-video |
| 8 | **Hands & contact-physics avoidance + repair protocol** — frame hands out / give a simple object / slow motion for hand shots; short 3–5 s segments; frame-by-frame hand scrub; masked inpainting for warped hands; never generate pouring/grasping/tying as a hero action | Hands (extra/fused fingers, changing grips) and physics (liquid, cloth, collisions) are the most recognisable artifacts; models have no physics engine, only statistical priors | https://www.8frame.co/blog/why-ai-video-looks-fake ; https://hackernoon.com/how-to-fix-warped-hands-and-faces-in-ai-generated-video ; https://www.therankmasters.com/insights/ai-video/how-to-create-realistic-ai-videos-that-dont-look-fake |
| 9 | **Anti-plastic skin system** — name texture explicitly (visible pores, fine lines, freckles, uneven tone, under-eye texture, peach fuzz), side/skimming light, camera+film words, ban "flawless/perfect/airbrushed", lower guidance (FLUX 2.0–2.5 cited) | "Too perfect" skin is a primary tell; flat front light + high guidance + beauty words produce waxy skin | https://aipromptgeneer.com/articles/why-ai-images-look-plastic/ ; https://artificialguy.com/blog/flux-photorealism-guide/ |
| 10 | **Editing-rhythm system (J/L cuts, cut on action, beat sync)** — J-cut audio 4–12 frames early, L-cut audio trailing, cut mid-movement, cut on phrase not every beat, hard cut as default | Stitched clips with simultaneous audio+video cuts feel "stitched together"; J/L cuts are what make an edit feel continuous/human | https://domer.io/blog/fast-clip-editing-tiktok-shorts ; https://openaisuite.com/iart-ai/motion-design-skills/beat-sync-editing/ ; https://www.mcpinstall.com/skills/calesthio/generative-media-skills/editing-montage |
| 11 | **Film-finish pipeline (after grading)** — fixed order: correct → creative LUT at reduced strength (20–40% per one guide; 50–70% for print emulations per another — see disagreement note) → 35 mm grain 8–15% → light blur; highlight rolloff, halation/bloom/gate weave as separate adjustable ingredients | AI footage is "too clean": ultra-sharp, plasticky, baked contrast; a LUT alone on unstable footage makes drift more visible, so foundations come first | https://invideo.io/blog/luts-film-grain-ai-video/ ; https://www.veo3ai.io/blog/filmic-color-grading |
| 12 | **Voice-drift measurement (audio twin of face-embedding drift)** — speaker-embedding similarity per line and per episode, plus prosody fingerprint (pace/pitch range) per character **[INFERENCE]** | The system already measures face drift quantitatively but has no equivalent for voice; a cloned voice can drift in timbre/pace across episodes unnoticed | Inference from https://genmagic.co/blog/consistent-characters-ai-video (face-drift measurement) + https://www.codesota.com/tasks/text-to-speech (prosody as quality marker). No source directly proposes voice-embedding QC for this system. |

### P1 — add next (high value, moderate effort)

| # | Headline | Why | Source |
|---|---|---|---|
| 13 | **Temporal-artifact QC pass** — scrub every take for texture swimming, flicker, object drift, cadence stutter/missing motion blur, morphing; reject/regenerate, don't patch in grading | The problem "lives in time, not in resolution" — a 4K clip can look faker than 720p phone footage | https://www.therankmasters.com/insights/ai-video/how-to-create-realistic-ai-videos-that-dont-look-fake |
| 14 | **Camera-imperfection system** — handheld breathing/micro-drift, focus breathing, focus pulls, subtle lens flare, natural motion blur / 24 fps shutter feel, reframing drift | Perfectly locked, perfectly smooth camera reads as CGI; real cameras breathe and hunt focus | https://www.elvory.ai/ai/video-generator/hailuo-2-3 (handheld breathing example) ; https://www.8frame.co/blog/why-ai-video-looks-fake (too-smooth motion) |
| 15 | **Lighting-continuity lock** — shadow direction, colour temperature and light-source position fixed per scene (extends script-grading: not just time-of-day, but *where* the light comes from in every shot) **[INFERENCE]** | Existing grading follows time-of-day; nothing in the baseline locks shadow direction/light position across cuts, a classic viewer-noticed inconsistency | Inference from https://aivideobootcamp.com/blog/photorealistic-ai-prompts-guide-2026/ (lighting inconsistency as a viewer cue) |
| 16 | **Background-life rule** — secondary motion in every shot (curtain, leaves, distant people, steam, dust in light) at low amplitude; empty/overly smooth backgrounds are a tell | Backgrounds that are "overly smooth or empty" are listed among the commonest tells | https://www.tomsguide.com/ai/this-is-a-dead-giveaway-that-youre-watching-an-ai-generated-video |
| 17 | **Cloth/hair physics direction** — hair and fabric must follow wind/gravity/momentum, never float; keep hair/cloth motion small in dialogue shots | Hair/cloth moving unnaturally / floating is a named tell; Hailuo 2.3 is singled out for getting this right | https://www.elvory.ai/ai/video-generator/hailuo-2-3 ; https://www.tomsguide.com/ai/this-is-a-dead-giveaway-that-youre-watching-an-ai-generated-video |
| 18 | **Distance & space in voice** — voice level/reverb/muffling must change with camera distance and room (close = dry/intimate, far = quieter + more reverb); off-screen voices muffled **[INFERENCE]** | Baseline masters to −14 LUFS globally; nothing ties voice treatment to shot distance/space, yet "crisp studio voice in outdoor footage" is a named tell | Inference from https://www.tomsguide.com/ai/this-is-a-dead-giveaway-that-youre-watching-an-ai-generated-video (ambient/echo mismatch) |
| 19 | **Spotting sheet for sound** (pre-generation, per shot: timecode, sound class, sync-or-not, distance) + ambience-loop crossfade rule (0.5–1 s) | Ad-hoc SFX generation produces mismatched, unsynced sound; a spotting sheet is the professional workflow | https://hardeststories.com/ai-sound-effects-video/ ; http://hypernatural.ai/skill/hn/guide-add-sound-effects |
| 20 | **AI-disclosure & provenance pack** — per-video disclosure checklist: YouTube Studio "AI use" disclosure, EU AI Act Art. 50 deployer disclosure where applicable, C2PA Content Credentials / SynthID where the tool supports it, on-screen label wording | Distribution pack exists but no disclosure system; Art. 50 has applied since 2 Aug 2026 and YouTube auto-labels undisclosed photorealistic AI since May 2026. *Not legal advice — verify with counsel.* | https://www.axtrelis.com/knowledge/ai-disclosure-under-the-eu-ai-act ; https://hypefox.app/blog/ai-label-youtube-instagram-tiktok/ ; https://www.sheevook.com/blog/label-ai-generated-content |
| 21 | **Self-QC with detectors (adversarial check)** — run finished episodes through provenance-first checks (C2PA Verify, SynthID Detector) + classifier ensemble (Hive etc.) as a *triage* score, never a verdict | Detectors catch what human eyes miss (and vice versa: only 0.1% of people reliably sorted real vs fake in iProov 2025); use them to find your own tells before viewers do | https://www.androidpolice.com/5-tools-to-detect-ai-generated-text-photos-and-videos/ ; https://rankite.com/blog/best-ai-image-detection-tools ; https://www.duckduckgoose.ai/blog/why-deepfakes-look-so-real-now |
| 22 | **Accessibility beyond captions: audio-description track** — narration of visual action in dialogue pauses (WCAG 2.1 SC 1.2.5, AA), plus descriptive transcript | Captions serve deaf/hard-of-hearing viewers only; blind/low-vision viewers get nothing from the current system | https://eliteai.tools/blog/ai-audio-description-video-automation ; https://www.3playmedia.com/blog/standards-requirements-quality-audio-description/ |
| 23 | **Voice ageing / state variants** — per-character voice variants for age, illness, whisper/shout, tiredness, cold (parallel to existing visual ageing variants) **[INFERENCE]** | Visual ageing exists; voice is a character attribute that also changes with age/state, and version 3/4 tags work best when the base voice already contains the manner | Inference from https://givon.ai/en/help/voiceover-script-and-tags (tags work best close to the voice's recorded manner) |
| 24 | **Code-switching & dialect rule** — explicit handling for mid-sentence language switching (e.g. Bengali↔English) and regional accent: test per language, don't assume a multilingual model is equally good in all of them | Multilingual TTS quality "falls off a cliff" outside major languages and struggles with code-switching inside one passage | https://www.videosdk.live/developer-hub/tts/elevenlabs-text-to-speech-review ; https://www.ringlyn.com/blog/ai-voice-synthesis-voice-cloning-2026/ |

### P2 — strengthen / future-proof

| # | Headline | Why | Source |
|---|---|---|---|
| 25 | **Model-version pinning + golden regression set** — pin exact model versions per project; re-test a golden set of shots whenever a provider updates a model; keep a fallback model per lane | Providers silently update models and shut them down (Sora API shut 24 Sep 2026); unpinned pipelines drift without anyone changing a prompt | https://aiunpacking.com/blog/consistent-ai-characters-video-workflows/ (Sora shutdown) ; https://apimart.ai/blog/best-ai-video-generators-2026 |
| 26 | **Long-form consistency: re-anchor rule** — re-inject reference images + first-frame anchoring every ~8–16 s / every scene, because consistency degrades sharply past ~16 s and with time since last appearance | Face-embedding drift measurement exists but no *schedule* for when to re-anchor; the research gives a number (~16 s) to build the schedule around | https://genmagic.co/blog/consistent-characters-ai-video |
| 27 | **Reference-count strategy per model** — document per-model reference limits (Veo 3.1 ≤3, Seedance 2.5 up to 30 images per one guide / 50 refs per another — *disagreement, verify*), and a multi-angle reference set (front/three-quarter/profile + expression) per character | Reference-to-video is the main 2026 consistency tool, but limits differ 10× between models; a single front photo is the weakest reference set | https://www.clipspeed.ai/blog/consistent-ai-characters-video.html ; https://genmagic.co/blog/consistent-characters-ai-video |
| 28 | **Human blind-test gate** — before release, show episodes to viewers who don't know it's AI and record "what felt off" (not a MOS score — MOS saturates at 4.3–4.6 and misses long-form failures) | Vendor MOS/benchmarks are unreliable; unaided human "off" notes are the only signal that tracks the uncanny valley | https://www.codesota.com/tasks/text-to-speech (MOS misleading in 2026) |
| 29 | **Teeth/tongue/mouth-interior QC in lip-sync** — check mouth interior sharpness, teeth stability and tongue on close-ups; prefer LatentSync-class diffusion lip-sync for hero shots, MuseTalk for speed | Blurry teeth/lips were the stated reason for LatentSync 1.6's 512×512 retrain; mouth interior is where cheap lip-sync fails | https://jutsustudio.com/blog/open-source-lip-sync/ |
| 30 | **Wardrobe wear & continuity detail** — wrinkles, stains, wear, fit and layering must persist; fabric creases change with pose, not randomly per shot **[INFERENCE]** | Wardrobe registry exists (what is worn) but not *how it wears* — creases/wear resetting per shot is a subtle continuity tell | Inference from https://www.therankmasters.com/insights/ai-video/how-to-create-realistic-ai-videos-that-dont-look-fake (object drift / texture swimming) |
| 31 | **Imperfection budget** — deliberate, *counted* imperfections per shot (asymmetry, flyaway hairs, dust, a crooked prop) instead of "add imperfections" as a vague prompt line **[INFERENCE]** | "Imperfections increase realism most" is the consensus, but an uncounted instruction is unverifiable in QC; a budget makes it checkable | Inference from https://aivideobootcamp.com/blog/photorealistic-ai-prompts-guide-2026/ |
| 32 | **Music-ducking & dialogue-first mix rule** — music/SFX duck under dialogue, never compete; dialogue ~60% of attention | Existing audio mastering sets loudness (−14 LUFS) but not the *balance* rule that keeps dialogue intelligible and human | https://fruitloveisland.ai/blog/ai-sound-design-video-creators/ (60/25/15 rule) |

---

## 2. Humanization techniques (2025–2026 state of the art)

### Voice
- **Prosody is the gap, not pronunciation.** Modern TTS infers prosody from context (questions rise, lists fall then rise) and exposes emotion/pace/emphasis controls; "poor prosody is the single most common reason a synthetic voice still sounds 'off'." — https://www.ringlyn.com/blog/ai-voice-synthesis-voice-cloning-2026/
- **Audio tags (ElevenLabs versions 3/4):** `[whispers] [sighs] [laughs] [excited] [sarcastic] [curious] [crying] [gasps] [clears throat]` placed just before the affected words, 1–2 per line; versions 3/4 ignore SSML `<break>` — use ellipsis/dashes for pauses. Tags describing the voice work more reliably than sound-effect tags. — https://www.blurstudio.ai/knowledge/elevenlabs-audio-tags-and-v3 ; https://micdrop.dev/blog/elevenlabs-audio-tags-voice-agent
- **Disfluencies & breath:** premium TTS is now judged on breathing/micro-pause insertion, hesitation markers, and self-corrections; "most TTS scrubs them — the frontier ones model them." — https://www.codesota.com/tasks/text-to-speech
- **Multi-speaker in one pass:** ElevenLabs Text to Dialogue (up to 10 voices, ≤~2,000 chars/request per vendor advice), Gemini TTS (2 speakers/request). — https://www.kukarella.com/resources/text-to-speech/how-to-create-realistic-multi-speaker-dialogues-with-ai
- **Open TTS alternatives to OmniVoice:** Voxtral TTS (Mistral, 26 Mar 2026, 4B, 9 langs, ~3 s cloning, emotion steering, captures disfluencies) — https://www.digitalapplied.com/blog/mistral-voxtral-tts-open-source-text-to-speech-guide ; VoxCPM2 (OpenBMB, 2B, 30 langs, 48 kHz, inline style cues, retains breaths/micro-pauses) — https://voxcpm.app/ ; Chatterbox Multilingual V3 (Resemble AI, MIT, 0.5B, 23 langs, emotion-exaggeration 0–1, PerTh watermark) — https://pypi.org/project/chatterbox-tts/0.1.5/
- **Bengali specifically:** ElevenLabs version 4 lists Bengali among 90+ languages, version 3 among 70+; note that quality varies by language and code-switching inside one passage is a known weakness — test Bengali lines separately, don't assume parity with English. — https://docs.avalai.ir/en/providers/elevenlabs ; https://www.videosdk.live/developer-hub/tts/elevenlabs-text-to-speech-review

### Image
- **Skin:** visible pores, fine lines, freckles, uneven tone, under-eye texture, peach fuzz, slight asymmetry; side/sk transitions; "no plastic sheen"; never "flawless/perfect". Lower guidance (FLUX 2.0–2.5 cited) removes waxiness. — https://aipromptgeneer.com/articles/why-ai-images-look-plastic/ ; https://artificialguy.com/blog/flux-photorealism-guide/
- **Imperfection as method:** "The single most important concept here is imperfections… the technique that produces the most visible improvement." — https://aivideobootcamp.com/blog/photorealistic-ai-prompts-guide-2026/
- **Light:** one motivated source, side light to skim texture; flat front light hides texture and reads as AI. — https://aipromptgeneer.com/articles/why-ai-images-look-plastic/
- **Camera language in the prompt:** named camera/lens/film stock instead of "8K, masterpiece, flawless". — https://aipromptgeneer.com/articles/why-ai-images-look-plastic/

### Video / motion
- **Micro-motion recipe (most-cited):** "gentle blink every 2 seconds, slight head tilt, soft breathing, keep identity and lighting consistent, keep mouth closed, no background movement" for stills; 2–4 s loops hold identity best; large smiles/laughter/turns cause drift. — https://pict.ai/blog/how-to-animate-your-photo-with-ai/
- **Full performance recipe:** "slowly blinks once, slightly narrows eyes, gently raises eyebrows, relaxes them, very subtle half-smile, returns to calm; tiny eye movements as if focusing; micro-expressions, subtle breathing, slight eye-moisture movement, minute eyelid motion, barely perceptible head movement; no beauty filter, no skin smoothing, no plastic/waxy appearance." — https://adreelo.growduct.com/blog/realistic-people-ai-video
- **Performance transfer** beats prompting for full-body acting (Act‑Two / Kling Motion Control / Wan‑Animate — see §3).
- **Physics:** keep physical interactions (pouring, grasping, collisions) out of generated hero shots or film them; generate the room/mood and film the interaction. Short 3–5 s segments limit drift. — https://www.8frame.co/blog/why-ai-video-looks-fake
- **Motion blur / cadence:** check the downloaded file at its native 24 fps before blaming the model; too-smooth motion + missing motion blur = "cadence stutter" tell. — https://www.8frame.co/blog/why-ai-video-looks-fake ; https://www.therankmasters.com/insights/ai-video/how-to-create-realistic-ai-videos-that-dont-look-fake

### Colour grading
- **Order matters:** correct/grade foundations (exposure, skin hue, shot-to-shot continuity) *before* any LUT/print emulation; a strong look on unstable footage makes problems easier to see. — https://www.veo3ai.io/blog/filmic-color-grading
- **LUT at reduced strength:** creative LUT 20–40% mix (one guide) or 50–70% for Kodak 2383 / Fuji 3510 print emulations (another guide) — *sources disagree on the number; treat as a range to test, not a fixed value*. Free 2383/3510 ship in DaVinci Resolve. — https://invideo.io/blog/luts-film-grain-ai-video/ ; https://www.veo3ai.io/blog/filmic-color-grading
- **Film as ingredients, not a filter:** highlight shoulder (gradual rolloff, no hard ceiling), cooler shadows/warmer highlights only where the scene supports it, grain, halation, bloom, gate weave. — https://www.veo3ai.io/blog/filmic-color-grading ; https://luttie.app/faq (browser-based film engine, .cube/.3dl export; Luttie pricing not verified — see §5)
- **Grain economics:** grain costs bitrate (+50–120% at same CRF per cited measurements); a mezzanine *above* delivery resolution preserves grain best through compression. — https://github.com/konradre/video-production-skills/blob/HEAD/skills/video-finish/references/EVIDENCE.md
- **ACES pipeline:** input transform → grade in a wide-gamut space → display output transform; technical vs creative LUTs are not interchangeable. — https://www.veo3ai.io/blog/filmic-color-grading

### Sound
- **Four layers, in order:** ambience/room tone first → foley/hard effects on visible beats → dialogue → music. "Sound design… actively compensates for visual artifacts." — https://fruitloveisland.ai/blog/ai-sound-design-video-creators/ ; https://hackernoon.com/ai-video-comes-out-silent-here-is-the-sound-design-workflow-i-run-on-every-shot
- **Never silence:** "Even a quiet room has a low hum. Add room tone to every indoor scene." Ambience ~20–30% volume; 60/25/15 dialogue/music+SFX/ambience attention rule. — https://fruitloveisland.ai/blog/ai-sound-design-video-creators/
- **Foley subtlety:** "if you notice it consciously, it is too loud"; match surface (marble vs grass, stone vs wood). — https://fruitloveisland.ai/blog/ai-sound-design-video-creators/
- **Looping:** crossfade loop points 0.5–1 s; change ambience only at cuts. — http://hypernatural.ai/skill/hn/guide-add-sound-effects
- **Generators:** ElevenLabs Sound Effects (text-to-SFX, up to 30 s, seamless looping), Stable Audio 3.0 (1 s–6 min, best for long ambience), Adobe Firefly Generate Sound Effects (free daily generations, commercial use per Sep 2026 guide). Real recordings beat synthesis for anything that must sync to picture. — https://undetectr.com/blog/ai-sound-effect-generator ; https://hardeststories.com/ai-sound-effects-video/

### Editing
- **J/L cuts, cut on action, cut on phrase:** see gap #10. "Faster pacing is not automatically better. Pace is the controlled contrast between density, rests, anticipations, and payoffs." — https://www.mcpinstall.com/skills/calesthio/generative-media-skills/editing-montage
- **Every shot must earn its time** (orient, reveal, prove, compare, intensify, relieve, bridge, humanize, close). — https://www.mcpinstall.com/skills/calesthio/generative-media-skills/editing-montage

---

## 3. Tools / models / methods 2026

### Character consistency (image/video)
| Tool / method | What it does | Needs GPU / API? | Notes / licence caution |
|---|---|---|---|
| Veo 3.1 "Ingredients to Video" (Google) | Up to 3 reference images; 4/6/8 s clips; 720p default, 1080p/4K at 8 s; native audio | API (Gemini API / Flow) | Best for short realistic dialogue shots per guides |
| Seedance 2.5 (ByteDance) | Longest single clip 30 s; many references (30 images per one guide, "up to 50 reference inputs" per another — **disagreement**); native audio | API | Best for long/reference-heavy clips |
| Kling 3.0 / 3.0 Omni (Kuaishou) | Elements/Element Library (main + up to 3 supplementary angles); multi-shot up to 6 shots in one generation; 4K mode; native audio; Voice Binding | API | Best for cinematic multi-shot |
| MiniMax Hailuo 2.3 | Micro-expressions, physical motion; 6–10 s; **no native audio** | API | Budget motion/action; add sound separately |
| MiniMax H3 | 2K default output; omni-reference; native stereo audio; up to 15 s | API | Higher-res option |
| FLUX.2 (Black Forest Labs) | Image model; up to 8 refs via API / 10 in playground | API or GPU | For stills/character sheets |
| Runway Gen-4.5 + Act‑Two | Gen-4.5 video; Act‑Two performance transfer (see §2) | API/subscription (Standard $12/mo billed annually cited — verify) | Standalone Lip Sync retired 27 May 2026 in favour of Act‑Two |
| Wan 2.2 (Alibaba, Apache-2.0) | Open T2V/I2V; 5B variant cited as fitting a single consumer GPU | GPU (local) | Only SOTA-tier open video model fully permissive per secondary guide |
| LTX-2 (Lightricks) | Open, joint audio+video, up to 4K, ~20 s | GPU | Licence is revenue-gated — check before commercial use |
| Wan-Animate-2 (Alibaba, Aug 2026) | Driving-video → character animation, text-controlled camera | GPU (heavy) | Research-grade |
| Higgsfield Soul ID | Trained identity from 20–80 photos, ~3–5 min training cited | API | Vendor claim; verify |

### Natural multilingual TTS with emotion
| Tool | What it does | Needs GPU / API? |
|---|---|---|
| ElevenLabs version 4 / version 4 Turbo (90+ langs incl Bengali) | Flagship expressive TTS, audio tags, native accent handling; Turbo ~150 ms first speech cited | API (paid) |
| ElevenLabs v3 (70+ langs incl Bengali) + Text to Dialogue | Multi-speaker dialogue in one pass, up to 10 voices | API (paid) |
| Mistral Voxtral TTS (4B, 9 langs) | Open-weights, ~3–5 s cloning, emotion steering, disfluencies; runs on consumer hardware per guide | GPU (local) or API |
| VoxCPM2 (OpenBMB, 2B, 30 langs, Apache-2.0) | Tokenizer-free, 48 kHz, inline style cues, breaths/micro-pauses retained | GPU (local) |
| Chatterbox Multilingual V3 (Resemble AI, MIT, 0.5B, 23 langs) | Zero-shot cloning, emotion-exaggeration slider, PerTh watermark | GPU (local) |
| Gemini TTS (Google) | 2 speakers/request dialogue; broad language coverage | API |

### Realistic lip-sync
| Tool | What it does | Needs GPU / API? |
|---|---|---|
| sync-3 (sync.labs) | Mouth replacement, up to 4K, 95+ langs, profiles/hands-in-front-of-mouth; ~$0.11–0.13/s cited Oct 2026 | API (paid) |
| LatentSync 1.6 (ByteDance, Apache-2.0) | Sharpest open mouth, diffusion, 512×512; **18 GB VRAM min** | GPU (local) |
| MuseTalk 1.5 (Tencent, MIT code) | Real-time (30+ fps V100), 256×256 face region; README says weights usable commercially | GPU (local, light) |
| InfiniteTalk (MeiGen, Apache-2.0, Wan2.1-based) | Dubbing *with* head/body motion, long clips (default max 40 s), 480/720p; also image+audio | GPU (local, heavy) |
| Wan2.2-S2V-14B (Alibaba, Apache-2.0) | Photo + audio → talking video 480/720p, optional pose video | GPU (80 GB VRAM for single-GPU command cited — heavy) |
| HunyuanVideo-Avatar (Tencent) | Multi-character audio-driven, emotion control | GPU (24 GB min, 96 GB recommended) — **licence void in EU/UK/South Korea; avoid or lawyer-check** |
| Sonic (Alibaba) | Expressive/emotional dubbing | GPU — **CC-NC licence; not for commercial use** |
| Wav2Lip (2020) | Foundation, tight sync, blurry mouth | GPU (light) — **README prohibits commercial use** |

### Film-like grading
| Tool | What it does | Needs GPU / API? |
|---|---|---|
| DaVinci Resolve (free) + Kodak 2383 / Fuji 3510 LUTs | Print-emulation LUTs shipped free; full grading, .cube export | Desktop GPU (local) |
| FilmConvert Nitrate ($99–$199 cited) | Named film-stock emulation + resolution-matched grain | Desktop (paid plugin) |
| Dehancer ($149/yr cited) | Halation, bloom, gate weave, grain — the physics a LUT can't encode | Desktop (paid plugin) |
| Luttie (browser) | Film engine (5 negatives / 2 prints), curves/wheels/HSL, AI Grade, .cube/.3dl export; WebGL/WebGPU on-device | Browser (free grade; Pro for LUT export — price not verified) |
| Topaz Video AI ("Topaz Video") | Upscale to 4K/8K, denoise, deblur, frame interpolation (Apollo/Chronos/Aion), stabilisation; 19 models; local, plugins for Resolve/After Effects | Desktop GPU (local) — **subscription since Oct 2025; Personal $299/yr cited by one source, ~$39/mo by another — disagreement, verify** |

### Detecting / fixing AI-looking artifacts
| Tool / method | What it does | Needs GPU / API? |
|---|---|---|
| C2PA Content Credentials Verify (free) | Reads signed provenance manifest — who made it, with what, was AI involved | Web (free) |
| Google SynthID Detector (free) | Detects SynthID watermark in image/video/audio from Google + partners (incl OpenAI, NVIDIA, Kakao, Apple per Oct 2026) | Web (free, upload) |
| Hive AI Detector / Moderation | Classifier: AI-likelihood + likely generator model; video ≤30 s on free extension | Browser ext. / API |
| AI or Not, Sightengine, Illuminarty | Classifier ensemble members; heatmaps / confidence scores | Web / API |
| Frame-by-frame hand/face scrub + masked inpainting; Netflix VOID (Apr 2026, CogVideoX-based, open source) | Inpaint warped hands/faces with physics-aware fill (removed hand → cup falls) | GPU (VOID) / in-tool |
| Columbia DIVID detector (2026, cited) | Diffusion-video detector, up to 93.7% on benchmark — research, not a product | Research |

**Licence warnings (sourced, not legal advice):** OmniVoice is CC-BY-NC (per mission); check that any new TTS/video component's licence is compatible with the repo's AGPL-3.0 + commercial-use claims before adding it. HunyuanVideo-Avatar, Sonic and Wav2Lip have the restrictions above; LTX-2 is revenue-gated.

---

## 4. What gives away AI content — and how professionals avoid it

| Tell | What viewers see | How pros avoid it |
|---|---|---|
| **Eyes** (biggest tell, 2025) | Locked gaze, no micro-tracking/saccades, robotic/slow blink, gaze not following head, pupils not reacting to light, flat painted-on look | Prompt + QC eye motion explicitly; performance-transfer a real take; check eye-line across cuts |
| **Voice too perfect** | Overly smooth, no pauses/stutters/breaths, flat rhythm, emotions that don't land, studio-clean voice outdoors, no echo indoors | Audio tags, disfluencies, breaths; room tone + matched reverb; single-pass dialogue |
| **Identity drift** | Face subtly morphs/ages/melts during movement | Reference-to-video, fixed descriptor, first-frame anchor, re-anchor every ~16 s, face-embedding QC |
| **Texture swimming / flicker** | Skin/hair/fabric/grass "boils" or slides frame to frame; background brightness pulses | Short segments, stability-first prompts, temporal QC, grain to mask micro-flicker |
| **Physics violations** | Water/cloth/collisions move with wrong weight; hair floats; objects touch without pushing | Don't generate hero physics; film it; keep cloth/hair motion small |
| **Hands** | Extra/fused fingers, wrong bends, changing grips | Frame out / simple object / slow-mo / inpaint; scrub frame-by-frame |
| **Object drift** | Items grow/shrink/vanish/float | Persistent reference images, start/end frames, object registry (already exists — enforce per-shot) |
| **Text degradation** | On-screen text warps/scrambles after 1–2 s | Avoid AI-rendered text in motion; add text in post |
| **Cadence stutter** | Judder at stated frame rate, missing motion blur | Native 24 fps check, motion-blur-aware prompts, frame interpolation in post |
| **Too-perfect visuals** | Perfect symmetry, waxy/plastic skin, overly smooth/empty backgrounds, flat lighting | Imperfection budget, side light, asymmetry, background life, grain |
| **Silence / wrong ambience** | Street with no wind/traffic; indoor with zero echo | Room tone always; ambience matched to location, changed only at cuts |
| **Simultaneous dialogue** | Both mouths moving; overlapping lines with no turn-taking | Speaker-talks-listener-reacts rule; Text-to-Dialogue single pass |

**Audience numbers (sourced, context matters):** Animoto survey Jan 2026 (cited in a guide): 83% of consumers said they can spot AI video and 36% said it lowers trust in a brand — https://genmagic.co/blog/consistent-characters-ai-video ; iProov 2025 study of 2,000 US/UK consumers: only 0.1% could reliably sort *every* real and fake image/video — https://www.duckduckgoose.ai/blog/why-deepfakes-look-so-real-now ; FakeParts 2025: trained viewers flagged AI/partially manipulated video only 75.3% of the time, hardest were temporally coherent text-to-video — https://www.therankmasters.com/insights/ai-video/how-to-create-realistic-ai-videos-that-dont-look-fake . These three numbers measure different things (self-report vs forced sorting vs trained detection) — do not combine them into one claim.

**The professional mindset (sourced):** "Realistic AI video is no longer a model problem" — the gap is workflow: model choice → prompt/cinematography → motion/frame settings → artifact remediation → consistency locking → post-production finishing, in that order. — https://www.therankmasters.com/insights/ai-video/how-to-create-realistic-ai-videos-that-dont-look-fake

---

## 5. Gaps in the existing systems list (not covered at all)

These are areas with **no corresponding system** in the baseline list as described:
1. **Editing / montage system** — no J/L cuts, rhythm, beat-sync, cut-on-action, or shot-function rules. The system stitches clips; it does not yet *edit* them.
2. **Performance-capture lane** — no driving-video / mocap-from-phone workflow at all.
3. **Sound-spotting & foley system** — sound design exists, but no spotting sheet, no room-tone rule, no reverb/distance matching, no foley-sync rule.
4. **Disclosure / AI-labelling system** — distribution exists, but no EU AI Act / YouTube / platform disclosure checklist or provenance embedding.
5. **Accessibility system** — captions (opt-in) exist, but no audio description, no descriptive transcript, no WCAG mapping.
6. **Model-lifecycle / maintenance system** — no version pinning, no golden regression set, no fallback-model map, no deprecation watch (Sora shutdown is the cautionary tale). The repo's own naming rule is about *public naming*, not about *internal* pinning — the two should not be confused. **[INFERENCE — the naming rule is from the mission; the pinning need follows from the Sora shutdown source.]**
7. **Human-evaluation / blind-test system** — QC checklist exists, but no blind audience test, no "what felt off" capture, no MOS-free evaluation rule.
8. **Voice-consistency measurement** — face drift is measured; voice drift is not (see gap #12).
9. **Per-language quality gate** — languages are supported, but no per-language/per-dialect test (especially Bengali and code-switching) before a language is declared ready.
10. **Failure / fallback playbook** — no documented "if the model fails this shot, do X" (regenerate vs inpaint vs film vs cut around) per artifact type. **[INFERENCE — no source directly proposes this playbook; it follows from the artifact-fix sources.]**
11. **Child-safety is present, but adult-real-person safeguards are thinner** — the system has child-safety rules and consent records, but no explicit deepfake-of-a-real-adult policy, no "real person says/does something they never did" disclosure trigger, and no likeness-revocation workflow. **[INFERENCE — based on the YouTube/EU disclosure sources, which centre on real-person deepfakes.]**
12. **No cost-of-realism accounting** — cost/credit tracking exists, but not a *realism budget*: which humanising steps (performance take, extra takes, grain pass, foley) are worth their credits/minutes per shot type. **[INFERENCE]**

---

## Could not verify / open questions
- **Live verification:** no page was opened in the research browser and no tool was run; all findings are index-sourced. Prices, VRAM figures and reference limits should be re-checked on vendor pages/READMEs before they are written into the repo.
- **Disagreements between sources (do not pick one silently):** (a) LUT strength 20–40% vs 50–70%; (b) Seedance 2.5 references "up to 30 images" vs "up to 50 reference inputs"; (c) Topaz pricing $299/yr vs ~$39/mo; (d) Runway Act‑Two launch 15 vs 17 Jul 2025 in different guides.
- **OmniVoice vs newer TTS:** I did not verify OmniVoice's current tag set, language list or emotion range against Voxtral/VoxCPM2/Chatterbox/ElevenLabs version 4 — a direct comparison is still needed before swapping or adding a voice lane.
- **OpenMontage's actual capabilities/limits** were not researched in this run (not in the mission's questions beyond the baseline); its clip-length, audio and reference limits are an open question for the stitching lane.
- **Bengali TTS quality:** sources confirm Bengali is *listed* by ElevenLabs versions 3/4; none gave a Bengali-specific quality evaluation. A listening test in Bengali (and Bengali↔English code-switching) is still missing.
- **Legal:** EU AI Act / YouTube disclosure summaries above are secondary guides, not legal advice; applicability to a given channel (EU Establishment, professional vs personal use, artistic-work exception) needs counsel.

## Sourced vs inferred
- **Directly sourced:** everything in §§2–4 with a URL, and gaps #1–11, #13–22, #24–29 in §1.
- **Inferences (flagged [INFERENCE] inline):** gaps #12, #15, #18, #23, #30, #31, §5 items #6, #10, #11, #12. These follow from sourced facts but no source directly proposes them for this system.

## Sources
Full URL list (verbatim from search results; read 12 Nov 2026 via index):
- https://www.elvory.ai/ai/video-generator/hailuo-2-3
- https://pict.ai/blog/how-to-animate-your-photo-with-ai/
- https://adreelo.growduct.com/blog/realistic-people-ai-video
- https://www.colossyan.com/posts/best-ai-face-video-generators-to-create-digital-humans-instantly/
- https://www.digitalapplied.com/blog/mistral-voxtral-tts-open-source-text-to-speech-guide
- https://www.ringlyn.com/blog/ai-voice-synthesis-voice-cloning-2026/
- https://voxcpm.app/
- https://www.videosdk.live/developer-hub/tts/elevenlabs-text-to-speech-review
- https://www.codesota.com/tasks/text-to-speech
- https://www.clipspeed.ai/blog/consistent-ai-characters-video.html
- https://genmagic.co/blog/consistent-characters-ai-video
- https://aiunpacking.com/blog/consistent-ai-characters-video-workflows/
- https://www.duckduckgoose.ai/blog/why-deepfakes-look-so-real-now
- https://www.therankmasters.com/insights/ai-video/how-to-create-realistic-ai-videos-that-dont-look-fake
- https://www.tomsguide.com/ai/this-is-a-dead-giveaway-that-youre-watching-an-ai-generated-video
- https://www.cinemadrop.com/blog/ai-lip-sync
- https://jutsustudio.com/blog/open-source-lip-sync/
- https://www.pixazo.ai/blog/best-open-source-ai-lip-sync-models
- https://invideo.io/blog/luts-film-grain-ai-video/
- https://www.veo3ai.io/blog/filmic-color-grading
- https://luttie.app/faq
- https://fruitloveisland.ai/blog/ai-sound-design-video-creators/
- http://hypernatural.ai/skill/hn/guide-add-sound-effects
- https://hardeststories.com/ai-sound-effects-video/
- https://undetectr.com/blog/ai-sound-effect-generator
- https://hackernoon.com/ai-video-comes-out-silent-here-is-the-sound-design-workflow-i-run-on-every-shot
- https://domer.io/blog/fast-clip-editing-tiktok-shorts
- https://openaisuite.com/iart-ai/motion-design-skills/beat-sync-editing/
- https://www.mcpinstall.com/skills/calesthio/generative-media-skills/editing-montage
- https://artificialguy.com/blog/flux-photorealism-guide/
- https://aipromptgeneer.com/articles/why-ai-images-look-plastic/
- https://aivideobootcamp.com/blog/photorealistic-ai-prompts-guide-2026/
- https://www.androidpolice.com/5-tools-to-detect-ai-generated-text-photos-and-videos/
- https://rankite.com/blog/best-ai-image-detection-tools
- https://stacksheriff.com/ai-tools/runway-act-two-tutorial/
- https://hackernoon.com/ai-motion-capture-turns-your-phone-into-a-mocap-studio-heres-the-workflow-i-run
- https://kompozy.io/guides/ai-motion-transfer
- https://www.blurstudio.ai/knowledge/elevenlabs-audio-tags-and-v3
- https://micdrop.dev/blog/elevenlabs-audio-tags-voice-agent
- https://givon.ai/en/help/voiceover-script-and-tags
- https://www.8frame.co/blog/why-ai-video-looks-fake
- https://hackernoon.com/how-to-fix-warped-hands-and-faces-in-ai-generated-video
- https://www.axtrelis.com/knowledge/ai-disclosure-under-the-eu-ai-act
- https://www.sheevook.com/blog/label-ai-generated-content
- https://hypefox.app/blog/ai-label-youtube-instagram-tiktok/
- https://jutsustudio.com/blog/open-source-lip-sync/ (duplicate — lip-sync comparison)
- https://hyperautomationlabs.co/the-zero-ai-stack.pdf
- https://www.fuzzpuppy.com/open-source-video-models
- https://aiwiki.ai/wiki/elevenlabs_v3
- https://www.kukarella.com/resources/text-to-speech/how-to-create-realistic-multi-speaker-dialogues-with-ai
- https://eliteai.tools/blog/ai-audio-description-video-automation
- https://www.3playmedia.com/blog/standards-requirements-quality-audio-description/
- https://apimart.ai/blog/best-ai-video-generators-2026
- https://syntx.ai/blog/ai-video-generation-models
- https://pypi.org/project/chatterbox-tts/0.1.5/
- https://savrn.com/models/chatterbox
- https://docs.avalai.ir/en/providers/elevenlabs
- https://www.toolworthy.ai/tool/topaz-video-ai
- https://pexo.ai/blog/topaz-video-enhance-ai-3501
- https://github.com/konradre/video-production-skills/blob/HEAD/skills/video-finish/references/EVIDENCE.md
- https://www.tavus.io/blog/intro-to-conversational-video-ai
- https://www.facebook.com/reel/1069258062111840/ (secondary/social — illustrative only)

Working notes: notes/source-voice-dialogue.md, notes/source-video-consistency.md, notes/source-tells-grading-sound.md
