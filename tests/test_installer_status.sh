#!/usr/bin/env bash
# P0 installer status + component-pin tests (CF-P0-014-INST, CF-P0-014-PIN)
# plus worktree setup-gate tests (CF-P0-015-WT).
# Uses isolated temporary fixtures only — never touches the real repo,
# never touches the network, never downloads the components. Every git
# fixture is created fresh here (git init + local commits); component
# clones are redirected to local fixture sources with git's
# url.<base>.insteadOf mechanism, so no real URL is ever fetched.
# Exit 0 = PASS, 1 = FAIL.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FAILURES=0
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP" ${WT_BASE:+"$WT_BASE"}' EXIT

ok()   { echo "PASS $1"; }
bad()  { echo "FAIL $1"; FAILURES=$((FAILURES + 1)); }

# --- fixture helpers -------------------------------------------------------
make_git_repo() {  # $1 = dir; creates a repo with one commit, prints HEAD
  local dir="$1"
  mkdir -p "$dir"
  git init -q -b main "$dir"
  git -C "$dir" config user.email "test@example.invalid"
  git -C "$dir" config user.name "Test"
  printf 'fixture\n' > "$dir/file.txt"
  git -C "$dir" add file.txt
  git -C "$dir" commit -qm "fixture commit"
  git -C "$dir" rev-parse HEAD
}

# --- Section 1: core sync exit propagation (CF-P0-014-INST) --------------
# A copy of the real setup.sh runs in an isolated git fixture whose
# scripts/sync-skills.sh is a stub that exits with $SYNC_EXIT.
FIX="$TMP/setup-fixture"
mkdir -p "$FIX/scripts"
git init -q -b main "$FIX"
cp "$REPO_ROOT/setup.sh" "$FIX/setup.sh"
cat > "$FIX/scripts/sync-skills.sh" <<'EOF'
#!/usr/bin/env bash
echo "STUB-SYNC-MARKER exit=${SYNC_EXIT:-0}" >&2
exit "${SYNC_EXIT:-0}"
EOF
chmod +x "$FIX/scripts/sync-skills.sh"

# 1. Sync exit 0 -> setup exit 0, SUCCESS summary.
OUT="$(cd "$FIX" && SYNC_EXIT=0 bash setup.sh 2>&1)"; CODE=$?
[ "$CODE" = 0 ] \
  && ok "CF-P0-014-INST-01: sync exit 0 -> setup exit 0" \
  || bad "CF-P0-014-INST-01: sync exit 0 -> setup exit 0 (code=$CODE)"
echo "$OUT" | grep -q "== Setup SUCCESS:" \
  && ok "CF-P0-014-INST-01: setup reports SUCCESS" \
  || bad "CF-P0-014-INST-01: setup reports SUCCESS"

# 2. The stub's stderr diagnostics reach the user unchanged.
echo "$OUT" | grep -q "STUB-SYNC-MARKER exit=0" \
  && ok "CF-P0-014-INST-02: sync stderr diagnostics preserved" \
  || bad "CF-P0-014-INST-02: sync stderr diagnostics preserved"

# 3. Sync exit 2 -> setup exit 2, PARTIAL summary (core-only).
OUT2="$(cd "$FIX" && SYNC_EXIT=2 bash setup.sh 2>&1)"; CODE2=$?
[ "$CODE2" = 2 ] \
  && ok "CF-P0-014-INST-03: sync exit 2 -> setup exit 2" \
  || bad "CF-P0-014-INST-03: sync exit 2 -> setup exit 2 (code=$CODE2)"
echo "$OUT2" | grep -q "== Setup PARTIAL:" \
  && ok "CF-P0-014-INST-03: setup reports PARTIAL" \
  || bad "CF-P0-014-INST-03: setup reports PARTIAL"
echo "$OUT2" | grep -q "skills=PARTIAL" \
  && ok "CF-P0-014-INST-03: summary names skills=PARTIAL" \
  || bad "CF-P0-014-INST-03: summary names skills=PARTIAL"

# 4. Sync exit 2 with --with-components: still exit 2, and the
# component installation never begins.
OUT2C="$(cd "$FIX" && SYNC_EXIT=2 bash setup.sh --with-components 2>&1)"; CODE2C=$?
[ "$CODE2C" = 2 ] \
  && ok "CF-P0-014-INST-04: sync exit 2 + --with-components -> setup exit 2" \
  || bad "CF-P0-014-INST-04: sync exit 2 + --with-components -> setup exit 2 (code=$CODE2C)"
[ ! -d "$FIX/components" ] \
  && ok "CF-P0-014-INST-04: no components directory after PARTIAL sync" \
  || bad "CF-P0-014-INST-04: no components directory after PARTIAL sync"
echo "$OUT2C" | grep -q "Installing bundled components" \
  && bad "CF-P0-014-INST-04: component install not started after PARTIAL" \
  || ok "CF-P0-014-INST-04: component install not started after PARTIAL"

# 5. Sync exit 1 -> setup exit 1, FAILED summary.
OUT1="$(cd "$FIX" && SYNC_EXIT=1 bash setup.sh 2>&1)"; CODE1=$?
[ "$CODE1" = 1 ] \
  && ok "CF-P0-014-INST-05: sync exit 1 -> setup exit 1" \
  || bad "CF-P0-014-INST-05: sync exit 1 -> setup exit 1 (code=$CODE1)"
echo "$OUT1" | grep -q "== Setup FAILED:" \
  && ok "CF-P0-014-INST-05: setup reports FAILED" \
  || bad "CF-P0-014-INST-05: setup reports FAILED"

# 6. Sync exit 1 with --with-components: still exit 1, no components.
OUT1C="$(cd "$FIX" && SYNC_EXIT=1 bash setup.sh --with-components 2>&1)"; CODE1C=$?
[ "$CODE1C" = 1 ] \
  && ok "CF-P0-014-INST-06: sync exit 1 + --with-components -> setup exit 1" \
  || bad "CF-P0-014-INST-06: sync exit 1 + --with-components -> setup exit 1 (code=$CODE1C)"
[ ! -d "$FIX/components" ] \
  && ok "CF-P0-014-INST-06: no components directory after FAILED sync" \
  || bad "CF-P0-014-INST-06: no components directory after FAILED sync"

# 7. An unexpected sync exit code (3) is FAILED, exit 1 — never 2, never 0.
OUT3="$(cd "$FIX" && SYNC_EXIT=3 bash setup.sh 2>&1)"; CODE3=$?
[ "$CODE3" = 1 ] \
  && ok "CF-P0-014-INST-07: unexpected sync exit 3 -> setup exit 1" \
  || bad "CF-P0-014-INST-07: unexpected sync exit 3 -> setup exit 1 (code=$CODE3)"
echo "$OUT3" | grep -q "== Setup FAILED:" \
  && ok "CF-P0-014-INST-07: unexpected sync failure reports FAILED" \
  || bad "CF-P0-014-INST-07: unexpected sync failure reports FAILED"

# 8. SUCCESS is never reported after a PARTIAL or FAILED sync.
echo "$OUT2$OUT2C$OUT1$OUT1C$OUT3" | grep -q "== Setup SUCCESS:" \
  && bad "CF-P0-014-INST-08: no SUCCESS summary after PARTIAL/FAILED sync" \
  || ok "CF-P0-014-INST-08: no SUCCESS summary after PARTIAL/FAILED sync"

# --- Section 2: existing-component verification (CF-P0-014-PIN) ----------
VS_URL="https://github.com/debpalash/VoiceStudio"
OM_URL="https://github.com/OpenMontageInc/OpenMontage"
VS_PIN_REAL="2f2f5a9b0e982c6147efc6baaeae62936f29b79b"
OM_PIN_REAL="fecb9a1e3cc23ef84de30b272059457a427f16f8"

# PIN-01: the real call sites pin the exact configured commits and
# official URLs (static check on the real setup.sh).
if grep -qF "clone_component \"VoiceStudio\" \"$VS_URL\" \"components/voicestudio\" \"$VS_PIN_REAL\"" "$REPO_ROOT/setup.sh" \
  && grep -qF "clone_component \"OpenMontage\" \"$OM_URL\" \"components/openmontage\" \"$OM_PIN_REAL\"" "$REPO_ROOT/setup.sh"; then
  ok "CF-P0-014-PIN-01: call sites use exact pins + official URLs"
else
  bad "CF-P0-014-PIN-01: call sites use exact pins + official URLs"
fi

# Extract the real verification functions from setup.sh and source
# them, so these tests exercise the production code, not a copy.
FUNCS="$TMP/funcs.sh"
awk '/^(is_git_work_tree|canonical_github_repo|verify_component_checkout|clone_component)\(\) \{/ { on=1 } on { print } /^}$/ { on=0 }' \
  "$REPO_ROOT/setup.sh" > "$FUNCS"
PIN_NAMES=(
  "CF-P0-014-PIN-02: verification helpers present in setup.sh"
  "CF-P0-014-PIN-03: origin URL forms accepted/rejected"
  "CF-P0-014-PIN-04: valid existing checkout at pin is reused"
  "CF-P0-014-PIN-05: SSH origin form is accepted"
  "CF-P0-014-PIN-06: different commit is rejected, dir preserved"
  "CF-P0-014-PIN-07: wrong origin is rejected, dir preserved"
  "CF-P0-014-PIN-08: origin prefix attack is rejected"
  "CF-P0-014-PIN-09: http origin is rejected"
  "CF-P0-014-PIN-10: uncommitted modification is rejected, content preserved"
  "CF-P0-014-PIN-11: untracked file is rejected, dir preserved"
  "CF-P0-014-PIN-12: invalid git metadata is rejected, dir preserved"
  "CF-P0-014-PIN-13: .git garbage file is rejected, dir preserved"
  "CF-P0-014-PIN-14: fresh clone is verified at the exact pin"
  "CF-P0-014-PIN-15: no rejected checkout is deleted"
  "CF-P0-014-PIN-16: no false SUCCESS for a rejected checkout"
)
if ! grep -q "^canonical_github_repo() {" "$FUNCS" \
  || ! grep -q "^verify_component_checkout() {" "$FUNCS" \
  || ! grep -q "^clone_component() {" "$FUNCS"; then
  for n in "${PIN_NAMES[@]}"; do bad "$n (helpers missing from setup.sh)"; done
else
  # shellcheck disable=SC1090
  source "$FUNCS"
  ok "CF-P0-014-PIN-02: verification helpers present in setup.sh"

  # PIN-03: canonical origin forms. HTTPS, HTTPS+.git, SSH, ssh:// are
  # accepted; http://, another host, and an extra path segment are not.
  PIN03_OK=1
  [ "$(canonical_github_repo "https://github.com/debpalash/VoiceStudio")" = "debpalash/VoiceStudio" ] || PIN03_OK=0
  [ "$(canonical_github_repo "https://github.com/debpalash/VoiceStudio.git")" = "debpalash/VoiceStudio" ] || PIN03_OK=0
  [ "$(canonical_github_repo "https://github.com/debpalash/VoiceStudio/")" = "debpalash/VoiceStudio" ] || PIN03_OK=0
  [ "$(canonical_github_repo "git@github.com:debpalash/VoiceStudio.git")" = "debpalash/VoiceStudio" ] || PIN03_OK=0
  [ "$(canonical_github_repo "ssh://git@github.com/debpalash/VoiceStudio")" = "debpalash/VoiceStudio" ] || PIN03_OK=0
  canonical_github_repo "http://github.com/debpalash/VoiceStudio" >/dev/null 2>&1 && PIN03_OK=0
  canonical_github_repo "https://evil.example.com/debpalash/VoiceStudio" >/dev/null 2>&1 && PIN03_OK=0
  # An extra path segment extracts to a longer path, which never equals
  # the expected owner/repo — so verification rejects it at comparison.
  [ "$(canonical_github_repo "https://github.com/debpalash/VoiceStudio/tree/main")" != "debpalash/VoiceStudio" ] || PIN03_OK=0
  [ "$PIN03_OK" = 1 ] \
    && ok "CF-P0-014-PIN-03: origin URL forms accepted/rejected" \
    || bad "CF-P0-014-PIN-03: origin URL forms accepted/rejected"

  # Fixture source repos for the fresh-clone tests (local only).
  VS_SRC="$TMP/vs-src"; OM_SRC="$TMP/om-src"
  VS_FIX_PIN="$(make_git_repo "$VS_SRC")"
  OM_FIX_PIN="$(make_git_repo "$OM_SRC")"
  # Redirect any clone/fetch of the official URLs to the local fixture
  # sources, so no test ever touches the network — and a bug that
  # tried to clone the real URL would still stay offline.
  export GIT_CONFIG_COUNT=2
  export GIT_CONFIG_KEY_0="url.file://$VS_SRC.insteadOf"
  export GIT_CONFIG_VALUE_0="$VS_URL"
  export GIT_CONFIG_KEY_1="url.file://$OM_SRC.insteadOf"
  export GIT_CONFIG_VALUE_1="$OM_URL"

  # PIN-04: valid existing checkout at the pin, HTTPS origin — reused.
  VS_DIR="$TMP/vs-valid"
  VS_PIN="$(make_git_repo "$VS_DIR")"
  git -C "$VS_DIR" remote add origin "$VS_URL"
  OUT_V="$(clone_component "VoiceStudio" "$VS_URL" "$VS_DIR" "$VS_PIN" 2>&1)"; CODE_V=$?
  [ "$CODE_V" = 0 ] \
    && ok "CF-P0-014-PIN-04: valid existing checkout at pin is reused" \
    || bad "CF-P0-014-PIN-04: valid existing checkout at pin is reused (code=$CODE_V)"
  echo "$OUT_V" | grep -q "already present (verified" \
    && ok "CF-P0-014-PIN-04: reuse is reported as verified" \
    || bad "CF-P0-014-PIN-04: reuse is reported as verified"
  [ "$(git -C "$VS_DIR" rev-parse HEAD)" = "$VS_PIN" ] \
    && ok "CF-P0-014-PIN-04: HEAD unchanged after reuse" \
    || bad "CF-P0-014-PIN-04: HEAD unchanged after reuse"

  # PIN-05: the same checkout with an SSH origin is accepted.
  git -C "$VS_DIR" remote set-url origin "git@github.com:debpalash/VoiceStudio.git"
  if clone_component "VoiceStudio" "$VS_URL" "$VS_DIR" "$VS_PIN" >/dev/null 2>&1; then
    ok "CF-P0-014-PIN-05: SSH origin form is accepted"
  else
    bad "CF-P0-014-PIN-05: SSH origin form is accepted"
  fi
  git -C "$VS_DIR" remote set-url origin "$VS_URL"

  # PIN-06: same repo, one more commit — HEAD differs from the pin.
  printf 'second commit\n' >> "$VS_DIR/file.txt"
  git -C "$VS_DIR" add file.txt
  git -C "$VS_DIR" commit -qm "second commit"
  OUT_D="$(clone_component "VoiceStudio" "$VS_URL" "$VS_DIR" "$VS_PIN" 2>&1)"; CODE_D=$?
  [ "$CODE_D" != 0 ] \
    && ok "CF-P0-014-PIN-06: different commit is rejected" \
    || bad "CF-P0-014-PIN-06: different commit is rejected"
  echo "$OUT_D" | grep -q "not the pinned" \
    && ok "CF-P0-014-PIN-06: error names the pinned commit" \
    || bad "CF-P0-014-PIN-06: error names the pinned commit"
  [ -d "$VS_DIR/.git" ] && grep -q "second commit" "$VS_DIR/file.txt" \
    && ok "CF-P0-014-PIN-06: dir preserved after rejection" \
    || bad "CF-P0-014-PIN-06: dir preserved after rejection"
  # Restore the fixture to the pinned commit for the later cases.
  git -C "$VS_DIR" reset -q --hard "$VS_PIN"

  # PIN-07: correct pin, wrong origin.
  git -C "$VS_DIR" remote set-url origin "https://github.com/evil/VoiceStudio"
  OUT_W="$(clone_component "VoiceStudio" "$VS_URL" "$VS_DIR" "$VS_PIN" 2>&1)"; CODE_W=$?
  [ "$CODE_W" != 0 ] \
    && ok "CF-P0-014-PIN-07: wrong origin is rejected" \
    || bad "CF-P0-014-PIN-07: wrong origin is rejected"
  echo "$OUT_W" | grep -q "unexpected origin" \
    && ok "CF-P0-014-PIN-07: error names the unexpected origin" \
    || bad "CF-P0-014-PIN-07: error names the unexpected origin"
  [ -d "$VS_DIR/.git" ] \
    && ok "CF-P0-014-PIN-07: dir preserved after rejection" \
    || bad "CF-P0-014-PIN-07: dir preserved after rejection"
  git -C "$VS_DIR" remote set-url origin "$VS_URL"

  # PIN-08: origin prefix attack — a longer repo name sharing the prefix.
  git -C "$VS_DIR" remote set-url origin "https://github.com/debpalash/VoiceStudio-evil"
  if clone_component "VoiceStudio" "$VS_URL" "$VS_DIR" "$VS_PIN" >/dev/null 2>&1; then
    bad "CF-P0-014-PIN-08: origin prefix attack is rejected"
  else
    ok "CF-P0-014-PIN-08: origin prefix attack is rejected"
  fi
  git -C "$VS_DIR" remote set-url origin "$VS_URL"

  # PIN-09: plain http origin is not an accepted official form.
  git -C "$VS_DIR" remote set-url origin "http://github.com/debpalash/VoiceStudio"
  if clone_component "VoiceStudio" "$VS_URL" "$VS_DIR" "$VS_PIN" >/dev/null 2>&1; then
    bad "CF-P0-014-PIN-09: http origin is rejected"
  else
    ok "CF-P0-014-PIN-09: http origin is rejected"
  fi
  git -C "$VS_DIR" remote set-url origin "$VS_URL"

  # PIN-10: uncommitted modification of a tracked file.
  printf 'USER EDIT — DO NOT OVERWRITE\n' >> "$VS_DIR/file.txt"
  OUT_M="$(clone_component "VoiceStudio" "$VS_URL" "$VS_DIR" "$VS_PIN" 2>&1)"; CODE_M=$?
  [ "$CODE_M" != 0 ] \
    && ok "CF-P0-014-PIN-10: uncommitted modification is rejected" \
    || bad "CF-P0-014-PIN-10: uncommitted modification is rejected"
  echo "$OUT_M" | grep -qi "modified\|uncommitted" \
    && ok "CF-P0-014-PIN-10: error says the tree is modified" \
    || bad "CF-P0-014-PIN-10: error says the tree is modified"
  grep -q "USER EDIT" "$VS_DIR/file.txt" \
    && ok "CF-P0-014-PIN-10: content preserved after rejection" \
    || bad "CF-P0-014-PIN-10: content preserved after rejection"
  git -C "$VS_DIR" checkout -q -- file.txt

  # PIN-11: untracked file in an otherwise clean checkout.
  printf 'untracked\n' > "$VS_DIR/notes.txt"
  if clone_component "VoiceStudio" "$VS_URL" "$VS_DIR" "$VS_PIN" >/dev/null 2>&1; then
    bad "CF-P0-014-PIN-11: untracked file is rejected"
  else
    ok "CF-P0-014-PIN-11: untracked file is rejected"
  fi
  [ -f "$VS_DIR/notes.txt" ] \
    && ok "CF-P0-014-PIN-11: dir preserved after rejection" \
    || bad "CF-P0-014-PIN-11: dir preserved after rejection"
  rm -f "$VS_DIR/notes.txt"

  # PIN-12: a directory with an empty .git directory is not a repo.
  BAD_DIR="$TMP/bad-empty-git"
  mkdir -p "$BAD_DIR/.git"
  OUT_B="$(clone_component "VoiceStudio" "$VS_URL" "$BAD_DIR" "$VS_PIN" 2>&1)"; CODE_B=$?
  [ "$CODE_B" != 0 ] \
    && ok "CF-P0-014-PIN-12: invalid git metadata is rejected" \
    || bad "CF-P0-014-PIN-12: invalid git metadata is rejected"
  [ -d "$BAD_DIR/.git" ] \
    && ok "CF-P0-014-PIN-12: dir preserved after rejection" \
    || bad "CF-P0-014-PIN-12: dir preserved after rejection"

  # PIN-13: a .git regular file with garbage is not a repo.
  GARBAGE_DIR="$TMP/bad-git-file"
  mkdir -p "$GARBAGE_DIR"
  printf 'garbage, not a gitdir\n' > "$GARBAGE_DIR/.git"
  if clone_component "VoiceStudio" "$VS_URL" "$GARBAGE_DIR" "$VS_PIN" >/dev/null 2>&1; then
    bad "CF-P0-014-PIN-13: .git garbage file is rejected"
  else
    ok "CF-P0-014-PIN-13: .git garbage file is rejected"
  fi
  [ -f "$GARBAGE_DIR/.git" ] \
    && ok "CF-P0-014-PIN-13: dir preserved after rejection" \
    || bad "CF-P0-014-PIN-13: dir preserved after rejection"

  # PIN-14: fresh clone is verified at the exact pin (both components).
  FRESH="$TMP/fresh"
  OUT_F="$(clone_component "VoiceStudio" "$VS_URL" "$FRESH/voicestudio" "$VS_FIX_PIN" 2>&1)"; CODE_F=$?
  [ "$CODE_F" = 0 ] \
    && ok "CF-P0-014-PIN-14: fresh VoiceStudio clone succeeds" \
    || bad "CF-P0-014-PIN-14: fresh VoiceStudio clone succeeds (code=$CODE_F)"
  [ "$(git -C "$FRESH/voicestudio" rev-parse HEAD 2>/dev/null)" = "$VS_FIX_PIN" ] \
    && ok "CF-P0-014-PIN-14: fresh clone HEAD equals the pin" \
    || bad "CF-P0-014-PIN-14: fresh clone HEAD equals the pin"
  [ "$(git -C "$FRESH/voicestudio" config --get remote.origin.url 2>/dev/null)" = "$VS_URL" ] \
    && ok "CF-P0-014-PIN-14: fresh clone origin is the official URL" \
    || bad "CF-P0-014-PIN-14: fresh clone origin is the official URL"
  [ -z "$(git -C "$FRESH/voicestudio" status --porcelain 2>/dev/null)" ] \
    && ok "CF-P0-014-PIN-14: fresh clone working tree is clean" \
    || bad "CF-P0-014-PIN-14: fresh clone working tree is clean"
  OUT_FO="$(clone_component "OpenMontage" "$OM_URL" "$FRESH/openmontage" "$OM_FIX_PIN" 2>&1)"; CODE_FO=$?
  [ "$CODE_FO" = 0 ] && [ "$(git -C "$FRESH/openmontage" rev-parse HEAD 2>/dev/null)" = "$OM_FIX_PIN" ] \
    && ok "CF-P0-014-PIN-14: fresh OpenMontage clone verified at the pin" \
    || bad "CF-P0-014-PIN-14: fresh OpenMontage clone verified at the pin (code=$CODE_FO)"

  # PIN-15: every rejected fixture directory still exists afterwards.
  PIN15_OK=1
  for d in "$VS_DIR" "$BAD_DIR" "$GARBAGE_DIR"; do [ -d "$d" ] || PIN15_OK=0; done
  [ "$PIN15_OK" = 1 ] \
    && ok "CF-P0-014-PIN-15: no rejected checkout is deleted" \
    || bad "CF-P0-014-PIN-15: no rejected checkout is deleted"

  # PIN-16: no rejected checkout was ever reported as verified/success.
  echo "$OUT_D$OUT_W$OUT_M$OUT_B" | grep -q "already present (verified" \
    && bad "CF-P0-014-PIN-16: no false SUCCESS for a rejected checkout" \
    || ok "CF-P0-014-PIN-16: no false SUCCESS for a rejected checkout"

  unset GIT_CONFIG_COUNT GIT_CONFIG_KEY_0 GIT_CONFIG_VALUE_0 GIT_CONFIG_KEY_1 GIT_CONFIG_VALUE_1
fi

# --- Section 3: worktree setup gates (CF-P0-015-WT) ----------------------
# P0-014's verify_component_checkout() accepts valid .git files
# (worktrees), but the old setup gates only accepted .git directories
# (`[ -d "components/<name>/.git" ]`), so a valid worktree passed
# verification and then silently skipped its setup while the run still
# reported SUCCESS. The gates now use is_git_work_tree() (real git
# plumbing). The end-to-end cases below run a copy of the real
# setup.sh in an isolated fixture whose component directories are
# worktrees (or normal clones), with mocked bun/uv/make on PATH that
# log their invocations — no real component command ever runs.
WT_NAMES=(
  "CF-P0-015-WT-01: gate accepts a normal .git directory"
  "CF-P0-015-WT-02: gate accepts a valid worktree (.git file)"
  "CF-P0-015-WT-03: gate rejects invalid git metadata"
  "CF-P0-015-WT-04: VoiceStudio setup runs for a valid worktree"
  "CF-P0-015-WT-05: OpenMontage setup runs for a valid worktree"
  "CF-P0-015-WT-06: setup runs for valid normal clones"
  "CF-P0-015-WT-07: invalid metadata ends FAILED, never SUCCESS"
  "CF-P0-015-WT-08: worktree is preserved by a successful run"
)
if ! grep -q "^is_git_work_tree() {" "$FUNCS"; then
  for n in "${WT_NAMES[@]}"; do bad "$n (helper missing from setup.sh)"; done
else
  # shellcheck disable=SC1090
  source "$FUNCS"

  # WT-01/WT-02/WT-03: the helper itself, on local fixtures.
  WT_MAIN="$TMP/wt-main"
  WT_MAIN_PIN="$(make_git_repo "$WT_MAIN")"
  git -C "$WT_MAIN" remote add origin "$VS_URL"
  WT_VS="$TMP/wt-vs"
  git -C "$WT_MAIN" worktree add -q --detach "$WT_VS" "$WT_MAIN_PIN"
  if is_git_work_tree "$WT_MAIN"; then
    ok "CF-P0-015-WT-01: gate accepts a normal .git directory"
  else
    bad "CF-P0-015-WT-01: gate accepts a normal .git directory"
  fi
  [ -f "$WT_VS/.git" ] && is_git_work_tree "$WT_VS" \
    && ok "CF-P0-015-WT-02: gate accepts a valid worktree (.git file)" \
    || bad "CF-P0-015-WT-02: gate accepts a valid worktree (.git file)"
  WT_BAD_DIR="$TMP/wt-bad-empty-git"
  mkdir -p "$WT_BAD_DIR/.git"
  WT_GARBAGE_DIR="$TMP/wt-bad-git-file"
  mkdir -p "$WT_GARBAGE_DIR"
  printf 'garbage, not a gitdir\n' > "$WT_GARBAGE_DIR/.git"
  if is_git_work_tree "$WT_BAD_DIR" || is_git_work_tree "$WT_GARBAGE_DIR"; then
    bad "CF-P0-015-WT-03: gate rejects invalid git metadata"
  else
    ok "CF-P0-015-WT-03: gate rejects invalid git metadata"
  fi

  # End-to-end fixtures live under $WT_BASE, not $TMP: setup.sh
  # refuses --with-components when its disk-space check sees under
  # 5 GB free, and $TMP is a 512 MB tmpfs — so a fixture there would
  # fail before any component logic runs. The repo lives on the main
  # disk, so fixtures under it see the real free space. $WT_BASE is
  # removed at the end of this section (and by the EXIT trap).
  WT_BASE="$(mktemp -d "$REPO_ROOT/.tmp-wt-XXXXXX")"
  # Shared end-to-end harness: a fixture copy of the real setup.sh,
  # stub sync, mocked bun/uv/make logging to $WT_LOG. The fixture pins
  # are rewritten to local fixture commits, and the component origins
  # are the official URL strings (verify only compares the string).
  # Both components are always pre-created, so no run ever clones —
  # the insteadOf redirects below are a safety net only, and no real
  # URL is ever fetched.
  WT_VS_MAIN="$TMP/wt-vs-main"
  WT_VS_PIN="$(make_git_repo "$WT_VS_MAIN")"
  git -C "$WT_VS_MAIN" remote add origin "$VS_URL"
  WT_OM_MAIN="$TMP/wt-om-main"
  WT_OM_PIN="$(make_git_repo "$WT_OM_MAIN")"
  git -C "$WT_OM_MAIN" remote add origin "$OM_URL"
  export GIT_CONFIG_COUNT=2
  export GIT_CONFIG_KEY_0="url.file://$WT_VS_MAIN.insteadOf"
  export GIT_CONFIG_VALUE_0="$VS_URL"
  export GIT_CONFIG_KEY_1="url.file://$WT_OM_MAIN.insteadOf"
  export GIT_CONFIG_VALUE_1="$OM_URL"
  WT_BIN="$TMP/wt-bin"
  mkdir -p "$WT_BIN"
  cat > "$WT_BIN/bun" <<'EOF'
#!/usr/bin/env bash
echo "bun $*" >> "${WT_LOG:?}"
exit 0
EOF
  cat > "$WT_BIN/make" <<'EOF'
#!/usr/bin/env bash
echo "make $*" >> "${WT_LOG:?}"
exit 0
EOF
  cat > "$WT_BIN/uv" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
  chmod +x "$WT_BIN/bun" "$WT_BIN/make" "$WT_BIN/uv"
  setup_wt_fixture() {  # $1 = fixture dir; $2 = worktree|normal
    local fix="$1" mode="$2"
    mkdir -p "$fix/scripts" "$fix/components"
    git init -q -b main "$fix"
    cp "$REPO_ROOT/setup.sh" "$fix/setup.sh"
    cat > "$fix/scripts/sync-skills.sh" <<'EOF'
#!/usr/bin/env bash
echo "STUB-SYNC-MARKER exit=${SYNC_EXIT:-0}" >&2
exit "${SYNC_EXIT:-0}"
EOF
    chmod +x "$fix/scripts/sync-skills.sh"
    if [ "$mode" = "worktree" ]; then
      git -C "$WT_VS_MAIN" worktree add -q --detach "$fix/components/voicestudio" "$WT_VS_PIN"
      git -C "$WT_OM_MAIN" worktree add -q --detach "$fix/components/openmontage" "$WT_OM_PIN"
    else
      git clone -q "$WT_VS_MAIN" "$fix/components/voicestudio"
      git -C "$fix/components/voicestudio" remote set-url origin "$VS_URL"
      git clone -q "$WT_OM_MAIN" "$fix/components/openmontage"
      git -C "$fix/components/openmontage" remote set-url origin "$OM_URL"
    fi
    sed -i "s/$VS_PIN_REAL/$WT_VS_PIN/; s/$OM_PIN_REAL/$WT_OM_PIN/" "$fix/setup.sh"
  }

  # WT-04/WT-05: both components as worktrees — both setup sections
  # must execute (mocked commands log), and the run reports SUCCESS
  # only because setup actually ran.
  WT_FIX="$WT_BASE/wt-setup-fixture"
  setup_wt_fixture "$WT_FIX" "worktree"
  export WT_LOG="$TMP/wt.log"
  : > "$WT_LOG"
  OUT_WT="$(cd "$WT_FIX" && PATH="$WT_BIN:$PATH" SYNC_EXIT=0 bash setup.sh --with-components 2>&1)"; CODE_WT=$?
  grep -q "^bun install$" "$WT_LOG" \
    && ok "CF-P0-015-WT-04: VoiceStudio bun install runs for a worktree" \
    || bad "CF-P0-015-WT-04: VoiceStudio bun install runs for a worktree"
  grep -q "^bun run setup:api$" "$WT_LOG" \
    && ok "CF-P0-015-WT-04: VoiceStudio setup:api runs for a worktree" \
    || bad "CF-P0-015-WT-04: VoiceStudio setup:api runs for a worktree"
  [ "$CODE_WT" = 0 ] && echo "$OUT_WT" | grep -q "== Setup SUCCESS:" \
    && ok "CF-P0-015-WT-04: worktree run exits 0 with SUCCESS" \
    || bad "CF-P0-015-WT-04: worktree run exits 0 with SUCCESS (code=$CODE_WT)"
  grep -q "^make setup$" "$WT_LOG" \
    && ok "CF-P0-015-WT-05: OpenMontage make setup runs for a worktree" \
    || bad "CF-P0-015-WT-05: OpenMontage make setup runs for a worktree"
  echo "$OUT_WT" | grep -q "voicestudio=SUCCESS openmontage=SUCCESS" \
    && ok "CF-P0-015-WT-05: summary names both components SUCCESS" \
    || bad "CF-P0-015-WT-05: summary names both components SUCCESS"

  # WT-06: the same run with valid NORMAL clones — the fix must not
  # have broken the ordinary path.
  WT_FIX_N="$WT_BASE/wt-setup-fixture-normal"
  setup_wt_fixture "$WT_FIX_N" "normal"
  export WT_LOG="$TMP/wt-normal.log"
  : > "$WT_LOG"
  OUT_WTN="$(cd "$WT_FIX_N" && PATH="$WT_BIN:$PATH" SYNC_EXIT=0 bash setup.sh --with-components 2>&1)"; CODE_WTN=$?
  grep -q "^bun install$" "$WT_LOG" && grep -q "^make setup$" "$WT_LOG" \
    && ok "CF-P0-015-WT-06: setup runs for valid normal clones" \
    || bad "CF-P0-015-WT-06: setup runs for valid normal clones"
  [ "$CODE_WTN" = 0 ] && echo "$OUT_WTN" | grep -q "== Setup SUCCESS:" \
    && ok "CF-P0-015-WT-06: normal-clone run exits 0 with SUCCESS" \
    || bad "CF-P0-015-WT-06: normal-clone run exits 0 with SUCCESS (code=$CODE_WTN)"

  # WT-07: invalid metadata end-to-end — the run ends FAILED and
  # never reports SUCCESS.
  WT_FIX_BAD="$WT_BASE/wt-setup-fixture-bad"
  setup_wt_fixture "$WT_FIX_BAD" "normal"
  rm -rf "$WT_FIX_BAD/components/voicestudio"
  mkdir -p "$WT_FIX_BAD/components/voicestudio"
  printf 'garbage, not a gitdir\n' > "$WT_FIX_BAD/components/voicestudio/.git"
  export WT_LOG="$TMP/wt-bad.log"
  : > "$WT_LOG"
  OUT_WTB="$(cd "$WT_FIX_BAD" && PATH="$WT_BIN:$PATH" SYNC_EXIT=0 bash setup.sh --with-components 2>&1)"; CODE_WTB=$?
  [ "$CODE_WTB" = 1 ] \
    && ok "CF-P0-015-WT-07: invalid metadata run exits 1" \
    || bad "CF-P0-015-WT-07: invalid metadata run exits 1 (code=$CODE_WTB)"
  echo "$OUT_WTB" | grep -q "== Setup FAILED:" && ! echo "$OUT_WTB" | grep -q "== Setup SUCCESS:" \
    && ok "CF-P0-015-WT-07: run reports FAILED, never SUCCESS" \
    || bad "CF-P0-015-WT-07: run reports FAILED, never SUCCESS"
  [ -f "$WT_FIX_BAD/components/voicestudio/.git" ] \
    && ok "CF-P0-015-WT-07: invalid dir preserved after rejection" \
    || bad "CF-P0-015-WT-07: invalid dir preserved after rejection"

  # WT-08: a successful worktree run leaves the worktree intact —
  # still a .git file, still at the pinned commit, user content kept.
  WT_VS_AFTER="$WT_FIX/components/voicestudio"
  [ -f "$WT_VS_AFTER/.git" ] \
    && [ -n "$(git -C "$WT_VS_AFTER" rev-parse HEAD 2>/dev/null)" ] \
    && grep -q "fixture" "$WT_VS_AFTER/file.txt" \
    && ok "CF-P0-015-WT-08: worktree is preserved by a successful run" \
    || bad "CF-P0-015-WT-08: worktree is preserved by a successful run"
  unset WT_LOG
  unset GIT_CONFIG_COUNT GIT_CONFIG_KEY_0 GIT_CONFIG_VALUE_0 GIT_CONFIG_KEY_1 GIT_CONFIG_VALUE_1
  rm -rf "$WT_BASE"
fi

echo "test_installer_status: $([ "$FAILURES" = 0 ] && echo PASS || echo FAIL) ($FAILURES failure(s))"
exit "$([ "$FAILURES" = 0 ] && echo 0 || echo 1)"
