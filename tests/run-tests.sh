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
run_one "P0-SHELL" bash -n tests/test_installer_security.sh
run_one "P0-SHELL" bash -n tests/test_installer_manifest_security.sh
run_one "P0-SHELL" bash -n tests/test_installer_metadata_failure.sh
run_one "P0-SHELL" bash -n tests/test_installer_status.sh
run_one "P0-SHELL" bash -n tests/run-tests.sh

# Repo validation (schemas, frontmatter, registries, privacy, secrets,
# absolute claims).
run_one "P0-SCHEMA" python3 scripts/validate-repo.py

# Registry generation check (committed registries must match the live repo).
run_one "CF-INT-023" python3 scripts/generate-registries.py --check

# Routing catalog generation check (committed catalog must match the
# canonical routing sources).
run_one "CF-P1-002-CATALOG" python3 scripts/generate-routing-catalog.py --check

# Unit / integration tests.
run_one "P0-SCHEMA" python3 tests/test_schemas.py
run_one "P0-ROUTING" python3 tests/test_routing.py
run_one "CF-P0-ROUTING-001" python3 tests/test_routing.py
run_one "CF-P0-ROUTING-002" python3 tests/test_routing.py
run_one "CF-P0-ROUTING-003" python3 tests/test_routing.py
run_one "CF-INT-023" python3 tests/test_registries.py
run_one "CF-P0-ASSET-001" python3 tests/test_modes.py
run_one "CF-P0-ASSET-002" python3 tests/test_modes.py
run_one "CF-P0-ASSET-003" python3 tests/test_modes.py
run_one "CF-P0-LEARN-001" python3 tests/test_modes.py
run_one "CF-P0-LEARN-001" python3 tests/test_schemas.py
run_one "CF-P0-PERF-001" python3 tests/test_performance_semantics.py
run_one "CF-P0-PERF-002" python3 tests/test_performance_semantics.py
run_one "CF-P0-PERF-003" python3 tests/test_performance_semantics.py
run_one "CF-P0-PERF-004" python3 tests/test_performance_semantics.py
run_one "CF-P0-PERF-005" python3 tests/test_performance_semantics.py
run_one "P0-PRIVACY" python3 tests/test_private_overlay.py
run_one "CF-P0-006-AC-REG" python3 tests/test_character_registration.py
run_one "CF-P0-006-AC-DIR" python3 tests/test_production_direction.py
run_one "CF-P0-007-AC-TIMELINE" python3 tests/test_timeline_manifest.py
run_one "CF-P0-008-SEC" python3 tests/test_private_voice_security.py
run_one "CF-INT-014" bash tests/test_installer.sh
run_one "CF-INT-015" bash tests/test_installer.sh
run_one "CF-INT-015" bash tests/test_installer_security.sh
run_one "CF-P0-SEC-MANIFEST-01" bash tests/test_installer_manifest_security.sh
run_one "CF-P0-SEC-MANIFEST-02" bash tests/test_installer_manifest_security.sh
run_one "CF-P0-SEC-MANIFEST-03" bash tests/test_installer_manifest_security.sh
run_one "CF-P0-SEC-MANIFEST-04" bash tests/test_installer_manifest_security.sh
run_one "CF-P0-SEC-METADATA-05" bash tests/test_installer_metadata_failure.sh
run_one "CF-P0-SEC-METADATA-06" bash tests/test_installer_metadata_failure.sh no-change
run_one "CF-P0-SEC-METADATA-07" bash tests/test_installer_metadata_failure.sh failed-no-backup
run_one "CF-P0-014-INST" bash tests/test_installer_status.sh
run_one "CF-P0-014-PIN" bash tests/test_installer_status.sh
run_one "CF-P0-015-WT" bash tests/test_installer_status.sh
run_one "CF-P1-001-SESSION" python3 tests/test_local_session_runtime.py
run_one "CF-P1-001-AUTHZ" python3 tests/test_session_authorization.py
run_one "CF-P0-ATOMIC-001" python3 tests/test_atomic_write.py
run_one "CF-P1-002-CATALOG" python3 tests/test_skill_router.py
run_one "CF-P1-002-SCHEMA" python3 tests/test_skill_router.py
run_one "CF-P1-002-ROUTING" python3 tests/test_skill_router.py
run_one "CF-P1-002-CONFLICTS" python3 tests/test_skill_router.py
run_one "CF-P1-002-MODES" python3 tests/test_skill_router.py
run_one "CF-P1-002-PLAN" python3 tests/test_skill_router.py
run_one "CF-P1-002-SECURITY" python3 tests/test_skill_router.py
run_one "CF-P1-002-R1-SCOPE" python3 tests/test_skill_router.py
run_one "CF-P1-002-R1-SCHEMA" python3 tests/test_skill_router.py
run_one "CF-P1-002-R1-HANDOFF" python3 tests/test_skill_router.py
run_one "CF-P1-002-R1-CATALOG" python3 tests/test_skill_router.py
run_one "CF-P1-003-SESSION-ROUTING" python3 tests/test_script_to_performance_runtime.py
run_one "CF-P1-003-SCRIPT" python3 tests/test_script_to_performance_runtime.py
run_one "CF-P1-003-PLANS" python3 tests/test_script_to_performance_runtime.py
run_one "CF-P1-003-DIALOGUE" python3 tests/test_script_to_performance_runtime.py
run_one "CF-P1-003-XREF" python3 tests/test_script_to_performance_runtime.py
run_one "CF-P1-003-DETERMINISM" python3 tests/test_script_to_performance_runtime.py
run_one "CF-P1-003-NULL156" python3 tests/test_script_to_performance_runtime.py
run_one "CF-P1-003-R1-BUNDLE-SHAPE" python3 tests/test_script_to_performance_runtime.py
run_one "CF-P1-003-R1-FAIL-CLOSED" python3 tests/test_script_to_performance_runtime.py
run_one "CF-P1-003-R1-DIALOGUE-META" python3 tests/test_script_to_performance_runtime.py
run_one "CF-P1-003-R2-SCRIPT" python3 tests/test_script_to_performance_runtime.py
run_one "CF-P1-003-R2-PROFILE" python3 tests/test_script_to_performance_runtime.py
run_one "CF-P1-003-R2-SCENE" python3 tests/test_script_to_performance_runtime.py
run_one "CF-P1-003-R2-SHOT" python3 tests/test_script_to_performance_runtime.py
run_one "CF-P1-003-R2-PERFORMANCE" python3 tests/test_script_to_performance_runtime.py
run_one "CF-P1-003-R2-EDITING" python3 tests/test_script_to_performance_runtime.py
run_one "CF-P1-003-R2-BINDINGS" python3 tests/test_script_to_performance_runtime.py
run_one "CF-P1-003-R2-BUNDLE" python3 tests/test_script_to_performance_runtime.py
run_one "CF-P1-004-ANALYSIS" python3 tests/test_production_analysis.py
run_one "CF-P1-004-ORCHESTRATOR" python3 tests/test_production_orchestrator.py
run_one "CF-P1-004-COMPILER" python3 tests/test_task_compiler.py
run_one "CF-P1-004-R1-STORE" python3 tests/test_production_store.py
run_one "CF-P1-004-R1-ADAPTER" python3 tests/test_muse_adapter_conformance.py
run_one "CF-P1-004-R1-IDENTITY-RESOLUTION" python3 tests/test_identity_resolution.py
run_one "CF-P1-004-R1-IDENTITY-POLICY" python3 tests/test_identity_resolution.py
run_one "CF-P1-004-R1-IDENTITY-BINDING" python3 tests/test_identity_resolution.py
run_one "CF-P1-004-R1-IDENTITY-VOICE" python3 tests/test_identity_resolution.py
run_one "CF-P1-004-R1-IDENTITY-E2E" python3 tests/test_identity_resolution.py
run_one "CF-P1-004-R1-IDENTITY-NEWONLY" python3 tests/test_identity_resolution.py
run_one "CF-P1-004-R1-IDENTITY-PRIVACY" python3 tests/test_identity_resolution.py

# Whitespace / diff hygiene.
run_one "P0-DIFF-CHECK" git diff --check

# Report provenance (P0-002 §§6-7) BEFORE the living-report regen:
# the manifest-integrity group (CF-P1-003-R2-MANIFEST) verifies the
# committed manifest against the committed tree, and the regen below
# rewrites the living report (a manifest-listed file) — so the
# report tests must run before it, not after. (R2: the suite's own
# regen step used to run first and invalidated the manifest check
# on every full-suite run; see corrections doc §12.2.)
run_one "CF-P0-REPORT-001" python3 tests/test_reports.py
run_one "CF-P0-REPORT-002" python3 tests/test_reports.py
run_one "CF-P0-REPORT-003" python3 tests/test_reports.py
run_one "CF-P0-REPORT-004" python3 tests/test_reports.py
run_one "CF-P0-REPORT-005" python3 tests/test_reports.py
run_one "CF-P1-003-R2-MANIFEST" python3 tests/test_reports.py

# Living report: regenerate from canonical records, then verify it matches.
run_one "CF-INT-023" python3 scripts/generate-report.py
run_one "CF-INT-023" python3 scripts/generate-report.py --check

# Companion evidence (P0-002 §6).
run_one "CF-P0-ROUTING-004" python3 tests/test_routing.py

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
