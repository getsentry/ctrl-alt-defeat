"""
A name for an opponent that is not a person.

"AI Opponent (Round 4)" tells the player two things they did not need to know
and nothing they did. These racks were built by something playing the game, so
they are named like the handles a player would pick -- built from the same
world the items come from, because a Sentry-themed autobattler full of null
blades and stack smashers should not field opponents called Bot_4471.

The name is DERIVED FROM THE BUILD, not drawn at random, so the same rack is
always the same opponent. A player who meets one twice sees the same handle,
and one who screenshots a defeat can be told who beat them.
"""

from __future__ import annotations

import hashlib

_FIRST = (
    "null", "stack", "cache", "heap", "async", "lazy", "eager", "stale",
    "cold", "warm", "dark", "prod", "edge", "core", "root", "proxy",
    "quantum", "vector", "atomic", "silent", "rogue", "phantom", "crimson",
    "amber", "zero", "prime", "hyper", "micro", "deep", "raw", "brittle",
    "graceful", "eventual", "idle", "pinned", "sharded",
)

_SECOND = (
    "pointer", "overflow", "trace", "daemon", "kernel", "packet", "socket",
    "thread", "cursor", "buffer", "cluster", "gateway", "beacon", "monolith",
    "sentinel", "regex", "commit", "rollback", "handshake", "heartbeat",
    "timeout", "retry", "fallback", "canary", "sunset", "cascade", "drift",
    "spike", "burst", "leak", "loop", "fork", "merge", "patch", "hotfix",
)

_SUFFIX = ("", "", "", "", "_x", "_ii", "99", "42", "_dev", "_ops", "77", "_v2")


def name_for(build: dict) -> str:
    """A stable handle for a stored build.

    Hashed from the rack itself, so it survives a reshuffle of the file and
    never needs storing. Two builds that collide simply share a handle, which
    real players do too.
    """
    seed = hashlib.blake2b(
        repr((build.get("i"), build.get("c"), build.get("e"))).encode(),
        digest_size=8,
    ).digest()
    n = int.from_bytes(seed, "big")

    first = _FIRST[n % len(_FIRST)]
    second = _SECOND[(n // len(_FIRST)) % len(_SECOND)]
    suffix = _SUFFIX[(n // (len(_FIRST) * len(_SECOND))) % len(_SUFFIX)]
    return f"{first}_{second}{suffix}"
