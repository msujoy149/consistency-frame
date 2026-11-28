# Motion prompts — "Nadia and the River Light" (preflight)

Status: **DRAFT — script awaiting user approval.** No keyframe, reference image, or provider clip has been generated from these prompts. Every shot uses `generate_audio: false` (external narration handled separately by the existing voice pipeline; the provider must not generate unintended audio). No on-screen text of any kind. Photorealistic digital human only.

Style lock (every shot): Photorealistic digital human only: natural skin texture with visible pores, dark brown eyes of natural size, long straight black hair with centre part, rust-orange linen shirt (#B4552A), dark indigo jeans, brown leather sandals, brass bangle on the LEFT wrist, small gold hoop earrings. Realistic proportions, natural light and shadow, cinematic colour and exposure. Never cartoon, anime, illustration, or stylized.

Text prohibition (appended to every composed provider prompt): "No visible text, writing, signage, typography, subtitles, captions, watermarks, or logos."

## Shot s1 — scene SC1, line l1 (6 s, $1.344, audio off, with elements)

- **Source script segment:** "Before the sun wakes the river, Nadia lights the first lantern of the day."
- **Narrative purpose:** Establishing action: the light is kindled. Also the film's establishing shot — the rooftop terrace, the river and rooftops below, and the dawn light are all established inside this shot.
- **Character:** DEMO-CHAR-002 (Nadia) — expression: concentration
- **Scene keyframe:** shot s1 keyframe, status `pending-generation-after-script-approval`, 1152x2048, 9:16 (pending generation after script approval)
- **Character elements:** frontal @Element1 (`ref-nadia-front`, `frontal_image_url`) + @Element2 (`ref-nadia-three-quarter`, `reference_image_urls`, three-quarter, upper body, head turned slightly left) + expression sheet `ref-nadia-expressions` (concentration). All pending generation after script approval; element conditioning implementation in progress in a parallel workstream and not yet wired into the provider contract.
- **Environment:** Rooftop terrace at dawn: low clay table, potted plant at the left edge, river and rooftops far below, pale gold sky brightening.
- **Action:** Nadia lights the round paper lantern on the rooftop terrace at dawn; the flame catches and the lantern glows warm.
- **Body movement:** She leans slightly over the low clay table, shoulders relaxed, weight settled.
- **Facial movement:** She looks down at the lantern, blinks slowly, and breathes out as the light steadies; a soft, focused expression.
- **Hand / object interaction:** Both hands cup the flame and steady the lantern; her fingers move naturally around the match and the lantern rim.
- **Hair / cloth movement:** Her long black hair and rust-orange linen shirt move gently in the morning breeze.
- **Environmental motion:** The pale gold dawn sky brightens behind her and the river far below catches the first light.
- **Camera movement:** Steady medium shot, drifting in very slowly; no pan and no fast zoom.
- **Physical realism constraints:** The match flame stays attached to the match head, then to the wick; the lantern paper glows from within without warping; her hands never pass through the lantern or the table; the flame flickers at a natural rate and steadies.
- **Negative prompt:** cartoon, anime, illustration, stylized 3D render, flat 2D, plastic-smooth skin, oversized eyes, distorted face, extra fingers, deformed hands, morphing face, changing outfit, changing hair colour, second character, on-screen text, captions, subtitles, keywords, labels, logos, watermarks, decorative typography, title card, static poster, motion graphics, slideshow effect, unlit lantern, flame detaching from the wick, match burning her fingers
- **Expected duration:** 6 s (provider enum "6", range "3"–"15"). 6 s: the narration line needs 5.8 s, and the strike-cup-light movement needs the full clip; a shorter clip would cut the lighting action.
- **Audio:** `generate_audio: false`. **Text overlay:** all six flags false (see `shot-list.json`).

## Shot s2 — scene SC2, line l2 (6 s, $1.344, audio off, with elements)

- **Source script segment:** "She walks the old stone steps down to the water, carrying the light."
- **Narrative purpose:** Journey: the light is carried to the water. Movement through the river-steps location — the full-body walk down the steps, ending at the water.
- **Character:** DEMO-CHAR-002 (Nadia) — expression: joyful
- **Scene keyframe:** shot s2 keyframe, status `pending-generation-after-script-approval`, 1152x2048, 9:16 (pending generation after script approval)
- **Character elements:** frontal @Element1 (`ref-nadia-front`, `frontal_image_url`) + @Element2 (`ref-nadia-full-body`, `reference_image_urls`, full body, standing, front, whole outfit visible) + expression sheet `ref-nadia-expressions` (joyful). All pending generation after script approval; element conditioning implementation in progress in a parallel workstream and not yet wired into the provider contract.
- **Environment:** Wide old stone steps receding to the river, fallen leaves at the edges, trees behind, morning light on the water.
- **Action:** Nadia walks down the wide old stone steps toward the river, carrying the lit round lantern in one hand, one foot mid-step, hair and shirt moving with her stride.
- **Body movement:** She walks down the stone steps with a natural stride: weight shifts from one foot to the other, arms swing gently at her sides, the lantern arm held steady so the flame stays upright.
- **Facial movement:** She smiles warmly and looks ahead toward the water, blinking in the morning light.
- **Hand / object interaction:** One hand carries the lit round lantern steady at her side, fingers wrapped around its bamboo frame, the flame glowing inside; her other hand lifts the hem of her shirt slightly as she steps.
- **Hair / cloth movement:** Her long black hair and rust-orange linen shirt move with her stride and the light breeze.
- **Environmental motion:** The river ripples behind her and leaves stir at the edges of the steps.
- **Camera movement:** Steady full-body shot, holding her in frame as she walks toward the camera; no pan.
- **Physical realism constraints:** Each step plants on a stone tread before the weight shifts; the carried lantern stays upright and its flame stays lit and attached; her feet never slide across the steps; stride length matches a real walking pace for a 6-second shot.
- **Negative prompt:** cartoon, anime, illustration, stylized 3D render, flat 2D, plastic-smooth skin, oversized eyes, distorted face, extra fingers, deformed hands, morphing face, changing outfit, changing hair colour, second character, on-screen text, captions, subtitles, keywords, labels, logos, watermarks, decorative typography, title card, static poster, motion graphics, slideshow effect, standing still, frozen mid-step, lantern vanishing between frames, feet sliding without stepping
- **Expected duration:** 6 s (provider enum "6", range "3"–"15"). 6 s: the narration line needs 5.2 s, and the walk needs several full strides to read as movement, not a pose.
- **Audio:** `generate_audio: false`. **Text overlay:** all six flags false (see `shot-list.json`).

## Shot s3a — scene SC3, line l3 (6 s, $1.344, audio off, with elements)

- **Source script segment:** "At the river's edge, she sets the lantern on the water and lets it go."
- **Narrative purpose:** Giving action — hands, water, release. Detail shot: a single wide shot cannot show both her hands on the lantern and her face, so the hands get their own close-up.
- **Character:** DEMO-CHAR-002 (Nadia) — expression: concentration
- **Scene keyframe:** shot s3a keyframe, status `pending-generation-after-script-approval`, 1152x2048, 9:16 (pending generation after script approval)
- **Character elements:** frontal @Element1 (`ref-nadia-front`, `frontal_image_url`) + @Element2 (`ref-nadia-three-quarter`, `reference_image_urls`, three-quarter, upper body, head turned slightly left) + expression sheet `ref-nadia-expressions` (concentration). All pending generation after script approval; element conditioning implementation in progress in a parallel workstream and not yet wired into the provider contract.
- **Environment:** River's edge at golden hour: rippling water filling the frame behind, soft bokeh of trees.
- **Action:** Close-up on Nadia's hands: she kneels at the river's edge and sets the rectangular floating lantern on the water; the current takes it.
- **Body movement:** She kneels at the water's edge and leans forward slowly, lowering the lantern with care.
- **Facial movement:** She looks down at the lantern, eyes lowered in concentration, lips closed.
- **Hand / object interaction:** Both hands lower the lantern to the water, fingers spread beneath it, then open and release it; the lantern floats free and the water ripples around it.
- **Hair / cloth movement:** A few strands of her long black hair fall forward as she leans; her rust-orange shirt stays settled.
- **Environmental motion:** Ripples spread from the lantern as it touches the water, and the current carries it gently away.
- **Camera movement:** Steady close-up on her hands and the lantern; no pan, no zoom.
- **Physical realism constraints:** The lantern floats on the water surface and never sinks; ripples spread outward from the point of contact at a natural speed; her fingers leave the lantern before it drifts; the waterline stays consistent.
- **Negative prompt:** cartoon, anime, illustration, stylized 3D render, flat 2D, plastic-smooth skin, oversized eyes, distorted face, extra fingers, deformed hands, morphing face, changing outfit, changing hair colour, second character, on-screen text, captions, subtitles, keywords, labels, logos, watermarks, decorative typography, title card, static poster, motion graphics, slideshow effect, lantern sinking, lantern tipping over, hands passing through water, water splashing unnaturally
- **Expected duration:** 6 s (provider enum "6", range "3"–"15"). 6 s: the narration line needs 5.2 s, and the lower, release and first drift need the full clip to read as one continuous action.
- **Audio:** `generate_audio: false`. **Text overlay:** all six flags false (see `shot-list.json`).

## Shot s3b — scene SC3, line l4 (6 s, $1.344, audio off, with elements)

- **Source script segment:** "The lantern drifts away, and the whole morning holds its breath."
- **Narrative purpose:** Reaction: hope on her face as the lantern leaves. A different shot from s3a, not a longer single shot, because the camera cannot be on her hands and her face at once.
- **Character:** DEMO-CHAR-002 (Nadia) — expression: hopeful
- **Scene keyframe:** shot s3b keyframe, status `pending-generation-after-script-approval`, 1152x2048, 9:16 (pending generation after script approval)
- **Character elements:** frontal @Element1 (`ref-nadia-front`, `frontal_image_url`) + @Element2 (`ref-nadia-three-quarter`, `reference_image_urls`, three-quarter, upper body, head turned slightly left) + expression sheet `ref-nadia-expressions` (hopeful). All pending generation after script approval; element conditioning implementation in progress in a parallel workstream and not yet wired into the provider contract.
- **Environment:** River's edge at golden hour: rippling water and the glowing lantern at the right of frame, soft bokeh of trees.
- **Action:** Nadia watches the floating lantern drift away on the river, chin near her folded hands, a soft hopeful expression.
- **Body movement:** She kneels still at the water's edge, shoulders down, breathing slowly and visibly.
- **Facial movement:** She watches the lantern with a soft hopeful expression, blinking slowly, her gaze following it as it drifts.
- **Hand / object interaction:** Her hands stay folded beneath her chin, fingers still, knuckles relaxed.
- **Hair / cloth movement:** A few strands of her long black hair stir in the evening air; her rust-orange shirt stays settled.
- **Environmental motion:** The lantern drifts slowly on the rippling water and its reflection shivers; the light on the water moves with the current.
- **Camera movement:** Steady close-up, holding her face; no pan, no zoom.
- **Physical realism constraints:** The lantern drifts away from her at a steady current speed and stays the same size relative to distance; her gaze tracks it smoothly; her face structure never changes; blinks are slow and natural.
- **Negative prompt:** cartoon, anime, illustration, stylized 3D render, flat 2D, plastic-smooth skin, oversized eyes, distorted face, extra fingers, deformed hands, morphing face, changing outfit, changing hair colour, second character, on-screen text, captions, subtitles, keywords, labels, logos, watermarks, decorative typography, title card, static poster, motion graphics, slideshow effect, lantern drifting backwards, lantern vanishing, face changing shape, blinking unnaturally fast
- **Expected duration:** 6 s (provider enum "6", range "3"–"15"). 6 s: the narration line needs 4.1 s; the remaining time is the silent watching beat — the lantern drifting while she holds her breath — which is the point of the shot.
- **Audio:** `generate_audio: false`. **Text overlay:** all six flags false (see `shot-list.json`).

## Shot s4 — scene SC4, line l5 (6 s, $1.344, audio off, with elements)

- **Source script segment:** "In the market, she gathers marigolds bright as the evening sun."
- **Narrative purpose:** Gathering: flowers for the evening. The market street is established inside this shot — stall, hanging fabrics, shoppers — so no standalone market wide is needed.
- **Character:** DEMO-CHAR-002 (Nadia) — expression: joyful
- **Scene keyframe:** shot s4 keyframe, status `pending-generation-after-script-approval`, 1152x2048, 9:16 (pending generation after script approval)
- **Character elements:** frontal @Element1 (`ref-nadia-front`, `frontal_image_url`) + @Element2 (`ref-nadia-full-body`, `reference_image_urls`, full body, standing, front, whole outfit visible) + expression sheet `ref-nadia-expressions` (joyful). All pending generation after script approval; element conditioning implementation in progress in a parallel workstream and not yet wired into the provider contract.
- **Environment:** Market street in morning: stall at the left, hanging fabrics behind, shoppers softly blurred in the distance, warm dusty daylight.
- **Action:** Nadia reaches for the woven basket of marigolds on the market stall and lifts it gently with both hands.
- **Body movement:** She stands at the stall and leans forward slightly as she lifts the basket, her weight settling into the lift.
- **Facial movement:** She smiles gently at the flowers, eyes bright, glancing down at the basket as she lifts it.
- **Hand / object interaction:** Both hands close around the basket handle and lift it: fingers grip the woven handle, the basket rises, and a few marigold stems tremble with the movement.
- **Hair / cloth movement:** Her long black hair falls forward slightly with the lean and settles back; her shirt moves with her shoulders.
- **Environmental motion:** Hanging fabrics sway almost imperceptibly behind her and distant shoppers move softly out of focus.
- **Camera movement:** Steady medium shot, holding her centred; no pan, no zoom.
- **Physical realism constraints:** The basket has real weight: it rises only when both hands lift it and sags slightly with the lift; marigold stems tremble but stay in the basket; her grip closes around the woven handle.
- **Negative prompt:** cartoon, anime, illustration, stylized 3D render, flat 2D, plastic-smooth skin, oversized eyes, distorted face, extra fingers, deformed hands, morphing face, changing outfit, changing hair colour, second character, on-screen text, captions, subtitles, keywords, labels, logos, watermarks, decorative typography, title card, static poster, motion graphics, slideshow effect, basket passing through the stall, marigolds changing colour, flowers detaching and floating
- **Expected duration:** 6 s (provider enum "6", range "3"–"15"). 6 s: the narration line needs 4.1 s; the reach, grip and lift need the full clip to read as one continuous action.
- **Audio:** `generate_audio: false`. **Text overlay:** all six flags false (see `shot-list.json`).

## Shot s5 — scene SC5, line l6 (6 s, $1.344, audio off, with elements)

- **Source script segment:** "Rain comes without asking, and she opens her umbrella over the day."
- **Narrative purpose:** Weather endured: the same market street in its rain state. The day is endured, not stopped — the calm reaction in the rain is the beat.
- **Character:** DEMO-CHAR-002 (Nadia) — expression: calm
- **Scene keyframe:** shot s5 keyframe, status `pending-generation-after-script-approval`, 1152x2048, 9:16 (pending generation after script approval)
- **Character elements:** frontal @Element1 (`ref-nadia-front`, `frontal_image_url`) + @Element2 (`ref-nadia-full-body`, `reference_image_urls`, full body, standing, front, whole outfit visible) + expression sheet `ref-nadia-expressions` (calm). All pending generation after script approval; element conditioning implementation in progress in a parallel workstream and not yet wired into the provider contract.
- **Environment:** Market street in rain: wet cobblestones, warm shop lights reflecting on wet stone, overcast daylight, stalls softly blurred.
- **Action:** Rain begins in the market; Nadia opens the bamboo umbrella above her head with one hand and stands under it as the rain falls.
- **Body movement:** She stands under the umbrella, shoulders relaxed, breathing calmly as the rain falls around her.
- **Facial movement:** She looks calmly into the rain, blinking against the drops, a quiet unhurried expression.
- **Hand / object interaction:** One hand raises the bamboo umbrella and opens it above her head: the umbrella unfolds, its ribs spreading, and she steadies the handle.
- **Hair / cloth movement:** Her long black hair, damp from the rain, moves in the wind; her wet rust-orange shirt clings slightly and drips.
- **Environmental motion:** Rain falls steadily around her and splashes on the wet cobblestones; warm shop light shimmers on the wet stone.
- **Camera movement:** Steady medium shot, holding her centred; no pan, no zoom.
- **Physical realism constraints:** Rain falls downward at a natural rate and splashes on the cobblestones; the umbrella unfolds rib by rib over a visible moment, not instantly; her hair and shirt grow damp and cling slightly; drops bead on the umbrella surface.
- **Negative prompt:** cartoon, anime, illustration, stylized 3D render, flat 2D, plastic-smooth skin, oversized eyes, distorted face, extra fingers, deformed hands, morphing face, changing outfit, changing hair colour, second character, on-screen text, captions, subtitles, keywords, labels, logos, watermarks, decorative typography, title card, static poster, motion graphics, slideshow effect, rain falling upward, umbrella opening instantly, dry clothes in rain, umbrella passing through her head
- **Expected duration:** 6 s (provider enum "6", range "3"–"15"). 6 s: the narration line needs 4.5 s; the unfold and the first rain splashes need the full clip.
- **Audio:** `generate_audio: false`. **Text overlay:** all six flags false (see `shot-list.json`).

## Shot s6a — scene SC6, line l7 (6 s, $1.344, audio off, with elements)

- **Source script segment:** "At dusk, she lifts the sky lantern high, its flame reaching for the dark."
- **Narrative purpose:** The lift — the climax begins in her arms. A separate shot from the release because the lift and the rise are two different movements.
- **Character:** DEMO-CHAR-002 (Nadia) — expression: joyful
- **Scene keyframe:** shot s6a keyframe, status `pending-generation-after-script-approval`, 1152x2048, 9:16 (pending generation after script approval)
- **Character elements:** frontal @Element1 (`ref-nadia-front`, `frontal_image_url`) + @Element2 (`ref-nadia-full-body`, `reference_image_urls`, full body, standing, front, whole outfit visible) + expression sheet `ref-nadia-expressions` (joyful). All pending generation after script approval; element conditioning implementation in progress in a parallel workstream and not yet wired into the provider contract.
- **Environment:** Rooftop terrace at dusk: deep blue sky, river lights and rooftops below, warm lantern glow.
- **Action:** Nadia lifts the cylindrical sky lantern overhead with both hands, its flame already reaching for the dark.
- **Body movement:** She stands tall on the rooftop and raises both arms overhead, lifting the lantern with her whole body.
- **Facial movement:** She smiles and looks up at the lantern, eyes bright with anticipation.
- **Hand / object interaction:** Both hands hold the lantern rim from below, fingers spread around the frame, steadying it as it fills with warm air.
- **Hair / cloth movement:** Her long black hair blows in the evening wind and her rust-orange shirt moves with the breeze.
- **Environmental motion:** The dusk sky deepens to blue behind her and the river lights below shimmer.
- **Camera movement:** Steady medium shot, holding her centred as her arms rise; no pan, no fast zoom.
- **Physical realism constraints:** The lantern stays in her hands until the release shot; it fills with warm air and tugs gently upward against her grip; her arms rise at a natural lifting speed; the flame stays inside the lantern.
- **Negative prompt:** cartoon, anime, illustration, stylized 3D render, flat 2D, plastic-smooth skin, oversized eyes, distorted face, extra fingers, deformed hands, morphing face, changing outfit, changing hair colour, second character, on-screen text, captions, subtitles, keywords, labels, logos, watermarks, decorative typography, title card, static poster, motion graphics, slideshow effect, lantern rising before release, flame going out, arms bending unnaturally
- **Expected duration:** 6 s (provider enum "6", range "3"–"15"). 6 s: the narration line needs 5.2 s, and the two-handed overhead lift needs the full clip.
- **Audio:** `generate_audio: false`. **Text overlay:** all six flags false (see `shot-list.json`).

## Shot s6b — scene SC6, line l8 (6 s, $1.344, audio off, with elements)

- **Source script segment:** "She lets it go, and the river light rises to meet the first stars."
- **Narrative purpose:** The release — the lantern leaves her hands and rises into the sky. The film's closing shot: she watches it go, smiling.
- **Character:** DEMO-CHAR-002 (Nadia) — expression: joyful
- **Scene keyframe:** shot s6b keyframe, status `pending-generation-after-script-approval`, 1152x2048, 9:16 (pending generation after script approval)
- **Character elements:** frontal @Element1 (`ref-nadia-front`, `frontal_image_url`) + @Element2 (`ref-nadia-full-body`, `reference_image_urls`, full body, standing, front, whole outfit visible) + expression sheet `ref-nadia-expressions` (joyful). All pending generation after script approval; element conditioning implementation in progress in a parallel workstream and not yet wired into the provider contract.
- **Environment:** Rooftop terrace at dusk: deep blue sky, river lights and rooftops below, warm lantern glow.
- **Action:** Nadia releases the glowing sky lantern; it rises into the dusk sky as she watches it go, smiling.
- **Body movement:** She releases the lantern and lowers her arms slowly, watching it rise, her shoulders easing down.
- **Facial movement:** She smiles broadly and looks up, following the lantern with her eyes as it rises.
- **Hand / object interaction:** Both hands hold the lantern rim, fingers spread, then open and release it; the lantern lifts away from her hands.
- **Hair / cloth movement:** Her long black hair blows in the evening wind and her rust-orange shirt moves with the breeze.
- **Environmental motion:** The sky lantern rises into the deep blue dusk sky, glowing warm, while the river lights below shimmer.
- **Camera movement:** Steady medium-wide shot, holding her centred as the lantern rises; no pan, no fast zoom.
- **Physical realism constraints:** Once released the lantern rises steadily and grows smaller with distance; her arms lower at a natural speed; her gaze follows it upward smoothly; the lantern never falls back down.
- **Negative prompt:** cartoon, anime, illustration, stylized 3D render, flat 2D, plastic-smooth skin, oversized eyes, distorted face, extra fingers, deformed hands, morphing face, changing outfit, changing hair colour, second character, on-screen text, captions, subtitles, keywords, labels, logos, watermarks, decorative typography, title card, static poster, motion graphics, slideshow effect, lantern falling, lantern hovering at her hands, face changing shape
- **Expected duration:** 6 s (provider enum "6", range "3"–"15"). 6 s: the narration line needs 5.2 s, and the release plus the first rise need the full clip to close the film.
- **Audio:** `generate_audio: false`. **Text overlay:** all six flags false (see `shot-list.json`).
