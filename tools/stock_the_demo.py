#!/usr/bin/env python3
"""Set a running demo up so the auras can be looked at.

    python tools/stock_the_demo.py            # both zones, one run
    python tools/stock_the_demo.py --port 8090

Every one of the twenty-five items that projects an aura the engine acts on is
`in_shop: false`, so no seed will ever put one in front of a player. This says
what is for sale instead, and stands the items an aura can act on on the rack
so there is something for it to land on.

Run it after starting a game in the demo. It finds the session that was touched
last, which is the one you are playing, and stocks that. Run it again whenever
you want the set back -- the shelf is rolled again at every round.

Both hooks are TEST_MODE only, so a server started any other way refuses them.

What it sets up:

    on the shelf   Cube Garbo   8g   2x2, star left and right, diamond above
                                     and below, both acting on anything
                   Web Crawler  4g   1x2, a six-square star acting on pets and
                                     scripts only

    on the rack    Hot Path          a script: the narrowed star fills on it
                   Nope Stamp        another script, two squares tall, so one
                                     filled marker covers both of its squares
                   Ping of Death     a weapon: the narrowed star passes over it
                   Cron Cake         a third script, off to one side

Thirteen gold buys both shelf items with a gold left over. Pick one up and the
zone follows the pointer, so you can see what a square would be worth before
letting go.
"""

import argparse
import json
import urllib.error
import urllib.request

import asyncio
import asyncpg

# What goes where. Slugs, because that is what the hooks take.
FOR_SALE = ["cubert", "data_crawler"]
ON_THE_RACK = [
    ("cache_optimizer", [2, 3]),   # Hot Path, a script
    ("firewall_script", [3, 3]),   # Nope Stamp, a script two squares tall
    ("ping_flood", [6, 3]),        # Ping of Death, a weapon and no kind of script
    ("cupcake", [7, 3]),           # Cron Cake, another script
]


async def _newest_session() -> str:
    """The player whose session was touched last, which is the one being played."""
    conn = await asyncpg.connect(
        host="localhost", port=5432, database="autobattler",
        user="postgres", password="",
    )
    try:
        row = await conn.fetchrow(
            "SELECT player_id, player_name, round, updated_at FROM game_sessions "
            "ORDER BY updated_at DESC LIMIT 1"
        )
    finally:
        await conn.close()

    if row is None:
        raise SystemExit("No session at all. Start a game in the demo first.")
    print("Playing as %s (player %s), round %s"
          % (row["player_name"], row["player_id"], row["round"]))
    return row["player_id"]


def _post(port: int, path: str, body: dict) -> dict:
    request = urllib.request.Request(
        "http://localhost:%d%s" % (port, path),
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request) as answer:
            return json.loads(answer.read())
    except urllib.error.HTTPError as refused:
        raise SystemExit(
            "%s said %d: %s\n"
            "A server not started in TEST_MODE has no test hooks; run_demo.sh "
            "starts one that has." % (path, refused.code, refused.read().decode())
        ) from None
    except urllib.error.URLError:
        raise SystemExit(
            "Nothing is answering on port %d. Start the demo first." % port
        ) from None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8090,
                        help="where the demo server is listening")
    port = parser.parse_args().port

    player_id = asyncio.run(_newest_session())

    shop = _post(port, "/test/shop", {"player_id": player_id, "items": FOR_SALE})
    rack = _post(port, "/test/rack", {
        "player_id": player_id,
        "items": [{"item_type": slug, "position": at} for slug, at in ON_THE_RACK],
    })

    print("\nOn the shelf:")
    for item in shop["current_shop"]:
        zones = ", ".join(sorted(item["aura"])) or "no zone the engine acts on"
        print("   %-14s %2dg  %s" % (item["name"], item["price"], zones))
    print("\nOn the rack:")
    for item in rack["inventory_grid"]:
        print("   %-14s at %s  (%s)"
              % (item["name"], item["position"], item["category"]))
    print("\nRe-roll the shop and this goes; run it again to get it back.")


if __name__ == "__main__":
    main()
