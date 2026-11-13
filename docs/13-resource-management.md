# On-Demand Resources — Load Only What the Work Needs

When a job runs, only the resources that job needs are loaded. Audio work loads the audio side. Video work loads the video side. When neither is running, only the assistant's own working memory is in use. Never open everything at once "just in case" and fill the machine's memory. Use resources slowly and carefully, only as needed — and never at the cost of the work. The work must stay beautiful.

Counting note: this 1 system is part of the repo total. Together with the 12 professional, 18 extended, 3 language/captions/format, 7 additional, 36 humanization, 7 agency advertising, 1 video regeneration, 5 cinematic power, 6 live-action & VFX, 7 emotional performance, and 1 user-supplied voice cloning systems, the repo holds 104 distinct systems, presented as 115 numbered entries.

## The three loads

There are only three things that can be loaded, and each one has its own time:

- **The voice plugin** — the VoiceStudio backend plus the OmniVoice model weights (a bundled component). It runs only for voice work.
- **The video plugin** — the OpenMontage assembly pipeline, FFmpeg, Remotion and Node (a bundled component). It runs only for video assembly.
- **The assistant's own working memory** — the current phase's context only: the characters in this episode, the current script, the current shot list. Not the whole library, not every character ever registered, not every past episode. The character registry holds the rest; working memory holds what this phase is doing.

## The phase table

| Phase | What runs | What stays off |
| --- | --- | --- |
| Planning and writing (script, shot list, story bible) | Working memory only | Both plugins |
| Voice generation | Voice plugin only | Video plugin |
| Video assembly | Video plugin only | Voice plugin — unless that same step genuinely needs new voice lines |
| Quality control and delivery | Only what the check needs — the finished render, the reference images and audio for the checks | Everything the check does not need |

Both plugins run together only when a step genuinely needs both at the same time. Otherwise the steps are sequenced: finish the voice work, stop the voice plugin, then start assembly. Together is the exception, decided by the step — never the default.

## Model weights and batch discipline

The OmniVoice weights load only while voice is being generated, and unload after — stopping the backend unloads them. Never preload the model before the voice phase starts; never leave it loaded after the voice phase ends. Voice generation is generate-once-reuse (`voice-consistency` skill, §2): a finished line is saved and reused as reference audio, so the model is never reloaded to regenerate the same line.

One character's voice at a time; never preload all characters' voices. Generate a character's lines, save them, move to the next character. Cloned voices follow the same rule (`voice-consistency` skill, §13): the clone is made once from the fixed reference, then reused.

## Stop rules

Never leave a plugin running "in case" it is needed later. Stop the voice backend immediately after the voice work is done. Stop the assembly processes immediately after the render is done. At the end of every phase, the only thing still running is the assistant's own working memory.

## The quality guard — non-negotiable

Resource discipline must NEVER degrade quality. If a job needs both plugins, run both. If the machine cannot hold both at once, do the work in sequence — never by cutting quality, skipping checks, or degrading output. Never skip the episode QC checklist (`production-systems` skill) to save resources. A skipped check is a defect, not a saving. If sequencing would change the result — for example, a line must be heard against the assembled cut — say so plainly and run both. Quality decides, not convenience.

## Honest limit

This repo cannot measure memory on every platform. This system is a start/stop discipline, not a memory meter: which plugin starts, when it starts, and when it stops. On the reference install, the production scripts start the plugins per phase and stop them after. If a platform cannot stop a plugin, say so plainly; the discipline still applies to everything that can be stopped.

Full rules: [`skills/resource-management/SKILL.md`](../skills/resource-management/SKILL.md) is the source of truth.
