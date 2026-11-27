# Media execution runtime (CF-WO-P1-005)

The media execution runtime is the seventh production runtime
component of Consistency Frame, built on the P1-001 trusted local
session, the P1-004 production orchestrator and task compiler, the
P1-004-R1 persistent production store, and the P1-004-R1-F1
unified identity workflow. It answers the question the P1-004
runtime deliberately left open: *a task packet is compiled — now
what actually runs it, and how do we know the output is real?*

P1-004 compiled deterministic, provider-neutral task packets and
matched them to providers on evidenced capabilities only, but it
never executed anything: a packet's `provider_status` stayed
`not-executed`, `handed-off`, or `unavailable-no-verified-provider`,
and `record_execution_result` recorded only facts handed to it.
This runtime supplies the execution itself — a canonical adapter
interface, a deterministic state machine, local and external
provider adapters, timeline delivery from validated artifacts, and
a human-review handoff for the semantic checks no tool can make —
without duplicating anything that already exists: execution state
rides on the production job record (`job["executions"]`) and is
persisted by the existing production store. There is no second job
database, and a compiled packet is still never proof of execution.

## What it guarantees

1. **One adapter interface, one result contract.**
   `runtime/media_execution.py` defines `MediaAdapter`
   (`capabilities` / `preflight` / `translate` / `prepare` /
   `submit` / `poll` / `cancel` / `retrieve` / `verify_output`)
   and the submit/poll result shape
   (`{provider_job_id, completed, output, failure}`). Every method
   fails closed with `MediaExecutionError` and never invents a
   result; an operation an adapter does not support raises naming
   the operation. `submit` returns a synchronous completion or an
   async provider job id; an uncertain submission must raise with
   code `submission-uncertain`.
2. **A deterministic state machine.** Twelve states:
   `PLANNED`, `WAITING_FOR_AUTHORIZATION`, `READY`, `SUBMITTED`,
   `RUNNING`, `RETRIEVING`, `VALIDATING_OUTPUT`, `SUCCEEDED`,
   `FAILED`, `CANCELLED`, `NEEDS_USER_ACTION`, `BLOCKED`. Every
   transition is explicit, reasoned, and recorded in the history
   (no timestamps, so the job hash stays deterministic).
   `SUCCEEDED` is reachable only from `VALIDATING_OUTPUT` and only
   with a validated output artifact; `FAILED` always carries a
   failure classification from the fixed vocabulary
   (`provider-timeout`, `submission-uncertain`, `malformed-output`,
   `hash-mismatch`, `cancelled-by-user`, `cancelled-by-provider`,
   `authorization-denied`, `provider-error`, `validation-failed`,
   `local-tool-error`, `credential-missing`,
   `service-unavailable`); terminal records never transition.
   `BLOCKED` remembers the previous state and resumes to it.
3. **Stable identity, no double charge.** An execution id is
   `exec-` plus the first 24 hex chars of the idempotency key, and
   the key is the SHA-256 of
   `job_id|task_id|provider_id|packet_hash|attempt`. The same
   attempt is never created twice; a retry is an explicit new
   attempt (only for a retryable failure or a resolved
   `NEEDS_USER_ACTION`), linked from the old record via
   `superseded_by`. An uncertain submission moves the execution to
   `NEEDS_USER_ACTION` and is never auto-resubmitted — a network
   cut must not silently cause a second paid generation.
4. **Authorization and identity locks are enforced, not assumed.**
   `run_execution_pipeline` matches providers with the P1-004 rule
   (VERIFIED then EXERCISED; NOT_TESTED and FAILED never match;
   commercial jobs exclude unapproved providers), checks the
   per-task explicit user authorizations (`{task_id: True}` —
   nothing is authorized implicitly), and checks every packet's
   bindings against the frozen identity snapshot before submitting.
   A mismatch blocks the execution; nothing is silently re-bound.
   One task failing never aborts the others.
5. **Only a genuine adapter result can succeed.** `submit_execution`
   drives a synchronous completion to `VALIDATING_OUTPUT` and an
   async acceptance to `RUNNING` (polled up to `max_polls`).
   `verify_execution_output` independently re-verifies the artifact
   (file existence, SHA-256, byte count, ffprobe duration agreement)
   and is the only path to `SUCCEEDED`; a hash mismatch fails with
   `hash-mismatch`, any other verification failure with
   `validation-failed`. Terminal executions are mirrored into the
   P1-004 `execution_results` via `record_execution_result`, so the
   orchestrator's QC loop sees real outcomes.
6. **Technical QC is deterministic; semantic QC is human.**
   `run_technical_qc` checks only what a tool can decide (file
   readability, corrupt frames, frame rate, resolution, codec,
   duration, audio presence, peak levels, technical A/V sync),
   with severities Critical / Major / Minor / Polish; the verdict
   is `pass` only with no Critical or Major defect. A passing
   technical report is NOT a G6 PASS. Semantic checks (character
   continuity, face drift, lip-sync quality, physical realism,
   creative intent) go through a human-review handoff
   (`schemas/human-review-handoff.json`): it is never
   auto-approved, and only a named human reviewer may approve or
   reject it — `automated` is refused. `evaluate_delivery_gate`
   checks the G6 evidence only (valid manifest, passing technical
   QC, human-approved handoff); the gate itself is evaluated by
   `production_orchestrator.evaluate_production_gate`.
7. **Timeline delivery admits only validated artifacts.**
   `runtime/timeline_delivery.py` builds the delivery manifest
   from SUCCEEDED executions only, re-verifying every artifact
   against the real file under the delivery root. No fabricated
   path, placeholder output, or unvalidated file ever enters the
   manifest. The manifest is the canonical v2.5 editor-neutral
   format (`editor_neutral_v1`), schema-valid and structurally
   valid; the strict cross-reference check runs only when the
   caller supplies both requester ids. The manifest resolution
   comes from the first delivered video artifact when probed,
   otherwise 1920x1080 — the production format profile carries no
   media geometry.
8. **No secrets, no private media, no mandatory providers.**
   Provider credentials come only from allow-listed environment
   variables (`resolve_provider_secret`); no key appears in Git,
   logs, reports, or packets, and error text is redacted. Private
   character images, voice references, user recordings and
   generated private media never enter the public repo, source
   ZIPs, or public reports. External providers are never mandatory
   for basic use: install the Brain and use planning and handoff
   features with no paid API keys at all.

## Components

- `runtime/media_execution.py` — the state machine, the record
  validators, the idempotency keys, and the `MediaAdapter` base
  interface. Schema: `schemas/execution-record.json`.
- `runtime/media_adapters.py` — the local adapters (FFmpeg,
  VoiceStudio, OpenMontage), the OpenTimelineIO probe, the
  spec-driven HTTP provider adapter, the eight live provider
  specs, and the `get_adapter` factory. See
  `docs/runtime/PROVIDER_ADAPTERS.md`.
- `runtime/execution_orchestrator.py` — provider selection,
  authorization and identity-lock checks, submit/poll/verify,
  technical QC, the semantic handoff, the G6 evidence check, and
  the `run_execution_pipeline` driver.
- `runtime/timeline_delivery.py` — artifact re-verification, the
  minimal registry built from a job, and delivery-manifest
  construction. Schema: `schemas/timeline-manifest.json`;
  validation: `scripts/timeline_policy.py`.
- `schemas/human-review-handoff.json` — the semantic QC handoff.

## Local adapters

- **FFmpeg / ffprobe** (`provider-ffmpeg`, EXERCISED): technical
  operations only — probe, transcode, assembly. Safe argument
  arrays, path/symlink containment inside the workspace root,
  timeouts, a 2 GiB output size limit, and the recorded binary
  version. Conformance: `tests/test_ffmpeg_adapter.py`
  (`CF-P1-005-FFMPEG`).
- **VoiceStudio** (`provider-voicestudio-omnivoice`, EXERCISED,
  non-commercial only): a safe wrapper around the bundled backend
  (`GET /health`, `POST /generate` multipart). It never starts the
  backend and never modifies VoiceStudio internals. Preflight
  verifies the service, the engine (it pins `engine=omnivoice`
  on submit; a cold backend reports no engine until one is
  selected or used), the language (evidenced: bn, en, hi), the
  voice-profile identity against the authorized context, the
  dialogue line id, and voice consent — and refuses commercial /
  monetized production outright, because the default OmniVoice
  weights are CC-BY-NC. A different model is eligible only after
  its exact weights, tokenizer, model terms and dependencies are
  independently cleared.
- **OpenMontage** (`provider-openmontage-assembly`, EXERCISED for
  the demo-render entry only): a thin wrapper around the bundled
  checkout (origin + HEAD pin verified, the P0-014 pattern).
  `submit` runs only the verified render entry (`render_demo.py`
  for a named demo composition); a production pipeline render has
  no verified entry and fails closed. Production assembly stays
  NOT exercised until a real production output is generated and
  independently validated.
- **OpenTimelineIO**: probed, not installed, no adapter built.
  The canonical timeline manifest already covers editorial
  interchange, so OTIO is never a mandatory dependency.

## External providers

Eight live providers have spec-driven HTTP adapters (see
`docs/runtime/PROVIDER_ADAPTERS.md`): OpenAI image, Gemini image,
fal.ai image, Veo video, Kling video, LTX video, ElevenLabs voice,
Lyria music. Sora has no adapter: the service was shut down
2026-09-24. All eight are conformance NOT_TESTED — no live paid
call has been made, and none is made without explicit user
authorization for that run. Adapter tests use mock transports.

## Tests

- `tests/test_media_execution.py` (`CF-P1-005-EXECUTION`, 85
  checks): record/failure/artifact validation, the schemas, the
  state machine (create, transitions, resume, retry), the
  orchestrator (sync/async/uncertain/failure submit, poll,
  hash-mismatch verify, authorization, identity lock), the
  end-to-end pipeline (short-form 1 task, long-form 3 tasks,
  mixed 1 good + 1 failing task, persistent recovery through the
  production store), technical QC, the semantic handoff, and the
  G6 evidence check.
- `tests/test_ffmpeg_adapter.py` (`CF-P1-005-FFMPEG`, 28 checks):
  real local execution on deterministic lavfi media.
- `tests/test_media_adapters.py` (`CF-P1-005-ADAPTERS`, 56
  checks): VoiceStudio against a mock backend, OpenMontage
  checkout verification and fail-closed submit, the OTIO probe,
  credential handling and redaction, the HTTP adapter over mock
  transports (sync image, async video submit + poll, cancel),
  and the factory (Sora refused).
- `tests/test_timeline_delivery.py` (`CF-P1-005-DELIVERY`, 26
  checks): manifest from validated artifacts, rejection of
  fabricated/missing/mismatched paths, the strict cross-reference
  check with a real requester, and the registry built from a job.

## Known gaps (P1-005)

- The VoiceStudio adapter does not forward the voice binding's
  vocal characteristics (pitch, pace, emotional delivery, pauses)
  or an `instruct` string to the backend; the 2026-11-13
  instruct+seed test pattern is reproducible only by a direct
  backend call, not through the adapter. Forwarding needs a
  voice-binding schema decision first.
- No video provider is VERIFIED or EXERCISED, and no external
  provider has had a live conformance run (no credentials, no
  authorization in this round). Open items per provider are in
  `docs/runtime/PROVIDER_ADAPTERS.md` § "Open items".
- The handbook PDF behind the P1-003 Addendum-01 still has not
  arrived; its cross-check stays open. All hosts except Muse are
  NOT_TESTED. Workflows are SCHEMA_DEFINED. The media factory is
  not finished.
