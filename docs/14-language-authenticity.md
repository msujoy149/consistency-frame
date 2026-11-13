# Language Authenticity — Native Patterns, Multi-Language Delivery, and Lip-Sync

Every language in a video is spoken the way its native speakers speak it — never flattened into stiff, generic, textbook speech. US English sounds American, Bengali sounds Bengali, Hindi sounds Hindi. If the user asks for the same video in three languages, deliver it in all three; if asked separately, deliver separate videos. And the mouth must move with the words: a talking character with a still mouth is a defect, never a delivery.

Counting note: this 1 system is part of the repo total. Together with the 12 professional, 18 extended, 3 language/captions/format, 7 additional, 36 humanization, 7 agency advertising, 1 video regeneration, 5 cinematic power, 6 live-action & VFX, 7 emotional performance, 1 user-supplied voice cloning, and 1 on-demand resource management systems, the repo holds 105 distinct systems, presented as 116 numbered entries.

## The native-pattern rule

Every language has its own pattern: tone, rhythm, idioms, the way its speakers actually talk. Study how native speakers of that language talk, then speak that way. US English carries the American tone and everyday phrasing; Bengali carries the Bengali tone and idiom; Hindi carries the Hindi tone and idiom. Any other language the user asks for follows the same rule. If a listener cannot tell which language's speakers the voice belongs to, the pattern is wrong.

## Native register

Match the register the script calls for. When the script is casual, the speech is casual the way natives are casual — including colloquial and slang words the way native speakers actually use them. Authenticity changes how a line is spoken, never what it says: never invent profanity or add words the script does not call for, and never clean a character's natural way of speaking into formal speech unless the script asks for it.

## Per-character language stays

Each character keeps their own language (see the `voice-consistency` skill, §9, and the `production-systems` skill, B15). A character speaking a different language still sounds like the same person — the voice profile does not change, only the language does. Mid-sentence language switching and regional accent are handled explicitly, with a separate listening test per language and per dialect.

## Multi-language delivery

When the user asks for the same video in N languages, deliver N versions — each one fully in its language: dialogue, voice, lip-sync, and on-screen text where applicable. When the user asks for them separately, deliver separate videos, one per language. Each version is a complete video in its own language, not a re-voiced copy with the old language's mouth movements.

## One voice across languages

The same character voice profile speaks each language — the engine is multilingual, so the voice stays recognizably the same character across languages. A cloned voice (see the `voice-consistency` skill, §13) speaks another language the same way: the approved recording stays the reference, and the clone speaks the new language in that person's voice.

## Lip-sync follows the language's sounds

The mouth and lip shapes follow the sounds (phonemes) of the language actually being spoken. English, Bengali, and Hindi move the mouth differently. Verify every line's mouth movement against its own audio track, in its own language version. A talking character with a still mouth is a defect — never deliver it. Check mouth interior sharpness, teeth stability, and tongue on close-ups (see the `humanized-production` skill, §30.29). If lip-sync is not supported on the platform, say so honestly instead of promising it (see the `production-systems` skill, A10).

## On-screen text and captions per language

Each language version carries its own on-screen text and captions in that version's language — a caption track per language the user requests (see the `production-systems` skill, B15). Never burn in one language's text over another language's version.

## QC per language version

Before delivering any language version, run both checks for that version: a native-plausibility listening test (does it sound like a native speaker of that language?) and a lip-sync check per line (the mouth matches the audio of that line, in that language). Do not deliver a version that fails either check without telling the user what failed.

Full rules: [`skills/language-authenticity/SKILL.md`](../skills/language-authenticity/SKILL.md).
