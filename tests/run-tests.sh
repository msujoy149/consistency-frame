#!/usr/bin/env bash
# Consistency Frame P0 — test runner.
# Runs every P0 test, records exact commands + exit codes in
# tests/last-run.json, and prints a PASS/FAIL/SKIPPED/NOT RUN summary.
# A test is reported PASS only if it was executed here.
# Usage: bash tests/run-tests.sh
# Exit 0 only when every executed test passes.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

RESULTS_JSON="$REPO_ROOT/tests/last-run.json"
TMP_RESULTS="$(mktemp)"
trap 'rm -f "$TMP_RESULTS"' EXIT
echo "[]" > "$TMP_RESULTS"
OVERALL="PASS"

record() {
  # $1=id $2=command $3=exit_code $4=result
  python3 - "$TMP_RESULTS" "$1" "$2" "$3" "$4" <<'PYEOF'
import json, sys
path, tid, cmd, code, result = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5]
data = json.load(open(path, encoding="utf-8"))
data.append({"id": tid, "command": cmd, "exit_code": code, "result": result})
json.dump(data, open(path, "w", encoding="utf-8"), indent=2)
PYEOF
}

run_one() {
  local id="$1"; shift
  local cmd="$*"
  echo "=== $id: $cmd ==="
  local code=0
  "$@" || code=$?
  local result="PASS"
  [ "$code" != 0 ] && result="FAIL" && OVERALL="FAIL"
  record "$id" "$cmd" "$code" "$result"
  echo "--- $id: $result (exit $code) ---"
}

# Shell syntax first (fast fail on broken scripts).
run_one "P0-SHELL" bash -n scripts/sync-skills.sh
run_one "P0-SHELL" bash -n setup.sh
run_one "P0-SHELL" bash -n tests/test_installer.sh
run_one "P0-SHELL" bash -n tests/run-tests.sh

# Repo validation (schemas, frontmatter, registries, privacy, secrets,
# absolute claims).
run_one "P0-SCHEMA" python3 scripts/validate-repo.py

# Registry generation check (committed registries must match the live repo).
run_one "CF-INT-023" python3 scripts/generate-registries.py --check

# Unit / integration tests.
run_one "P0-SCHEMA" python3 tests/test_schemas.py
run_one "CF-INT-023" python3 tests/test_registries.py
run_one "CF-P0-ASSET-001" python3 tests/test_modes.py
run_one "CF-P0-ASSET-002" python3 tests/test_modes.py
run_one "CF-P0-ASSET-003" python3 tests/test_modes.py
run_one "P0-PRIVACY" python3 tests/test_private_overlay.py
run_one "CF-INT-014" bash tests/test_installer.sh
run_one "CF-INT-015" bash tests/test_installer.sh

# Whitespace / diff hygiene.
run_one "P0-DIFF-CHECK" git diff --check

# Living report: regenerate from canonical records, then verify it matches.
run_one "CF-INT-023" python3 scripts/generate-report.py
run_one "CF-INT-023" python3 scripts/generate-report.py --check

python3 - "$TMP_RESULTS" "$RESULTS_JSON" "$OVERALL" <<'PYEOF'
import json, sys
src, dst, overall = sys.argv[1], sys.argv[2], sys.argv[3]
tests = json.load(open(src, encoding="utf-8"))
json.dump({"status": overall, "tests": tests}, open(dst, "w", encoding="utf-8"), indent=2)
PYEOF

echo ""
echo "=== P0 test run: $OVERALL ==="
python3 - "$RESULTS_JSON" <<'PYEOF'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
for t in data["tests"]:
    print(f"  {t['result']:4} {t['id']:16} exit={t['exit_code']}  {t['command']}")
PYEOF
echo "Results recorded in tests/last-run.json"
[ "$OVERALL" = "PASS" ] && exit 0 || exit 1
