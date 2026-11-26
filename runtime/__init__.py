"""Consistency Frame P1 — trusted local application session runtime.

This package is the first real runtime component of Consistency Frame
(CF-WO-P1-001): a trusted LOCAL application session and authorization
boundary. It is deliberately small and standard-library only:

- :mod:`runtime.local_session` — first-run installation identity
  (stable opaque owner/workspace IDs stored outside the repository)
  and the process-bound :class:`LocalSession` (start / validate /
  close, exact-type + object-identity issuance verification).
- :mod:`runtime.authorization` — the authorization bridge: every
  decision takes actor identity from a verified session and delegates
  to the P0 policy in ``scripts/asset_policy.py``; it also issues
  trusted private-voice export contexts through the P0 factory.
- :mod:`runtime.skill_router` — the deterministic runtime skill
  router and workflow plan builder (CF-WO-P1-002): resolves skills
  and builds deterministic workflow plans from structured requests
  using only the compiled routing catalog
  (``registry/routing-catalog.json``). Standard-library only; it
  never reads a private project asset, never contacts a provider,
  never generates media, and never persists anything. See
  ``docs/runtime/SKILL_ROUTING_RUNTIME.md`` for the routing contract.

This is a local application runtime, not a cryptographic identity
provider and not a server: it operates inside the security boundary
of the current operating-system user and claims no protection
against another process or attacker already controlling that same
OS account. See ``docs/runtime/LOCAL_SESSION_AND_TRUST_BOUNDARY.md``
for exactly what the boundary guarantees and what it does not.
"""

__all__ = ["local_session", "authorization", "skill_router"]
