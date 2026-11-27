# CF-WO-P1-005 Corrections Record

Real Media Execution Runtime, Provider Adapters & Timeline
Delivery — CF-WO-P1-005, branch
`feat/cf-p1-004-universal-production-brain`, PR #5 (Draft, unmerged).
This record contains no generated values (no manifest SHA, no final
head, no ZIP SHAs): those are printed from the final tree in the
delivery report only.

## 1. Gap map (preflight audit)

The implementation gap map is `evidence/p1005/gap-map.md` (gaps
G-A–G-M). The audit read the ten listed targets plus the FFmpeg,
VoiceStudio and OpenMontage capabilities without changing any
companion internals. Headline findings that shaped the build:

- The P1-004 compiler matches only VERIFIED/EXERCISED providers,
  commercial jobs exclude unapproved providers, and NOT_TESTED /
  FAILED providers never match — the execution runtime reuses that
  rule unchanged instead of inventing its own.
- The P1-004 orchestrator's `record_execution_result` takes
  `{provider_id, outcome, output_ref?, notes?}` and `validate_job`
  ignores unknown extra fields, so execution state rides on the
  job (`job["executions"]`) with no job-schema change and no
  second job database.
- The production store persists the job dict, so execution state
  persists through the existing store.
- The timeline-manifest schema is v2.5 with strict cross-reference
  validation in `scripts/timeline_policy.py`; structural validation
  alone is never authorization.
- `schemas/provider-capability.json` had no documentation, API
  version, async/cancel/retrieval/charge fields — extended
  additively (all new fields optional).

## 2. Test-found defects (fixed in this round)

Six defects in the P1-005 code itself were found by writing the
tests and fixed before delivery. None of them weakens a previous
round; all are pinned by the new suites.

### 2.1 `load_schema` called without the `.json` extension

`timeline_delivery.build_delivery_manifest` and
`execution_orchestrator.evaluate_delivery_gate` called
`task_compiler.load_schema("timeline-manifest")`. `load_schema`
takes a filename, so both calls raised `FileNotFoundError` at
runtime. Fixed to `"timeline-manifest.json"`.

### 2.2 `validate_instance` called with the wrong arity

Both call sites above also called
`task_compiler.validate_instance(schema, value, path)` and used
the return value as the error list. `validate_instance` takes
four arguments `(schema, value, path, errors)` and returns
`None`. Both call sites now use `task_compiler.schema_errors`,
the same helper every other caller uses.

### 2.3 `VALIDATING_OUTPUT` dropped the output artifact

`transition_execution` stored `output` only on the SUCCEEDED
branch, so the `VALIDATING_OUTPUT` transition silently dropped
the artifact — and `verify_execution_output` then had nothing to
verify. `output`, when supplied, is now validated as an artifact
and stored on the record for any transition; SUCCEEDED still
requires it.

### 2.4 `SUCCEEDED` was unreachable

`ALLOWED_TRANSITIONS` had no `SUCCEEDED` entry, so
`ALLOWED_TRANSITIONS.get("SUCCEEDED", ())` was empty and every
`VALIDATING_OUTPUT -> SUCCEEDED` transition was refused before
the SUCCEEDED special-case check ran. Added
`"SUCCEEDED": ("VALIDATING_OUTPUT",)`.

### 2.5 A synchronous completion with a provider job id stalled

`submit_execution` checked `provider_job_id` before `completed`,
so a sync adapter returning both (VoiceStudio returns the
`X-Audio-Id` as its provider job id alongside `completed: True`)
drove the execution to RUNNING, where the next poll failed
because the adapter has no poll. `completed` is now checked
first, and the provider job id is recorded on the RUNNING
transition.

### 2.6 The delivery manifest used schema-invalid defaults

`build_delivery_manifest` took `format`, `aspect_ratio`,
`resolution` and `frame_rate` from the production format
profile — but `validate_format_profile` only allows
`delivery_profile`, `duration_target_seconds` and `chapters`,
so the profile never carries media geometry and the builder
always fell back to its defaults: `format: "video"` (not in the
schema enum — only `editor_neutral_v1` and `otio_candidate`
are) and `resolution: "1920x1080"` (a string; the schema wants
`{width, height}`). Every manifest the builder produced failed
its own schema validation. The builder now always emits
`format: "editor_neutral_v1"` and a resolution object — from the
first delivered video artifact when probed, otherwise
1920x1080 — with a comment explaining why the profile cannot
supply geometry.

### 2.7 ffprobe JSON was truncated by error-text redaction

`_run_argv` applied `_redact` (capped at 2,000 chars) to stdout
and stderr, so ffprobe JSON over 2,000 chars came back truncated
and unparseable (`JSONDecodeError: Unterminated string`). `_redact`
now takes a `limit` (`None` = full output); `_run_argv` returns
full stdout/stderr (secrets and home paths still stripped), and
call sites that embed output in an error message redact + truncate
there instead.

### 2.8 The HTTP adapter did not resolve output paths

`HttpProviderAdapter` had no `verify_output` override, so the
base implementation checked the workspace-relative path against
the process working directory and reported the file missing.
It now resolves under the workspace root first (the same pattern
as the FFmpeg and OpenMontage adapters) and keeps the relative
path in the artifact.

### 2.9 `duration_limits` was a string, the schema wants an object

The registry YAML and the provider specs recorded
`duration_limits` as a descriptive string; the schema defines it
as `{min_seconds?, max_seconds?}` (integers), and the registry
loader rejected the records. All four records (Veo, Kling, LTX,
Lyria) now carry the object form in both places.

### 2.10 A re-render was invisible to the OpenMontage adapter

`OpenMontageAdapter.submit` detected produced files by name-set
difference, so re-rendering the same demo (which overwrites the
same filename) reported "no new output file". It now snapshots
`(mtime_ns, size)` per file and treats a changed file as
produced. Pinned by the real adapter run (§4).

### 2.11 Schema nullability: omit, never explicit null

The two new schemas first declared nullable fields as
`"type": ["string", "null"]` (and `"enum": [..., null]`). The
repo's minimal validator supports single-type only and treats an
explicit null as a type error everywhere, and no existing schema
uses null. The schemas now declare plain types and the runtime
omits absent optional fields (`provider_job_id`,
`previous_state`, `failure`, `output` on execution records;
`decision`, `note` on handoffs) instead of setting them to null.
`transition_execution`, `resume_execution`,
`resolve_semantic_qc_handoff` and `prepare_semantic_qc_handoff`
were changed accordingly.

### 2.12 `registry_from_job` built invalid ownership

Audio assets got `"ownership": {}`, which fails strict
validation (an empty dict is not a valid ownership binding), and
the snapshot's `sharing` was a dict where the ownership contract
wants the string `"none"`. A bound audio asset now carries its
character's snapshot ownership; an unowned asset carries no
ownership key and fails the strict check closed.

### 2.13 The VoiceStudio adapter could never warm a cold backend

On a cold backend `/health` reports `engine: null` until an
engine is selected or used, and the adapter treated that as a
preflight failure — while never sending an engine itself, so it
could never warm the backend on its own. The adapter now pins
`engine=omnivoice` on submit (the engine it serves) and treats
a null engine as "not yet selected"; a named different engine is
still a preflight error.

## 3. Provider audit (2026-11-27)

Current official documentation was audited for all nine external
providers before any adapter code was written for them. Findings
are recorded in the specs (`PROVIDER_SPECS`,
`runtime/media_adapters.py`) and the provider registry.

- **Sora is SHUT DOWN.** OpenAI, 2026-09-24: "The Sora 2 models
  and Videos API were shut down on September 24, 2026 and are no
  longer available. There is no one-to-one replacement API."
  Recorded as FAILED; no adapter exists and none will be built.
  `gpt-image-1` is also shut down (2026-10-23); the current
  OpenAI image family is gpt-image-1.5/2/2.5/2.6.
- **Direct reads:** OpenAI image, Gemini image, fal.ai image, Veo
  video, Lyria music (`documentation_status: official`).
- **Secondary-quoting-official:** Kling video (official docs are
  login/JS-gated), LTX video (direct read not completed),
  ElevenLabs voice (direct fetch blocked here).
- **UNCONFIRMED items** (recorded in the specs and in
  `docs/runtime/PROVIDER_ADAPTERS.md`, to close before any live
  conformance run): current OpenAI image pricing; Gemini pricing
  page direct re-read; Kling docs direct read, commercial terms
  and cancellation; LTX licence, training terms, failed-task
  charging, webhooks and cancellation; ElevenLabs direct read and
  the under-18 clause; fal.ai training-use clause; Veo preview-ID
  deprecation and cancellation.

## 4. Real local execution evidence (2026-11-27)

Full record: `evidence/p1005/local-execution-evidence.md`
(hashes, durations, commands; media bytes are git-ignored and
not committed).

- **VoiceStudio:** backend started once, one Bengali generation
  via `/generate` (instruct `child, female, high pitch`, seed
  11, engine `omnivoice`), HTTP 200, 1.98 s WAV, audio id
  `1faa2e3e`, independently verified (wave probe + SHA-256).
  Backend stopped afterwards; no backend left running.
- **OpenMontage:** `make preflight` passed; demo
  `animated-reel-20s` rendered directly (630 frames) and again
  through `OpenMontageAdapter.submit`; output ffprobe-validated
  (21.056 s, 1920x1080, h264 + aac). Scope is the demo-render
  entry only — production pipeline assembly is NOT exercised.
- **FFmpeg:** real probe/transcode/assembly in
  `tests/test_ffmpeg_adapter.py` and the end-to-end pipeline
  tests, on deterministic lavfi media generated at test time.
- **External providers:** no live call. All eight are
  NOT_TESTED; adapter tests use mock transports only.

## 5. What this round did NOT do

- No live paid external API call, no credentials, no
  authorization for one in this round.
- No video provider VERIFIED or EXERCISED; no external provider
  live conformance run.
- No production OpenMontage assembly run (demo render only).
- No new skill (15 stays 15); no new numbered entries (109/120
  unchanged). The audit found no gap that needs a skill.
- No change to VoiceStudio or OpenMontage internals; no previous
  regression test removed or weakened.
- No Master Prompt change (v4.20 untouched); no "Master Prompt"
  mention in the repo, README, blog or theme.
- No merge of any PR; PR #5 stays Draft/open/unmerged; no P2/P3.
- The handbook PDF behind the P1-003 Addendum-01 still has not
  arrived; its cross-check stays open. All hosts except Muse are
  NOT_TESTED. Workflows are SCHEMA_DEFINED. The media factory is
  not finished.

## 6. Open limitations carried forward

- The VoiceStudio adapter does not forward the voice binding's
  vocal characteristics (pitch, pace, emotional delivery,
  pauses) or an `instruct` string to the backend; the
  2026-11-13 instruct+seed test pattern is reproducible only by
  a direct backend call, not through the adapter. Forwarding
  needs a voice-binding schema decision first.
- `docs/06-installation.md` was updated in this round (the
  P1-004 system-security notice did not block the edit this
  time): a "Media execution (P1-005)" section now covers
  optional providers, credential handling, commercial rules and
  real execution limitations. The P1-004 limitation is closed.
- `.github/workflows/p0-ci.yml` was changed locally (six new
  windows-compat steps: identity resolution, production store,
  and the four P1-005 suites) and CANNOT be pushed via the
  GitHub API (403) — it must go up via the GitHub website, and
  no CI coverage is claimed until an actual run proves it.
- The Cinematic-skill import as an adapted 16th skill is still
  awaiting user approval; the Flick Digital launch film still
  has three approvals pending; the Facebook email retry is still
  awaiting his answer. P1-005 does not change any of these.

## 7. Manifest scope

New tracked files in this round: the four runtime modules
(`runtime/media_execution.py`, `runtime/media_adapters.py`,
`runtime/execution_orchestrator.py`, `runtime/timeline_delivery.py`),
two schemas (`schemas/execution-record.json`,
`schemas/human-review-handoff.json`), four test suites
(`tests/test_media_execution.py`, `tests/test_ffmpeg_adapter.py`,
`tests/test_media_adapters.py`, `tests/test_timeline_delivery.py`),
two runtime docs (`docs/runtime/MEDIA_EXECUTION_RUNTIME.md`,
`docs/runtime/PROVIDER_ADAPTERS.md`), this corrections record,
and three evidence records (`evidence/p1005/gap-map.md`,
`evidence/p1005/local-execution-evidence.md`,
`evidence/p1005/vs-headers.txt`).
`MANIFEST_EXPECTED_COUNT` was updated with the recorded reason
(see the delivery report).

## 8. Parent verification fix (2026-11-27)

The coordinator's handoff claimed `git diff --check` clean; the parent's
independent check found it was not: `evidence/p1005/vs-headers.txt` (the
raw VoiceStudio HTTP response headers) carried CRLF line endings, which
`git diff --check` flags as trailing whitespace on every line, plus a
blank line at end of file. The parent normalized the file to LF endings
with a single trailing newline — header values unchanged, no evidence
altered — and regenerated the reports. The file is a header record, not
media; the audio it evidences is not in the repo.

## 9. R1 — Windows `os.fchmod` defect in the atomic-write helper (2026-11-27)

The first CI run on the P1-005 final head failed both `windows-compat`
jobs (p0-validate passed) at the same step: step 11, the identity
resolution suite, in its end-to-end group at
`store.save_production_job` → `runtime/production_store.py`
`_write_record` → `atomic_write_json` → `scripts/atomic_write.py`
`atomic_write` → `os.fchmod(fd, mode)`, which raised `AttributeError:
module 'os' has no attribute 'fchmod'` on Windows Python 3.10 and 3.12.
The job stopped there, so the production-store step and the four
P1-005 suite steps never ran on Windows.

Root cause: the helper called `os.fchmod` unconditionally. P1-001-R2
had fixed the identical hole in `runtime/local_session.py`
(`_publish_profile_atomic`, capability-checked with `hasattr(os,
"fchmod")`) but explicitly left `scripts/atomic_write.py` untouched,
and the production store — unlike the profile publisher — writes
through this helper. The identity suite only started exercising that
path on Windows in this round, because the identity and store steps
were added to `windows-compat` by P1-005. A repository-wide grep
confirmed this helper was the only remaining unconditional `os.fchmod`
call outside the components.

Fix (one line of behaviour, same pattern as R2): `atomic_write`
applies the mode only when `os.fchmod` exists and skips it on Windows,
where the file inherits the parent directory's ACL behaviour; no POSIX
mode-bit equivalence is claimed there. The module docstring records
the Windows behaviour.

Regression: a new group in `tests/test_production_store.py`
(`CF-P1-005-R1-STORE`, six checks) simulates the Windows absence by
hiding `os.fchmod` (the `test_local_session_runtime.py` pattern) and
verifies: `save_production_job` succeeds and the loaded record
validates; `atomic_write_json` writes exact bytes; a failed
`atomic_write` leaves the target unchanged with no temporary file
behind; `os.fchmod` is restored after the simulation; and, POSIX-only,
the requested mode is still applied when `os.fchmod` exists. The
group was verified to reproduce the defect: with the fix stashed, the
suite crashes with the same `AttributeError` the CI logs show.

No previous check was removed or weakened; the store suite grows by
the six new checks. No generated values are quoted in this section.

## 10. R2 — Windows absolute paths accepted by the POSIX-only path check (2026-11-27)

The CI run on the R1 final head failed both `windows-compat` jobs
again (p0-validate passed) at the same step: step 16, the timeline
delivery suite, with exactly one failure on each job —
`CF-P1-005-DELIVERY-artifact-absolute-refused` ("operation succeeded
instead of refusing"). The R1 fix had worked: steps 11 (identity)
and 12 (production store) now ran, as did steps 13–15 (media
execution 68 checks, FFmpeg skipped with no ffmpeg installed, media
adapters 50 checks — all passing).

Root cause: `validate_delivery_artifact`
(`runtime/timeline_delivery.py`) rejected absolute paths with a
POSIX-only test — `path.startswith("/")` plus `".." in
path.split("/")`. The test builds its absolute case with
`os.path.join(delivery_root, video_rel)`, which on Linux is
`/tmp/...` (refused) but on Windows is `D:\...` (accepted: no
leading `/`, no `/`-separated `..`), so the file verified and the
operation succeeded. The same POSIX-only pattern existed in
`validate_execution_artifact` (`runtime/media_execution.py`): its
test used a hardcoded `/tmp/out.mp4`, which the POSIX check catches
on every host, so the execution suite passed on Windows while the
hole stayed open. A repository-wide grep confirmed these two were
the only `startswith("/")` path checks in `runtime/`.
(`runtime/media_adapters.py` `_contained_path` uses `os.path.isabs`
and only refuses escapes, which is its design — absolute paths
under the root are allowed there; not the same hole.)

Fix: one shared host-independent predicate,
`is_safe_relative_path` in `runtime/media_execution.py`, used by
both validators (the delivery module already imports from the
execution module, so there is no new coupling). It refuses any
drive letter (`ntpath.splitdrive`), any absolute form on either
platform (`ntpath.isabs`, which recognises both separators on any
host), and any `..` segment under either separator. `ntpath` is
used deliberately so the check is identical on Linux and Windows.

Regression: seven new execution checks (six Windows-style paths —
`C:/`, `C:\`, UNC, drive-relative, backslash `..` — plus a
relative-subdirectory control) and twelve new delivery predicate
checks (eight unsafe forms including empty and non-string, three
safe forms, one non-string case). The execution cases reproduce
the defect pre-fix on Linux: with the runtime fix stashed, all six
Windows-path checks fail. The delivery predicate is new code, so
there is no pre-fix function to call — its pre-fix reproduction is
the CI run #266 failure itself. The execution suite grows by the
seven new checks; the delivery suite by the twelve new checks. No
previous check was removed or weakened. No generated values are
quoted in this section.

## 11. R3 — `ntpath.isabs` changed in Python 3.13, so the R2 predicate still accepted leading-slash paths on the CI runner (2026-11-27)

The CI run on the R2 content head failed `p0-validate` (both
`windows-compat` jobs SUCCEEDED — the R2 fix worked there) with
exactly three failures, all leading-slash paths:
`CF-P1-005-EXECUTION-artifact-absolute-path` (`/tmp/out.mp4`) and
`CF-P1-005-DELIVERY-artifact-absolute-refused` plus
`CF-P1-005-DELIVERY-path-unsafe: /abs/escape.mp4`. Every
Windows-style case passed. The same run also failed the manifest
check — expected at that point, because the docs push had not
happened yet and the manifest on the remote still listed the R1
file hashes.

Root cause: the R2 predicate relied on `ntpath.isabs()` for the
leading-slash case. Since Python 3.13 (GH-44626) `ntpath.isabs()`
returns False for a path starting with exactly one (back)slash —
on Windows that form is drive-relative, not absolute. The CI
`p0-validate` job runs Python 3.14.4, where
`ntpath.isabs("/tmp/out.mp4")` is False; local Python is 3.12.3,
where it is still True — which is why the local suite passed and
CI failed. Verified from the upstream change record (the 3.13
release note: "On Windows, `os.path.isabs` no longer considers
paths starting with exactly one (back)slash to be absolute") and
by the failure pattern itself: precisely the drive-less
leading-slash cases failed, nothing else.

Fix: the predicate now refuses a leading `/` or `\` EXPLICITLY
(first-character test), before consulting `ntpath` at all, so the
refusal is identical on every Python version. `ntpath.splitdrive`
and `ntpath.isabs` still cover drive-qualified and UNC forms.

Regression: the three failing checks ARE the pin — they failed
on run #267 and pass locally. The fix is additionally pinned by a
committed simulation group in `tests/test_timeline_delivery.py`
(`CF-P1-005-DELIVERY-path-unsafe-py313` / `-safe-py313`, eight
checks): it replaces `ntpath.isabs` with the Python 3.13+
semantics (False for a single leading slash) and requires every
unsafe form to still be refused and both relative controls to
still be accepted. Without the explicit first-character test
this group fails on local Python 3.12 too (the two
leading-slash cases fail), so the pin does not depend on the CI
runner's version. The delivery suite grows by the eight new
checks. No previous check was removed or weakened. No generated
values are quoted in this section.
