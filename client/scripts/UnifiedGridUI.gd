extends Control

const APITypes = preload("res://scripts/api_types.gd")

# Game state is pulled from GameStateManager - no local copies

# Grid settings
const ROOM_WIDTH = 9   # Fixed grid width
const ROOM_HEIGHT = 7  # Fixed grid height
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

# Signal handlers for InventoryGrid
func _on_item_placed(item_data, grid_pos: Vector2i):
	"""Called when an item is placed in the inventory grid"""
	# Save the inventory state
	_save_current_state()


func _on_item_removed(item_data, grid_pos: Vector2i):
	"""Called when an item is removed from the inventory grid"""
	# Save the inventory state
	_save_current_state()


func _on_item_sold(item_data):
	"""Called when an item is sold (right-clicked)"""
	# TODO: Call server to sell item
	print("Selling item: ", item_data.name if item_data.has("name") else "Unknown")

func _on_item_moved(item_uid: String, from_pos: Vector2i, to_pos: Vector2i):
	"""Called after an item has been successfully moved within the inventory"""
	print("Item %s successfully moved from %s to %s" % [item_uid, from_pos, to_pos])
	# Save the current state to GameStateManager
	_save_current_state()


func _save_current_state():
	"""Save the current inventory state to GameStateManager"""
	var state = inventory_grid.get_inventory_state()
	GameStateManager.save_inventory_state(state.items, state.servers)

func _process(_delta):
	# Update drag preview position if dragging from shop
	if drag_preview:
		drag_preview.global_position = get_global_mouse_position() - drag_preview.size / 2

		# Show hover preview on the inventory grid
		if dragging_shop_item and inventory_grid:
			var mouse_pos = inventory_grid.get_local_mouse_position()
			var grid_pos = inventory_grid.pixel_to_grid(mouse_pos)

			# Update the inventory grid's hover preview for shop items
			inventory_grid.show_hover_preview_for_shop(dragging_shop_data, grid_pos)

func _input(event):
	# Handle shop item drop
	if dragging_shop_item and event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_LEFT and not event.pressed:
			_end_shop_drag()

# Grid managers
var inventory_grid: InventoryGrid  # Main inventory grid
var storage_grid: InventoryGrid    # Storage grid

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

# UI state
var hover_preview: Panel = null  # For shop preview

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

	# Skip inventory loading for read-only mode (BattleScreen will load its own)
	if read_only_mode:
		print("Read-only mode - skipping inventory initialization")
		return

	# Then load saved inventory if it exists
	var saved_inventory = GameStateManager.get_inventory_state()
	print("DEBUG: Loading saved inventory on UnifiedGridUI startup:")
	print("  Items: %d" % saved_inventory.get("items", []).size())
	print("  Servers: %d" % saved_inventory.get("servers", []).size())
	if saved_inventory.get("items", []).size() > 0:
		for item in saved_inventory.items:
			if item is Dictionary:
				print("    Item (dict): %s at %s" % [item.get("name", "unknown"), item.get("position", "?")])
			else:
				print("    Item (object): %s" % item)
	_load_saved_inventory(saved_inventory)


	if not hide_shop:
		_load_shop_from_state()

func configure(settings: Dictionary):
	read_only_mode = settings.get("read_only", false)
	hide_shop = settings.get("hide_shop", false)
	hide_storage = settings.get("hide_storage", false)

	# Settings will be applied in _ready() if not ready yet
	if not is_node_ready():
		return

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
	# Delegate to InventoryGrid
	if inventory_grid:
		inventory_grid.load_inventory_state(inventory_data)

	# Update our tracking arrays for compatibility
	servers.clear()
	for container_data in inventory_grid.containers:
		servers.append({
			"data": container_data.data,
			"pos": container_data.position
		})

	items = inventory_grid.items.duplicate()

func get_inventory_state() -> Dictionary:
	# Delegate to InventoryGrid
	if inventory_grid:
		return inventory_grid.get_inventory_state()
	return {"servers": [], "items": []}

func _initialize_grids():
	# Legacy arrays kept for compatibility but not actively used
	active_grid = []
	item_grid = []
	grid_cells = []

	for y in range(ROOM_HEIGHT):
		var active_row = []
		var item_row = []
		var cell_row = []
		for x in range(ROOM_WIDTH):
			active_row.append(false)
			item_row.append(null)
			cell_row.append(null)
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

	# Hide elements based on configuration
	if has_node("ShopContainer") and hide_shop:
		$ShopContainer.visible = false
	if has_node("StorageContainer") and hide_storage:
		$StorageContainer.visible = false
	if has_node("CharacterStats") and (hide_shop or read_only_mode):
		$CharacterStats.visible = false

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

	# Create inventory grid to fill the panel
	inventory_grid = InventoryGrid.new()
	var padding = 20  # Padding inside panel
	inventory_grid.position = Vector2(padding, padding)

	# Calculate cell size based on panel size and desired grid dimensions
	var panel_size = room_bg.size - Vector2(padding * 2, padding * 2)
	var cell_width = (panel_size.x - (ROOM_WIDTH - 1) * CELL_SPACING) / ROOM_WIDTH
	var cell_height = (panel_size.y - (ROOM_HEIGHT - 1) * CELL_SPACING) / ROOM_HEIGHT
	var cell_size = min(cell_width, cell_height)  # Use the smaller to maintain square cells

	inventory_grid.configure(ROOM_WIDTH, ROOM_HEIGHT, cell_size, CELL_SPACING)
	inventory_grid.title = ""  # Title is already in the UI
	inventory_grid.read_only = read_only_mode
	room_bg.add_child(inventory_grid)

	# Connect signals
	inventory_grid.item_placed.connect(_on_item_placed)
	inventory_grid.item_removed.connect(_on_item_removed)
	inventory_grid.item_sold.connect(_on_item_sold)
	inventory_grid.item_moved.connect(_on_item_moved)

	# Set legacy references for compatibility
	server_room_container = inventory_grid
	grid_container = inventory_grid

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

		# Create storage grid
		storage_grid = InventoryGrid.new()
		storage_grid.position = Vector2(5, 5)  # Small padding
		storage_grid.configure(STORAGE_WIDTH, STORAGE_HEIGHT, CELL_SIZE, CELL_SPACING)
		storage_grid.title = "Storage"
		storage_grid.read_only = read_only_mode
		storage_bg.add_child(storage_grid)

		# Set legacy reference
		storage_container = storage_grid

		# Storage is always active (no servers needed)
		for y in range(STORAGE_HEIGHT):
			for x in range(STORAGE_WIDTH):
				storage_grid.active_grid[y][x] = true

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
				# Start dragging the shop item
				_start_shop_drag(shop_item, item_data)

var dragging_shop_item: Panel = null
var dragging_shop_data: Dictionary = {}
var drag_preview: Control = null

func _start_shop_drag(shop_item: Panel, item_data: Dictionary):
	"""Start dragging a shop item"""
	# Don't allow dragging sold items
	if shop_item.modulate.a < 1.0:
		print("This item has already been sold")
		return

	# Check if player has enough gold
	var cost = item_data.get("cost", 0)
	if GameStateManager.gold < cost:
		print("Not enough gold! Need %d, have %d" % [cost, GameStateManager.gold])
		return

	# Start dragging
	dragging_shop_item = shop_item
	dragging_shop_data = item_data

	# Create drag preview
	drag_preview = Control.new()
	drag_preview.mouse_filter = Control.MOUSE_FILTER_IGNORE

	# Determine size based on shape or default
	var shape = item_data.get("shape", [[0, 0]])
	var max_x = 0
	var max_y = 0
	for offset in shape:
		if offset is Array and offset.size() >= 2:
			max_x = max(max_x, offset[0])
			max_y = max(max_y, offset[1])

	var width = max_x + 1
	var height = max_y + 1
	drag_preview.size = Vector2(
		width * (inventory_grid.cell_size + inventory_grid.cell_spacing) - inventory_grid.cell_spacing,
		height * (inventory_grid.cell_size + inventory_grid.cell_spacing) - inventory_grid.cell_spacing
	)

	# Create visual for each cell in the shape
	for offset in shape:
		if offset is Array and offset.size() >= 2:
			var cell = Panel.new()
			cell.position = Vector2(
				offset[0] * (inventory_grid.cell_size + inventory_grid.cell_spacing),
				offset[1] * (inventory_grid.cell_size + inventory_grid.cell_spacing)
			)
			cell.size = Vector2(inventory_grid.cell_size, inventory_grid.cell_size)
			cell.mouse_filter = Control.MOUSE_FILTER_IGNORE

			var style = StyleBoxFlat.new()
			style.bg_color = _get_color_for_category(item_data.get("category", "problem"))
			style.bg_color.a = 0.7  # Semi-transparent
			style.border_color = Color(0.4, 0.7, 1.0, 1.0)
			style.set_border_width_all(2)
			style.set_corner_radius_all(4)
			cell.add_theme_stylebox_override("panel", style)
			drag_preview.add_child(cell)

	# Add to scene
	add_child(drag_preview)

func _end_shop_drag():
	"""End dragging a shop item and try to purchase/place it"""
	if not dragging_shop_item or not drag_preview:
		return

	# Check if we're over the inventory grid
	var mouse_pos = inventory_grid.get_local_mouse_position()
	var grid_pos = inventory_grid.pixel_to_grid(mouse_pos)

	# Use the grid's can_place_item method
	if inventory_grid.can_place_item(dragging_shop_data, grid_pos):
		# Place the item in the grid immediately (optimistic update)
		if inventory_grid.place_shop_item(dragging_shop_data, grid_pos):
			print("Placed item at position [%d, %d]" % [grid_pos.x, grid_pos.y])

			# Now tell the server about the purchase
			var item_id = dragging_shop_data.get("id", "")
			if item_id:
				print("Purchasing item %s at position [%d, %d]" % [item_id, grid_pos.x, grid_pos.y])
				BattleServerAPI.purchase_item(item_id, [grid_pos.x, grid_pos.y])
				_mark_shop_item_sold(dragging_shop_item)
		else:
			print("Failed to place item at position")
	else:
		print("Cannot place item at this position")

	# Hide the hover preview
	inventory_grid.hide_hover_preview()

	# Clean up drag state
	if drag_preview:
		drag_preview.queue_free()
		drag_preview = null
	dragging_shop_item = null
	dragging_shop_data = {}

func _try_purchase_from_shop(shop_item: Panel, item_data: Dictionary):
	# Don't allow purchasing sold items
	if shop_item.modulate.a < 1.0:
		print("This item has already been sold")
		return

	# Check if player has enough gold
	var cost = item_data.get("cost", 0)
	if GameStateManager.gold < cost:
		print("Not enough gold! Need %d, have %d" % [cost, GameStateManager.gold])
		return

	# For now, just add the item to storage or first available spot
	# TODO: Let player choose placement
	if item_data.get("type", "") == "server":
		# Add server container to inventory
		print("Purchasing server container: ", item_data.get("name", "Unknown"))
		# TODO: Call server API to purchase and place container
	else:
		# Try to place item in first available spot
		print("Purchasing item: ", item_data.get("name", "Unknown"))
		var item_id = item_data.get("id", "")
		if item_id:
			# Debug: Check if we have any active grid spots
			var active_count = 0
			for y in range(inventory_grid.grid_height):
				for x in range(inventory_grid.grid_width):
					if inventory_grid.active_grid[y][x]:
						active_count += 1
			print("DEBUG: Found %d active grid cells" % active_count)
			print("DEBUG: Number of containers: %d" % inventory_grid.containers.size())

			# Try to find first valid placement spot
			for y in range(inventory_grid.grid_height):
				for x in range(inventory_grid.grid_width):
					if inventory_grid.active_grid[y][x] and not inventory_grid.item_grid[y][x]:
						# Found empty spot on a server, try to place here
						print("DEBUG: Purchasing item %s at position [%d, %d]" % [item_id, x, y])
						BattleServerAPI.purchase_item(item_id, [x, y])
						_mark_shop_item_sold(shop_item)
						return
			# No space found
			print("No space available for item!")


func _mark_shop_item_sold(shop_item: Panel):
	"""Mark a shop item as sold"""
	shop_item.modulate = Color(0.5, 0.5, 0.5, 0.5)
	var sold_label = Label.new()
	sold_label.text = "SOLD"
	sold_label.position = Vector2(70, 25)
	sold_label.add_theme_font_size_override("font_size", 16)
	sold_label.add_theme_color_override("font_color", Color(1.0, 0.3, 0.3))
	shop_item.add_child(sold_label)

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
	# Input handled by InventoryGrid

	return container

func _on_ready_for_battle():
	# Save current inventory state
	var inventory_state = get_inventory_state()

	# Get the actual inventory from the grid
	var grid_state = inventory_grid.get_inventory_state()

	print("DEBUG: Saving inventory before battle:")
	print("  Items to save: %d" % grid_state.items.size())
	for item in grid_state.items:
		if item is Dictionary:
			print("    - %s at %s" % [item.get("name", "?"), item.get("position", "?")])

	# Save to GameStateManager so it persists across scene changes
	GameStateManager.save_inventory_state(grid_state.items, grid_state.servers)

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

func _get_stats_text() -> String:
	return "Round %d | Gold: %d | Lives: %d | Wins: %d | Losses: %d" % [
		GameStateManager.current_round,
		GameStateManager.gold,
		GameStateManager.player_lives,
		GameStateManager.wins,
		GameStateManager.losses
	]

func _update_stats():
	if stats_label:
		stats_label.text = _get_stats_text()

func _on_purchase_completed(response: APITypes.PurchaseResponse):
	# Update gold from server response
	if response != null:
		GameStateManager.gold = response.gold
		_update_stats()

		# Add the purchased item to inventory
		var item_data = response.purchased_item
		if item_data and item_data.has("position"):
			# Create typed item for inventory grid
			var typed_item = APITypes.InventoryItem.new(item_data)
			inventory_grid._add_item(typed_item)
			_save_current_state()

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
