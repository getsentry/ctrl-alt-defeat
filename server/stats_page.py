"""The stats as a page, in the game's own colours.

One file, no build step, no assets: the server that already deploys on every
push serves it, so there is nothing else to keep running. It refreshes itself
every half minute, because the question it answers -- is anybody playing right
now -- is one somebody leaves open on a second screen.

The numbers come from stats.py. Nothing is worked out here.
"""

from html import escape

from stats import ROUNDS, Stats

#: The game's own palette, from the client's Slab and Keycap.
INK = "#f2e3c4"
GROUND = "#0e0a14"
PANEL = "#1c1428"
EDGE = "#463859"
MUTED = "#8a789e"
MAGENTA = "#ff3dbe"
MINT = "#60f6a3"

#: How often the page asks again, in seconds.
REFRESH = 30


def _tile(caption: str, value, note: str = "", colour: str = INK) -> str:
    under = f'<span class="note">{escape(note)}</span>' if note else ""
    return (
        f'<div class="tile"><span class="caption">{escape(caption)}</span>'
        f'<b style="color:{colour}">{value}</b>{under}</div>'
    )


def _bars(reached: list) -> str:
    """How far runs got, as a row per round.

    Every round is drawn whether or not a run reached it: the gaps are the
    point, and a chart that skips them reads as though nobody stopped there.
    """
    if not reached:
        return '<p class="none">No runs yet.</p>'

    counts = {row["round"]: row["runs"] for row in reached}
    most = max(counts.values())
    rows = []
    for number in range(1, max(ROUNDS, max(counts)) + 1):
        runs = counts.get(number, 0)
        width = 0 if most == 0 else round(runs / most * 100)
        colour = MINT if number >= ROUNDS else MAGENTA
        rows.append(
            f'<div class="bar"><span class="round">{number}</span>'
            f'<span class="track"><span class="fill" style="width:{width}%;'
            f'background:{colour}"></span></span>'
            f'<span class="runs">{runs}</span></div>'
        )
    return "".join(rows)


def render(stats: Stats, token: str = "") -> str:
    """The whole page, with the numbers already in it.

    Rendered rather than fetched: the page arrives complete, so it says
    something even if the browser it opens in can call nothing.
    """
    players = stats.players
    runs = stats.runs
    battles = stats.battles
    query = f"?token={escape(token)}" if token else ""

    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="{REFRESH}">
<title>Ctrl Alt Defeat &mdash; who is playing</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{
    margin: 0; padding: 40px 28px 64px; background: {GROUND}; color: {INK};
    font: 16px/1.5 "IBM Plex Sans", ui-sans-serif, system-ui, sans-serif;
  }}
  .wrap {{ max-width: 980px; margin: 0 auto; }}
  h1 {{ font-size: 30px; margin: 0 0 4px; letter-spacing: -.01em; }}
  h2 {{
    font-size: 12px; text-transform: uppercase; letter-spacing: .16em;
    color: {MUTED}; margin: 36px 0 12px; font-weight: 600;
  }}
  .asked {{ color: {MUTED}; margin: 0 0 8px; font-size: 13px; }}
  .grid {{
    display: grid; gap: 12px;
    grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
  }}
  .tile {{
    background: {PANEL}; border: 1px solid {EDGE}; border-radius: 12px;
    padding: 14px 16px; display: flex; flex-direction: column; gap: 2px;
  }}
  .caption {{
    font-size: 11px; text-transform: uppercase; letter-spacing: .1em;
    color: {MUTED};
  }}
  .tile b {{
    font-size: 30px; font-weight: 600; font-variant-numeric: tabular-nums;
  }}
  .note {{ font-size: 12px; color: {MUTED}; }}
  .bar {{ display: flex; align-items: center; gap: 10px; margin: 3px 0; }}
  .round {{
    width: 26px; text-align: right; color: {MUTED}; font-size: 13px;
    font-variant-numeric: tabular-nums;
  }}
  .track {{
    flex: 1; height: 14px; background: {PANEL}; border: 1px solid {EDGE};
    border-radius: 7px; overflow: hidden;
  }}
  .fill {{ display: block; height: 100%; }}
  .runs {{
    width: 44px; font-size: 13px; font-variant-numeric: tabular-nums;
    color: {MUTED};
  }}
  .none {{ color: {MUTED}; }}
  footer {{ margin-top: 40px; color: {MUTED}; font-size: 12px; }}
  a {{ color: {MAGENTA}; }}
</style>
</head><body><div class="wrap">
  <h1>Who is playing</h1>
  <p class="asked">Taken {escape(stats.taken_at)} &middot; refreshes every
     {REFRESH}s &middot; <a href="/stats{query}">the same numbers as JSON</a></p>

  <h2>People</h2>
  <div class="grid">
    {_tile("Playing right now", players.get("playing_this_hour", 0),
           "moved a run in the last hour", MINT)}
    {_tile("Played today", players.get("playing_this_day", 0))}
    {_tile("Came back", players.get("returned_this_day", 0),
           "played today, signed up before today", MAGENTA)}
    {_tile("Everyone, ever", players.get("total", 0))}
    {_tile("New today", players.get("new_this_day", 0))}
    {_tile("New this week", players.get("new_this_week", 0))}
  </div>

  <h2>Runs</h2>
  <div class="grid">
    {_tile("Begun today", runs.get("begun_this_day", 0))}
    {_tile("Begun this week", runs.get("begun_this_week", 0))}
    {_tile("In hand", runs.get("in_hand", 0), "started, not yet paid out")}
    {_tile("Played to the end", runs.get("played_to_the_end", 0))}
    {_tile("Standing at a win", runs.get("won", 0),
           f"{ROUNDS} wins banked", MINT)}
    {_tile("Battles today", battles.get("fought_this_day", 0))}
  </div>

  <h2>Where each player's latest run stands</h2>
  {_bars(stats.reached)}

  <footer>An account is made when somebody presses New Game, and it is kept in
  their browser, so these are people rather than page loads. A player has one
  session row, reset when they start again, so runs are counted where a
  finished one is banked &mdash; on the player. Counts only: no names are read
  to build this page.</footer>
</div></body></html>"""
