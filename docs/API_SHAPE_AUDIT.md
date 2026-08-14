# API Shape Audit

Date: 2026-08-14. Scope: `server/` and `client/` at commit `c0feed2`.

## 1. Summary

The API returns **7 different forms of an item**, **5 different forms of a container**, and
**3 different forms of a position**. No endpoint agrees fully with another. The client
absorbs this with 163 defensive lookups and 32 explicit type branches.

The cause is clear. The server has one enrichment function, `serialize_inventory_item()`,
that adds tooltip fields to a minimal stored dict. Three endpoints call it. Two do not.
One endpoint has no response model at all. The stored dict itself has only 6 keys, because
`/purchase/item` writes only 6 keys.

The repair is large but not difficult. The shapes are all near-identical supersets of each
other. There is no deep logic to change — only serialization and the branches that read it.
**Estimate: 3 to 4 days of solo work, or 1.5 to 2 days with AI help.** See section 7.

The audit also found **8 live defects** that this mess hides. Four of them break game
features today. See section 6.

---

## 2. Endpoint inventory

15 endpoints. Three lack a `response_model` argument, but only **two** are truly
unvalidated. FastAPI also reads the return type annotation, so
`GET /session/{player_id}` is validated against `GameSession` through its
`-> GameSession` annotation. `GET /auth/me` and `POST /auth/upgrade-guest` have no
annotation and no model, so nothing checks them.

| Endpoint | Response model | Objects it returns |
|---|---|---|
| `POST /auth/guest` | `GuestLoginResponse` | token |
| `POST /auth/register` | `Token` | token |
| `POST /auth/login` | `Token` | token |
| `GET /auth/me` | **none** | user dict (8 keys) |
| `POST /auth/upgrade-guest` | **none** | `Token` |
| `GET /health` | `HealthResponse` | — |
| `POST /session/start` | `StartSessionResponse` | Item ×A, ×C · Container ×B · Session ×1 |
| `GET /session/{player_id}` | `GameSession` (inferred) | Item ×D · Container ×C · Session ×2 |
| `POST /shop/refresh` | `ShopRefreshResponse` | Item ×A |
| `POST /battle/simulate` | `BattleResponse` | Item ×A, ×B · Container ×A · Session ×3 |
| `POST /purchase/item` | `PurchaseResponse` | Item ×A · Container ×B |
| `POST /sell/item` | `SellResponse` | Item ×D |
| `POST /move/item` | `MoveItemResponse` | Item ×C, ×E |
| `GET /leaderboard` | `LeaderboardResponse` | leaderboard entry |
| `GET /battle/history/{id}` | `BattleHistoryResponse` | opaque `battle_data` dict |

---

## 3. The item object: 7 forms

| # | Form | Fields | Where it comes from |
|---|---|---|---|
| A | `ShopItem` | 12 | `/shop/refresh`.shop[], `/session/start`.session.current_shop[], `/battle/simulate`.new_shop[], `/purchase/item`.purchased_item |
| B | `PlacedItem` | 18 | `/battle/simulate` → battle_result.player_inventory.items[] and enemy_inventory.items[] |
| C | enriched stored dict | 17 | `serialize_inventory_item()` → `/session/start`.session.inventory_grid[] and .inventory_storage[], `/move/item`.inventory_grid[] and .inventory_storage[] |
| D | bare stored dict | 6–7 | `/sell/item`.sold_item, `/session/{player_id}`, and form C when `item_type` is not in `ITEM_CATALOG` |
| E | `ItemInfo` | 4 | `/move/item`.item |
| F | `ItemCatalogEntry` | 8 | **Dead schema.** Declared in `schemas.py:103`. No endpoint uses it. |
| G | client round-trip dict | 7 | `InventoryGrid.get_inventory_state()` (`InventoryGrid.gd:550`). Position becomes a dict. |

### The critical difference

Form **C** is built at `main.py:366`. It starts from the stored dict and adds 11 tooltip
fields. The stored dict is written at `main.py:1556` with only these keys:

```python
inventory_item = {
    "id": ..., "item_type": ..., "name": ...,
    "slug": ..., "cost": ..., "rarity": ...,
}
```

So form C **has no `shape` and no `category`**. Form B has both. The client
`InventoryItem` class reads `shape` with a default of `[]` (`api_types.gd:63`). Result: a
multi-square item shows correctly during a battle, and shows as a single square after you
reload the session. This is defect D5 in section 6.

Form **D** occurs when `serialize_inventory_item()` cannot find the item type. It then
returns the input unchanged (`main.py:459`). The client then fails its `data["slug"]`
lookup and prints a warning.

---

## 4. The container object: 5 forms

| # | Form | Fields | Where |
|---|---|---|---|
| A | `ServerContainer` schema | id, slug, type, position, width, height | battle inventories |
| B | session dict | same 6 keys, position as list | `/session/start`.session.server_containers, `/purchase/item`.server_containers |
| C | `InventoryGrid.containers` dict | same 6 keys, **position as a tuple** | `/session/{player_id}` (no response model, so the tuple leaks) |
| D | `ShopItem` with `is_container=true` | 12, **no width, no height** | shop slots |
| E | `ServerContainer` dataclass | spec, position, uid, rotation | `server_containers.py:14` — a **second class with the same name** as the schema |

Two problems follow from this:

- `main.py:1496` reads `item.width if hasattr(item, "width") else 2`. `ShopItem` (form D)
  has no `width` field, so this is **always** 2. Every container you buy becomes 2×2,
  whatever its real shape.
- `serialize_container()` (`main.py:1052`) derives width and height from the largest square
  in the shape. Your own comment marks it: `XXX: We shouldn't be using max x and y here`.
  A T-shaped container reports as a rectangle.

---

## 5. Other objects

**Position — 3 forms.** `[x, y]` list (the server standard), `(x, y)` tuple (server memory
and `/session/{player_id}`), and `{"x": _, "y": _}` dict (made by the client itself at
`InventoryGrid.gd:562`). `APITypes.Position._init` branches on two of them
(`api_types.gd:11`).

**Session — 3 forms.** `StartSessionResponse.session` (enriched), the raw `GameSession`
from `/session/{player_id}` (not enriched), and `SessionUpdate` (8 fields, a different
subset) from `/battle/simulate`. Also `GameSession.last_battle_result` is an untyped
`Optional[Dict]` that the client never reads.

**`BattleAction.details` — 6 forms.** `null`, `{"reason"}`, `{"buff_name",
"actual_value"}`, `{"debuff_name", "actual_value"}`, `{"type"}`, `{"debuff"}`.

**Action codes — 2 dialects.** `battle_engine.py:43` declares short codes (`"a"`, `"d"`,
`"bf"`). The engine then emits long names only (`"damage"`, `"buff"`, `"cpu_fail"`). The
client `match` blocks accept both (`BattleEventProcessor.gd:107` and `:144`). Four client
branches are therefore dead code.

---

## 6. Defects this mess hides

| ID | Defect | Location | Effect |
|---|---|---|---|
| D1 | **Sell is fully broken.** Client sends `item_id` and `from_storage`. Server requires `item_uid`. | `BattleServerAPI.gd:316` vs `schemas.py:85` | Every sell returns HTTP 422. |
| D2 | `healing_done` never fires. Server sends `"heal"`; the second match block only lists `"h"`. | `BattleEventProcessor.gd:164` | Heals show in the log but not in the HP bar. |
| D3 | `item_activated` never fires. The server emits no `"activate"` or `"a"` action. | `BattleEventProcessor.gd:148` | No activation animation. |
| D4 | Buff and debuff names are always empty. Client reads `details["buff"]`; server writes `details["buff_name"]`. Also the `"bf"` and `"df"` branches never match. | `BattleEventProcessor.gd:180` vs `battle_engine.py:651` | Buff labels are blank. |
| D5 | Grid items lose `shape` and `category` after a reload. | `main.py:366` | Multi-square items render as 1×1. |
| D6 | Bought containers are always 2×2. | `main.py:1496` | Wrong grid space. |
| D7 | `/health` calls `db_manager.execute`, which does not exist. | `main.py:211` | Production reports `degraded`. |
| D8 | `/session/{player_id}` needs no auth token. | `main.py:323` | Any player can read any session. |

Two more items to note, not defects but risks:
`InventoryManager.place_item` and `.move_item` catch bare `Exception` and return `False`
(`inventory_manager.py:229`, `:269`). Real errors become silent placement failures.
The client `refresh_shop` sends a `round` field that the server ignores.

---

## 7. Effort estimate

### Where the work is

| Area | Size | Churn |
|---|---|---|
| `server/schemas.py` | 304 lines | ~60% rewritten |
| `server/main.py` serialization | 3 functions, 10 return sites | ~250 lines touched |
| `server/inventory_manager.py` | 337 lines | store the full item, not 6 keys |
| `client/scripts/api_types.gd` | 332 lines | ~40% deleted |
| 5 client consumer scripts | 32 type branches, 163 defensive lookups | most branches deleted |
| `server/tests/` | 18 of 25 files touch these shapes | fixture updates |
| `client/test/` | 9 of 14 files | fixture updates |

### Plan and time

| Phase | Work | Solo | With AI |
|---|---|---|---|
| 1 | One canonical `Item` schema. One `Container` schema. Position is always `[x, y]`. Store the full item at purchase, so no enrichment step is needed. | 0.5 d | 0.25 d |
| 2 | Update all 10 server return sites. Add a `response_model` to the 3 endpoints that lack one. Delete `ItemCatalogEntry`, `ItemInfo`, and the dual `ServerContainer`. | 0.75 d | 0.5 d |
| 3 | Collapse `api_types.gd` to one `InventoryItem` and use it for shop items too. Delete the `is Dictionary` branches in `ItemVisual`, `ItemTooltip`, `InventoryGrid`, `UnifiedGridUI`. | 1 d | 0.5 d |
| 4 | Fix D1–D6 (they become obvious once the shapes are one shape). Pick one action dialect and delete the other. | 0.5 d | 0.25 d |
| 5 | Repair the server and client test suites. | 0.75 d | 0.5 d |
| **Total** | | **3.5 d** | **2 d** |

### Why this is easier than it looks

- The 7 item forms are **subsets of one superset**. Form B (`PlacedItem`, 18 fields) already
  contains every field the others hold. Make it the one form and each other form becomes a
  deletion, not a redesign.
- You do not need a compatibility layer. This is pre-alpha, and the client and server ship
  together.
- The client already has a type layer (`api_types.gd`). The work removes branches from it.
  It does not add a new layer.
- Godot fails loudly on a missing dict key. Once you remove the `.get()` defaults, the
  tests will point at every remaining mismatch.

### Main risk

`session.inventory_grid` is stored as JSON in Postgres. If you change the stored item shape,
old rows will not match. For pre-alpha the cheap answer is to drop the session rows, or to
add one Alembic migration that rewrites them. Budget 0.25 d if you want the migration.

---

## 8. Recommended target

One item type. One container type. One position type.

```python
class Item(BaseModel):
    id: str
    slug: str
    item_type: str
    name: str
    category: str
    rarity: str
    cost: int
    shape: list[list[int]]           # always present
    position: list[int] | None       # None = in storage or in the shop
    is_container: bool = False
    # stats
    min_damage: int = 0
    max_damage: int = 0
    min_heal: int = 0
    max_heal: int = 0
    block_amount: int = 0
    cooldown: float = 0.0
    cpu_cost: int = 0
    special_effect: str = ""
    description: str = ""

class Container(BaseModel):
    id: str
    slug: str
    type: str
    position: list[int]
    shape: list[list[int]]           # replaces width and height

class Inventory(BaseModel):
    items: list[Item]
    containers: list[Container]      # rename from "servers"
```

Then every endpoint that returns inventory returns `Inventory`. The shop returns
`list[Item | None]`. `/sell/item` returns the same `Item`. `/move/item` returns the same
`Inventory`. `serialize_inventory_item()` and `serialize_placed_item()` become one function.
