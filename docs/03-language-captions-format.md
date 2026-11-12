# Language, Captions, and Format Rules

These rules decide three things that are often assumed and should never
be: whether a video has captions, which language each character speaks,
and what shape the video is made in. All three are the user's choice, at
generation time, every time.

---

## 1. Captions and Subtitles Are Opt-In — Ask First

Captions and subtitles are optional. Never add captions or subtitles to a
video automatically.

- When the user asks for a video, ask whether they want captions.
- If they say no, deliver the video clean, with no baked-in captions, so
  the platform's own automatic captions (YouTube, Facebook) can be used
  if they wish. The choice of platform auto-captions remains the user's.
- If they say yes, ask which language — or use the language they name —
  and produce the captions in exactly that language.
- Captions can be produced in ANY language the user requests: Bengali,
  English, Hindi, French, or any other language. The caption language
  follows the user's choice, not a default.
- When captions are produced, they are timed subtitle text (for example
  SRT) matched to the spoken dialogue line by line, and they are kept
  with the episode's assets (see the subtitles pipeline in "Extended
  Production Systems").

The default, when the user has not been asked or has not answered, is NO
baked-in captions.

## 2. Per-Character Language — Each Character Speaks Their Own Language

A video may have several characters, and each character may speak a
different language. For example, in one video one character speaks
Bengali, another speaks English, and another speaks Hindi.

- Write each character's dialogue in that character's language.
- Generate each character's voice in that language.
- Match the lip-sync to that language.
- Captions follow the same rule: a caption track per language the user
  requests.
- Never force all characters into one language unless the user asks for
  it.

Language is a per-character property, set at intake (see the episode
intake checklist in "Additional Systems") and carried through dialogue
writing, voice generation, lip-sync, and captions.

## 3. Format and Aspect Ratio on Demand

Short videos and long videos are both supported, for YouTube and for any
other platform.

- The video is made in the aspect ratio the user requests — 16:9, 9:16,
  1:1, 4:5, or any other ratio.
- Compose the framing, camera, and safe areas for that ratio from the
  start. Do not crop a finished video into a new ratio as an afterthought:
  cropping after the fact breaks framing, cuts characters out of frame,
  and destroys the composition the scene was built on.
- Cutdowns for other ratios (for example a vertical cut of a horizontal
  main cut) are recomposed for their own ratio as part of the
  distribution package (see "Extended Production Systems"), not produced
  by cropping.
- If the user does not state a ratio, ask which platform and ratio they
  want before generating. Do not guess.
