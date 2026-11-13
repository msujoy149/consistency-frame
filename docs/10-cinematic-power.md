# Cinematic Power

This document describes the cinematic-power layer of Consistency Frame: the five systems that turn an acceptable video into a powerful cinematic one — a locked visual style, animals and creatures that perform, editing that breathes with the music, trailers built as arcs, and scale and colour scripted for the whole piece. The full rules are in the `cinematic-power` skill (`skills/cinematic-power/SKILL.md`); this document explains each system in full.

Nothing in this layer replaces the existing systems. The visual style bible, script-driven camera angles (A12), editing rhythm, script-driven colour grading, the character registry, and the episode QC checklist all still apply, unchanged. The five systems below add only the cinematic-power layer on top.

Counting note: these 5 systems are part of the repo total. Together with the 12 professional, 18 extended, 3 language/captions/format, 7 additional, 36 humanization, 7 agency advertising, 1 video regeneration, 6 live-action & VFX, 7 emotional performance, 1 user-supplied voice cloning, and 1 on-demand resource management, and 1 language authenticity, and 1 realistic person video, 1 2D explainer animation, 1 command authority, and 1 kids & family animation systems, the repo holds 109 distinct systems, presented as 120 numbered entries.

## 1. Stylized Animation Style Lock

Choose the visual style first, before any generation, and record it in the project (visual style bible). There are three styles, one choice per project:

- **2D anime** — consistent line weight, cel colour blocks, fixed highlight and shadow shapes, limited-animation rules. Holds, motion smears, and cycles are used deliberately, never by accident.
- **3D stylized CG** — fixed proportions, squash-and-stretch, a consistent material look: skin, hair, and cloth read the same in every shot.
- **Photorealistic live-action** — the existing realism rules apply: natural skin, physically accurate light, believable movement.

Background treatment follows the style. A full environment is one choice; a deliberate graphic backdrop — a clean colour with floating motifs — is another, used as a design decision rather than an empty background. Either way, the treatment is chosen with the style and held.

A style change inside one video is a deliberate, recorded decision — noted in the project record with what changed and why — never an accident of a new generation. The style lock covers characters, animals, objects, and backgrounds alike: a photorealistic character in a cel-shaded world (or the reverse) is a style break, not a creative choice. Every shot is checked against the style lock before delivery.

## 2. Animal & Creature Performance

Animals and creatures are registered like characters. Each one is distinct — species, size, colours, markings — recorded in its own record (`<creature-id>`), and held consistent across every shot.

Movement follows the creature's real body: quadruped gait, flight, swimming, crawling — the movement a real body of that shape can make. Human movement is never pasted onto an animal: no upright walking for a quadruped, no human hand gestures from a paw, no human facial expressions on a muzzle that cannot make them.

Creatures act. A sidekick animal has comic timing — head tilts, eye pops, delayed reactions — and the joke lands because the timing is deliberate. A monster has menace in stillness before it moves: it is frightening because it waits, not because it flails. Elemental forces (an ocean, a fire, a storm) may act as characters, behaving as a living presence with consistent behaviour across the piece; when an element acts, its continuity is checked like any character's. Groups of animals are never clones: each animal in a group is distinct in look and in timing. Animals follow the same continuity rules as characters — identity, markings, and props never change between shots unless the story requires it.

## 3. Music-Beat Editing & Synchronized Ensemble

In music-driven videos, the beat is the clock. Build the edit from the song's structure — verse, chorus, drop — and place cuts, gestures, and movements on the musical beat. The biggest movement lands on the strongest beat.

When many characters — and animals — move together, they share one timing reference: a synchronized jump, dance, or reaction happens on the same beat for everyone, with no drift between them. Rehearse ensemble timing in the shot list before generation. A group out of sync reads as a mistake, never as style — a character or an animal landing a beat late is a defect to correct, not a variation to keep.

Introductions follow the music: characters are introduced one by one in time with the music, then brought together in a group shot, then closed with the synchronized finale on the strongest beat. Each section is timed to the song, not to an arbitrary shot count. A cut that lands between beats must have a story reason; a movement that ignores the beat must be deliberate and visible as a choice.

## 4. Trailer & Teaser Structure

A trailer is built, not summarized. It has six beats, in this order:

1. **Open on wonder.** A striking image, no explanation. The audience feels the world before they understand it.
2. **Escalate the stakes.** A threat, a storm, a monster — something that makes the journey necessary.
3. **Reveal the characters.** Each introduction has a job: one shows the hero's determination, one shows the companion's power, one shows the sidekick's comedy. No introduction is decoration.
4. **One comedy beat after tension.** A sidekick, a small creature, a visual gag — placed right after tension so the audience can breathe. Exactly one beat; comedy is a pause, not the trailer.
5. **Climax montage.** Short, fast, escalating — the biggest images in the shortest time, each one raising the last.
6. **End on the title card, then credits.** The title is the last image the audience keeps. Nothing after it competes with it.

Never reveal the ending. Never explain what the images already show — if a shot says it, no line of dialogue needs to say it again. Each beat has a duration budget in the shot list. The trailer must work without the full film: a viewer who never sees the film still feels a complete arc. A teaser is the same structure shortened — wonder, one stake, one character, title. The order never changes; only the length does.

## 5. Scale, Spectacle & Colour Scripting

Awe is planned, not improvised. Scale contrast is the primary tool for wonder: a small character against a giant wave, volcano, or island makes the audience feel the size of the world. Use it at the beats that need it — not everywhere, or it stops working.

Spectacle shots are planned per beat in the shot list, never improvised. Each spectacle shot has a named beat, a named purpose (wonder, threat, triumph), and a camera angle chosen from that beat (A12). A spectacle shot without a beat is decoration.

Colour is scripted for the whole piece. Assign a palette to each emotional beat — bright wonder, warm sunset, dark storm, monster glow, bright title — and plan the transitions between palettes. Colour follows emotion, not only time of day: a storm is dark because the story is dark, and the title is bright because the story resolves. Never change palette randomly inside a beat: within one beat the palette holds, and it changes only when the emotion changes, with the change planned in the colour script. Scale and colour work together — the biggest scale contrast lands on the beat with the strongest palette shift, so wonder and colour arrive at the same moment.

## Working records

Cinematic-power work is recorded in the project's shot list, in the private overlay — never in the public repository:

```text
projects/<project-id>/
  style-lock.md        # chosen style (2D anime / 3D stylized CG / photorealistic) + background treatment
  colour-script.md     # palette per emotional beat + planned transitions
  trailer-plan.md      # trailer beats in order + duration budget per beat (trailers only)
  shot-list.md         # per shot: angle (A12), style check, spectacle purpose, beat timing
```

The style lock, colour script, and trailer plan are written before generation, not after. A change to any of them is a deliberate, recorded decision.
