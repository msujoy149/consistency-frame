# Changelog

All notable changes to Consistency Frame are recorded here. Releases use
semantic-style versioning: small updates bump the minor number (2.1,
2.2), big breaking changes bump the major number (3.0). Every release
lists what changed.

## [2.0] — 2026-11-12 — First release

The first public release. The complete system: **86 systems** for
consistent characters, consistent voices, and human-feeling video, in
any AI platform.

### Included

- **Character consistency** — character registry (per-character folder:
  `character.yaml`, 3–4 reference images, voice reference audio),
  registration rules (name + unique ID + reference image(s) + explicit
  authorization; name-on-image not mandatory, required only when several
  characters' images arrive in one batch), identity resolution (a name
  in a script resolves to that character's ID + reference image + voice
  + prompt block), prompt builder (fixed prompt block + fixed seed per
  character), 100% reference fidelity (face and height most important;
  one photo enough, several more reliable), character recall (show the
  character exactly as stored, on request), fixed identity structure
  with scene-variable clothing and props, multi-character scenes with no
  overlap, private character data separation with a private overlay.
- **Voice consistency** — fixed voice profiles (tags + seed + reference
  audio) per character, reused every episode; VoiceStudio/OmniVoice
  integration; single-pass multi-speaker dialogue; voice-drift
  measurement; voice ageing and state variants; code-switching and
  dialect rule with a separate listening test per language;
  distance-and-space in voice; dialogue-first mixing.
- **Professional production systems (11)** — visual style bible;
  camera language and shot list; negative prompt library; sound design
  system; music and theme; story bible; episode continuity tracker;
  dialogue writing rules; reference photo quality rules; lip-sync and
  dubbing workflow; episode QC checklist.
- **Extended production systems (18)** — subtitles/captions pipeline;
  thumbnail/poster generator; character turnaround/model sheets;
  wardrobe/prop/location registry; clip-boundary seam continuity;
  quantitative drift measurement; per-character LoRA training;
  character aging/time-jump variants; shot-level provenance log; cost &
  credit tracking; backup/versioning of character data;
  multi-project/multi-series namespaces; child-safety rules; audio
  mastering standard (−14 LUFS); localisation/dubbing pack;
  distribution package; rights/consent/provenance records; audience
  feedback loop.
- **Language, captions, and format rules (3)** — captions OPT-IN (ask
  first, default no baked-in captions, any language on request);
  per-character language in one video; format/aspect ratio on demand
  (16:9, 9:16, 1:1, 4:5, any ratio; short or long; any platform;
  compose for the ratio from the start, never crop afterwards).
- **Additional systems (7)** — private character data separation;
  multi-character scenes and no overlap; episode intake checklist;
  demo project (on-demand system, no demo content shipped); script
  template and automatic script enhancement; contribution guide;
  script-driven realism and colour grading by time of day and light
  source.
- **Humanization systems (36)** — performance-driven acting;
  single-pass multi-speaker dialogue; involuntary micro-motion;
  listener-reaction rule; room tone / never-silence + 4-layer sound;
  non-verbal voice layer; eye/gaze continuity; hands & physics
  avoidance + repair; anti-plastic skin; editing rhythm; film-finish
  pipeline; voice-drift measurement; temporal-artifact QC; camera
  imperfection; lighting-continuity lock; background life; cloth/hair
  physics; distance & space in voice; sound spotting sheet; AI
  disclosure & provenance pack; detector self-QC; audio description
  track; voice ageing/state variants; code-switching & dialect rule;
  model-version pinning + golden regression; re-anchor every ~8–16 s;
  reference-count strategy per model; human blind-test gate;
  mouth-interior QC in lip-sync; wardrobe wear & continuity detail;
  imperfection budget; music-ducking / dialogue-first mix; failure &
  fallback playbook; real-person safeguards; realism budget; cinematic
  backgrounds.
- **Portable install** — Agent Skills standard (`skills/` as the source
  of truth) with thin per-platform manifests for Claude Code, Codex,
  Gemini CLI, and Antigravity, plus a Muse path (clone + `./setup.sh`).
  VoiceStudio and OpenMontage bundled as submodules; OmniVoice weights
  downloaded at install from Hugging Face with the CC-BY-NC notice.
- **Docs** — full system documentation in `docs/`, including the two
  background research reports in `docs/research/`.
- **Licence** — this project's own work under Apache-2.0; VoiceStudio
  and OpenMontage under AGPL-3.0 (submodules, licences intact);
  OmniVoice model under CC-BY-NC (noncommercial).
