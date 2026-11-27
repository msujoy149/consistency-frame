# P1-005 local execution evidence (2026-11-27)

Real local executions performed for CF-WO-P1-005. No paid external
call was made. Media bytes are git-ignored (`.gitignore`: `*.wav`,
`*.mp4`) and are not committed; this record carries the hashes,
durations and commands so the runs are verifiable without the bytes.

## VoiceStudio — one real generation

Backend started once, generation run, backend stopped afterwards
(no backend left running).

- Command (from `components/voicestudio`):
  `NO_PROXY=localhost,127.0.0.1,::1 no_proxy=localhost,127.0.0.1,::1 OMNIVOICE_HF_ENDPOINT_MODE=manual .venv/bin/python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 3900`
- Health before generation: `{"status":"ok","device":"unknown","engine":null,"version":"0.5.8"}`
  (engine null on a cold backend until an engine is selected or used;
  the adapter pins `engine=omnivoice` on submit — see corrections
  doc §5.)
- Health after generation: `{"status":"ok","device":"cpu","engine":"omnivoice","version":"0.5.8"}`
- Generation (`POST /generate`, multipart):
  text `এটা একটা পরীক্ষা। আমি ভালো আছি।`, language `bn`,
  instruct `child, female, high pitch`, seed `11`, engine `omnivoice`
  (the evidenced 2026-11-13 test pattern; no reference audio, no
  real person's voice — a synthetic test voice).
- Response: HTTP 200, `X-Audio-Id: 1faa2e3e`, `X-Audio-Duration: 1.98`,
  `X-Gen-Time: 134.61`, `X-Seed: 11`, backend `0.5.8`.
- Output: `evidence/p1005/vs-test-001.wav` — 95,030 bytes, mono,
  24,000 Hz, 47,493 frames, 1.98 s (verified with the stdlib `wave`
  module), SHA-256
  `ec2eb338cc47beb9f0e1f5694063aac56b9c06aebb85a0e51f4ce40968d16508`.
- Backend stopped after the run: `/health` refused connection, no
  uvicorn process remains.

## OpenMontage — demo render, direct + through the adapter

- `make preflight` in `components/openmontage`: passed 2026-11-27
  (tool-registry discovery; exit 0).
- Direct render: `.venv/bin/python render_demo.py animated-reel-20s`
  (~6 min, 630 frames encoded).
- Output: `components/openmontage/projects/demos/renders/animated-reel-20s.mp4`
  — 2,131,511 bytes, SHA-256
  `b1d5c6cd0f4a0f2e7458ce9cb022f6c73053b593e6028e6d5a55a1bc29d8bbd3`,
  independently validated with ffprobe: 21.056 s, 1920x1080, h264
  30 fps, aac audio.
- Adapter run: `OpenMontageAdapter.submit` with pipeline
  `{"composition": "animated-reel-20s"}` (same demo, re-render).
  Completed; output copied to
  `evidence/p1005/om-adapter-run/outputs/exec-om-test-001.mp4` —
  2,131,511 bytes, SHA-256 identical to the direct render
  (`b1d5c6cd…`), verified by the adapter's `verify_output`.
  (The re-render overwrote the same filename; the adapter detects
  produced files by mtime + size, not by name alone — see
  corrections doc §5.)
- Scope: the demo-render entry only. Production pipeline assembly
  is NOT exercised.

## FFmpeg — real execution in tests

- `tests/test_ffmpeg_adapter.py` (CF-P1-005-FFMPEG, 28 checks):
  deterministic lavfi media generated at test time (2 s, 320x240,
  24 fps testsrc + 440 Hz sine), probed, transcoded (320x240 →
  160x120) and assembled (2 × 2 s → ~4 s) through the real
  `FFmpegAdapter`; SHA-256 of every output recomputed from the file.
- `tests/test_media_execution.py` pipeline group (CF-P1-005-EXECUTION):
  short-form (1 task), long-form (3 tasks) and mixed (1 good + 1
  failing task) end-to-end runs through `run_execution_pipeline`
  with the real FFmpeg adapter; manifests, technical QC and the
  semantic handoff built from the real outputs.
