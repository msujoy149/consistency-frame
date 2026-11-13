---
name: command-authority
description: "The repo is the command master — after install, every video is made by reading and using the repo's skills first. A skill that exists is used, never reinvented; a missing system is generated from the repo's own generation command and saved as a new skill; light details are delegated with direction from the repo; a new task type starts from the distilled common core; and when the repo has no instruction at all it says 'do it yourself' — never bare, always with the quality commands and the main flow attached."
---

# Command Authority — Repo First, Self-Generate Only When Missing

This repo is the command master. After a user installs it, videos are made WITH PERMISSION from the repo — the assistant reads and uses the repo's skills FIRST for every video, before generating anything itself.

## 1. The Repo Commands, the Assistant Follows

- Every video starts by reading the user's script and the video type they named.
- Find the repo skill for that type and follow it exactly: character, voice, language, camera, style, QC.
- A skill that exists in the repo is used, not reinvented. Never generate on your own while ignoring the repo.

## 2. Order of Work for Every Video

1. Read the script and the video type the user named.
2. Check the skill FIRST: if the skill already has the command for the thing being made, build from those skill commands. Skill commands take priority whenever they exist — for the videos this repo makes, almost all commands are already in the skills, so video work almost always takes this path.
3. Apply the supporting skills the type skill cross-references (character, voice, language, camera, humanization, realism).
4. Run the QC checklist before delivery.
5. Only when no skill has the command for it does the repo fall back — to the generation command (§5) for a missing system, or to "do it yourself" (§7) for work with no repo instruction at all.

## 3. Missing Skill Fallback — Check the Repo First, Then Generate

- If a needed skill is NOT in the repo, check the repo's comments and notes about that topic FIRST — the README, the docs, AGENTS.md, and the skill descriptions. If the repo has a comment on it, follow the comment.
- If the repo gives no comment, the repo issues a generation command (§5): generate the needed system from that command, in the repo's skill format, and save it as a new skill in `skills/` so the repo now has it.
- Tell the user plainly what was added and why.
- Never silently invent a system that contradicts a repo skill or a repo comment.

## 4. This Rule Applies to Everything

- To every skill in the repo, including future ones, and to every platform the repo is installed on.
- The user's explicit instructions and script still outrank everything else.

## 5. The Generation Command — What the Repo Issues When a Skill Is Missing

When a skill is missing, the repo does not leave the assistant guessing — it issues a generation command in this standard form, and the assistant generates from it:

- **Generate:** [the missing system, in one line — what it must do].
- **Preserve:** the fixed identity — the character's face, structure, hands, and feet; the character's voice (tags + seed + reference audio); the locked visual style; continuity with the episode and the series. Nothing fixed is ever redesigned.
- **Quality bar:** correct, cinematic, human-generated — human-feeling, never robotic. Realism target 100%, 99.9% as the floor.
- **Verify:** check the result against the fixed reference; run the episode QC checklist; the user approves before anything is locked in.
- **Save:** write it as a new skill in `skills/` in the repo's skill format, and tell the user plainly what was added and why.

## 6. Light Details Are Delegated — the AI Decides Them, the Repo Directs Them

Small things the AI creates itself — the emotion in a line, the tone of a reply, natural phrasing, a pause, a sigh, a small gesture. The AI decides these details. But the direction for them comes from the repo: the script's emotion per line, the character's established personality, the scene's beat, and the humanization systems. The AI never invents a detail that contradicts a fixed identity, a locked voice, or the script.

## 7. "Do It Yourself" — The Explicit Permission, Never Bare

When the repo has no instruction at all for something, it explicitly says "do it yourself" — that is permission, not an error and not a stop. The AI does it on its own. But the permission is NEVER bare: it always carries the quality commands with it, AND the main flow — "do it yourself, following this flow, step by step." The flow is what keeps the work correct: the AI follows the repo's order and improvises only the details inside each step (emotion, tone, phrasing — §6), never the video itself. Without the flow, "do it yourself" could produce any video; with the flow, it produces the right video.

- **Do it CORRECTLY** — the work must be right, not approximate.
- **Do it CINEMATICALLY** — framed, lit, and cut like cinema, not like a placeholder.
- **Do it HUMAN-GENERATED** — human-feeling, never robotic; a person must feel like a person, a voice like a voice.
- **Do it according to the TASK** — the need and the script decide the details; the script outranks everything else.

**The main flow — the repo's order for every video, handed over with the permission:**

1. **Read the script and the user's instructions.** The script decides. If an essential detail is missing, ask the smallest necessary clarification — never guess at something that could make the wrong video (`production-systems` C3).
2. **Lock what is fixed before generating anything.** Character identity from the approved reference (face, structure, hands, feet); voice (tags + seed + reference audio); one locked visual style; each character's language. Nothing fixed is ever redesigned (`character-consistency`, `voice-consistency` §1–§2, `production-systems` A1).
3. **Break the script into beats and plan the shots from the beats.** Storyboard and shot list first; the angle follows the beat — establishing shot, main action, reaction shot, closing shot (`production-systems` A2, A12). With no script, write the story as beats first, then direct the angles from those beats (A12 §10).
4. **Decide the voice/video order for this project and keep it.** Voice first, then video matched to it — or video first, then voice. One order, followed consistently through the whole project (`production-systems` A10, `voice-consistency` §8).
5. **Generate shot by shot, line by line, from the script.** Dialogue in each character's language, in natural spoken language, short lines with pauses; lip-sync matched to the sounds of that language (`production-systems` A8, A10, D2). Apply the standing defect list (`production-systems` A3); keep the locked style and the scene's colour grade (C7).
6. **Keep continuity while generating.** Story bible and continuity tracker (`production-systems` A6, A7); no overlap between characters (C2); check each shot against the fixed reference as you go — a drifted face is regenerated fresh, never inpainted (`character-consistency` §14); clip boundaries must match (B5).
7. **Add the sound.** Ambience and room tone, foley on visible beats, dialogue, music ducked under dialogue; scene music follows the scene's emotion (`production-systems` A4, A5). Master to −14 LUFS, true peak below −1 dBTP (B14).
8. **Run the QC checklist before delivery.** Faces, voices, emotions, dialogue exact, no defects, clothing, sound matched, no contradiction with the story bible or the continuity tracker (`production-systems` A11). Never deliver a failed check without telling the user what failed.
9. **Deliver in the requested format, and get approval.** Aspect ratio and platform as asked (`production-systems` D3). The user approves before anything is locked in.
10. **If the work grows into a system, save it.** Generate it as a new skill from the generation command (§5) so the repo now has it.

And the priority from §2 still holds: this path is ONLY when no skill has the command. If a skill has it, build from the skill.

## 8. The Common Core — One Instruction for Any New Task

For a NEW kind of task — for example animation: make a small animation, or make an animated cartoon from a given video or script — do NOT hunt through the skills one by one looking for a matching skill. The repo distills the main common rules from ALL its skills into ONE core instruction and gives that to the AI: "do the work this way." The AI works from this core — no skill-hunting.

The core instruction is short — it does not explain everything in detail — but it carries the universal rules that apply to ALL videos, the same in every chat and session:

- **Human-like, never robotic** — characters move, talk, and act like people; voices sound like people; nothing sits as a still with a voice over it (`humanized-production`, `voice-consistency` §4).
- **No overlap** — characters never overlap each other; each character keeps their own space (`character-consistency` multi-character scenes).
- **Lip-sync** — if a character speaks, the mouth moves with the voice: the lips match the sounds of the language being spoken. A talking character with a still mouth is a defect (`language-authenticity`, `voice-consistency`).
- **Fixed identity** — a character's face, structure, hands, and feet never change; their voice (tags + seed + reference audio) never changes (`character-consistency`, `voice-consistency` §1–§2).
- **The script decides** — the user's script and instructions outrank everything else (§4).
- **Physical realism and continuity** — movement, objects, and light stay believable and continuous across cuts (`production-systems`).
- **QC before delivery** — the episode QC checklist runs before anything is delivered (`production-systems`).
- **Rights and consent** — a real person's photo or voice is used only with permission (`production-systems` B17).

If the new task later grows into a full system, generate it as a new skill from the generation command (§5) so the repo now has it.

The core carries the rules; the main flow in §7 carries the order — a "do it yourself" command hands over both, so the work is the right video, not any video.
