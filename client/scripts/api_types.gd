extends Resource
class_name APITypes

# Position type - always normalized to dictionary format
class Position extends Resource:
	var x: int = 0
	var y: int = 0

	func _init(data = null):
		if data == null:
			return
		elif data is Array and data.size() >= 2:
			x = data[0]
			y = data[1]
		elif data is Dictionary:
			x = data.get("x", 0)
			y = data.get("y", 0)
		elif data is Vector2 or data is Vector2i:
			x = int(data.x)
			y = int(data.y)

	func to_dict() -> Dictionary:
		return {"x": x, "y": y}

	func to_vector2() -> Vector2:
		return Vector2(x, y)

# Size type
class Size extends Resource:
	var x: int = 1
	var y: int = 1

	func _init(data = null):
		if data == null:
			return
		elif data is Dictionary:
			x = data.get("x", 1)
			y = data.get("y", 1)
		elif data is Array:  # From shape calculation
			x = data[0] if data.size() > 0 else 1
			y = data[1] if data.size() > 1 else 1

	func to_dict() -> Dictionary:
		return {"x": x, "y": y}

# Inventory item
class InventoryItem extends Resource:
	var id: String = ""
	var item_type: String = ""
	var name: String = ""
	var category: String = ""
	var position: Position
	var size: Size

	func _init(data: Dictionary = {}):
		if data.is_empty():
			return

		# Required fields
		id = data["id"]
		item_type = data["item_type"]
		name = data["name"]

		# Optional fields
		if data.has("category"):
			category = data["category"]
		if data.has("position"):
			position = Position.new(data["position"])

		# Calculate size from shape or use size field
		if data.has("size"):
			size = Size.new(data["size"])
		elif data.has("shape") and data["shape"] is Array:
			# Calculate size from shape array
			var max_x = 0
			var max_y = 0
			for coord in data.shape:
				if coord is Array and coord.size() >= 2:
					max_x = max(max_x, coord[0])
					max_y = max(max_y, coord[1])
			size = Size.new({"x": max_x + 1, "y": max_y + 1})
		else:
			size = Size.new()

	func to_dict() -> Dictionary:
		return {
			"id": id,
			"item_type": item_type,
			"name": name,
			"category": category,
			"position": position.to_dict(),
			"size": size.to_dict()
		}

# Container/Server - matches server response
class ServerContainer extends Resource:
	var id: String = ""
	var type: String = ""
	var position: Position
	var width: int = 2
	var height: int = 2

	func _init(data: Dictionary = {}):
		if data.is_empty():
			return

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

	func _init(data: Dictionary = {}):
		if data.is_empty():
			return

		# Load items - required
		items.clear()
		for item_data in data["items"]:
			items.append(InventoryItem.new(item_data))

		# Load containers - try both field names since server might use either
		containers.clear()
		if data.has("containers"):
			for container_data in data["containers"]:
				containers.append(ServerContainer.new(container_data))
		elif data.has("servers"):
			for container_data in data["servers"]:
				containers.append(ServerContainer.new(container_data))
		else:
			push_error("InventoryState missing containers/servers field")

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

# Battle action
class BattleAction extends Resource:
	var time: float = 0.0
	var action: String = ""
	var player: int = 0
	var item_id: String = ""
	var value: int = 0

	func _init(data: Dictionary = {}):
		if data.is_empty():
			return

		# Required fields
		if data.has("t"):
			time = data["t"]
		if data.has("a"):
			action = data["a"]
		# Optional fields
		if data.has("p"):
			player = data["p"]
		if data.has("i"):
			item_id = data["i"]
		if data.has("v"):
			value = data["v"]

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
	var session_update: Dictionary = {}

	func _init(data: Dictionary = {}):
		if data.is_empty():
			return

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

		# Session update data - required
		session_update = data["session_update"]

# Session start response
class SessionStartResponse extends Resource:
	var player_id: String = ""
	var round: int = 1
	var gold: int = 12
	var current_shop: Array = []
	var starting_containers: Array = []  # Array of ServerContainer
	var item_catalog: Dictionary = {}

	func _init(data: Dictionary = {}):
		player_id = data.get("player_id", "")

		# Get session data from nested structure if needed
		var session = data.get("session", data)
		round = session.get("round", 1)
		gold = session.get("gold", 12)
		current_shop = session.get("current_shop", [])
		item_catalog = data.get("item_catalog", {})

		# Parse starting containers
		starting_containers.clear()
		for container_data in data.get("starting_containers", []):
			starting_containers.append(ServerContainer.new(container_data))

# Shop refresh response
class ShopRefreshResponse extends Resource:
	var shop: Array = []
	var gold: int = 0

	func _init(data: Dictionary = {}):
		shop = data.get("shop", [])
		gold = data.get("gold", 0)

# Purchase response
class PurchaseResponse extends Resource:
	var success: bool = false
	var gold: int = 0
	var item: InventoryItem
	var error: String = ""

	func _init(data: Dictionary = {}):
		success = not data.has("error")
		gold = data.get("gold", 0)
		error = data.get("error", "")

		if data.has("item"):
			item = InventoryItem.new(data.get("item"))

# Sell response
class SellResponse extends Resource:
	var success: bool = false
	var gold: int = 0
	var error: String = ""

	func _init(data: Dictionary = {}):
		success = not data.has("error")
		gold = data.get("gold", 0)
		error = data.get("error", "")
