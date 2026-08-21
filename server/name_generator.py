"""Names for player accounts.

A player gets a name the moment they first play, without being asked for one.
The name is the account's only identity, and it is what a leaderboard shows,
so it has to be unique.

The generator here only proposes a name. Uniqueness is settled by the database,
because two players can ask for the same name at the same moment and only a
unique index can decide between them.
"""

import random
import re

MIN_NAME_LENGTH = 3
MAX_NAME_LENGTH = 20

# Letters, digits, underscore and hyphen. No spaces: a name with a space in it
# reads as two names in a leaderboard row.
_ALLOWED = re.compile(r"^[A-Za-z0-9_-]+$")

ADJECTIVES = [
    "Blocking",
    "Brittle",
    "Cold",
    "Cursed",
    "Dangling",
    "Deep",
    "Eager",
    "Fatal",
    "Flaky",
    "Frozen",
    "Ghosted",
    "Greedy",
    "Hidden",
    "Idle",
    "Lazy",
    "Leaky",
    "Muted",
    "Nested",
    "Noisy",
    "Orphan",
    "Pending",
    "Phantom",
    "Quiet",
    "Raw",
    "Rogue",
    "Rusty",
    "Shallow",
    "Silent",
    "Sparse",
    "Stale",
    "Stray",
    "Tangled",
    "Thin",
    "Unbound",
    "Vacant",
    "Vague",
    "Verbose",
    "Wired",
    "Zombie",
]

NOUNS = [
    "Beacon",
    "Buffer",
    "Cache",
    "Checksum",
    "Cluster",
    "Cron",
    "Cursor",
    "Daemon",
    "Dump",
    "Fuse",
    "Gateway",
    "Handler",
    "Heap",
    "Index",
    "Kernel",
    "Latch",
    "Lambda",
    "Monitor",
    "Mutex",
    "Node",
    "Packet",
    "Payload",
    "Pointer",
    "Probe",
    "Queue",
    "Rack",
    "Relay",
    "Router",
    "Runtime",
    "Scheduler",
    "Sensor",
    "Shard",
    "Signal",
    "Socket",
    "Spool",
    "Stack",
    "Symlink",
    "Thread",
    "Ticket",
    "Token",
    "Trace",
    "Tunnel",
    "Vector",
    "Worker",
]


def random_name() -> str:
    """A proposed name, such as `SilentPacket`. It may already be taken."""
    return random.choice(ADJECTIVES) + random.choice(NOUNS)


def name_with_suffix(base: str, suffix: int) -> str:
    """`base` with a number on the end, trimmed to fit the length limit.

    Used when the plain combinations are exhausted or unlucky.
    """
    tail = str(suffix)
    keep = MAX_NAME_LENGTH - len(tail)
    return base[:keep] + tail


def name_error(name: str) -> str | None:
    """Why `name` cannot be used, or None if it can be.

    The message is shown to the player as it is, so write it for them.
    """
    if len(name) < MIN_NAME_LENGTH:
        return f"A name needs at least {MIN_NAME_LENGTH} characters."
    if len(name) > MAX_NAME_LENGTH:
        return f"A name can be at most {MAX_NAME_LENGTH} characters."
    if not _ALLOWED.match(name):
        return "A name can hold only letters, digits, - and _."
    return None
