#!/usr/bin/env bash
# P0 installer status + component-pin tests (CF-P0-014-INST, CF-P0-014-PIN).
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
trap 'rm -rf "$TMP"' EXIT

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
awk '/^(canonical_github_repo|verify_component_checkout|clone_component)\(\) \{/ { on=1 } on { print } /^}$/ { on=0 }' \
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

echo "test_installer_status: $([ "$FAILURES" = 0 ] && echo PASS || echo FAIL) ($FAILURES failure(s))"
exit "$([ "$FAILURES" = 0 ] && echo 0 || echo 1)"
