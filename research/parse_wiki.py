#!/usr/bin/env python3
"""Parse the committed wiki corpus (research/wiki_pages/*.wikitext) into one
JSON dataset per item: stats, effects, grid, recipe, and shop availability.

The corpus is the durable copy of every Sentaur-relevant Backpack Battles
page; reprocess it with this script instead of fetching anything.

Shop availability decodes into one of:
  normal      - can appear in the shop
  gated       - in the shop only while holding `shop_needs` (may also craft)
  recipe_only - never in the shop; Godly items and pages that say so
  treasure    - Unique rarity; found as treasure, not sold
Subclass items additionally carry `subclass`.

Usage: python3 research/parse_wiki.py > /tmp/parsed.json  (or import parse())
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PAGES = os.path.join(HERE, "wiki_pages")

FIELDS = ("name", "rarity", "icontype", "type", "cost", "class", "mindamage",
          "maxdamage", "stamina", "accuracy", "cooldown", "sockets", "inshop",
          "skillround", "addshop", "subclassname")


def _params(block):
    """Template parameters from one {{...}} block. Multiline values (effect,
    grid) run until the next |param= line."""
    out = {}
    key = None
    for line in block.splitlines():
        m = re.match(r"^\|(\w+)=(.*)$", line)
        if m:
            key = m.group(1)
            out[key] = m.group(2).strip()
        elif key and not line.startswith("{{") and not line.startswith("}}"):
            out[key] = (out[key] + "\n" + line).strip()
    return out


def _blocks(text, name):
    """Top-level {{name ...}} template blocks, brace-balanced."""
    for m in re.finditer(r"\{\{" + name, text):
        depth, i = 0, m.start()
        for j in range(m.start(), len(text)):
            if text[j:j + 2] == "{{":
                depth += 1
            if text[j:j + 2] == "}}":
                depth -= 1
                if depth == 0:
                    yield text[i:j + 2]
                    break


def _effects(raw):
    """Effect text as a list of lines, wiki markup unwrapped except the
    {{icon/...}} templates, which the catalogue keeps."""
    if not raw:
        return []
    raw = re.sub(r"\[\[([^|\]]*)\|([^\]]*)\]\]", r"\2", raw)
    raw = re.sub(r"\[\[([^\]]*)\]\]", r"\1", raw)
    raw = raw.replace("'''", "")
    lines = [l.lstrip("* ").strip() for l in raw.splitlines()]
    return [l for l in lines if l]


#: Two items the template names outright rather than deriving.
NAMED_OUT = ("Star of Courage", "Sack of Surprises")


def _in_shop(rec):
    """What the wiki's own "In shop" row would say, as one word.

    Template:Item_infobox decides it in this order, and so does this:

    1. a subclass item                       -> `subclass`
    2. a skill, offered on round 3 or 10     -> `skill`
    3. something else adds it to the shop    -> `gated`
    4. a recipe makes it                     -> `recipe_only`
    5. Star of Courage, Sack of Surprises    -> `recipe_only`
    6. a Chess Piece                         -> `gated`, on the Chess Board
    7. a Puzzlebag                           -> `gated`
    8. a Bag belonging to a class            -> `recipe_only`
    9. anything else                         -> `normal`

    Rarity is not one of the steps. A Unique item is sold like any other
    unless one of these says otherwise.
    """
    name = rec["name"]
    if rec.get("subclass"):
        return "subclass"
    if rec.get("skillround"):
        return "skill"
    if rec.get("shop_needs"):
        return "gated"
    if rec.get("recipes") or any(out in name for out in NAMED_OUT):
        return "recipe_only"
    kind = (rec.get("type") or "")
    if "Chess Piece" in kind:
        return "gated"
    if "Bag" in kind:
        if "Puzzlebag" in name:
            return "gated"
        # A bag of a class is that class's, and the shop does not offer it.
        return "recipe_only" if rec.get("class") else "normal"
    return "normal"


def parse():
    items = {}
    for fn in sorted(os.listdir(PAGES)):
        if not fn.endswith(".wikitext"):
            continue
        text = open(os.path.join(PAGES, fn)).read()
        rec = {"file": fn}
        for block in _blocks(text, "Item infobox"):
            p = _params(block)
            for f in FIELDS:
                rec[f] = p.get(f) or None
            rec["effects"] = _effects(p.get("effect", ""))
            grid = p.get("grid") or ""
            rec["grid"] = [l for l in grid.splitlines() if l.strip()]
            break
        if "name" not in rec or not rec["name"]:
            rec["name"] = fn[:-len(".wikitext")].replace("_", " ")
        recipes = []
        for block in _blocks(text, "Recipe infobox"):
            p = _params(block)
            if p.get("recipename", rec["name"]) != rec["name"]:
                continue  # a recipe this item is an ingredient of, not its own
            # Some recipe slots name an item class rather than an item: the
            # wiki's Fire page is a listing of every icontype-fire item, and
            # "catalysts=Fire" means any of them.
            CLASS_PAGES = {"Fire": "class:fire"}

            def names(field):
                raw = re.sub(r"\[\[([^|\]]*)(\|[^\]]*)?\]\]", r"\1",
                             p.get(field, ""))
                return [CLASS_PAGES.get(i.strip(), i.strip())
                        for i in raw.split(",") if i.strip()]
            rec_entry = {
                "ingredients": names("ingredients"),
                "cost": p.get("requirementcost") or None,
            }
            # A catalyst joins the combination and survives it (GDD 5.3).
            if names("catalysts"):
                rec_entry["catalysts"] = names("catalysts")
            recipes.append(rec_entry)
        rec["recipes"] = recipes

        if rec.get("subclassname"):
            rec["subclass"] = rec["subclassname"].strip()
        items[rec["name"]] = rec

    # A gate is written on the item that opens it, not on the item behind it:
    # Box of Riches says `addshop=Amethyst, Emerald, Ruby, Sapphire, Topaz`.
    # So it can only be resolved once every page has been read.
    for opener in list(items.values()):
        for opened in (opener.get("addshop") or "").split(","):
            opened = opened.strip()
            if opened and opened in items:
                items[opened]["shop_needs"] = opener["name"]

    # The wiki renders an "In shop" row that is written on no page:
    # Template:Item_infobox works it out. This is what it does, in its own
    # order -- copied from the template source rather than guessed at, because
    # guessing got it wrong twice. Rarity plays no part (Tim is Unique and
    # sold) and the opening sentence is not evidence (Torch's says "available
    # in the shop" and its row says No).
    for rec in items.values():
        rec["shop"] = _in_shop(rec)
    return items


if __name__ == "__main__":
    data = parse()
    json.dump(data, sys.stdout, indent=1)
    counts = {}
    for r in data.values():
        counts[r["shop"]] = counts.get(r["shop"], 0) + 1
    print(f"\n{len(data)} items parsed; shop states: {counts}; "
          f"with recipes: {sum(1 for r in data.values() if r['recipes'])}",
          file=sys.stderr)
