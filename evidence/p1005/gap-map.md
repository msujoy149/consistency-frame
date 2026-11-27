# CF-WO-P1-005 — implementation gap map

Preflight: PR #5 source HEAD `c7e3d346355d4a3050cc9d47359f47b9e85da388`
(Open, Draft, unmerged; base `feat/cf-p1-003-script-to-performance-runtime`
at `b32a4df`; 7 commits +16,994/-191, 56 files) verified live 2026-11-27.
Local branch HEAD `dba00ec`, tree hash `6723be02...` (equals the remote
`c7e3d346` tree), tree clean. FFmpeg 8.1.2 + ffprobe 8.1.2 present.
Master Prompt v4.20 md5 `d9785e89...`, 1,332 lines, untouched.

Every claim below cites the audited file. Nothing in P1-004 is recreated.

## What already exists (do not rebuild)

- **Planning:** `runtime/task_compiler.py` (1,971 lines) compiles
  deterministic provider-neutral task packets; `match_provider_for_task`
  (line 483) matches only VERIFIED/EXERCISED providers on evidenced
  capabilities, commercial jobs exclude unapproved providers, NOT_TESTED
  and FAILED never match. `TASK_PROVIDER_REQUIREMENTS` (line 84) maps
  14 task types to provider types/operations. `compile_task_package`
  (line 677) emits packets whose `provider_status` is only
  `not-executed` / `handed-off` / `unavailable-no-verified-provider`
  (`schemas/task-packet.json`) — a packet never claims execution.
- **Orchestration:** `runtime/production_orchestrator.py` (1,867 lines)
  — job state machine, G1–G6 gates, `record_execution_result` (line
  1766, records `{provider_id, outcome, output_ref?, notes?}` with
  outcome succeeded/failed/not-executed against a compiled package),
  `build_qc_correction_tasks` (line 1820, localized repair only),
  `validate_job` (line 745, checks known fields + recomputed
  `job_hash`; unknown extra fields are ignored, so execution records
  can ride on the job without a job-schema change).
- **Persistence:** `runtime/production_store.py` (467 lines) —
  `save_production_job` (line 303), `save_production_checkpoint`
  (line 374), `resume_production_job` (line 395, rebinds a NEW session,
  refuses DELIVERED, never auto-resumes paid/external tasks). The
  store persists the job dict; execution state rides on the job —
  no second job database is needed or wanted.
- **Timeline contract:** `schemas/timeline-manifest.json` (v2.5,
  tracks/clips with media paths relative-only) +
  `scripts/timeline_policy.py` (`validate_timeline_structural` line
  421, `validate_timeline_cross_references` line 449, strict by
  default on v2.5). Nothing populates a manifest from execution
  output yet (see G-G).
- **Registries:** `registry/providers.json` (13 records, compiled by
  `scripts/generate-registries.py:build_providers` from the
  `providers:` section of
  `architecture/COMPANION_CAPABILITY_REGISTRY.yaml:300`);
  `registry/adapters.json` (15 records, compiled from the static
  `ADAPTERS` tuple in `generate-registries.py:382`).
  `schemas/provider-capability.json` is `additionalProperties: false`
  with a fixed property set — it already carries optional
  `duration_limits` / `resolution_limits`, but no documentation URL,
  API version, async/cancellation/retrieval or charge-behaviour
  fields; extending it is an additive schema change (see G-F).
- **Companions present:** `components/voicestudio` (backend
  `POST /generate` in `api/routers/generation.py:1886`,
  `GET /health` in `backend/main.py:2185`,
  `GET /generate/budget` at `generation.py:1837`; OmniVoice engine
  in `engines/omnivoice_gguf/`) and `components/openmontage`
  (`.venv` present, `make preflight` runs tool-registry discovery,
  `render_demo.py` renders Remotion demos only; node v24.22.1
  available). OpenTimelineIO is NOT installed (`import
  opentimelineio` fails).

## Gaps

### G-A — No execution adapter interface or result contract (WO §3)
No canonical adapter exists. Nothing declares capabilities, runs
preflight, translates a packet, submits, polls, cancels, retrieves,
verifies output, classifies failure, retries, or records provenance
in one place. `record_execution_result` records facts after the
fact; it cannot drive execution. **Build:** `runtime/media_execution.py`
— `MediaAdapter` base interface + canonical execution result +
execution state machine (WO §4 states) + idempotency keys +
submission-uncertainty handling (NEEDS_USER_ACTION, never
auto-resubmit) + failure classification vocabulary.

### G-B — FFmpeg has no runtime adapter (WO §5A)
Binary present (8.1.2) and provider record `provider-ffmpeg` is
conformance EXERCISED (demo renders 2026-11-12/13) with
`commercial_use_approved: true`, but `adapter-ffmpeg` is conformance
NOT_TESTED ("Binary presence on a machine is not a conformance
test; no P0 test invokes it") and no runtime code invokes ffmpeg at
all. **Build:** `FFmpegAdapter` — ffprobe probing, safe-argv
transcode/assembly/export, SHA-256, integrity verification, path +
symlink containment, timeouts, size limits, recorded binary version.
No creative-editing claims.

### G-C — VoiceStudio has no Brain-side wrapper (WO §5B)
Backend exposes `POST /generate` (multipart form: text, voice
profile/ref audio, language, seed, engine) and `GET /health`
(`{"status": "ok", "device", "engine", "version"}` or 503 while
starting). No adapter verifies service/engine/model/language/
voice-profile/consent/commercial eligibility before a task, and no
code calls it. Provider record `provider-voicestudio-omnivoice` is
EXERCISED (non-commercial only; CC-BY-NC weights). **Build:**
`VoiceStudioAdapter` — loopback-only HTTP, `/health` preflight,
pre-submit checks incl. commercial refusal for OmniVoice, mocked
HTTP in tests, one real generation attempt in this environment as
evidence (backend started only for the attempt, stopped after).

### G-D — OpenMontage has no execution adapter (WO §5C)
Component present; `make preflight` is runnable; `render_demo.py`
is Remotion-demo-only. No adapter prepares a real pipeline request
from validated artifacts, submits a render, or verifies output
files. Provider record `provider-openmontage-assembly` is
NOT_TESTED ("no production assembly run recorded in this account").
**Build:** thin `OpenMontageAdapter` — component-checkout
verification (origin + HEAD pin, P0-014 pattern), `make preflight`
as preflight, pipeline-request preparation from validated artifacts
+ timeline manifest, output-file verification via ffprobe. Do NOT
claim EXERCISED until a real output is generated and independently
validated; a real demo render is attempted once, time-boxed.

### G-E — OpenTimelineIO adds no value unless installed (WO §5D)
Not installed; the canonical timeline manifest already covers
editorial interchange (tracks/clips/timing/cross-references).
**Build:** probe-only record — the runtime reports OTIO as
unavailable and refuses its use fail-closed; no adapter, no
mandatory dependency. Documented, not faked.

### G-F — External providers are documented-only; two are dead (WO §6)
All 9 external records are conformance NOT_TESTED with
`adapter_version: ""` and evidence "documented-only ... no live
paid call made". No HTTP adapter code, no credential handling, no
mock adapters exist. Current official docs (audited 2026-11-27,
browser only, no API calls) change the plan:
- **Sora is SHUT DOWN** (OpenAI, 2026-09-24; "no replacement API").
  Do not build an adapter. Record `provider-sora-video` as FAILED
  with the shutdown evidence — FAILED providers are never matched.
- **gpt-image-1 is SHUT DOWN** (2026-10-23). Current family is GPT
  Image 1.5/2/2.5/2.6; update `provider-openai-image` to the live
  models (sync, base64 out, up to 10 reference images on edit).
- Gemini image (Nano Banana, Interactions API, sync, base64 out, up
  to 14 reference images, 4 character max on 2.1); fal.ai image
  (per-endpoint, sync + queue, cancellation YES, fal.media URLs
  ≥7 days, 500+ never charged); Veo 3.1 (async long-running op, up
  to 3 reference images Std/Fast, 8 s max, cancellation
  UNCONFIRMED, preview IDs on Gemini API / GA on Vertex); Kling
  (async task_id polling, callback_url, cancellation UNCONFIRMED,
  prepaid units, failed tasks not charged, commercial terms
  UNCONFIRMED); LTX-2.5 (V2 async only, 202 + job ID, 6–20 s, one
  first-frame image, audio-to-video lip-sync, cancellation +
  hosted-API licence UNCONFIRMED); ElevenLabs TTS (sync, `xi-api-key`
  header, free tier 10k credits/mo non-commercial, paid = commercial
  licence, under-18 clause relevant to kids content); Lyria 3.5
  (sync, base64 MP3, $0.08/song including failed takes).
- **Build:** `HttpProviderAdapter` (mockable transport, credential
  read only from an allow-listed env var, never logged) + one
  declarative spec per live provider (endpoint, auth, async
  pattern, cancellation, retrieval, charge behaviour, licensing,
  privacy). Extend `schemas/provider-capability.json` additively
  with optional `documentation_url`, `api_version`,
  `async_behaviour`, `cancellation_support`, `output_retrieval`,
  `charge_behaviour`, `aspect_ratios`, `audio_support`,
  `character_reference_limits`; update the YAML records and
  regenerate. No live paid call in this round; mock-based tests
  only; providers stay NOT_TESTED (Sora FAILED).

### G-G — No timeline delivery from real artifacts (WO §7)
Schema + policy exist; no code builds a manifest from validated
execution output. **Build:** `runtime/timeline_delivery.py` —
artifact metadata capture (project/job/scene/shot/character/voice/
task/execution/provider/model, asset location, SHA-256, size,
format, resolution, fps, duration, audio streams, approved
reference dependencies, QC status, version, provenance) from
SUCCEEDED + validated artifacts only; structural + cross-reference
validation via `scripts/timeline_policy.py`; fabricated paths and
placeholder outputs refused. A planned task is never an artifact.

### G-H — No execution orchestration pipeline (WO §8)
The orchestrator plans and gates; nothing runs the 18-step
pipeline (select → authorize → prepare → submit → track →
retrieve → verify → register → technical QC → semantic-QC
handoff → localized repair → state update → timeline manifest →
G6 checks). **Build:** `runtime/execution_orchestrator.py` as
discrete step functions + a fail-closed driver over the existing
orchestrator, preserving dialogue/character/voice locks,
short/long profiles, and localized repair only (reuse
`build_qc_correction_tasks`).

### G-I — No semantic-QC handoff (WO §9)
QC severity (Critical/Major/Minor/Polish) exists in the addendum
docs, but no handoff record exists and G6 has no execution
evidence wired to it. **Build:** technical QC (file readability,
corrupt frames, fps, resolution, codec, duration, audio presence,
peak levels, technical A/V sync, missing/invalid artifacts) +
`human-review handoff` record for semantic checks; G6 PASS never
follows from ffprobe readability alone.

### G-J — No execution persistence or in-flight recovery (WO §4)
`job["execution_results"]` is append-only with three outcomes; no
execution IDs, no idempotency keys, no state history, no resume of
in-flight async jobs. **Build:** execution records ride on the job
(`job["executions"]`), persisted by the existing store; resume
revalidates in-flight records and never auto-resumes paid/external
tasks (the store's existing rule).

### G-K — docs/06-installation.md update blocked (WO §12)
A system security notice blocks editing/opening that file in an
editor (hit in P1-004, recorded as an open limitation). Attempt
the read/audit; if the notice blocks the edit, do not force it:
record the intended P1-005 update text in the corrections doc and
carry it as an open limitation.

### G-L — Windows CI lacks the identity + store suites (WO §14)
`.github/workflows/p0-ci.yml` `windows-compat` runs 5 suites
(local session, session auth, private voice security, skill
router, S2P). Identity (`tests/test_identity_resolution.py`,
2,869 lines) and store (`tests/test_production_store.py`, 369
lines) are not run there. Audit found both suites already
Windows-safe in structure (symlink tests catch OSError;
POSIX mode checks gated on `os.name == "posix"`). **Build:**
add the two steps; the workflow file cannot be pushed via the
GitHub API (403) — prepare locally, verify, and FLAG to the
parent (website upload).

### G-M — Manifest scope grows (WO §13, §15)
New runtime modules, schemas, tests, docs and evidence enter the
manifest. `MANIFEST_EXPECTED_COUNT` (216, `tests/test_reports.py:120`)
must be updated with a recorded reason, and the new files must be
manifest-listed by the final regen.

## Out of scope (explicitly not built)
- No redesign of P1-004 planning, identity or voice resolution.
- No new skill (15 stays 15) — the audit found no technique gap
  that needs one; execution is runtime/adapter work over the
  existing skills.
- No LLM, no rendering engine, no server, no API backend, no cloud
  database (Brain Amendment v2.4).
- No live paid provider call; no live provider conformance run
  (no credentials, no user authorization in this round).
- No companion internals modified (VoiceStudio/OpenMontage read-only).
