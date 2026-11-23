# CF-WO-P0-012 — Public Installation Guidance Correction & Regression Protection

**Work order:** CF-WO-P0-012
**Date:** 2026-11-23
**Branch:** `feat/cf-p0-safe-foundations`
**Previous head (P0-011 delivered):** `83b1be0` (remote `a9748880`)
**Scope:** documentation correction + automated regression test only. No
installer behaviour changed. No component installed. No model downloaded.
No skill changed. No P1 work started.

## 1. Original discrepancy

During the P0-011 independent package review, the reviewer found that
the README's Installation section describes a different install than
`setup.sh` actually performs. The README told new users that running
`bash setup.sh` automatically installs VoiceStudio and OpenMontage and
walks them through downloading the voice model. The implementation does
none of that by default.

### Exact incorrect statements (pre-fix README.md)

1. **Install section** (the first paragraph a new user reads):

   > "`setup.sh` fetches and installs the bundled components
   > (VoiceStudio for voice, OpenMontage for long-form video)
   > automatically — no separate install is needed — and copies the
   > skills into `.agents/skills/`, so any platform that reads skills
   > from that directory picks them up automatically. It also walks
   > you through downloading the voice model (see [Voice](#voice))."

   Every clause of this is wrong for the default run: `setup.sh` does
   not fetch or install the components by default, a separate install
   step (`--with-components`) IS needed for them, and it does not walk
   the user through downloading the voice model (the default run never
   mentions the model download at all).

2. **Voice section:**

   > "Voice work runs through VoiceStudio, bundled as a component
   > (`components/voicestudio`, cloned by `setup.sh`), with the
   > OmniVoice model for zero-shot voice cloning across 600+
   > languages."

   "Cloned by `setup.sh`" without qualification reads as a default
   behaviour. The clone happens only with the opt-in
   `--with-components`.

3. **Voice section, model bullet:**

   > "The OmniVoice model weights (~3.2 GB) are **not** bundled in
   > this repo. `setup.sh` walks you through downloading them from
   > the original Hugging Face source (`k2-fsa/OmniVoice`) at install
   > time — you run the download step yourself."

   The first sentence is true; the second is false. `setup.sh` never
   downloads the model, and the default run does not even print the
   download steps — they are printed only in the all-SUCCESS final
   summary of a `--with-components` run (see §2).

4. **Voice section, OpenMontage bullet:**

   > "Long-form video runs through OpenMontage, bundled as a component
   > (`components/openmontage`, cloned by `setup.sh`), which stitches
   > short clips into long episodes."

   Same unqualified "cloned by `setup.sh`" as (2).

5. **Windows — Git Bash note:**

   > "If `make --version` reports nothing in Git Bash, the OpenMontage
   > step in `setup.sh` will say so; use WSL for that step."

   Implies an OpenMontage step runs in a plain `bash setup.sh`. It
   runs only with `--with-components`.

6. **Licence section:**

   > "Bundled components keep their own licences: VoiceStudio and
   > OpenMontage are **AGPL-3.0** (included as bundled components,
   > cloned by `setup.sh`, licences intact), and the OmniVoice model
   > is **CC-BY-NC (noncommercial)** (downloaded at install, weights
   > not bundled)."

   "Cloned by `setup.sh`" (unqualified) and "(downloaded at install)"
   — the latter reads as part of the install the script performs.

## 2. Root cause

The README was written when the install story was told as one command
that does everything. The implementation was later made core-only by
default (P0 safe foundations: `setup.sh` is core-only, components are
opt-in, per-component truthful status), and `docs/06-installation.md`
was updated to describe that split correctly — but the README's
Install, Voice, Windows-note, and Licence passages were never
reconciled with it. There was also no automated check tying the README
to the installer, so the drift survived eleven rounds of review.

Verified implementation behaviour (`setup.sh`, read in full):

- `WITH_COMPONENTS=0` (line 39) — the default.
- `--with-components` sets `WITH_COMPONENTS=1` (line 46);
  `--core-only` resets it to 0 (line 45).
- Default run: skill sync only (`scripts/sync-skills.sh`), then:
  "Core install done. Components were NOT installed (default). / To
  also install VoiceStudio + OpenMontage, run: / `bash setup.sh
  --with-components` / The voice model (OmniVoice, CC-BY-NC) is never
  downloaded by setup.sh; install it separately when you need it"
  (lines 87–96), exit 0.
- Header comment (lines 4–19): core = "Non-destructive skill sync
  only … No network download, no model weights, no paid service";
  components = opt-in; "The voice model (OmniVoice, CC-BY-NC) is NEVER
  downloaded by this script — it is installed separately, on request,
  from Hugging Face."
- The model-download `curl` steps are printed only in the
  all-SUCCESS final summary of a `--with-components` run (lines
  232–238), as instructions for the user to run themselves.
- `docs/06-installation.md` ("What setup.sh does") already states the
  split correctly: item 1 — "This is the default: `bash setup.sh` does
  this and nothing else"; items 2–4 — "Only with `--with-components`";
  item 5 — "Walks you through the voice-model download (next section)
  — it does not download the model itself"; the Muse section states
  "A core-only install does NOT include VoiceStudio or OpenMontage"
  and "The voice model (OmniVoice) is never downloaded by `setup.sh`".
  No change to `docs/06-installation.md` was needed.
- Scope check: the false phrases ("fetches and installs the bundled
  components", "walks you through downloading", "no separate install
  is needed", unqualified "cloned by `setup.sh`") appeared nowhere
  else in `docs/`, `AGENTS.md`, or `skills/` — the discrepancy was
  confined to README.md.

## 3. Files changed

| File | Change |
|---|---|
| `README.md` | TASK A: Install section rewritten (core-only default vs opt-in `--with-components`, voice model never downloaded by `setup.sh`); Voice section qualified (both component mentions + model bullet); Windows Git Bash note qualified; Licence section qualified. No other README content touched. |
| `tests/test_reports.py` | TASK B: new group CF-P0-REPORT-005 (10 checks) + module-docstring ID list. No existing check touched. |
| `tests/run-tests.sh` | TASK B: one new `run_one "CF-P0-REPORT-005" python3 tests/test_reports.py` line after CF-P0-REPORT-004. |
| `docs/implementation/CF-WO-P0-012-corrections.md` | This record. |
| `CHANGELOG.md` | `[Unreleased]` P0-012 entry. |
| `docs/implementation/BUILD_REPORT_P0.md`, `build-report.json`, `CHECKSUMS.txt`, `release-manifest.json`, `docs/architecture/living-architecture-report-v2.4-p0.md` | Provenance regenerated with the repo's own generators (see §6). |

`setup.sh` was NOT changed. No skill file changed. No component was
installed and no model was downloaded.

## 4. Corrected installation behaviour (what the README now says)

**Core installation (default)** — `bash setup.sh`:

> "`bash setup.sh` is a **core-only install by default**: it
> synchronizes the skills into `.agents/skills/` (non-destructively)
> and nothing else … The bundled components are **not** installed by
> default."

**Optional component installation** — `bash setup.sh --with-components`:

> "To also install the components, opt in explicitly … That fetches
> VoiceStudio (voice) and OpenMontage (long-form video), pinned to
> tested commits, and runs their own setup procedures. It needs
> network access and about 5 GB of free disk space, plus bun, uv,
> Node.js and `make` for the component setups."

**Voice model:**

> "The voice model (OmniVoice) is **not** downloaded by `setup.sh` —
> it is installed separately, on request, from Hugging Face."

The Voice section now says each component is "installed only with the
opt-in `bash setup.sh --with-components`", the model bullet says
"`setup.sh` never downloads them" and that "after a successful
`--with-components` install, `setup.sh` prints the download steps; you
run them yourself", the Windows note says the OpenMontage step "runs
only with `bash setup.sh --with-components`", and the Licence section
says the components are "cloned only by the opt-in `bash setup.sh
--with-components`" and the model is "downloaded separately, never by
`setup.sh`".

## 5. Regression test design (CF-P0-REPORT-005)

Location: `tests/test_reports.py`, new group CF-P0-REPORT-005 (10
checks), registered in `tests/run-tests.sh` as its own recorded entry
(so the suite grows from 49 entries / 37 IDs to 50 entries / 38 IDs;
commands stay 30 — `test_reports.py` was already a recorded command).

The test reads the live `README.md` and the live `setup.sh` and
asserts:

1. The Install section (text between `## Install` and the next `## `
   heading) states the core-only default — contains "core-only" and
   "default".
2. The Install section identifies `--with-components` as the optional
   path — contains "--with-components", "optional" or "opt in",
   "VoiceStudio", and "OpenMontage".
3. The README states the voice model is not downloaded by `setup.sh`
   — regex `voice model … not downloaded by` (bold markers stripped
   first, because `**not**` sits between the words) or "never
   downloaded by `setup.sh`".
4. Four forbidden phrases are absent (checked against a
   whitespace-normalized copy, so a claim wrapped across lines is
   still caught): "no separate install is needed", "fetches and
   installs the bundled components", "walks you through downloading",
   "downloads the voice model".
5. The README never claims components are installed by default —
   regexes for "components are installed (automatically?) by default"
   and "installs the bundled components … automatically" (the first
   does not match the corrected "are **not** installed by default").
6. The documented behaviour is consistent with the implementation —
   `setup.sh` contains `WITH_COMPONENTS=0`,
   `--with-components) WITH_COMPONENTS=1`, "is NEVER downloaded by
   this script", and "Components were NOT installed (default)".

Assertions are phrase-level, not byte-identical paragraphs, so honest
rewording does not break them. The forbidden phrases are the exact
false claims found in the pre-fix README.

### Before / after

**Before** — new test run against the pre-fix README (exit 1, 7
failures, all CF-P0-REPORT-005):

```text
FAIL CF-P0-REPORT-005: README Install section states the core-only default
FAIL CF-P0-REPORT-005: README identifies --with-components as the optional component path
FAIL CF-P0-REPORT-005: README states the voice model is not downloaded by setup.sh
FAIL CF-P0-REPORT-005: README has no false claim: 'no separate install is needed'
FAIL CF-P0-REPORT-005: README has no false claim: 'fetches and installs the bundled components'
FAIL CF-P0-REPORT-005: README has no false claim: 'walks you through downloading'
FAIL CF-P0-REPORT-005: README never claims components are installed by default
test_reports: FAIL (7 failure(s))
```

Notes: the two setup.sh-anchor checks passed even before the fix
(the implementation was already correct — only the documentation was
wrong), and the "downloads the voice model" phrase check passed
before the fix only because the old README said "downloading the
voice model" — the "walks you through downloading" check is the one
that caught that claim. The whitespace normalization was added after
the first before-run, when "no separate install is needed" initially
passed because the phrase wrapped across a line break in the README;
after normalization it fails as it should. The corrected count is 7.

**After** — same test against the fixed README:

```text
test_reports: PASS (0 failure(s))
```

47 PASS lines in `tests/test_reports.py` (was 37 before this round:
10 new CF-P0-REPORT-005 checks), exit 0. Full before/after outputs
are kept in the delivery folder (`p0-012-test-reports-after.txt`;
the before-run failure list is recorded verbatim above).

## 6. Verification (commands and exit codes)

- `bash -n setup.sh` — exit 0.
- `python3 tests/test_reports.py` — exit 0, 47 PASS lines, 0 failures
  (after fix); exit 1 with 7 failures before the fix (see §5).
- `bash tests/run-tests.sh` — run TWICE at final state, exit 0 both
  times. **Recalculated from the final run: 50 recorded entries, 38
  distinct test IDs, 30 distinct commands; 50 PASS, 0 FAIL, 0 SKIP.**
  (Was 49/37/30 — the new CF-P0-REPORT-005 entry adds one entry and
  one ID; the command string `python3 tests/test_reports.py` already
  existed, so commands stay 30.) Per-file PASS lines: schemas 91,
  routing 305, registries 261, performance-semantics 32,
  character-registration 142, production-direction 132,
  private-overlay 28, timeline-manifest 58, private-voice-security
  158, modes 32, reports **47** (was 37; +10 new checks),
  atomic-write 18 — 12-file total 1,304 (comparable 11-file total
  1,286, was 1,276, +10). `tests/last-run.json` SHA-256
  `6feca3e2c1231f9f0697ea390588caccd45deef3b18f2ce67c2ae6c2d1249c04`
  — changed from the P0-011 `cdb30569…` because the recorded entries
  changed (the new CF-P0-REPORT-005 entry); the runner records
  per-file/per-command PASS/FAIL, not per-check counts.
- `python3 scripts/validate-repo.py` — PASS.
- `python3 scripts/generate-registries.py --check` — CHECK OK.
- `python3 scripts/generate-report.py --check` — CHECK OK (with the
  same `--github-head a9748880` as the generation run — the check
  compares against a freshly generated report, so the head flag must
  match; an earlier invocation without the flag failed for that
  reason alone, and was re-run correctly).
- `git diff --check` — clean.
- `bash setup.sh --dry-run` — exit 0 (core-only; `--with-components`
  NOT RUN, as before — the full component installation has never been
  run end-to-end in this environment and stays honestly labelled).

Provenance order (P0-010 lesson): `scripts/generate-report.py`
first, `scripts/generate-build-report.py` last, both with
`--github-head a9748880` (the current remote head; no push in this
phase); the manifest was regenerated AFTER the final suite run and
verified 0 mismatches; the suite was NOT run again before committing.
Manifest: 158 files, commit `83b1be0`, github_branch_head `a9748880`,
0 mismatches vs the tree. Manifest SHA-256
`f85f08d304bdcce843b82d076fb68273a6b055d66e7c3fafca34d60b04cd260e`;
build-report SHA-256
`370a23c3c9d5c4383e7e82db305c43c5a1082e591a380dfa02393e09db4244ca`;
BUILD_REPORT_P0.md SHA-256
`0cf87d799a0322ddb1ef877b7f584fb97bddb64e267b7a987a9b4bf24be4f4a0`;
CHECKSUMS.txt 3/3 OK. Note: the manifest lists tracked files only,
so the new corrections doc (untracked at generation time) is not in
it yet and the recorded commit is the pre-commit head `83b1be0` — the
parent regenerates provenance after pushing, as in P0-010/P0-011.

## 7. Remaining limitations

- Documentation-only correction: it does not change what `setup.sh`
  does, and it does not test the component install itself.
  `setup.sh --with-components` (full VoiceStudio + OpenMontage
  install, ~5 GB + ~1 GB downloads) has still never been run
  end-to-end in this environment and remains honestly labelled NOT
  RUN in the build report. The corrected README now says so plainly
  for the reader too (network + disk + prerequisites for the opt-in
  path).
- The regression test pins the README against the current `setup.sh`
  behaviour. If the installer ever changes its default, the test
  fails until the README is updated with it — that is the intended
  behaviour, not a false alarm.
- The README's Mac/Windows per-OS commands were checked against the
  official installer docs only (no Mac/Windows machine available) —
  unchanged by this round; the honest note in the README already says
  so.
- P0-012 does not constitute P0 final approval. After delivery, all
  implementation stops and the independent reviewer conducts the
  complete final P0 audit of the exact GitHub HEAD. P1 does not start
  unless P0 is independently accepted and the user explicitly agrees.
