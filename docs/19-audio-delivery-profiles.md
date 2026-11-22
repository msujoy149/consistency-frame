# 19. Audio Delivery Profiles

Loudness is a delivery profile, not a universal constant. The pre-P0
rule — master everything to one loudness target — is retired.

## Rule

1. The project names a delivery profile **before** mastering (see
   `architecture/audio-delivery-profiles.json` for the machine-readable
   profiles).
2. If no profile is named, ask the user which destination the video is
   for. There is no universal default.
3. Within one project or series, use the **same** profile for every
   episode, so dialogue, music and sound effects stay at the same
   volume.
4. A profile carries: integrated loudness (LUFS), loudness range (LU),
   maximum true peak (dBTP), destination, source of the specification,
   checked date and tolerance.

## Profiles (v2.3, checked 2026-11-22)

| Profile | Destination | Integrated loudness | Loudness range | Max true peak |
|---|---|---|---|---|
| `streaming-social` | Streaming / social platforms (e.g. YouTube, social video) | −14 LUFS | 11 LU | −1 dBTP |
| `broadcast-ebu-r128` | Broadcast (EBU R 128) | −23 LUFS | 20 LU | −1 dBTP |
| `podcast-spoken` | Podcast / spoken-word audio | −16 LUFS | 12 LU | −1 dBTP |
| `cinema-theatrical` | Cinema / theatrical | −27 LUFS | 20 LU | −2 dBTP |

−14 LUFS is the `streaming-social` profile — one profile among several,
not the default for all destinations. EBU R 128 v5.0 (Nov 2023)
specifies −23 LUFS average programme loudness for broadcast; that is
why a single target must never be hard-coded for all destinations.

Re-check platform requirements before a release; do not assume any one
target fits every destination. Tolerances: ±1 LU for streaming,
broadcast and podcast; ±2 LU for cinema.

## Where the old rule lived

The universal target appeared in `production-systems` B14,
`voice-consistency`, `humanized-production`, `command-authority` §7 and
`docs/02`. All of those now point to the named delivery profile. The
mix rules themselves are unchanged: dialogue carries ~60% of attention,
music and sound effects duck under dialogue and never compete.
