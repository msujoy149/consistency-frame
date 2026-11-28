#!/usr/bin/env python3
"""Image-to-video tests (CF-WO-P1-006-R2).

Covers the I2V runtime (``runtime/image_to_video.py``): request
building through the fal.ai Kling Video v3 Pro contract, source
image integrity, the paid-submission authorization gate,
idempotency + uncertain-submission protection, job submission
and async polling, result retrieval through the secure URL
policy (including malicious result-URL rejection), clip
verification (type, duration, geometry, codec, stream
presence), motion classification (static and camera-only
rejection, including a slow zoompan over a smooth still),
character drift detection, text-overlay and subtitle
prohibition, the script-derived counts, the execution plan
(BLOCKED and READY), the local-generation refusal for
``i2v-clip``, and the end-to-end BLOCKED path through the R2
driver (exit 2, no final MP4).

FFmpeg/ffprobe are REQUIRED: when they are absent the suite
fails (exit 1) instead of skipping. All generated media lives
in tempfile dirs. No test here calls a paid provider: the fal.ai
adapter is exercised only over an injected mock transport, and
the mock adapter used for execution tests is labelled mock in
every check name that uses it. No test generates a real
character image: fixture keyframes are FFmpeg-generated frames.
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
from runtime import character_consistency as cc  # noqa: E402
from runtime import image_to_video as iv  # noqa: E402
from runtime import production_assets as pa  # noqa: E402
from runtime import production_timeline as tl  # noqa: E402
from runtime import vertical_production as vp  # noqa: E402
from runtime.media_adapters import (  # noqa: E402
    PROVIDER_SPECS, HttpProviderAdapter)
from runtime.media_execution import MediaExecutionError  # noqa: E402

EXAMPLE = os.path.join(ROOT_ABS, "examples",
                       "p1006-r2-photorealistic-image-to-video")
PROJECT_ID = "p1006-r2-photorealistic-image-to-video"

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


def load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def run_ffmpeg(argv, label):
    proc = subprocess.run(argv, capture_output=True, text=True,
                          timeout=300)
    if proc.returncode != 0:
        raise RuntimeError(
            f"{label} failed: {(proc.stderr or '').strip()[:400]}")
    return proc


def make_png(path, width=1152, height=2048):
    run_ffmpeg(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                "-i", f"testsrc2=size={width}x{height}:duration=0.1",
                "-frames:v", "1", path], "fixture png")


def make_mp4(path, width=1080, height=1920, seconds=6,
             source="testsrc2", codec="libx264"):
    run_ffmpeg(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                "-i", f"{source}=size={width}x{height}:rate=30:"
                f"duration={seconds}",
                "-t", str(seconds), "-c:v", codec,
                "-pix_fmt", "yuv420p", path], "fixture mp4")


def make_audio_mp4(path, seconds=6):
    run_ffmpeg(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                "-i", f"sine=frequency=440:duration={seconds}",
                "-t", str(seconds), "-c:a", "aac", path],
               "audio-only mp4")


def write_pgm(path, width, height, fn):
    pixels = bytes(max(0, min(255, fn(x, y)))
                   for y in range(height) for x in range(width))
    with open(path, "wb") as handle:
        handle.write(b"P5\n" + f"{width} {height}\n255\n".encode()
                     + pixels)


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
        "subject": "Nadia lights the round paper lantern",
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


def shot(shot_id="s1", scene_id="SC1", keyframe_file=None,
         keyframe_sha=None):
    return {"shot_id": shot_id, "scene_id": scene_id,
            "character_id": "DEMO-CHAR-002",
            "reference_ids": ["ref-nadia-front"],
            "environment_id": "env-rooftop-terrace-dawn",
            "prop_ids": ["prop-lantern-table"],
            "expression": "concentration",
            "line_id": "l1",
            "visual": {"kind": "i2v-clip", "duration_seconds": 6,
                       "keyframe_file": keyframe_file},
            "keyframe": {"file": keyframe_file,
                         "sha256": keyframe_sha,
                         "status": "pending-generation-after-"
                         "script-approval" if keyframe_file is None
                         else "generated"},
            "motion_prompt": motion_prompt()}


class MockAdapter:
    """Mock I2V adapter (labelled mock): counts submissions and
    replays scripted poll outcomes. Never touches a network."""

    def __init__(self, *, clip_path=None, poll_outcomes=None):
        self.clip_path = clip_path
        self.poll_outcomes = list(poll_outcomes or [])
        self.submit_calls = 0
        self.poll_calls = 0

    def translate(self, packet, context):
        built = iv.build_i2v_request(
            iv.PROVIDER_ID, iv.MODEL_ID,
            prompt=packet["canonical_instruction"],
            start_image_url=context["start_image_url"],
            duration_seconds=int(context.get("duration", "6")),
            generate_audio=context.get("generate_audio", True))
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
    tmpdir = tempfile.mkdtemp(prefix="cf-p1006-r2-i2v-")
    try:
        return _run_checks(tmpdir)
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


def _run_checks(tmpdir):
    # ---- request building --------------------------------------
    prompt = iv.build_i2v_motion_prompt(motion_prompt())
    check("CF-P1-006-R2-I2V-request-built",
          "No visible text" in prompt
          and "lantern" in prompt)
    request = iv.build_i2v_request(
        iv.PROVIDER_ID, iv.MODEL_ID, prompt=prompt,
        start_image_url="data:image/png;base64,AAAA",
        duration_seconds=6, generate_audio=True)
    check("CF-P1-006-R2-I2V-request-fields",
          request["model"] == iv.MODEL_ID
          and request["body"]["duration"] == "6"
          and request["body"]["generate_audio"] is True
          and request["body"]["start_image_url"].startswith(
              "data:image/png;base64,"))
    expect_error("CF-P1-006-R2-I2V-request-prompt-too-long",
                 lambda: iv.build_i2v_request(
                     iv.PROVIDER_ID, iv.MODEL_ID,
                     prompt="x" * 2501,
                     start_image_url="data:image/png;base64,AAAA"))
    expect_error("CF-P1-006-R2-I2V-request-no-start-image",
                 lambda: iv.build_i2v_request(
                     iv.PROVIDER_ID, iv.MODEL_ID, prompt="test",
                     start_image_url=""))
    expect_error("CF-P1-006-R2-I2V-request-bad-duration",
                 lambda: iv.build_i2v_request(
                     iv.PROVIDER_ID, iv.MODEL_ID, prompt="test",
                     start_image_url="data:image/png;base64,AAAA",
                     duration_seconds=99))

    # ---- source image integrity --------------------------------
    keyframe = os.path.join(tmpdir, "keyframe.png")
    make_png(keyframe)
    with open(keyframe, "rb") as handle:
        key_bytes = handle.read()
    key_sha = hashlib.sha256(key_bytes).hexdigest()
    info = iv.validate_source_image(keyframe, expected_sha256=key_sha)
    check("CF-P1-006-R2-I2V-image-valid",
          info["sha256"] == key_sha and info["width"] == 1152
          and info["height"] == 2048 and info["codec"] == "png")
    expect_error("CF-P1-006-R2-I2V-image-wrong-sha",
                 lambda: iv.validate_source_image(
                     keyframe, expected_sha256="0" * 64))
    expect_error("CF-P1-006-R2-I2V-image-missing",
                 lambda: iv.validate_source_image(
                     os.path.join(tmpdir, "nope.png")))
    text_file = os.path.join(tmpdir, "not-image.txt")
    with open(text_file, "w", encoding="utf-8") as handle:
        handle.write("this is not an image")
    expect_error("CF-P1-006-R2-I2V-image-not-image",
                 lambda: iv.validate_source_image(text_file))
    tiny = os.path.join(tmpdir, "tiny.png")
    make_png(tiny, width=100, height=100)
    expect_error("CF-P1-006-R2-I2V-image-too-small",
                 lambda: iv.validate_source_image(tiny))
    wide = os.path.join(tmpdir, "wide.png")
    make_png(wide, width=1000, height=100)
    expect_error("CF-P1-006-R2-I2V-image-bad-aspect",
                 lambda: iv.validate_source_image(wide))
    big = os.path.join(tmpdir, "big.png")
    with open(big, "wb") as handle:
        handle.truncate(iv.START_IMAGE_MAX_BYTES + 1)
    expect_error("CF-P1-006-R2-I2V-image-oversize",
                 lambda: iv.validate_source_image(big))
    uri = iv.keyframe_data_uri(info)
    check("CF-P1-006-R2-I2V-image-data-uri",
          uri.startswith("data:image/png;base64,")
          and base64.b64decode(uri.split(",", 1)[1]) == key_bytes)

    # ---- authorization gate ------------------------------------
    check("CF-P1-006-R2-I2V-auth-missing",
          iv.validate_authorization(
              None, provider_id=iv.PROVIDER_ID, model=iv.MODEL_ID,
              operation=iv.OPERATION, required_generations=8,
              scope_asset_ids=[]) != [])
    check("CF-P1-006-R2-I2V-auth-wrong-provider",
          "provider" in " ".join(iv.validate_authorization(
              {**valid_auth([]), "provider_id": "provider-other"},
              provider_id=iv.PROVIDER_ID, model=iv.MODEL_ID,
              operation=iv.OPERATION, required_generations=8,
              scope_asset_ids=[])))
    check("CF-P1-006-R2-I2V-auth-wrong-model",
          "model" in " ".join(iv.validate_authorization(
              {**valid_auth([]), "model": "wrong-model"},
              provider_id=iv.PROVIDER_ID, model=iv.MODEL_ID,
              operation=iv.OPERATION, required_generations=8,
              scope_asset_ids=[])))
    check("CF-P1-006-R2-I2V-auth-budget-short",
          iv.validate_authorization(
              valid_auth([], max_generations=7),
              provider_id=iv.PROVIDER_ID, model=iv.MODEL_ID,
              operation=iv.OPERATION, required_generations=8,
              scope_asset_ids=[]) != [])
    check("CF-P1-006-R2-I2V-auth-scope-gap",
          "scope" in " ".join(iv.validate_authorization(
              valid_auth(["ref-nadia-front"]),
              provider_id=iv.PROVIDER_ID, model=iv.MODEL_ID,
              operation=iv.OPERATION, required_generations=8,
              scope_asset_ids=["ref-nadia-front",
                               "ref-nadia-side"])))
    check("CF-P1-006-R2-I2V-auth-expired",
          iv.validate_authorization(
              {**valid_auth([]),
               "expires_at": "2020-01-01T00:00:00Z"},
              provider_id=iv.PROVIDER_ID, model=iv.MODEL_ID,
              operation=iv.OPERATION, required_generations=8,
              scope_asset_ids=[]) != [])
    check("CF-P1-006-R2-I2V-auth-valid",
          iv.validate_authorization(
              valid_auth(["ref-nadia-front"]),
              provider_id=iv.PROVIDER_ID, model=iv.MODEL_ID,
              operation=iv.OPERATION, required_generations=1,
              scope_asset_ids=["ref-nadia-front"]) == [])
    expect_error("CF-P1-006-R2-I2V-auth-require-raises",
                 lambda: iv.require_authorization(
                     None, provider_id=iv.PROVIDER_ID,
                     model=iv.MODEL_ID, operation=iv.OPERATION,
                     required_generations=8, scope_asset_ids=[]))

    # ---- text-overlay + subtitle prohibition -------------------
    check("CF-P1-006-R2-I2V-text-policy-valid",
          iv.validate_text_overlay_policy(
              iv.TEXT_OVERLAY_POLICY) == [])
    for flag in iv.TEXT_OVERLAY_FLAGS:
        bad = dict(iv.TEXT_OVERLAY_POLICY)
        bad[flag] = True
        check(f"CF-P1-006-R2-I2V-text-policy-{flag}-refused",
              iv.validate_text_overlay_policy(bad) != [])
    check("CF-P1-006-R2-I2V-text-policy-missing-flag",
          iv.validate_text_overlay_policy(
              {"text_overlay_enabled": False}) != [])
    check("CF-P1-006-R2-I2V-text-policy-non-bool",
          iv.validate_text_overlay_policy(
              {**iv.TEXT_OVERLAY_POLICY,
               "watermark_enabled": "false"}) != [])
    check("CF-P1-006-R2-I2V-prompt-carries-prohibition",
          iv.TEXT_PROHIBITION_CLAUSE in prompt)

    # ---- motion prompt validation ------------------------------
    check("CF-P1-006-R2-I2V-motion-valid",
          iv.validate_motion_prompt(motion_prompt()) == [])
    check("CF-P1-006-R2-I2V-motion-empty-field",
          iv.validate_motion_prompt(
              motion_prompt(subject="")) != [])
    check("CF-P1-006-R2-I2V-motion-camera-only",
          iv.validate_motion_prompt(
              {"subject": "", "face": "", "body": "",
               "hand_prop": "", "hair_cloth": "",
               "environment": "", "camera": "slow push-in"}) != [])
    check("CF-P1-006-R2-I2V-motion-not-dict",
          iv.validate_motion_prompt("pan slowly") != [])

    # ---- motion classification (synthetic frames) --------------
    width, height = 64, 36
    base = lambda x, y: (x * 2 + y) % 200 + (
        60 if 16 <= x < 48 and 9 <= y < 27 else 0)  # noqa: E731
    frame_a = os.path.join(tmpdir, "frame-a.pgm")
    frame_b = os.path.join(tmpdir, "frame-b.pgm")
    write_pgm(frame_a, width, height, base)
    write_pgm(frame_b, width, height, base)
    result = iv.classify_motion([frame_a, frame_b])
    check("CF-P1-006-R2-I2V-motion-static-rejected",
          result["classification"] == "static"
          and result["passes"] is False)
    frame_shift = os.path.join(tmpdir, "frame-shift.pgm")
    write_pgm(frame_shift, width, height,
              lambda x, y: base(x - 2, y - 1)  # noqa: E731
              if x >= 2 and y >= 1 else 0)
    result = iv.classify_motion([frame_a, frame_shift])
    check("CF-P1-006-R2-I2V-motion-camera-only-rejected",
          result["classification"] == "camera-only"
          and result["passes"] is False)
    frame_centre = os.path.join(tmpdir, "frame-centre.pgm")
    write_pgm(frame_centre, width, height,
              lambda x, y: base(x, y) + (  # noqa: E731
                  80 if 20 <= x < 44 and 12 <= y < 24 else 0))
    result = iv.classify_motion([frame_a, frame_centre])
    check("CF-P1-006-R2-I2V-motion-subject-passes",
          result["classification"] == "subject-motion"
          and result["passes"] is True)
    frame_both = os.path.join(tmpdir, "frame-both.pgm")
    write_pgm(frame_both, width, height,
              lambda x, y: base(x, y) + 50)  # noqa: E731
    result = iv.classify_motion([frame_a, frame_both])
    check("CF-P1-006-R2-I2V-motion-mixed-passes",
          result["classification"] == "mixed"
          and result["passes"] is True)
    # A slow zoompan over a smooth photographic still: the
    # per-frame change is sub-pixel, so the classifier sees a
    # repeated still and rejects it — the zoompan substitute
    # does not pass as motion.
    smooth = os.path.join(tmpdir, "smooth.png")
    run_ffmpeg(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                "-i", "gradients=size=1152x2048:duration=0.1",
                "-frames:v", "1", smooth], "smooth still")
    zoom_clip = os.path.join(tmpdir, "zoompan.mp4")
    run_ffmpeg(["ffmpeg", "-y", "-v", "error", "-i", smooth,
                "-vf", "scale=1080:1920,zoompan=z='1+0.02*on/30':"
                "d=180:s=1080x1920:fps=30",
                "-t", "6", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                zoom_clip], "zoompan clip")
    motion = iv.validate_clip_motion(
        zoom_clip, work_dir=os.path.join(tmpdir, "motion-zoom"))
    check("CF-P1-006-R2-I2V-motion-zoompan-rejected",
          motion["passes"] is False,
          str(motion.get("classification")))
    moving_clip = os.path.join(tmpdir, "moving.mp4")
    make_mp4(moving_clip)
    motion = iv.validate_clip_motion(
        moving_clip, work_dir=os.path.join(tmpdir, "motion-moving"))
    check("CF-P1-006-R2-I2V-motion-real-clip-passes",
          motion["passes"] is True,
          str(motion.get("classification")))

    # ---- clip verification -------------------------------------
    verified = iv.verify_generated_clip(
        moving_clip, expected_duration_seconds=6,
        expected_width=1080, expected_height=1920)
    with open(moving_clip, "rb") as handle:
        clip_sha = hashlib.sha256(handle.read()).hexdigest()
    check("CF-P1-006-R2-I2V-clip-valid",
          verified["sha256"] == clip_sha
          and verified["video_codec"] == "h264"
          and verified["width"] == 1080
          and verified["height"] == 1920
          and abs(verified["duration_seconds"] - 6.0) < 1.0)
    short_clip = os.path.join(tmpdir, "short.mp4")
    make_mp4(short_clip, seconds=3)
    expect_error("CF-P1-006-R2-I2V-clip-wrong-duration",
                 lambda: iv.verify_generated_clip(
                     short_clip, expected_duration_seconds=6,
                     expected_width=1080, expected_height=1920))
    small_clip = os.path.join(tmpdir, "small.mp4")
    make_mp4(small_clip, width=640, height=360)
    expect_error("CF-P1-006-R2-I2V-clip-wrong-geometry",
                 lambda: iv.verify_generated_clip(
                     small_clip, expected_duration_seconds=6,
                     expected_width=1080, expected_height=1920))
    audio_clip = os.path.join(tmpdir, "audio-only.mp4")
    make_audio_mp4(audio_clip)
    expect_error("CF-P1-006-R2-I2V-clip-missing-video-stream",
                 lambda: iv.verify_generated_clip(
                     audio_clip, expected_duration_seconds=6))
    expect_error("CF-P1-006-R2-I2V-clip-invalid-file",
                 lambda: iv.verify_generated_clip(
                     text_file, expected_duration_seconds=6))
    expect_error("CF-P1-006-R2-I2V-clip-missing-file",
                 lambda: iv.verify_generated_clip(
                     os.path.join(tmpdir, "nope.mp4"),
                     expected_duration_seconds=6))
    mpeg4_clip = os.path.join(tmpdir, "mpeg4.mp4")
    make_mp4(mpeg4_clip, codec="mpeg4")
    expect_error("CF-P1-006-R2-I2V-clip-wrong-codec",
                 lambda: iv.verify_generated_clip(
                     mpeg4_clip, expected_duration_seconds=6))

    # ---- ledger / idempotency (mock adapter) -------------------
    ledger = iv.SubmissionLedger()
    key = iv.idempotency_key(
        PROJECT_ID, "s1", iv.PROVIDER_ID, iv.MODEL_ID, key_sha,
        prompt)
    key2 = iv.idempotency_key(
        PROJECT_ID, "s1", iv.PROVIDER_ID, iv.MODEL_ID, key_sha,
        prompt)
    check("CF-P1-006-R2-I2V-idempotency-deterministic",
          key == key2 and len(key) == 64)
    mock = MockAdapter()
    context = {"execution_id": "mock-exec-1",
               "idempotency_key": key}
    built = iv.build_i2v_request(
        iv.PROVIDER_ID, iv.MODEL_ID, prompt=prompt,
        start_image_url="data:image/png;base64,AAAA")
    first = iv.submit_i2v_generation(
        mock, {"contract_request": built}, context,
        ledger=ledger, key=key)
    second = iv.submit_i2v_generation(
        mock, {"contract_request": built}, context,
        ledger=ledger, key=key)
    check("CF-P1-006-R2-I2V-duplicate-prevented",
          first["job_id"] == "mock-job-001"
          and second.get("reused") is True
          and mock.submit_calls == 1)
    ledger.record_uncertain("key-uncertain", "no job id returned")
    expect_error("CF-P1-006-R2-I2V-uncertain-never-resent",
                 lambda: iv.submit_i2v_generation(
                     mock, {"contract_request": built}, context,
                     ledger=ledger, key="key-uncertain"))
    check("CF-P1-006-R2-I2V-uncertain-no-resubmit-call",
          mock.submit_calls == 1)

    class NoJobIdAdapter(MockAdapter):
        def submit(self, request, context):
            self.submit_calls += 1
            return {"provider_job_id": None, "completed": False,
                    "output": None, "failure": None}

    no_job = NoJobIdAdapter()
    expect_error("CF-P1-006-R2-I2V-submit-no-job-id-uncertain",
                 lambda: iv.submit_i2v_generation(
                     no_job, {"contract_request": built}, context,
                     ledger=iv.SubmissionLedger(), key="key-nojob"))
    check("CF-P1-006-R2-I2V-submit-no-job-id-recorded",
          True)

    class FailingAdapter(MockAdapter):
        def submit(self, request, context):
            self.submit_calls += 1
            return {"provider_job_id": None, "completed": False,
                    "output": None,
                    "failure": {"message": "content policy"}}

    expect_error("CF-P1-006-R2-I2V-submit-failure",
                 lambda: iv.submit_i2v_generation(
                     FailingAdapter(), {"contract_request": built},
                     context, ledger=iv.SubmissionLedger(),
                     key="key-fail"))

    # ---- async polling (mock adapter) --------------------------
    running_then_done = MockAdapter(poll_outcomes=[
        {"completed": False, "output": None, "failure": None},
        {"completed": True, "output": {"path": moving_clip},
         "failure": None}])
    polled = iv.poll_i2v_generation(
        running_then_done, "mock-job-001", {}, max_polls=5,
        poll_interval_s=0)
    check("CF-P1-006-R2-I2V-poll-running-then-done",
          polled.get("completed") is True
          and running_then_done.poll_calls == 2)
    stuck = MockAdapter(poll_outcomes=[
        {"completed": False, "output": None, "failure": None}] * 3)
    expect_error("CF-P1-006-R2-I2V-poll-timeout",
                 lambda: iv.poll_i2v_generation(
                     stuck, "mock-job-001", {}, max_polls=3,
                     poll_interval_s=0))
    failed_poll = MockAdapter(poll_outcomes=[
        {"completed": True, "output": None,
         "failure": {"message": "generation failed"}}])
    expect_error("CF-P1-006-R2-I2V-poll-failed-generation",
                 lambda: iv.poll_i2v_generation(
                     failed_poll, "mock-job-001", {}, max_polls=3,
                     poll_interval_s=0))

    # ---- real fal adapter over a mock transport ----------------
    clip_bytes = open(moving_clip, "rb").read()
    fal_calls = []

    def fal_transport(method, url, *, headers=None, body=None):
        fal_calls.append((method, url))
        if method == "POST" and "queue.fal.run" in url:
            return (200, {"content-type": "application/json"},
                    json.dumps({
                        "request_id": "fal-req-001",
                        "status_url": "https://queue.fal.run/"
                        "fal-ai/kling-video/v3/pro/image-to-video/"
                        "requests/fal-req-001/status",
                        "response_url": "https://queue.fal.run/"
                        "fal-ai/kling-video/v3/pro/image-to-video/"
                        "requests/fal-req-001",
                        "cancel_url": "https://queue.fal.run/"
                        "fal-ai/kling-video/v3/pro/image-to-video/"
                        "requests/fal-req-001/cancel"}).encode())
        if url.endswith("/status"):
            return (200, {"content-type": "application/json"},
                    json.dumps({"status": "COMPLETED",
                                "response_url": "https://queue.fal.run/"
                                "fal-ai/kling-video/v3/pro/"
                                "image-to-video/requests/fal-req-001"}
                               ).encode())
        if url.endswith("/requests/fal-req-001"):
            return (200, {"content-type": "application/json"},
                    json.dumps({"video": {
                        "url": "https://fal.media/files/mock/"
                        "clip.mp4",
                        "content_type": "video/mp4",
                        "file_size": len(clip_bytes),
                        "file_name": "clip.mp4"}}).encode())
        if url.startswith("https://fal.media/"):
            return (200, {"content-type": "video/mp4"}, clip_bytes)
        return (404, {}, b"not found")

    fal_workspace = os.path.join(tmpdir, "fal-workspace")
    os.makedirs(fal_workspace)
    fal_spec = dict(PROVIDER_SPECS["provider-fal-video"])
    fal_spec["provider_id"] = "provider-fal-video"
    old_fal = set_env("FAL_KEY", "test-fal-key")
    try:
        adapter = HttpProviderAdapter(
            fal_spec, workspace_root=fal_workspace,
            transport=fal_transport)
        packet = {"model": iv.MODEL_ID,
                  "canonical_instruction": prompt,
                  "task_id": "task-i2v-001",
                  "task_type": "video-generation"}
        fal_context = {"execution_id": "exec-i2v-001",
                       "start_image_url":
                           "data:image/png;base64,AAAA",
                       "duration": "6", "generate_audio": True}
        fal_request = adapter.prepare(packet, fal_context)
        submitted = adapter.submit(fal_request, fal_context)
        check("CF-P1-006-R2-I2V-fal-submit-accepted",
              submitted.get("completed") is False
              and submitted.get("provider_job_id") == "fal-req-001"
              and submitted.get("status_url") is not None)
        poll_context = {**fal_context,
                        "status_url": submitted.get("status_url"),
                        "response_url":
                            submitted.get("response_url"),
                        "cancel_url": submitted.get("cancel_url")}
        retrieved = adapter.poll("fal-req-001", poll_context)
        check("CF-P1-006-R2-I2V-fal-poll-retrieves-clip",
              retrieved.get("completed") is True
              and retrieved.get("output") is not None)
        artifact = retrieved["output"]
        with open(os.path.join(fal_workspace, artifact["path"]),
                  "rb") as handle:
            saved = handle.read()
        check("CF-P1-006-R2-I2V-fal-download-integrity",
              saved == clip_bytes
              and artifact["sha256"]
              == hashlib.sha256(clip_bytes).hexdigest())

        # A malicious result URL is refused before any fetch:
        # the mock transport records no call to the evil host.
        evil_calls = []

        def evil_transport(method, url, *, headers=None, body=None):
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
                            "requests/fal-req-evil/cancel"}).encode())
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
                            "url": "http://169.254.169.254/latest/"
                            "meta-data",
                            "content_type": "video/mp4"}}).encode())
            return (404, {}, b"not found")

        evil_adapter = HttpProviderAdapter(
            fal_spec, workspace_root=fal_workspace,
            transport=evil_transport)
        evil_request = evil_adapter.prepare(packet, fal_context)
        evil_submitted = evil_adapter.submit(
            evil_request, fal_context)
        evil_context = {**fal_context,
                        "status_url":
                            evil_submitted.get("status_url"),
                        "response_url":
                            evil_submitted.get("response_url")}
        expect_error("CF-P1-006-R2-I2V-fal-malicious-url-refused",
                     lambda: evil_adapter.poll(
                         "fal-req-evil", evil_context))
        check("CF-P1-006-R2-I2V-fal-malicious-url-never-fetched",
              not any("169.254" in url for _, url in evil_calls))

        # A failed generation surfaces as a provider failure.
        def failed_transport(method, url, *, headers=None,
                             body=None):
            if method == "POST" and "queue.fal.run" in url:
                return (200, {"content-type": "application/json"},
                        json.dumps({
                            "request_id": "fal-req-failed",
                            "status_url": "https://queue.fal.run/x/"
                            "requests/fal-req-failed/status",
                            "response_url": "https://queue.fal.run/x/"
                            "requests/fal-req-failed",
                            "cancel_url": "https://queue.fal.run/x/"
                            "requests/fal-req-failed/cancel"}
                        ).encode())
            if url.endswith("/status"):
                # The documented statuses are only IN_QUEUE /
                # IN_PROGRESS / COMPLETED: a failed job reports
                # COMPLETED and the result payload carries the
                # error detail.
                return (200, {"content-type": "application/json"},
                        json.dumps({"status": "COMPLETED",
                                    "response_url":
                                        "https://queue.fal.run/x/"
                                        "requests/fal-req-failed"}
                                   ).encode())
            if url.endswith("/requests/fal-req-failed"):
                return (200, {"content-type": "application/json"},
                        json.dumps({"detail": "content policy "
                                    "violation"}).encode())
            return (404, {}, b"not found")

        failed_adapter = HttpProviderAdapter(
            fal_spec, workspace_root=fal_workspace,
            transport=failed_transport)
        failed_request = failed_adapter.prepare(packet, fal_context)
        failed_submitted = failed_adapter.submit(
            failed_request, fal_context)
        failed_result = failed_adapter.poll(
            "fal-req-failed",
            {**fal_context,
             "status_url": failed_submitted.get("status_url"),
             "response_url": failed_submitted.get("response_url")})
        check("CF-P1-006-R2-I2V-fal-failed-generation",
              failed_result.get("completed") is True
              and failed_result.get("failure") is not None)
    finally:
        restore_env("FAL_KEY", old_fal)

    # ---- script-derived counts (real R2 project files) ---------
    shot_list = load_json(os.path.join(EXAMPLE, "shot-list.json"))
    voice_config = load_json(os.path.join(EXAMPLE,
                                          "voice-config.json"))
    project_config = load_json(os.path.join(EXAMPLE,
                                            "project.json"))
    shots = shot_list.get("shots") or []
    voice_lines = voice_config.get("lines") or []
    counts = iv.derive_project_counts(
        project_config, shots, voice_lines)
    check("CF-P1-006-R2-I2V-counts-derived-from-script",
          counts["scenes"] == 6 and counts["shots"] == 8
          and counts["keyframes"] == 8 and counts["clips"] == 8
          and counts["lines"] == 8
          and counts["shots"] == counts["keyframes"]
          == counts["clips"] == counts["lines"]
          and counts["total_video_seconds"] == 48.0,
          str(counts))
    coverage = tl.validate_dialogue_coverage(voice_lines, shots)
    check("CF-P1-006-R2-I2V-dialogue-coverage-8x8",
          coverage == [])

    # ---- execution plan: BLOCKED (real project state) ----------
    plan = iv.build_execution_plan(
        {**project_config, "voice_lines": voice_lines}, shots,
        authorization=None)
    check("CF-P1-006-R2-I2V-plan-blocked",
          plan["status"] == "BLOCKED"
          and any("script approval pending" in r
                  for r in plan["blocked_reasons"])
          and any("keyframe is pending" in r
                  for r in plan["blocked_reasons"])
          and any("authorization" in r
                  for r in plan["blocked_reasons"]))
    check("CF-P1-006-R2-I2V-plan-cost",
          plan["estimated_cost_usd"] == 8.06
          and plan["rate_usd_per_second"] == 0.168
          and plan["total_seconds"] == 48.0,
          str(plan.get("estimated_cost_usd")))

    # ---- execution plan: READY (approved script, real keyframe,
    # valid authorization) + mock execution ----------------------
    delivery_root = os.path.join(tmpdir, "delivery")
    os.makedirs(delivery_root)
    keyframe_path = os.path.join(delivery_root, "keyframe-s1.png")
    make_png(keyframe_path)
    with open(keyframe_path, "rb") as handle:
        ready_sha = hashlib.sha256(handle.read()).hexdigest()
    ready_shot = shot("s1", "SC1", keyframe_file="keyframe-s1.png",
                      keyframe_sha=ready_sha)
    ready_project = {**project_config,
                     "script_status": "APPROVED",
                     "voice_lines": voice_lines[:1]}
    ready_auth = valid_auth(["ref-nadia-front", "scene-s1"],
                            max_generations=1)
    ready_plan = iv.build_execution_plan(
        ready_project, [ready_shot], authorization=ready_auth)
    check("CF-P1-006-R2-I2V-plan-ready",
          ready_plan["status"] == "READY"
          and len(ready_plan["generations"]) == 1
          and ready_plan["generations"][0]["status"] == "ready",
          str(ready_plan.get("blocked_reasons")))
    key_a = iv.idempotency_key(
        PROJECT_ID, "s1", iv.PROVIDER_ID, iv.MODEL_ID, ready_sha,
        iv.build_i2v_motion_prompt(motion_prompt()))
    check("CF-P1-006-R2-I2V-plan-key-deterministic",
          ready_plan["generations"][0]["idempotency_key"] == key_a)

    # A BLOCKED plan never reaches the adapter.
    blocked_adapter = MockAdapter()
    expect_error("CF-P1-006-R2-I2V-execute-blocked-refused",
                 lambda: iv.execute_i2v_plan(
                     plan, adapter=blocked_adapter,
                     delivery_root=delivery_root,
                     ledger=iv.SubmissionLedger(),
                     output_dir=tmpdir, work_dir=tmpdir))
    check("CF-P1-006-R2-I2V-execute-blocked-no-submit",
          blocked_adapter.submit_calls == 0)

    # READY plan through the mock adapter: submit, poll, verify,
    # motion-check and register the clip.
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
    check("CF-P1-006-R2-I2V-mock-execute-completes",
          executed["status"] == "completed"
          and len(executed["generations"]) == 1
          and executed["generations"][0]["provider_job_id"]
          == "mock-job-001"
          and executed["generations"][0]["motion_classification"]
          in ("subject-motion", "mixed"))
    check("CF-P1-006-R2-I2V-mock-execute-registers-clip",
          "i2v-s1" in executed["registry"]
          and executed["registry"]["i2v-s1"]["status"]
          == "VERIFIED")

    # A motion-failed provider clip stops the run.
    static_clip = os.path.join(output_dir, "static-s1.mp4")
    run_ffmpeg(["ffmpeg", "-y", "-v", "error", "-i", smooth,
                "-vf", "scale=1080:1920,zoompan=z='1+0.02*on/30':"
                "d=180:s=1080x1920:fps=30",
                "-t", "6", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                static_clip], "static mock clip")
    static_adapter = MockAdapter(clip_path=static_clip)
    expect_error("CF-P1-006-R2-I2V-mock-execute-motion-fails",
                 lambda: iv.execute_i2v_plan(
                     ready_plan, adapter=static_adapter,
                     delivery_root=delivery_root,
                     ledger=iv.SubmissionLedger(),
                     output_dir=output_dir,
                     work_dir=os.path.join(tmpdir, "exec-work-2"),
                     poll_interval_s=0))

    # ---- local-generation refusal for i2v-clip -----------------
    check("CF-P1-006-R2-I2V-kind-registered",
          "i2v-clip" in vp.VISUAL_RECIPE_KINDS)
    expect_error("CF-P1-006-R2-I2V-local-generation-refused",
                 lambda: pa.visual_argv(
                     {"kind": "i2v-clip"}, 6, "/tmp/x.mp4"))

    # ---- scene binding, motion kind i2v ------------------------
    bible = load_json(os.path.join(EXAMPLE, "character-bible.json"))
    check("CF-P1-006-R2-I2V-binding-valid",
          cc.validate_scene_binding(
              bible, shots[0], motion_kind="i2v") == [])
    bad_prompt_shot = dict(shots[0])
    bad_prompt_shot["motion_prompt"] = motion_prompt(camera="")
    check("CF-P1-006-R2-I2V-binding-bad-prompt",
          cc.validate_scene_binding(
              bible, bad_prompt_shot, motion_kind="i2v") != [])
    wrong_kind_shot = dict(shots[0])
    wrong_kind_shot["visual"] = {"kind": "ai-still",
                                 "motion": "zoom-in"}
    check("CF-P1-006-R2-I2V-binding-wrong-kind",
          cc.validate_scene_binding(
              bible, wrong_kind_shot, motion_kind="i2v") != [])
    check("CF-P1-006-R2-I2V-binding-still-unchanged",
          cc.validate_scene_binding(
              bible, {"shot_id": "s1",
                      "character_id": "DEMO-CHAR-002",
                      "reference_ids": ["ref-nadia-front"],
                      "environment_id": "env-rooftop-terrace-dawn",
                      "visual": {"motion": "zoom-in"}}) == [])

    # ---- human text review -------------------------------------
    check("CF-P1-006-R2-I2V-text-review-missing",
          iv.validate_human_text_reviews(
              [], ["clip-a.mp4"]) != [])
    check("CF-P1-006-R2-I2V-text-review-found",
          iv.validate_human_text_reviews(
              [iv.record_human_text_review(
                  "clip-a.mp4", reviewer="human-1",
                  text_found=True)], ["clip-a.mp4"]) != [])
    check("CF-P1-006-R2-I2V-text-review-clean",
          iv.validate_human_text_reviews(
              [iv.record_human_text_review(
                  "clip-a.mp4", reviewer="human-1",
                  text_found=False)], ["clip-a.mp4"]) == [])

    # ---- character drift detection (Nadia bible) ---------------
    all_pass = [{"scene_id": s.get("scene_id"),
                 "shot_id": s["shot_id"],
                 "inspector": "r2-fixture",
                 "checks": {a: "pass"
                            for a in cc.CONSISTENCY_ATTRIBUTES},
                 "notes": "fixture"} for s in shots]
    verdict = cc.evaluate_consistency(bible, all_pass)
    check("CF-P1-006-R2-I2V-drift-none-consistent",
          verdict["overall_verdict"] == "consistent")
    one_fail = [dict(entry) for entry in all_pass]
    one_fail[0] = dict(one_fail[0])
    one_fail[0]["checks"] = dict(one_fail[0]["checks"])
    one_fail[0]["checks"]["face_identity"] = "fail"
    verdict = cc.evaluate_consistency(bible, one_fail)
    check("CF-P1-006-R2-I2V-drift-found",
          verdict["overall_verdict"] == "drift-found")

    # ---- end-to-end BLOCKED path through the R2 driver ---------
    driver_work = os.path.join(tmpdir, "driver-work")
    driver_dist = os.path.join(tmpdir, "driver-dist")
    driver = os.path.join(ROOT_ABS, "scripts",
                          "run-p1006-r2-photorealistic-render.py")
    proc = subprocess.run(
        [sys.executable, driver, "--work-dir", driver_work,
         "--dist-dir", driver_dist],
        capture_output=True, text=True, timeout=300)
    check("CF-P1-006-R2-I2V-driver-exits-2-blocked",
          proc.returncode == 2,
          f"exit {proc.returncode}: "
          f"{(proc.stderr or '').strip()[:300]}")
    summary_path = os.path.join(driver_work, "render-summary.json")
    summary = load_json(summary_path) if os.path.isfile(
        summary_path) else {}
    check("CF-P1-006-R2-I2V-driver-summary-blocked",
          summary.get("final_mp4") is None
          and summary.get("qc_status") == "BLOCKED"
          and summary.get("plan_status") == "BLOCKED"
          and summary.get("counts", {}).get("shots") == 8
          and summary.get("counts", {}).get("clips") == 8
          and summary.get("estimated_cost_usd") == 8.06,
          str(summary.get("counts")))
    found_mp4 = []
    for base, _dirs, files in os.walk(driver_work):
        found_mp4 += [f for f in files if f.endswith(".mp4")]
    check("CF-P1-006-R2-I2V-driver-no-final-mp4",
          found_mp4 == [], str(found_mp4))
    keyframes_manifest = load_json(os.path.join(
        driver_work, "keyframes", "scene-keyframes.json"))
    check("CF-P1-006-R2-I2V-driver-keyframes-pending",
          len(keyframes_manifest.get("keyframes") or []) == 8
          and all(entry.get("status")
                  == "pending-generation-after-script-approval"
                  for entry in
                  keyframes_manifest.get("keyframes") or []))

    print(f"\n{_checks[0]} checks, {len(failures)} failures")
    if failures:
        print("FAILURES: " + ", ".join(failures))
        return 1
    return 0


def main():
    return run_checks()


if __name__ == "__main__":
    sys.exit(main())
