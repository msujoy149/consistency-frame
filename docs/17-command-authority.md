# Command Authority — Repo First, Self-Generate Only When Missing

This repo is the command master. After a user installs it, videos are made WITH PERMISSION from the repo — the assistant reads and uses the repo's skills FIRST for every video, before generating anything itself. A skill that exists in the repo is used, not reinvented; a missing system is generated from the repo's own generation command, then saved as a new skill and reported to the user.

Counting note: this 1 system is part of the repo total. Together with the 12 professional, 18 extended, 3 language/captions/format, 7 additional, 36 humanization, 7 agency advertising, 1 video regeneration, 5 cinematic power, 6 live-action & VFX, 7 emotional performance, 1 user-supplied voice cloning, 1 on-demand resource management, 1 language authenticity, 1 realistic person video, 1 2D explainer animation, and 1 kids & family animation systems, the repo holds 109 distinct systems, presented as 120 numbered entries.

## Order of work for every video

1. Read the script and the video type the user named.
2. Check the skill FIRST: if the skill already has the command for the thing being made, build from those skill commands. Skill commands take priority whenever they exist — for the videos this repo makes, almost all commands are already in the skills, so video work almost always takes this path.
3. Apply the supporting skills the type skill cross-references.
4. Run the QC checklist before delivery.
5. Only when no skill has the command does the repo fall back — to the generation command for a missing system, or to "do it yourself" for work with no repo instruction at all.

Never generate on your own while ignoring the repo.

## Missing skill fallback

If a needed skill is NOT in the repo, check the repo's comments and notes about that topic FIRST — the README, the docs, AGENTS.md, and the skill descriptions. If the repo has a comment on it, follow the comment. If the repo gives no comment, the repo issues a generation command (see below): generate the needed system from that command, in the repo's skill format, save it as a new skill in `skills/` so the repo now has it, and tell the user plainly what was added and why. Never silently invent a system that contradicts a repo skill or a repo comment.

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

When the repo has no instruction at all for something, it explicitly says "do it yourself" — that is permission, not an error and not a stop. But the permission is NEVER bare: it always carries the quality commands with it — do it CORRECTLY, do it CINEMATICALLY, do it HUMAN-GENERATED (human-feeling, never robotic), and do it according to the TASK (the need and the script decide the details). This path is ONLY when no skill has the command; if a skill has it, build from the skill.

## The common core — one instruction for any new task

For a NEW kind of task — for example animation: make a small animation, or make an animated cartoon from a given video or script — do NOT hunt through the skills one by one looking for a matching skill. The repo distills the main common rules from ALL its skills into ONE core instruction and gives that to the AI: "do the work this way." The core is short — it does not explain everything in detail — but it carries the universal rules that apply to ALL videos, the same in every chat and session: human-like, never robotic; no overlap between characters; lip-sync (the mouth moves with the voice, matching the sounds of the language); fixed character identity and fixed voice per character; the script decides; physical realism and continuity; QC before delivery; rights and consent for real people. If the new task later grows into a full system, generate it as a new skill from the generation command above so the repo now has it.

## Scope

This rule applies to every skill in the repo, including future ones, and to every platform the repo is installed on. The user's explicit instructions and script still outrank everything else.
