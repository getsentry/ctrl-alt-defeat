"""
Drive the REAL server code: no HTTP, no auth, no Postgres, no disk.

WHY THIS EXISTS
---------------
The trainer used to talk to `rules.py`, a hand-copy of the rules that live in
main.py's request handlers. That copy drifted and broke within two days of a
refactor (`PlacedItem` became `BattleItem`). A copy can only ever detect
divergence; importing the real thing prevents it structurally.

HOW IT WORKS -- three facts, in order of how surprising they are
----------------------------------------------------------------
1. A FastAPI handler is a plain async function. `Depends(get_current_user)` is
   only a DEFAULT ARGUMENT, so passing `current_user=` yourself means the
   dependency injection never runs. No HTTP, no token, no auth.

2. Every storage call funnels through ONE seam, `db_manager.get_session()`
   (database.py:245). Reassigning `db_manager.engine` and
   `.async_session_maker` from out here points the whole server at a database
   of our choosing. NOTHING IN server/ IS MODIFIED.

3. `sqlite+aiosqlite:///:memory:` never touches the disk -- but it needs
   StaticPool. With the default pool every new connection opens its OWN blank
   in-memory database and the tables silently vanish between calls.

WHY THE SESSION IS CACHED
-------------------------
Measured cost of one battle through the real handler, before caching:

    update_session      (db write)   1.10 ms   29%
    get_session         (db read)    0.68 ms   18%
    save_battle_history (db write)   0.44 ms   12%
    BattleSimulator     (the game)   0.39 ms   10%   <-- the only real work
    find_opponent       (db read)    0.33 ms    9%

68% storage, 10% game. A training run is one player's private state that
nothing else reads, and the replay log is never replayed, so the durable copy
buys the trainer nothing. CachedSessionManager keeps the live session in a
dict and drops the battle history on the floor.

The game rules are untouched. Only where the state is kept changes.

WHAT A BOT CAN DO THROUGH HERE
------------------------------
    buy                purchase(who, item_id, position)
    buy to storage     purchase(who, item_id, to_storage=True)
    sell               sell(who, item_id)
    move / repack      move(who, item_id, [x, y])
    move to storage    move(who, item_id, "storage")
    reroll the shop    refresh_shop(who)
    fight              battle(who, seed)

ROTATION IS NOT IN THAT LIST, and not because of this module. The data model
carries it (`Item.placed_at(position, rotation)`, and BattleSimulator reads
`item.rotation` at main.py:493), but NO endpoint accepts one: PurchaseRequest
takes item_id/target_position/to_storage, and MoveItemRequest takes
item_id/to_location. So every item is placed at Rotation.NONE, by a bot or by
a player. Rotation is modelled and unreachable.
"""

from __future__ import annotations

import asyncio

import contextlib
import logging
import os
import sys
from pathlib import Path

os.environ.setdefault("TEST_MODE", "true")
os.environ.setdefault("SKIP_MIGRATION_CHECK", "true")

_SERVER = str(Path(__file__).resolve().parent.parent / "server")
if _SERVER not in sys.path:
    sys.path.insert(0, _SERVER)


@contextlib.contextmanager
def _in_server_dir():
    """config_loader builds its catalogue AT IMPORT TIME from a CWD-RELATIVE
    "data" path (config_loader.py:32 and the load_all() at the module bottom).

    Import it from anywhere but server/ and you get an EMPTY catalogue: no
    items, empty shops, and bots that buy nothing. It does not raise -- it
    prints "Warning: Items directory not found" and carries on."""
    prev = os.getcwd()
    os.chdir(_SERVER)
    try:
        yield
    finally:
        os.chdir(prev)


# Load the catalogue HERE, at import time, under the chdir.
#
# It must happen before anything else touches a server module, because
# config_loader is a module-level singleton built once from a cwd-relative
# path: whoever imports it first decides whether the catalogue is full or
# empty, for the whole process.
#
# This bit us through multiprocessing. A spawned worker inherits sys.path, so
# a top-level `from containers import GRID_SIZE` in another module SUCCEEDED
# there while failing in the parent -- pulling in config_loader from the wrong
# directory, yielding an empty catalogue, killing the pool initializer, and
# leaving Pool respawning workers forever. Importing this module is now the
# one way in, so order stops mattering.
with _in_server_dir():
    from config_loader import config_loader as CATALOGUE  # noqa: E402

if not CATALOGUE.items:
    raise RuntimeError(
        f"Item catalogue is empty; expected data under {_SERVER}/data. "
        "config_loader logs and continues on a bad file (config_loader.py:92), "
        "so a JSON typo looks exactly like this."
    )


class CachedSessionManager:
    """Delegates to the real SessionManager, but keeps the session in memory.

    Deliberately a WRAPPER rather than a reimplementation. `create_session` is
    126 lines of real setup -- initial gold, starting containers, the first
    shop roll -- and copying it would recreate the exact drift problem this
    module exists to remove. So creation goes through the real code once per
    run, and only the per-call reads and writes are served from the cache.
    """

    def __init__(self, real):
        self._real = real
        self._live: dict[str, object] = {}
        self.history_writes_skipped = 0

    async def create_session(self, player_id, game_seed=None, player_name=None):
        session = await self._real.create_session(player_id, game_seed, player_name)
        self._live[str(player_id)] = session
        return session

    async def get_session(self, player_id):
        return self._live.get(str(player_id))

    async def update_session(self, session) -> bool:
        self._live[str(session.player_id)] = session
        return True

    async def delete_session(self, player_id) -> bool:
        return self._live.pop(str(player_id), None) is not None

    async def save_battle_history(self, *args, **kwargs) -> None:
        # Training never replays a battle. This was 12% of every battle.
        self.history_writes_skipped += 1

    async def get_battle_history(self, player_id, limit: int = 10) -> list:
        return []

    def __getattr__(self, name):
        # Anything not overridden above stays the real implementation.
        return getattr(self._real, name)


class Harness:
    """One process, one in-memory database, one event loop.

    The loop is kept alive on purpose: asyncio.run() builds and tears down a
    fresh loop per call, which costs more than the work being done here.

    ALWAYS CLOSE IT. Use it as a context manager:

        with Harness() as h:
            ...

    aiosqlite runs its connection on a NON-DAEMON thread, so a process holding
    an undisposed engine never exits. It finishes all the work, prints all the
    output, and then sits at interpreter shutdown forever. That failure looks
    exactly like a slow harness and is not one -- it cost hours in this repo
    before it was pinned down.

    atexit CANNOT rescue a caller who forgets: CPython joins non-daemon
    threads BEFORE it runs atexit handlers, so the handler never executes.
    close() has to be called while the program is still running.
    """

    def __init__(self, quiet: bool = True):
        if quiet:
            # TEST_MODE turns on DEBUG logging for everything, and aiosqlite
            # logs every statement. That alone dominates the runtime.
            logging.disable(logging.CRITICAL)

        self._loop = asyncio.new_event_loop()
        self._engine = None
        self.server = None
        self.sessions = None
        self.catalogue = None
        self.opponent_source = None   # see _install_opponent_hook
        self.opponents_served = 0
        self._user_ids: dict[str, int] = {}
        try:
            self._loop.run_until_complete(self._boot())
        except BaseException:
            self.close()   # a failed boot must exit, not hang. See below.
            raise

    # ---------------------------------------------------------------- boot

    async def _boot(self):
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool

        import database
        from models import Base

        self._engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            poolclass=StaticPool,   # REQUIRED: see the module docstring
            connect_args={"check_same_thread": False},
        )
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        dm = database.db_manager
        dm.engine = self._engine
        dm.async_session_maker = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        dm._initialized = True   # so it never tries to reach Postgres

        with _in_server_dir():
            import main as server

        config_loader = CATALOGUE
        self.server = server
        self.sessions = CachedSessionManager(server.session_manager)
        server.session_manager = self.sessions
        self._install_opponent_hook()

        self.catalogue = config_loader

    # ----------------------------------------------------------- opponents

    def _install_opponent_hook(self):
        """Let the trainer choose who the bot fights.

        Self-play needs control of the opponent -- that is the whole mechanism.
        The battle handler picks one itself via MatchmakingService.find_opponent
        (main.py:530), so replacing that ONE method hands the choice to us while
        every other line of the handler runs untouched. Still no server change.

        Set `harness.opponent_source` to a callable taking (round_number) and
        returning a build dict, or None to fall back to the server's own AI.
        """
        from matchmaking import MatchmakingService

        harness = self
        real = MatchmakingService.find_opponent

        async def find_opponent(self, *args, **kwargs):
            if harness.opponent_source is None:
                return await real(self, *args, **kwargs)
            build = harness.opponent_source(kwargs.get("round_number", 1))
            harness.opponents_served += 1 if build else 0
            return build

        MatchmakingService.find_opponent = find_opponent

    # ---------------------------------------------------------------- users

    def _run(self, coro):
        return self._loop.run_until_complete(coro)

    def user(self, name: str = "bot"):
        """A TokenData for `name`, creating the row on first use."""
        from auth import TokenData

        if name not in self._user_ids:
            self._user_ids[name] = self._run(self._make_user(name))
        return TokenData(user_id=self._user_ids[name], username=name,
                         account_type="guest")

    async def _make_user(self, name: str) -> int:
        import database
        from models import User

        async with database.db_manager.get_session() as db:
            u = User(username=name, account_type="guest")
            db.add(u)
            await db.flush()
            return u.id

    # ------------------------------------------------------------- actions
    #
    # Thin sync wrappers over the real handlers. They add no rules of their
    # own -- every one is a direct call into main.py.

    def start_run(self, who, seed: int):
        from schemas import StartSessionRequest

        return self._run(self.server.start_session(
            StartSessionRequest(seed=seed), current_user=who)).session

    def session(self, who):
        return self._run(self.server.session_manager.get_session(str(who.user_id)))

    def purchase(self, who, item_id: str, position=None, to_storage: bool = False):
        from schemas import PurchaseRequest

        return self._run(self.server.purchase_item(
            PurchaseRequest(item_id=item_id,
                            target_position=list(position) if position else None,
                            to_storage=to_storage),
            current_user=who))

    def sell(self, who, item_id: str):
        from schemas import SellRequest

        return self._run(self.server.sell_item(
            SellRequest(item_id=item_id), current_user=who))

    def move(self, who, item_id: str, to):
        """Move a placed item. `to` is a square [x, y] or the string "storage".

        This is how a bot repacks: to free a spot for a better item it must
        move what is already there. NOTE there is no rotation here, because
        the server offers no way to set one -- see the ROTATION note below.
        """
        from schemas import MoveItemRequest

        return self._run(self.server.move_item(
            MoveItemRequest(item_id=item_id,
                            to_location=to if isinstance(to, str) else list(to)),
            current_user=who))

    def refresh_shop(self, who):
        return self._run(self.server.refresh_shop(current_user=who))

    def battle(self, who, seed: int):
        from schemas import SimpleBattleRequest

        return self._run(self.server.simulate_battle(
            SimpleBattleRequest(seed=seed), current_user=who))

    def close(self):
        """Safe to call twice, and on a half-built harness. See __init__."""
        try:
            if self._engine is not None and not self._loop.is_closed():
                self._loop.run_until_complete(self._engine.dispose())
                self._engine = None
        finally:
            if not self._loop.is_closed():
                self._loop.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False
