#!/usr/bin/env python3
"""Preflight storyboard tests (CF-WO-P1-006-R2-PREFLIGHT-STORYBOARD).

Covers the preflight storyboard / cost / gates work for the R2
photorealistic image-to-video production ("Nadia and the River
Light"):

- exact per-shot cost calculation (audio off, $0.224/s with
  elements — every shot carries the Nadia character element;
  the $0.112/s base rate applies only WITHOUT elements) and the
  dynamic total from the actual storyboard;
- retry cost calculation (one retry per failed shot, maximum
  retry budget, worst-case total);
- dynamic shot count (counts come from the storyboard, not a
  constant; no fixed shot-count or clip-count ceiling);
- required location coverage (every location in the script has
  coverage; every shot has a narrative purpose + a source line);
- generate_audio: false in every shot record;
- text overlay disabled in every shot record;
- paid submission blocked without explicit authorization (Gate A
  + Gate B both required — neither may be inferred);
- no provider call during preflight (mock transport only: the
  preflight path takes a recording mock transport and makes zero
  calls through it).

No test here calls a paid provider and no test touches the
network: the only transport in this file is a mock, clearly
labelled mock in every check name that uses it. No credential
is read or used. FFmpeg/ffprobe are NOT required by this suite.
"""

import json
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
ROOT_ABS = os.path.abspath(ROOT)
sys.path.insert(0, ROOT)

EXAMPLE = os.path.join(ROOT_ABS, "examples",
                       "p1006-r2-photorealistic-image-to-video")
PROJECT_ID = "p1006-r2-photorealistic-image-to-video"

RATE_AUDIO_OFF = 0.112
RATE_AUDIO_ON = 0.168
# fal.ai Kling 3.0 Pro per-second rates, re-verified live
# 2026-11-28 (fal.ai learn comparison pages; the official API
# schema page lists no pricing). The base rates apply ONLY
# WITHOUT elements; a shot carrying a character element is
# priced at the separate, higher elements tier.
RATE_ELEMENTS_AUDIO_OFF = 0.224
RATE_ELEMENTS_AUDIO_ON = 0.336
RATE_VOICE_CONTROL_NO_ELEMENTS = 0.196
RATE_VOICE_CONTROL_WITH_ELEMENTS = 0.392
TEXT_FLAGS = (
    "text_overlay_enabled", "subtitle_burn_in_enabled",
    "keyword_overlay_enabled", "subtext_overlay_enabled",
    "title_card_enabled", "watermark_enabled")
MOTION_FIELDS = ("subject", "face", "body", "hand_prop",
                 "hair_cloth", "environment", "camera")
TEXT_PROHIBITION_CLAUSE = (
    "No visible text, writing, signage, typography, subtitles, "
    "captions, watermarks, or logos.")

failures = []
_checks = [0]


def check(name, cond, detail=""):
    _checks[0] += 1
    if cond:
        print(f"PASS {name}")
    else:
        print(f"FAIL {name} {detail}")
        failures.append(name)


def load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


# ------------------------------------------------------------------
# Preflight pure helpers (the logic under test lives here, in the
# test module: it reads only local storyboard files and never
# touches the network, a provider, or a credential).
# ------------------------------------------------------------------

def shot_uses_elements(shot):
    """A shot uses the elements tier when it carries a
    character (the runtime additionally requires an identity
    binding for that character; this pure helper models the
    storyboard side — a shot with no character_id prices at
    the base rate)."""
    return bool(isinstance(shot, dict) and shot.get("character_id"))


def shot_cost_usd(duration_seconds, *, audio=False,
                  with_elements=False):
    """One shot's generation cost. Audio off is $0.224/s WITH
    elements, $0.112/s without; audio on $0.336/$0.168."""
    if with_elements:
        rate = RATE_ELEMENTS_AUDIO_ON if audio \
            else RATE_ELEMENTS_AUDIO_OFF
    else:
        rate = RATE_AUDIO_ON if audio else RATE_AUDIO_OFF
    return round(float(duration_seconds) * rate, 3)


def total_cost_usd(shots, *, audio=False):
    # Per-shot pricing: each shot pays its own elements usage,
    # never one flat rate for a mixed plan.
    return round(sum(
        shot_cost_usd((shot.get("visual") or {}).get(
            "duration_seconds") or 0, audio=audio,
            with_elements=shot_uses_elements(shot))
        for shot in shots), 3)


def retry_budget_usd(shots, *, retries_per_shot=1, audio=False):
    """Maximum retry spend: one retry per failed shot."""
    return round(total_cost_usd(shots, audio=audio)
                 * retries_per_shot, 3)


def derive_counts(shots, voice_lines):
    """Storyboard-derived counts. No count is a constant: every
    number comes from the inputs, so a storyboard of any size
    derives its own counts."""
    scene_ids = sorted({shot.get("scene_id") for shot in shots
                        if isinstance(shot, dict)})
    total = sum(float((shot.get("visual") or {}).get(
        "duration_seconds") or 0) for shot in shots)
    return {"scenes": len(scene_ids), "scene_ids": scene_ids,
            "shots": len(shots),
            "shot_ids": [shot.get("shot_id") for shot in shots
                         if isinstance(shot, dict)],
            "keyframes": len(shots), "clips": len(shots),
            "lines": len(voice_lines or []),
            "total_video_seconds": total}


def paid_generation_allowed(gate_a_approved, gate_b_approved):
    """Paid generation needs BOTH gates explicitly approved.
    Only the actual boolean True counts for either gate: a
    missing value, a string such as "approved", or one gate
    alone never authorizes a paid submission."""
    return gate_a_approved is True and gate_b_approved is True


class MockTransport:  # mock transport: records calls, never sends
    """Recording stand-in for a network transport. The preflight
    path must make zero calls through it."""

    def __init__(self):
        self.calls = []

    def request(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        raise AssertionError("mock transport must never be called "
                             "by the preflight path")


def run_preflight_checks(project_dir, *, transport=None):
    """Run the preflight file checks. Accepts an optional
    (mock) transport for the no-network assertion; the checks
    never call it. Returns a list of error strings (empty = ok).
    """
    errors = []
    shot_list = load_json(os.path.join(project_dir, "shot-list.json"))
    shots = shot_list.get("shots") or []
    for shot in shots:
        if shot.get("generate_audio") is not False:
            errors.append(
                f"shot {shot.get('shot_id')}: generate_audio is not False")
        for flag in TEXT_FLAGS:
            if (shot.get("text_overlay") or {}).get(flag) is not False:
                errors.append(
                    f"shot {shot.get('shot_id')}: text flag {flag} "
                    "is not False")
    # The transport is accepted and never used: zero network calls
    # in the preflight path by construction.
    _ = transport
    return errors


def run_checks():
    shot_list = load_json(os.path.join(EXAMPLE, "shot-list.json"))
    shots = shot_list.get("shots") or []
    voice = load_json(os.path.join(EXAMPLE, "voice-config.json"))
    project = load_json(os.path.join(EXAMPLE, "project.json"))
    cost_plan = load_json(os.path.join(EXAMPLE, "cost-plan.json"))
    coverage = load_json(os.path.join(
        EXAMPLE, "story-coverage-report.json"))
    locations = load_json(os.path.join(
        EXAMPLE, "location-coverage.json"))
    durations = load_json(os.path.join(
        EXAMPLE, "shot-duration-plan.json"))
    scenes = load_json(os.path.join(
        EXAMPLE, "scene-breakdown.json"))
    appearances = load_json(os.path.join(
        EXAMPLE, "character-appearance-map.json"))

    # --- exact per-shot cost, audio off, WITH elements ($0.224/s)
    for shot in shots:
        dur = (shot.get("visual") or {}).get("duration_seconds")
        expected = round(float(dur) * RATE_ELEMENTS_AUDIO_OFF, 3)
        planned = [p for p in cost_plan["shots"]
                   if p["shot_id"] == shot["shot_id"]]
        check("CF-P1-006-R2-PREFLIGHT-STORYBOARD-cost-per-shot-"
              f"{shot['shot_id']}",
              len(planned) == 1
              and shot_uses_elements(shot)
              and planned[0]["uses_elements"] is True
              and planned[0]["estimated_cost_usd"] == expected
              and planned[0]["rate_usd_per_second"] \
              == RATE_ELEMENTS_AUDIO_OFF
              and planned[0]["audio"] is False,
              f"shot {shot['shot_id']}: expected ${expected:.3f}")
    check("CF-P1-006-R2-PREFLIGHT-STORYBOARD-cost-formula",
          shot_cost_usd(6, audio=False, with_elements=True) == 1.344
          and shot_cost_usd(6, audio=False,
                            with_elements=False) == 0.672
          and shot_cost_usd(6, audio=True,
                            with_elements=True) == 2.016
          and shot_cost_usd(15, audio=False,
                            with_elements=True) == 3.36
          and shot_cost_usd(3, audio=False,
                            with_elements=True) == 0.672,
          "per-shot cost = duration x rate, audio off $0.224/s "
          "with elements ($0.112/s without)")
    check("CF-P1-006-R2-PREFLIGHT-STORYBOARD-cost-total",
          cost_plan["totals"]["total_generation_cost_usd_exact"]
          == total_cost_usd(shots, audio=False) == 10.752
          and cost_plan["totals"]["total_generation_cost_usd_rounded"]
          == 10.75
          and cost_plan["totals"]["total_generated_seconds"] == 48
          and cost_plan["totals"]["shot_count"] == len(shots),
          f"total is {cost_plan['totals']}")
    check("CF-P1-006-R2-PREFLIGHT-STORYBOARD-cost-not-audio-on",
          total_cost_usd(shots, audio=True) == 16.128
          and cost_plan["totals"]["total_generation_cost_usd_exact"]
          != total_cost_usd(shots, audio=True),
          "the plan uses the audio-off WITH-ELEMENTS rate, not "
          "the $16.13 audio-on-with-elements figure")
    check("CF-P1-006-R2-PREFLIGHT-STORYBOARD-cost-keyframe-zero",
          cost_plan["keyframe_generation_cost"]["cost_usd_billed"] == 0
          and cost_plan["keyframe_generation_cost"]["keyframes"]
          == len(shots),
          "keyframe generation is $0 billed, not an invented number")

    # --- retry cost ---------------------------------------------
    check("CF-P1-006-R2-PREFLIGHT-STORYBOARD-retry-per-shot",
          retry_budget_usd([shots[0]], retries_per_shot=1) == 1.344,
          "one retry of one 6 s shot costs $1.344")
    check("CF-P1-006-R2-PREFLIGHT-STORYBOARD-retry-max-budget",
          retry_budget_usd(shots, retries_per_shot=1) == 10.752
          and cost_plan["retry_budget"]["max_retry_budget_usd"] == 10.752
          and cost_plan["retry_budget"]["max_retry_budget_usd_rounded"]
          == 10.75,
          "maximum retry budget is one retry per failed shot")
    check("CF-P1-006-R2-PREFLIGHT-STORYBOARD-retry-worst-case",
          cost_plan["retry_budget"]["worst_case_total_usd"] == 21.5,
          "worst case = generation $10.752 + full retry $10.752 "
          "= $21.504, rounded $21.50")
    check("CF-P1-006-R2-PREFLIGHT-STORYBOARD-retry-rule-recorded",
          "One retry per failed shot" in
          cost_plan["retry_budget"]["rule"],
          "the retry budget rule is stated, not implied")

    # --- dynamic shot count (no constants, no ceilings) ---------
    derived = derive_counts(shots, voice.get("lines") or [])
    check("CF-P1-006-R2-PREFLIGHT-STORYBOARD-counts-dynamic",
          derived["shots"] == len(shots) == 8
          and derived["scenes"] == 6
          and derived["keyframes"] == 8
          and derived["clips"] == 8
          and derived["lines"] == 8
          and derived["total_video_seconds"] == 48.0
          and coverage["counts"]["shots"] == derived["shots"]
          and coverage["counts"]["scenes"] == derived["scenes"]
          and coverage["counts"]["total_video_seconds"]
          == derived["total_video_seconds"],
          f"derived counts are {derived}")
    check("CF-P1-006-R2-PREFLIGHT-STORYBOARD-counts-match-driver-inputs",
          scenes["counts"]["shots"] == len(shots)
          and durations["total_video_seconds"] == 48
          and project["i2v"]["clips"] == len(shots)
          and project["i2v"]["total_video_seconds"] == 48,
          "scene breakdown, duration plan and project agree on the counts")
    check("CF-P1-006-R2-PREFLIGHT-STORYBOARD-no-shot-count-ceiling",
          derive_counts(
              [{"shot_id": f"s{i}", "scene_id": f"SC{i}",
                "visual": {"duration_seconds": 6}}
               for i in range(1, 13)], [])["shots"] == 12
          and derive_counts(
              [{"shot_id": "s1", "scene_id": "SC1",
                "visual": {"duration_seconds": 6}}], [])["shots"] == 1,
          "a 12-shot storyboard derives 12 shots; a 1-shot one derives 1")
    check("CF-P1-006-R2-PREFLIGHT-STORYBOARD-no-clip-count-ceiling",
          derive_counts(
              [{"shot_id": f"s{i}", "scene_id": "SC1",
                "visual": {"duration_seconds": 5}}
               for i in range(1, 16)], [])["clips"] == 15
          and derive_counts(
              [{"shot_id": f"s{i}", "scene_id": "SC1",
                "visual": {"duration_seconds": 5}}
               for i in range(1, 16)], [])
          ["total_video_seconds"] == 75.0,
          "a 15-clip storyboard derives 15 clips and 75 s")
    check("CF-P1-006-R2-PREFLIGHT-STORYBOARD-counts-not-fixed-eight",
          coverage["counts_vs_r2_draft"]["shots_added"] == []
          and coverage["counts_vs_r2_draft"]["shots_removed"] == []
          and "UNCHANGED" in
          coverage["counts_vs_r2_draft"]["verdict"],
          "the report records the count comparison explicitly instead of "
          "assuming eight")

    # --- location coverage ---------------------------------------
    loc_names = {loc["name"] for loc in locations["locations"]}
    check("CF-P1-006-R2-PREFLIGHT-STORYBOARD-locations-covered",
          loc_names == {"rooftop terrace",
                        "river (stone steps + water's edge)",
                        "market street"}
          and len(locations["locations"]) == 3,
          f"locations are {sorted(loc_names)}")
    for loc in locations["locations"]:
        cov = loc["coverage"]
        check("CF-P1-006-R2-PREFLIGHT-STORYBOARD-location-"
              f"{loc['location_id']}-aspects",
              set(cov) == {"exterior_establishing",
                           "interior_establishing", "wide_environment",
                           "character_arrival",
                           "character_movement_through_location",
                           "relevant_objects_spatial_relationships",
                           "detail_shots", "reaction_shots",
                           "closing_departure"}
              and all(entry.get("covered") is True
                      and entry.get("note")
                      for entry in cov.values()),
              f"location {loc['name']}: every aspect covered or "
              "explicitly not-applicable with a note")
    check("CF-P1-006-R2-PREFLIGHT-STORYBOARD-location-scenes-match",
          sorted({sc for loc in locations["locations"]
                  for sc in loc["scenes"]})
          == ["SC1", "SC2", "SC3", "SC4", "SC5", "SC6"],
          "every scene belongs to a covered location")

    # --- every shot: narrative purpose + source line -------------
    for shot in shots:
        record = shot.get("prompt_record") or {}
        line = [ln for ln in voice.get("lines") or []
                if ln.get("line_id") == shot.get("line_id")]
        check("CF-P1-006-R2-PREFLIGHT-STORYBOARD-shot-purpose-"
              f"{shot['shot_id']}",
              bool(record.get("narrative_purpose"))
              and bool(record.get("source_script_segment"))
              and len(line) == 1
              and record["source_script_segment"] == line[0]["text"]
              and record["scene_id"] == shot["scene_id"]
              and record["shot_id"] == shot["shot_id"],
              f"shot {shot['shot_id']}: purpose + verbatim source line")
    check("CF-P1-006-R2-PREFLIGHT-STORYBOARD-coverage-lines",
          len(coverage["line_coverage"]) == 8
          and all(entry.get("covered") is True
                  for entry in coverage["line_coverage"]),
          "all 8 narration lines are covered by exactly one shot each")

    # --- motion prompts + no-text policy --------------------------
    for shot in shots:
        mp = shot.get("motion_prompt") or {}
        record = shot.get("prompt_record") or {}
        composed = "; ".join(mp.get(f, "").strip()
                             for f in MOTION_FIELDS)
        composed = f"{composed}. {TEXT_PROHIBITION_CLAUSE}"
        check("CF-P1-006-R2-PREFLIGHT-STORYBOARD-motion-prompt-"
              f"{shot['shot_id']}",
              all(isinstance(mp.get(f), str) and mp.get(f).strip()
                  for f in MOTION_FIELDS)
              and len(composed) <= 2500
              and record.get("negative_prompt")
              and "on-screen text" in record["negative_prompt"]
              and record.get("style_lock")
              and "Photorealistic digital human only"
              in record["style_lock"]
              and record.get("physical_realism_constraints"),
              f"shot {shot['shot_id']}: 7 motion fields, negative "
              "prompt, style lock, realism constraints, prompt fits")
    check("CF-P1-006-R2-PREFLIGHT-STORYBOARD-character-map",
          appearances["characters"][0]["shot_count"] == len(shots)
          and len(appearances["appearances"]) == len(shots)
          and all(a.get("present") is True
                  and a.get("speaks_on_screen") is False
                  for a in appearances["appearances"]),
          "Nadia appears in every shot and speaks on screen in none")

    # --- generate_audio: false in every shot record --------------
    check("CF-P1-006-R2-PREFLIGHT-STORYBOARD-audio-off-every-shot",
          all(shot.get("generate_audio") is False for shot in shots)
          and all((shot.get("provider_generation") or {}).get(
              "generate_audio") is False for shot in shots)
          and all((shot.get("prompt_record") or {}).get(
              "generate_audio") is False for shot in shots),
          "shot, provider_generation and prompt_record all say false")
    check("CF-P1-006-R2-PREFLIGHT-STORYBOARD-audio-off-project",
          project["i2v"].get("generate_audio") is False,
          "project.json i2v block records audio off")
    check("CF-P1-006-R2-PREFLIGHT-STORYBOARD-audio-off-cost-plan",
          cost_plan["pricing"]["audio_setting"] is False
          and cost_plan["pricing"]["rate_audio_off_usd_per_second"]
          == RATE_ELEMENTS_AUDIO_OFF
          and cost_plan["pricing"]["uses_elements"] is True,
          "the cost plan prices the audio-off WITH-ELEMENTS rate")

    # --- text overlay disabled in every shot record --------------
    check("CF-P1-006-R2-PREFLIGHT-STORYBOARD-text-off-every-shot",
          all(all((shot.get("text_overlay") or {}).get(flag) is False
                  for flag in TEXT_FLAGS) for shot in shots),
          "all six text-overlay flags are false in every shot")
    check("CF-P1-006-R2-PREFLIGHT-STORYBOARD-text-off-project",
          all(project.get("text_overlay_policy", {}).get(flag) is False
              for flag in TEXT_FLAGS),
          "the project text-overlay policy is all false")

    # --- paid submission blocked without explicit authorization ---
    check("CF-P1-006-R2-PREFLIGHT-STORYBOARD-gates-both-required",
          paid_generation_allowed(True, True) is True
          and paid_generation_allowed(True, False) is False
          and paid_generation_allowed(False, True) is False
          and paid_generation_allowed(False, False) is False,
          "both gates must pass; one gate alone never authorizes")
    check("CF-P1-006-R2-PREFLIGHT-STORYBOARD-gates-not-inferred",
          paid_generation_allowed("approved", True) is False
          and paid_generation_allowed(True, "approved") is False
          and paid_generation_allowed(None, None) is False
          and paid_generation_allowed(1, 1) is False,
          "a string, None or 1 is never approval — only boolean True")
    gate_a_text = open(os.path.join(
        ROOT_ABS, "docs", "implementation",
        "CF-WO-P1-006-R2-PREFLIGHT-gate-a-checklist.md"),
        encoding="utf-8").read()
    gate_b_text = open(os.path.join(
        ROOT_ABS, "docs", "implementation",
        "CF-WO-P1-006-R2-PREFLIGHT-gate-b-authorization.md"),
        encoding="utf-8").read()
    check("CF-P1-006-R2-PREFLIGHT-STORYBOARD-gates-unchecked",
          "- [ ]" in gate_a_text
          and "- [x]" not in gate_a_text
          and "- [ ]" in gate_b_text
          and "- [x]" not in gate_b_text,
          "no gate item is marked approved in either document")

    # --- no provider call during preflight (mock transport only) --
    mock = MockTransport()  # mock transport
    errors = run_preflight_checks(EXAMPLE, transport=mock)
    check("CF-P1-006-R2-PREFLIGHT-STORYBOARD-no-provider-call-mock",
          errors == [] and mock.calls == [],
          "preflight checks pass with zero calls through the mock "
          "transport")
    recorder = MockTransport()  # mock transport
    try:
        recorder.request("POST", "https://example.invalid")
        recorded = False
    except AssertionError:
        recorded = len(recorder.calls) == 1
    check("CF-P1-006-R2-PREFLIGHT-STORYBOARD-mock-records-calls",
          recorded,
          "mock transport records a call instead of sending it")
    try:
        probe = MockTransport()  # mock transport
        probe.request("POST", "https://example.invalid")
        check("CF-P1-006-R2-PREFLIGHT-STORYBOARD-mock-refuses",
              False, "mock transport unexpectedly sent a request")
    except AssertionError:
        check("CF-P1-006-R2-PREFLIGHT-STORYBOARD-mock-refuses", True)

    print(f"\n{_checks[0]} checks, {len(failures)} failures")
    if failures:
        print("FAILURES: " + ", ".join(failures))
        return 1
    return 0


def main():
    return run_checks()


if __name__ == "__main__":
    sys.exit(main())
