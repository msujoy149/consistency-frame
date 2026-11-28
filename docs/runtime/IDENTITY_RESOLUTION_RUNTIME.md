# Identity resolution runtime (CF-WO-P1-004-R1-ADDENDUM-IDENTITY)

Persistent character and voice identity selection, resolution and
production binding — the sixth production runtime component of
Consistency Frame, built on the P1-001 trusted local session, the
P1-003 Script-to-Performance runtime and the P1-004 production
orchestrator and task compiler. It answers one question the P1-004
runtime could not answer on its own: *which registered character
and voice is this job using, and exactly which approved reference
data is bound into each task?*

P1-004 already resolved a character name to an approved registry
record or a task-local proposal, and already carried a voice
profile id on each speaking line. What it did not supply was a
project-level selection policy, a frozen identity snapshot, or
structured identity data inside the task packets: image and video
packets carried only the instruction to match the approved
reference, and voice tasks never loaded or validated the voice
profile record. This runtime supplies all three, without
duplicating anything that already exists: it wraps the P0
authorization and voice-validation policy (`scripts/asset_policy.py`)
and the P1-004 orchestrator and compiler, and it persists its state
in the same production job record — there is no second job database.

## What it guarantees

1. **Selection is explicit, never inferred.** A job uses registered
   characters only through an approved identity-selection policy
   (`schemas/identity-selection-policy.json`): one of
   `SELECTED_REGISTERED_ONLY`, `MIXED_REGISTERED_AND_NEW`,
   `NEW_ONLY`, or `AUTO_MATCH_APPROVED`, with explicit selected and
   excluded character ids. The whole registry is never auto-added;
   an approved identity is never redesigned; selection is not
   permission to invent story events. A character cannot be both
   included and excluded. `NEW_ONLY` disables registry reuse
   entirely — no registered visual reference, fixed prompt block,
   seed, or voice identity may appear in any packet of that job.
2. **Resolution is exact, never fuzzy.** A unique id is strongest;
   a unique name resolves within the authorized owner/workspace
   scope; duplicate names require the unique id; a name+id mismatch
   fails closed; unknown ids never silently create a different
   identity; there is no speculative fuzzy matching and no
   cross-workspace resolution. Error messages never leak private
   registry contents.
3. **The cast is classified, not assumed.** Every script character
   is classified as `VISIBLE_CHARACTER`, `OFF_SCREEN_SPEAKER`,
   `NARRATOR_OR_VOICE_OVER`, or `MENTIONED_ONLY`. A mentioned name
   is not a visible character; a narrator needs no image task
   unless the script requires a visible narrator; a non-speaking
   visible character needs no voice task; an off-screen speaker
   needs voice resolution, not automatic visual assets.
4. **Identity is frozen in a snapshot.** `build_identity_snapshot`
   freezes the resolved characters (reference asset ids and
   SHA-256s, model-sheet reference, fixed identity reference,
   expression references, wardrobe constraints, registry record
   version and hash), the task-local proposal ids, the voice
   selections, the cast classes, the registry snapshot version and
   hash, and the approval records, under one snapshot hash. A later
   registry change never silently mutates an approved snapshot:
   resume revalidates the snapshot against the current registries,
   and a changed record, a missing asset, or a hash mismatch stops
   the resume and reports it.
5. **Packets carry structured bindings, not just text.** Every
   image and video packet for a visible registered character
   carries an `identity_bindings` entry: character id, canonical
   reference asset ids, primary identity-reference id, model-sheet
   reference, angle-matched reference, expression reference, fixed
   identity reference, reference SHA-256, approved wardrobe/scene
   variation, and source ownership/access scope. Every speaking
   dialogue-line task carries a `voice_binding`: character id,
   voice profile id, dialogue line id, language, accent, vocal
   characteristics, pitch range, pace, pronunciation, emotional
   delivery, pauses, approved voice reference-audio asset id and
   SHA-256, provider voice id, model and version, seed, and voice
   ownership/consent evidence reference. One binding per character
   in a multi-character shot; no reference cross-contamination.
6. **Voice resolution is fail-closed.** A voice profile belongs to
   exactly one character. Exactly one eligible approved profile
   for the language and role may resolve automatically; several
   eligible profiles with no default require one clear selection;
   a default is only the character's explicit default, or the
   first entry of `voice_profile_ids` on the character.json shape
   — the first additional profile of a registration is not a
   default. A rejected, revoked, pending, mismatched, or
   unauthorized profile is never silently substituted. All P0
   voice checks (existence, character match, ownership and
   workspace, approval, consent, provider transmission disclosure,
   commercial-use restriction) are delegated to
   `scripts/asset_policy.py::resolve_voice_for_production`, never
   reimplemented.
7. **Task-local characters stay task-local.** A new character is a
   proposal with a stable job-scoped id and references; it is never
   permanently registered without the existing explicit approval
   workflow, and it never leaks into the registry or into a
   `NEW_ONLY` job's packets.
8. **Regeneration reuses the same anchors.** A QC correction or
   regeneration packet copies the original packet's identity and
   voice bindings verbatim, so a drift correction re-anchors to the
   approved reference instead of inventing a new one. A generated
   image never becomes the new anchor, and the registry is never
   updated because a generated image drifted.

## Module layout

All new identity logic lives in one module,
`runtime/identity_resolution.py` (standard library only), so the
orchestrator and compiler take only thin additive hooks:

- `load_authorized_character_registry(root, *, owner_id,
  workspace_id)` — loads the authorized private registry from an
  explicit absolute root (or the `CONSISTENCY_FRAME_CHARACTERS`
  environment variable). Refuses a missing, non-absolute, or
  symlinked root; schema-validates every record; silently excludes
  records under another owner or workspace; a duplicate character
  id is an error naming only the id. Registry files are read
  directly (`character.json` / `character-registration.json` files
  and a top-level `registry.json`); there is no second registry.
- `load_authorized_voice_registry(root, *, owner_id,
  workspace_id)` (F1) — the corresponding canonical voice path
  from the same overlay root: `voice-profile.json` files anywhere
  under the root plus a top-level `voices.json`. Same refusal,
  validation, scoping and symlink rules as the character loader;
  a root with no voice files loads as empty. `overlay_root_configured()`
  reports whether the overlay environment variable is set, and
  `scope_registry_to_session(registry, *, owner_id, workspace_id)`
  filters an explicitly supplied mapping to the session's owner
  and workspace (records without ownership pass through; the
  voice ownership check still happens at selection time).
- `resolve_character_reference(registry, *, character_id=None,
  name=None)` — the exact name/id resolution rules above.
- `resolve_project_identity_policy(policy, *, registry)` —
  validates the policy and resolves its selected ids. The
  canonical selector record `selected_characters` (F1) selects by
  exact id, exact unique name, or both (both must name the same
  record); `selected_character_ids` stays valid, and when both
  lists are supplied they must resolve to the same character set.
- `complete_auto_match_selection(*, cast, policy_resolution,
  registry, analysis)` / `enrich_analysis_for_auto_match(analysis,
  *, registry)` (F1) — the two halves of `AUTO_MATCH_APPROVED`:
  enrichment fills `registered_character_id` on name-only
  approved resolutions by exact unique name before validation,
  and completion resolves every eligible unselected cast
  reference (all classes except `MENTIONED_ONLY`) into the policy
  resolution, failing closed on duplicate names, unknown names
  and conflicting identifiers.
- `validate_new_only_inputs(*, analysis, bundle,
  character_registry, voice_registry=None, proposals=None)` (F1)
  — NEW_ONLY hardening: an approved registered resolution, a
  proposal reusing a registered reference asset, or a bundle
  voice binding naming a registered voice all fail closed,
  naming only caller-supplied references.
- `resolve_script_cast(script, analysis, bundle)` — classifies the
  script cast from dialogue, analysis resolutions, shot
  `character_ids`, and performance lines; an excluded character in
  the cast fails closed.
- `resolve_character_voice(character, *, voice_registry,
  language=None, role=None, preferred_voice_profile_id=None,
  session, commercial_use=False)` — the voice selection rules
  above, delegating all P0 checks to the asset policy.
- `build_identity_snapshot(...)` /
  `validate_identity_snapshot(snapshot, *, registry=None,
  voice_registry=None)` / `validate_resumed_identity(job, *,
  registry, voice_registry=None)` — freeze, revalidate, and
  resume-check the snapshot. `validate_resumed_identity` is called
  by the caller after `resume_production_job` returns the job,
  under the new active session.
- `identity_binding_for_character(snapshot, character_id, *,
  role=None, emotion=None)` /
  `identity_bindings_for_shot(snapshot, shot)` /
  `voice_binding_for_line(snapshot, line, *, dialogue_line_id=None)`
  — the packet binding builders used by the task compiler. The
  voice binding normalizes the performance line's pause
  direction to one string (the performance-plan schema types
  `voice.pauses` as an array, the task-packet schema types
  `voice_binding.pauses` as a string); a list joins with `"; "`.

The orchestrator hooks are `create_production_job(...,
identity_policy=None)`, `validate_job` (validates a stored policy
and snapshot structurally), `build_production_bundle(...,
identity_policy=None, character_registry=None, voice_registry=None,
proposals=None)` (resolves the effective policy, classifies the
cast, resolves registered speaking characters' voices, and stores
`job["identity_snapshot"]`), and `compile_provider_tasks` /
`build_qc_correction_tasks` (pass the stored snapshot through).
The compiler hooks are `compile_task_package(...,
identity_snapshot=None)` and `compile_regeneration_packets(...,
identity_snapshot=None)`. The snapshot rides in
`job["identity_snapshot"]`, so the production store persists it
with the job — no store changes and no second database.

## Machine-readable identity fields

The fixed prompt block and the generation seed are now
machine-readable in the canonical character records:
`schemas/character.json` and `schemas/character-registration.json`
both carry optional `fixed_prompt_block` (string) and
`generation_seed` (integer). The character-consistency skill
already required a fixed prompt block and a fixed seed per
character; the schemas now carry them as data instead of leaving
them in prose only. The project record links its policy through
the optional `identity_policy_id` field on
`schemas/project.json` (schema version `2.5` alongside the
preserved `2.3`); the policy itself is a separate record, like a
character-design proposal.

## What this runtime does not do

- It does not register characters or voices, and it does not
  change any P0 authorization rule, P1-001/002/003 protection, or
  VoiceStudio/OpenMontage internal.
- It does not score face similarity: there is no measurement
  engine in the repo, so no numerical similarity score is ever
  invented. Drift is checked by the character-consistency skill's
  angle-matched comparison, and a drifted output is marked failed
  and corrected against the same anchors.
- It does not match an identity-critical task to a provider that
  cannot support the required references. When a provider cannot
  support them, the compiler marks the mismatch and the
  orchestrator surfaces the handoff or shot-decomposition
  recommendation instead of pretending a generic prompt preserves
  the identity.
- It does not contact any host. All hosts except Muse usage remain
  untested, and no provider is claimed exercised without evidence.

## Tests

`tests/test_identity_resolution.py` covers the work order's
regression cases: name/id resolution, selection policy,
image/video binding, voice resolution, multi-character and
continuity end-to-end (including a five-character scenario and a
`NEW_ONLY` end-to-end test that asserts on actual packet
contents, not on a mode field), and registration/privacy. Valid
and invalid fixtures live in `tests/fixtures/identity-registry.json`
and `tests/fixtures/identity-voice-registry.json`; the fixture
names are synthetic test identities with no relation to any real
private registration. The suite is registered in
`tests/run-tests.sh` under the `CF-P1-004-R1-IDENTITY-*` ids.
