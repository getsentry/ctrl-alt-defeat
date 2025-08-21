extends Control

const APITypes = preload("res://scripts/api_types.gd")

# Game state is pulled from GameStateManager - no local copies

# Grid settings
const ROOM_WIDTH = 9
const ROOM_HEIGHT = 7
const CELL_SIZE = 45  # Default cell size, actual size calculated from container
const CELL_SPACING = 1

# Storage settings
const STORAGE_WIDTH = 12
const STORAGE_HEIGHT = 2

# Runtime calculated cell size
var actual_cell_size: float = CELL_SIZE
var actual_cell_spacing: float = CELL_SPACING

func get_cell_size() -> float:
	return actual_cell_size

func get_cell_spacing() -> float:
	return actual_cell_spacing

func get_cell_total() -> float:
	return actual_cell_size + actual_cell_spacing

func _update_active_grid_for_server(x: int, y: int, pattern: Array):
	"""Update the active grid to mark where server cells are"""
	for py in range(pattern.size()):
		for px in range(pattern[py].size()):
			if pattern[py][px] == 1:
				var gx = x + px
				var gy = y + py
				if gy < ROOM_HEIGHT and gx < ROOM_WIDTH:
					active_grid[gy][gx] = true

# Grid managers
var inventory_grid: GridManager  # Main inventory grid
var storage_grid: GridManager    # Storage grid

# Game state tracking
var active_grid: Array = []  # Tracks which cells have server grids
var item_grid: Array = []    # Tracks items placed on the grid
var servers: Array = []       # Server objects (for tracking)
var items: Array = []         # Item objects

# Legacy references - these now point to GridManager
var server_room_container: Node  # Points to inventory_grid
var storage_container: Node      # Points to storage_grid
var grid_container: Node         # Points to inventory_grid
var grid_cells: Array = []       # Grid cell tracking
var server_visuals: Array = []   # Server visual tracking

# Shop
var shop_items: Array = []

# Mode settings
var read_only_mode: bool = false
var hide_shop: bool = false
var hide_storage: bool = false

# Drag and drop
var dragging_object = null
var drag_offset = Vector2.ZERO
var original_position = Vector2.ZERO
var original_parent = null
var original_grid_pos = Vector2i(-1, -1)
var hover_preview: Panel = null
var valid_placement = false
var last_rotation_time: float = 0.0
var last_drag_position = Vector2.ZERO  # Track last position during drag for placement
const ROTATION_COOLDOWN: float = 0.3  # Seconds between rotations (increased for less sensitivity)

# UI References
var shop_container: Control
var stats_label: Label
var gold_preview_label: Label

# Server types (now just define grid patterns)
var server_types = {
	"rack_2x3": {
		"name": "Rack 2x3",
		"pattern": [[1,1],[1,1],[1,1]],  # 2 wide, 3 tall
		"color": Color(0.3, 0.4, 0.5, 0.3),
		"cost": 8,
		"type": "server"
	},
	"blade_3x2": {
		"name": "Blade 3x2",
		"pattern": [[1,1,1],[1,1,1]],  # 3 wide, 2 tall
		"color": Color(0.4, 0.3, 0.5, 0.3),
		"cost": 8,
		"type": "server"
	},
	"tower_1x4": {
		"name": "Tower 1x4",
		"pattern": [[1],[1],[1],[1]],  # 1 wide, 4 tall
		"color": Color(0.35, 0.45, 0.4, 0.3),
		"cost": 6,
		"type": "server"
	},
	"cube_2x2": {
		"name": "Cube 2x2",
		"pattern": [[1,1],[1,1]],  # 2x2
		"color": Color(0.45, 0.35, 0.4, 0.3),
		"cost": 5,
		"type": "server"
	},
	"L_shape": {
		"name": "L-Server",
		"pattern": [[1,1,0],[1,0,0]],  # L-shaped
		"color": Color(0.4, 0.4, 0.3, 0.3),
		"cost": 6,
		"type": "server"
	}
}


func _ready():
	print("UnifiedGridUI starting...")

	# Set window size for consistency (scaling 1600x1024 to 2560x1600)
	if not OS.has_feature("headless"):
		DisplayServer.window_set_size(Vector2i(2560, 1600))
		get_window().min_size = Vector2i(2560, 1600)
		get_window().max_size = Vector2i(2560, 1600)

	# Connect to API signals for typed responses
	BattleServerAPI.purchase_completed.connect(_on_purchase_completed)

	# State is read directly from GameStateManager, no local copies

	# Initialize UI first
	_initialize_grids()
	_setup_ui()

	# Ensure GridManagers are ready
	await get_tree().process_frame

	# Then load saved inventory if it exists
	var saved_inventory = GameStateManager.get_inventory_state()
	if saved_inventory.has("servers") and saved_inventory.servers.size() > 0:
		_load_saved_inventory(saved_inventory)
	elif GameStateManager.current_round == 1:
		# First round - give player starting containers
		_place_starting_containers()

	if not hide_shop:
		_load_shop_from_state()

func configure(settings: Dictionary):
	read_only_mode = settings.get("read_only", false)
	hide_shop = settings.get("hide_shop", false)
	hide_storage = settings.get("hide_storage", false)

	# Reload UI with new settings
	for child in get_children():
		child.queue_free()

	_setup_ui()

func _place_starting_containers():
	print("Placing starting containers for new game")

	# Check if server provided starting containers
	var containers_to_place = []
	if GameStateManager.starting_containers.size() > 0:
		containers_to_place = GameStateManager.starting_containers
		print("Using server-provided starting containers: %d" % containers_to_place.size())
	else:
		# Default starting containers - 3 adjacent 2x2 containers
		containers_to_place = [
			{"type": "cube_2x2", "position": Vector2i(1, 3)},
			{"type": "cube_2x2", "position": Vector2i(3, 3)},
			{"type": "cube_2x2", "position": Vector2i(5, 3)}
		]
		print("Using default starting containers")

	# Place each container
	for container_info in containers_to_place:
		var container_type_key = container_info["type"]
		var position = container_info["position"]

		# Map server container types to client types
		if container_type_key == "standard_vm":
			container_type_key = "cube_2x2"  # Map server type to client type

		if not server_types.has(container_type_key):
			print("Warning: Unknown container type '%s', using cube_2x2" % container_type_key)
			container_type_key = "cube_2x2"

		var container_type = server_types[container_type_key]
		var x_pos = position.x
		var y_pos = position.y

		# Create the server data
		var server_data = {
			"data": container_type.duplicate(),
			"pos": Vector2i(x_pos, y_pos)
		}

		# Place the server using GridManager
		var server_visual = inventory_grid.place_server(container_type, Vector2i(x_pos, y_pos))
		server_visual.gui_input.connect(_on_server_input.bind(server_visual))
		server_visual.set_meta("is_placed_server", true)

		# Update grid tracking
		_update_active_grid_for_server(x_pos, y_pos, container_type.pattern)

		# Track the server
		servers.append(server_data)

	print("Placed %d starting containers" % containers_to_place.size())

	# Save this initial state
	var initial_state = get_inventory_state()
	GameStateManager.save_inventory_state(initial_state.items, initial_state.servers)

func _load_saved_inventory(saved_data: Dictionary):
	# Wrapper to load saved inventory from GameStateManager
	if saved_data.has("items") and saved_data.has("servers"):
		print("Loading saved inventory with %d servers and %d items" % [
			saved_data.servers.size(),
			saved_data.items.size()
		])
		# Convert to typed InventoryState
		var typed_inventory = APITypes.InventoryState.new(saved_data)
		load_inventory_state(typed_inventory)
		_update_stats()

func load_inventory_state(inventory_data: APITypes.InventoryState):
	# Convert typed inventory to dictionary for internal processing
	var data_dict = inventory_data.to_dict()

	# Load containers - handle both typed objects and dicts
	for server_data in data_dict.get("containers", data_dict.get("servers", [])):
		var pos_x: int
		var pos_y: int
		var width: int
		var height: int
		var server_type: String
		var server_id: String

		# Handle both dictionary and typed object
		if server_data is Dictionary:
			var pos = server_data["position"]
			if pos is Dictionary:
				pos_x = pos["x"]
				pos_y = pos["y"]
			else:  # Array format [x, y]
				pos_x = pos[0]
				pos_y = pos[1]
			width = server_data["width"]
			height = server_data["height"]
			server_type = server_data["type"]
			server_id = server_data["id"]
		else:
			var typed_server: APITypes.ServerContainer = server_data
			pos_x = typed_server.position.x
			pos_y = typed_server.position.y
			width = typed_server.width
			height = typed_server.height
			server_type = typed_server.type
			server_id = typed_server.id

		# Generate pattern from width/height (all cells active for now)
		var pattern = []
		for y in range(height):
			var row = []
			for x in range(width):
				row.append(1)  # All cells active
			pattern.append(row)

		var container_data = {
			"pattern": pattern,
			"width": width,
			"height": height,
			"type": server_type,
			"id": server_id,
			"color": Color(0.3, 0.6, 1.0, 0.7)  # Default blue color for servers
		}
		_place_server_pattern(pos_x, pos_y, container_data)
		servers.append({"data": container_data, "pos": Vector2i(pos_x, pos_y)})

	# Load items
	for item_info in data_dict.items:
		var item_data = {}
		var grid_x = 0
		var grid_y = 0

		# Only handle typed InventoryItem
		var typed_item: APITypes.InventoryItem = item_info as APITypes.InventoryItem
		grid_x = typed_item.position.x
		grid_y = typed_item.position.y

		# Calculate width/height from shape for display
		var max_x = 0
		var max_y = 0
		for coord in typed_item.shape:
			if coord is Array and coord.size() >= 2:
				max_x = max(max_x, coord[0])
				max_y = max(max_y, coord[1])

		item_data = {
			"id": typed_item.id,
			"item_type": typed_item.item_type,
			"name": typed_item.name,
			"category": typed_item.category,
			"shape": typed_item.shape,  # Store shape for validation
			"width": max_x + 1,  # Calculate width from shape
			"height": max_y + 1  # Calculate height from shape
		}

		# Create the item visual
		var item = _create_item(item_data)

		# Place on grid
		item.position = Vector2(grid_x * (CELL_SIZE + CELL_SPACING),
								grid_y * (CELL_SIZE + CELL_SPACING))
		server_room_container.add_child(item)

		# Mark grid cells based on shape
		for offset in item_data.shape:
			if offset is Array and offset.size() >= 2:
				var cell_x = grid_x + offset[0]
				var cell_y = grid_y + offset[1]
				if cell_x >= 0 and cell_y >= 0 and cell_x < ROOM_WIDTH and cell_y < ROOM_HEIGHT:
					item_grid[cell_y][cell_x] = item

		item.set_meta("grid_pos", Vector2(grid_x, grid_y))
		items.append(item)

func get_inventory_state() -> Dictionary:
	var state = {
		"servers": servers.duplicate(),
		"items": []
	}

	# Save item positions
	for item in items:
		if item.has_meta("grid_pos"):
			state.items.append({
				"data": item.get_meta("item_data"),
				"grid_pos": item.get_meta("grid_pos")
			})

	return state

func _initialize_grids():
	active_grid = []
	item_grid = []
	grid_cells = []

	for y in range(ROOM_HEIGHT):
		var active_row = []
		var item_row = []
		var cell_row = []
		for x in range(ROOM_WIDTH):
			active_row.append(false)  # No server grid here initially
			item_row.append(null)      # No item here initially
			cell_row.append(null)      # No visual cell initially
		active_grid.append(active_row)
		item_grid.append(item_row)
		grid_cells.append(cell_row)

func _setup_ui():
	# Check if nodes already exist in the scene
	_create_header()
	_create_shop_panel()
	_create_server_room()
	_create_storage_area()
	_create_controls()

	# Gold preview
	gold_preview_label = Label.new()
	gold_preview_label.add_theme_font_size_override("font_size", 16)
	gold_preview_label.add_theme_color_override("font_color", Color(1.0, 0.85, 0.3))
	gold_preview_label.visible = false
	add_child(gold_preview_label)

	# Hover preview for placement
	hover_preview = Panel.new()
	hover_preview.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hover_preview.visible = false
	var hover_style = StyleBoxFlat.new()
	hover_style.bg_color = Color(0.3, 1.0, 0.3, 0.3)
	hover_style.border_color = Color(0.5, 1.0, 0.5, 0.8)
	hover_style.set_border_width_all(2)
	hover_preview.add_theme_stylebox_override("panel", hover_style)
	add_child(hover_preview)

	print("UI setup complete")

func _create_header():
	# Character stats in bottom-left area (no bounding box, just text)
	if not read_only_mode:
		stats_label = $CharacterStats
		stats_label.text = _get_stats_text()

func _create_shop_panel():
	if hide_shop:
		return
	shop_container = $ShopContainer

func _create_server_room():
	# Panel already exists, just style it
	var room_bg = $InventoryPanel
	var room_style = StyleBoxFlat.new()
	room_style.bg_color = Color(0.05, 0.1, 0.15, 0.2)  # Semi-transparent blue
	room_style.border_color = Color(0.0, 1.0, 1.0, 0.4)  # Cyan border
	room_style.set_border_width_all(2)
	room_style.set_corner_radius_all(4)
	room_bg.add_theme_stylebox_override("panel", room_style)

	# Create inventory grid manager
	var GridManagerClass = preload("res://scripts/GridManager.gd")
	inventory_grid = GridManagerClass.new()
	inventory_grid.position = Vector2(10, 10)  # Small padding inside panel
	inventory_grid.size = room_bg.size - Vector2(20, 20)  # Account for padding
	inventory_grid.setup(ROOM_WIDTH, ROOM_HEIGHT)
	room_bg.add_child(inventory_grid)

	# Set legacy references
	server_room_container = inventory_grid
	grid_container = inventory_grid

	# Initialize grid cells array for compatibility
	for y in range(ROOM_HEIGHT):
		var row = []
		for x in range(ROOM_WIDTH):
			row.append(null)
		grid_cells.append(row)

	# Connect signals
	inventory_grid.gui_input.connect(_on_inventory_input)

func _create_storage_area():
	if hide_storage:
		return

	# Use existing nodes from scene if available
	if has_node("StoragePanel"):
		var storage_bg = $StoragePanel
		var storage_style = StyleBoxFlat.new()
		storage_style.bg_color = Color(0.1, 0.05, 0.15, 0.2)  # Semi-transparent purple
		storage_style.border_color = Color(0.0, 1.0, 1.0, 0.4)  # Cyan border
		storage_style.set_border_width_all(2)
		storage_style.set_corner_radius_all(4)
		storage_bg.add_theme_stylebox_override("panel", storage_style)

		# Create storage grid manager
		var GridManagerClass = preload("res://scripts/GridManager.gd")
		storage_grid = GridManagerClass.new()
		storage_grid.position = Vector2(5, 5)  # Small padding
		storage_grid.size = storage_bg.size - Vector2(10, 10)
		storage_grid.setup(STORAGE_WIDTH, STORAGE_HEIGHT)
		storage_bg.add_child(storage_grid)

		# Set legacy reference
		storage_container = storage_grid

		# Create visual cells for storage
		for y in range(STORAGE_HEIGHT):
			for x in range(STORAGE_WIDTH):
				storage_grid.create_cell_visual(x, y, Color(0.0, 0.1, 0.2, 0.3))

func _create_controls():
	if not read_only_mode:
		if not hide_shop:
			# Use existing RefreshButton from scene if available
			if has_node("RefreshButton"):
				var refresh_btn = $RefreshButton
				if not refresh_btn.pressed.is_connected(_on_refresh_shop):
					refresh_btn.pressed.connect(_on_refresh_shop)
			else:
				# Fallback to creating new
				var refresh_btn = Button.new()
				refresh_btn.name = "RefreshButton"
				refresh_btn.text = "Refresh (1g)"
				refresh_btn.position = Vector2(1950, 200)
				refresh_btn.size = Vector2(120, 40)
				refresh_btn.pressed.connect(_on_refresh_shop)
				add_child(refresh_btn)

		# Use existing ReadyButton from scene if available
		if has_node("ReadyButton"):
			var battle_btn = $ReadyButton
			if not battle_btn.pressed.is_connected(_on_ready_for_battle):
				battle_btn.pressed.connect(_on_ready_for_battle)
		else:
			# Fallback to creating new
			var battle_btn = Button.new()
			battle_btn.name = "ReadyButton"
			battle_btn.text = "Ready for Battle!"
			battle_btn.position = Vector2(1050, 600)
			battle_btn.size = Vector2(150, 40)
			battle_btn.add_theme_font_size_override("font_size", 16)
			battle_btn.pressed.connect(_on_ready_for_battle)
			add_child(battle_btn)

	if not read_only_mode and not hide_shop:
		# HelpText node is already in scene, no need to create
		if not has_node("HelpText"):
			# Fallback if not in scene
			var help = Label.new()
			help.text = "Drag servers to create grid → Place items on any grid cells → Items can span servers"
			help.position = Vector2(300, 605)
			help.add_theme_font_size_override("font_size", 12)
			help.add_theme_color_override("font_color", Color(0.6, 0.6, 0.7))
			add_child(help)

func _load_shop_from_state():
	# Load shop from GameStateManager
	print("Loading shop from state, current_shop size: %d" % GameStateManager.current_shop.size())
	print("Displaying %d shop items from server" % GameStateManager.current_shop.size())
	_display_shop_items(GameStateManager.current_shop)


func _display_shop_items(shop_data: Array):
	# Clear existing shop items (but not the containers/labels)
	for child in shop_container.get_children():
		if child.name.begins_with("ShopItem") and child.get_child_count() > 0:
			for item_child in child.get_children():
				item_child.queue_free()
	shop_items.clear()

	print("Displaying shop items, data size: %d" % shop_data.size())

	# Use the predefined shop item positions from the scene
	var shop_positions = []
	for i in range(1, 6):  # ShopItem1 through ShopItem5
		var item_node = shop_container.get_node_or_null("ShopItem" + str(i))
		var price_node = shop_container.get_node_or_null("ShopPrice" + str(i))
		if item_node and price_node:
			shop_positions.append({"item": item_node, "price": price_node})

	for i in range(min(shop_data.size(), shop_positions.size())):
		if shop_data[i] == null:
			print("  Slot %d: empty" % i)
			# Hide the price label for empty slots
			shop_positions[i].price.visible = false
			continue  # Empty slot

		var item_data = shop_data[i]
		print("  Slot %d: %s (cost: %d)" % [i, item_data.get("name", "Unknown"), item_data.get("cost", 0)])

		# Create shop item and add to the specific position container
		var shop_item = _create_shop_item_from_data(item_data)
		shop_item.position = Vector2.ZERO  # Position relative to container
		shop_positions[i].item.add_child(shop_item)
		shop_items.append(shop_item)

		# Update the price label
		shop_positions[i].price.text = str(item_data.get("cost", 0)) + "g"
		shop_positions[i].price.visible = true

	print("Added %d shop items to container" % shop_items.size())

func _create_shop_item_from_data(data: Dictionary) -> Control:
	var shop_item = Panel.new()
	shop_item.custom_minimum_size = Vector2(200, 140)
	shop_item.size = Vector2(200, 140)

	# Style the panel - minimal/no border for shelf display
	var item_style = StyleBoxFlat.new()
	item_style.bg_color = Color(0.1, 0.05, 0.15, 0.15)  # Very subtle background
	item_style.set_corner_radius_all(4)
	shop_item.add_theme_stylebox_override("panel", item_style)

	# Check if it's a container
	var is_container = data.get("is_container", false)

	# Item visual
	var item_visual = ColorRect.new()
	item_visual.size = Vector2(40, 40)
	item_visual.position = Vector2(10, 15)

	# Use different color for containers
	if is_container:
		item_visual.color = Color(0.5, 0.3, 0.7)  # Purple for containers
	else:
		item_visual.color = _get_color_for_category(data.get("category", "problem"))
	shop_item.add_child(item_visual)

	# Name label
	var name_label = Label.new()
	name_label.text = data.get("name", "Unknown")
	name_label.position = Vector2(60, 10)
	name_label.add_theme_font_size_override("font_size", 12)
	shop_item.add_child(name_label)

	# Size label for containers
	if is_container:
		var size_label = Label.new()
		size_label.text = "%dx%d slots" % [data.get("internal_width", 2), data.get("internal_height", 2)]
		size_label.position = Vector2(60, 25)
		size_label.add_theme_font_size_override("font_size", 10)
		size_label.add_theme_color_override("font_color", Color(0.7, 0.7, 0.8))
		shop_item.add_child(size_label)

	# Cost label - positioned below item
	var cost_label = Label.new()
	cost_label.text = "%d GOLD" % data.get("cost", 5)
	cost_label.position = Vector2(70, 100)
	cost_label.add_theme_font_size_override("font_size", 18)
	cost_label.add_theme_color_override("font_color", Color(1.0, 1.0, 0.0))  # Yellow
	cost_label.add_theme_color_override("font_shadow_color", Color(0.0, 0.0, 0.0))
	cost_label.add_theme_constant_override("shadow_offset_x", 2)
	cost_label.add_theme_constant_override("shadow_offset_y", 2)
	shop_item.add_child(cost_label)

	# Store data and connect input
	shop_item.set_meta("shop_item", true)
	shop_item.set_meta("item_data", data)
	shop_item.set_meta("cost", data.get("cost", 5))

	# Prepare full item data for the handler - include all original fields
	var handler_data = data.duplicate()
	# Add display-specific fields if not present
	if not handler_data.has("width"):
		handler_data["width"] = data.get("internal_width", 2) if is_container else 1
	if not handler_data.has("height"):
		handler_data["height"] = data.get("internal_height", 2) if is_container else 1
	if not handler_data.has("color"):
		handler_data["color"] = Color(0.5, 0.3, 0.7) if is_container else _get_color_for_category(data.get("category", "problem"))
	if not handler_data.has("type"):
		handler_data["type"] = "server" if is_container else "item"  # Mark containers as servers
	if is_container and not handler_data.has("pattern"):
		handler_data["pattern"] = _create_pattern_from_size(data.get("internal_width", 2), data.get("internal_height", 2))

	# Connect input handling for dragging
	shop_item.gui_input.connect(_on_shop_item_input.bind(shop_item, handler_data))

	return shop_item

func _create_pattern_from_size(width: int, height: int) -> Array:
	# Create a pattern array for a container of given size
	var pattern = []
	for y in range(height):
		var row = []
		for x in range(width):
			row.append(1)  # All cells are active in container
		pattern.append(row)
	return pattern

func _get_color_for_category(category: String) -> Color:
	match category:
		"problem":
			return Color(0.9, 0.3, 0.3)
		"defense":
			return Color(0.3, 0.6, 0.9)
		"infrastructure":
			return Color(0.3, 0.9, 0.6)
		"consumable":
			return Color(0.9, 0.6, 0.3)
		_:
			return Color(0.5, 0.5, 0.5)

func _on_shop_item_input(event: InputEvent, shop_item: Panel, item_data: Dictionary):
	if read_only_mode:
		return
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_LEFT:
			if event.pressed:
				_start_dragging_from_shop(shop_item, item_data, event.position)

func _start_dragging_from_shop(shop_item: Panel, item_data: Dictionary, local_pos: Vector2):
	# Don't allow dragging sold items
	if shop_item.modulate.a < 1.0:
		print("This item has already been sold")
		return

	if item_data.get("type", "") == "server":
		dragging_object = _create_server_preview(item_data)
	else:
		dragging_object = _create_item(item_data)

	dragging_object.position = shop_item.global_position
	dragging_object.modulate.a = 0.7
	add_child(dragging_object)

	drag_offset = local_pos
	original_parent = shop_item  # Remember it came from shop
	original_position = Vector2.ZERO  # Not applicable for shop items

	gold_preview_label.text = "-%d gold" % item_data.cost
	gold_preview_label.visible = true
	hover_preview.visible = true

func _create_server_preview(server_data: Dictionary) -> Control:
	var preview = Control.new()
	preview.set_meta("server_data", server_data)
	preview.set_meta("is_server", true)

	# Create visual representation of the pattern
	var pattern = server_data.pattern
	for y in range(pattern.size()):
		for x in range(pattern[y].size()):
			if pattern[y][x] == 1:
				var cell = Panel.new()
				cell.position = Vector2(x * (CELL_SIZE + CELL_SPACING),
									   y * (CELL_SIZE + CELL_SPACING))
				cell.size = Vector2(CELL_SIZE, CELL_SIZE)

				var cell_style = StyleBoxFlat.new()
				cell_style.bg_color = server_data.color
				cell_style.border_color = Color(0.3, 0.4, 0.3, 0.5)
				cell_style.set_border_width_all(1)
				cell.add_theme_stylebox_override("panel", cell_style)

				preview.add_child(cell)

	return preview

func _create_item(item_data: Dictionary) -> Control:
	var container = Control.new()
	# Store original dimensions for rotation
	var rotated_data = item_data.duplicate()
	rotated_data["original_width"] = item_data.get("original_width", item_data.get("width", 1))
	rotated_data["original_height"] = item_data.get("original_height", item_data.get("height", 1))
	rotated_data["rotation"] = item_data.get("rotation", 0)  # 0, 90, 180, 270

	# Ensure we have width and height for display
	if not rotated_data.has("width"):
		rotated_data["width"] = 1
	if not rotated_data.has("height"):
		rotated_data["height"] = 1

	# Ensure we have a color
	if not rotated_data.has("color"):
		rotated_data["color"] = Color(0.3, 0.9, 0.6, 1.0)  # Default green color

	# Apply rotation to dimensions
	if rotated_data.rotation == 90 or rotated_data.rotation == 270:
		rotated_data.width = rotated_data.original_height
		rotated_data.height = rotated_data.original_width

	container.size = Vector2(rotated_data.width * (CELL_SIZE + CELL_SPACING) - CELL_SPACING,
					   rotated_data.height * (CELL_SIZE + CELL_SPACING) - CELL_SPACING)

	# Render each cell individually based on shape
	for offset in rotated_data.shape:
		if offset is Array and offset.size() >= 2:
			var cell_panel = Panel.new()
			cell_panel.position = Vector2(offset[0] * (CELL_SIZE + CELL_SPACING),
										  offset[1] * (CELL_SIZE + CELL_SPACING))
			cell_panel.size = Vector2(CELL_SIZE, CELL_SIZE)

			var cell_style = StyleBoxFlat.new()
			var base_color = rotated_data.get("color", Color(0.3, 0.9, 0.6, 1.0))
			cell_style.bg_color = Color(base_color.r, base_color.g, base_color.b, 0.7)  # Semi-transparent
			cell_style.border_color = Color(0.0, 1.0, 1.0, 0.8)  # Cyan border
			cell_style.set_border_width_all(1)
			cell_style.set_corner_radius_all(3)
			cell_panel.add_theme_stylebox_override("panel", cell_style)
			container.add_child(cell_panel)

	var label = Label.new()
	label.text = rotated_data.name
	label.position = Vector2(3, 3)
	label.add_theme_font_size_override("font_size", 10)
	label.add_theme_color_override("font_color", Color(1.0, 1.0, 1.0))
	label.add_theme_color_override("font_shadow_color", Color(0.0, 0.0, 0.0))
	label.add_theme_constant_override("shadow_offset_x", 1)
	label.add_theme_constant_override("shadow_offset_y", 1)
	# Rotate label with item
	label.rotation_degrees = rotated_data.rotation
	if rotated_data.rotation == 90:
		label.position = Vector2(container.size.x - 15, 3)
	elif rotated_data.rotation == 180:
		label.position = Vector2(container.size.x - 3, container.size.y - 15)
	elif rotated_data.rotation == 270:
		label.position = Vector2(15, container.size.y - 3)
	container.add_child(label)

	container.set_meta("item_data", rotated_data)
	container.set_meta("is_item", true)
	container.gui_input.connect(_on_item_input.bind(container))

	return container

func _on_inventory_input(event: InputEvent):
	"""Handle input on the inventory grid"""
	if read_only_mode:
		return
	# Check if we clicked on a server or item
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_LEFT:
			if event.pressed:
				# Get mouse position safely
				var global_mouse = get_global_mouse_position()
				var local_pos = inventory_grid.to_local(global_mouse) if inventory_grid.is_inside_tree() else Vector2.ZERO
				var grid_pos = inventory_grid.pixel_to_grid(local_pos)
				# Check for items at this position
				if grid_pos in inventory_grid.items:
					_start_dragging_item(inventory_grid.items[grid_pos], event.position)
				# Check for servers at this position
				elif grid_pos in inventory_grid.servers:
					_start_dragging_server(inventory_grid.servers[grid_pos], event.position)

func _on_server_input(event: InputEvent, server: Control):
	if read_only_mode:
		return
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_LEFT:
			if event.pressed:
				_start_dragging_server(server, event.position)

func _start_dragging_server(server: Control, local_pos: Vector2):
	# Check if server is empty
	var server_data = server.get_meta("server_data")
	var grid_pos = server.get_meta("grid_pos")
	var pattern = server_data.pattern

	# Check if any items are on this server
	for py in range(pattern.size()):
		for px in range(pattern[py].size()):
			if pattern[py][px] == 1:
				var gx = grid_pos.x + px
				var gy = grid_pos.y + py
				if item_grid[gy][gx] != null:
					print("Cannot move server with items on it!")
					return

	# Clear the grid cells
	for py in range(pattern.size()):
		for px in range(pattern[py].size()):
			if pattern[py][px] == 1:
				var gx = grid_pos.x + px
				var gy = grid_pos.y + py
				active_grid[gy][gx] = false
				if grid_cells[gy][gx]:
					grid_cells[gy][gx].queue_free()
					grid_cells[gy][gx] = null

	# Start dragging
	dragging_object = server
	drag_offset = local_pos
	original_position = server.position
	original_parent = server_room_container
	original_grid_pos = grid_pos
	server.modulate.a = 0.7

	if server.get_parent() != self:
		var global_pos = server.global_position
		server.get_parent().remove_child(server)
		add_child(server)
		server.global_position = global_pos

	hover_preview.visible = true

func _on_item_input(event: InputEvent, item: Panel):
	if read_only_mode:
		return
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_LEFT:
			if event.pressed:
				_start_dragging_item(item, event.position)

func _start_dragging_item(item: Panel, local_pos: Vector2):
	# Clear from grid
	if item.has_meta("grid_pos"):
		var grid_pos = item.get_meta("grid_pos")
		var item_data = item.get_meta("item_data")
		for dy in range(item_data.height):
			for dx in range(item_data.width):
				if grid_pos.y + dy < ROOM_HEIGHT and grid_pos.x + dx < ROOM_WIDTH:
					item_grid[grid_pos.y + dy][grid_pos.x + dx] = null
		original_grid_pos = grid_pos

	dragging_object = item
	drag_offset = local_pos
	original_position = item.position
	original_parent = item.get_parent()
	item.modulate.a = 0.7

	if item.get_parent() != self:
		var global_pos = item.global_position
		item.get_parent().remove_child(item)
		add_child(item)
		item.global_position = global_pos

	hover_preview.visible = true

func _stop_dragging(drop_position: Vector2 = Vector2.ZERO):
	if not dragging_object:
		print("DEBUG: No dragging_object to stop!")
		return

	dragging_object.modulate.a = 1.0

	var placed = false

	if dragging_object.has_meta("is_server"):
		placed = _try_place_server(dragging_object, drop_position)
	elif dragging_object.has_meta("is_placed_server"):
		placed = _try_move_server(dragging_object, drop_position)
	elif dragging_object.has_meta("is_item"):
		placed = _try_place_item(dragging_object, drop_position)

	if not placed:
		# Return to original position based on where it came from
		if original_parent:
			if original_parent.has_meta("shop_item"):
				# Item was from shop - just delete the preview
				dragging_object.queue_free()
			elif original_parent == server_room_container:
				# Item was on grid - restore it
				if original_grid_pos.x >= 0:
					var item_data = dragging_object.get_meta("item_data")
					for dy in range(item_data.height):
						for dx in range(item_data.width):
							if original_grid_pos.y + dy < ROOM_HEIGHT and original_grid_pos.x + dx < ROOM_WIDTH:
								item_grid[original_grid_pos.y + dy][original_grid_pos.x + dx] = dragging_object
					dragging_object.position = original_position
					if dragging_object.get_parent() != server_room_container:
						dragging_object.get_parent().remove_child(dragging_object)
						server_room_container.add_child(dragging_object)
			elif original_parent == storage_container:
				# Item was in storage - restore it
				dragging_object.position = original_position
				if dragging_object.get_parent() != storage_container:
					dragging_object.get_parent().remove_child(dragging_object)
					storage_container.add_child(dragging_object)
		else:
			# No original parent (shouldn't happen) - delete it
			dragging_object.queue_free()

	gold_preview_label.visible = false
	hover_preview.visible = false
	dragging_object = null
	original_grid_pos = Vector2i(-1, -1)
	original_parent = null
	last_drag_position = Vector2.ZERO  # Clear saved position

func _try_place_server(server_preview: Control, drop_position: Vector2 = Vector2.ZERO) -> bool:
	var global_pos = drop_position if drop_position != Vector2.ZERO else get_global_mouse_position()
	# Convert global position to local position relative to the grid
	var mouse_pos = Vector2.ZERO
	if inventory_grid and inventory_grid.is_inside_tree():
		# Convert global to local position relative to inventory_grid's global position
		mouse_pos = global_pos - inventory_grid.global_position
	else:
		mouse_pos = global_pos
	var room_bounds = Vector2(ROOM_WIDTH * (CELL_SIZE + CELL_SPACING),
							  ROOM_HEIGHT * (CELL_SIZE + CELL_SPACING))

	if mouse_pos.x >= 0 and mouse_pos.x < room_bounds.x and \
	   mouse_pos.y >= 0 and mouse_pos.y < room_bounds.y:

		var server_data = server_preview.get_meta("server_data")
		var grid_x = int((mouse_pos.x + CELL_SIZE/2) / (CELL_SIZE + CELL_SPACING))
		var grid_y = int((mouse_pos.y + CELL_SIZE/2) / (CELL_SIZE + CELL_SPACING))

		# Check if pattern fits
		var pattern = server_data.pattern
		if _can_place_server_pattern(grid_x, grid_y, pattern):
			# Pay for it if from shop
			if original_parent and original_parent.has_meta("shop_item"):
				if GameStateManager.gold < server_data.cost:
					print("Not enough gold!")
					return false
				GameStateManager.gold -= server_data.cost
				_update_stats()

			# Place server cells
			_place_server_pattern(grid_x, grid_y, server_data)

			# Remove preview
			server_preview.queue_free()

			if original_parent and original_parent.has_meta("shop_item"):
				servers.append({"data": server_data, "pos": Vector2i(grid_x, grid_y)})

			return true

	return false

func _can_place_server_pattern(x: int, y: int, pattern: Array) -> bool:
	for py in range(pattern.size()):
		for px in range(pattern[py].size()):
			if pattern[py][px] == 1:
				var gx = x + px
				var gy = y + py
				if gx < 0 or gx >= ROOM_WIDTH or gy < 0 or gy >= ROOM_HEIGHT:
					return false
				if active_grid[gy][gx]:
					return false
	return true

func _place_server_pattern(x: int, y: int, server_data: Dictionary):
	var pattern = server_data.pattern

	# Use GridManager if available
	if inventory_grid:
		var server_visual = inventory_grid.place_server(server_data, Vector2i(x, y))
		server_visual.gui_input.connect(_on_server_input.bind(server_visual))
		server_visual.set_meta("is_placed_server", true)
		server_visuals.append(server_visual)

		# Update active grid
		_update_active_grid_for_server(x, y, pattern)
		return

	# Fallback for when GridManager isn't ready yet
	var server_visual = Control.new()
	server_visual.position = Vector2(x * (CELL_SIZE + CELL_SPACING),
									 y * (CELL_SIZE + CELL_SPACING))
	server_visual.set_meta("server_data", server_data)
	server_visual.set_meta("grid_pos", Vector2i(x, y))
	server_visual.set_meta("is_placed_server", true)
	server_visual.gui_input.connect(_on_server_input.bind(server_visual))

	# Calculate server size
	var width = pattern[0].size()
	var height = pattern.size()
	server_visual.size = Vector2(width * (CELL_SIZE + CELL_SPACING) - CELL_SPACING,
								 height * (CELL_SIZE + CELL_SPACING) - CELL_SPACING)

	# Add thick border to show server bounds
	var server_panel = Panel.new()
	server_panel.position = Vector2.ZERO
	server_panel.size = server_visual.size
	server_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE

	var server_style = StyleBoxFlat.new()
	server_style.bg_color = Color(0, 0, 0, 0)  # Transparent background
	server_style.border_color = server_data.color
	server_style.border_color.a = 0.8
	server_style.set_border_width_all(3)  # Thick border
	server_panel.add_theme_stylebox_override("panel", server_style)
	server_visual.add_child(server_panel)

	for py in range(pattern.size()):
		for px in range(pattern[py].size()):
			if pattern[py][px] == 1:
				var gx = x + px
				var gy = y + py

				# Mark as active
				active_grid[gy][gx] = true

				# Create visual cell
				var cell = Panel.new()
				cell.position = Vector2(gx * (CELL_SIZE + CELL_SPACING),
									   gy * (CELL_SIZE + CELL_SPACING))
				cell.size = Vector2(CELL_SIZE, CELL_SIZE)
				cell.mouse_filter = Control.MOUSE_FILTER_IGNORE

				var cell_style = StyleBoxFlat.new()
				cell_style.bg_color = Color(0.0, 0.1, 0.2, 0.2)  # Semi-transparent blue
				cell_style.border_color = Color(0.0, 1.0, 1.0, 0.6)  # Cyan border
				cell_style.set_border_width_all(1)
				cell.add_theme_stylebox_override("panel", cell_style)

				grid_container.add_child(cell)
				grid_cells[gy][gx] = cell

	server_room_container.add_child(server_visual)
	server_visuals.append(server_visual)

func _try_place_item(item: Control, drop_position: Vector2 = Vector2.ZERO) -> bool:
	var item_data = item.get_meta("item_data")

	# Use provided drop position, fallback to saved position or mouse
	var global_pos = drop_position
	if global_pos == Vector2.ZERO:
		global_pos = last_drag_position if last_drag_position != Vector2.ZERO else get_global_mouse_position()
	# Convert global position to local position relative to the grid
	var mouse_pos = Vector2.ZERO
	if inventory_grid and inventory_grid.is_inside_tree():
		# Convert global to local position relative to inventory_grid's global position
		mouse_pos = global_pos - inventory_grid.global_position
	else:
		mouse_pos = global_pos
	var room_bounds = Vector2(ROOM_WIDTH * (CELL_SIZE + CELL_SPACING),
							  ROOM_HEIGHT * (CELL_SIZE + CELL_SPACING))
	if mouse_pos.x >= 0 and mouse_pos.x < room_bounds.x and \
	   mouse_pos.y >= 0 and mouse_pos.y < room_bounds.y:

		var grid_x = int((mouse_pos.x + CELL_SIZE/2) / (CELL_SIZE + CELL_SPACING))
		var grid_y = int((mouse_pos.y + CELL_SIZE/2) / (CELL_SIZE + CELL_SPACING))

		# Use shape-based validation if shape is available
		var can_place = _can_place_item_with_shape(grid_x, grid_y, item_data.shape)

		if can_place:
			# Pay if from shop
			if original_parent and original_parent.has_meta("shop_item"):
				if GameStateManager.gold < item_data.cost:
					print("Not enough gold!")
					return false

				# Call server to purchase item
				var item_id = original_parent.get_meta("item_data").get("id", "")
				if item_id != "":
					BattleServerAPI.purchase_item(item_id, [grid_x, grid_y])

					# Mark item as sold in shop display
					for i in range(shop_items.size()):
						var shop_item = shop_items[i]
						if shop_item == original_parent:
							# Update the shop data to mark as sold
							if i < GameStateManager.current_shop.size():
								GameStateManager.current_shop[i] = null
							# Update visual to show as sold
							original_parent.modulate = Color(0.5, 0.5, 0.5, 0.5)
							var sold_label = Label.new()
							sold_label.text = "SOLD"
							sold_label.position = Vector2(70, 25)
							sold_label.add_theme_font_size_override("font_size", 16)
							sold_label.add_theme_color_override("font_color", Color(1.0, 0.3, 0.3))
							original_parent.add_child(sold_label)
							break

				GameStateManager.gold -= item_data.cost
				_update_stats()

			# Place item
			item.position = Vector2(grid_x * (CELL_SIZE + CELL_SPACING),
								   grid_y * (CELL_SIZE + CELL_SPACING))

			if item.get_parent() != server_room_container:
				item.get_parent().remove_child(item)
				server_room_container.add_child(item)

			# Mark grid cells
			for dy in range(item_data.height):
				for dx in range(item_data.width):
					item_grid[grid_y + dy][grid_x + dx] = item

			item.set_meta("grid_pos", Vector2i(grid_x, grid_y))

			if original_parent and original_parent.has_meta("shop_item"):
				items.append(item)

			return true

	# Check storage
	var storage_global_pos = drop_position if drop_position != Vector2.ZERO else get_global_mouse_position()
	# Convert to storage local position safely
	var storage_mouse = Vector2.ZERO
	if storage_grid:
		storage_mouse = storage_grid.to_local(storage_global_pos) if storage_grid.is_inside_tree() else storage_global_pos
	else:
		storage_mouse = storage_global_pos
	if storage_mouse.x >= 0 and storage_mouse.x < storage_container.size.x and \
	   storage_mouse.y >= 0 and storage_mouse.y < storage_container.size.y:

		# Pay if from shop
		if original_parent and original_parent.has_meta("shop_item"):
			if GameStateManager.gold < item_data.cost:
				print("Not enough gold!")
				return false

			# Call server to purchase item (storage placement)
			var item_id = original_parent.get_meta("item_data").get("id", "")
			if item_id != "":
				BattleServerAPI.purchase_item(item_id, "storage")

				# Mark item as sold in shop display
				for i in range(shop_items.size()):
					var shop_item = shop_items[i]
					if shop_item == original_parent:
						# Update the shop data to mark as sold
						if i < GameStateManager.current_shop.size():
							GameStateManager.current_shop[i] = null
						# Update visual to show as sold
						original_parent.modulate = Color(0.5, 0.5, 0.5, 0.5)
						var sold_label = Label.new()
						sold_label.text = "SOLD"
						sold_label.position = Vector2(70, 25)
						sold_label.add_theme_font_size_override("font_size", 16)
						sold_label.add_theme_color_override("font_color", Color(1.0, 0.3, 0.3))
						original_parent.add_child(sold_label)
						break

			GameStateManager.gold -= item_data.cost
			_update_stats()

		if item.get_parent() != storage_container:
			item.get_parent().remove_child(item)
			storage_container.add_child(item)

		item.position = storage_mouse - drag_offset
		item.position.x = clamp(item.position.x, 0, storage_container.size.x - item.size.x)
		item.position.y = clamp(item.position.y, 0, storage_container.size.y - item.size.y)

		if item.has_meta("grid_pos"):
			item.remove_meta("grid_pos")

		if original_parent and original_parent.has_meta("shop_item"):
			items.append(item)

		return true

	return false

func _can_place_item_on_grid(x: int, y: int, width: int, height: int) -> bool:
	# Legacy rectangular check - kept for compatibility
	if x < 0 or y < 0 or x + width > ROOM_WIDTH or y + height > ROOM_HEIGHT:
		return false

	for dy in range(height):
		for dx in range(width):
			# Must have active grid cell
			if not active_grid[y + dy][x + dx]:
				return false
			# Must not have another item
			if item_grid[y + dy][x + dx] != null:
				return false

	return true

func _can_place_item_with_shape(x: int, y: int, shape: Array) -> bool:
	# Check if item with given shape can be placed at position
	for offset in shape:
		if offset is Array and offset.size() >= 2:
			var cell_x = x + offset[0]
			var cell_y = y + offset[1]

			# Check bounds
			if cell_x < 0 or cell_y < 0 or cell_x >= ROOM_WIDTH or cell_y >= ROOM_HEIGHT:
				return false

			# Must have active grid cell
			if not active_grid[cell_y][cell_x]:
				return false

			# Must not have another item
			if item_grid[cell_y][cell_x] != null:
				return false

	return true

func _input(event):
	# Handle mouse release globally to drop items
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_LEFT and not event.pressed:
			_stop_dragging(event.global_position)
		# Handle rotation with mouse wheel - only on initial press, with cooldown
		elif (event.button_index == MOUSE_BUTTON_WHEEL_UP or event.button_index == MOUSE_BUTTON_WHEEL_DOWN):
			# Only process if pressed (not released) and cooldown has passed
			if event.pressed:
				var current_time = Time.get_ticks_msec() / 1000.0
				if current_time - last_rotation_time >= ROTATION_COOLDOWN:
					if event.button_index == MOUSE_BUTTON_WHEEL_UP:
						_rotate_dragging_item(true)  # Clockwise
					else:
						_rotate_dragging_item(false)  # Counter-clockwise
					last_rotation_time = current_time

	# Handle dragging motion
	if dragging_object and event is InputEventMouseMotion:
		dragging_object.global_position = get_global_mouse_position() - drag_offset
		last_drag_position = event.global_position  # Save position for placement

		if gold_preview_label.visible:
			gold_preview_label.position = get_global_mouse_position() + Vector2(10, -20)

		# Update hover preview
		_update_hover_preview()

func _update_hover_preview(global_pos: Vector2 = Vector2.ZERO):
	if not dragging_object:
		hover_preview.visible = false
		return

	if global_pos == Vector2.ZERO:
		global_pos = get_global_mouse_position()
	# Convert global position to local position relative to the grid
	var mouse_pos = Vector2.ZERO
	if inventory_grid and inventory_grid.is_inside_tree():
		# Convert global to local position relative to inventory_grid's global position
		mouse_pos = global_pos - inventory_grid.global_position
	else:
		mouse_pos = global_pos
	var room_bounds = Vector2(ROOM_WIDTH * (CELL_SIZE + CELL_SPACING),
							  ROOM_HEIGHT * (CELL_SIZE + CELL_SPACING))

	if mouse_pos.x >= 0 and mouse_pos.x < room_bounds.x and \
	   mouse_pos.y >= 0 and mouse_pos.y < room_bounds.y:

		var grid_x = int((mouse_pos.x + CELL_SIZE/2) / (CELL_SIZE + CELL_SPACING))
		var grid_y = int((mouse_pos.y + CELL_SIZE/2) / (CELL_SIZE + CELL_SPACING))

		if dragging_object.has_meta("is_server"):
			var server_data = dragging_object.get_meta("server_data")
			var pattern = server_data.pattern

			valid_placement = _can_place_server_pattern(grid_x, grid_y, pattern)

			# Show preview for pattern
			var width = pattern[0].size()
			var height = pattern.size()
			hover_preview.position = server_room_container.global_position + \
									 Vector2(grid_x * (CELL_SIZE + CELL_SPACING),
											grid_y * (CELL_SIZE + CELL_SPACING))
			hover_preview.size = Vector2(width * (CELL_SIZE + CELL_SPACING) - CELL_SPACING,
										 height * (CELL_SIZE + CELL_SPACING) - CELL_SPACING)

		elif dragging_object.has_meta("is_placed_server"):
			var server_data = dragging_object.get_meta("server_data")
			var pattern = server_data.pattern

			valid_placement = _can_place_server_pattern(grid_x, grid_y, pattern)

			# Show preview for pattern
			var width = pattern[0].size()
			var height = pattern.size()
			hover_preview.position = server_room_container.global_position + \
									 Vector2(grid_x * (CELL_SIZE + CELL_SPACING),
											grid_y * (CELL_SIZE + CELL_SPACING))
			hover_preview.size = Vector2(width * (CELL_SIZE + CELL_SPACING) - CELL_SPACING,
										 height * (CELL_SIZE + CELL_SPACING) - CELL_SPACING)

		elif dragging_object.has_meta("is_item"):
			var item_data = dragging_object.get_meta("item_data")

			valid_placement = _can_place_item_on_grid(grid_x, grid_y, item_data.width, item_data.height)

			hover_preview.position = server_room_container.global_position + \
									 Vector2(grid_x * (CELL_SIZE + CELL_SPACING),
											grid_y * (CELL_SIZE + CELL_SPACING))
			hover_preview.size = Vector2(item_data.width * (CELL_SIZE + CELL_SPACING) - CELL_SPACING,
										 item_data.height * (CELL_SIZE + CELL_SPACING) - CELL_SPACING)

		# Update color based on validity
		var hover_style = hover_preview.get_theme_stylebox("panel") as StyleBoxFlat
		if valid_placement:
			hover_style.bg_color = Color(0.3, 1.0, 0.3, 0.3)
			hover_style.border_color = Color(0.5, 1.0, 0.5, 0.8)
		else:
			hover_style.bg_color = Color(1.0, 0.3, 0.3, 0.3)
			hover_style.border_color = Color(1.0, 0.5, 0.5, 0.8)

		hover_preview.visible = true
	else:
		hover_preview.visible = false

func _get_stats_text() -> String:
	return "Gold: %d | Round: %d | Health: %d/%d" % [
		GameStateManager.gold,
		GameStateManager.current_round,
		GameStateManager.player_health,
		GameStateManager.max_player_health
	]

func _update_stats():
	if stats_label:
		stats_label.text = _get_stats_text()

func _on_purchase_completed(response: APITypes.PurchaseResponse):
	# Update gold from server response
	if response != null:
		GameStateManager.gold = response.gold
		_update_stats()

func _on_refresh_shop():
	if GameStateManager.gold >= 1:
		print("Refreshing shop from server...")
		# Call the real server to refresh shop
		var response = await BattleServerAPI.refresh_shop(GameStateManager.current_round)
		if response != null and response.shop.size() > 0:
			GameStateManager.gold = response.gold  # Server manages gold deduction
			_update_stats()
			_display_shop_items(response.shop)
			GameStateManager.current_shop = response.shop
		else:
			print("Failed to refresh shop from server")

func _try_move_server(server: Control, drop_position: Vector2 = Vector2.ZERO) -> bool:
	var global_pos = drop_position if drop_position != Vector2.ZERO else get_global_mouse_position()
	# Convert global position to local position relative to the grid
	var mouse_pos = Vector2.ZERO
	if inventory_grid and inventory_grid.is_inside_tree():
		# Convert global to local position relative to inventory_grid's global position
		mouse_pos = global_pos - inventory_grid.global_position
	else:
		mouse_pos = global_pos
	var room_bounds = Vector2(ROOM_WIDTH * (CELL_SIZE + CELL_SPACING),
							  ROOM_HEIGHT * (CELL_SIZE + CELL_SPACING))

	if mouse_pos.x >= 0 and mouse_pos.x < room_bounds.x and \
	   mouse_pos.y >= 0 and mouse_pos.y < room_bounds.y:

		var server_data = server.get_meta("server_data")
		var grid_x = int((mouse_pos.x + CELL_SIZE/2) / (CELL_SIZE + CELL_SPACING))
		var grid_y = int((mouse_pos.y + CELL_SIZE/2) / (CELL_SIZE + CELL_SPACING))

		# Check if pattern fits at new location
		var pattern = server_data.pattern
		if _can_place_server_pattern(grid_x, grid_y, pattern):
			# Place server at new location
			_place_server_pattern(grid_x, grid_y, server_data)

			# Update server entry in list
			for s in servers:
				if s.pos == original_grid_pos:
					s.pos = Vector2i(grid_x, grid_y)
					break

			# Remove old visual
			server.queue_free()

			return true
		else:
			# Restore at original position
			var orig_data = server.get_meta("server_data")
			_place_server_pattern(original_grid_pos.x, original_grid_pos.y, orig_data)
			server.position = original_position
			if server.get_parent() != server_room_container:
				server.get_parent().remove_child(server)
				server_room_container.add_child(server)
			return true

	return false

func _on_ready_for_battle():
	# Save current inventory state
	var inventory_state = get_inventory_state()

	# Make sure we're passing the actual inventory data, not the raw objects
	var items_data = []
	for item in items:
		if item.has_meta("grid_pos") and item.has_meta("item_data"):
			items_data.append({
				"data": item.get_meta("item_data"),
				"grid_pos": item.get_meta("grid_pos")
			})

	GameStateManager.save_inventory_state(items_data, servers)

	# Submit battle to server
	var battle_response = await BattleServerAPI.submit_battle(inventory_state)

	# Check if battle request failed (null result indicates error)
	if battle_response == null:
		push_error("Battle request failed")
		# In tests, fail immediately
		if OS.get_environment("BATTLE_SERVER_URL") != "":
			assert(false, "Battle request failed")
		return

	# Update game state with results
	GameStateManager.update_after_battle(battle_response)

	# Check if we have battle events to play
	if GameStateManager.last_battle_events.size() == 0:
		push_error("Server returned battle result with no events")
		assert(false, "Cannot start battle without events")
		return

	# Go to battle visualization screen
	get_tree().change_scene_to_file("res://scenes/BattleScreen.tscn")

	# Old simulation code (can be removed once battle is fully integrated)
	var active_items = 0
	var total_attack = 0
	var total_defense = 0

	# Count items on grid (not in storage)
	for y in range(ROOM_HEIGHT):
		for x in range(ROOM_WIDTH):
			if item_grid[y][x] != null and not item_grid[y][x] in items:
				continue  # Skip duplicates
			if item_grid[y][x] != null:
				var item_data = item_grid[y][x].get_meta("item_data")
				total_attack += item_data.get("attack", 0)
				total_defense += item_data.get("defense", 0)
				active_items += 1

	print("Battle: %d servers, %d active items" % [servers.size(), active_items])
	print("Stats: ATK %d, DEF %d" % [total_attack, total_defense])

func _rotate_dragging_item(clockwise: bool):
	if not dragging_object or not dragging_object.has_meta("is_item"):
		return

	if read_only_mode:
		return

	# Additional check to prevent rotation spam
	if not dragging_object.visible:
		return

	var item_data = dragging_object.get_meta("item_data")
	var current_rotation = item_data.get("rotation", 0)

	# Calculate new rotation
	if clockwise:
		current_rotation = (current_rotation + 90) % 360
	else:
		current_rotation = (current_rotation - 90 + 360) % 360

	item_data.rotation = current_rotation

	# Swap width and height if needed
	if current_rotation == 90 or current_rotation == 270:
		item_data.width = item_data.original_height
		item_data.height = item_data.original_width
	else:
		item_data.width = item_data.original_width
		item_data.height = item_data.original_height

	# Update item size
	dragging_object.size = Vector2(item_data.width * (CELL_SIZE + CELL_SPACING) - CELL_SPACING,
								   item_data.height * (CELL_SIZE + CELL_SPACING) - CELL_SPACING)

	# Update label rotation
	for child in dragging_object.get_children():
		if child is Label:
			child.rotation_degrees = current_rotation
			# Adjust label position based on rotation
			if current_rotation == 0:
				child.position = Vector2(3, 3)
			elif current_rotation == 90:
				child.position = Vector2(dragging_object.size.x - 15, 3)
			elif current_rotation == 180:
				child.position = Vector2(dragging_object.size.x - 3, dragging_object.size.y - 15)
			elif current_rotation == 270:
				child.position = Vector2(15, dragging_object.size.y - 3)

	dragging_object.set_meta("item_data", item_data)

	# Update hover preview
	_update_hover_preview()

	print("Rotated item to %d degrees" % current_rotation)
