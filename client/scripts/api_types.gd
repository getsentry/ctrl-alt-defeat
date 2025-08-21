extends Resource
class_name APITypes

# Position type - server always sends as [x, y] array
class Position extends Resource:
	var x: int = 0
	var y: int = 0

	func _init(data: Array):
		x = int(data[0])
		y = int(data[1])

	func to_dict() -> Dictionary:
		return {"x": x, "y": y}

	func to_vector2() -> Vector2:
		return Vector2(x, y)


# Inventory item
class InventoryItem extends Resource:
	var id: String = ""
	var item_type: String = ""
	var name: String = ""
	var category: String = ""
	var position: Position
	var shape: Array = []  # Array of [x, y] offsets

	func _init(data: Dictionary):
		# Required fields per server PlacedItem schema
		id = data["id"]
		item_type = data["item_type"]
		name = data["name"]
		category = data["category"]
		position = Position.new(data["position"])
		shape = data["shape"]  # Shape as list of [x, y] offsets

	func to_dict() -> Dictionary:
		return {
			"id": id,
			"item_type": item_type,
			"name": name,
			"category": category,
			"position": position.to_dict(),
			"shape": shape
		}

# Container/Server - matches server response
class ServerContainer extends Resource:
	var id: String = ""
	var type: String = ""
	var position: Position
	var width: int = 2
	var height: int = 2

	func _init(data: Dictionary):
		# Server sends all these fields - let it error if missing
		id = data["id"]
		type = data["type"]
		position = Position.new(data["position"])
		width = data["width"]
		height = data["height"]

	func to_dict() -> Dictionary:
		return {
			"id": id,
			"type": type,
			"position": position.to_dict(),
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
		for item_data in data["items"]:
			items.append(InventoryItem.new(item_data))

		# Load containers - server sends "servers" field per InventoryData schema
		containers.clear()
		for container_data in data["servers"]:
			containers.append(ServerContainer.new(container_data))

	func to_dict() -> Dictionary:
		var items_array = []
		for item in items:
			items_array.append(item.to_dict())

		var containers_array = []
		for container in containers:
			containers_array.append(container.to_dict())

		return {
			"items": items_array,
			"containers": containers_array
		}

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

# Session start response - matches server StartSessionResponse
class SessionStartResponse extends Resource:
	var player_id: String = ""
	var session: Dictionary = {}  # GameSession object - TODO: type this when we have GameSession class
	# Extracted fields for convenience
	var round: int = 1
	var gold: int = 12
	var current_shop: Array = []  # Array of ShopItem dicts
	var server_containers: Array[ServerContainer] = []  # Array of ServerContainer

	func _init(data: Dictionary):
		# Required fields per server schema
		player_id = data["player_id"]
		session = data["session"]

		# Extract from session for convenience
		round = session["round"]
		gold = session["gold"]
		current_shop = session["current_shop"]

		# Parse server containers from session - typed array
		server_containers.clear()
		for container_data in session["server_containers"]:
			var container := ServerContainer.new(container_data)
			server_containers.append(container)

# Shop refresh response
class ShopRefreshResponse extends Resource:
	var shop: Array[Dictionary] = []  # Array of ShopItem dicts
	var gold: int = 0

	func _init(data: Dictionary):
		shop = data["shop"]
		gold = data["gold"]

# Purchase response - matches server PurchaseResponse
class PurchaseResponse extends Resource:
	var purchased_item: Dictionary = {}  # ShopItem
	var gold: int = 0

	func _init(data: Dictionary):
		# Required fields per server schema
		# Server doesn't send success - HTTP 200 means success
		purchased_item = data["purchased_item"]
		gold = data["gold"]

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
