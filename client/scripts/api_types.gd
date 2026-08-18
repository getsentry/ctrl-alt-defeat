extends Resource
class_name APITypes

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
	var shape: Array = []  # Array[Array[int]]: the [x, y] offsets it covers
	var description: String = ""
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
	var special_effect: String = ""

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
		shape = data["shape"]
		description = data["description"]
		color = data["color"]
		pattern = data["pattern"]
		min_damage = int(data["min_damage"])
		max_damage = int(data["max_damage"])
		min_heal = int(data["min_heal"])
		max_heal = int(data["max_heal"])
		block_amount = int(data["block_amount"])
		cooldown = float(data["cooldown"])
		cpu_cost = float(data["cpu_cost"])
		special_effect = data["special_effect"]

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
			"shape": shape,
			"description": description,
			"color": color,
			"pattern": pattern,
			"min_damage": min_damage,
			"max_damage": max_damage,
			"min_heal": min_heal,
			"max_heal": max_heal,
			"block_amount": block_amount,
			"cooldown": cooldown,
			"cpu_cost": cpu_cost,
			"special_effect": special_effect
		}

	# The same item, now on the grid.
	func placed_at(grid_pos: Vector2i) -> PlacedItem:
		var fields = to_dict()
		fields["position"] = [grid_pos.x, grid_pos.y]
		fields["rotation"] = 0
		return PlacedItem.new(fields)

# An item on the grid. Only a placed item has somewhere to be and a way to face.
class PlacedItem extends Item:
	var position: Position
	var rotation: int = 0  # Quarter turns clockwise, 0/90/180/270

	func _init(data: Dictionary):
		super(data)
		position = Position.new(data["position"])
		rotation = int(data["rotation"])

	# The grid squares this item covers.
	func covered_squares() -> Array[Vector2i]:
		var squares: Array[Vector2i] = []
		for offset in shape:
			squares.append(Vector2i(position.x + int(offset[0]), position.y + int(offset[1])))
		return squares

	func to_dict() -> Dictionary:
		var fields = super.to_dict()
		fields["position"] = position.to_array()
		fields["rotation"] = rotation
		return fields

# Container/Server - matches server response
class ServerContainer extends Resource:
	var is_container: bool = true
	var id: String = ""
	var type: String = ""
	var slug: String = ""
	var position: Position
	var shape: Array = []  # Array[Array[int]]: the [x, y] offsets it covers
	var rotation: int = 0  # Quarter turns clockwise, 0/90/180/270

	func _init(data: Dictionary):
		# Server sends all these fields
		id = data["id"]
		type = data["type"]
		slug = data["slug"]
		position = Position.new(data["position"])
		shape = data["shape"]
		rotation = int(data["rotation"])

	func to_dict() -> Dictionary:
		return {
			"id": id,
			"type": type,
			"slug": slug,
			"position": position.to_array() if position else null,
			"shape": shape,
			"rotation": rotation
		}

	# The grid squares this container covers.
	func covered_squares() -> Array[Vector2i]:
		var squares: Array[Vector2i] = []
		for offset in shape:
			squares.append(Vector2i(position.x + int(offset[0]), position.y + int(offset[1])))
		return squares

# Inventory state (used in battles and saved state)
class InventoryState extends Resource:
	var items: Array[PlacedItem] = []
	var containers: Array[ServerContainer] = []

	func _init(data: Dictionary):
		items.clear()
		for item_data in data["items"]:
			items.append(PlacedItem.new(item_data))

		# The server calls the containers "servers" in InventoryData
		containers.clear()
		for container_data in data["servers"]:
			containers.append(ServerContainer.new(container_data))

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
	var game_over: bool
	var victory: bool

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
	# Inventory fields
	var inventory_grid: Array[PlacedItem] = []
	var inventory_storage: Array[Item] = []
	var server_containers: Array[ServerContainer]

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
		inventory_grid = []
		for item_data in data["inventory_grid"]:
			inventory_grid.append(PlacedItem.new(item_data))
		inventory_storage = []
		for item_data in data["inventory_storage"]:
			inventory_storage.append(Item.new(item_data))

		server_containers = []
		for container_data in data["server_containers"]:
			server_containers.append(ServerContainer.new(container_data))


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

	func _init(data: Dictionary):
		shop = APITypes.parse_shop(data["shop"])
		gold = data["gold"]

# Purchase response - matches server PurchaseResponse
class PurchaseResponse extends Resource:
	var purchased_item: Item
	var gold: int = 0
	var server_containers: Array[ServerContainer] = []

	func _init(data: Dictionary):
		purchased_item = Item.new(data["purchased_item"])
		gold = data["gold"]
		for container_data in data["server_containers"]:
			server_containers.append(ServerContainer.new(container_data))

# Battle response - matches server BattleResponse schema
class BattleResponse extends Resource:
	var battle_result: BattleResult
	var session_update: SessionUpdate  # Typed SessionUpdate
	var new_shop: Array[Item] = []  # null in a slot whose item was bought
	var battle_id: String = ""

	func _init(data: Dictionary):
		battle_result = BattleResult.new(data["battle_result"])
		session_update = SessionUpdate.new(data["session_update"])
		new_shop = APITypes.parse_shop(data["new_shop"])
		battle_id = data["battle_id"]

# Sell response
class SellResponse extends Resource:
	var gold_gained: int = 0
	var gold: int = 0
	var sold_item: Item

	func _init(data: Dictionary):
		gold_gained = int(data["gold_gained"])
		gold = int(data["gold"])
		sold_item = Item.new(data["sold_item"])

# Move item response
class MoveItemResponse extends Resource:
	var inventory_grid: Array[PlacedItem] = []
	var inventory_storage: Array[Item] = []

	func _init(data: Dictionary):
		for item_data in data["inventory_grid"]:
			inventory_grid.append(PlacedItem.new(item_data))
		for item_data in data["inventory_storage"]:
			inventory_storage.append(Item.new(item_data))
