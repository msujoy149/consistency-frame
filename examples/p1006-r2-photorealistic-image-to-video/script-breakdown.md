# Script breakdown — "Nadia and the River Light"

Status: **DRAFT — AWAITING USER APPROVAL.** No visual asset has
been generated from this script. No keyframe, reference image, or
voice recording will be generated until the user approves this
script and breakdown. Counts below are DERIVED from the script,
not fixed in advance: nothing was omitted to reduce clips and
nothing was invented to inflate them.

## The complete script

Character: Nadia, DEMO-CHAR-002, fictional adult 27,
photorealistic-digital-human. Narrator-only (en-US); no character
speaks on screen, so no lip-sync is claimed. No text on screen.

| Line | Shot | Narration |
| --- | --- | --- |
| l1 | s1 | Before the sun wakes the river, Nadia lights the first lantern of the day. |
| l2 | s2 | She walks the old stone steps down to the water, carrying the light. |
| l3 | s3a | At the river's edge, she sets the lantern on the water and lets it go. |
| l4 | s3b | The lantern drifts away, and the whole morning holds its breath. |
| l5 | s4 | In the market, she gathers marigolds bright as the evening sun. |
| l6 | s5 | Rain comes without asking, and she opens her umbrella over the day. |
| l7 | s6a | At dusk, she lifts the sky lantern high, its flame reaching for the dark. |
| l8 | s6b | She lets it go, and the river light rises to meet the first stars. |

## Script analysis (what the story requires)

**Locations (3):** rooftop terrace; river (stone steps + water's
edge); market street.

**Environments / states (6):** rooftop at dawn; stone steps in
morning light; river's edge at golden hour; market street in
morning; market street in rain; rooftop at dusk.

**Character actions:** lighting a lantern with a match; walking
down stone steps; setting a lantern afloat; watching it drift;
lifting a basket of marigolds; opening an umbrella in the rain;
lifting a sky lantern overhead; releasing it and watching it rise.

**Important objects (5):** round table lantern (s1); rectangular
floating lantern (s3a, s3b); woven basket of orange marigolds (s4);
bamboo oil-paper umbrella (s5); cylindrical sky lantern (s6a, s6b).
The three lanterns are three distinct props, each appropriate to
its scene — they are NOT one continuous prop.

**Physical events:** flame catching and steadying; weight shifting
in a walking stride; water rippling as the lantern is set afloat;
the lantern drifting on the current; the basket rising in both
hands; rain falling and splashing; the umbrella unfolding; the sky
lantern lifting away and rising.

**Emotional reactions:** concentration (s1, s3a); ease and joy
(s2); hope (s3b); warmth (s4); calm endurance (s5); joy (s6a, s6b).

**Narrative developments:** light is kindled (s1) → carried to
the river (s2) → given to the water (s3a, s3b) → flowers gathered
for the evening (s4) → weather endured (s5) → light released to
the sky (s6a, s6b). One day, dawn to dusk, one lantern's journey
mirrored by the sky lantern at the end.

## Scene and shot breakdown

| Scene | Shot | What happens | Why this shot exists |
| --- | --- | --- | --- |
| SC1 rooftop, dawn | s1 | Nadia lights the round lantern with a match. | Establishing action: the light is kindled. |
| SC2 river steps, morning | s2 | Nadia walks down the stone steps toward the river. | Journey: the light is carried to the water. |
| SC3 river's edge, golden hour | s3a | Close-up on her hands: she sets the floating lantern on the water. | The giving action — hands, water, release. Needs its own close-up; a single wide shot cannot show both the hands and her face. |
| SC3 river's edge, golden hour | s3b | Close-up on her face: she watches the lantern drift. | The reaction — hope on her face as the lantern leaves. A different shot from s3a, not a longer single shot, because the camera cannot be on her hands and her face at once. |
| SC4 market, morning | s4 | Nadia lifts the basket of marigolds with both hands. | Gathering: flowers for the evening. |
| SC5 market, rain | s5 | Nadia opens the bamboo umbrella as rain falls. | Weather: the day is endured, not stopped. |
| SC6 rooftop, dusk | s6a | Nadia lifts the sky lantern overhead with both hands. | The lift — the climax begins in her arms. A separate shot from the release because the lift and the rise are two different movements. |
| SC6 rooftop, dusk | s6b | She releases the lantern; it rises as she watches, smiling. | The release — the lantern leaves her hands and rises into the sky. |

## Derived counts (calculated from this breakdown)

- Scenes: **6** (SC1–SC6)
- Shots: **8** (s1, s2, s3a, s3b, s4, s5, s6a, s6b)
- Keyframes required: **8** (one per shot — each shot starts from its own verified photorealistic keyframe)
- Genuine I2V generations required: **8** (one per shot)
- Narration lines: **8** (one per shot; dialogue coverage is 1:1)
- Reference images required: **4** (front, three-quarter, side, full-body) — generated after approval, chained from the front reference
- Clip duration: **6 s** per clip (inside the provider's 3–15 s range)
- Total video runtime: **8 × 6 s = 48 s** (inside the 30–60 s target)
- Narration: ~39.3 s planned (l1 5.8, l2 5.2, l3 5.2, l4 4.1, l5 4.1, l6 4.5, l7 5.2, l8 5.2) + 7 × 0.5 s pauses + 1.0 s lead-in + 1.5 s tail-out ≈ **45.3 s** of audio timeline
- Timing model: video-led. The 48 s of video leads; each narration line plays inside its 6 s shot; the remaining ~2.7 s across the film is ambient (river, rain, lantern glow, music, synthesized room tone). Provider clips carry no native audio in this round (generate_audio is false for every shot; see cost-plan.json). The final schedule is computed from the MEASURED narration durations at assembly time, after the authorized provider execution returns the real clips.

## What is NOT in the breakdown

- No scene was cut to save clips: the river's-edge scene keeps
  both its shots (action + reaction) and the release scene keeps
  both its shots (lift + rise).
- No shot was invented to inflate the count: every shot maps to
  a story event or a reaction the script requires.
- No title card, no end card, no text overlay of any kind.
- No second character. No lip-sync (narration only).

## Approval gate

This script + breakdown is presented for the user's approval. Until
he approves: no reference image, no keyframe, no voice recording,
and no paid provider call is generated. After approval, the build
order is: (1) regenerate the 4 reference images, chained from the
front reference, visually inspected; (2) generate the 8 keyframes,
one per shot, visually inspected; (3) generate the real narration
WAVs; (4) on the separate paid-call authorization, run the 8
image-to-video generations.
