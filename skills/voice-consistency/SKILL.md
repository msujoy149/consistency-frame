---
name: voice-consistency
description: Keeps every character's voice identical across all episodes, like their visual identity. Covers fixed per-character voice profiles, generating once and reusing reference audio, the bundled VoiceStudio/OmniVoice local engine and its licence limits, script-driven emotional performance, single-pass multi-speaker dialogue, the non-verbal voice layer, voice-drift measurement, ageing and state variants, code-switching and dialect handling, distance and space in voice, and dialogue-first mixing.
---

# Voice Consistency

A character's voice is part of their identity, exactly like their face. If the voice changes between episodes, the audience notices — even when the face is perfect. This skill keeps each character's voice fixed, emotional, and human across every episode.

## 1. Voice Profiles — Fix Once, Reuse Every Episode

For every registered character, fix a voice profile once and reuse the same profile in every episode:

- Male or female voice, tone, apparent age, and language.
- The text-to-speech voice ID used for that character.
- Fixed performance tags and a fixed seed for the voice generation.
- A clean reference audio recording of the character's voice, stored in the character's own folder.

A character's voice must stay consistent across all episodes like their visual identity. Never assign one character's dialogue to another character, and never swap a voice between characters without the user explicitly asking for it. Record the voice profile (voice ID, tags, seed, reference audio) in the shot's provenance log alongside the visual prompt and seed, so any voice change can be traced.

If the platform supports voice references, use them to maintain consistency. If voice persistence is not supported on a platform, explain the limitation honestly rather than promising identical voices across every project.

## 2. Voice System — Generate Once, Reuse as Reference

Generate a character's voice once, save the output, and reuse it as reference audio to lock a consistent voice for later generations. Do not regenerate a character's voice from scratch for every line: start from the saved reference audio and the fixed profile, and only regenerate when the profile itself changes or a take fails quality control.

## 3. VoiceStudio / OmniVoice — The Bundled Local Voice Engine

The repo ships with a bundled local voice engine, VoiceStudio, built on OmniVoice:

- OmniVoice is a zero-shot voice-cloning text-to-speech model supporting 600+ languages.
- The model weights are downloaded by the user at install time — `setup.sh` walks you through installing them from Hugging Face (k2-fsa/OmniVoice). The weights are NOT bundled in the repository.
- The OmniVoice model is licensed CC-BY-NC (noncommercial). Commercial use of that model needs a different voice provider. Do not use the bundled OmniVoice weights for commercial voice work; if a project is commercial, switch the voice lane to a provider whose licence covers commercial use, and record that choice in the project notes.
- Check any new text-to-speech or voice component's licence for compatibility before adding it.

## 4. Realistic, Script-Driven Emotion — Perform Like a Human Actor

The voice performs like a human actor. Emotion comes from the script and matches each line:

- If the script calls for comedy, laughing, and joking, the character laughs and jokes — the voice laughs with the line, and the face and body laugh too.
- If the script calls for sadness, the character is sad — the voice, the face, and the posture carry the sadness.
- The character must "feel" the dialogue: understand what the line is asking for and express it the way a human actor would — facial expression, hand and foot movement, gestures, posture, and timing, everything the moment calls for. The performance must feel like a human is working, with a human brain behind it.
- Never use a generic "AI smile", a flat fixed expression, or the same emotion for every line. An emotion that does not fit the dialogue breaks both realism and consistency. If dialogue sounds robotic, viewers will realise it is AI and lose interest.
- Voice emotion must match the dialogue line by line: a laughing line is spoken with laughter in the voice, a sad line is spoken with sadness; never a flat, generic, or robotic delivery.

If the user's script is weak — flat dialogue with no feeling — improve it automatically: add emotion, natural pauses, reactions, and lively expression so the video has feeling, while keeping the story, the meaning, and the user's dialogue intact. Never change the story to add emotion; add the feeling to the story the user gave. A video with no feeling is a failed video.

## 5. Single-Pass Multi-Speaker Dialogue

Generate a whole conversation in one call instead of generating one line at a time and stitching the lines together. Where the tool supports it, a single call can carry up to 10 voices.

Real conversation has ~200 ms gaps between turns, rare overlaps, and handoffs timed by the speakers. Stitched lines with clean, identical gaps sound edited, not spoken. A single-pass generation preserves the natural rhythm, interruptions, and turn-taking of a real conversation.

When one character speaks, the other character must be visibly listening — micro-nods, brow movement, breath, gaze — and must NOT move their mouth. Two mouths moving at once is the commonest AI dialogue failure.

## 6. Non-Verbal Voice Layer

Every dialogue line may carry performance tags — sighs, laughs, whispers, gasps, clearing the throat — plus breaths, hesitations (um/uh), stutters, trailing off, and ellipsis pauses. Never deliver a clean, pause-free take. Real speech is messy; overly smooth text-to-speech is the audio uncanny valley.

Keep lines short enough to speak naturally, with pauses where a human would pause. Dialogue must be natural spoken language, not bookish language. A child speaks like a child; an adult speaks like an adult; an elderly character speaks like an elderly person. Never give a child adult words. If a line sounds robotic when read aloud, rewrite it.

## 7. Voice-Drift Measurement

Voice drift is the audio twin of face-drift measurement. A cloned voice can drift in timbre and pace across episodes unnoticed, so measure it — do not judge it by ear alone.

- Measure speaker-embedding similarity per line and per episode against the character's reference audio.
- Keep a prosody fingerprint per character: pace and pitch range.
- If similarity falls below the project's threshold, regenerate the line or episode.
- Record the scores in the provenance log.

Note: this measurement approach is an inference drawn from face-embedding drift measurement — no source directly proposes voice-embedding quality control for this system — so treat thresholds as project settings to calibrate, not as settled industry values, and always confirm with a human listening check.

## 8. Voice Ageing and State Variants

Keep per-character voice variants for age, illness, whisper/shout, tiredness, and cold — the voice parallel of visual ageing variants. When the story jumps in time, the voice changes only in the ways time or state would change it, deliberately and consistently, and the change is recorded in the continuity tracker. A time jump never silently creates a different voice.

Decide the order for each project before starting: voice first, then video matched to the voice; or video first, then voice matched to the video. Follow one order consistently inside a project. Dialogue timing must match the mouth: a line must not finish long before or after the character stops speaking. If lip-sync is not supported on the platform, say so honestly instead of promising it.

## 9. Code-Switching & Dialect Rule

Handle mid-sentence language switching (for example Bengali↔English) and regional accent explicitly. A character may switch languages mid-sentence, and the voice must follow the switch naturally, not flatten it into one language.

Test per language and per dialect with a separate listening test. Do not assume a multilingual model is equally good in all of them — especially Bengali and code-switched lines need a separate listening test. In one video each character may speak a different language (for example one Bengali, one English, one Hindi); write each character's dialogue in that character's language, generate each character's voice in that language, and match the lip-sync to that language. Never force all characters into one language unless the user asks for it.

## 10. Distance & Space in Voice

Voice level, reverb, and muffling change with camera distance and room:

- Close shots are dry and intimate.
- Far shots are quieter, with more reverb.
- Off-screen voices are muffled.
- Reverb matches the room; a studio-clean voice outdoors is an instant tell.

A crisp studio voice in outdoor footage is a named giveaway. Apply distance and space treatment as part of the sound design for every shot, not as an afterthought.

## 11. Music-Ducking / Dialogue-First Mix

Music and sound effects duck under dialogue and never compete with it. Dialogue carries ~60% of attention, so the mix is built around keeping dialogue intelligible and human.

Master the final audio of every video to one consistent loudness: target −14 LUFS, true peak below −1 dBTP, so dialogue, music, and sound effects are the same volume across episodes and platforms. A character's voice must not be louder in one episode and barely audible in the next.

## 12. Web-Series Voices

A web series typically has 5–10 characters. Each of them needs a DISTINCT voice that stays consistent across all episodes — distinct enough that a listener can tell who is speaking without seeing the screen, and stable enough that episode 1 and episode 10 sound like the same people. Keep one voice profile per character, one reference audio per character, and one prosody fingerprint per character, and check all of them in the episode quality-control checklist before delivery.
