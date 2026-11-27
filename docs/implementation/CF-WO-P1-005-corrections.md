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


## 12. R4 — provider URL security, provider contracts, timeline geometry, VoiceStudio honesty, local end-to-end (2026-11-27)

Five workstreams, one round. (A) Provider URL security /
SSRF prevention. (B) Provider-specific contracts replacing
the generic `{model, prompt}` payload. (C) Timeline geometry
and media metadata: the hardcoded 16:9 / 24 FPS / 1920x1080
fallback is gone. (D) VoiceStudio capability honesty. (E)
Local execution + end-to-end regression with real FFmpeg.
No generated values are quoted in this section.

### 12.A URL security policy

`runtime/provider_url_policy.py` (new in R4-A) is the single
place outbound provider URLs are judged: explicit
per-provider API and output/CDN origin allowlists, HTTPS only,
no userinfo, no unapproved host or port, no IP-literal /
loopback / private / link-local / multicast / reserved /
unspecified destination, no cloud-metadata address, no
alternate numeric address representation, no encoded
path/hostname trick, no trailing-dot hostname. Every redirect
hop is validated before it is followed (at most five hops);
authorization headers are kept only on same-origin hops and
are sent with a download only when the download URL's host is
the provider's own API origin — a signed CDN download URL
never receives them. The default transport pins the
connection to a validated resolved address, so a hostname
cannot resolve to a prohibited destination between validation
and connection; that pinning protects this client against
DNS-rebinding of its own requests and is documented as exactly
that, never as a claim about the provider's infrastructure.
A forbidden destination is refused before the transport is
called for that hop, and no signed URL query string,
credential, or authorization header is ever logged.

Defect found while wiring workstream B: the adapter's submit
path read a `canonical` key from `validate_url`, which returns
parsed components (`scheme`, `host`, `port`, `path`, `query`)
and has no such key — every redirect test failed with a
`KeyError` before any request. Fixed by validating the URL and
using the submitted string as-is. Regression: the redirect
groups in the security suite, which fail without the fix.

### 12.B Provider contracts

`runtime/provider_contracts.py` (new in R4-B) holds one
contract class per live provider — OpenAI image, Gemini image,
fal image, Veo video, Kling video, LTX video, ElevenLabs
voice, Lyria music — each implementing request construction,
model selection, authentication, reference serialization,
submit/poll/result/cancel parsing, and error classification.
`HttpProviderAdapter` now builds every request through its
provider's contract and refuses any packet that was not built
by one, including a tampered body or a request built for
another provider. Reference assets arrive through the
execution context (`{"mime", "base64"}` or a workspace
`{"path"}`) and are normalized inside the workspace root
before the contract validates them.

The official-doc audit (2026-11-27, table in
`docs/runtime/PROVIDER_ADAPTERS.md`) corrected the specs:
OpenAI gains `gpt-image-1-mini`, the `gpt-image-2-2026-04-21`
and 2.5/2.6 snapshots, and `chatgpt-image-latest`, and edits
take up to 16 images; Gemini gains the deprecated-but-working
`gemini-3.1-flash-image` and the full reference-count
breakdown; fal.ai refuses reference images (serialization
UNCONFIRMED, no upload flow) and its poll statuses are only
`IN_QUEUE` / `IN_PROGRESS` / `COMPLETED`; Veo job ids are the
full operation name, its poll URL is the documented
operations.get URL, its output downloads from the Gemini Files
API on the same host (so auth is kept for that origin only),
and it has no documented cancellation; Kling uses the legacy
/v1 design (`kling-v1` … `kling-v2-6`, 5/10 s) — the newer
path-based models are NOT implemented and failed-task
charging is UNCONFIRMED; LTX gains `ltx-2-3-fast/pro` and
charges only on success (a failed job releases its
reservation); Lyria gains `lyria-3-clip-preview` (30 s) while
WAV output is refused explicitly (fields unconfirmed). Sora
stays FAILED and has no contract. The registry YAML and the
generated `registry/providers.json` were re-synced to the
corrected specs (shared-key diff zero after the sync).

Defects found while wiring: (1) the fal contract dropped
`response_url` from a COMPLETED poll response, so the adapter
had no result document to fetch — fixed by carrying the URL
from the poll response, with a context-carried URL as
fallback; (2) the adapter called `parse_cancel_response`
with swapped arguments and treated its dict return as a bool
— fixed to `(status, data)` and `result["cancelled"]`;
(3) `parse_result_response` returns a dict, not a bare URL —
fixed at the call site. Regression: the new
`CF-P1-005-R4-CONTRACTS` suite (161 checks) pins exact
method, endpoint, auth header, and body per provider, the
async lifecycles, cancellation only where supported,
malformed responses, missing output, wrong content type,
download failure, size limits, submission uncertainty, and
the generic-payload refusal. Existing Veo/fal/Kling/LTX
fixtures were updated to the new verified response shapes;
no previous check was removed or weakened.

Two honest limits stay. First, Kling and LTX completed jobs
carry a result URL whose host is UNCONFIRMED, so the
download fails closed until the host is confirmed — the
contract tests pin that refusal rather than pretending the
download works. Second, Kling, LTX and ElevenLabs are
`secondary-quoting-official`, so `prepare()` (preflight)
refuses them until the official documentation is verified;
their contract tests call `translate()` directly, which
exercises the contract without the live-call gate.

### 12.C Timeline geometry

The hardcoded aspect ratio 16:9, frame rate 24 and 1920x1080
fallback is removed from `runtime/timeline_delivery.py`,
`runtime/media_execution.py` and
`runtime/production_orchestrator.py`. Final timeline geometry
now comes from an explicit validated output profile or from
verified media probe results: a profile target is validated
against the generated media; with no target, geometry is
derived from the verified media; incompatible source geometry
is normalized through an explicit, recorded media operation
to the selected target or rejected with a clear validation
error; audio-only timelines invent no video geometry. Probe
results carry width, height, aspect ratio, frame rate
(rational representations handled), duration, codec and audio
stream metadata, and a multi-clip timeline is never
characterized from its first clip alone. The stale sentence
in `docs/runtime/MEDIA_EXECUTION_RUNTIME.md` ("otherwise
1920x1080") was corrected with the code. Regression:
`CF-P1-005-R4-GEOMETRY` (80 checks) covers 9:16 1080x1920
30 FPS, 16:9 1920x1080 24 and 30 FPS, 1:1 square, 4:3, mixed
aspect ratios and frame rates, missing probe metadata,
invalid output profile, audio-only timelines, explicit FFmpeg
normalization, and failure when actual output does not match
its declared profile.

### 12.D VoiceStudio capability honesty

The bundled VoiceStudio API was inspected (its internals
never modified) to determine which controls the backend plus
the selected engine genuinely support. The adapter now
forwards exactly `instruct`, `speed` and `seed` to the
documented backend fields, and refuses pitch, pace, emotion
and pauses with a precise capability error instead of
silently dropping them; the provider capability registry
never advertises an unsupported feature. The OmniVoice
CC-BY-NC commercial restriction is unchanged. Regression:
`CF-P1-005-R4-VOICE` (41 checks).

### 12.E Local end-to-end regression

`tests/test_e2e_local.py` (`CF-P1-005-R4-E2E`, 28 checks)
runs the validated packet → local media execution → verified
output artifact (SHA-256 + byte size) → FFmpeg probe →
timeline manifest → delivery validation → evidence record
path on deterministic locally generated media. It exercises
real FFmpeg/ffprobe operations and fails, never skips, when
FFmpeg is absent; `.github/workflows/p0-ci.yml` now installs
a known FFmpeg/ffprobe version in `p0-validate`, and the
`windows-compat` job runs the new contracts suite alongside
the geometry and voice suites (Python 3.10 and 3.12; the
py313 path-policy simulation group is retained). No optional
external provider became a mandatory dependency.

### 12.F Open defect found by this round (not fixed here)

The full suite currently fails at the `P0-SCHEMA` step:
`scripts/validate-repo.py` reports
`schemas/provider-capability.json.voice_controls.unsupported:
object schema needs non-empty properties` and
`additionalProperties must be false`. The R4-D schema addition
declares `unsupported` as a free-form map (control name to
refusal reason, `additionalProperties: {"type": "string"}`),
but the validator's closed-object rule requires every object
schema to carry non-empty `properties` and
`additionalProperties: false`. The schema file and the
validator are both untouched by this round, so the failure is
pre-existing relative to workstreams B and F; it is recorded
here rather than fixed by re-shaping D's schema or by
weakening the validator inside a contracts/docs commit. Fix
options for the D follow-up: restructure `unsupported` as an
array of `{control, reason}` objects, enumerate the refused
controls as fixed properties, or extend the validator to allow
map-style objects with a typed `additionalProperties`.

Closed by §12.G below (the enumerated-properties option was
chosen).

### 12.G Follow-up fixes — schema defect closed, Veo contract rewritten onto Vertex AI (2026-11-27)

**Schema defect (§12.F) — closed.** `voice_controls.properties.unsupported`
in `schemas/provider-capability.json` now carries explicit
properties for exactly the five refused-control keys used by
the VoiceStudio adapter constant
`VOICESTUDIO_UNSUPPORTED_VOICE_CONTROLS` and by the registry
record `provider-voicestudio-omnivoice` — `emotional_delivery`,
`pauses`, `pitch_range`, `pronunciation_preferences`,
`vocal_characteristics` — each `{"type": "string",
"description": "<the same reason text the adapter/registry
uses>"}`, with `additionalProperties: false`. The registry keys
and the adapter constant are unchanged; the existing test
`CF-P1-005-R4-VOICE-registry-unsupported` (registry keys equal
adapter keys) still passes. `python3 scripts/validate-repo.py`
now prints `VALIDATE-REPO: PASS`.

One drift found while aligning the reason texts: the registry
and the YAML record say "a stored pronunciation dictionary"
for `pronunciation_preferences`, while the adapter constant
says "a stored user pronunciation dictionary". Keys are what
the test pins; values are not asserted equal anywhere. The
wording difference is recorded here, not silently harmonised.

**Veo contract — rewritten onto the live Vertex AI route.**
The consolidated provider audit (two workers, direct reads of
the official deprecations page, 2026-11-27) confirms the
Gemini API Veo preview IDs (`veo-3.1-generate-preview`,
`veo-3.1-fast-generate-preview`,
`veo-3.1-lite-generate-preview`) were shut down 2026-10-22.
The old contract used `generativelanguage.googleapis.com` +
`:predictLongRunning` + `x-goog-api-key` + those IDs, a GET
poll via `operations.get`, and a Gemini Files download. All
of that is gone. The contract now uses, with only the audit's
confirmed facts:

- Models `veo-3.1-generate-001` (GA, Nov 17 2025),
  `veo-3.1-fast-generate-001` (GA),
  `veo-3.1-lite-generate-001` (Preview, Apr 2 2026).
- Submit: `POST
  https://us-central1-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/us-central1/publishers/google/models/{MODEL_ID}:predictLongRunning`.
- Auth: `Authorization: Bearer <OAuth token>`, credential from
  the allow-listed environment variable `VERTEX_ACCESS_TOKEN`
  only — never hardcoded, never logged. `GEMINI_API_KEY` is
  removed from the Veo contract; the Gemini-image and Lyria
  contracts keep `generativelanguage.googleapis.com` +
  `x-goog-api-key` (live, untouched).
- Poll: `POST .../models/{MODEL_ID}:fetchPredictOperation`
  with `{"operationName": "<full operation name>"}` in the
  body. The adapter gained a base-class `build_poll_request`
  hook (default: GET of `build_poll_url`); Veo overrides it.
  The job id is the full Vertex operation name
  (`projects/<project>/locations/us-central1/publishers/google/models/<model>/operations/<id>`),
  validated segment by segment (project id shape, model in
  the live set, operation id shape).
- Output: inline video bytes in the poll response (no
  `storageUri`) are saved and verified; a GCS URI output is
  refused explicitly, because the audit states no GCS download
  origin — `output_origins` stays empty and the contract fails
  closed rather than guessing a host.
- Constraints enforced by the contract: us-central1 only,
  `vertex_project_id` required from the execution context,
  1–4 outputs, 4/6/8 s, 24 fps, at most 3 reference images
  (Standard/Fast only), image input at most 20 MB. No cancel
  operation is documented — cancellation stays explicitly
  non-cancellable.
- Pricing: the official unit is per "1 count" (the pricing
  page does not define 1 count). No per-second price is
  encoded anywhere; the earlier per-second figures were
  SECONDARY-only.
- The registry record `provider-veo-video`, the adapter spec,
  and `docs/runtime/PROVIDER_ADAPTERS.md` were updated to the
  Vertex route; conformance stays NOT_TESTED — mock tests alone
  never promote readiness, and no live paid call was made.
  Sora stays FAILED/unavailable; nothing was restored.

Marked UNCONFIRMED in the registry and the docs: Fast 4K
(pricing lists it, model page does not); Lite image input
(model page says not supported, capabilities row says
supported — the contract refuses Lite references until the
conflict is resolved); GA-ID retirement wording (model page
says Nov 17, 2026 or later, versions page says no date
announced). `gemini-omni-1.2-flash` (the Gemini API
replacement) needs its own audit and is out of scope for this
round.

The request `instances`/`parameters` body shape was carried
over unchanged from the prior contract — it was NOT
independently re-verified against the Vertex docs in this
round; a live conformance run (still unauthorised) is the
place that shape is proved.

Tests: the Veo contract group grew from 16 to 20 checks — the
dead preview IDs are refused, a missing or malformed Vertex
project id is refused, the old Gemini-API operation-name form
is refused, the poll is pinned to POST + `fetchPredictOperation`
+ `operationName` body, inline-bytes completion saves and
verifies, and a GCS-only completion is refused with
`validation-failed`. The Veo groups in the adapter and URL
security suites were updated to the same Vertex shapes (7 and
3 checks, counts unchanged). Gemini-image and Lyria tests are
untouched.
