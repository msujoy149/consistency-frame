# CF-WO-P1-004 Corrections Record

**Work Order:** CF-WO-P1-004 — Universal AI Production Brain &
Script-to-Production Orchestration Runtime.
**Branch:** `feat/cf-p1-004-universal-production-brain`.
**Scope:** task audit (Task A), five new schemas, production
orchestrator runtime, task compiler, provider registry, host
compatibility reconciliation, workflow records, documentation.
**Rule for this record:** no generated values appear here — no
manifest SHA, no head/commit values, no byte counts. Final values
go in the delivery report and the PR body only.

## 1. Gap map (Task A audit)

The audit inspected the audit document, the P0 implementation
plan, all four architecture YAML files, the adapters, workflows,
skills and routing-catalog registries, the schemas, and the three
P1 runtimes. The full gap map is in the delivery evidence folder
(`evidence/p1004/gap-map.md`).

The P1 runtimes that exist are real: trusted local session
(P1-001), authorization (P1-001), skill router (P1-002) and
script-to-performance (P1-003). No orchestration, state-machine,
task-compiler or provider-matching module existed anywhere in the
repo — that is the gap this round fills. Plan contracts were
strong; the missing pieces were the analysis contract, the task
packets, the provider records, and the gate state.

The audit's nine gaps (G-A–G-I in the gap map) covered: the
production-analysis contract, the provider capability registry,
the host conformance vocabulary split, the workflow status
vocabulary, the orchestration runtime, the task compiler, the
gate-state contract, the provider-neutral handoff rule, and the
documentation numbering clarification. Every gap was implemented
in this round as runtime, schema, registry or documentation work
over the existing 15 skills. **No new skill was created** — the
audit found no gap that needs one; any genuinely missing creative
system goes through Command Authority §9 (task-local draft, then
explicit user authorisation), not this round.

## 2. Muse compatibility reconciliation (four dimensions)

The audit resolved the discrepancy between the compatibility
matrix (Muse knowledge-pack path `VERIFIED`) and the adapters
registry / platform-capabilities document (Muse conformance
`NOT_TESTED`) by tracking four dimensions separately. This is a
vocabulary collision, not a factual contradiction:

1. **Native installation support — UNSUPPORTED.** There is no
   documented Meta custom-skill install flow; the matrix, the
   adapters registry, the platform-capabilities document and the
   README agree on this.
2. **Packaged knowledge-pack support — EXISTS and is the path in
   use.** Clone the repo and read the skills; `setup.sh` syncs the
   15 skill copies. The "pack" is the repository itself — no
   discrete pack artifact exists.
3. **Actual host conformance — split.** Muse is USED DAILY in this
   account since the repo was created (real, informal usage), but
   formal conformance is NOT_TESTED (no standardized conformance
   test run, no test ID or pass/fail criteria recorded). The
   matrix's `VERIFIED` meant "exercised in this account"; the
   adapters registry's `NOT_TESTED` meant "no formal test run".
   Both records now carry both fields: `verification_status:
   VERIFIED` with `verification_basis:
   usage-exercised-in-account`, and `formal_conformance_status:
   NOT_TESTED` with `formal_conformance_test_id:
   CF-P0-ADAPTER-001`. The formal test itself is still to be run.
4. **Media execution capability — NO.** Muse directs tools only;
   media execution is done by providers (VoiceStudio's local API,
   OpenMontage, paid providers) and local tools. No record had
   stated this negative explicitly; it now does.

All other hosts (Claude Code, Codex, Gemini CLI, Antigravity,
ChatGPT, OpenCode, Claude, Cursor, GitHub Copilot) remain
NOT_TESTED with zero conformance evidence. Plugin/extension
manifests on disk are not evidence of loading. Three hosts
(Claude, Cursor, GitHub Copilot) had no adapter records at all;
records now exist for them, all PACKAGED and NOT_TESTED.

## 3. Addendum-01 §18 SHA correction (reviewer was right)

The Addendum-01 Bengali report's §18 printed wrong narrative
SHA-256 values for `docs/implementation/build-report.json` and
`docs/implementation/BUILD_REPORT_P0.md`. The reviewer was
right; the values were recomputed from the final tree at the
P1-003 final head by the P1-004 coordinator and confirmed against
the live CHECKSUMS.txt at that head (the manifest SHA in the
report was correct).

Root cause, refined beyond the work-order text: the wrong values
were the coordinator's provisional-regen blobs (committed in the
docs/provisional commit); the parent's final docs commit re-ran
the final regen and overwrote them with the correct values. The
report paired the provisional SHA with the final byte count — a
mixed pair, which is why the byte-count check did not catch it.
The values the work order had attributed to the intermediate
commit were not its source; the committed tree of that commit
holds an older, different file. Full verification evidence is in
the delivery evidence folder (`evidence/p1004/sha-18-verification.md`).

Lesson carried into this round and recorded here: after the FINAL
regen, print every SHA-256 and byte count from the final tree —
never copy values from an earlier regen, log line, or provisional
commit, even when byte counts match.

## 4. Commercial voice restriction

The default OmniVoice weights are CC-BY-NC (non-commercial). The
provider registry records VoiceStudio/OmniVoice as
`commercial_use_approved: false`, and the task compiler refuses
to match it for commercial jobs — a commercial voice packet
compiles as an unavailable handoff, never as a silent substitution.
A different commercial voice route must be independently cleared
before it can be matched; no such route is cleared in this round.

## 5. Workflow status vocabulary

All 13 workflow records in `registry/workflows.json` were
`SCHEMA_DEFINED` with empty `skills_invoked` lists. This round
populates `skills_invoked` from the routing matrix (mode → skill
ids in precedence order) through the registry generator, and
defines the `EXERCISED` vocabulary — but promotes no workflow to
`EXERCISED` this round. The `wf-generate-from-script` workflow's
stated outputs include a timeline plan, and no runtime in this
round builds a timeline manifest (the orchestrator produces shot,
performance and audio plans plus task packets), so no workflow
meets the exercised bar yet. The status stays `SCHEMA_DEFINED`
for all 13, and the reason is recorded here rather than silently
promoted.

## 6. Provider matching and handoffs

The provider registry (`registry/providers.json`, compiled from
the `providers:` section of
`architecture/COMPANION_CAPABILITY_REGISTRY.yaml`) holds 13
records: the local companions and tools (VoiceStudio/OmniVoice,
OpenMontage, FFmpeg, OpenTimelineIO) plus nine documented-only
paid external providers. Only two providers are exercised in this
account (VoiceStudio for voice, FFmpeg for local media work);
OpenMontage assembly and all nine external providers are
NOT_TESTED, so video, image, sound and reference tasks compile as
provider-neutral handoffs with the reason recorded — never as
pretended executions. Matching prefers VERIFIED, then EXERCISED;
NOT_TESTED and FAILED providers never match.

## 7. Numbering systems (clarification, not a change)

Three numbering systems exist in the repo and must never be
confused:

- **Production Complexity P0–P3** — a video-quality scope
  classification (Essential / Strongly Recommended / Advanced /
  Specialized).
- **Engineering milestones P0/P1/P2/P3** — project phases (P0
  safe foundations, P1 runtimes, P2/P3 future work).
- **G1–G6** — production approval gates (the stage-gate workflow).

The runtime doc, the command-authority doc and the README now
state this explicitly.

## 8. What this round did NOT do

- No new skill was created (see §1).
- No VoiceStudio or OpenMontage internal code was changed.
- No P0 canonical authorization changes; no P1-001/002/003
  protections weakened; no existing test weakened or deleted.
- No handbook content was duplicated or redone — the handbook's
  selected recommendations were already integrated in Addendum-01.
  The handbook PDF itself was never received in the workspace, so
  no cross-check against the file was possible in this round
  either; that limitation stands.
- No PR was merged; no PR base was changed; no branch was deleted;
  no history was rewritten.
- No paid media-generation call was made; no provider was treated
  as verified without conformance evidence; no private character
  image or voice sample was sent to any provider.

## 9. BLOCKED resume to an operation-gated previous state (test-found)

The `CF-P1-004-ORCHESTRATOR` suite found that a job blocked from
`BATCH_PRODUCTION` (or `PLAN_READY` / `TEST_READY`) could not
resume: `transition_job` checked the operation-gated targets
before the BLOCKED-resume branch, so resuming to the state the
job came from raised "operation-gated". That was a defect, not
the design — the work order, the module docstring and the repo
instructions all say a blocked job resumes to its previous
state, with the only bar being a gate still BLOCKED. The fix
moves the operation-gated check into the forward-transition
branch only; resuming from BLOCKED now returns to the previous
state even when it is operation-gated, because the operation
that put the job there already passed the gate. The suite
regression covers the resume for all three gated states; bare
forward transitions into them are still refused.

## 10. R1: production contract fidelity (Tasks A–B)

The production-analysis schema gained the structured
environment and asset requirements (background design, weather,
atmosphere, foreground/midground/background requirements,
environment continuity, asset references) and the sound timing
contract (stable cue id, scene/shot/beat ids, start anchor from
the seven-value vocabulary, optional end anchor, offset and
duration, distance, perspective, intensity, sync target, mixing
priority). `character_resolutions` may now be empty — but only
when the source genuinely has no visible character subjects;
when the source has speaking or visible identities, every
distinct required identity must be resolved exactly once
(missing, duplicate and unknown all rejected). A narrator /
voice-over is not a visible character: an identity marked with a
narrator role needs no visible-character resolution, and a
speaking identity in no scene and no shot is treated as a
voice-over. The P1-003 zero-dialogue limitation stands — the
runtime never invents dialogue. The task-packet schema gained
`beat_id`, structured `cue_timing` (with `timing_status`
`planned` / `actual-rendered`), and the task types
`media-technical`, `creative-editing` and `semantic-qc-review`;
`editing-finishing` and `qc-review` stay in the enum so
already-compiled packages can still regenerate. The
production-analysis nullability matrix grew from 24 to 53
optional paths; the coverage assertion compares the declared
matrix against the optional paths discovered from the schema
itself, so a future optional schema field without a matching
test fails the suite.

Cross-reference integrity is checked against the actual built
bundle, not a fixture: `validate_analysis_bundle_references`
runs inside `build_production_bundle` and again explicitly in
`plan_script_to_production`. Scene ids must resolve to the
Scene Plan, beat ids within their scene, shot-direction shot
ids to the Shot Plan with the scene agreeing, sound cue
scene/shot/beat references must resolve, and character
resolutions must cover every identity the source and the
approved plans require. Duplicate shot-direction entries are
rejected; unknown references are never silently ignored.

The compiler now builds the two missing packet paths.
Environment packets carry every validated scene-environment
detail plus approved asset ids as required `approved-asset`
inputs. Prop packets are one per distinct prop, keyed by the
approved prop id when approved else by the task-local prop id:
an approved prop is prepared from its approved record (never
redesigned) as a handed-off packet; a prop with no approved
record gets a task-local proposal packet and fails closed
without a design brief or without a matching approved record;
nothing permanently registers a prop. Sound packets preserve
the full structured cue timing with `timing_status: "planned"`;
intentional silence still generates no sound-generation
request; fallback S2P audio-plan cues get planned timing only.

Provider capability accuracy (B4): FFmpeg matches only the
technical media operations it genuinely evidences (probe,
assemble, transcode) as `media-technical` tasks. The old single
`editing-finishing` and `qc-review` packets bundled technical
operations with creative work and matched FFmpeg on one
technical operation alone; they are replaced by the split —
`media-technical` (assemble/transcode/export, and probe/validate
for technical QC) plus `creative-editing` and
`semantic-qc-review`, which have no verified provider and always
compile as handoffs for human work. Existing test assertions
that encoded the old matching were updated to the corrected
behaviour (the B4 correction); no other existing coverage was
weakened. The end-to-end package is now 12 packets with 8
unmatched handoffs (was 10 packets, 6 unmatched).

## 11. R1: persistent production job store (Task C)

`runtime/production_store.py` is new: local JSON storage for
production jobs and checkpoints under an explicitly configured
local workspace root, standard library only, atomic writes
through `scripts/atomic_write.py` (loaded by file path, never by
mutating `sys.path`). Only production metadata is persisted —
ids, state, gate states, analysis/bundle hashes, task package
and statuses, execution-result references, QC reports,
correction rounds, approved character/prop/voice ids, asset
references with provenance, version information. Raw media,
voice recordings, personal photos, model weights, API keys,
passwords, tokens, raw private voice samples and private media
bytes are never stored. Every record is an envelope with an
integrity hash; files are `0o600` and directories `0o700` on
POSIX (Windows relies on the user-data-directory ACL behaviour,
the P1-001 R2 pattern). The root must be absolute; ids match
the strict id pattern; paths are built only from validated
components; symlink containment is checked with `realpath` and
a symlinked record file is refused on read. Malformed or
tampered records are reported, never silently dropped. A stored
session id is provenance only: resume needs a NEW exact active
session, a project/owner/workspace match, stored-job validation
and gate revalidation, rebinds the session id, refuses
`DELIVERED` jobs, and never triggers execution or auto-resumes
paid/external provider tasks. New suite
`CF-P1-004-R1-STORE` (save/load round trip, integrity, path
safety, tamper rejection, checkpoint save, resume under a new
session, DELIVERED and wrong-owner/project refusals, gate
revalidation).

## 12. R1: the unified entry point (Task D)

`plan_script_to_production` is the one deterministic
script-to-production planning entry point: validate the job and
session, validate the analysis draft, build the P1-003 bundle
(including the analysis-to-plan cross-reference checks),
validate the analysis-to-plan references once more explicitly,
compile all task packets, build the complete task package, and
persist the planned job and a `plan-<bundle_id>` checkpoint
through the production store when a store root is given. It
returns the bundle, the updated job, the task package and the
persistence information. No media is generated, no provider is
executed, and no creative reasoning happens inside it.
`wf-generate-from-script` is NOT promoted: no timeline manifest
is produced and no fake media path is invented. End-to-end
regression covers the short form (12 packets), the narrator
form (13 packets, 3 voice packets, narrator line verbatim), and
the long form (21 packets including the fisherman task-local
proposal's character-design and reference-sheet packets, 14
unmatched handoffs), all with dialogue preserved verbatim.

## 13. R1: proposals lost through the orchestrator (test-found)

The long-form end-to-end test found that a task-local proposal
passed to `plan_script_to_production` was silently lost:
`compile_provider_tasks` keyed the proposals list into a dict
and passed the dict to `compile_task_package`, which iterated
its argument as a list of proposal records — iterating a dict
yields its string keys, which the compiler filtered out as
non-dict records — so compilation failed with "no proposal
record was supplied". That was a defect, not the design: the
P1-004 orchestrator tests never compiled through
`compile_provider_tasks` with proposals, so the double keying
was latent. The fix passes proposals through as a list; the
compiler does the keying itself. The long-form end-to-end test
pins the fix.

## 14. R1: Muse formal conformance CF-P0-ADAPTER-001 (Task E)

The outstanding formal conformance test for the Muse
knowledge-pack route ran in this environment and passed
(`tests/test_muse_adapter_conformance.py`, suite
`CF-P1-004-R1-ADAPTER`, 20 checks). It verified the nine work
order items in this environment: knowledge-pack access (the
repo's 15 skill directories readable from the workspace),
required-skill identification through the P1-002 router
(command-authority, character-consistency, voice-consistency
selected for a GENERATE_FROM_SCRIPT request), canonical
contract read (production-analysis schema, records carry
schema_version 2.5, provenance labels present), short-form
fixture analysis (structured production-analysis output),
verbatim source dialogue preservation (counts agree; compiled
voice packets carry the script text byte-identical), real schema
+ runtime validation of the output (0 errors), unsupported
media-provider operations correctly identified (video/image/
sound unmatched; FFmpeg only for technical media operations;
creative editing and semantic QC unmatched; no packet claims
execution; OpenMontage stays NOT_TESTED), and no native Meta
custom-skill installation claim (matrix and adapters registry
both record native install UNSUPPORTED; the documented route is
the versioned knowledge pack). After the test passed, the
canonical records were updated through their existing
generators: the matrix Muse entry now records
`formal_conformance_status: VERIFIED` with the test as
evidence, and its duplicate keys (`formal_conformance_status`
×2, `media_execution` ×2 — PyYAML silently took the last) were
cleaned; the `ADAPTERS` table in
`scripts/generate-registries.py` gained per-adapter
conformance fields (last_verified, evidence, status) and the
Muse tuple records conformance VERIFIED with the test file as
evidence, last verified on the test date, status verified; the
adapters registry was regenerated (only the Muse record and
the registry note changed). Native Muse install stays
UNSUPPORTED. No claim is made about ChatGPT, Claude or Gemini
conformance.

## 15. R1: what this round did NOT do

- No new skill was created (15 stays 15).
- No VoiceStudio or OpenMontage internal code was changed.
- No P0 canonical authorization changes; no P1-001/002/003
  protections weakened; no existing test weakened or deleted
  except the B4 correction in §10, where existing assertions
  encoded the wrong provider matching and were updated to the
  corrected behaviour.
- `docs/06-installation.md` was not edited: a system security
  notice on that file blocks editing (both the previous
  coordinator and the parent hit it). No Task G change to that
  file was needed in this round; the limitation stands as an
  open item for the user's decision.
- The handbook PDF cross-check is still open (never received).
- No video provider is VERIFIED or EXERCISED; no timeline
  manifest exists; `wf-generate-from-script` stays
  SCHEMA_DEFINED.
- No PR was merged; no PR base was changed; no branch was
  deleted; no history was rewritten.
- No paid media-generation call was made; no provider was
  treated as verified without conformance evidence; no private
  character image or voice sample was sent to any provider.
- A parallel workstream (persistent Character & Voice Identity
  Selection, Resolution and Production Binding) runs separately
  in a detached worktree from the same baseline and integrates
  after this round commits; this round's scope and files are
  unaffected by it.
## P1-004-R1-ADDENDUM-IDENTITY

Persistent character and voice identity selection, resolution and
production binding. One new module, `runtime/identity_resolution.py`,
holds all new identity logic; the orchestrator and compiler take only
thin additive hooks. Two new schemas, `identity-selection-policy.json`
and `identity-snapshot.json`; additive optional fields only on the
existing schemas. No new skill; no second job database; no P0
authorization change.

### 1. Gap map (Task A audit)

Twelve capabilities already existed and were not recreated: unique
character ids and names, reference image records, model sheets,
expression libraries, fixed identity instructions, character-to-voice
relationships, multiple voice-profile ids per character, voice
ownership and workspace restrictions, consent and approval, explicit
permanent-registration authorization, task-local proposals, and the
private registry overlay. Eight genuine gaps were confirmed against
the integrated source and closed:

- **G1** — image and video packets carried only the instruction to
  match the approved reference, no structured identity data. Closed
  by `identity_bindings` on the task packet.
- **G2** — voice tasks took a voice profile id as a string and never
  loaded or validated the profile record. Closed by
  `resolve_character_voice` plus the `voice_binding` on the packet,
  delegating all P0 checks to the asset policy.
- **G3** — no authorized private-registry loader or name-to-id
  resolution (`resolve_character` only took a caller-supplied
  mapping; the `CONSISTENCY_FRAME_CHARACTERS` variable was
  documented only). Closed by `load_authorized_character_registry`
  and `resolve_character_reference`.
- **G4** — no selection policy or opt-out semantics (`project.json`
  carried only `character_ids`). Closed by the
  identity-selection-policy schema and the four modes.
- **G5** — no job identity snapshot. Closed by `build_identity_snapshot`
  and the snapshot stored on the job.
- **G6** — the fixed prompt block and generation seed were not
  machine-readable in `character.json` or
  `character-registration.json` (the skill said the seed lives in
  `character.yaml`, but neither canonical schema had the fields).
  Closed by additive optional `fixed_prompt_block` and
  `generation_seed` fields on both schemas.
- **G7** — no cast classification. Closed by `resolve_script_cast`
  and the `cast_class` field on analysis resolutions
  (`VISIBLE_CHARACTER`, `OFF_SCREEN_SPEAKER`,
  `NARRATOR_OR_VOICE_OVER`, `MENTIONED_ONLY`).
- **G8** — no identity-specific drift-correction task. Closed
  without a new task type: regeneration packets copy the original
  packet's identity and voice bindings verbatim, so a correction
  re-anchors to the approved reference.

### 2. Defect found in P1-004 and fixed here

`compile_provider_tasks` converts proposals to a mapping keyed by
proposal id and passes it to `compile_task_package`, which iterated
it as a list. Iterating a mapping yields its keys (strings), so
every proposal was silently dropped and any orchestrator-level
compile with task-local proposals failed with "no proposal record
was supplied". `compile_task_package` now normalizes a mapping as
well as a list; list callers are unchanged. The identity suite
regression covers the orchestrator-level compile with task-local
proposals.

Two smaller rules were corrected while building the snapshot and
the bindings. First, an expression reference's name is derived
from the asset path's basename under the skill's
`expression-<name>` naming convention, never from the asset's
`role` field (which is always the literal word "expression" and
therefore can never match an emotion). Second, a task-local
proposal's reference ids are sanitized through the same stable-id
derivation as registered references, with a per-snapshot dedupe,
so a proposal cannot collide with a registered reference id.

### 3. Default-voice rule (clarification, not a change)

A registration's default voice is only its explicit
`default_voice_profile_id`. The first entry of
`additional_voice_profile_ids` is not a default: a registration
with several eligible profiles and no explicit default must fail
closed and ask for one clear selection. The character.json shape
keeps its canonical rule — the default is the first entry of
`voice_profile_ids`. This follows the work order's Task I
("multiple eligible + no default → request one clear selection")
and is pinned by the identity suite's ambiguity case.

### 4. Snapshot and resume contract

The snapshot is the job's frozen identity state. It is stored on
the job record, so the production store persists it with the job
and no second database exists. Resume revalidates the snapshot
against the current registries under the new active session:
a changed registry record, a missing reference asset, a reference
hash mismatch, a voice profile that no longer belongs to its
character, or a changed voice reference-audio hash all stop the
resume and report the cause. The snapshot is never silently
rebuilt from a new image, and a generated image never becomes the
new anchor. The resume validation is called by the caller after
`resume_production_job` returns the job; the unified
script-to-production entry point wires it in at integration.

### 5. What this round did NOT do

- No branch, no PR, no push, no merge, no change to any PR base.
- No P0 authorization change; no P1-001/002/003 protection
  weakened; no VoiceStudio or OpenMontage internal code changed.
- No paid media-generation call; no provider claimed exercised
  without evidence; no host marked verified without a conformance
  test. The formal Muse conformance test remains Workstream A's
  task; all other hosts remain untested.
- No private character image, model sheet, voice recording, or
  personal photo was committed, copied into a report, or read from
  another workspace. The public `characters/` directory stays
  intentionally empty; the identity fixtures use synthetic test
  identities with no relation to any real private registration.
- `docs/06-installation.md` was not edited (the system security
  notice on that file blocks editing; recorded as an open item).
  The handbook PDF cross-check is still open (the reference PDF
  was never received).
- The stale "186 entries" label strings in `tests/test_reports.py`
  were deliberately left untouched: fixing them is Workstream A's
  regression task, and editing the same lines here would create a
  needless merge conflict. The assertions themselves already use
  the expected-count constant and verify the actual entries.

## 16. Integration: R1 + ADDENDUM-IDENTITY (parent, 2026-11-26)

The two parallel workstreams were integrated by the parent onto
one branch, by cherry-picking the identity workstream's content
commit onto the R1 final head and resolving every conflict by
keeping both sides — nothing was cloned, nothing was dropped,
and no workstream's file was overwritten by the other.

- The proposals fix exists exactly once. Both workstreams found
  the same latent defect independently (the orchestrator keyed
  task-local proposals into a dict and the compiler iterated it
  as a list, dropping every proposal). The merged compiler
  normalizes a list or a mapping by proposal id in one place
  (`compile_task_package`); the merged orchestrator passes
  proposals through as a list and no longer re-keys them. The
  R1 long-form test and the identity mixed-cast test both pin
  the single fix.
- The schemas merged additively. `production-analysis.json`
  keeps the R1 environment and sound-timing fields and gains
  the identity `cast_class` and `scene_ids` on resolutions; the
  R1 rule stands that an empty `character_resolutions` array is
  valid (no `minItems` was taken from the identity side).
  `task-packet.json` keeps the R1 `beat_id` and `cue_timing`
  and the expanded task-type list, and gains `identity_bindings`
  and `voice_binding`. The analysis NULL matrix covers both
  sides' new optional paths.
- `tests/test_reports.py` carries both sides' fixes: the R1
  stale-label correction and the identity count update, combined
  into the integrated expected count. `tests/run-tests.sh`
  carries both suites' entries. The corrections sections of
  both workstreams sit side by side in this file.
- Resume revalidation is now wired through the store. The
  identity workstream's `validate_resumed_identity` was
  caller-side by design; the parent gave `resume_production_job`
  optional `registry` / `voice_registry` parameters so a caller
  can revalidate a stored job's snapshot against the current
  registries inside the resume itself (a changed record, missing
  asset or hash mismatch stops the resume before the session is
  rebound). Without registries the behaviour is unchanged and
  the caller revalidates separately after resume, as documented.
  Two checks pin the wiring in the identity suite: store resume
  with the current registries rebinds the session and keeps the
  frozen snapshot, and a changed voice reference-audio hash
  blocks the resume.
- The identity section's note that the stale label strings were
  left untouched for Workstream A is now historical: the
  integration applied Workstream A's label fix, so the labels
  and the expected count agree in the integrated tree.

## 17. R1-F1: unified identity workflow, exact name resolution & end-to-end production integration

Independent review of P1-004-R1 found the identity system and
the production orchestration system each correct on their own
but not yet joined: the unified entry point did not accept an
identity policy or registries, the canonical policy named
characters by id only, and the NEW_ONLY hardening had been
proven only on renamed fixtures. This round joins them without
redesigning either system. No P1-004-R1 behaviour changes for
jobs without an identity policy.

- **Defect A — the planner now carries identity end to end.**
  `plan_script_to_production` takes optional keyword-only
  `identity_policy`, `character_registry`, `voice_registry`,
  `character_registry_root` and `voice_registry_root`. An
  explicit policy wins over a policy stored on the job. With a
  policy, registries resolve in this order — explicit mapping,
  then root, then the authorized overlay environment variable —
  and the voice registry defaults to the character registry
  root; a loader failure fails the planning. The resolved
  policy and registries are passed to `build_production_bundle`,
  which freezes the identity snapshot on the job, and the
  result records the effective policy. With no policy, behaviour
  is exactly the pre-F1 behaviour and no registry is accessed.
  An explicitly supplied registry is scoped to the session
  (`scope_registry_to_session`) inside the snapshot builder,
  so records under another owner or workspace are invisible
  there exactly as the loader excludes them at load time.
- **Defect B — canonical selectors and exact auto-matching.**
  `schemas/identity-selection-policy.json` gains optional
  `selected_characters`, an array of `{character_id, name}`
  records (at least one of the two per record; both must resolve
  to the same record). `selected_character_ids` stays valid.
  When both selector lists are supplied they must resolve to
  the same character set, or the policy is refused as
  conflicting; the agreement check runs at resolution time
  because names need the registry, and the repo's validator
  subset cannot express it in the schema. `AUTO_MATCH_APPROVED`
  completes in two places: the planner enriches the analysis
  first (`enrich_analysis_for_auto_match` fills
  `registered_character_id` on name-only approved resolutions
  by exact unique name, so the analysis validates), and the
  snapshot builder completes the selection from the script cast
  (`complete_auto_match_selection` resolves every eligible
  unselected cast reference by exact id, else exact unique
  name; duplicate names, unknown names and conflicting
  identifiers fail closed; no fuzzy matching). A character only
  mentioned in dialogue receives no visible binding: the
  analysis validator now accepts a resolution ref outside the
  known set only when it declares `cast_class`
  `MENTIONED_ONLY`, and the snapshot builder refuses any
  disagreement between a declared cast class and the class the
  cast classifier derives from the script structure.
- **Defect C — the 12-step sequence runs through the real
  planner.** The F1 integration tests call
  `plan_script_to_production` itself across all four modes and
  verify the bundle, the frozen snapshot, the image/video
  packets, the voice packets and persistence; the existing
  helper-level tests are preserved unchanged.
- **Task D — NEW_ONLY hardening and the adversarial test.**
  `validate_new_only_inputs` runs in the snapshot builder for
  every NEW_ONLY job: an analysis resolution that approves a
  registered character, a task-local proposal reusing a
  registered reference asset, or a bundle voice binding naming
  a registered voice profile all fail closed, naming only the
  caller-supplied reference (character ref, proposal id,
  dialogue line id) — never registry contents. The adversarial
  test uses the original script/cast references against the
  populated registries (the previous NEW_ONLY fixture renamed
  them first): the story roles are reinterpreted as new
  task-local identities, and the whole compiled package, the
  production bundle and the snapshot are scanned for registered
  reference ids, paths and hashes, model-sheet ids, fixed
  prompt blocks, fixed-identity references, generation seeds,
  voice-profile ids, reference-audio ids, paths and hashes, and
  any seed key. The old registry records are deep-compared
  before and after and are never modified, deleted or
  deprecated. Two rejection cases pin the fail-closed path:
  the original approved analysis under NEW_ONLY, and a
  task-local analysis whose draft still names a registered
  voice profile.
- **Task E — the preserved binding builders are actually
  invoked.** `identity_bindings_for_shot`,
  `identity_binding_for_character`, `voice_binding_for_line`,
  `build_identity_snapshot` and `validate_identity_snapshot`
  are unchanged in contract and are exercised through the
  planner in every mode; the F1 tests assert exact approved
  reference ids, primary references, model sheets, expression
  references and identity hashes on visible registered
  characters, and exact approved voice-profile ids with
  authorized reference-audio ids and hashes on speaking
  registered characters. Task-local characters and voices use
  job-scoped references throughout.
- **Test-found defect: voice-binding pauses.**
  `voice_binding_for_line` copied the performance line's
  `voice.pauses` verbatim into the packet binding, but the
  performance-plan schema types `pauses` as an array of pause
  descriptions while the task-packet schema types
  `voice_binding.pauses` as one string. The identity fixture's
  lines carry empty pause lists (falsy, so the key was omitted
  and the defect never fired); the canonical short/long drafts
  carry a non-empty list, which the F5 test exposed as a
  schema rejection at compile time. The binding now normalizes
  the pause direction to one string (a list joins with `"; "`,
  a plain string passes through, anything else is no pause
  direction). No existing packet changes: empty pause lists
  still omit the key.
- **Voice registry canonical path.** One overlay root serves
  both registries. `load_authorized_voice_registry` reads
  `voice-profile.json` files anywhere under the root plus a
  top-level `voices.json` (a `{"voice_profiles": [...]}` object
  or a bare list); it schema-validates every record, refuses
  duplicate voice ids and symlinked paths, enforces owner /
  workspace scoping, and loads as empty when no voice files
  exist. No second registry was added: the voice registry is
  the same private overlay the character registry already
  used, and the fixture voice registry remains test-only.
- **What this round did NOT do.** No P0 authorization logic
  changed; no VoiceStudio or OpenMontage internals changed; no
  new skill; no new tracked file (the manifest scope is
  unchanged); no provider was exercised and no media was
  generated — packets compile as provider-neutral handoffs as
  before. The handbook PDF cross-check and the
  `docs/06-installation.md` update remain open from earlier
  rounds.
