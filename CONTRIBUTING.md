# Contributing to Consistency Frame

Thank you for helping make this system better. Consistency Frame exists
so that characters stay the same and videos feel human — contributions
must protect that, not weaken it.

## Rules for contributors

1. **Keep the consistency and safety rules intact.** Never change a rule
   that protects character identity, voice consistency, child safety,
   consent, or real-person safeguards in a way that weakens it. If a
   change touches those rules, explain in the pull request why it is
   safe, and how the old protection is preserved.
2. **Describe every change.** Every pull request states what changed,
   why, and which systems it touches. A change without a description
   will not be merged.
3. **Test before submitting.** Run the system end to end with a real
   character and a real generation wherever the change affects
   generation: register a character, generate a scene, check the face,
   the voice, and the QC checklist. Say in the pull request what you
   tested and what you saw. Untested generation changes will not be
   merged.
4. **Keep licence and attribution.** This project's own work is
   Apache-2.0. VoiceStudio and OpenMontage are AGPL-3.0 and stay that
   way; the OmniVoice model is CC-BY-NC (noncommercial). Do not
   re-licence, strip, or hide anyone's licence, and do not
   reverse-engineer anything to change its licence. New files you add
   are under Apache-2.0 unless you say otherwise in the pull request.
5. **Keep the skills as the source of truth.** If a rule changes, change
   it in `skills/` first, then update `docs/` and `README.md` to match.
   `AGENTS.md`, `CLAUDE.md`, and `GEMINI.md` stay thin pointers — do not
   duplicate skill content into them.
6. **One change, one pull request.** Small, reviewable pull requests
   merge faster than large ones. A large change should be split, or
   discussed in an issue first.
7. **No character data, no secrets.** Never commit reference images,
   voice recordings, prompt blocks for real people, API keys, tokens,
   or credentials. Character data is private by default and lives in a
   separate private overlay — never in this public repo.

## How to contribute

1. Fork the repo and create a branch from `main`.
2. Make your change, following the rules above.
3. Update `CHANGELOG.md` under an "Unreleased" section.
4. Open a pull request describing the change and the tests you ran.

## Release versioning

Releases are numbered like `2.0`, `2.1`, `3.0`. Small updates bump the
minor number; big breaking changes bump the major number. Every release
updates `CHANGELOG.md`.

## Code of conduct

Be kind, be direct, and assume good faith. Disagree about the work, not
about the person. Harassment, hate speech, and spam are not welcome.
