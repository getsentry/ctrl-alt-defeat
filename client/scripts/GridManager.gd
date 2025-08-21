extends Control
class_name GridManager

# Grid configuration
var grid_width: int = 9
var grid_height: int = 7
var cell_spacing: float = 1.0

# Calculated values
var cell_size: float = 45.0
var actual_size: Vector2

# Visual elements
var cells: Array = []  # 2D array of cell visuals
var items: Dictionary = {}  # Items keyed by their position
var servers: Dictionary = {}  # Servers keyed by their position

signal cell_clicked(x: int, y: int)
signal item_dragged(item: Control, from_pos: Vector2i)

func _ready():
	mouse_filter = Control.MOUSE_FILTER_PASS
	_recalculate_size()

func setup(width: int, height: int):
	grid_width = width
	grid_height = height
	_recalculate_size()
	_create_grid_visuals()

func _recalculate_size():
	# Calculate cell size based on our current size
	if size.x > 0 and size.y > 0:
		var available_width = size.x - (grid_width - 1) * cell_spacing
		var available_height = size.y - (grid_height - 1) * cell_spacing
		var cell_width = available_width / grid_width
		var cell_height = available_height / grid_height
		# Keep cells square
		cell_size = min(cell_width, cell_height)

		# Update our actual size based on calculated cell size
		actual_size = Vector2(
			grid_width * cell_size + (grid_width - 1) * cell_spacing,
			grid_height * cell_size + (grid_height - 1) * cell_spacing
		)

func _create_grid_visuals():
	# Clear existing cells
	for row in cells:
		for cell in row:
			if cell:
				cell.queue_free()
	cells.clear()

	# Create new grid
	for y in range(grid_height):
		var row = []
		for x in range(grid_width):
			row.append(null)  # Cells created on demand
		cells.append(row)

func grid_to_pixel(grid_pos: Vector2i) -> Vector2:
	"""Convert grid coordinates to pixel position"""
	return Vector2(
		grid_pos.x * (cell_size + cell_spacing),
		grid_pos.y * (cell_size + cell_spacing)
	)

func pixel_to_grid(pixel_pos: Vector2) -> Vector2i:
	"""Convert pixel position to grid coordinates"""
	var x = int((pixel_pos.x + cell_size/2) / (cell_size + cell_spacing))
	var y = int((pixel_pos.y + cell_size/2) / (cell_size + cell_spacing))
	return Vector2i(
		clamp(x, 0, grid_width - 1),
		clamp(y, 0, grid_height - 1)
	)

func create_cell_visual(x: int, y: int, color: Color = Color(0.2, 0.3, 0.4, 0.3)) -> Panel:
	"""Create a visual cell at the given grid position"""
	if x < 0 or x >= grid_width or y < 0 or y >= grid_height:
		return null

	# Remove existing cell if any
	if cells[y][x]:
		cells[y][x].queue_free()

	var cell = Panel.new()
	cell.position = grid_to_pixel(Vector2i(x, y))
	cell.size = Vector2(cell_size, cell_size)
	cell.mouse_filter = Control.MOUSE_FILTER_IGNORE

	var style = StyleBoxFlat.new()
	style.bg_color = color
	style.border_color = Color(0.0, 1.0, 1.0, 0.5)
	style.set_border_width_all(1)
	cell.add_theme_stylebox_override("panel", style)

	add_child(cell)
	cells[y][x] = cell
	return cell

func place_server(server_data: Dictionary, grid_pos: Vector2i) -> Control:
	"""Place a server visual at the given grid position"""
	var pattern = server_data.get("pattern", [[1]])
	var color = server_data.get("color", Color(0.3, 0.4, 0.5, 0.3))

	# Create server container
	var server = Control.new()
	server.position = grid_to_pixel(grid_pos)
	server.set_meta("grid_pos", grid_pos)
	server.set_meta("server_data", server_data)

	# Calculate server size based on pattern
	var width = pattern[0].size()
	var height = pattern.size()
	server.size = Vector2(
		width * cell_size + (width - 1) * cell_spacing,
		height * cell_size + (height - 1) * cell_spacing
	)

	# Create border panel
	var panel = Panel.new()
	panel.size = server.size
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE

	var style = StyleBoxFlat.new()
	style.bg_color = Color(0, 0, 0, 0)
	style.border_color = color
	style.border_color.a = 0.8
	style.set_border_width_all(3)
	panel.add_theme_stylebox_override("panel", style)
	server.add_child(panel)

	# Create cells for the server pattern
	for py in range(pattern.size()):
		for px in range(pattern[py].size()):
			if pattern[py][px] == 1:
				create_cell_visual(grid_pos.x + px, grid_pos.y + py, color)

	add_child(server)
	servers[grid_pos] = server
	return server

func place_item(item_data: Dictionary, grid_pos: Vector2i) -> Control:
	"""Place an item visual at the given grid position"""
	var item = Control.new()
	item.position = grid_to_pixel(grid_pos)
	item.set_meta("grid_pos", grid_pos)
	item.set_meta("item_data", item_data)

	# Get dimensions
	var width = item_data.get("width", 1)
	var height = item_data.get("height", 1)
	var shape = item_data.get("shape", [[0, 0]])
	var color = item_data.get("color", Color(0.3, 0.9, 0.6, 1.0))

	item.size = Vector2(
		width * cell_size + (width - 1) * cell_spacing,
		height * cell_size + (height - 1) * cell_spacing
	)

	# Create visual for each cell in the shape
	for offset in shape:
		if offset is Array and offset.size() >= 2:
			var cell = Panel.new()
			cell.position = Vector2(
				offset[0] * (cell_size + cell_spacing),
				offset[1] * (cell_size + cell_spacing)
			)
			cell.size = Vector2(cell_size, cell_size)
			cell.mouse_filter = Control.MOUSE_FILTER_IGNORE

			var style = StyleBoxFlat.new()
			style.bg_color = color
			style.border_color = color * 1.2
			style.set_border_width_all(2)
			style.set_corner_radius_all(4)
			cell.add_theme_stylebox_override("panel", style)
			item.add_child(cell)

	# Add label if item has a name
	if item_data.has("name"):
		var label = Label.new()
		label.text = item_data.name
		label.add_theme_font_size_override("font_size", 10)
		label.position = Vector2(2, 2)
		item.add_child(label)

	add_child(item)
	items[grid_pos] = item
	return item

func remove_item(grid_pos: Vector2i):
	"""Remove an item at the given position"""
	if grid_pos in items:
		items[grid_pos].queue_free()
		items.erase(grid_pos)

func remove_server(grid_pos: Vector2i):
	"""Remove a server at the given position"""
	if grid_pos in servers:
		servers[grid_pos].queue_free()
		servers.erase(grid_pos)

func clear_all():
	"""Clear all items and servers"""
	for item in items.values():
		item.queue_free()
	items.clear()

	for server in servers.values():
		server.queue_free()
	servers.clear()

	for row in cells:
		for cell in row:
			if cell:
				cell.queue_free()
	_create_grid_visuals()

func _notification(what):
	if what == NOTIFICATION_RESIZED:
		_recalculate_size()
		# Reposition all existing elements
		for pos in servers:
			servers[pos].position = grid_to_pixel(pos)
			_update_server_size(servers[pos])
		for pos in items:
			items[pos].position = grid_to_pixel(pos)
			_update_item_size(items[pos])
		# Update cell visuals
		for y in range(cells.size()):
			for x in range(cells[y].size()):
				if cells[y][x]:
					cells[y][x].position = grid_to_pixel(Vector2i(x, y))
					cells[y][x].size = Vector2(cell_size, cell_size)

func _update_server_size(server: Control):
	"""Update server size based on new cell size"""
	var server_data = server.get_meta("server_data")
	var pattern = server_data.get("pattern", [[1]])
	var width = pattern[0].size()
	var height = pattern.size()
	server.size = Vector2(
		width * cell_size + (width - 1) * cell_spacing,
		height * cell_size + (height - 1) * cell_spacing
	)
	# Update panel child
	if server.get_child_count() > 0:
		server.get_child(0).size = server.size

func _update_item_size(item: Control):
	"""Update item size based on new cell size"""
	var item_data = item.get_meta("item_data")
	var width = item_data.get("width", 1)
	var height = item_data.get("height", 1)
	item.size = Vector2(
		width * cell_size + (width - 1) * cell_spacing,
		height * cell_size + (height - 1) * cell_spacing
	)
	# Update child cells
	var shape = item_data.get("shape", [[0, 0]])
	var child_idx = 0
	for offset in shape:
		if offset is Array and offset.size() >= 2:
			if child_idx < item.get_child_count():
				var cell = item.get_child(child_idx)
				if cell is Panel:
					cell.position = Vector2(
						offset[0] * (cell_size + cell_spacing),
						offset[1] * (cell_size + cell_spacing)
					)
					cell.size = Vector2(cell_size, cell_size)
			child_idx += 1
