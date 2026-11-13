---
name: language-authenticity
description: Speaks every language the way its native speakers speak it — US English, Bengali, Hindi — and delivers the same video in every language the user asks for, with lip-sync matched to the sounds of the language being spoken.
---

# Language Authenticity — Native Patterns, Multi-Language Delivery, and Lip-Sync

Every language in a video is spoken the way its native speakers speak it — never flattened into stiff, generic, textbook speech. If the user asks for the same video in three languages, deliver it in all three. If the user asks for them separately, deliver separate videos. And the mouth must move with the words: a character talking with a still mouth is a defect, never a delivery.

## 1. The Native-Pattern Rule — Speak Like a Native, Not Like a Textbook

Every language has its own pattern: its tone, its rhythm, its idioms, the way its speakers actually talk. Study how native speakers of that language talk, then speak that way.

- **US English** — American tone and idiom, the way Americans actually talk: natural contractions, everyday phrasing, the casual register of real conversation. Never stiff textbook English, never a flattened "neutral" accent that belongs to no one.
- **Bengali** — the Bengali tone and idiom, the way Bengali speakers actually talk.
- **Hindi** — the Hindi tone and idiom, the way Hindi speakers actually talk.
- **Any other language the user asks for** — the same rule: learn how its native speakers talk first, then speak that way.

The tone must be recognizably that language's own. If a listener cannot tell which language's speakers the voice belongs to, the pattern is wrong — fix it before delivery.

## 2. Native Register — Colloquial the Way Natives Use It

Match the register the script calls for. When the script is casual, the speech is casual the way natives are casual — including colloquial and slang words the way native speakers actually use them. The point is authenticity, not sanitizing the tone into something no native speaker would say.

- Do NOT invent profanity or add words the script does not call for. The script's meaning and dialogue stay intact; authenticity changes how a line is spoken, never what it says.
- Do NOT clean up a character's natural way of speaking into formal speech unless the script asks for formal speech. A street-smart character does not suddenly sound like a newsreader.

## 3. Per-Character Language Stays

Each character keeps their own language (see the `voice-consistency` skill, §9, and the `production-systems` skill, B15). A character speaking a different language still sounds like the same person — the voice profile does not change, only the language does. In one video each character may speak a different language; write each character's dialogue in that character's language and generate each character's voice in that language. Never force all characters into one language unless the user asks for it. Mid-sentence language switching (for example Bengali↔English) and regional accent are handled explicitly, with a separate listening test per language and per dialect (see the `voice-consistency` skill, §9).

## 4. Multi-Language Delivery — One Video, Every Language Asked For

When the user asks for the same video in N languages, deliver N versions — each one fully in its language: dialogue, voice, lip-sync, and on-screen text where applicable. When the user asks for them separately, deliver separate videos, one per language. Never deliver one language and promise the rest later without saying so plainly; never deliver a version in the wrong language.

- Each version is a complete video in its own language, not a re-voiced copy with the old language's mouth movements. The lip-sync, the on-screen text, and the captions all belong to that version's language (see §6 and §7).
- If the user names the languages in the prompt (for example "the same video in English, Bengali, and Hindi"), those are the versions to deliver — all of them, in that order unless the user says otherwise.

## 5. One Voice Across Languages — The Same Character in Every Language

The same character voice profile speaks each language — the engine is multilingual, so the voice stays recognizably the same character across languages. A character's voice (tags + seed + reference audio) is fixed across every episode and every language version; only the language changes. A cloned voice (see the `voice-consistency` skill, §13) speaks another language the same way: the approved recording stays the reference, and the clone speaks the new language in that person's voice.

## 6. Lip-Sync Follows the Language's Sounds

The mouth and lip shapes follow the sounds (phonemes) of the language actually being spoken. English, Bengali, and Hindi move the mouth differently — the same face with the same words in another language must move differently, because the sounds are different.

- Verify every line's mouth movement against its own audio track, in its own language version. A line whose mouth shapes belong to another language is a defect.
- A talking character with a still mouth is a defect — never deliver it. Dialogue timing must match the mouth: a line must not finish long before or after the character stops speaking (see the `production-systems` skill, A10).
- Check mouth interior sharpness, teeth stability, and tongue on close-ups, as part of the episode QC checklist (see the `humanized-production` skill, §30.29).
- If lip-sync is not supported on the platform, say so honestly instead of promising it (see the `production-systems` skill, A10).

## 7. On-Screen Text and Captions Per Language

Each language version carries its own on-screen text and captions in that version's language. Captions follow the same rule as dialogue: a caption track per language the user requests (see the `production-systems` skill, B15). Never burn in one language's text over another language's version.

## 8. QC Per Language Version — Native-Plausibility and Lip-Sync Checks

Before delivering any language version, run both checks for that version:

- **Native-plausibility check** — does it sound like a native speaker of that language? Test per language and per dialect with a separate listening test (see the `voice-consistency` skill, §9). Do not assume a multilingual model is equally good in all of them — especially Bengali and code-switched lines need a separate listening test.
- **Lip-sync check, per line** — the mouth matches the audio of that line, in that language. A still mouth, a mistimed line, or mouth shapes from another language fails the check; regenerate the line, do not accept the defect.

Do not deliver a language version that fails either check without telling the user what failed.

## 9. Honest Limits — Say Plainly What Cannot Be Verified

This system cannot prove native fluency beyond listening tests and the checks above. If a language version's quality cannot be verified — no listener for that language, no lip-sync support on the platform — say so plainly and deliver only what was actually checked. Never claim a version is native-perfect or lip-synced without the checks to back it.
