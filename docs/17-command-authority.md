# Command Authority — Repo First, Self-Generate Only When Missing

This repo is the command master. After a user installs it, videos are made WITH PERMISSION from the repo — the assistant reads and uses the repo's skills FIRST for every video, before generating anything itself. A skill that exists in the repo is used, not reinvented; a missing system is first written and saved as a new skill, and the video is then made by following that skill (the skill-first loop) — and reported to the user.

Counting note: this 1 system is part of the repo total. Together with the 12 professional, 18 extended, 3 language/captions/format, 7 additional, 36 humanization, 7 agency advertising, 1 video regeneration, 5 cinematic power, 6 live-action & VFX, 7 emotional performance, 1 user-supplied voice cloning, 1 on-demand resource management, 1 language authenticity, 1 realistic person video, 1 2D explainer animation, and 1 kids & family animation systems, the repo holds 109 distinct systems, presented as 120 numbered entries.

## Order of work for every video

1. Read the script and the video type the user named.
2. Check the skill FIRST: if the skill already has the command for the thing being made, build from those skill commands. Skill commands take priority whenever they exist — for the videos this repo makes, almost all commands are already in the skills, so video work almost always takes this path.
3. Apply the supporting skills the type skill cross-references.
4. Run the QC checklist before delivery.
5. Only when no skill has the command does the repo fall back — to the generation command for a missing system, or to "do it yourself" for work with no repo instruction at all.

Never generate on your own while ignoring the repo.

## Missing skill fallback

If a needed skill is NOT in the repo, check the repo's comments and notes about that topic FIRST — the README, the docs, AGENTS.md, and the skill descriptions. If the repo has a comment on it, follow the comment. If the repo gives no comment, the repo issues a generation command (see below): generate the needed system from that command, in the repo's skill format, save it as a new skill in `skills/` so the repo now has it, and tell the user plainly what was added and why. The order is fixed by the skill-first loop below: the skill is written and saved BEFORE any video is generated from it. Never silently invent a system that contradicts a repo skill or a repo comment.

## The generation command

When a skill is missing, the repo issues a generation command in this standard form:

- **Generate:** [the missing system, in one line — what it must do].
- **Preserve:** the fixed identity — the character's face, structure, hands, and feet; the character's voice (tags + seed + reference audio); the locked visual style; continuity with the episode and the series. Nothing fixed is ever redesigned.
- **Quality bar:** correct, cinematic, human-generated — human-feeling, never robotic. Realism target 100%, 99.9% as the floor.
- **Verify:** check the result against the fixed reference; run the episode QC checklist; the user approves before anything is locked in.
- **Save:** write it as a new skill in `skills/` in the repo's skill format, and tell the user plainly what was added and why.

## Light details are delegated

Small things the AI creates itself — the emotion in a line, the tone of a reply, natural phrasing, a pause, a sigh, a small gesture. The AI decides these details. But the direction for them comes from the repo: the script's emotion per line, the character's established personality, the scene's beat, and the humanization systems. The AI never invents a detail that contradicts a fixed identity, a locked voice, or the script.

## "Do it yourself" — the explicit permission, never bare

When the repo has no instruction at all for something, it explicitly says "do it yourself" — that is permission, not an error and not a stop. But the permission is NEVER bare: it always carries the quality commands with it, AND the main flow — "do it yourself, following this flow, step by step." The flow is what keeps the work correct: the AI follows the repo's order and improvises only the details inside each step (emotion, tone, phrasing), never the video itself. Without the flow, "do it yourself" could produce any video; with the flow, it produces the right video. The quality commands: do it CORRECTLY, do it CINEMATICALLY, do it HUMAN-GENERATED (human-feeling, never robotic), and do it according to the TASK (the need and the script decide the details). This path is ONLY when no skill has the command; if a skill has it, build from the skill.

**The main flow — the repo's order for every video, handed over with the permission:**

1. Read the script and the user's instructions. The script decides. If an essential detail is missing, ask the smallest necessary clarification — never guess at something that could make the wrong video.
2. Lock what is fixed before generating anything: character identity from the approved reference (face, structure, hands, feet); voice (tags + seed + reference audio); one locked visual style; each character's language. Nothing fixed is ever redesigned.
3. Break the script into beats and plan the shots from the beats. Storyboard and shot list first; the angle follows the beat — establishing shot, main action, reaction shot, closing shot. With no script, write the story as beats first, then direct the angles from those beats.
4. Decide the voice/video order for this project and keep it: voice first, then video matched to it — or video first, then voice. One order, followed consistently through the whole project.
5. Generate shot by shot, line by line, from the script. Dialogue in each character's language, in natural spoken language, short lines with pauses; lip-sync matched to the sounds of that language. Apply the standing defect list; keep the locked style and the scene's colour grade.
6. Keep continuity while generating: story bible and continuity tracker; no overlap between characters; check each shot against the fixed reference as you go — a drifted face is regenerated fresh, never inpainted; clip boundaries must match.
7. Add the sound: ambience and room tone, foley on visible beats, dialogue, music ducked under dialogue; scene music follows the scene's emotion. Master to −14 LUFS, true peak below −1 dBTP.
8. Run the QC checklist before delivery: faces, voices, emotions, dialogue exact, no defects, clothing, sound matched, no contradiction with the story bible or the continuity tracker. Never deliver a failed check without telling the user what failed.
9. Deliver in the requested format, and get approval. Aspect ratio and platform as asked. The user approves before anything is locked in.
10. If the work grows into a system, save it: generate it as a new skill from the generation command above so the repo now has it.

## The common core — one instruction for any new task

For a NEW kind of task — for example animation: make a small animation, or make an animated cartoon from a given video or script — do NOT hunt through the skills one by one looking for a matching skill. The repo distills the main common rules from ALL its skills into ONE core instruction and gives that to the AI: "do the work this way." The core is short — it does not explain everything in detail — but it carries the universal rules that apply to ALL videos, the same in every chat and session: human-like, never robotic; no overlap between characters; lip-sync (the mouth moves with the voice, matching the sounds of the language); fixed character identity and fixed voice per character; the script decides; physical realism and continuity; QC before delivery; rights and consent for real people. If the new task later grows into a full system, generate it as a new skill from the generation command above so the repo now has it.

The core carries the rules; the main flow above carries the order — a "do it yourself" command hands over both, so the work is the right video, not any video.

## The skill-first loop — a missing skill is written first, the video follows it

The missing-skill fallback and the generation command say a missing skill is generated and saved. The loop fixes the ORDER, because the order is what makes the video correct: a skill written after the video is only a record of what was improvised. A skill written BEFORE the video is what the video is made by. When a skill is missing, the repo runs this loop, in this exact order — never skipped, never reordered:

1. Detect the gap: no skill has the command for the thing being made.
2. Check the repo's comments and notes first — the README, the docs, AGENTS.md, and the skill descriptions. If the repo has a comment on it, follow the comment.
3. Write the new skill FIRST. If the repo gives no comment, build the missing system from the script's need, the common core, the main flow, and the generation command — in the repo's skill format: YAML frontmatter with name and description, numbered sections, and citations to the existing systems it builds on. Save it in `skills/` BEFORE generating any video.
4. Then make the video by following that new skill exactly — the normal skill-first path. Never improvise the video from the generation command alone.
5. Run the QC checklist before delivery. The user approves before anything is locked in.
6. Tell the user plainly what was added and why.
7. Keep the repo's own numbers true. When a new skill is actually added this way, update the counts, the README, docs/01, the CHANGELOG, and the plugin manifests (which list every skill) — so the repo's own numbers never go stale.

The guarantee: with this loop, no video is ever improvised — every video is made by following some skill — and every gap is closed permanently the first time it appears. The next time the same kind of video is asked for, the skill is already there, and the work takes the ordinary skill-first path.

What this loop is NOT: it does not change "do it yourself". Small work with no repo instruction at all still takes that path — quality commands plus the main flow. The loop is only for a genuinely missing SYSTEM — a skill the repo does not have.

## Scope

This rule applies to every skill in the repo, including future ones, and to every platform the repo is installed on. The user's explicit instructions and script still outrank everything else.
