extends Resource
class_name APITypes

# Position type - server always sends as [x, y] array
class Position extends Resource:
	var x: int = 0
	var y: int = 0

	func _init(data):
		# Handle both Array [x, y] and Dictionary {x: _, y: _} formats
		if data is Array:
			x = int(data[0])
			y = int(data[1])
		elif data is Dictionary:
			x = int(data.get("x", 0))
			y = int(data.get("y", 0))
		else:
			push_error("Position received invalid data type: " + str(typeof(data)))

	func to_dict() -> Dictionary:
		return {"x": x, "y": y}

	func to_vector2() -> Vector2:
		return Vector2(x, y)


# Inventory item
class InventoryItem extends Resource:
	var id: String = ""
	var item_type: String = ""
	var slug: String = ""
	var name: String = ""
	var category: String = ""
	var position: Position
	var shape: Array = []  # Array of [x, y] offsets
	# Additional fields for tooltips
	var rarity: String = ""
	var cost: int = 0
	var min_damage: int = 0
	var max_damage: int = 0
	var min_heal: int = 0
	var max_heal: int = 0
	var cooldown: float = 0.0
	var cpu_cost: int = 0
	var special_effect: String = ""
	var block_amount: int = 0
	var description: String = ""

	func _init(data: Dictionary):
		# Required fields per server PlacedItem schema
		if not data.has("id"):
			print("InventoryItem missing id", data)
			return  # Invalid data
		id = data["id"]
		item_type = data.get("item_type", "")
		if not data.has("slug"):
			print("Slug missing from InventoryItem", data)
		slug = data["slug"]
		name = data.get("name", "")
		category = data.get("category", "")
		if data.has("position"):
			position = Position.new(data["position"])
		shape = data.get("shape", [])  # Shape as list of [x, y] offsets

		# Parse additional tooltip fields (optional for backwards compatibility)
		rarity = data.get("rarity", "")
		cost = data.get("cost", 0)
		min_damage = data.get("min_damage", 0)
		max_damage = data.get("max_damage", 0)
		min_heal = data.get("min_heal", 0)
		max_heal = data.get("max_heal", 0)
		cooldown = data.get("cooldown", 0.0)
		cpu_cost = data.get("cpu_cost", 0)
		special_effect = data.get("special_effect", "")
		block_amount = data.get("block_amount", 0)
		description = data.get("description", "")

	func to_dict() -> Dictionary:
		return {
			"id": id,
			"item_type": item_type,
			"slug": slug,
			"name": name,
			"category": category,
			"position": position.to_dict() if position else {"x": 0, "y": 0},
			"shape": shape
		}

# Container/Server - matches server response
class ServerContainer extends Resource:
	var id: String = ""
	var type: String = ""
	var slug: String = ""
	var position: Position
	var width: int = 2
	var height: int = 2

	func _init(data: Dictionary):
		# Server sends all these fields
		id = data["id"]
		type = data.get("type", "")
		if not data.has("slug"):
			print("slug missing from ServerContainer", data)
		slug = data["slug"]
		position = Position.new(data["position"])
		width = data.get("width", 2)
		height = data.get("height", 2)

	func to_dict() -> Dictionary:
		return {
			"id": id,
			"type": type,
			"slug": slug,
			"position": position.to_dict() if position else {"x": 0, "y": 0},
			"width": width,
			"height": height
		}

# Inventory state (used in battles and saved state)
class InventoryState extends Resource:
	var items: Array = []  # Array of InventoryItem
	var containers: Array = []  # Array of ServerContainer

	func _init(data: Dictionary):
		# Load items - required
		items.clear()
		for item_data in data.get("items", []):
			# Check if already an InventoryItem object or needs to be created
			if item_data is InventoryItem:
				items.append(item_data)
			elif item_data is Dictionary and item_data.has("id"):
				items.append(InventoryItem.new(item_data))
			# else skip invalid item

		# Load containers - server sends "servers" field per InventoryData schema
		containers.clear()
		for container_data in data.get("servers", []):
			# Check if already a ServerContainer object or needs to be created
			if container_data is ServerContainer:
				containers.append(container_data)
			elif container_data is Dictionary and container_data.has("id"):
				containers.append(ServerContainer.new(container_data))
			# else skip invalid container

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
	var actions: Array = []  # Array of BattleAction
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

		# Parse opponent info - optional for backwards compatibility
		opponent_name = data.get("opponent_name", "AI Opponent")
		opponent_type = data.get("opponent_type", "ai")

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
	var current_shop: Array
	var game_seed: int
	var shop_refresh_count: int = 0  # Track number of shop refreshes for seed variation
	# Inventory fields
	var inventory_grid: Array  # Not used right now
	var server_containers: Array[ServerContainer]

	func _init(data: Dictionary):
		player_id = data["player_id"]
		player_name = data["player_name"]
		round = data["round"]
		gold = data["gold"]
		lives = data["lives"]
		wins = data["wins"]
		losses = data["losses"]
		current_shop = data["current_shop"]
		game_seed = data["game_seed"]
		shop_refresh_count = data["shop_refresh_count"]
		inventory_grid = data["inventory_grid"]

		server_containers = []
		for container_data in data.get("server_containers", []):
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
	var shop: Array = []  # Array of ShopItem dicts (untyped for flexibility)
	var gold: int = 0

	func _init(data: Dictionary):
		shop = data["shop"]
		gold = data["gold"]

# Purchase response - matches server PurchaseResponse
class PurchaseResponse extends Resource:
	var purchased_item: Dictionary = {}  # ShopItem
	var gold: int = 0
	var server_containers: Array = []  # Array of server containers (when purchasing a container)

	func _init(data: Dictionary):
		# Required fields per server schema
		# Server doesn't send success - HTTP 200 means success
		purchased_item = data["purchased_item"]
		gold = data["gold"]
		# Optional field for container purchases
		# TODO: This is probably unnecessary, just expect it to always be there.
		# TODO: Probably fetch the whole session down instead and refresh from that
		if data.has("server_containers") and data["server_containers"] != null:
			server_containers = data["server_containers"]
		else:
			server_containers = []  # Initialize as empty array if not provided

# Battle response - matches server BattleResponse schema
class BattleResponse extends Resource:
	var battle_result: BattleResult
	var session_update: SessionUpdate  # Typed SessionUpdate
	var new_shop: Array = []  # List of ShopItem or null
	var battle_id: String = ""

	func _init(data: Dictionary):
		battle_result = BattleResult.new(data["battle_result"])
		session_update = SessionUpdate.new(data["session_update"])
		new_shop = data["new_shop"]
		battle_id = data["battle_id"]

# Sell response
class SellResponse extends Resource:
	var gold: int = 0

	func _init(data: Dictionary):
		gold = data["gold"]

# Move item response
class MoveItemResponse extends Resource:
	var inventory_grid: Array[InventoryItem] = []
	var inventory_storage: Array[InventoryItem] = []
	var item: InventoryItem

	func _init(data: Dictionary):
		if data.has("inventory_grid"):
			for item_data in data["inventory_grid"]:
				inventory_grid.append(InventoryItem.new(item_data))
		if data.has("inventory_storage"):
			for item_data in data["inventory_storage"]:
				inventory_storage.append(InventoryItem.new(item_data))
		if data.has("item"):
			item = InventoryItem.new(data["item"])
