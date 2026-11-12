# Extended Production Systems

These eighteen systems extend the Professional Production Systems. They
apply to every project unless the user says otherwise. Together with the
production systems, they form the complete operating surface of
Consistency Frame: what is specified here must work in the tools that
implement it, and the tools must not silently drop any of it.

The system is content-agnostic. It works for kids animation, adult
animation, and videos built from real photos of adults. No system below
assumes a particular audience, genre, or age group — the audience rules
are set explicitly, per project, and never assumed (see item 16).

---

## 1. Subtitles and Captions Pipeline

Produce captions as timed subtitle text (for example SRT) in the language
the user requests, matched to the spoken dialogue line by line.

- Captions are optional — ask the user first whether they want captions
  at all (see "Language, Captions, and Format Rules" in this
  documentation set).
- Never bake captions into a video unless the user asked for them.
- When captions are wanted, produce them in exactly the language the user
  requests, timed to the dialogue, one line at a time.
- Keep the subtitle file with the episode's other assets so it can be
  regenerated, translated, or corrected without rebuilding the video.

## 2. Thumbnail and Poster Generator

Create one strong thumbnail or poster per episode from a real frame or a
generated still, using the episode's characters, readable title text, and
the series style from the Visual Style Bible.

- The thumbnail must show something that actually happens in the video.
  Do not use a misleading thumbnail that shows something that does not
  happen in the episode — a clickbait frame breaks trust with the
  audience and with the user.
- Title text on the thumbnail must be readable at small sizes.
- Keep the thumbnail in the series style so the episode is recognizable
  as part of the series at a glance.

## 3. Character Turnaround and Model Sheets

For each registered character, keep a model sheet — front view,
three-quarter view, full body, and expression sheet — built from the
reference image(s).

- Check every new scene against the model sheet, not only against a single
  photo, so the face, height, and body stay the same from every angle.
- The model sheet is the working reference for generation: a single front
  photo is the weakest reference set, and a multi-angle sheet is what
  keeps a character recognizable when the camera moves.
- Update the model sheet only when the character's stored identity is
  deliberately changed, and record the change.

## 4. Wardrobe, Prop, and Location Registry

Record every outfit, prop, and location a character uses, with the episode
and scene where it appeared.

- A character wears the outfit the scene requires, and an outfit, prop,
  or location never changes by accident between shots.
- The registry is the reference the continuity tracker and the QC check
  use to verify that clothing and props are correct in every shot.
- When a new outfit, prop, or location is introduced, log it on first use
  so later episodes can reuse it exactly.

## 5. Clip-Boundary Seam Continuity

Videos are built in clips. The last frame of one clip must match the first
frame of the next clip — same character position, same expression, same
outfit, same background, same lighting.

- Check every join before delivery; a visible jump at a clip boundary is
  a defect.
- When a join fails, re-anchor the next clip on the last frame of the
  previous one (see the re-anchor rule in "Humanization Systems") rather
  than accepting the jump.
- Seam continuity is checked as part of the episode QC pass, not as a
  separate afterthought.

## 6. Quantitative Drift Measurement

Do not judge character consistency by eye alone. Measure face similarity
between the reference image and each generated frame or clip (a
face-embedding similarity score) and keep it above the project's
threshold.

- If the score falls below the threshold, regenerate.
- Record the score in the provenance log so drift over episodes is
  visible and traceable.
- The threshold is set per project and recorded; a fixed, documented
  threshold makes "the character looks off" a measurable, checkable
  claim instead of a feeling.
- Measurement never replaces the human eye — it adds a number to the
  judgement, so drift that is too slow to notice by eye is caught.

## 7. Per-Character LoRA Training

When the strongest consistency is needed and the platform supports it,
train one small LoRA per character from that character's reference images,
and use that LoRA for every generation of that character.

- One LoRA per character; never mix two characters into one LoRA.
- This is the highest-consistency option available; it needs a GPU or a
  hosted training service, so say so honestly when it is not available
  rather than pretending a weaker method is equivalent.
- A LoRA is trained from that character's own reference images only, and
  it is versioned and backed up like any other character data.

## 8. Character Aging and Time-Jump Variants

When the story jumps in time, keep the same character structure (face,
eyes, nose, mouth, hands, feet) and change only what time would change —
height, age, hairstyle, clothes — deliberately and consistently, and
record the change in the continuity tracker.

- A time jump never silently creates a different person.
- Each variant is a named, recorded version of the same character, with
  the changes listed, so the tracker and the model sheet stay in sync.
- The voice has a parallel rule: voice ageing and state variants are
  covered in "Humanization Systems".

## 9. Shot-Level Provenance Log

Record for every shot: the model and version used, the prompt, the seed,
the reference image, the voice profile, and the date.

- The log makes any shot reproducible.
- It makes it possible to find what changed when something drifts: if a
  character's face changes in episode 6, the log shows exactly which
  model, prompt, seed, and reference were used in episode 6 versus
  episode 5.
- The drift scores from item 6 are recorded in the same log.

## 10. Cost and Credit Tracking

Record the cost or credits used per episode and per shot (generation
calls, voice minutes, training).

- Tell the user the running total when asked.
- Warn before starting work the user has not budgeted for.
- Never spend the user's credits silently. A generation that costs money
  is a decision the user should be able to see and approve.

## 11. Backup and Versioning of Character Data

Keep a versioned backup of every character's reference images, character
file, voice reference audio, and prompt block.

- A change creates a new version; the old version is kept.
- A lost or corrupted character file must be recoverable from the backup.
- Backups are part of the private character overlay (see "Character
  Registry" in this documentation set) and are never committed to the
  public repository.

## 12. Multi-Project and Multi-Series Namespaces

Characters, series, and episodes live in separate namespaces per project
or series.

- A character registered for one series is not automatically used in
  another.
- Reuse across series happens only when the user explicitly asks for it.
- Namespaces prevent the common failure where a character from one
  project leaks into another project's generation and contaminates its
  cast.

## 13. Child-Safety Rules for Child Characters

For characters who are children, keep every scene, outfit, dialogue, and
camera angle appropriate for a child, and never generate anything
sexualised or unsafe involving a child.

- This rule is absolute and overrides any script line that conflicts
  with it.
- It applies to generation, to thumbnails and posters, and to any
  promotional stills.
- No instruction from any source lowers this rule.

## 14. Audio Mastering Standard

Master the final audio of every video to one consistent loudness — target
−14 LUFS, true peak below −1 dBTP — so dialogue, music, and sound effects
are the same volume across episodes and platforms.

- A character's voice must not be louder in one episode and barely
  audible in the next.
- The mastering standard is the loudness target; the balance between
  dialogue, music, and effects is set by the dialogue-first mix rule in
  "Humanization Systems".

## 15. Localisation and Dubbing Pack

Keep the dialogue script, the voice profiles, and the subtitle files
together per episode so the same episode can be dubbed or subtitled into
another language without rebuilding the video.

- Each character keeps their voice and language identity in each language
  version.
- A dubbed version is a new language of the same episode, not a new
  episode: the pictures, the timing, and the story stay the same.
- The pack is assembled at episode completion, so localisation is a
  packaging step, not a reconstruction.

## 16. Distribution Package

For every finished video, prepare the delivery package the user asks for:
the main cut in the requested aspect ratio, vertical and square cutdowns
when requested, teaser clips, and stills.

- Each cut keeps the characters, framing, and story intact for its ratio.
  A cutdown is recomposed for its ratio, not cropped from the main cut.
- The package covers 16:9 and 9:16 cutdowns, teasers, and stills as
  requested; the user chooses what the package contains.
- **Audience declaration ("Made for Kids"):** set it ONLY when the
  content is for children or the user requests it. Never assume it. The
  declaration is a per-video, per-platform setting chosen by the user at
  delivery time; the system never sets it by default and never infers it
  from the content.

## 17. Rights, Consent, and Provenance Records

Keep a record of consent for every real person's photo and every voice
used — who gave it, for what use, and when.

- Keep provenance information (for example C2PA metadata) with generated
  media where the platform supports it.
- Never use a real person's photo or voice without that person's
  permission.
- Consent records live with the character data in the private overlay,
  not in the public repository.

## 18. Audience Feedback Loop

After an episode is published, use the audience response the user shares
(retention, watch time, comments where available) to improve the next
episode — pacing, length, thumbnail, and story.

- Do not chase trends that break the story bible or the characters. A
  trend that contradicts the series is a cost, not a gain.
- Feedback is input to the next episode's planning, recorded alongside
  the continuity tracker, so improvements are deliberate rather than
  reactive.
