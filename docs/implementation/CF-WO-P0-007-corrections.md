# CF-WO-P0-007 — Final Autonomous Completion: Corrections

Work order CF-WO-P0-007 (received 2026-11-22), branch
`feat/cf-p0-safe-foundations`. Local head at start `f7fd0d5`
(P0-006 final, verified, tree clean); remote head `33dc78b8`
(61 snapshot commits, verified live via the GitHub connector).
This order completes the P0-006 architecture: timeline contract,
ownership enforcement, conditional voice validation, animal
classification, companion licensing, documentation reconciliation,
full regression, and reports/provenance. It does NOT start P1, does
NOT merge, does NOT change the PR Draft state, and does NOT touch
the Master Prompt, `main`, or VoiceStudio/OpenMontage internals.

Four part-workers ran in parallel on strictly disjoint file sets
and committed nothing; the coordinator integrated, fixed the
cross-cutting items, ran the full suite, reconciled the docs, and
regenerated the reports. No worker touched `main`, the Master
Prompt, or any P1 runtime.

## Objective

Close the five substantive gaps P0-006 left open (timeline
manifest still v2.3; generic `ownership_scope` string instead of a
structured owner/workspace contract; v2.5 voice-profile fields
optional in JSON Schema although acceptance tests expect them;
speaking-bird fixtures classified as `real-animal`; OmniVoice
CC-BY-NC recorded without a commercial-use consequence), reconcile
the documentation with the implemented contracts (§8, 15 points),
and prove the whole package with the full regression suite and
regenerated reports/manifest/provenance.

## 1. What already existed

- `schemas/timeline-manifest.json` v2.3: media references + timing
  only, with stable dialogue/shot IDs. It did not represent the
  P0-006 character/dialogue/audio/video binding contract.
- Character registration and voice profiles carried a generic
  `ownership_scope` string (free text, e.g. `"user-a"` or
  `"owner: user; workspace: this workspace only; private, never
  shared across users"`). No structured owner/workspace contract
  existed, and a voice profile was resolvable by Character ID
  alone.
- `schemas/voice-profile.json` had v2.5 fields (source, consent,
  approval, provider) but most were optional in the schema, while
  the acceptance tests expected them present.
- The Kiki speaking-parrot fixtures classified the bird as
  `real-animal` (and `character_type: "Animal"`), although the
  parrot is a generated talking character, not captured footage.
- `architecture/COMPANION_CAPABILITY_REGISTRY.yaml` recorded
  OmniVoice as CC-BY-NC but did not mark the commercial-use
  consequence: no verified commercial voice provider existed, yet
  nothing in the registry said the commercial voice adapter was
  unsupported.
- The P0-006 corrections record (§12) listed these as follow-ups;
  this order closes them.

## 2. What was contradictory

- **Timeline vs Addendum C.** Addendum C promised "one shared
  audio-visual timeline" with Character ID + reference-asset IDs +
  Voice Profile ID + Dialogue Line ID + Audio Asset ID per shot /
  line, but the timeline manifest schema (v2.3) could not express
  any of those bindings — the contract the docs described did not
  exist in the schema.
- **Ownership string vs privacy promise.** The docs promised
  owner/workspace-scoped, private-by-default characters and voices,
  but the records carried only a free-text `ownership_scope` that
  no validator could enforce and that a resolver could ignore.
- **Schema vs tests (voice).** The voice-profile schema accepted
  records the acceptance tests rejected (missing source, missing
  approval state, missing consent) — the two layers disagreed.
- **Bird classification vs the S6 rule.** The routing scenarios
  correctly treated captured real-animal footage (S6, red fox) as
  `real-animal`, but the speaking-parrot fixtures used the same
  value for a generated talking character — so "real animal" meant
  two different things in the same test suite.
- **Licence vs commercial intent.** OmniVoice was recorded
  CC-BY-NC while the user's intended production may be commercial
  YouTube work; nothing in the registry stopped a reader from
  treating a non-commercial model as a commercial provider.

## 3. What was missing

- A v2.5 timeline contract (clip/shot/audio bindings, sync
  groups, cross-reference validation) and its test suite.
- A structured ownership model with a production resolver that
  requires BOTH the Character ID + Voice Profile binding AND
  matching ownership.
- Conditional v2.5 voice validation (by source and approval
  state), with schema and validators in agreement.
- A corrected real-animal vs CGI-animal classification in all
  fixtures, plus the articulation and listening-line rules that
  follow from it.
- A recorded commercial-use decision for every companion
  capability (commercial vs technical capability kept distinct).
- Documentation that states the above accurately, without
  claiming the first-run registration UI exists (it does not —
  P0-007 is a contract + validation round).

## 4. What was changed (per Correction A–H)

### 4.1 Correction A — Timeline contract (v2.5, additive)

`schemas/timeline-manifest.json` migrated to additive v2.5
(`schema_version: ["2.3", "2.5"]`, `$id` to the v2.5 path; no
existing required field removed, renamed, or retyped; every v2.5
addition is optional):

- **(A) Identity.** `sequence_id`, project/timeline plan links,
  `frame_rate`, `resolution`, `aspect_ratio`, `timebase` enum
  (`seconds` / `frames` / `timecode`), track names.
- **(B) Video-clip binding.** `media_asset_id`, `shot_id`,
  `scene_id`, `character_ids` (array — a multi-character shot
  associates more than one Character ID), `source_media`,
  `duration_seconds`, `track_id`, `timeline_start_seconds` /
  `timeline_end_seconds`, `transition_in` / `transition_out`,
  `edit_note`.
- **(C) Audio-clip binding.** `audio_asset_id`,
  `dialogue_line_id`, `character_id`, `voice_profile_id`,
  `scene_id`, `shot_ids` (array), `audio_type` enum (`dialogue`,
  `narration`, `sound-effect`, `foley`, `ambience`, `music`,
  `other`), `language` pattern, `role` enum (`speaker`,
  `listener`, `narrator`). Music/ambience remain valid WITHOUT a
  Character ID or Voice Profile ID; intentional narration is
  permitted without a character voice binding.
- **(D) Synchronization.** `synchronization_groups[]`
  (`sync_group_id` + video/audio/dialogue/shot ID lists —
  several audio/video events associate WITHOUT renumbering the
  original IDs) and a `hierarchy` object (Project → Timeline →
  Scene → Shot → Character/Dialogue/Voice/Audio + Video Clip;
  Audio Track → Audio Clip).
- **(E) Real cross-reference validation.**
  `validate_timeline_cross_references(manifest, registry)` in
  `tests/test_timeline_manifest.py`: a Shot ID must exist in its
  shot plan; a Dialogue Line ID must exist in its performance
  plan; a Character ID must resolve to a registered or approved
  temporary character; a Voice Profile ID must resolve to the
  CORRECT Character ID; an Audio Asset ID must resolve to the
  corresponding private/approved audio asset record; a video clip
  must not reference an unrelated dialogue/character; an audio
  clip must not silently switch to another character's voice.
  Registry sections that are absent are skipped; a section that
  is present is authoritative. `media_asset_id` is deliberately
  NOT resolved — no media registry exists in this work order.
- **(F) Backward compatibility.** New fixtures
  `tests/fixtures/timeline-valid-v23.json` (valid legacy, no v2.5
  fields) and
  `tests/fixtures/timeline-valid-v25-multicharacter.json`
  (two-speaker, sync group + hierarchy). The 14 work-order cases
  are the test suite (single human speaker sync; two characters,
  separate voice profiles; human + CGI bird, one scene; narrator
  with no visible character; music/ambience without character
  bindings; one dialogue line across several shots; several visual
  shots + one audio asset; missing Shot ID; missing Dialogue Line
  ID; Voice Profile belonging to the wrong Character ID; invalid
  Audio Asset ID; inconsistent sync-group references; valid legacy
  v2.3 timeline; valid v2.5 non-dialogue video timeline) —
  `tests/test_timeline_manifest.py`, 34 PASS lines, plus pins
  (approved-temporary resolves; music binding a dialogue line
  fails; a v2.3 record with a v2.5-only field still validates).
  Runner entry `CF-P0-007-AC-TIMELINE` added to
  `tests/run-tests.sh`.

**Validator-subset gap (documented, not silent).**
`scripts/validate-repo.py` supports only `type` / `properties` /
`required` / `enum` / `pattern` / `minLength` / `minimum` /
`maximum` / `exclusiveMinimum` / `minItems` / `items` /
`additionalProperties` — NO `if`/`then`, `allOf`/`oneOf`,
`$ref`, `dependentRequired`. No conditional rule lives in any
schema; cross-field rules are enforced semantically in Python
(the same pattern `tests/test_schemas.py` already uses). This gap
is recorded in the test file's docstring, in both schema
descriptions, and in `scripts/asset_policy.py`.

### 4.2 Correction B — Private character and voice ownership

Structured ownership, implemented verbatim in both schemas
(same property order and content):

```json
{"ownership": {"owner_id": "<pattern ^[a-z0-9][a-z0-9\\-]{2,63}$>",
                "workspace_id": "<same pattern>",
                "visibility": "private" | "shared",
                "sharing": "none" | "workspace" | "explicit"}}
```

All four fields required, `additionalProperties: false`.
`character-registration.json` is v2.5-only, so `ownership` is
REQUIRED there; `ownership_scope` is kept as an optional
legacy/deprecated string and removed from `required`.
`voice-profile.json` carries the same `ownership` object
(optional in the schema — see §4.3 — because v2.3 profiles must
stay valid). Owner IDs are stable, opaque, randomly generated
local identifiers — never real names, emails, or account details.
Test IDs: `owner-a` / `owner-b`, `workspace-a` / `workspace-b`.

`scripts/asset_policy.py` gains `validate_ownership`,
`ownerships_match`, `ownership_allows_access`,
`resolve_voice_for_production` (production resolver),
`validate_private_voice_export`,
`validate_release_manifest_paths`, and `resolve_private_path`
(traversal + symlink-escape rejection). Existing
functions/signatures are untouched.

**The resolver rule (both conditions, no exceptions).** A Voice
Profile resolves for production only when (1) the Character ID +
Voice Profile binding matches AND (2) the character's ownership
and the voice profile's ownership match. Same Character ID with
a different owner or workspace is REJECTED. Also rejected: voice
assigned to the wrong Character ID; voice from another workspace;
voice from another local owner; unapproved/inaccessible private
asset; private asset accessed outside its permitted scope.
Private by default; a character never becomes public merely
because an image was uploaded; shared access requires an explicit
future sharing permission; temporary asset use never silently
becomes permanent registration. No cross-user sharing by default.
Local-first: the existing local/private overlay architecture,
filesystem permissions + safe path validation where supported;
no path is called private merely because it sits in a folder
named `private`; no private media binaries in public GitHub; no
server/API/cloud database for owner/workspace separation.
External provider transmission is disclosed, requires user
approval, and records provider + data-use scope; provider
retention/privacy limits are respected, and no "never leaves the
device" promise is made.

B security tests (36 checks, all PASS, in
`tests/test_character_registration.py` and
`tests/test_private_overlay.py`): Owner-A resolves / Owner-B
rejected / same-owner-wrong-workspace rejected / no cross-user
sharing by default / `sharing: workspace` admits the same
workspace but rejects another / voice owned by another user or
workspace rejected / correct Character ID but mismatched
ownership rejected / cross-character assignment rejected /
private voice export blocked without auth, blocked with partial
auth, allowed with full explicit auth / private media excluded
from release manifests (including a smuggled-path manifest) /
path traversal rejected (`../`, absolute, `a/../../b`, empty,
`//`) / safe private path resolves / symlink escape rejected,
in-base symlink resolves / "private"-folder-name never decides
access or releasability / temporary use never becomes permanent /
upload never makes a character public / `shared` without sharing
permission rejected / owner IDs must be opaque (name/email
rejected).

### 4.3 Correction C — Conditional v2.5 voice validation

Because the repo validator cannot express conditional-required
(see §4.1), JSON Schema stays permissive for v2.5 conditional
fields and `asset_policy.validate_voice_profile` enforces them
when `schema_version == "2.5"` (v2.3 records exempt; records
without `schema_version` get base rules only). "Fully valid
v2.5" = schema AND Python both pass; every C case pins both
layers' verdicts explicitly, so a v2.5 profile missing
`ownership` / `source` / `voice_profile_id` / etc. is
**schema-valid but Python-invalid** — asserted, not silent.
True agreement holds wherever the schema can express the rule
(enums, patterns, types — e.g. a bad `owner_id` pattern or
`visibility: "public"` are rejected by both layers).

Minimum v2.5 required fields: `voice_profile_id`,
`character_id`, `source`, explicit owner/workspace binding,
appropriate voice asset references, appropriate approval state,
appropriate consent state. Governing definitions:
**`consent_status` governs** (must agree with
`consent.granted`); **provider** governs the provider ID,
**model** governs the model ID (model and/or `model_version`
required); `approval_status` must exist and agree with `status`
(approved ⟺ approved, never automatic);
`not-required` is legitimate only with
`human_voice_donor: false`.

- **(A) user-recording.** At least one approved audio reference
  asset must exist; consent explicitly granted; owner/workspace
  must match the associated character; identifiable Character ID;
  must not be usable for another character.
- **(B) ai-generated.** Provider identification must exist;
  model identification when available; approval status must
  exist; a generated voice must NOT become approved automatically
  before required user review; an approved profile is required
  for final production use; if a real-person voice donor/cloned
  voice was used, explicit permission + consent are handled; if
  no real-person donor was involved, the no-human-donor condition
  is accurately recorded (`human_voice_donor: false` legitimises
  `consent_status: "not-required"`) — `not-required` is NEVER
  used to bypass an actual permission requirement.
- **(C) Draft/pending/approved.** Generated/recorded sample vs
  pending user review vs approved voice profile vs
  rejected/deprecated are distinct; ONLY an approved, correctly
  owned profile may be selected for production when approval is
  required; sample-generation success is not user approval. (The
  in-test §5 `validate_voice_profile` keeps its contract but now
  treats `approval_status: pending` as a legitimate state —
  production approval is the resolver's job, not validity — and
  adds consent-agreement/donor/status-agreement rules.)
- **(D) Version-aware.** A v2.5 profile enforces its v2.5 fields;
  a v2.3 profile remains valid under the legacy contract. No new
  field was added to the global `required` array.
- **(E) Agreement.** JSON Schema, `scripts/validate-repo.py`,
  `scripts/asset_policy.py`, character registration tests,
  production direction tests, the voice binding resolver, and the
  timeline cross-reference validator all agree: a record the
  custom validator rejects is never described as fully
  schema-valid, and a record JSON Schema accepts never bypasses a
  stricter security/ownership rule.

C tests (39 checks in `test_character_registration.py` + 16
agreement checks in `test_schemas.py`, all PASS): positives —
valid v2.5 user-recorded (approved + granted + matching
ownership), valid v2.5 AI-generated (approved, provider+model,
no-human-donor), valid v2.3 legacy still passes; negatives —
missing Voice Profile ID, missing source, missing owner/
workspace, user recording without audio reference, user
recording without granted consent, AI-generated without provider,
without approval state, without model ID, unauthorized
real-person sample (donor claimed `not-required`),
`not-required` without donor flag recorded, status approved
without approval record, bad `owner_id` pattern (both layers
reject), `shared`+`none`, undisclosed provider transmission,
pending profile used as approved production voice (record valid,
resolver rejects), voice bound to another character, voice bound
to another workspace. All valid v2.3 fixtures + historical
records preserved.

### 4.4 Correction D — Real animal vs CGI/AI animal classification

10 fixtures corrected (Kiki the speaking parrot `real-animal` →
`cgi-animal`; `character-registration-valid-bird.json`
`character_type` `"Animal"` → `"CGI Animal"`):

- `tests/fixtures/performance-plan-valid-bird.json`
- `tests/fixtures/performance-plan-bird.json`
- `tests/fixtures/character-valid-v25-animal.json` (also fixes
  its internal contradiction vs the provenance note "CGI parrot
  created for this series; not footage of a real bird";
  `is_live_action_footage: false` kept)
- `tests/fixtures/performance-plan-two-person.json` (2
  occurrences)
- `tests/fixtures/scene-plan-two-person.json`
- `tests/fixtures/scene-plan-valid-human-bird.json`
- `tests/fixtures/shot-plan-directed.json` (2 occurrences)
- `tests/fixtures/shot-plan-valid-human-bird.json`
- `tests/fixtures/performance-plan-invalid-bird-human-lips.json`
  (`subject_kind` fixed; articulation kept
  `human-mouth-lips`, so it REMAINS invalid)
- `tests/fixtures/character-registration-valid-bird.json`
  (character type only; ownership added at integration, §4.8)

The S6 red fox is now the ONLY `real-animal` left in
`tests/fixtures/` (verified correct, unchanged); S4 was already
`cgi-animal`. No routing/semantic/skill changes were needed —
the skills already stated the correct distinction, and
`test_performance_semantics.py` has no Kiki assertion.

9 acceptance cases, 37 checks, 0 failures: (1) genuine captured
parrot = `real-animal`; (2) generated talking parrot =
`cgi-animal`; (3) generated parrot may use its registered
character-specific voice; (4) articulation target bird-beak;
(5) bird may NOT use human-mouth-lips; (6) real animal not
automatically given fictional dialogue; (7) human speaking to a
genuine animal handled correctly; (8) human speaking to a CGI
talking bird handled correctly; (9) hybrid live-action human +
CGI bird routed correctly. **Case-9 wording note:** S4 is a
digital-human + cgi-animal bird production, NOT a live-action
human; S5 (`routing-profile-s5-live-action-creature.json`) is
the true live-action-human + CGI-creature hybrid — the worker
asserted correctly and no fixture was altered to fit the
wording.

### 4.5 Correction E — Companion licensing and capability accuracy

Licence evidence verified (2026-11-22):

- **VoiceStudio app code: AGPL-3.0** — commercial use of the app
  itself permitted (`components/voicestudio/LICENSE`,
  `LICENSE-NOTICE.md`, upstream README "AGPL-3.0 app").
- **OmniVoice model weights: CC-BY-NC (non-commercial only).**
  Live Hugging Face model card
  https://huggingface.co/k2-fsa/OmniVoice (fetched 2026-11-22):
  "Our code is released under the Apache 2.0 License. The
  pre-trained model is licensed under the CC-BY-NC due to
  constraints from its training data (e.g., Emilia)" (CC version
  unspecified). Corroborated by
  `components/voicestudio/LICENSE-NOTICE.md` and
  `components/voicestudio/backend/config/model_licenses.json`
  (licence "CC-BY-NC (version unspecified); Higgs Audio 2; Meta
  Llama 3", `commercial_use: false`, `review_status:
  noncommercial`, commercial inference restricted, commercial
  outputs unknown, pinned revision
  `c5fdb5ccb189668d56333f77ba2629f4cd7535f4`). The GGUF variant
  `Serveurperso/OmniVoice-GGUF` is **CC-BY-NC-4.0** per local
  sources only (live fetch failed HTTP 429 after 3 attempts, not
  retried; pinned revision
  `361609388ae572a820d085185bbbe2a2aac4b30e` per
  `quant_map.json`).
- **Bundled `omnivoice/` package: Apache-2.0 code only** (does
  not clear CC-BY-NC weights); GGUF runtime `omnivoice.cpp` MIT;
  audio tokenizer separate Boson Higgs Audio 2 + Meta Llama 3
  terms, `component_closure: incomplete`,
  `commercial_outputs: unknown`.

Registry changes (`architecture/COMPANION_CAPABILITY_REGISTRY.yaml`,
+72 insertions, 0 deletions, additive only): a header
COMMERCIAL-USE RULE comment (`commercial_use_approved: false` =
not cleared — either a noncommercial licence or unverified;
monetised/commercial YouTube needs a verified commercial
provider — none exists, commercial voice adapter unsupported);
VoiceStudio companion `licence_scope` (app code only) +
`commercial_use_approved: false` / reason
`noncommercial_licence` + a new `models:` list (4 entries:
k2-fsa/OmniVoice, Serveurperso/OmniVoice-GGUF, bundled
omnivoice package, audio tokenizer — each with provider + model
version/revision, code vs weights licence,
`commercial_use_approved`, reason, evidence); TTS capability
(OmniVoice engine) + zero-shot voice cloning:
`commercial_use_approved: false` / `noncommercial_licence`
("TECHNICALLY CAPABLE (exercised_recorded_run) but NOT
COMMERCIALLY APPROVED … Non-commercial / test use only");
additional TTS engines: `false` / `unverified` (all 73 models in
`model_licenses.json` have `commercial_use: false`; all but five
noncommercial ones are `review_status: unreviewed` metadata
labels only); VoiceStudio `explicitly_not_claimed` +3 bullets;
OpenMontage companion: `licence_scope` (AGPL-3.0 app code;
bundles no model weights) + `commercial_use_approved: false` /
`unverified` (no paid route exercised or terms-verified; no
rendered video produced); paid third-party provider routes:
`false` / `unverified`; OpenMontage `explicitly_not_claimed` +1
bullet. **No verified commercial voice provider exists** — none
was invented. `production_verified` count stays 0.

**Open item — licence conflict inside VoiceStudio's own docs.**
`components/voicestudio/backend/engines/omnivoice_gguf/README.md`
claims the GGUF weights are Apache-2.0 ("Same license as the
upstream…"), contradicting `model_licenses.json`,
`model-credits.md`, and `docs/engines/omnivoice-gguf.md` (all
CC-BY-NC / noncommercial only). The restrictive record governs;
the Apache-2.0 claim was NOT adopted. This needs a
VoiceStudio-upstream check; VoiceStudio internals were not
modified. Other unverified registry claims were NOT silently
fixed: OpenMontage AGPL-3.0 rests on local LICENSE + README badge
only; the "646 languages" claim remains
`upstream_inspected_pinned_commit` (headline only, count
unverified); all `present_locally` capabilities are not
exercised; five other noncommercial models are noted but have no
individual registry entries. Consistent with the existing doc
statements: `skills/voice-consistency/SKILL.md` §3 and
`architecture/SKILL_ROUTING_MATRIX.yaml` already state the
CC-BY-NC noncommercial rule — no doc edit was needed from W4.

### 4.6 Correction F — Documentation and product contracts

Reconciled: `README.md`, `AGENTS.md`,
`docs/07-character-registry.md`, `docs/19-audio-delivery-profiles.md`
(no change needed — loudness profiles only, no voice-profile
content), `docs/architecture/ANIMATION_SCOPE_AND_PRODUCTION_MODES.md`,
`docs/implementation/CF-WO-P0-006-corrections.md` (short
follow-up pointer in §12, additive only — no history rewritten),
`docs/implementation/BUILD_REPORT_P0.md` (regenerated, §4.7),
`docs/implementation/P0_UPDATED_IMPLEMENTATION_PLAN.md`
(§9 P0-006 marked complete, new §10 P0-007),
`schemas/README.md`, and the relevant skills/architecture files
(voice-consistency §3 and the routing matrix already stated the
CC-BY-NC rule; no change needed there).

The §8 15-point mapping:

1. Reference video optional — already in the canonical doc §C1
   and README; unchanged, still true.
2. Script-only production planning supported — Path B, already
   documented; unchanged.
3. Supplied reference images associated with registered
   characters — §C4; unchanged.
4. Temporary use vs permanent registration — docs/07 +
   §C2; unchanged, plus the structured-ownership note in docs/07.
5. Character ID persistent + unique — §C3 table; unchanged.
6. Registered character images stay with the same identity —
   §C4; unchanged.
7. Every approved Voice Profile linked to its correct Character
   ID — §C7 + the new conditional validation in §C5.
8. Character/voice ownership private + workspace-scoped — §C6
   strengthened (structured `ownership`, both-conditions
   resolver rule) + new Ownership row in the §C3 table.
9. User-recorded vs AI-generated voice profiles follow different
   validation rules — NEW in §C5 (conditional validation
   subsection).
10. Voice/Profile data not publicly shared by default — §C6;
    unchanged.
11. Real animals distinct from generated/CGI animals — §6
    already distinguishes them; sharpened with an explicit
    sentence (a real animal is never automatically given
    fictional dialogue or a speaking voice — a speaking animal
    is a `cgi-animal` / `anthropomorphic` subject) and the
    fixtures corrected (§4.4).
12. Human lips vs bird beaks vs other creature articulation
    different — §7.2 / §C8; unchanged.
13. Every relevant dialogue + shot bound to the shared timeline
    — §C11 updated to the v2.5 contract + the contract table row.
14. Camera movements + focus motivated by scene requirements —
    §C10; unchanged.
15. P0 contracts do not mean P1 runtime is complete — stated in
    repo `AGENTS.md` (P0-007 section) and the implementation
    plan §10.

**Do NOT claim the first-run registration UI exists.** It does
not. P0-007 is principally a contract + validation correction
round; the implemented-architecture vs future-runtime
distinction is explicit in `AGENTS.md`, the implementation
plan, and §5 below.

### 4.7 Correction G — Tests, validation, regression

See §6 (full results). Runner gains
`CF-P0-007-AC-TIMELINE`. All previous installer security tests
kept (SEC-01..08, SEC-MANIFEST-01..04, SEC-METADATA-05..07,
CF-P0-ATOMIC-001..006). The §9B inventory is covered: installer
security, manifest traversal/symlink protections, atomic writes,
false SUCCESS prevention, metadata failure diagnostics, v2.3
backward compat, v2.5 voice validation, character registration,
character reference resolution, Character–Image binding,
Character–Voice binding, owner isolation, workspace isolation,
private media restrictions, CGI-animal vs real-animal
classification, subject-specific articulation, multi-character
performance, timeline synchronization, audio/video handoff
contracts, cinematography direction, production report
consistency, registry generation.

### 4.8 Integration fixes (coordinator, beyond the four workers)

1. **`character-registration-bird-valid.json` (char-002).**
   Not in W3's file list and not in W2's: it still carried
   `character_type: "Animal"` and no `ownership` object. Fixed:
   type → `"CGI Animal"`; `ownership` added (`owner-a` /
   `workspace-a`, `private`, `none`); `ownership_scope`
   kept as legacy (W2 kept it in the other fixtures).
2. **`character-registration-valid-bird.json` (char-kiki-001).**
   W3 had fixed its type to `"CGI Animal"`; W2 had left it
   without ownership. `ownership` added (same values);
   `ownership_scope` kept as legacy. Both of W2's SKIPs
   (one in `test_character_registration.py`, one in
   `test_schemas.py`) now disappear — the suite runs with
   **0 skipped**; the checks un-skip automatically and PASS.
3. **`articulation_fits_subject()` species matching**
   (`tests/test_production_direction.py`). Pre-existing quirk:
   it recognised only the exact species strings `"parrot"` /
   `"bird"`, so `"African grey parrot"` fell through to
   `animal-muzzle`. Fixed to substring matching (same rule the
   schema-side check in `test_schemas.py` already uses), with a
   regression check in the Correction D case-4 test. W3's
   workaround NOTE in that test is replaced by the pin.
4. **Listening-line voice rule**
   (`validate_performance_line()`). Pre-existing quirk: it
   required `voice_profile_id` on EVERY line, including
   listening lines — so a genuine-animal listening line with no
   voice passed only the new classification validator, not the
   full line validator (the two validators disagreed). Fixed:
   a speaking line MUST carry a voice profile; a
   listening/silent/reacting line MAY omit one (a genuine animal
   listener has no speaking voice at all), but a voice profile
   that IS present must still resolve to the right character.
   Correction D case 7 now asserts the genuine-animal listening
   line (no dialogue, no voice) passes BOTH the classification
   rule AND full line validation, and that a speaking line
   without a voice profile still FAILS.
5. **`tests/test_schemas.py` Kiki binding line.** The inline
   dict used `subject_kind: "real-animal"` for the Kiki binding
   articulation check; changed to `"cgi-animal"` (passes either
   way — both kinds allow bird-beak — but the record must say
   what Kiki is).
6. **Runner.** `CF-P0-007-AC-TIMELINE` entry added to
   `tests/run-tests.sh` (workers were told not to touch it).

## 5. P0 vs P1 separation

P0-007 completes architecture / security / schemas / validation /
tests / reports / GitHub readiness ONLY. Still P1 (not started,
not claimed): first-run registration UI; actual persistent
registration workflow; actual image upload/reference retrieval;
actual voice recording interface; actual AI voice
creation/approval interface; actual reusable per-character voice
generation; real image/video generation provider execution;
actual image-to-video/video-to-video; actual lip-sync/beak-muzzle
articulation generation; real facial/body animation execution;
actual camera-motion/focus generation; actual VoiceStudio handoff
execution; actual OpenMontage editing/rendering; complete
automated script-to-finished-video runtime. No P1 item was
converted to P0 by writing a contract or a mock. No new
backend/cloud service was started; nothing was deployed.

## 6. Test results

Final integrated run (coordinator, 2026-11-22, branch
`feat/cf-p0-safe-foundations`; all commands run from the repo
root, before the reports/provenance commit):

- `bash tests/run-tests.sh` → exit 0. **48 recorded entries,
  all PASS; 36 distinct test IDs; 29 distinct command strings;
  0 failures, 0 skipped.** (P0-006: 47 / 35 / 28. The +1 entry
  is the new `CF-P0-007-AC-TIMELINE` runner entry.)
- Per-file PASS lines (each file exit 0, 0 failures):
  `validate-repo.py` 7 checks; `generate-registries.py --check`
  OK (15 skills / 165 features / 13 workflows / 12 adapters);
  `test_schemas.py` 91; `test_routing.py` 305;
  `test_registries.py` 261; `test_performance_semantics.py` 32;
  `test_character_registration.py` 140 (0 skipped — the two
  bird-fixture skips from the part work are gone);
  `test_production_direction.py` 132;
  `test_private_overlay.py` 28; `test_timeline_manifest.py` 34
  (new); `test_modes.py` 32; `test_reports.py` 37.
- `bash -n scripts/sync-skills.sh`, `bash -n setup.sh`,
  `bash -n tests/run-tests.sh` → all OK.
- `python3 scripts/validate-repo.py` → `VALIDATE-REPO: PASS`
  (schemas, skill_frontmatter, registries, private_overlay,
  secret_scan, absolute_claims, yaml_records).
- `python3 scripts/generate-registries.py --check` → `CHECK OK:
  registries match the live repo`.
- `git diff --check` → clean.
- `bash setup.sh --dry-run` → exit 0, `Setup SUCCESS:
  skills=SUCCESS voicestudio=SKIPPED openmontage=SKIPPED`
  (core-only default; components not installed; the OmniVoice
  model is never downloaded by `setup.sh`). Safe environment /
  isolated fixtures only — never against the user's actual
  environment. `--with-components` end-to-end was NOT run (still
  true since P0).

No test was reported PASS unless executed with the expected
successful result; no skipped test was counted as passed; no
count was invented. The `tests/last-run.json` written by the
final run is the recorded evidence (SHA-256
`03bcf746e8e0321a723cfa48e6ba40fef07257586b0b09faa6917283052b8309`).

## 7. Validation (integrated run)

- The full suite was run once after all four part-workers
  reported, then again after the coordinator's integration fixes
  (§4.8) — both runs green, 48/48.
- Part-worker verification (each from the repo root, exit 0):
  W1 timeline — `test_timeline_manifest.py`, `test_schemas.py`,
  `validate-repo.py`; W2 ownership/voice —
  `test_character_registration.py` (139 PASS, 0 FAIL, 1 SKIP at
  that point — the bird fixture, fixed at integration),
  `test_private_overlay.py` (28 PASS), `test_schemas.py`
  (90 PASS, 0 FAIL, 1 SKIP at that point),
  `validate-repo.py`, plus `test_modes.py` (shared
  `asset_policy` module); W3 animal classification —
  `test_production_direction.py`,
  `test_performance_semantics.py`, `test_routing.py`,
  `test_schemas.py`; W4 licensing — `validate-repo.py`
  (incl. `yaml_records`), `generate-registries.py --check`,
  YAML parse.
- No test, count, or CI claim in this record is made for a run
  that has not finished. Remote CI is the parent's step, after
  pushing (two-head rule, §8).

## 8. Reports, release manifest and provenance

- Generators were inspected (`--help` / usage text) before use.
  Registries were regenerated only if canonical Skill /
  architecture data changed — `generate-registries.py --check`
  passes, so no regeneration was needed (the companion-registry
  YAML change is not a canonical registry input).
- `scripts/generate-build-report.py --github-head <live head>`
  regenerates `BUILD_REPORT_P0.md`, `build-report.json`,
  `release-manifest.json`, and `docs/implementation/CHECKSUMS.txt`;
  `scripts/generate-report.py` regenerates the living
  architecture report. The `--github-head` value used was the
  live head verified at the start of this order (`33dc78b8`);
  the parent re-runs provenance after pushing. No future SHA was
  recorded; no GitHub CI pass was claimed before the relevant run
  finishes.
- Two-head rule preserved: the manifest records the actual source
  code head and the actual GitHub branch head; the delivery
  message states both. No circular/self-referential manifest
  hashing: `release-manifest.json` is excluded from its own
  `files` list; it IS listed in `build-report.json`'s
  `changed_files` (names, not hashes). The project's actual
  manifest/checksum verification was run; the file count and the
  hash-verification result are recorded in the release manifest,
  `CHECKSUMS.txt`, and the delivery report to the parent.
- The P0-006 Part A evidence constants in the report generators
  (latest verified CI: push run #47 + PR run #48 on `24d2e62`)
  are superseded by the P0-006 final CI (push run #83 + PR run #84
  on `33dc78b8`, 47 recorded entries, 35 distinct test IDs, 28
  distinct command strings, all PASS — see the delivery report);
  the generators were updated accordingly before regeneration.

## 9. Remaining limitations + unresolved decisions

1. **Validator subset.** The repo validator cannot express
   conditional requirements (`if`/`then`, `allOf`, `dependentRequired`).
   Conditional v2.5 voice rules live in Python
   (`scripts/asset_policy.py`) and are pinned by tests. If the
   validator is ever extended, the schema should carry the
   conditionals and the two layers re-verified for agreement.
2. **VoiceStudio GGUF licence conflict** (§4.5): the GGUF
   engine README claims Apache-2.0 for the weights; every other
   record says CC-BY-NC. The restrictive record governs; the
   conflict needs a VoiceStudio-upstream check.
3. **GGUF live evidence incomplete.** The
   `Serveurperso/OmniVoice-GGUF` CC-BY-NC-4.0 licence rests on
   local sources only — the live Hugging Face fetch failed HTTP
   429 after 3 attempts and was not retried.
4. **OpenMontage AGPL-3.0** rests on local LICENSE + README badge
   only; no paid route exercised or terms-verified; no rendered
   video produced. Its commercial status stays `unverified`.
5. **"646 languages"** remains `upstream_inspected_pinned_commit`
   (headline only, count unverified).
6. **No verified commercial voice provider exists.** The
   commercial voice adapter stays unsupported until a provider
   with genuinely verified commercial licence terms is found.
7. **Counts.** 109 distinct systems / 120 numbered entries and
   the registry's 165 derived features keep their existing
   reconciliation note; count reconciliation remains deferred
   (P1, per the implementation plan §5).
8. **"Made for Kids" and child-safety rules** are unchanged by
   this order; the kids & family skill's reference library
   remains verified-records-only (R-01–R-19).
9. **The referenced "End-to-End Script-to-Finished-Video
   Addendum"** was not found on disk when P0-006 began and has
   still not appeared; this order proceeds with P0-006 +
   Addendum C + P0-007 as given. If it appears, it is reconciled
   separately.
10. **First-run registration UI, persistent registration
    workflow, voice recording / AI voice creation interfaces,
    provider execution, and the script-to-finished-video runtime
    are P1** (§5). P0-007 proves contracts, not runtime.
11. **NOT approved for merge.** This order does not mark anything
    merge-ready; a separate independent review must approve the
    EXACT head before any merge, and the PR stays Draft until the
    parent changes it after verifying CI.

## 10. Architecture decision record (summary)

- **ADR-1 — Timeline v2.5 is additive, not a rewrite.**
  Preserving every valid v2.3 record was non-negotiable (the
  repo's additive-evolution rule); all v2.5 additions are
  optional, and version-specific requirements are conditional.
- **ADR-2 — Conditional rules live in Python, not in the
  schema.** The stdlib validator's restricted subset cannot
  express them; putting `if`/`then` in a schema would fail
  `validate-repo.py`. The schema stays permissive where it
  cannot express a rule, the Python validator enforces it, and
  the tests pin both layers' verdicts so the disagreement is
  explicit, never silent.
- **ADR-3 — Ownership is structured, opaque, and
  both-conditions.** A free-text scope string cannot be enforced;
  opaque IDs carry no personal data; and Character-ID-only
  resolution was the actual leak (same ID, different owner).
  Both conditions must match.
- **ADR-4 — Restrictive licence record governs.** Where
  VoiceStudio's own docs contradict each other on the GGUF
  weights, the noncommercial record governs and the conflict is
  flagged, not resolved by picking the convenient claim.
- **ADR-5 — No capability without evidence.** Technical
  capability (`exercised_recorded_run`) and commercial approval
  are separate fields; nothing is marked `production_verified`
  without an actual recorded production run. Count stays 0.

## 11. Files changed

- **Correction A (timeline):**
  `schemas/timeline-manifest.json`,
  `tests/test_timeline_manifest.py` (new),
  `tests/fixtures/timeline-valid-v23.json` (new),
  `tests/fixtures/timeline-valid-v25-multicharacter.json` (new),
  `tests/run-tests.sh` (runner entry).
- **Corrections B + C (ownership + voice validation):**
  `schemas/character-registration.json`,
  `schemas/voice-profile.json`, `scripts/asset_policy.py`,
  `tests/test_character_registration.py`,
  `tests/test_private_overlay.py`, `tests/test_schemas.py`
  (voice/ownership sections),
  `tests/fixtures/character-registration-valid.json`,
  `tests/fixtures/character-registration-valid-human.json`,
  `tests/fixtures/voice-profile-valid-user-recorded.json`,
  `tests/fixtures/voice-profile-valid-ai-generated.json`.
- **Correction D (animal classification):**
  `tests/fixtures/performance-plan-valid-bird.json`,
  `tests/fixtures/performance-plan-bird.json`,
  `tests/fixtures/character-valid-v25-animal.json`,
  `tests/fixtures/performance-plan-two-person.json`,
  `tests/fixtures/scene-plan-two-person.json`,
  `tests/fixtures/scene-plan-valid-human-bird.json`,
  `tests/fixtures/shot-plan-directed.json`,
  `tests/fixtures/shot-plan-valid-human-bird.json`,
  `tests/fixtures/performance-plan-invalid-bird-human-lips.json`,
  `tests/fixtures/character-registration-valid-bird.json`,
  `tests/test_production_direction.py`.
- **Correction E (licensing):**
  `architecture/COMPANION_CAPABILITY_REGISTRY.yaml`.
- **Correction F (docs):** `README.md`, `AGENTS.md`,
  `docs/07-character-registry.md`,
  `docs/architecture/ANIMATION_SCOPE_AND_PRODUCTION_MODES.md`,
  `docs/implementation/CF-WO-P0-006-corrections.md` (§12
  pointer), `docs/implementation/P0_UPDATED_IMPLEMENTATION_PLAN.md`,
  `schemas/README.md` (plus regenerated `BUILD_REPORT_P0.md`,
  §4.7).
- **Integration (§4.8):**
  `tests/fixtures/character-registration-bird-valid.json`,
  `tests/fixtures/character-registration-valid-bird.json`,
  `tests/test_production_direction.py` (articulation substring
  fix, listening-line voice rule, case-7 strengthening),
  `tests/test_schemas.py` (Kiki binding line).
- **This record + changelog:**
  `docs/implementation/CF-WO-P0-007-corrections.md` (new),
  `CHANGELOG.md`.
- **Reports/provenance (§8, generated):**
  `docs/implementation/BUILD_REPORT_P0.md`,
  `docs/implementation/build-report.json`,
  `release-manifest.json`, `docs/implementation/CHECKSUMS.txt`,
  `docs/architecture/living-architecture-report-v2.4-p0.md`,
  `tests/last-run.json`.
