---
name: command-authority
description: The repo is the command master — after install, every video is made by reading and using the repo's skills first. A skill that exists is used, never reinvented; a missing system is generated only after checking the repo's notes, then saved as a new skill and reported to the user.
---

# Command Authority — Repo First, Self-Generate Only When Missing

This repo is the command master. After a user installs it, videos are made WITH PERMISSION from the repo — the assistant reads and uses the repo's skills FIRST for every video, before generating anything itself.

## 1. The Repo Commands, the Assistant Follows

- Every video starts by reading the user's script and the video type they named.
- Find the repo skill for that type and follow it exactly: character, voice, language, camera, style, QC.
- A skill that exists in the repo is used, not reinvented. Never generate on your own while ignoring the repo.

## 2. Order of Work for Every Video

1. Read the script and the video type the user named.
2. Find the repo skill for that type and follow it.
3. Apply the supporting skills the type skill cross-references (character, voice, language, camera, humanization, realism).
4. Run the QC checklist before delivery.

## 3. Missing Skill Fallback — Check the Repo First, Then Generate

- If a needed skill is NOT in the repo, check the repo's comments and notes about that topic FIRST — the README, the docs, AGENTS.md, and the skill descriptions. If the repo has a comment on it, follow the comment.
- If the repo gives no comment, generate the needed system yourself, in the repo's skill format, and save it as a new skill in `skills/` so the repo now has it.
- Tell the user plainly what was added and why.
- Never silently invent a system that contradicts a repo skill or a repo comment.

## 4. This Rule Applies to Everything

- To every skill in the repo, including future ones, and to every platform the repo is installed on.
- The user's explicit instructions and script still outrank everything else.
