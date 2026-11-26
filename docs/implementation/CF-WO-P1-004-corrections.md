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
