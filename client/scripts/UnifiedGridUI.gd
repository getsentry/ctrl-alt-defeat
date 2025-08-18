extends Control

# Game state
var current_gold: int = 50
var current_round: int = 1
var current_health: int = 100

# Grid settings
const ROOM_WIDTH = 12
const ROOM_HEIGHT = 8
const CELL_SIZE = 45
const CELL_SPACING = 1

# Storage settings
const STORAGE_WIDTH = 12
const STORAGE_HEIGHT = 2

# Unified grid system
var active_grid: Array = []  # Tracks which cells have server grids
var item_grid: Array = []    # Tracks items placed on the grid
var grid_cells: Array = []   # Visual grid cell references
var servers: Array = []       # Server objects (for tracking)
var items: Array = []         # Item objects

# Shop
var shop_items: Array = []

# Drag and drop
var dragging_object = null
var drag_offset = Vector2.ZERO
var original_position = Vector2.ZERO
var original_parent = null
var original_grid_pos = Vector2i(-1, -1)
var hover_preview: Panel = null
var valid_placement = false

# UI References
var server_room_container: Control
var grid_container: Control
var storage_container: Control
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

# Item types
var item_types = {
	"cpu": {
		"name": "CPU",
		"width": 1,
		"height": 1,
		"color": Color(0.9, 0.3, 0.3),
		"cost": 3,
		"attack": 3,
		"type": "item"
	},
	"ram": {
		"name": "RAM",
		"width": 2,
		"height": 1,
		"color": Color(0.3, 0.6, 0.9),
		"cost": 4,
		"defense": 3,
		"type": "item"
	},
	"firewall": {
		"name": "Firewall",
		"width": 1,
		"height": 2,
		"color": Color(0.6, 0.3, 0.9),
		"cost": 5,
		"defense": 5,
		"type": "item"
	},
	"balancer": {
		"name": "Balancer",
		"width": 2,
		"height": 2,
		"color": Color(0.3, 0.9, 0.6),
		"cost": 7,
		"attack": 2,
		"defense": 3,
		"type": "item"
	},
	"cooler": {
		"name": "Cooler",
		"width": 1,
		"height": 1,
		"color": Color(0.6, 0.8, 0.9),
		"cost": 2,
		"heal": 2,
		"type": "item"
	},
	"storage": {
		"name": "Storage",
		"width": 3,
		"height": 1,
		"color": Color(0.5, 0.5, 0.7),
		"cost": 6,
		"defense": 4,
		"type": "item"
	}
}

func _ready():
	print("UnifiedGridUI starting...")
	_initialize_grids()
	_setup_ui()
	_generate_shop()

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
	# Background
	var bg = ColorRect.new()
	bg.color = Color(0.02, 0.02, 0.03, 1.0)
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(bg)

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
	var header = ColorRect.new()
	header.color = Color(0.05, 0.05, 0.08, 1.0)
	header.position = Vector2(0, 0)
	header.size = Vector2(1280, 70)
	add_child(header)

	var title = Label.new()
	title.text = "SENTRY DATA CENTER"
	title.position = Vector2(480, 10)
	title.add_theme_font_size_override("font_size", 28)
	title.add_theme_color_override("font_color", Color(0.9, 0.9, 1.0))
	add_child(title)

	stats_label = Label.new()
	stats_label.text = _get_stats_text()
	stats_label.position = Vector2(460, 40)
	stats_label.add_theme_font_size_override("font_size", 16)
	stats_label.add_theme_color_override("font_color", Color(1.0, 0.9, 0.3))
	add_child(stats_label)

func _create_shop_panel():
	var shop_bg = Panel.new()
	shop_bg.position = Vector2(20, 90)
	shop_bg.size = Vector2(240, 500)
	var shop_style = StyleBoxFlat.new()
	shop_style.bg_color = Color(0.06, 0.06, 0.10, 0.95)
	shop_style.set_corner_radius_all(6)
	shop_bg.add_theme_stylebox_override("panel", shop_style)
	add_child(shop_bg)

	var shop_title = Label.new()
	shop_title.text = "SHOP"
	shop_title.position = Vector2(110, 100)
	shop_title.add_theme_font_size_override("font_size", 18)
	shop_title.add_theme_color_override("font_color", Color(1.0, 1.0, 1.0))
	add_child(shop_title)

	shop_container = Control.new()
	shop_container.position = Vector2(30, 130)
	shop_container.size = Vector2(220, 450)
	add_child(shop_container)

func _create_server_room():
	# Server Room Background
	var room_bg = Panel.new()
	room_bg.position = Vector2(280, 90)
	room_bg.size = Vector2(ROOM_WIDTH * (CELL_SIZE + CELL_SPACING) + 20,
						   ROOM_HEIGHT * (CELL_SIZE + CELL_SPACING) + 20)
	var room_style = StyleBoxFlat.new()
	room_style.bg_color = Color(0.04, 0.06, 0.04, 0.95)
	room_style.border_color = Color(0.15, 0.20, 0.15, 0.6)
	room_style.set_border_width_all(2)
	room_style.set_corner_radius_all(6)
	room_bg.add_theme_stylebox_override("panel", room_style)
	add_child(room_bg)

	var room_title = Label.new()
	room_title.text = "SERVER ROOM"
	room_title.position = Vector2(550, 100)
	room_title.add_theme_font_size_override("font_size", 18)
	room_title.add_theme_color_override("font_color", Color(0.9, 1.0, 0.9))
	add_child(room_title)

	# Container for the room
	server_room_container = Control.new()
	server_room_container.position = Vector2(290, 130)
	server_room_container.size = Vector2(ROOM_WIDTH * (CELL_SIZE + CELL_SPACING),
										 ROOM_HEIGHT * (CELL_SIZE + CELL_SPACING))
	add_child(server_room_container)

	# Grid container (for cells created by servers)
	grid_container = Control.new()
	grid_container.position = Vector2(0, 0)
	grid_container.size = server_room_container.size
	grid_container.mouse_filter = Control.MOUSE_FILTER_IGNORE
	server_room_container.add_child(grid_container)

func _create_storage_area():
	var storage_bg = Panel.new()
	storage_bg.position = Vector2(280, 480)
	storage_bg.size = Vector2(ROOM_WIDTH * (CELL_SIZE + CELL_SPACING) + 20, 100)
	var storage_style = StyleBoxFlat.new()
	storage_style.bg_color = Color(0.05, 0.05, 0.08, 0.95)
	storage_style.border_color = Color(0.2, 0.2, 0.25, 0.6)
	storage_style.set_border_width_all(2)
	storage_style.set_corner_radius_all(6)
	storage_bg.add_theme_stylebox_override("panel", storage_style)
	add_child(storage_bg)

	var storage_title = Label.new()
	storage_title.text = "STORAGE (Inactive)"
	storage_title.position = Vector2(500, 490)
	storage_title.add_theme_font_size_override("font_size", 14)
	storage_title.add_theme_color_override("font_color", Color(0.7, 0.7, 0.8))
	add_child(storage_title)

	storage_container = Control.new()
	storage_container.position = Vector2(290, 515)
	storage_container.size = Vector2(ROOM_WIDTH * (CELL_SIZE + CELL_SPACING), 55)
	add_child(storage_container)

func _create_controls():
	var refresh_btn = Button.new()
	refresh_btn.text = "Refresh (2g)"
	refresh_btn.position = Vector2(50, 600)
	refresh_btn.size = Vector2(100, 30)
	refresh_btn.pressed.connect(_on_refresh_shop)
	add_child(refresh_btn)

	var battle_btn = Button.new()
	battle_btn.text = "Battle"
	battle_btn.position = Vector2(1100, 600)
	battle_btn.size = Vector2(100, 30)
	battle_btn.pressed.connect(_on_start_battle)
	add_child(battle_btn)

	var help = Label.new()
	help.text = "Drag servers to create grid → Place items on any grid cells → Items can span servers"
	help.position = Vector2(300, 605)
	help.add_theme_font_size_override("font_size", 12)
	help.add_theme_color_override("font_color", Color(0.6, 0.6, 0.7))
	add_child(help)

func _generate_shop():
	for child in shop_container.get_children():
		child.queue_free()
	shop_items.clear()

	var all_items = {}
	for key in server_types:
		all_items[key] = server_types[key]
	for key in item_types:
		all_items[key] = item_types[key]

	var keys = all_items.keys()
	keys.shuffle()

	var y_pos = 0
	for i in range(min(7, keys.size())):
		var item_key = keys[i]
		var item_data = all_items[item_key].duplicate()
		item_data["id"] = item_key

		var shop_item = Panel.new()
		shop_item.position = Vector2(0, y_pos)
		shop_item.size = Vector2(210, 60)

		var item_style = StyleBoxFlat.new()
		if item_data.type == "server":
			item_style.bg_color = Color(0.2, 0.25, 0.3, 0.9)
		else:
			item_style.bg_color = item_data.color
			item_style.bg_color.a = 0.8
		item_style.set_corner_radius_all(4)
		shop_item.add_theme_stylebox_override("panel", item_style)

		shop_item.gui_input.connect(_on_shop_item_input.bind(shop_item, item_data))
		shop_item.set_meta("shop_item", true)
		shop_item.set_meta("item_data", item_data)

		var name_label = Label.new()
		name_label.text = item_data.name
		name_label.position = Vector2(10, 10)
		name_label.add_theme_font_size_override("font_size", 14)
		name_label.add_theme_color_override("font_color", Color(1.0, 1.0, 1.0))
		shop_item.add_child(name_label)

		var info_label = Label.new()
		if item_data.type == "server":
			var pattern = item_data.pattern
			info_label.text = "Grid %dx%d" % [pattern[0].size(), pattern.size()]
		else:
			info_label.text = "%dx%d" % [item_data.width, item_data.height]
		info_label.position = Vector2(10, 30)
		info_label.add_theme_font_size_override("font_size", 11)
		info_label.add_theme_color_override("font_color", Color(0.8, 0.8, 0.8))
		shop_item.add_child(info_label)

		var cost_label = Label.new()
		cost_label.text = "%dg" % item_data.cost
		cost_label.position = Vector2(160, 20)
		cost_label.add_theme_font_size_override("font_size", 14)
		cost_label.add_theme_color_override("font_color", Color(1.0, 0.85, 0.3))
		shop_item.add_child(cost_label)

		shop_container.add_child(shop_item)
		shop_items.append(shop_item)

		y_pos += 65

	print("Shop generated with %d items" % shop_items.size())

func _on_shop_item_input(event: InputEvent, shop_item: Panel, item_data: Dictionary):
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_LEFT:
			if event.pressed:
				_start_dragging_from_shop(shop_item, item_data, event.position)
			else:
				_stop_dragging()

func _start_dragging_from_shop(shop_item: Panel, item_data: Dictionary, local_pos: Vector2):
	if item_data.type == "server":
		dragging_object = _create_server_preview(item_data)
	else:
		dragging_object = _create_item(item_data)

	dragging_object.position = shop_item.global_position
	dragging_object.modulate.a = 0.7
	add_child(dragging_object)

	drag_offset = local_pos
	original_parent = null

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

func _create_item(item_data: Dictionary) -> Panel:
	var item = Panel.new()
	item.size = Vector2(item_data.width * (CELL_SIZE + CELL_SPACING) - CELL_SPACING,
					   item_data.height * (CELL_SIZE + CELL_SPACING) - CELL_SPACING)

	var item_style = StyleBoxFlat.new()
	item_style.bg_color = item_data.color
	item_style.set_corner_radius_all(3)
	item.add_theme_stylebox_override("panel", item_style)

	var label = Label.new()
	label.text = item_data.name
	label.position = Vector2(3, 3)
	label.add_theme_font_size_override("font_size", 10)
	label.add_theme_color_override("font_color", Color(1.0, 1.0, 1.0))
	item.add_child(label)

	item.set_meta("item_data", item_data)
	item.set_meta("is_item", true)
	item.gui_input.connect(_on_item_input.bind(item))

	return item

func _on_item_input(event: InputEvent, item: Panel):
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_LEFT:
			if event.pressed:
				_start_dragging_item(item, event.position)
			else:
				_stop_dragging()

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

func _stop_dragging():
	if not dragging_object:
		return

	dragging_object.modulate.a = 1.0

	var placed = false

	if dragging_object.has_meta("is_server"):
		placed = _try_place_server(dragging_object)
	elif dragging_object.has_meta("is_item"):
		placed = _try_place_item(dragging_object)

	if not placed:
		if original_parent:
			if dragging_object.has_meta("is_item") and original_grid_pos.x >= 0:
				# Restore to grid
				var item_data = dragging_object.get_meta("item_data")
				for dy in range(item_data.height):
					for dx in range(item_data.width):
						if original_grid_pos.y + dy < ROOM_HEIGHT and original_grid_pos.x + dx < ROOM_WIDTH:
							item_grid[original_grid_pos.y + dy][original_grid_pos.x + dx] = dragging_object
				dragging_object.position = original_position
				if dragging_object.get_parent() != server_room_container:
					dragging_object.get_parent().remove_child(dragging_object)
					server_room_container.add_child(dragging_object)
			else:
				dragging_object.position = original_position
		else:
			dragging_object.queue_free()

	gold_preview_label.visible = false
	hover_preview.visible = false
	dragging_object = null
	original_grid_pos = Vector2i(-1, -1)

func _try_place_server(server_preview: Control) -> bool:
	var mouse_pos = server_room_container.get_local_mouse_position()

	if mouse_pos.x >= 0 and mouse_pos.x < server_room_container.size.x and \
	   mouse_pos.y >= 0 and mouse_pos.y < server_room_container.size.y:

		var server_data = server_preview.get_meta("server_data")
		var grid_x = int((mouse_pos.x + CELL_SIZE/2) / (CELL_SIZE + CELL_SPACING))
		var grid_y = int((mouse_pos.y + CELL_SIZE/2) / (CELL_SIZE + CELL_SPACING))

		# Check if pattern fits
		var pattern = server_data.pattern
		if _can_place_server_pattern(grid_x, grid_y, pattern):
			# Pay for it
			if not original_parent:
				if current_gold < server_data.cost:
					print("Not enough gold!")
					return false
				current_gold -= server_data.cost
				_update_stats()

			# Place server cells
			_place_server_pattern(grid_x, grid_y, server_data)

			# Remove preview
			server_preview.queue_free()

			if not original_parent:
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
				cell_style.bg_color = Color(0.1, 0.15, 0.1, 0.3)
				cell_style.border_color = Color(0.3, 0.4, 0.3, 0.5)
				cell_style.set_border_width_all(1)
				cell.add_theme_stylebox_override("panel", cell_style)

				grid_container.add_child(cell)
				grid_cells[gy][gx] = cell

func _try_place_item(item: Panel) -> bool:
	var item_data = item.get_meta("item_data")

	# Check if over grid
	var mouse_pos = server_room_container.get_local_mouse_position()

	if mouse_pos.x >= 0 and mouse_pos.x < server_room_container.size.x and \
	   mouse_pos.y >= 0 and mouse_pos.y < server_room_container.size.y:

		var grid_x = int((mouse_pos.x + CELL_SIZE/2) / (CELL_SIZE + CELL_SPACING))
		var grid_y = int((mouse_pos.y + CELL_SIZE/2) / (CELL_SIZE + CELL_SPACING))

		if _can_place_item_on_grid(grid_x, grid_y, item_data.width, item_data.height):
			# Pay if from shop
			if not original_parent:
				if current_gold < item_data.cost:
					print("Not enough gold!")
					return false
				current_gold -= item_data.cost
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

			if not original_parent:
				items.append(item)

			return true

	# Check storage
	var storage_mouse = storage_container.get_local_mouse_position()
	if storage_mouse.x >= 0 and storage_mouse.x < storage_container.size.x and \
	   storage_mouse.y >= 0 and storage_mouse.y < storage_container.size.y:

		# Pay if from shop
		if not original_parent:
			if current_gold < item_data.cost:
				print("Not enough gold!")
				return false
			current_gold -= item_data.cost
			_update_stats()

		if item.get_parent() != storage_container:
			item.get_parent().remove_child(item)
			storage_container.add_child(item)

		item.position = storage_mouse - drag_offset
		item.position.x = clamp(item.position.x, 0, storage_container.size.x - item.size.x)
		item.position.y = clamp(item.position.y, 0, storage_container.size.y - item.size.y)

		if item.has_meta("grid_pos"):
			item.remove_meta("grid_pos")

		if not original_parent:
			items.append(item)

		return true

	return false

func _can_place_item_on_grid(x: int, y: int, width: int, height: int) -> bool:
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

func _input(event):
	if dragging_object and event is InputEventMouseMotion:
		dragging_object.global_position = get_global_mouse_position() - drag_offset

		if gold_preview_label.visible:
			gold_preview_label.position = get_global_mouse_position() + Vector2(10, -20)

		# Update hover preview
		_update_hover_preview()

func _update_hover_preview():
	if not dragging_object:
		hover_preview.visible = false
		return

	var mouse_pos = server_room_container.get_local_mouse_position()

	if mouse_pos.x >= 0 and mouse_pos.x < server_room_container.size.x and \
	   mouse_pos.y >= 0 and mouse_pos.y < server_room_container.size.y:

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
	return "Gold: %d | Round: %d | Health: %d" % [current_gold, current_round, current_health]

func _update_stats():
	stats_label.text = _get_stats_text()

func _on_refresh_shop():
	if current_gold >= 2:
		current_gold -= 2
		_update_stats()
		_generate_shop()

func _on_start_battle():
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

	var win_chance = 0.3 + (total_attack * 0.05) + (total_defense * 0.03) + (servers.size() * 0.02)
	win_chance = min(win_chance, 0.95)

	if randf() < win_chance:
		print("Victory!")
		current_gold += 5 + current_round
		current_round += 1
	else:
		print("Defeat!")
		current_health -= 10

	_update_stats()

	if current_health <= 0:
		print("GAME OVER! Survived %d rounds" % current_round)
