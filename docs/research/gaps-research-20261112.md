# Consistency Frame — Gaps in a Professional AI Video / Character-Consistency System

**Date researched:** 2026-11-12. **Method:** web index (search results); no live-browser verification of vendor docs. Secondary sources (guides, vendor blogs) are flagged where they summarise primary docs. No tool names or prices invented; uncertain items are marked **uncertain**.

## Summary

1. **Gaps:** the system covers identity, voice, story and QC well, but is missing the packaging/distribution layer (subtitles, thumbnails, multi-format exports), quantitative drift measurement, per-character LoRA training, clip-boundary continuity, cost tracking, versioning/backup, child-safety rules, and an audience-feedback loop — 18 gaps listed below.
2. **Cross-platform skills:** in 2026 the portable core is the **Agent Skills open standard** — one `SKILL.md` folder per skill. Claude Code, Codex, ChatGPT, Gemini CLI and Antigravity all read it; only the install paths and plugin manifests differ. Meta's personal **Muse app has no documented skill-install flow** (Muse Code is the exception) — paste-into-chat is the practical route there.
3. **YouTube kids publishing:** set Made for Kids on every video, disclose realistic AI use, expect no personalized ads/comments/end screens, and avoid templated mass-produced content (YouTube's "inauthentic content" policy). Details and a short checklist in §3.

---

## 1. Gaps in professional AI video / character-consistency pipelines

Each gap is something the system as described does **not** include. "Why it matters" is one line. Items marked *(inference)* are logical gaps with no direct source found — verify before building.

| # | Gap | Why it matters |
|---|---|---|
| 1 | **Subtitles/captions pipeline** — Bengali SRT/VTT per episode, plus English subtitles, burned-in vs. sidecar captions, and a subtitle QC step | Captions are a listed distribution deliverable and an accessibility/discovery requirement; the system has dialogue and lip-sync but no caption output at all. |
| 2 | **Thumbnail/poster & channel-art generator** — one honest frame-based thumbnail per episode, title text rules, poster/character cards | YouTube Kids filters scan title + thumbnail + video; misleading/sensational thumbnails are a top demonetisation trigger. |
| 3 | **Turnaround / model sheets per character** — approved front, three-quarter, profile and full-body refs before any episode generation | Reference adapters drift without a canonical multi-angle sheet; this is the standard first step in creator workflows. |
| 4 | **Wardrobe, prop & location registry** — per-character outfit/props with version IDs, not just face/height | Faces can hold while clothes, hair and props drift shot to shot — the most visible continuity break after face drift. |
| 5 | **Clip-boundary / seam continuity** — end frame of clip N becomes the start frame of clip N+1; a seam-check step | Identity holds inside a 5–8s clip and breaks at clip boundaries; this seam is where most AI "films" fall apart. |
| 6 | **Quantitative drift measurement** — face-embedding similarity score (e.g. InsightFace cosine similarity) vs. the reference, with a numeric pass/fail threshold per shot | The QC checklist is currently human-eyeball only; without a number, "100% fidelity" is unenforceable and drift compounds silently. |
| 7 | **Per-character LoRA training option** — a trained character LoRA stacked under the identity adapter, as the maximum-consistency tier | Zero-shot adapters alone are the lower tier; production series use LoRA + adapter for the strongest lock. |
| 8 | **Character aging / time-jump variants** — versioned age states (child → older) with explicit rules for when a character ages | A multi-season series needs characters to grow; without versioned age states, "consistency" and "aging" contradict each other. *(inference)* |
| 9 | **Shot-level provenance log** — model name/version, prompt, seed, reference image hash recorded per shot | Without it you cannot reproduce a good shot, debug a bad one, or prove what a frame was made with. |
| 10 | **Cost & credit tracking** — per-episode/per-shot generation cost ledger (attempts counted, credits, API spend) and a per-finished-minute budget | AI generation cost is driven by attempts per shot and model choice; unbudgeted series routinely overspend on re-rolls. |
| 11 | **Backup & versioning of character data** — versioned registry (git + LFS or equivalent), checksums, restore procedure, changelog per character | Reference images, voice profiles and seeds are the series' core assets; one corrupted/overwritten file destroys a character. *(inference, standard practice)* |
| 12 | **Multi-project / multi-series management** — namespaces so characters, bibles and registers from Series A can't collide with Series B | A single global registry breaks the moment the user starts a second series with a same-named character. *(inference)* |
| 13 | **Child-safety rules for child characters** — hard bans (no distress/romantic/violent/sexualised depictions of child characters, no real-child photos as references without consent, no famous-character misuse) | YouTube's child-safety policy can terminate a channel outright; since March 2026 young-looking characters in distress can't earn ad revenue. |
| 14 | **Audio mastering standard** — loudness target (−14 LUFS is the cited standard), audio ducking, per-episode loudness check | Episodes with uneven dialogue/music loudness fail the professional bar and hurt retention; the system has sound design but no loudness spec. |
| 15 | **Localisation / dubbing pack** — English (or other-language) dub + subtitles from the same script and voice profiles | A Bengali series' growth path is dubbed/subtitled versions; building this in later means re-doing lip-sync and timing. |
| 16 | **Distribution package** — 16:9 episode + 9:16 Shorts cutdowns, teaser, stills, caption files, alternate ratios per platform | Publishing needs more than the master file; distribution deliverables are budgeted as a separate layer by professional studios. |
| 17 | **Rights, consent & provenance records** — voice-clone consent per voice, model licence checks, C2PA/content-credential watermarking | Cloned voices and generated likenesses without a consent/licence record are a legal and platform risk. |
| 18 | **Audience feedback loop** — retention/average-view-duration review per episode, structured "what to fix next episode" step (comments are disabled on Made-for-Kids videos, so feedback must come from analytics, not comments) | Without a watch-data → next-episode loop, continuity and pacing errors repeat every episode instead of being fixed once. *(inference, supported by retention evidence below)* |

**Sources for §1:** turnaround sheets, wardrobe drift and reusing the same references — https://www.aitoolspro.tech/blog/how-to-make-ai-video-with-consistent-characters-2026 (index, 2026 guide); clip-boundary seam and identity hardness — https://github.com/hoodini/ai-agents-skills/blob/HEAD/skills/director/references/16-ai-character-consistency.md (index); LoRA + adapter as max-consistency tier — https://github.com/neversight/learn-skills.dev/blob/HEAD/data/skills-md/mckruz/comfyui-expert/comfyui-character-gen/SKILL.md (index); reference pack, per-shot provenance, count attempts, acceptance checklist — https://magichour.ai/blog/ai-video-generation-tools-for-creators-and-studios (index, docs checked Sept 2026); −14 LUFS, audio ducking, kinetic subtitles, C2PA — https://www.autora.live/blog/multi-model-ai-video-workflows-character-consistency-motion-guide and https://www.paidmediaworld.com/ai-video-creative-pipelines-comfyui-runway-gen3-elevenlabs-meta-ads/ (index, vendor blogs — treat the 40–65% retention-drop claim on the AUTORA page as **uncertain**, vendor marketing); cost layers and per-finished-minute budgeting — https://www.alternateaistudio.com/blog/ai-microdrama-production-cost (index; vendor price examples $400–$1,200 per 1–2-min episode are vendor-reported, not a rate card — do not quote as market prices).

---

## 2. Cross-platform AI skill repos in 2026

### 2.1 The portable core: the Agent Skills open standard

- A skill is **a folder containing a `SKILL.md` file** (required) plus optional `scripts/`, `references/`, `assets/` subfolders. `SKILL.md` = YAML frontmatter (`name`, `description` — both required) + Markdown instructions.
- Frontmatter rules: `name` 1–64 chars, lowercase letters/numbers/hyphens, must match the folder name; `description` 1–1024 chars stating what the skill does **and when to use it**.
- **Progressive disclosure:** at startup the agent loads only name + description; on a matching task it reads the full `SKILL.md`; scripts/references load only on demand.
- History: Anthropic shipped skills Oct 2025; published as an open standard at agentskills.io on **18 Dec 2025**; donated to the Linux Foundation's Agentic AI Foundation in Oct 2026. 70+ platforms claimed to have integrated it.
- Portability rule: keep only standard fields (`name`, `description`, `license`, `metadata`, `compatibility`) in frontmatter; Claude-only fields (`allowed-tools`, `context: fork`, `model`, hooks) are client extensions that other hosts ignore.

Sources: https://agentscamp.com/guides/skills/agent-skills-open-standard (index, verified against vendor docs July 2026); https://app.thecompanion.sh/blog/what-is-skill-md (index); https://www.productbuilder.net/learn/agent-skills (index).

### 2.2 Per-platform install paths and formats

| Platform | Where skills are read from | Install mechanism |
|---|---|---|
| **Claude Code** | Project `.claude/skills/<name>/`, user `~/.claude/skills/<name>/` | Plugin: `.claude-plugin/marketplace.json` (registry) + `plugins/<name>/.claude-plugin/plugin.json` (manifest); `/plugin marketplace add owner/repo`, then install |
| **Codex (OpenAI CLI)** | Repo `.agents/skills/` (scanned from CWD up to repo root), user `~/.agents/skills/`, admin `/etc/codex/skills/` | Plugin manifest `.codex-plugin/plugin.json`, marketplace pointer `.agents/plugins/marketplace.json`; `codex plugin marketplace add owner/repo` (plugin marketplace since CLI v0.117.0, March 2026); Codex also reads a Claude-format marketplace as fallback |
| **ChatGPT** | Uploaded skill folders (Skills tab / Plugin Directory) | Upload the skill folder on an eligible plan; skills GA 9 July 2026. **Uncertain:** OpenAI's help centre lists Business/Enterprise/Healthcare/Edu only, while its pricing page lists "Skills beta" on Free/Go/Plus/Pro — the two pages conflict; check the account's Skills tab before promising access. Custom GPTs retire 11 Dec 2026 |
| **Gemini CLI** | Extension `skills/` dir; workspace `.gemini/skills/` or `.agents/skills/`; user `~/.gemini/skills/` or `~/.agents/skills/` | Extension = dir with `gemini-extension.json` at root; `gemini extensions install https://github.com/owner/repo [--ref v1.2.0]`; gallery auto-indexes public repos tagged `gemini-cli-extension`. **Note:** free/Google AI Pro/Ultra users were moved to Antigravity CLI on 18 June 2026; Gemini CLI continues for paid API keys and Code Assist Standard/Enterprise |
| **Antigravity (Google)** | IDE: workspace `.agents/skills/<name>/SKILL.md`, global `~/.gemini/config/skills/`; CLI: workspace `.agents/skills/`, global `~/.gemini/antigravity-cli/skills/` | Same `SKILL.md` files; rules live in `AGENTS.md`/`GEMINI.md` or `.agents/rules/` (12,000-char cap per rules file, per Antigravity docs). Legacy `.agents/workflows/` stopped working 19 Oct 2026 — migrate to skills |
| **Muse (Meta)** | **No documented install flow for the personal Muse app** (as of Sept–Oct 2026) | Practical route: open the repo's `SKILL.md`, paste it into chat, ask Muse to use/remember it (reported working; Muse may offer to save it as a reusable skill). **Muse Code** (dev agent) is the exception: reads `~/.agents/skills/` and `~/.claude/skills/` |
| **Generic installers** | Any host above | `npx skills add owner/repo` (vercel-labs/skills) and `gh skill install owner/repo` (GitHub CLI 2.90+) discover `SKILL.md` folders straight from GitHub — no clone, no marketplace |

Sources: Claude/Codex paths and marketplaces — https://github.com/gitguardian/agent-skills/blob/HEAD/docs/maintainers/distribution.md, https://www.skillsboard.sh/codex-skills, https://github.com/wshobson/agents/blob/main/docs/harnesses.md (index); ChatGPT — https://getcontexta.ai/guides/chatgpt-skills, https://swapbiswas.com/blog/chatgpt-skills/, https://kipt.me/guides/chatgpt-skills (index); Gemini CLI — https://github.com/hiivmind/skill-portability/blob/HEAD/docs/platforms/gemini-cli.md, https://kipt.me/guides/gemini-cli (index); Antigravity — https://datalakehousehub.com/blog/2026-03-context-management-google-antigravity/, https://thepromptshelf.dev/blog/google-antigravity-agents-md-rules-guide-2026/, https://www.professorgpt.ai/en/learn/gemini-cli-skills (index); Muse — https://www.aiagentslibrary.com/blog/meta-muse-skills/, https://github.com/aicodedecode/awesome-muse-skills/blob/HEAD/README.md (index).

### 2.3 Recommended single portable repo layout

One skill folder per skill (or one skill per system module), with per-platform manifests pointing at the same content — do not fork the text per host (the google/elephant-goldfish-model repo is the exemplar: shared `skills/` + `agents/` + `resources/`, thin per-harness manifests).

```
flick-consistency/
├── README.md                  # install commands for every platform
├── AGENTS.md                  # standing instructions (Claude Code, Codex, Antigravity read this)
├── CLAUDE.md                  # optional Claude-specific pointer (Claude Code prefers CLAUDE.md over AGENTS.md)
├── GEMINI.md                  # same content pointer for Gemini CLI / Antigravity
├── skills/
│   └── flick-consistency/
│       ├── SKILL.md           # required: name + description frontmatter + instructions
│       ├── scripts/           # optional helpers
│       ├── references/        # character registry, style bible, QC checklists, etc.
│       └── assets/            # templates (episode register, prompt blocks)
├── .agents/
│   ├── skills/                # symlink or copy of skills/ — the neutral dir Codex, Gemini CLI, Antigravity CLI all read
│   └── plugins/
│       └── marketplace.json   # Codex marketplace pointer
├── .claude-plugin/
│   └── marketplace.json       # Claude Code marketplace registry
├── plugins/flick-consistency/
│   ├── .claude-plugin/plugin.json   # Claude plugin manifest
│   └── .codex-plugin/plugin.json    # Codex plugin manifest (skills: ./skills/)
├── gemini-extension.json      # Gemini CLI extension manifest (name must match dir name)
├── .cursor-plugin/plugin.json # optional: Cursor plugin manifest (same pattern as revid-skills)
├── skills.json                # optional machine-readable skill index (used by some catalogues)
└── LICENSE (MIT/Apache-2.0)
```

Key points: keep `SKILL.md` under 500 lines and frontmatter strictly standard; ship an install section in the README with the six one-liners (`npx skills add`, `gh skill install`, Claude `/plugin marketplace add`, `codex plugin marketplace add`, `gemini extensions install`, Muse paste-into-chat); tag GitHub releases so `--ref vX.Y.Z` installs pin a version; validate with the canonical `skills-ref` validator from agentskills/agentskills and `npx skills add` in CI.

---

## 3. Publishing an AI-animated children's series on YouTube in 2026 (brief)

**Disclosure.** YouTube requires disclosure (the "altered content" / AI-use setting → "Made with AI" label) for **realistic** AI content — a real person appearing to say/do something they didn't, altered footage of a real event/place, a realistic scene that never happened, and AI-generated music. **Clearly unrealistic / cartoon animation is exempt** — so a stylised Bengali cartoon series usually needs no AI label, but disclose anyway if any shot is photorealistic or uses AI music. Disclosure does not limit audience or monetisation eligibility, per YouTube. **Uncertain:** whether YouTube will extend labels to YouTube Kids — as of Oct 2026 no Kids AI label existed.

**Made for Kids / COPPA.** Every video and the channel must be labelled Made for Kids or not; it is the creator's legal responsibility (COPPA, US FTC). COPPA civil penalties up to **$53,088 per violation**; Disney paid a **$10M** penalty in Sept 2025 for mislabelling. Made-for-Kids videos lose: personalized ads, comments, notification bell, cards and end screens, autoplay on home, miniplayer, save/Watch Later, channel memberships, merch/ticketing, live chat, Super Chat/Stickers, watermarks, donate button. YouTube's own ML can override your setting — do not rely on it.

**Monetisation.** YPP thresholds: **1,000 subscribers + 4,000 public watch hours (12 months)** or **1,000 subs + 10M Shorts views (90 days)**. Made-for-Kids videos can be monetised but only with non-personalized ads, so revenue per view is lower. Two 2025–26 policy traps for AI kids channels: (a) the **"inauthentic content"** policy (renamed from "repetitious content" 15 July 2025) excludes AI content made from generic templates that looks mass-produced — July 2026 policies require videos to be "materially varied"; (b) the spam policy lists "automated or synthetic mass-production". After a Feb 2026 NYT investigation, YouTube removed five channels from YPP. YouTube's **quality principles** also gate monetisation and YouTube Kids inclusion: low-quality = heavily promotional, encouraging negative behaviour, deceptively educational, hard to follow, sensational/misleading, or strange use of children's characters; a channel focused on low-quality kids content can be suspended from YPP. Since March 2026, videos with young-looking characters in distress can't earn ad revenue (**secondary source — verify**).

**Caution — Google's under-18 clause (uncertain, verify in Google's terms):** Google Cloud Service Specific Terms §20(d) reportedly bars using Google Generative AI services (Veo, Lyria, image models) in a service directed at or likely accessed by under-18s. If the pipeline uses Google video/music models for a kids' series, check the current terms first.

**Practical publishing checklist (per episode):**
1. Title: describes exactly what's inside, in parents' search words; no keyword stuffing, no ALL CAPS, no famous-character names, no lesson promised that the episode doesn't teach.
2. Thumbnail: a real frame/moment from the episode, calm colours, one friendly character + 2–3 words; no shocked faces, red arrows, fake danger or exaggerated emotion.
3. Description: parent-friendly, what the episode teaches, episode/series links; tags for discovery, not manipulation.
4. Subtitles: upload Bengali captions (+ English) — do not rely on auto-captions for Bengali.
5. Audience: set Made for Kids on the video (and channel default); set the AI-use disclosure toggle if any realistic AI content/music is used.
6. Remember end screens/cards don't work on Made-for-Kids videos — put the "next episode" cue inside the video itself.
7. Quality gate before upload: clear story with a resolution, gentle pacing, no scary/distressing imagery, no heavy promotion; keep episodes ~3–8 minutes (per creator guides).
8. Publish consistently and review retention per episode — that is the feedback loop (comments are off).

Sources: https://clipytoons.com/guides/youtube-monetization-ai-kids-content, https://www.vidpal.ai/blog/how-to-make-kids-videos-with-ai-2026, https://channelterminated.com/channel-types/kids-content/, https://www.goingstellar.ro/research/ai-youtube-channel-for-kids-songs-vs-cartoons/ (index, Sept–Oct 2026 guides summarising YouTube Help — not legal advice); https://air.io/en/academy/5-required-steps-to-get-your-video-content-on-youtube-kids, https://air.io/en/monetization/how-to-monetize-a-kids-youtube-channel-safely-in-2026 (index, AIR Media-Tech, official YouTube partner).

---

## Could not verify

- **Bengali-specific items** (Bengali TTS quality, Bengali auto-caption accuracy on YouTube, Bengali kids-content competition): no sources checked; not covered above.
- **Exact current prices** for generation tools (Kling, Runway, ElevenLabs, etc.): deliberately not quoted — prices change and no pricing pages were checked.
- **ChatGPT Skills plan availability**: OpenAI's own pages conflict (see §2.2).
- **Google under-18 clause** and the **March 2026 "characters in distress" demonetisation** rule: reported by secondary sources only; verify against Google's terms / YouTube Help before building on them.
- **Meta Muse skill install**: no official flow found as of Oct 2026; the paste-into-chat route is community-reported, not documented by Meta.
- All findings are **index-level** (search-result text), not live-page reads; vendor docs (agentskills.io spec, YouTube Help) should be re-checked live before the repo's README quotes them.

## Sources

- Notes: `notes/skills-platforms.md`, `notes/pipeline-youtube.md` (URLs + read date 2026-11-12).
- Key URLs (verbatim): https://agentscamp.com/guides/skills/agent-skills-open-standard · https://app.thecompanion.sh/blog/what-is-skill-md · https://www.aitoolspro.tech/blog/how-to-make-ai-video-with-consistent-characters-2026 · https://github.com/hoodini/ai-agents-skills/blob/HEAD/skills/director/references/16-ai-character-consistency.md · https://github.com/neversight/learn-skills.dev/blob/HEAD/data/skills-md/mckruz/comfyui-expert/comfyui-character-gen/SKILL.md · https://magichour.ai/blog/ai-video-generation-tools-for-creators-and-studios · https://www.alternateaistudio.com/blog/ai-microdrama-production-cost · https://github.com/gitguardian/agent-skills/blob/HEAD/docs/maintainers/distribution.md · https://www.skillsboard.sh/codex-skills · https://github.com/wshobson/agents/blob/main/docs/harnesses.md · https://getcontexta.ai/guides/chatgpt-skills · https://swapbiswas.com/blog/chatgpt-skills/ · https://kipt.me/guides/chatgpt-skills · https://github.com/hiivmind/skill-portability/blob/HEAD/docs/platforms/gemini-cli.md · https://kipt.me/guides/gemini-cli · https://datalakehousehub.com/blog/2026-03-context-management-google-antigravity/ · https://thepromptshelf.dev/blog/google-antigravity-agents-md-rules-guide-2026/ · https://www.professorgpt.ai/en/learn/gemini-cli-skills · https://www.aiagentslibrary.com/blog/meta-muse-skills/ · https://clipytoons.com/guides/youtube-monetization-ai-kids-content · https://www.vidpal.ai/blog/how-to-make-kids-videos-with-ai-2026 · https://channelterminated.com/channel-types/kids-content/ · https://www.goingstellar.ro/research/ai-youtube-channel-for-kids-songs-vs-cartoons/ · https://air.io/en/academy/5-required-steps-to-get-your-video-content-on-youtube-kids
