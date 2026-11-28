#!/usr/bin/env python3
"""Preflight tests (CF-WO-P1-006-R2-PREFLIGHT).

Covers the preflight round on top of the R2 I2V runtime:
Kling elements conditioning (exact payload fields, frontal +
1-3 additional references, prompt @Element references,
video_url / voice_id refusal), identity-reference validation
(missing / pending / unpermitted references block), the
provider-specific GCS output policy (only
storage.googleapis.com/falserverless/ plus the fal CDN
origins), download validation (content type, MP4 magic, no
authorization header on downloads, redirect validation),
retention headers (X-Fal-Store-IO: 0, lifecycle + ACL with
fal-CDN-v3-only scope, ZDR UNCONFIRMED), generate_audio
false, text-overlay prohibition, the paid-submission
authorization gate, the post-generation drift-review record
type, and the zero-network-call preflight path.

FFmpeg/ffprobe are REQUIRED: when they are absent the suite
fails (exit 1) instead of skipping. All generated media lives
in tempfile dirs. No test here calls a paid provider: the
fal.ai adapter is exercised only over injected mock
transports (labelled mock), and the mock adapter used for
execution tests is labelled mock in every check name that
uses it. The fake credential value used to exercise the
adapter's header handling is a test string, never a real
credential. No test generates a real character image:
fixture references are FFmpeg-generated frames.
"""

import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.join(os.path.dirname(__file__), "..")
ROOT_ABS = os.path.abspath(ROOT)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
from runtime import image_to_video as iv  # noqa: E402
from runtime.media_adapters import (  # noqa: E402
    PROVIDER_SPECS, HttpProviderAdapter)
from runtime.media_execution import MediaExecutionError  # noqa: E402
from runtime.provider_contracts import (  # noqa: E402
    FAL_ZDR_STATUS, fal_retention_headers,
    fal_retention_truth_table, validate_fal_video_elements)
from runtime.provider_url_policy import (  # noqa: E402
    FAL_VIDEO_GCS_OUTPUT_EXAMPLE, ProviderURLPolicy,
    record_result_url)

PROJECT_ID = "p1006-r2-photorealistic-image-to-video"
GCS_URL = FAL_VIDEO_GCS_OUTPUT_EXAMPLE
GCS_SIGNED_URL = (GCS_URL + "?X-Goog-Algorithm=GOOG4-RSA-SHA256"
                  "&X-Goog-Signature=test-signature-token")

failures = []
_checks = [0]


def check(name, cond, detail=""):
    _checks[0] += 1
    if cond:
        print(f"PASS {name}")
    else:
        print(f"FAIL {name} {detail}")
        failures.append(name)


def expect_error(label, fn, kinds=(Exception,)):
    try:
        fn()
    except kinds:
        check(label, True)
        return None
    except Exception as exc:  # noqa: BLE001 - any other error fails
        check(label, False, f"raised {type(exc).__name__}: {exc}")
        return None
    check(label, False, "operation succeeded instead of refusing")
    return None


def run_ffmpeg(argv, label):
    proc = subprocess.run(argv, capture_output=True, text=True,
                          timeout=300)
    if proc.returncode != 0:
        raise RuntimeError(
            f"{label} failed: {(proc.stderr or '').strip()[:400]}")
    return proc


def make_png(path, width=576, height=1024):
    run_ffmpeg(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                "-i", f"testsrc2=size={width}x{height}:duration=0.1",
                "-frames:v", "1", path], "fixture png")


def make_mp4(path, width=1080, height=1920, seconds=6):
    run_ffmpeg(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                "-i", f"testsrc2=size={width}x{height}:rate=30:"
                f"duration={seconds}",
                "-t", str(seconds), "-c:v", "libx264",
                "-pix_fmt", "yuv420p", path], "fixture mp4")


def sha256_file(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def set_env(name, value):
    old = os.environ.get(name)
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value
    return old


def restore_env(name, old):
    if old is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = old


def motion_prompt(**overrides):
    prompt = {
        "subject": "Nadia (@Element1) lights the round paper "
                   "lantern",
        "face": "She looks down, blinking slowly, focused.",
        "body": "She leans slightly over the table, settled.",
        "hand_prop": "Both hands cup the flame and steady it.",
        "hair_cloth": "Her hair and shirt move in the breeze.",
        "environment": "The dawn sky brightens behind her.",
        "camera": "Steady medium shot, drifting in slowly.",
    }
    prompt.update(overrides)
    return prompt


def valid_auth(scope, max_generations=8):
    return {"authorized_by": "test-user",
            "provider_id": iv.PROVIDER_ID,
            "model": iv.MODEL_ID,
            "operation": iv.OPERATION,
            "max_generations": max_generations,
            "scope": list(scope)}


def ref_record(asset_id, path, sha, status="approved",
               permitted=True):
    return {"asset_id": asset_id, "path": path, "sha256": sha,
            "mime": "image/png", "status": status,
            "transmission_permitted": permitted}


def binding(character_id, frontal, additional):
    return {"character_id": character_id, "frontal": frontal,
            "additional": list(additional)}


def shot(shot_id="s1", scene_id="SC1", character_id="DEMO-CHAR-002",
         keyframe_file=None, keyframe_sha=None):
    entry = {"shot_id": shot_id, "scene_id": scene_id,
             "reference_ids": ["ref-nadia-front"],
             "visual": {"kind": "i2v-clip", "duration_seconds": 6},
             "keyframe": {"file": keyframe_file,
                          "sha256": keyframe_sha,
                          "status": "pending-generation-after-"
                          "script-approval" if keyframe_file is None
                          else "generated"},
             "motion_prompt": motion_prompt()}
    if character_id is not None:
        entry["character_id"] = character_id
    return entry


def fal_policy():
    return ProviderURLPolicy(
        api_origins=["queue.fal.run"],
        output_origins=["fal.media", "v3b.fal.media",
                        "storage.googleapis.com"],
        output_path_prefixes={
            "storage.googleapis.com": ["/falserverless/"]},
        resolver=lambda host: ["93.184.216.34"])


class MockAdapter:
    """Mock I2V adapter (labelled mock): counts submissions and
    replays scripted poll outcomes. Never touches a network."""

    def __init__(self, *, clip_path=None, poll_outcomes=None):
        self.clip_path = clip_path
        self.poll_outcomes = list(poll_outcomes or [])
        self.submit_calls = 0
        self.poll_calls = 0
        self.last_result_url_record = None

    def translate(self, packet, context):
        built = iv.build_i2v_request(
            iv.PROVIDER_ID, iv.MODEL_ID,
            prompt=packet["canonical_instruction"],
            start_image_url=context["start_image_url"],
            duration_seconds=int(context.get("duration", "6")),
            generate_audio=context.get("generate_audio", True),
            elements=context.get("elements"))
        return {"contract_request": built}

    def submit(self, request, context):
        self.submit_calls += 1
        return {"provider_job_id": "mock-job-001",
                "completed": False, "output": None, "failure": None,
                "status_url": "https://mock.invalid/status",
                "response_url": "https://mock.invalid/response",
                "cancel_url": "https://mock.invalid/cancel"}

    def poll(self, job_id, context):
        self.poll_calls += 1
        if self.poll_outcomes:
            return self.poll_outcomes.pop(0)
        return {"completed": True,
                "output": {"path": self.clip_path},
                "failure": None}


def run_checks():
    tmpdir = tempfile.mkdtemp(prefix="cf-p1006-r2-preflight-")
    try:
        return _run_checks(tmpdir)
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


def _run_checks(tmpdir):
    # ---- fixture references ------------------------------------
    frontal_path = os.path.join(tmpdir, "ref-front.png")
    angle_paths = [os.path.join(tmpdir, f"ref-angle-{n}.png")
                   for n in (1, 2, 3, 4)]
    make_png(frontal_path)
    for path in angle_paths:
        make_png(path)
    frontal_sha = sha256_file(frontal_path)
    angle_shas = [sha256_file(p) for p in angle_paths]
    with open(frontal_path, "rb") as handle:
        frontal_bytes = handle.read()

    def good_binding():
        return binding(
            "DEMO-CHAR-002",
            ref_record("ref-nadia-front", frontal_path, frontal_sha),
            [ref_record(f"ref-nadia-angle-{n}", angle_paths[n - 1],
                        angle_shas[n - 1]) for n in (1, 2)])

    # ---- elements payload: exact fields (contract level) -------
    element = {"frontal_image_url": "https://example.invalid/"
               "front.png",
               "reference_image_urls": [
                   "https://example.invalid/angle-1.png"]}
    request = iv.build_i2v_request(
        iv.PROVIDER_ID, iv.MODEL_ID,
        prompt="Nadia (@Element1) lights the lantern. "
               + iv.TEXT_PROHIBITION_CLAUSE,
        start_image_url="data:image/png;base64,AAAA",
        duration_seconds=6, generate_audio=False,
        elements=[element])
    check("CF-P1-006-R2-PREFLIGHT-elements-exact-fields",
          request["body"]["elements"] == [element]
          and set(request["body"]["elements"][0].keys()) == {
              "frontal_image_url", "reference_image_urls"}
          and request["body"]["start_image_url"]
          == "data:image/png;base64,AAAA")
    check("CF-P1-006-R2-PREFLIGHT-elements-start-image-separate",
          request["body"]["elements"][0]["frontal_image_url"]
          != request["body"]["start_image_url"]
          and request["body"]["start_image_url"]
          not in request["body"]["elements"][0][
              "reference_image_urls"])
    two = [element,
           {"frontal_image_url": "https://example.invalid/"
            "front-2.png",
            "reference_image_urls": [
                "https://example.invalid/angle-2.png"]}]
    request2 = iv.build_i2v_request(
        iv.PROVIDER_ID, iv.MODEL_ID,
        prompt="@Element1 meets @Element2 by the river. "
               + iv.TEXT_PROHIBITION_CLAUSE,
        start_image_url="data:image/png;base64,AAAA",
        duration_seconds=6, generate_audio=False, elements=two)
    check("CF-P1-006-R2-PREFLIGHT-elements-two-characters",
          request2["body"]["elements"] == two
          and len(request2["body"]["elements"]) == 2)
    validated = validate_fal_video_elements(
        two, "@Element1 meets @Element2.")
    check("CF-P1-006-R2-PREFLIGHT-elements-validator-order",
          validated == two)

    # ---- elements: prompt references must match the array -----
    expect_error(
        "CF-P1-006-R2-PREFLIGHT-elements-unreferenced",
        lambda: iv.build_i2v_request(
            iv.PROVIDER_ID, iv.MODEL_ID,
            prompt="Nadia lights the lantern.",
            start_image_url="data:image/png;base64,AAAA",
            elements=[element]))
    expect_error(
        "CF-P1-006-R2-PREFLIGHT-elements-reference-beyond-array",
        lambda: iv.build_i2v_request(
            iv.PROVIDER_ID, iv.MODEL_ID,
            prompt="@Element1 meets @Element2.",
            start_image_url="data:image/png;base64,AAAA",
            elements=[element]))
    expect_error(
        "CF-P1-006-R2-PREFLIGHT-elements-empty-array",
        lambda: iv.build_i2v_request(
            iv.PROVIDER_ID, iv.MODEL_ID,
            prompt="@Element1 lights the lantern.",
            start_image_url="data:image/png;base64,AAAA",
            elements=[]))

    # ---- elements: per-element field rules ---------------------
    expect_error(
        "CF-P1-006-R2-PREFLIGHT-elements-no-frontal",
        lambda: validate_fal_video_elements(
            [{"reference_image_urls": [
                "https://example.invalid/a.png"]}],
            "@Element1 walks."))
    expect_error(
        "CF-P1-006-R2-PREFLIGHT-elements-no-images-at-all",
        lambda: validate_fal_video_elements(
            [{"frontal_image_url": "",
              "reference_image_urls": []}],
            "@Element1 walks."))
    expect_error(
        "CF-P1-006-R2-PREFLIGHT-elements-zero-references",
        lambda: validate_fal_video_elements(
            [{"frontal_image_url": "https://example.invalid/f.png",
              "reference_image_urls": []}],
            "@Element1 walks."))
    expect_error(
        "CF-P1-006-R2-PREFLIGHT-elements-four-references",
        lambda: validate_fal_video_elements(
            [{"frontal_image_url": "https://example.invalid/f.png",
              "reference_image_urls": [
                  "https://example.invalid/a1.png",
                  "https://example.invalid/a2.png",
                  "https://example.invalid/a3.png",
                  "https://example.invalid/a4.png"]}],
            "@Element1 walks."))
    for count in (1, 2, 3):
        refs = [f"https://example.invalid/a{n}.png"
                for n in range(count)]
        check(f"CF-P1-006-R2-PREFLIGHT-elements-refs-{count}-ok",
              validate_fal_video_elements(
                  [{"frontal_image_url":
                    "https://example.invalid/f.png",
                    "reference_image_urls": refs}],
                  "@Element1 walks.") == [
                      {"frontal_image_url":
                       "https://example.invalid/f.png",
                       "reference_image_urls": refs}])
    expect_error(
        "CF-P1-006-R2-PREFLIGHT-elements-video-url-refused",
        lambda: validate_fal_video_elements(
            [{"frontal_image_url": "https://example.invalid/f.png",
              "reference_image_urls": [
                  "https://example.invalid/a.png"],
              "video_url": "https://example.invalid/v.mp4"}],
            "@Element1 walks."))
    expect_error(
        "CF-P1-006-R2-PREFLIGHT-elements-voice-id-refused",
        lambda: validate_fal_video_elements(
            [{"frontal_image_url": "https://example.invalid/f.png",
              "reference_image_urls": [
                  "https://example.invalid/a.png"],
              "voice_id": "some-voice"}],
            "@Element1 walks."))
    expect_error(
        "CF-P1-006-R2-PREFLIGHT-elements-unknown-field",
        lambda: validate_fal_video_elements(
            [{"frontal_image_url": "https://example.invalid/f.png",
              "reference_image_urls": [
                  "https://example.invalid/a.png"],
              "surprise": True}],
            "@Element1 walks."))

    # ---- multi_prompt: design restriction, not a provider gap -
    try:
        iv.build_i2v_request(
            iv.PROVIDER_ID, iv.MODEL_ID, prompt="test",
            start_image_url="data:image/png;base64,AAAA",
            elements=None)
        check("CF-P1-006-R2-PREFLIGHT-multi-prompt-baseline",
              True)
    except Exception as exc:  # noqa: BLE001 - baseline must pass
        check("CF-P1-006-R2-PREFLIGHT-multi-prompt-baseline",
              False, str(exc))
    try:
        iv.build_i2v_request(
            iv.PROVIDER_ID, iv.MODEL_ID, prompt="test",
            start_image_url="data:image/png;base64,AAAA")
        # Direct contract call carrying multi_prompt:
        from runtime.provider_contracts import get_contract
        get_contract(iv.PROVIDER_ID).build_request(
            {"canonical_instruction": "test"},
            {"start_image_url": "data:image/png;base64,AAAA",
             "multi_prompt": [{"prompt": "a", "duration": "5"}]},
            iv.MODEL_ID)
        check("CF-P1-006-R2-PREFLIGHT-multi-prompt-refused",
              False, "multi_prompt was accepted")
    except MediaExecutionError as exc:
        text = " ".join(exc.errors)
        check("CF-P1-006-R2-PREFLIGHT-multi-prompt-refused",
              "design restriction" in text
              and "one shot is one generation" in text
              and "documents the field" in text, text)

    # ---- identity reference validation -------------------------
    good = good_binding()
    check("CF-P1-006-R2-PREFLIGHT-binding-valid",
          iv.validate_identity_binding(good) == [])
    check("CF-P1-006-R2-PREFLIGHT-reference-valid",
          iv.validate_reference_asset(good["frontal"]) == [])
    missing = binding(
        "DEMO-CHAR-002",
        ref_record("ref-missing", os.path.join(tmpdir, "nope.png"),
                   "0" * 64),
        [ref_record("ref-nadia-angle-1", angle_paths[0],
                    angle_shas[0])])
    check("CF-P1-006-R2-PREFLIGHT-reference-missing-file",
          iv.validate_identity_binding(missing) != [])
    wrong_sha = binding(
        "DEMO-CHAR-002",
        ref_record("ref-nadia-front", frontal_path, "0" * 64),
        [ref_record("ref-nadia-angle-1", angle_paths[0],
                    angle_shas[0])])
    check("CF-P1-006-R2-PREFLIGHT-reference-hash-mismatch",
          iv.validate_identity_binding(wrong_sha) != [])
    pending = binding(
        "DEMO-CHAR-002",
        ref_record("ref-nadia-front", frontal_path, frontal_sha,
                   status="pending-generation-after-script-approval"),
        [ref_record("ref-nadia-angle-1", angle_paths[0],
                    angle_shas[0])])
    pending_errors = iv.validate_identity_binding(pending)
    check("CF-P1-006-R2-PREFLIGHT-reference-pending-blocks",
          pending_errors != []
          and "BLOCKED" in " ".join(pending_errors),
          " ".join(pending_errors))
    unpermitted = binding(
        "DEMO-CHAR-002",
        ref_record("ref-nadia-front", frontal_path, frontal_sha,
                   permitted=False),
        [ref_record("ref-nadia-angle-1", angle_paths[0],
                    angle_shas[0])])
    check("CF-P1-006-R2-PREFLIGHT-reference-no-permission",
          iv.validate_identity_binding(unpermitted) != [])
    no_additional = binding(
        "DEMO-CHAR-002",
        ref_record("ref-nadia-front", frontal_path, frontal_sha),
        [])
    check("CF-P1-006-R2-PREFLIGHT-binding-zero-additional",
          iv.validate_identity_binding(no_additional) != [])
    four_additional = binding(
        "DEMO-CHAR-002",
        ref_record("ref-nadia-front", frontal_path, frontal_sha),
        [ref_record(f"ref-nadia-angle-{n}", angle_paths[n - 1],
                    angle_shas[n - 1]) for n in (1, 2, 3, 4)])
    check("CF-P1-006-R2-PREFLIGHT-binding-four-additional",
          iv.validate_identity_binding(four_additional) != [])
    no_frontal = {"character_id": "DEMO-CHAR-002",
                  "additional": [ref_record(
                      "ref-nadia-angle-1", angle_paths[0],
                      angle_shas[0])]}
    check("CF-P1-006-R2-PREFLIGHT-binding-no-frontal",
          iv.validate_identity_binding(no_frontal) != [])
    expect_error(
        "CF-P1-006-R2-PREFLIGHT-payload-pending-raises",
        lambda: iv.build_elements_payload([pending]))
    payload = iv.build_elements_payload([good])
    check("CF-P1-006-R2-PREFLIGHT-payload-from-binding",
          len(payload) == 1
          and payload[0]["frontal_image_url"].startswith(
              "data:image/png;base64,")
          and len(payload[0]["reference_image_urls"]) == 2
          and base64.b64decode(
              payload[0]["frontal_image_url"].split(",", 1)[1])
          == frontal_bytes)

    # ---- shot-level elements -----------------------------------
    check("CF-P1-006-R2-PREFLIGHT-shot-no-character-no-elements",
          iv.build_shot_elements(
              shot("s9", "SC9", character_id=None),
              {"s9": [good]}) is None)
    check("CF-P1-006-R2-PREFLIGHT-shot-character-gets-elements",
          iv.build_shot_elements(shot("s1", "SC1"),
                                 {"s1": [good]}) == payload)
    expect_error(
        "CF-P1-006-R2-PREFLIGHT-shot-missing-binding-blocks",
        lambda: iv.build_shot_elements(shot("s1", "SC1"), {}))
    check("CF-P1-006-R2-PREFLIGHT-shot-legacy-none",
          iv.build_shot_elements(shot("s1", "SC1"), None) is None)

    # ---- execution plan with identity bindings -----------------
    delivery_root = os.path.join(tmpdir, "delivery")
    os.makedirs(delivery_root)
    keyframe_path = os.path.join(delivery_root, "keyframe-s1.png")
    make_png(keyframe_path, width=1152, height=2048)
    ready_sha = sha256_file(keyframe_path)
    ready_shot = shot("s1", "SC1",
                      keyframe_file="keyframe-s1.png",
                      keyframe_sha=ready_sha)
    ready_project = {"project_id": PROJECT_ID,
                     "script_status": "APPROVED",
                     "text_overlay_policy": iv.TEXT_OVERLAY_POLICY,
                     "voice_lines": [{"line_id": "l1"}]}
    scope = ["ref-nadia-front", "ref-nadia-angle-1",
             "ref-nadia-angle-2", "ref-nadia-front",
             "scene-s1"]
    ready_auth = valid_auth(scope, max_generations=1)
    ready_plan = iv.build_execution_plan(
        ready_project, [ready_shot], authorization=ready_auth,
        generate_audio=False, identity_bindings={"s1": [good]})
    check("CF-P1-006-R2-PREFLIGHT-plan-ready-with-elements",
          ready_plan["status"] == "READY"
          and len(ready_plan["generations"]) == 1
          and ready_plan["generations"][0].get("elements")
          == payload
          and ready_plan["generations"][0]["generate_audio"]
          is False
          and ready_plan["zdr_status"] == "UNCONFIRMED",
          str(ready_plan.get("blocked_reasons")))
    check("CF-P1-006-R2-PREFLIGHT-plan-generate-audio-false",
          all(gen["generate_audio"] is False
              for gen in ready_plan["generations"]))
    pending_plan = iv.build_execution_plan(
        ready_project, [ready_shot], authorization=ready_auth,
        generate_audio=False, identity_bindings={"s1": [pending]})
    check("CF-P1-006-R2-PREFLIGHT-plan-pending-reference-blocked",
          pending_plan["status"] == "BLOCKED"
          and any("identity" in r
                  for r in pending_plan["blocked_reasons"]),
          str(pending_plan.get("blocked_reasons")))
    missing_plan = iv.build_execution_plan(
        ready_project, [ready_shot], authorization=ready_auth,
        generate_audio=False, identity_bindings={})
    check("CF-P1-006-R2-PREFLIGHT-plan-missing-binding-blocked",
          missing_plan["status"] == "BLOCKED"
          and any("identity" in r
                  for r in missing_plan["blocked_reasons"]))
    env_shot = shot("s9", "SC9", character_id=None,
                    keyframe_file="keyframe-s1.png",
                    keyframe_sha=ready_sha)
    env_plan = iv.build_execution_plan(
        ready_project, [env_shot], authorization=ready_auth,
        generate_audio=False, identity_bindings={})
    check("CF-P1-006-R2-PREFLIGHT-plan-non-character-no-elements",
          env_plan["status"] == "READY"
          and "elements" not in env_plan["generations"][0],
          str(env_plan.get("blocked_reasons")))
    bad_prompt_shot = shot("s1", "SC1",
                           keyframe_file="keyframe-s1.png",
                           keyframe_sha=ready_sha)
    bad_prompt_shot["motion_prompt"] = motion_prompt(
        subject="Nadia lights the round paper lantern")
    bad_prompt_plan = iv.build_execution_plan(
        ready_project, [bad_prompt_shot],
        authorization=ready_auth, generate_audio=False,
        identity_bindings={"s1": [good]})
    check("CF-P1-006-R2-PREFLIGHT-plan-prompt-elements-mismatch",
          bad_prompt_plan["status"] == "BLOCKED"
          and any("prompt/elements" in r
                  for r in bad_prompt_plan["blocked_reasons"]))

    # ---- text overlay disabled in the plan ---------------------
    bad_text_project = dict(ready_project)
    bad_text_project["text_overlay_policy"] = {
        **iv.TEXT_OVERLAY_POLICY, "watermark_enabled": True}
    bad_text_plan = iv.build_execution_plan(
        bad_text_project, [ready_shot], authorization=ready_auth,
        generate_audio=False, identity_bindings={"s1": [good]})
    check("CF-P1-006-R2-PREFLIGHT-plan-text-overlay-blocked",
          bad_text_plan["status"] == "BLOCKED"
          and any("text overlay" in r
                  for r in bad_text_plan["blocked_reasons"]))

    # ---- elements-aware plan pricing ---------------------------
    # With elements, audio off, a 6 s shot costs 6 x $0.224 =
    # $1.344 (the plan total rounds to 2 decimals: $1.34 for
    # one shot). Without elements the same shot costs 6 x
    # $0.112 = $0.672. A mixed plan prices EACH shot by its
    # own elements usage and its plan-level rate is None (no
    # single rate covers both tiers).
    check("CF-P1-006-R2-PREFLIGHT-plan-cost-with-elements",
          ready_plan["estimated_cost_usd"] == 1.34
          and ready_plan["rate_usd_per_second"] == 0.224
          and ready_plan["generations"][0]["uses_elements"]
          is True
          and ready_plan["generations"][0][
              "rate_usd_per_second"] == 0.224
          and ready_plan["generations"][0][
              "estimated_cost_usd"] == 1.344,
          str(ready_plan.get("estimated_cost_usd")))
    check("CF-P1-006-R2-PREFLIGHT-plan-cost-no-character",
          env_plan["status"] == "READY"
          and env_plan["estimated_cost_usd"] == 0.67
          and env_plan["rate_usd_per_second"] == 0.112
          and env_plan["generations"][0]["uses_elements"]
          is False
          and env_plan["generations"][0][
              "rate_usd_per_second"] == 0.112
          and env_plan["generations"][0][
              "estimated_cost_usd"] == 0.672,
          str(env_plan.get("estimated_cost_usd")))
    legacy_plan = iv.build_execution_plan(
        ready_project, [ready_shot], authorization=ready_auth,
        generate_audio=False, identity_bindings=None)
    check("CF-P1-006-R2-PREFLIGHT-plan-cost-legacy-no-bindings",
          legacy_plan["status"] == "READY"
          and "elements" not in legacy_plan["generations"][0]
          and legacy_plan["estimated_cost_usd"] == 0.67
          and legacy_plan["rate_usd_per_second"] == 0.112
          and legacy_plan["generations"][0]["uses_elements"]
          is False
          and legacy_plan["generations"][0][
              "rate_usd_per_second"] == 0.112
          and legacy_plan["generations"][0][
              "estimated_cost_usd"] == 0.672,
          str(legacy_plan.get("estimated_cost_usd")))
    mixed_auth = valid_auth(scope, max_generations=2)
    mixed_plan = iv.build_execution_plan(
        ready_project, [ready_shot, env_shot],
        authorization=mixed_auth, generate_audio=False,
        identity_bindings={"s1": [good]})
    mixed_gens = mixed_plan["generations"]
    check("CF-P1-006-R2-PREFLIGHT-plan-cost-mixed-elements",
          mixed_plan["status"] == "READY"
          and mixed_plan["estimated_cost_usd"] == 2.02
          and mixed_plan["rate_usd_per_second"] is None
          and mixed_gens[0]["uses_elements"] is True
          and mixed_gens[0]["rate_usd_per_second"] == 0.224
          and mixed_gens[0]["estimated_cost_usd"] == 1.344
          and mixed_gens[1]["uses_elements"] is False
          and mixed_gens[1]["rate_usd_per_second"] == 0.112
          and mixed_gens[1]["estimated_cost_usd"] == 0.672,
          str(mixed_plan.get("estimated_cost_usd")))
    check("CF-P1-006-R2-PREFLIGHT-kling-rate-table",
          iv.FAL_KLING_3_PRO_USD_PER_SECOND["with_elements"]
          == {"audio_off": 0.224, "audio_on": 0.336,
              "voice_control": 0.392}
          and iv.FAL_KLING_3_PRO_USD_PER_SECOND[
              "without_elements"]
          == {"audio_off": 0.112, "audio_on": 0.168,
              "voice_control": 0.196})
    check("CF-P1-006-R2-PREFLIGHT-kling-rate-helper",
          iv.kling_3_pro_rate_usd_per_second(
              generate_audio=False, with_elements=True) == 0.224
          and iv.kling_3_pro_rate_usd_per_second(
              generate_audio=True, with_elements=True) == 0.336
          and iv.kling_3_pro_rate_usd_per_second(
              generate_audio=False, with_elements=True,
              voice_control=True) == 0.392
          and iv.kling_3_pro_rate_usd_per_second(
              generate_audio=False, with_elements=False) == 0.112
          and iv.kling_3_pro_rate_usd_per_second(
              generate_audio=True, with_elements=False) == 0.168
          and iv.kling_3_pro_rate_usd_per_second(
              generate_audio=False, with_elements=False,
              voice_control=True) == 0.196)

    # ---- GCS output policy -------------------------------------
    policy = fal_policy()
    parsed = policy.validate_url(GCS_URL, "output")
    check("CF-P1-006-R2-PREFLIGHT-gcs-official-url-accepted",
          parsed["host"] == "storage.googleapis.com"
          and parsed["path"].startswith("/falserverless/"))
    check("CF-P1-006-R2-PREFLIGHT-gcs-signed-url-accepted",
          policy.validate_url(GCS_SIGNED_URL, "output")["host"]
          == "storage.googleapis.com")
    expect_error(
        "CF-P1-006-R2-PREFLIGHT-gcs-other-bucket-rejected",
        lambda: policy.validate_url(
            "https://storage.googleapis.com/other-bucket/"
            "clip.mp4", "output"))
    expect_error(
        "CF-P1-006-R2-PREFLIGHT-gcs-prefix-trick-rejected",
        lambda: policy.validate_url(
            "https://storage.googleapis.com/falserverless2/"
            "clip.mp4", "output"))
    expect_error(
        "CF-P1-006-R2-PREFLIGHT-gcs-no-path-rejected",
        lambda: policy.validate_url(
            "https://storage.googleapis.com/clip.mp4", "output"))
    check("CF-P1-006-R2-PREFLIGHT-fal-cdn-v3-accepted",
          policy.validate_url(
              "https://v3b.fal.media/files/mock/clip.mp4",
              "output")["host"] == "v3b.fal.media")
    check("CF-P1-006-R2-PREFLIGHT-fal-cdn-legacy-accepted",
          policy.validate_url(
              "https://fal.media/files/mock/clip.mp4",
              "output")["host"] == "fal.media")
    expect_error(
        "CF-P1-006-R2-PREFLIGHT-unapproved-origin-rejected",
        lambda: policy.validate_url(
            "https://evil.example.com/clip.mp4", "output"))
    expect_error(
        "CF-P1-006-R2-PREFLIGHT-gcs-lookalike-host-rejected",
        lambda: policy.validate_url(
            "https://storage.googleapis.com.evil.example.com/"
            "falserverless/clip.mp4", "output"))
    expect_error(
        "CF-P1-006-R2-PREFLIGHT-http-downgrade-rejected",
        lambda: policy.validate_url(
            "http://storage.googleapis.com/falserverless/"
            "clip.mp4", "output"))
    expect_error(
        "CF-P1-006-R2-PREFLIGHT-ip-literal-rejected",
        lambda: policy.validate_url(
            "https://127.0.0.1/falserverless/clip.mp4", "output"))
    expect_error(
        "CF-P1-006-R2-PREFLIGHT-metadata-rejected",
        lambda: policy.validate_url(
            "https://169.254.169.254/latest/meta-data", "output"))
    recorded = record_result_url(GCS_SIGNED_URL)
    check("CF-P1-006-R2-PREFLIGHT-result-url-redacted",
          recorded["url"] == GCS_URL
          and "Signature" not in recorded["url"]
          and "?" not in recorded["url"]
          and recorded["host"] == "storage.googleapis.com")

    # ---- real fal adapter over mock transports (GCS download) --
    clip_path = os.path.join(tmpdir, "clip.mp4")
    make_mp4(clip_path)
    with open(clip_path, "rb") as handle:
        clip_bytes = handle.read()
    clip_sha = hashlib.sha256(clip_bytes).hexdigest()
    fal_workspace = os.path.join(tmpdir, "fal-workspace")
    os.makedirs(fal_workspace)
    fal_spec = dict(PROVIDER_SPECS["provider-fal-video"])
    fal_spec["provider_id"] = "provider-fal-video"
    prompt = iv.build_i2v_motion_prompt(motion_prompt())
    packet = {"model": iv.MODEL_ID,
              "canonical_instruction": prompt,
              "task_id": "task-i2v-001",
              "task_type": "video-generation"}
    fal_context = {"execution_id": "exec-i2v-001",
                   "start_image_url": "data:image/png;base64,AAAA",
                   "duration": "6", "generate_audio": False}
    old_fal = set_env("FAL_KEY", "test-fal-key")
    try:
        download_headers = []

        def gcs_transport(method, url, *, headers=None, body=None):
            if method == "POST" and "queue.fal.run" in url:
                return (200, {"content-type": "application/json"},
                        json.dumps({
                            "request_id": "fal-req-gcs",
                            "status_url": "https://queue.fal.run/x/"
                            "requests/fal-req-gcs/status",
                            "response_url": "https://queue.fal.run/x/"
                            "requests/fal-req-gcs",
                            "cancel_url": "https://queue.fal.run/x/"
                            "requests/fal-req-gcs/cancel"}).encode())
            if url.endswith("/status"):
                return (200, {"content-type": "application/json"},
                        json.dumps({"status": "COMPLETED",
                                    "response_url":
                                        "https://queue.fal.run/x/"
                                        "requests/fal-req-gcs"}
                                   ).encode())
            if url.endswith("/requests/fal-req-gcs"):
                return (200, {"content-type": "application/json"},
                        json.dumps({"video": {
                            "url": GCS_SIGNED_URL,
                            "content_type": "video/mp4",
                            "file_size": len(clip_bytes),
                            "file_name": "out.mp4"}}).encode())
            if url.startswith("https://storage.googleapis.com/"):
                download_headers.append(dict(headers or {}))
                return (200, {"content-type": "video/mp4"},
                        clip_bytes)
            return (404, {}, b"not found")

        adapter = HttpProviderAdapter(
            fal_spec, workspace_root=fal_workspace,
            transport=gcs_transport)
        fal_request = adapter.prepare(packet, fal_context)
        check("CF-P1-006-R2-PREFLIGHT-gcs-request-audio-false",
              fal_request["contract_request"]["body"][
                  "generate_audio"] is False)
        submitted = adapter.submit(fal_request, fal_context)
        poll_context = {**fal_context,
                        "status_url": submitted.get("status_url"),
                        "response_url":
                            submitted.get("response_url"),
                        "cancel_url": submitted.get("cancel_url")}
        retrieved = adapter.poll("fal-req-gcs", poll_context)
        check("CF-P1-006-R2-PREFLIGHT-gcs-download-completes",
              retrieved.get("completed") is True
              and retrieved.get("output") is not None)
        artifact = retrieved["output"]
        with open(os.path.join(fal_workspace, artifact["path"]),
                  "rb") as handle:
            saved = handle.read()
        check("CF-P1-006-R2-PREFLIGHT-gcs-download-integrity",
              saved == clip_bytes
              and artifact["sha256"] == clip_sha)
        check("CF-P1-006-R2-PREFLIGHT-no-auth-on-download",
              len(download_headers) == 1
              and "authorization" not in
              {k.lower() for k in download_headers[0]},
              str(download_headers))
        check("CF-P1-006-R2-PREFLIGHT-result-url-recorded",
              adapter.last_result_url_record is not None
              and adapter.last_result_url_record["url"] == GCS_URL
              and "Signature" not in
              adapter.last_result_url_record["url"])

        # Redirect to a permitted same-policy GCS destination.
        redirect_calls = []

        def redirect_ok_transport(method, url, *, headers=None,
                                  body=None):
            redirect_calls.append((method, url))
            if method == "POST" and "queue.fal.run" in url:
                return (200, {"content-type": "application/json"},
                        json.dumps({
                            "request_id": "fal-req-redir",
                            "status_url": "https://queue.fal.run/x/"
                            "requests/fal-req-redir/status",
                            "response_url": "https://queue.fal.run/x/"
                            "requests/fal-req-redir",
                            "cancel_url": "https://queue.fal.run/x/"
                            "requests/fal-req-redir/cancel"}
                        ).encode())
            if url.endswith("/status"):
                return (200, {"content-type": "application/json"},
                        json.dumps({"status": "COMPLETED",
                                    "response_url":
                                        "https://queue.fal.run/x/"
                                        "requests/fal-req-redir"}
                                   ).encode())
            if url.endswith("/requests/fal-req-redir"):
                return (200, {"content-type": "application/json"},
                        json.dumps({"video": {
                            "url": "https://fal.media/files/mock/"
                            "clip.mp4",
                            "content_type": "video/mp4"}}).encode())
            if url.startswith("https://fal.media/"):
                return (302, {"location": GCS_URL}, b"")
            if url.startswith("https://storage.googleapis.com/"):
                return (200, {"content-type": "video/mp4"},
                        clip_bytes)
            return (404, {}, b"not found")

        redir_adapter = HttpProviderAdapter(
            fal_spec, workspace_root=fal_workspace,
            transport=redirect_ok_transport)
        redir_request = redir_adapter.prepare(packet, fal_context)
        redir_submitted = redir_adapter.submit(
            redir_request, fal_context)
        redir_result = redir_adapter.poll(
            "fal-req-redir",
            {**fal_context,
             "status_url": redir_submitted.get("status_url"),
             "response_url": redir_submitted.get("response_url")})
        check("CF-P1-006-R2-PREFLIGHT-redirect-permitted-validated",
              redir_result.get("completed") is True
              and redir_result.get("output") is not None
              and any("storage.googleapis.com" in url
                      for _, url in redirect_calls))

        # Redirect to a prohibited host is refused before fetch.
        evil_calls = []

        def redirect_evil_transport(method, url, *, headers=None,
                                    body=None):
            evil_calls.append((method, url))
            if method == "POST" and "queue.fal.run" in url:
                return (200, {"content-type": "application/json"},
                        json.dumps({
                            "request_id": "fal-req-evil",
                            "status_url": "https://queue.fal.run/x/"
                            "requests/fal-req-evil/status",
                            "response_url": "https://queue.fal.run/x/"
                            "requests/fal-req-evil",
                            "cancel_url": "https://queue.fal.run/x/"
                            "requests/fal-req-evil/cancel"}
                        ).encode())
            if url.endswith("/status"):
                return (200, {"content-type": "application/json"},
                        json.dumps({"status": "COMPLETED",
                                    "response_url":
                                        "https://queue.fal.run/x/"
                                        "requests/fal-req-evil"}
                                   ).encode())
            if url.endswith("/requests/fal-req-evil"):
                return (200, {"content-type": "application/json"},
                        json.dumps({"video": {
                            "url": "https://fal.media/files/mock/"
                            "clip.mp4",
                            "content_type": "video/mp4"}}).encode())
            if url.startswith("https://fal.media/"):
                return (302, {"location":
                              "https://evil.example.com/x.mp4"},
                        b"")
            return (404, {}, b"not found")

        evil_adapter = HttpProviderAdapter(
            fal_spec, workspace_root=fal_workspace,
            transport=redirect_evil_transport)
        evil_request = evil_adapter.prepare(packet, fal_context)
        evil_submitted = evil_adapter.submit(
            evil_request, fal_context)
        expect_error(
            "CF-P1-006-R2-PREFLIGHT-redirect-prohibited-refused",
            lambda: evil_adapter.poll(
                "fal-req-evil",
                {**fal_context,
                 "status_url": evil_submitted.get("status_url"),
                 "response_url":
                     evil_submitted.get("response_url")}))
        check("CF-P1-006-R2-PREFLIGHT-redirect-evil-never-fetched",
              not any("evil.example.com" in url
                      for _, url in evil_calls))

        # An unapproved GCS path in the result is refused.
        def bad_gcs_transport(method, url, *, headers=None,
                              body=None):
            if method == "POST" and "queue.fal.run" in url:
                return (200, {"content-type": "application/json"},
                        json.dumps({
                            "request_id": "fal-req-badgcs",
                            "status_url": "https://queue.fal.run/x/"
                            "requests/fal-req-badgcs/status",
                            "response_url": "https://queue.fal.run/x/"
                            "requests/fal-req-badgcs",
                            "cancel_url": "https://queue.fal.run/x/"
                            "requests/fal-req-badgcs/cancel"}
                        ).encode())
            if url.endswith("/status"):
                return (200, {"content-type": "application/json"},
                        json.dumps({"status": "COMPLETED",
                                    "response_url":
                                        "https://queue.fal.run/x/"
                                        "requests/fal-req-badgcs"}
                                   ).encode())
            if url.endswith("/requests/fal-req-badgcs"):
                return (200, {"content-type": "application/json"},
                        json.dumps({"video": {
                            "url": "https://storage.googleapis.com/"
                            "other-bucket/clip.mp4",
                            "content_type": "video/mp4"}}).encode())
            return (404, {}, b"not found")

        bad_gcs_adapter = HttpProviderAdapter(
            fal_spec, workspace_root=fal_workspace,
            transport=bad_gcs_transport)
        bad_gcs_request = bad_gcs_adapter.prepare(
            packet, fal_context)
        bad_gcs_submitted = bad_gcs_adapter.submit(
            bad_gcs_request, fal_context)
        expect_error(
            "CF-P1-006-R2-PREFLIGHT-result-unapproved-gcs-refused",
            lambda: bad_gcs_adapter.poll(
                "fal-req-badgcs",
                {**fal_context,
                 "status_url": bad_gcs_submitted.get("status_url"),
                 "response_url":
                     bad_gcs_submitted.get("response_url")}))

        # An HTML error page in place of MP4 media is refused.
        def html_transport(method, url, *, headers=None, body=None):
            if url.startswith("https://storage.googleapis.com/"):
                return (200, {"content-type": "text/html"},
                        b"<html><body>error</body></html>")
            return (404, {}, b"not found")

        html_adapter = HttpProviderAdapter(
            fal_spec, workspace_root=fal_workspace,
            transport=html_transport)
        expect_error(
            "CF-P1-006-R2-PREFLIGHT-html-error-page-refused",
            lambda: html_adapter.retrieve(
                "fal-req-html", GCS_URL,
                {"execution_id": "exec-html"}))
        check("CF-P1-006-R2-PREFLIGHT-html-no-partial-file",
              not os.path.exists(os.path.join(
                  fal_workspace, "outputs", "exec-html")))

        def fake_mp4_transport(method, url, *, headers=None,
                               body=None):
            if url.startswith("https://storage.googleapis.com/"):
                return (200, {"content-type": "video/mp4"},
                        b"<html><body>not a video</body></html>")
            return (404, {}, b"not found")

        fake_adapter = HttpProviderAdapter(
            fal_spec, workspace_root=fal_workspace,
            transport=fake_mp4_transport)
        expect_error(
            "CF-P1-006-R2-PREFLIGHT-fake-mp4-magic-refused",
            lambda: fake_adapter.retrieve(
                "fal-req-fake", GCS_URL,
                {"execution_id": "exec-fake"}))
        check("CF-P1-006-R2-PREFLIGHT-fake-mp4-no-partial-file",
              not os.path.exists(os.path.join(
                  fal_workspace, "outputs", "exec-fake")))
    finally:
        restore_env("FAL_KEY", old_fal)

    # ---- retention headers ---------------------------------------
    headers = fal_retention_headers()
    check("CF-P1-006-R2-PREFLIGHT-store-io-zero",
          headers.get("X-Fal-Store-IO") == "0")
    lifecycle = json.loads(
        headers.get("X-Fal-Object-Lifecycle-Preference", "{}"))
    check("CF-P1-006-R2-PREFLIGHT-lifecycle-header",
          lifecycle.get("expiration_duration_seconds") == 604800
          and lifecycle.get("initial_acl") == {"default": "forbid"})
    custom = fal_retention_headers({
        "lifecycle_expiration_seconds": 3600,
        "lifecycle_initial_acl": {
            "default": "hide",
            "rules": [{"user": "alice", "decision": "allow"}]}})
    custom_lifecycle = json.loads(
        custom["X-Fal-Object-Lifecycle-Preference"])
    check("CF-P1-006-R2-PREFLIGHT-lifecycle-override",
          custom_lifecycle["expiration_duration_seconds"] == 3600
          and custom_lifecycle["initial_acl"]["default"] == "hide"
          and custom_lifecycle["initial_acl"]["rules"] == [
              {"user": "alice", "decision": "allow"}])
    expect_error(
        "CF-P1-006-R2-PREFLIGHT-lifecycle-bad-acl",
        lambda: fal_retention_headers(
            {"lifecycle_initial_acl": {"default": "public"}}))
    built_headers = iv.build_i2v_request(
        iv.PROVIDER_ID, iv.MODEL_ID, prompt="test",
        start_image_url="data:image/png;base64,AAAA",
        generate_audio=False)["headers"]
    check("CF-P1-006-R2-PREFLIGHT-request-carries-retention",
          built_headers.get("X-Fal-Store-IO") == "0"
          and "X-Fal-Object-Lifecycle-Preference" in built_headers)
    table = fal_retention_truth_table()
    check("CF-P1-006-R2-PREFLIGHT-truth-table-shape",
          len(table) == 5
          and all(set(row.keys()) == {"item", "status", "scope"}
                  for row in table))
    zdr_row = [row for row in table if row["item"].startswith("ZDR")]
    lifecycle_row = [row for row in table
                     if row["item"].startswith(
                         "X-Fal-Object-Lifecycle")]
    store_io_row = [row for row in table
                    if row["item"].startswith("X-Fal-Store-IO")]
    gcs_row = [row for row in table
               if row["item"].startswith("GCS output")]
    check("CF-P1-006-R2-PREFLIGHT-zdr-unconfirmed",
          len(zdr_row) == 1
          and "UNCONFIRMED" in zdr_row[0]["status"]
          and FAL_ZDR_STATUS == "UNCONFIRMED")
    check("CF-P1-006-R2-PREFLIGHT-acl-scope-fal-cdn-only",
          len(lifecycle_row) == 1
          and "fal CDN v3" in lifecycle_row[0]["scope"]
          and "does NOT protect" in lifecycle_row[0]["scope"])
    check("CF-P1-006-R2-PREFLIGHT-store-io-not-zdr",
          len(store_io_row) == 1
          and "does NOT equal ZDR" in store_io_row[0]["scope"])
    check("CF-P1-006-R2-PREFLIGHT-gcs-public-by-link",
          len(gcs_row) == 1
          and "public-by-link" in gcs_row[0]["status"])
    check("CF-P1-006-R2-PREFLIGHT-truth-table-runtime",
          iv.retention_truth_table() == table)

    # ---- paid submission blocked without authorization -----------
    blocked_plan = iv.build_execution_plan(
        ready_project, [ready_shot], authorization=None,
        generate_audio=False, identity_bindings={"s1": [good]})
    check("CF-P1-006-R2-PREFLIGHT-plan-blocked-no-auth",
          blocked_plan["status"] == "BLOCKED")
    blocked_adapter = MockAdapter()
    expect_error(
        "CF-P1-006-R2-PREFLIGHT-execute-blocked-refused",
        lambda: iv.execute_i2v_plan(
            blocked_plan, adapter=blocked_adapter,
            delivery_root=delivery_root,
            ledger=iv.SubmissionLedger(),
            output_dir=tmpdir, work_dir=tmpdir))
    check("CF-P1-006-R2-PREFLIGHT-execute-blocked-no-submit",
          blocked_adapter.submit_calls == 0)

    # ---- mock execution with elements end to end -----------------
    output_dir = os.path.join(tmpdir, "outputs")
    os.makedirs(output_dir)
    mock_clip = os.path.join(output_dir, "mock-s1.mp4")
    make_mp4(mock_clip)
    mock_exec = MockAdapter(clip_path=mock_clip)
    executed = iv.execute_i2v_plan(
        ready_plan, adapter=mock_exec, delivery_root=delivery_root,
        ledger=iv.SubmissionLedger(), output_dir=output_dir,
        work_dir=os.path.join(tmpdir, "exec-work"),
        poll_interval_s=0)
    check("CF-P1-006-R2-PREFLIGHT-mock-execute-with-elements",
          executed["status"] == "completed"
          and len(executed["generations"]) == 1
          and executed["generations"][0]["provider_job_id"]
          == "mock-job-001"
          and executed["generations"][0]["motion_classification"]
          in ("subject-motion", "mixed"))

    # ---- character drift review record ---------------------------
    empty_review = iv.record_character_drift_review(
        "s1", "clip-s1.mp4", reviewer="human-1", frame_checks=[])
    check("CF-P1-006-R2-PREFLIGHT-drift-no-frames-no-verdict",
          empty_review["overall_verdict"] is None
          and empty_review["status"] == "incomplete")
    pass_review = iv.record_character_drift_review(
        "s1", "clip-s1.mp4", reviewer="human-1", frame_checks=[
            {"frame_time_seconds": 1.0, "attribute": "face",
             "verdict": "pass"},
            {"frame_time_seconds": 3.0, "attribute": "hair",
             "verdict": "pass"}])
    check("CF-P1-006-R2-PREFLIGHT-drift-all-pass-consistent",
          pass_review["overall_verdict"] == "consistent"
          and pass_review["status"] == "recorded")
    fail_review = iv.record_character_drift_review(
        "s1", "clip-s1.mp4", reviewer="human-1", frame_checks=[
            {"frame_time_seconds": 1.0, "attribute": "face",
             "verdict": "pass"},
            {"frame_time_seconds": 3.0, "attribute": "hair",
             "verdict": "fail", "notes": "hair colour drifted"}])
    check("CF-P1-006-R2-PREFLIGHT-drift-one-fail-found",
          fail_review["overall_verdict"] == "drift-found"
          and fail_review["status"] == "recorded")
    unchecked_review = iv.record_character_drift_review(
        "s1", "clip-s1.mp4", reviewer="human-1", frame_checks=[
            {"frame_time_seconds": 1.0, "attribute": "face",
             "verdict": "pass"},
            {"frame_time_seconds": 3.0, "attribute": "hair",
             "verdict": "not-checked"}])
    check("CF-P1-006-R2-PREFLIGHT-drift-unchecked-incomplete",
          unchecked_review["overall_verdict"] is None
          and unchecked_review["status"] == "incomplete")
    expect_error(
        "CF-P1-006-R2-PREFLIGHT-drift-bad-verdict",
        lambda: iv.record_character_drift_review(
            "s1", "clip-s1.mp4", reviewer="human-1",
            frame_checks=[{"frame_time_seconds": 1.0,
                           "attribute": "face",
                           "verdict": "perfect"}]))

    # ---- no provider call during preflight -----------------------
    network_calls = []

    def counting_transport(method, url, *, headers=None, body=None):
        network_calls.append((method, url))
        raise AssertionError("preflight made a network call")

    counting_adapter = HttpProviderAdapter(
        fal_spec, workspace_root=fal_workspace,
        transport=counting_transport)
    old_fal2 = set_env("FAL_KEY", "test-fal-key")
    try:
        preflight_errors = counting_adapter.preflight(
            packet, fal_context)
        prepared = counting_adapter.prepare(packet, fal_context)
        _plan = iv.build_execution_plan(
            ready_project, [ready_shot], authorization=None,
            generate_audio=False, identity_bindings={"s1": [good]})
        _request = iv.build_i2v_request(
            iv.PROVIDER_ID, iv.MODEL_ID, prompt=prompt,
            start_image_url="data:image/png;base64,AAAA",
            generate_audio=False, elements=[element])
        check("CF-P1-006-R2-PREFLIGHT-zero-network-calls",
              network_calls == []
              and preflight_errors == []
              and prepared["contract_request"]["body"][
                  "generate_audio"] is False,
              f"calls={network_calls} errors={preflight_errors}")
    finally:
        restore_env("FAL_KEY", old_fal2)

    # ---- new schemas validate ------------------------------------
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "validate_repo",
        os.path.join(ROOT_ABS, "scripts", "validate-repo.py"))
    validate_repo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validate_repo)
    schema_errors = []
    for name in ("character-identity.json",
                 "image-to-video-job.json"):
        with open(os.path.join(ROOT_ABS, "schemas", name),
                  encoding="utf-8") as handle:
            schema = json.load(handle)
        validate_repo.check_schema(
            schema, f"schemas/{name}", schema_errors)
        check(f"CF-P1-006-R2-PREFLIGHT-schema-{name}-wellformed",
              schema_errors == [], str(schema_errors))
        schema_errors = []
    identity_fixture = {
        "schema_version": "2.5",
        "character_id": "demo-char-002",
        "approval_status": "approved",
        "frontal_reference": {
            "asset_id": "ref-nadia-front",
            "path": "refs/front.png",
            "status": "approved",
            "transmission_permitted": True},
        "additional_references": [{
            "asset_id": "ref-nadia-angle-1",
            "path": "refs/angle-1.png",
            "status": "approved",
            "transmission_permitted": True}]}
    job_fixture = {
        "schema_version": "2.5",
        "job_id": "i2v-s1",
        "project_id": PROJECT_ID,
        "shot_id": "s1",
        "provider_id": iv.PROVIDER_ID,
        "model": iv.MODEL_ID,
        "generate_audio": False,
        "multi_prompt_status": "unused-design-restriction",
        "retention": {"store_io": "0",
                      "zdr_status": "UNCONFIRMED",
                      "lifecycle_preference": {
                          "expiration_duration_seconds": 604800,
                          "initial_acl": {"default": "forbid"}}},
        "output": {"origin": "storage.googleapis.com",
                   "content_type": "video/mp4"}}
    identity_schema = json.load(open(os.path.join(
        ROOT_ABS, "schemas", "character-identity.json"),
        encoding="utf-8"))
    job_schema = json.load(open(os.path.join(
        ROOT_ABS, "schemas", "image-to-video-job.json"),
        encoding="utf-8"))
    identity_errs = []
    validate_repo.validate_instance(
        identity_schema, identity_fixture, "$", identity_errs)
    check("CF-P1-006-R2-PREFLIGHT-schema-identity-fixture-valid",
          identity_errs == [], str(identity_errs))
    job_errs = []
    validate_repo.validate_instance(
        job_schema, job_fixture, "$", job_errs)
    check("CF-P1-006-R2-PREFLIGHT-schema-job-fixture-valid",
          job_errs == [], str(job_errs))
    bad_job = dict(job_fixture)
    bad_job["retention"] = {"store_io": "0",
                            "zdr_status": "confirmed"}
    bad_job_errs = []
    validate_repo.validate_instance(
        job_schema, bad_job, "$", bad_job_errs)
    check("CF-P1-006-R2-PREFLIGHT-schema-zdr-cannot-be-claimed",
          bad_job_errs != [])

    print(f"\n{_checks[0]} checks, {len(failures)} failures")
    if failures:
        print("FAILURES: " + ", ".join(failures))
        return 1
    return 0


def main():
    return run_checks()


if __name__ == "__main__":
    sys.exit(main())
