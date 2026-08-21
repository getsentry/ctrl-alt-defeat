extends Resource
class_name APITypes

# The squares a shape covers once it has been turned, as [x, y] offsets.
#
# Rows count downwards, so a quarter turn clockwise sends (x, y) to (-y, x) and
# the square to the right of an item ends up below it. That is the same
# direction Godot turns the artwork by a positive angle, and both have to be
# the same one: turned the other way, a spear was drawn pointing one way with
# its aura reaching the other.
#
# The result is pushed back so that its corner sits at the origin: turning an
# item changes the squares it covers, not where it is. The server turns shapes
# the same way, in grid_system._turn(), and the two have to agree or an item
# draws on squares the server has it standing somewhere else.
static func turn(shape: Array[Vector2i], rotation: int) -> Array[Vector2i]:
	if rotation == 0 or shape.is_empty():
		return shape.duplicate()

	var turned := _spin(shape, rotation)
	var corner := _corner(turned)
	var settled: Array[Vector2i] = []
	for square in turned:
		settled.append(square - corner)
	return settled


# The top left of a set of squares, which is what everything is settled against.
static func _corner(squares: Array[Vector2i]) -> Vector2i:
	if squares.is_empty():
		return Vector2i.ZERO
	var least := squares[0]
	for square in squares:
		least.x = mini(least.x, square.x)
		least.y = mini(least.y, square.y)
	return least


# Read the [x, y] pairs a server response carries as squares. The parameter is
# an untyped Array because that is what JSON hands over, and its numbers arrive
# as floats: [[0.0, 0.0]]. Converting here is what stops a float reaching the
# rest of the client, where `has(Vector2i(0, 0))` would quietly answer false.
static func squares(offsets: Array) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	for offset in offsets:
		if offset is Array and offset.size() >= 2:
			out.append(Vector2i(int(offset[0]), int(offset[1])))
	return out


# Read a list of names a response carries. JSON hands over an untyped Array,
# and an Array[String] is what the rest of the client wants to hold.
static func strings(values: Array) -> Array[String]:
	var out: Array[String] = []
	for value in values:
		out.append(str(value))
	return out


# And back, for a response this client builds or echoes.
static func offsets(squares_in: Array[Vector2i]) -> Array:
	var out := []
	for square in squares_in:
		out.append([square.x, square.y])
	return out


# The squares a zone covers once its item has been turned.
#
# A zone cannot go through turn() on its own. That settles what it is given
# against its own corner, and a zone settled against its own corner slides onto
# the item. So both are turned and both are pushed back by the FOOTPRINT's
# corner, which is the only frame the two share.
#
# `anchors` are covered squares whose zone points straight up on the grid
# however the item is turned, so they are left out of the turn and their square
# is worked out afterwards. It is dropped where it lands on the item itself.
static func turn_zone(
	shape: Array[Vector2i],
	zone: Array[Vector2i],
	anchors: Array[Vector2i],
	rotation: int,
) -> Array[Vector2i]:
	var turned_shape := _spin(shape, rotation)
	if turned_shape.is_empty():
		return []

	var corner := _corner(turned_shape)
	var covered := {}
	for square in turned_shape:
		covered[square - corner] = true

	# The square an anchor points into is drawn on the map, so it is in the zone
	# already for the way the item faces now. Take it out before turning, or the
	# item ends up with the old square and the new one.
	var was_projected := {}
	for anchor in anchors:
		var above := anchor + Vector2i.UP
		if not shape.has(above):
			was_projected[above] = true

	var reached := {}
	for square in zone:
		if not was_projected.has(square):
			reached[_spin([square], rotation)[0] - corner] = true

	# An anchor points up on the grid however the item is turned, so its square
	# is worked out after the turn rather than turned with the rest.
	for anchor in _spin(anchors, rotation):
		reached[anchor - corner + Vector2i.UP] = true

	var settled: Array[Vector2i] = []
	for square in reached:
		if not covered.has(square):
			settled.append(square)
	settled.sort()
	return settled


# The turn itself, without settling anything against a corner.
static func _spin(offsets: Array[Vector2i], rotation: int) -> Array[Vector2i]:
	var turned: Array[Vector2i] = []
	for square in offsets:
		match rotation:
			90: turned.append(Vector2i(-square.y, square.x))
			180: turned.append(Vector2i(-square.x, -square.y))
			270: turned.append(Vector2i(square.y, -square.x))
			_: turned.append(square)
	return turned


# Where an item faces after being turned this many quarters, clockwise for a
# positive number and the other way for a negative one.
static func turned_by(rotation: int, quarters: int) -> int:
	return posmod(rotation + quarters * 90, 360)


# A shop slot holds an item, or null once that item has been bought.
static func parse_shop(slots: Array) -> Array[Item]:
	var shop: Array[Item] = []
	for slot in slots:
		shop.append(Item.new(slot) if slot != null else null)
	return shop

# A position is an [x, y] array, in both directions.
class Position extends Resource:
	var x: int = 0
	var y: int = 0

	func _init(data):
		if not data is Array:
			push_error("Position must be an [x, y] array, got: " + str(data))
			return
		if data.size() != 2:
			push_error("Position must have exactly 2 items, got: " + str(data))
			return
		x = int(data[0])
		y = int(data[1])

	func to_array() -> Array[int]:
		return [x, y]

	func to_vector2() -> Vector2:
		return Vector2(x, y)

	func to_vector2i() -> Vector2i:
		return Vector2i(x, y)


# An item in the shop or in the chest.
class Item extends Resource:
	var id: String = ""
	var item_type: String = ""
	var name: String = ""
	var slug: String = ""
	var category: String = ""
	var rarity: String = ""
	var cost: int = 0
	# What the shop is charging today. Equal to cost unless it is on sale.
	var price: int = 0
	var sell_value: int = 0
	# Only ever true of a shop offer. Buying it ends the sale.
	var on_sale: bool = false
	var is_container: bool = false
	# The squares it covers, as offsets from its own corner.
	var shape: Array[Vector2i] = []
	# The zones this item reaches into, in the same frame as `shape`, so a
	# square above or left of the item is negative. Nothing draws them yet.
	var star: Array[Vector2i] = []
	var diamond: Array[Vector2i] = []
	# Covered squares whose zone points straight up on the grid however the item
	# is turned. Needed to work out a turned zone; see turn_zone.
	var anchors: Array[Vector2i] = []
	# What this item can be narrowed by, with its category: "Star Pets" and
	# "Star nature-items" are matched from these. See aura.gd.
	var kinds: Array[String] = []
	## The same kinds as a player reads them, which is the server's business:
	## it is the one that knows what a trait is called. `kinds` is what an
	## aura matches on and is never shown.
	var traits: Array[String] = []
	# What each of its zones acts on, keyed "star" and "diamond". A zone the
	# item draws but nothing acts through is absent, which is not the same as
	# one that acts on everything: that is present and empty.
	var aura: Dictionary = {}
	# How to draw the item while it has no artwork. The colour arrives as a
	# value, so the client keeps no palette; the pattern arrives as a name,
	# because the client is what draws it. Both are empty on a container.
	var color: String = ""
	var pattern: String = ""
	var min_damage: int = 0
	var max_damage: int = 0
	var min_heal: int = 0
	var max_heal: int = 0
	var block_amount: int = 0
	var cooldown: float = 0.0
	var cpu_cost: float = 0.0
	## How often the attack behind the damage lands. 1.0 for an item that does
	## not attack, since there was no attack to read it off.
	var accuracy: float = 1.0
	## What the item deals and what it eats in a second of battle, worked out
	## by the server. Not worked out here: a rate needs how often the attack
	## lands, and nothing else on the card says that.
	var damage_per_second: float = 0.0
	var cpu_per_second: float = 0.0
	## What the item does, a line per trigger, worked out by the server from
	## the item's own effects. The client shows them and knows nothing about
	## what any of it means.
	var effects: Array[String] = []

	func _init(data: Dictionary):
		id = data["id"]
		item_type = data["item_type"]
		name = data["name"]
		slug = data["slug"]
		category = data["category"]
		rarity = data["rarity"]
		cost = int(data["cost"])
		price = int(data["price"])
		sell_value = int(data["sell_value"])
		on_sale = data["on_sale"]
		is_container = data["is_container"]
		shape = APITypes.squares(data["shape"])
		star = APITypes.squares(data.get("star", []))
		diamond = APITypes.squares(data.get("diamond", []))
		anchors = APITypes.squares(data.get("anchors", []))
		kinds = APITypes.strings(data["kinds"])
		traits = APITypes.strings(data["traits"])
		aura = data["aura"]
		color = data["color"]
		pattern = data["pattern"]
		min_damage = int(data["min_damage"])
		max_damage = int(data["max_damage"])
		min_heal = int(data["min_heal"])
		max_heal = int(data["max_heal"])
		block_amount = int(data["block_amount"])
		cooldown = float(data["cooldown"])
		cpu_cost = float(data["cpu_cost"])
		accuracy = float(data["accuracy"])
		damage_per_second = float(data["damage_per_second"])
		cpu_per_second = float(data["cpu_per_second"])
		effects = []
		for line in data["effects"]:
			effects.append(str(line))

	func to_dict() -> Dictionary:
		return {
			"id": id,
			"item_type": item_type,
			"name": name,
			"slug": slug,
			"category": category,
			"rarity": rarity,
			"cost": cost,
			"price": price,
			"sell_value": sell_value,
			"on_sale": on_sale,
			"is_container": is_container,
			"shape": APITypes.offsets(shape),
			"star": APITypes.offsets(star),
			"diamond": APITypes.offsets(diamond),
			"anchors": APITypes.offsets(anchors),
			"kinds": kinds,
			"traits": traits,
			"aura": aura,
			"effects": effects,
			"color": color,
			"pattern": pattern,
			"min_damage": min_damage,
			"max_damage": max_damage,
			"min_heal": min_heal,
			"max_heal": max_heal,
			"block_amount": block_amount,
			"cooldown": cooldown,
			"cpu_cost": cpu_cost,
			"accuracy": accuracy,
			"damage_per_second": damage_per_second,
			"cpu_per_second": cpu_per_second,
		}

	# The offsets this item covers. An item that is not on the grid is not
	# facing any particular way, so this is its shape; a placed one answers
	# with the shape turned. Both answer, so nothing asking has to know which
	# kind it was handed.
	func turned_shape() -> Array[Vector2i]:
		return shape

	# The squares a zone covers, turned the way this item faces. One that is not
	# on the grid faces nowhere, so its zone is the one the catalogue drew.
	func turned_star() -> Array[Vector2i]:
		return star

	func turned_diamond() -> Array[Vector2i]:
		return diamond

	# Which way this item faces. One that is not on the grid faces nowhere in
	# particular, so it answers the same as one that has not been turned.
	func facing() -> int:
		return 0

	# The same item, turned. Where an item stands is its own business, so
	# nothing turning one has to know whether it is on the grid or in a hand:
	# this is the only place a quarter turn is worked out.
	func turned(quarters: int) -> PlacedItem:
		return placed_at(Vector2i.ZERO, APITypes.turned_by(facing(), quarters))

	# The same item, now on the grid, facing whichever way it is asked to.
	func placed_at(grid_pos: Vector2i, facing: int = 0) -> PlacedItem:
		var fields = to_dict()
		fields["position"] = [grid_pos.x, grid_pos.y]
		fields["rotation"] = facing
		return PlacedItem.new(fields)

# An item on the grid. Only a placed item has somewhere to be and a way to face.
class PlacedItem extends Item:
	var position: Position
	var rotation: int = 0  # Quarter turns clockwise, 0/90/180/270

	func _init(data: Dictionary):
		super(data)
		position = Position.new(data["position"])
		rotation = int(data["rotation"])

	# The catalogue holds a shape unturned, so anything asking which squares an
	# item takes has to turn it first or it is asking about a different item.
	func turned_shape() -> Array[Vector2i]:
		return APITypes.turn(shape, rotation)

	func turned_star() -> Array[Vector2i]:
		return APITypes.turn_zone(shape, star, anchors, rotation)

	func turned_diamond() -> Array[Vector2i]:
		# A diamond has no anchor rule, so it simply turns with the item.
		var none: Array[Vector2i] = []
		return APITypes.turn_zone(shape, diamond, none, rotation)

	func facing() -> int:
		return rotation

	# An item on the grid turns where it stands.
	func turned(quarters: int) -> PlacedItem:
		return placed_at(
			position.to_vector2i(), APITypes.turned_by(facing(), quarters))

	# An item already on the grid keeps facing the way it does unless it is
	# asked to face another way.
	func placed_at(grid_pos: Vector2i, facing: int = -1) -> PlacedItem:
		return super.placed_at(grid_pos, rotation if facing < 0 else facing)

	# The grid squares this item covers.
	func covered_squares() -> Array[Vector2i]:
		return _on_the_grid(turned_shape())

	# The grid squares each zone reaches, once turned and put down.
	func star_squares() -> Array[Vector2i]:
		return _on_the_grid(turned_star())

	func diamond_squares() -> Array[Vector2i]:
		return _on_the_grid(turned_diamond())

	func _on_the_grid(offsets: Array[Vector2i]) -> Array[Vector2i]:
		var here := Vector2i(position.x, position.y)
		var out: Array[Vector2i] = []
		for offset in offsets:
			out.append(here + offset)
		return out

	func to_dict() -> Dictionary:
		var fields = super.to_dict()
		fields["position"] = position.to_array()
		fields["rotation"] = rotation
		return fields

# A container is a PlacedItem that provides squares rather than filling them.
# It comes from the same catalogue, is bought from the same shop and stands on
# the same grid. What tells the two apart is which list they arrive in.

# Inventory state (used in battles and saved state)
class InventoryState extends Resource:
	var items: Array[PlacedItem] = []
	var containers: Array[PlacedItem] = []

	func _init(data: Dictionary):
		items.clear()
		for item_data in data["items"]:
			items.append(PlacedItem.new(item_data))

		# The server calls the containers "servers" in InventoryData
		containers.clear()
		for container_data in data["servers"]:
			containers.append(PlacedItem.new(container_data))

# Everything the player holds: the rack, the chest and the containers.
#
# What a battle answers with, and what a move answers with, are the same three
# lists, so they are read the same way.
class WholeInventory extends Resource:
	var inventory_grid: Array[PlacedItem] = []
	var inventory_storage: Array[Item] = []
	# Moving a container moves the containers, so the whole board comes back.
	var server_containers: Array[PlacedItem] = []

	func _init(data: Dictionary):
		for item_data in data["inventory_grid"]:
			inventory_grid.append(PlacedItem.new(item_data))
		for item_data in data["inventory_storage"]:
			inventory_storage.append(Item.new(item_data))
		for container_data in data["server_containers"]:
			server_containers.append(PlacedItem.new(container_data))

	# The board as the grid loads it.
	func as_inventory_state() -> InventoryState:
		var items: Array[Dictionary] = []
		for item in inventory_grid:
			items.append(item.to_dict())
		var servers: Array[Dictionary] = []
		for container in server_containers:
			servers.append(container.to_dict())
		return InventoryState.new({"items": items, "servers": servers})


# A recipe the rack is part or all of the way towards (GDD 5.3).
#
# `have` of `need` parts are there and touching each other. Equal means it will
# combine the moment the battle starts, which is the glow to draw. Fewer means
# it is progress, which is the label to put beside the part just put down.
#
# The parts are named by id, because the client is looking at those items.
# What it makes is named by type, because that item does not exist yet.
class Pending extends Resource:
	var makes: String = ""
	var have: int = 0
	var need: int = 0
	# Ids on the rack that would be used up.
	var ingredients: Array[String] = []
	# Ids on the rack that are needed and kept.
	var catalysts: Array[String] = []
	# Parts still wanted: an item type, or a `class:` wildcard over a kind.
	var missing: Array[String] = []

	func _init(data: Dictionary):
		makes = data["makes"]
		have = int(data["have"])
		need = int(data["need"])
		ingredients = APITypes.strings(data["ingredients"])
		catalysts = APITypes.strings(data["catalysts"])
		missing = APITypes.strings(data["missing"])

	# Whether this is a combination that will happen rather than progress
	# towards one.
	func complete() -> bool:
		return have == need

	# Every item on the rack this names, eaten or kept.
	func item_ids() -> Array[String]:
		var ids: Array[String] = []
		ids.append_array(ingredients)
		ids.append_array(catalysts)
		return ids

	func names(item_id: String) -> bool:
		return ingredients.has(item_id) or catalysts.has(item_id)


# One combining that happened, for the client to play (GDD 5.3).
#
# The consumed items are gone from the rack by the time this is read, so they
# arrive whole rather than named: a name would not be enough to draw one, and
# with two of a kind on the rack it would not say which two were eaten.
class Combination extends Resource:
	var made: String = ""
	var made_id: String = ""
	var consumed: Array[PlacedItem] = []
	var kept: Array[PlacedItem] = []
	# The squares the ingredients were standing on.
	var freed: Array[Vector2i] = []
	# Where the result landed. Null means it went to the chest.
	var position: Position = null

	func _init(data: Dictionary):
		made = data["made"]
		made_id = data["made_id"]
		for item_data in data["consumed"]:
			consumed.append(PlacedItem.new(item_data))
		for item_data in data["kept"]:
			kept.append(PlacedItem.new(item_data))
		freed = APITypes.squares(data["freed"])
		if data["position"] != null:
			position = Position.new(data["position"])


# Which item types go together in a recipe, for the whole catalogue.
#
# The same for every player and every rack, so it is fetched once and answered
# from here. It says these two appear in a recipe together and nothing more:
# whether a combination will actually happen is `pending`, which needs rules
# that stay on the server.
## What every buff and debuff does, per stack, as the server describes them.
##
## Asked for once: the rules never change, and a chip beside a fighter is
## hovered far too often to be a request each time. The words are the
## server's, because the rules are -- a copy over here would go on saying 2%
## the day after it stopped being 2%.
class StatusRules extends Resource:
	## Keyed by the name the engine uses: "optimized", "memory_leaked".
	var rules: Dictionary = {}

	func _init(data: Dictionary):
		for rule in data["statuses"]:
			rules[str(rule["status"])] = {
				"shown": str(rule["shown"]),
				"kind": str(rule["kind"]),
				"each": int(rule["each"]),
				"one": str(rule["one"]),
				"many": str(rule["many"]),
				"detail": str(rule.get("detail", "")),
			}

	## One status as the server describes it, or empty for one nothing is
	## known about.
	func about(status: String) -> Dictionary:
		return rules.get(status, {})

	func knows_any() -> bool:
		return not rules.is_empty()

	## What this many stacks of a status come to, in words. Empty for a status
	## nobody has written a rule for, and for one whose worth is not a number.
	func what_it_does(status: String, stacks: int) -> String:
		var rule: Dictionary = rules.get(status, {})
		if rule.is_empty():
			return ""
		if stacks <= 1 or int(rule["each"]) == 0 or str(rule["many"]) == "":
			return str(rule["one"])
		# The only arithmetic on this side: the rule that got to `each` stays
		# on the server.
		var total := int(rule["each"]) * stacks
		return str(rule["many"]).replace("{total}", str(total))


class CombiningCatalogue extends Resource:
	var partners: Dictionary = {}  # item type -> Array[String]
	var names: Dictionary = {}     # item type -> the name to show for it

	func _init(data: Dictionary):
		for item_type in data["partners"]:
			partners[item_type] = APITypes.strings(data["partners"][item_type])
		for item_type in data["names"]:
			names[item_type] = str(data["names"][item_type])

	func partners_of(item_type: String) -> Array[String]:
		var found: Array[String] = []
		found.assign(partners.get(item_type, []))
		return found

	# What to call an item type on screen. The slug where the catalogue has
	# never heard of it, which is better than a blank label.
	func name_of(item_type: String) -> String:
		return names.get(item_type, item_type)


# Battle action - matches server BattleAction schema
class BattleAction extends Resource:
	var timestamp: int = 0  # milliseconds
	var source: String = ""
	var action: String = ""
	var target: String = ""  # Optional (empty string when not provided)
	var damage: int = 0  # Optional int (0 when not provided)
	var player: int = 0
	var details: Dictionary = {}  # Optional (empty dict when not provided)

	func _init(data: Dictionary):
		# Required fields per server schema
		timestamp = int(data["timestamp"])
		source = str(data["source"])
		action = str(data["action"])
		player = int(data["player"])
		# Optional fields
		if data["target"] != null:
			target = str(data["target"])
		if data["damage"] != null:
			damage = int(data["damage"])
		if data["details"] != null:
			details = data["details"]

# Battle result
class BattleResult extends Resource:
	var winner: int = 0
	var duration: float = 0.0
	var player1_quota: int = 0
	var player2_quota: int = 0
	var actions: Array[BattleAction] = []
	var seed: int = 0
	var player_inventory: InventoryState
	var enemy_inventory: InventoryState
	var opponent_name: String = "AI Opponent"
	var opponent_type: String = "ai"  # "ai" or "player_ghost"

	func _init(data: Dictionary):
		# Required fields - fail if missing
		winner = data["winner"]
		duration = data["duration"]
		player1_quota = data["player1_quota"]
		player2_quota = data["player2_quota"]
		seed = data["seed"]

		# Parse actions - required
		actions.clear()
		for action_data in data["actions"]:
			actions.append(BattleAction.new(action_data))

		# Parse inventories - required in battle results
		player_inventory = InventoryState.new(data["player_inventory"])
		enemy_inventory = InventoryState.new(data["enemy_inventory"])

		opponent_name = data["opponent_name"]
		opponent_type = data["opponent_type"]

# Session update - matches server SessionUpdate schema
class SessionUpdate extends Resource:
	var round: int = 0
	var gold: int = 0
	var gold_earned: int = 0
	var wins: int = 0
	var losses: int = 0
	var lives: int = 0
	## What the first roll of the new round's shelf costs. The round resets the
	## count the price climbs with, and this is where a client learns the round
	## changed at all.
	var shop_refresh_cost: int = 1
	var game_over: bool
	var victory: bool
	# What combined as this shop phase began, in the order it happened.
	var combinations: Array[Combination] = []
	# What the rack is on the way to now, after that combining.
	var pending: Array[Pending] = []

	func _init(data: Dictionary):
		# Required fields per server SessionUpdate schema
		round = data["round"]
		gold = data["gold"]
		gold_earned = data["gold_earned"]
		wins = data["wins"]
		losses = data["losses"]
		lives = data["lives"]
		game_over = data["game_over"]
		victory = data["victory"]
		shop_refresh_cost = int(data["shop_refresh_cost"])
		for made in data["combinations"]:
			combinations.append(Combination.new(made))
		for waiting in data["pending"]:
			pending.append(Pending.new(waiting))


class GameSession extends Resource:
	var player_id: String
	var player_name: String
	var round: int
	var gold: int
	var lives: int
	var wins: int
	var losses: int
	var current_shop: Array[Item]  # null in a slot whose item was bought
	var game_seed: int
	var shop_refresh_count: int = 0  # Track number of shop refreshes for seed variation
	## What the next roll of the shelf costs. Quoted by the server rather than
	## worked out here: the price climbs with the rolls already taken, and a
	## client holding that rule says one number while the server charges
	## another the moment the rule moves.
	var shop_refresh_cost: int = 1
	# Inventory fields
	var inventory_grid: Array[PlacedItem] = []
	var inventory_storage: Array[Item] = []
	var server_containers: Array[PlacedItem]
	# What the rack is on the way to combining. See Pending.
	var pending: Array[Pending] = []

	func _init(data: Dictionary):
		player_id = data["player_id"]
		player_name = data["player_name"]
		round = data["round"]
		gold = data["gold"]
		lives = data["lives"]
		wins = data["wins"]
		losses = data["losses"]
		current_shop = APITypes.parse_shop(data["current_shop"])
		game_seed = data["game_seed"]
		shop_refresh_count = data["shop_refresh_count"]
		shop_refresh_cost = int(data["shop_refresh_cost"])
		inventory_grid = []
		for item_data in data["inventory_grid"]:
			inventory_grid.append(PlacedItem.new(item_data))
		inventory_storage = []
		for item_data in data["inventory_storage"]:
			inventory_storage.append(Item.new(item_data))

		server_containers = []
		for container_data in data["server_containers"]:
			server_containers.append(PlacedItem.new(container_data))

		for waiting in data["pending"]:
			pending.append(Pending.new(waiting))


# Session start response - matches server StartSessionResponse
class SessionStartResponse extends Resource:
	var player_id: String = ""
	var session: GameSession

	func _init(data: Dictionary):
		# Required fields per server schema
		player_id = data["player_id"]
		session = GameSession.new(data["session"])


# Shop refresh response
class ShopRefreshResponse extends Resource:
	var shop: Array[Item] = []  # null in a slot whose item was bought
	var gold: int = 0
	## What the roll after this one costs, so the button can say so without
	## asking the server again.
	var next_refresh_cost: int = 1

	func _init(data: Dictionary):
		shop = APITypes.parse_shop(data["shop"])
		gold = data["gold"]
		next_refresh_cost = int(data["next_refresh_cost"])

# Purchase response - matches server PurchaseResponse
class PurchaseResponse extends Resource:
	var purchased_item: Item
	var gold: int = 0
	var server_containers: Array[PlacedItem] = []
	var pending: Array[Pending] = []

	func _init(data: Dictionary):
		purchased_item = Item.new(data["purchased_item"])
		gold = data["gold"]
		for container_data in data["server_containers"]:
			server_containers.append(PlacedItem.new(container_data))
		for waiting in data["pending"]:
			pending.append(Pending.new(waiting))

# Battle response - matches server BattleResponse schema
class BattleResponse extends Resource:
	var battle_result: BattleResult
	var session_update: SessionUpdate  # Typed SessionUpdate
	var new_shop: Array[Item] = []  # null in a slot whose item was bought
	var battle_id: String = ""
	# What the player holds now, after the combining that began this shop
	# phase. Not the same as battle_result.player_inventory, which is the rack
	# that fought and so the rack before anything combined.
	var inventory: WholeInventory

	func _init(data: Dictionary):
		battle_result = BattleResult.new(data["battle_result"])
		session_update = SessionUpdate.new(data["session_update"])
		new_shop = APITypes.parse_shop(data["new_shop"])
		battle_id = data["battle_id"]
		inventory = WholeInventory.new(data["inventory"])

# Sell response
class SellResponse extends Resource:
	var gold_gained: int = 0
	var gold: int = 0
	var sold_item: Item
	var pending: Array[Pending] = []

	func _init(data: Dictionary):
		gold_gained = int(data["gold_gained"])
		gold = int(data["gold"])
		sold_item = Item.new(data["sold_item"])
		for waiting in data["pending"]:
			pending.append(Pending.new(waiting))

# Move item response
class MoveItemResponse extends WholeInventory:
	var pending: Array[Pending] = []

	func _init(data: Dictionary):
		super(data)
		for waiting in data["pending"]:
			pending.append(Pending.new(waiting))
