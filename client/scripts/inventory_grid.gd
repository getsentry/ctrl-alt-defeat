extends Control
class_name InventoryGrid

# Grid component that handles all inventory display and interaction
# Used by UnifiedGridUI for the main game and BattleScreen for replays

const APITypes = preload("res://scripts/api_types.gd")
const ItemVisual = preload("res://scripts/item_visual.gd")

# Grid configuration - can be customized per instance
var grid_width: int = 9
var grid_height: int = 7
var cell_size: float = 45.0
var cell_spacing: float = 1.0

# Visual settings
var grid_color = Color(0.15, 0.15, 0.2, 0.8)
var border_color = Color(0.3, 0.6, 1.0, 0.8)
var item_color = Color(0.2, 0.5, 1.0, 1.0)  # Full opacity
var server_color = Color(0.3, 0.4, 0.5, 0.3)

# Mode settings
var read_only: bool = false
var title: String = ""

# Grid data structures
var active_grid: Array = []  # 2D array tracking which cells have servers
var item_grid: Array = []    # 2D array tracking which cells have items
var grid_cells: Array = []   # 2D array of visual cell references

# Stored objects
var items: Array = []         # Array of item visuals
var containers: Array = []    # Array of server container visuals

# Drag and drop state
var dragging_object = null
var drag_offset = Vector2.ZERO
var original_position = Vector2.ZERO
var original_grid_pos = Vector2i(-1, -1)
var hover_preview: Panel = null
var valid_placement = false

# Signals
signal item_clicked(item)
signal item_placed(item_data, grid_pos)
signal item_removed(item_data, grid_pos)
signal item_sold(item_data)
signal item_moved(item_uid, from_pos, to_pos)

func _ready():
	mouse_filter = Control.MOUSE_FILTER_PASS
	_initialize_grids()
	_setup_visual()
	_create_hover_preview()

func configure(width: int, height: int, size: float = 45.0, spacing: float = 1.0):
	"""Configure grid dimensions and cell sizing"""
	grid_width = width
	grid_height = height
	cell_size = size
	cell_spacing = spacing
	_initialize_grids()
	_setup_visual()

func _initialize_grids():
	"""Initialize all grid arrays"""
	active_grid.clear()
	item_grid.clear()
	grid_cells.clear()

	for y in range(grid_height):
		var active_row = []
		var item_row = []
		var cell_row = []
		for x in range(grid_width):
			active_row.append(false)  # No server here initially
			item_row.append(null)      # No item here initially
			cell_row.append(null)      # No visual cell initially
		active_grid.append(active_row)
		item_grid.append(item_row)
		grid_cells.append(cell_row)

func _setup_visual():
	"""Setup the visual grid background and cells"""
	# Clear existing children
	for child in get_children():
		child.queue_free()

	# Set our size based on grid dimensions
	custom_minimum_size = Vector2(
		grid_width * (cell_size + cell_spacing),
		grid_height * (cell_size + cell_spacing)
	)
	size = custom_minimum_size

	# Create background panel
	var bg = Panel.new()
	bg.size = size
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var style = StyleBoxFlat.new()
	style.bg_color = Color(0.05, 0.1, 0.15, 0.2)
	style.border_color = border_color
	style.set_border_width_all(2)
	style.set_corner_radius_all(4)
	bg.add_theme_stylebox_override("panel", style)
	add_child(bg)

	# Create grid cells
	for y in range(grid_height):
		for x in range(grid_width):
			var cell = _create_cell_visual(x, y)
			grid_cells[y][x] = cell

	# Add title if provided
	if title != "":
		var title_label = Label.new()
		title_label.text = title
		title_label.position = Vector2(5, -25)
		title_label.add_theme_font_size_override("font_size", 16)
		title_label.add_theme_color_override("font_color", Color(0.8, 0.8, 0.9))
		add_child(title_label)

func _create_cell_visual(x: int, y: int) -> Panel:
	"""Create a visual cell at grid position"""
	var cell = Panel.new()
	cell.position = grid_to_pixel(Vector2i(x, y))
	cell.size = Vector2(cell_size, cell_size)
	cell.mouse_filter = Control.MOUSE_FILTER_IGNORE

	var cell_style = StyleBoxFlat.new()
	cell_style.bg_color = Color(0.1, 0.1, 0.15, 0.3)
	cell_style.border_color = Color(0.2, 0.2, 0.3, 0.3)
	cell_style.set_border_width_all(1)
	cell.add_theme_stylebox_override("panel", cell_style)

	add_child(cell)
	return cell

func _create_hover_preview():
	"""Create the hover preview panel for placement feedback"""
	hover_preview = Panel.new()
	hover_preview.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hover_preview.visible = false
	var hover_style = StyleBoxFlat.new()
	hover_style.bg_color = Color(0.3, 1.0, 0.3, 0.3)
	hover_style.border_color = Color(0.5, 1.0, 0.5, 0.8)
	hover_style.set_border_width_all(2)
	hover_preview.add_theme_stylebox_override("panel", hover_style)
	add_child(hover_preview)

func grid_to_pixel(grid_pos: Vector2i) -> Vector2:
	"""Convert grid coordinates to pixel position"""
	return Vector2(
		grid_pos.x * (cell_size + cell_spacing) + cell_spacing,
		grid_pos.y * (cell_size + cell_spacing) + cell_spacing
	)

func pixel_to_grid(pixel_pos: Vector2) -> Vector2i:
	"""Convert pixel position to grid coordinates"""
	var local_pos = pixel_pos
	if pixel_pos.x < 0 or pixel_pos.y < 0:
		return Vector2i(-1, -1)

	var x = int(local_pos.x / (cell_size + cell_spacing))
	var y = int(local_pos.y / (cell_size + cell_spacing))

	if x >= grid_width or y >= grid_height:
		return Vector2i(-1, -1)

	return Vector2i(x, y)

func load_inventory_state(inventory_state: APITypes.InventoryState):
	"""Load a complete inventory state"""
	clear_all()

	# Load containers first (server racks)
	for container_data in inventory_state.containers:
		_add_container(container_data)

	# Load items
	for item_data in inventory_state.items:
		_add_item(item_data)

func _add_container(container: APITypes.ServerContainer):
	"""Add a server container to the grid"""
	if not container.position:
		return

	var x = container.position.x
	var y = container.position.y
	var width = container.width
	var height = container.height

	# Create container visual using ItemVisual
	var container_visual = ItemVisual.new()
	container_visual.position = grid_to_pixel(Vector2i(x, y))
	container_visual.mouse_filter = Control.MOUSE_FILTER_IGNORE

	# Set up container data with shape based on width/height
	var container_data = container.to_dict() if container is Resource else container
	container_data["is_container"] = true

	# Generate shape array for the container
	var shape = []
	for cy in range(height):
		for cx in range(width):
			shape.append([cx, cy])
	container_data["shape"] = shape

	# Enable tooltips for containers too (must be before setup)
	container_visual.enable_tooltip = true

	# Set up the visual
	container_visual.setup(container_data, cell_size, cell_spacing)

	# Update grid cells to show server pattern and mark as active
	for cy in range(height):
		for cx in range(width):
			var grid_x = x + cx
			var grid_y = y + cy
			if grid_x >= 0 and grid_x < grid_width and grid_y >= 0 and grid_y < grid_height:
				# Mark as active for placement
				active_grid[grid_y][grid_x] = true

				# Update visual
				var cell = grid_cells[grid_y][grid_x]
				if cell:
					var style = StyleBoxFlat.new()
					style.bg_color = Color(0.2, 0.3, 0.5, 0.3)
					style.border_color = Color(0.3, 0.5, 0.8, 0.6)
					style.set_border_width_all(1)
					cell.add_theme_stylebox_override("panel", style)

	add_child(container_visual)
	containers.append({
		"visual": container_visual,
		"data": container,
		"position": Vector2i(x, y)
	})

func _add_item(item: APITypes.InventoryItem):
	"""Add an item to the grid"""
	if not item.position:
		return

	var x = item.position.x
	var y = item.position.y

	# Create item visual using the ItemVisual class
	var item_visual = ItemVisual.new()
	item_visual.position = grid_to_pixel(Vector2i(x, y))
	item_visual.mouse_filter = Control.MOUSE_FILTER_PASS if not read_only else Control.MOUSE_FILTER_IGNORE
	item_visual.set_meta("item_data", item)
	item_visual.set_meta("grid_pos", Vector2i(x, y))

	# Enable tooltips for all items (must be before setup)
	item_visual.enable_tooltip = true

	# Set up the visual with item data and grid settings
	item_visual.setup(item, cell_size, cell_spacing)

	# Mark grid cells as occupied
	for offset in item.shape:
		if offset is Array and offset.size() >= 2:
			var cell_x = x + offset[0]
			var cell_y = y + offset[1]
			if cell_x >= 0 and cell_y >= 0 and cell_x < grid_width and cell_y < grid_height:
				item_grid[cell_y][cell_x] = item_visual

	# Connect input if not read-only
	if not read_only:
		item_visual.gui_input.connect(_on_item_input.bind(item_visual))

	add_child(item_visual)
	items.append(item_visual)

func _on_item_input(event: InputEvent, item_visual: Control):
	"""Handle input on items for dragging"""
	if read_only:
		return

	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_LEFT:
			if event.pressed:
				# Start dragging
				_start_drag(item_visual)
			else:
				# End dragging
				_end_drag()
		elif event.button_index == MOUSE_BUTTON_RIGHT and event.pressed:
			# Right click to sell
			var item_data = item_visual.get_meta("item_data")
			item_sold.emit(item_data)
			_remove_item(item_visual)

func _start_drag(item_visual: Control):
	"""Start dragging an item"""
	# Don't allow dragging in read-only mode
	if read_only:
		return

	dragging_object = item_visual
	original_position = item_visual.position
	original_grid_pos = item_visual.get_meta("grid_pos")
	drag_offset = item_visual.position - get_local_mouse_position()

	# Ensure the item visual stays at its proper size while dragging
	item_visual.z_index = 10  # Bring to front

	# Clear item from grid
	var item_data = item_visual.get_meta("item_data")
	for offset in item_data.shape:
		if offset is Array and offset.size() >= 2:
			var cell_x = original_grid_pos.x + offset[0]
			var cell_y = original_grid_pos.y + offset[1]
			if cell_x >= 0 and cell_y >= 0 and cell_x < grid_width and cell_y < grid_height:
				item_grid[cell_y][cell_x] = null

	# Move to top for dragging (visual hierarchy)
	move_child(item_visual, get_child_count() - 1)

func _end_drag():
	"""End dragging and place item"""
	if not dragging_object:
		return

	var grid_pos = pixel_to_grid(get_local_mouse_position())
	var item_data = dragging_object.get_meta("item_data")
	var temp_object = dragging_object
	dragging_object = null
	hover_preview.visible = false

	# Check if we're trying to move to the same position - no-op
	if grid_pos == original_grid_pos:
		# Just put it back where it was visually, no API call needed
		_place_item_at(temp_object, original_grid_pos)
		return

	# Check if the new position is valid
	if _can_place_item(item_data, grid_pos):
		var item_uid = item_data.id if item_data is Dictionary and item_data.has("id") else (item_data.id if item_data is Resource else "")

		# Call API to move item
		var response = await BattleServerAPI.move_item(item_uid, [grid_pos.x, grid_pos.y])
		if response:
			print("Move persisted on server")
			# Move succeeded, place at new position
			_place_item_at(temp_object, grid_pos)
			# Emit signal for any listeners
			item_moved.emit(item_uid, original_grid_pos, grid_pos)
		else:
			print("Failed to persist move on server, reverting")
			# Move failed, return to original position
			_place_item_at(temp_object, original_grid_pos)

	else:
		# Can't place at target position, return to original
		_place_item_at(temp_object, original_grid_pos)

func _place_item_at(item_visual: Control, grid_pos: Vector2i):
	"""Place item visual at grid position"""
	item_visual.position = grid_to_pixel(grid_pos)
	item_visual.set_meta("grid_pos", grid_pos)
	item_visual.z_index = 0  # Reset z-index after placing

	# Mark grid cells as occupied
	var item_data = item_visual.get_meta("item_data")
	for offset in item_data.shape:
		if offset is Array and offset.size() >= 2:
			var cell_x = grid_pos.x + offset[0]
			var cell_y = grid_pos.y + offset[1]
			if cell_x >= 0 and cell_y >= 0 and cell_x < grid_width and cell_y < grid_height:
				item_grid[cell_y][cell_x] = item_visual

func can_place_item(item_data, grid_pos: Vector2i) -> bool:
	"""Public method to check if item can be placed at position"""
	return _can_place_item(item_data, grid_pos)

func _can_place_item(item_data, grid_pos: Vector2i) -> bool:
	"""Check if item can be placed at position"""
	if grid_pos.x < 0 or grid_pos.y < 0:
		return false

	# Check each cell in the item's shape
	for offset in item_data.shape:
		if offset is Array and offset.size() >= 2:
			var cell_x = grid_pos.x + offset[0]
			var cell_y = grid_pos.y + offset[1]

			# Check bounds
			if cell_x < 0 or cell_x >= grid_width or cell_y < 0 or cell_y >= grid_height:
				return false

			# Check if on active grid (server)
			if not active_grid[cell_y][cell_x]:
				return false

			# Check if occupied by another item
			if item_grid[cell_y][cell_x] != null and item_grid[cell_y][cell_x] != dragging_object:
				return false

	return true

func place_shop_item(item_data: Dictionary, grid_pos: Vector2i) -> bool:
	"""Place a shop item at the given position"""
	if not can_place_item(item_data, grid_pos):
		return false

	# Create a proper InventoryItem from the shop data
	var item_dict = {
		"id": item_data.get("id", ""),
		"item_type": item_data.get("item_type", ""),
		"slug": item_data.get("slug", ""),  # Include slug for texture loading
		"name": item_data.get("name", ""),
		"category": item_data.get("category", ""),
		"rarity": item_data.get("rarity", "common"),
		"position": [grid_pos.x, grid_pos.y],
		"shape": item_data.get("shape", [[0, 0]])
	}
	var inventory_item = APITypes.InventoryItem.new(item_dict)

	# Add the item to the grid
	_add_item(inventory_item)

	# Emit signal
	item_placed.emit(inventory_item, grid_pos)

	return true

func show_hover_preview_for_shop(item_data: Dictionary, grid_pos: Vector2i):
	"""Show hover preview for a shop item being dragged"""
	# Safety check - ensure hover_preview exists
	if not hover_preview or not is_instance_valid(hover_preview):
		_create_hover_preview()

	if can_place_item(item_data, grid_pos):
		hover_preview.visible = true
		hover_preview.position = grid_to_pixel(grid_pos)

		# Calculate hover size from shape
		var max_x = 0
		var max_y = 0
		var shape = item_data.get("shape", [[0, 0]])
		for offset in shape:
			if offset is Array and offset.size() >= 2:
				max_x = max(max_x, offset[0])
				max_y = max(max_y, offset[1])

		hover_preview.size = Vector2(
			(max_x + 1) * (cell_size + cell_spacing) - cell_spacing,
			(max_y + 1) * (cell_size + cell_spacing) - cell_spacing
		)

		# Green for valid placement
		var style = hover_preview.get_theme_stylebox("panel")
		if style:
			style.bg_color = Color(0.3, 1.0, 0.3, 0.3)
			style.border_color = Color(0.5, 1.0, 0.5, 0.8)
	else:
		if hover_preview and is_instance_valid(hover_preview):
			hover_preview.visible = false

func hide_hover_preview():
	"""Hide the hover preview"""
	if hover_preview and is_instance_valid(hover_preview):
		hover_preview.visible = false

func _remove_item(item_visual: Control):
	"""Remove an item from the grid"""
	var grid_pos = item_visual.get_meta("grid_pos")
	var item_data = item_visual.get_meta("item_data")

	# Clear from grid
	for offset in item_data.shape:
		if offset is Array and offset.size() >= 2:
			var cell_x = grid_pos.x + offset[0]
			var cell_y = grid_pos.y + offset[1]
			if cell_x >= 0 and cell_y >= 0 and cell_x < grid_width and cell_y < grid_height:
				item_grid[cell_y][cell_x] = null

	items.erase(item_visual)
	item_visual.queue_free()
	item_removed.emit(item_data, grid_pos)

func _process(_delta):
	"""Update dragging and hover preview"""
	if dragging_object:
		# Update position smoothly
		var target_pos = get_local_mouse_position() + drag_offset
		dragging_object.position = target_pos

		# Update hover preview - check if valid first
		if not hover_preview or not is_instance_valid(hover_preview):
			return  # Skip hover preview updates if it's invalid

		var grid_pos = pixel_to_grid(get_local_mouse_position())
		var item_data = dragging_object.get_meta("item_data")

		if _can_place_item(item_data, grid_pos):
			hover_preview.visible = true
			hover_preview.position = grid_to_pixel(grid_pos)

			# Calculate hover size from shape
			var max_x = 0
			var max_y = 0
			for offset in item_data.shape:
				if offset is Array and offset.size() >= 2:
					max_x = max(max_x, offset[0])
					max_y = max(max_y, offset[1])

			hover_preview.size = Vector2(
				(max_x + 1) * (cell_size + cell_spacing) - cell_spacing,
				(max_y + 1) * (cell_size + cell_spacing) - cell_spacing
			)

			# Green for valid placement
			var style = hover_preview.get_theme_stylebox("panel")
			style.bg_color = Color(0.3, 1.0, 0.3, 0.3)
			style.border_color = Color(0.5, 1.0, 0.5, 0.8)
		else:
			hover_preview.visible = false

func clear_all():
	"""Clear all items and containers"""
	# Remove all item visuals
	for item_visual in items:
		item_visual.queue_free()
	items.clear()

	# Remove all container visuals
	for container_data in containers:
		container_data.visual.queue_free()
	containers.clear()

	# Reset hover preview
	hover_preview = null

	# Reset grids
	_initialize_grids()
	_setup_visual()
	_create_hover_preview()

func get_inventory_state() -> Dictionary:
	"""Get current inventory state for saving"""
	var state = {
		"items": [],
		"servers": []
	}

	# Save items - convert to dictionaries for persistence
	for item_visual in items:
		var item_data = item_visual.get_meta("item_data")
		var grid_pos = item_visual.get_meta("grid_pos")

		# Convert InventoryItem to dictionary for saving, preserving position
		var item_dict
		if item_data is APITypes.InventoryItem:
			item_dict = item_data.to_dict()
		else:
			item_dict = item_data if item_data is Dictionary else {}

		item_dict["position"] = {"x": grid_pos.x, "y": grid_pos.y}

		state.items.append(item_dict)

	# Save containers - convert to dictionaries for persistence
	for container_data in containers:
		var container = container_data.data
		if container is APITypes.ServerContainer:
			state.servers.append(container.to_dict())
		else:
			state.servers.append(container)

	return state

func set_colors(new_grid_color: Color, new_border_color: Color, new_item_color: Color, new_server_color: Color = Color(0.3, 0.4, 0.5, 0.3)):
	"""Update grid colors"""
	grid_color = new_grid_color
	border_color = new_border_color
	item_color = new_item_color
	server_color = new_server_color

	# Refresh visual if already created
	if get_child_count() > 0:
		_setup_visual()
		# Reload current state to apply new colors
		var current_state = get_inventory_state()
		if current_state.servers.size() > 0 or current_state.items.size() > 0:
			var typed_state = APITypes.InventoryState.new(current_state)
			load_inventory_state(typed_state)
