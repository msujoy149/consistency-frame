---
name: resource-management
description: Loads only what the work needs — the voice plugin runs only for voice work, the video plugin only for video assembly, and the assistant's working memory holds only the current phase, never everything at once. Covers the phase table, the both-plugins-together rule, model-weight loading, batch discipline, stop rules, and the non-negotiable quality guard — resource discipline never degrades quality.
---

# Resource Management — Load Only What the Work Needs

When a job runs, only the resources that job needs are loaded. Audio work loads the audio side. Video work loads the video side. When neither is running, only the assistant's own working memory is in use. Never open everything at once "just in case" and fill the machine's memory. Use resources slowly and carefully, only as needed — and never at the cost of the work. The work must stay beautiful.

## 1. The Principle — Load Only What the Phase Needs

Every phase of a production needs different tools, so every phase loads different tools. A phase loads what it needs when it starts, and unloads it when it ends. Nothing is loaded early "to be safe", nothing is kept loaded "in case" the next phase wants it. The machine holds one phase's tools at a time, not the whole production at once.

## 2. The Three Loads

There are only three things that can be loaded, and each one has its own time:

- **The voice plugin** — the VoiceStudio backend plus the OmniVoice model weights (a bundled component). It runs only for voice work.
- **The video plugin** — the OpenMontage assembly pipeline, FFmpeg, Remotion and Node (a bundled component). It runs only for video assembly.
- **The assistant's own working memory** — the current phase's context only: the characters in this episode, the current script, the current shot list. Not the whole library, not every character ever registered, not every past episode. The character registry holds the rest; working memory holds what this phase is doing.

## 3. The Phase Table

| Phase | What runs | What stays off |
| --- | --- | --- |
| Planning and writing (script, shot list, story bible) | Working memory only | Both plugins |
| Voice generation | Voice plugin only | Video plugin |
| Video assembly | Video plugin only | Voice plugin — unless that same step genuinely needs new voice lines |
| Quality control and delivery | Only what the check needs — the finished render, the reference images and audio for the checks | Everything the check does not need |

## 4. Both Plugins Together — Only When the Step Genuinely Needs Both

If a step genuinely needs voice and assembly at the same time, run both. Otherwise sequence the steps: finish the voice work, stop the voice plugin, then start assembly. Never run both "in case" the next step might need one of them. Together is the exception, decided by the step — never the default.

## 5. Model Weights — Load to Generate, Unload After

The OmniVoice weights load only while voice is being generated, and unload after — stopping the backend unloads them. Never preload the model before the voice phase starts; never leave it loaded after the voice phase ends. Voice generation is generate-once-reuse (see the `voice-consistency` skill, §2): a finished line is saved and reused as reference audio, so the model is never reloaded to regenerate the same line.

## 6. Batch Discipline — One Character at a Time

One character's voice at a time; never preload all characters' voices. Generate a character's lines, save them, move to the next character. A series with 5–10 characters is still done one voice at a time (see the `voice-consistency` skill, §12). Cloned voices follow the same rule (see the `voice-consistency` skill, §13): the clone is made once from the fixed reference, then reused — the reference is never re-cloned to save a step.

## 7. Stop Rules — Nothing Runs "Just in Case"

Never leave a plugin running "in case" it is needed later. Stop the voice backend immediately after the voice work is done. Stop the assembly processes immediately after the render is done. At the end of every phase, the only thing still running is the assistant's own working memory.

## 8. The Quality Guard — Non-Negotiable

Resource discipline must NEVER degrade quality.

- If a job needs both plugins, run both.
- If the machine cannot hold both at once, do the work in sequence — never by cutting quality, skipping checks, or degrading output.
- Never skip the episode QC checklist (see the `production-systems` skill) to save resources. A skipped check is a defect, not a saving.
- If sequencing would change the result — for example, a line must be heard against the assembled cut — say so plainly and run both. Quality decides, not convenience.

## 9. Honest Limit — A Start/Stop Discipline, Not a Memory Meter

This repo cannot measure memory on every platform. This system is a start/stop discipline, not a memory meter: which plugin starts, when it starts, and when it stops. On the reference install, the production scripts start the plugins per phase and stop them after. If a platform cannot stop a plugin, say so plainly; the discipline still applies to everything that can be stopped.
