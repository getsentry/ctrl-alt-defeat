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
          "maxdamage", "stamina", "accuracy", "cooldown", "sockets", "inshop")


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

        rarity = (rec.get("rarity") or "").lower()
        inshop = rec.get("inshop")
        prose_hidden = bool(re.search(
            r"cannot be found in the shop|not available in the shop", text, re.I))
        prose_gate = re.search(
            r"in the shop (?:once|when|while) \[\[([^|\]]+)(?:\|[^\]]*)?\]\]",
            text, re.I)
        sub = re.search(r"^\|subclassname=(.+)$", text, re.M)
        if sub or "[[Category:Subclass]]" in text:
            rec["shop"] = "subclass"
            if sub:
                rec["subclass"] = sub.group(1).strip()
        elif inshop and inshop.lower() not in ("yes", "no", "true", "false"):
            rec["shop"] = "gated"
            rec["shop_needs"] = inshop
        elif prose_gate:
            rec["shop"] = "gated"
            rec["shop_needs"] = prose_gate.group(1).strip()
        elif rarity == "unique":
            rec["shop"] = "treasure"
        elif rarity == "godly" or prose_hidden or inshop in ("No", "no", "false"):
            rec["shop"] = "recipe_only"
        else:
            rec["shop"] = "normal"
        items[rec["name"]] = rec
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
