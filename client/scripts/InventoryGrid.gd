extends Control
class_name InventoryGrid

# Simple grid component for displaying inventory items
# Can be used in read-only mode (BattleScreen) or interactive mode (UnifiedGridUI)

const APITypes = preload("res://scripts/api_types.gd")

# Grid settings
const CELL_SIZE = 32
const CELL_SPACING = 2
const GRID_WIDTH = 10
const GRID_HEIGHT = 6

# Visual settings
var grid_color = Color(0.15, 0.15, 0.2, 0.8)
var border_color = Color(0.3, 0.6, 1.0, 0.8)
var item_color = Color(0.2, 0.5, 1.0, 0.9)

# Mode
var read_only: bool = false
var title: String = "Inventory"

# Grid data
var items: Array = []
var containers: Array = []
var grid_cells: Array = []

signal item_clicked(item)
signal cell_clicked(x, y)

func _ready():
	custom_minimum_size = Vector2(
		GRID_WIDTH * (CELL_SIZE + CELL_SPACING),
		GRID_HEIGHT * (CELL_SIZE + CELL_SPACING)
	)
	_setup_grid()

func _setup_grid():
	# Create background
	var bg = Panel.new()
	bg.size = custom_minimum_size
	var style = StyleBoxFlat.new()
	style.bg_color = grid_color
	style.border_color = border_color
	style.set_border_width_all(2)
	bg.add_theme_stylebox_override("panel", style)
	add_child(bg)

	# Create grid cells
	grid_cells = []
	for y in range(GRID_HEIGHT):
		var row = []
		for x in range(GRID_WIDTH):
			var cell = Panel.new()
			cell.position = Vector2(
				x * (CELL_SIZE + CELL_SPACING) + CELL_SPACING,
				y * (CELL_SIZE + CELL_SPACING) + CELL_SPACING
			)
			cell.size = Vector2(CELL_SIZE, CELL_SIZE)

			var cell_style = StyleBoxFlat.new()
			cell_style.bg_color = Color(0.1, 0.1, 0.15, 0.5)
			cell_style.border_color = Color(0.2, 0.2, 0.3, 0.5)
			cell_style.set_border_width_all(1)
			cell.add_theme_stylebox_override("panel", cell_style)

			add_child(cell)
			row.append(cell)
		grid_cells.append(row)

	# Add title if provided
	if title != "":
		var title_label = Label.new()
		title_label.text = title
		title_label.position = Vector2(5, -20)
		title_label.add_theme_font_size_override("font_size", 14)
		add_child(title_label)

func load_inventory_state(inventory_state: APITypes.InventoryState):
	clear_items()

	# Load containers first (server racks)
	for container_data in inventory_state.containers:
		_add_container(container_data)

	# Load items
	for item_data in inventory_state.items:
		_add_item(item_data)

func _add_container(container: APITypes.ServerContainer):
	if not container.position:
		return

	var x = container.position.x
	var y = container.position.y

	# Draw container cells
	for cy in range(container.height):
		for cx in range(container.width):
			var grid_x = x + cx
			var grid_y = y + cy
			if grid_x >= 0 and grid_x < GRID_WIDTH and grid_y >= 0 and grid_y < GRID_HEIGHT:
				var cell = grid_cells[grid_y][grid_x]
				var style = StyleBoxFlat.new()
				style.bg_color = Color(0.2, 0.3, 0.5, 0.3)
				style.border_color = Color(0.3, 0.5, 0.8, 0.8)
				style.set_border_width_all(2)
				cell.add_theme_stylebox_override("panel", style)

	containers.append(container)

func _add_item(item: APITypes.InventoryItem):
	if not item.position:
		return

	var x = item.position.x
	var y = item.position.y

	# Create item visual
	var item_panel = Panel.new()
	item_panel.position = Vector2(
		x * (CELL_SIZE + CELL_SPACING) + CELL_SPACING,
		y * (CELL_SIZE + CELL_SPACING) + CELL_SPACING
	)

	# Calculate size from shape
	var max_x = 0
	var max_y = 0
	for offset in item.shape:
		if offset is Array and offset.size() >= 2:
			max_x = max(max_x, offset[0])
			max_y = max(max_y, offset[1])

	item_panel.size = Vector2(
		(max_x + 1) * (CELL_SIZE + CELL_SPACING) - CELL_SPACING,
		(max_y + 1) * (CELL_SIZE + CELL_SPACING) - CELL_SPACING
	)

	var item_style = StyleBoxFlat.new()
	item_style.bg_color = item_color
	item_style.border_color = Color(0.4, 0.7, 1.0, 1.0)
	item_style.set_border_width_all(2)
	item_panel.add_theme_stylebox_override("panel", item_style)

	# Add item name label
	var label = Label.new()
	label.text = item.name if item.name else item.item_type
	label.add_theme_font_size_override("font_size", 10)
	label.position = Vector2(2, 2)
	item_panel.add_child(label)

	# Handle clicks if not read-only
	if not read_only:
		item_panel.gui_input.connect(_on_item_input.bind(item))

	add_child(item_panel)
	items.append({"panel": item_panel, "data": item})

func _on_item_input(event: InputEvent, item):
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		item_clicked.emit(item)

func clear_items():
	for item_data in items:
		if item_data.panel:
			item_data.panel.queue_free()
	items.clear()

	# Reset container visuals
	for y in range(GRID_HEIGHT):
		for x in range(GRID_WIDTH):
			var cell = grid_cells[y][x]
			var cell_style = StyleBoxFlat.new()
			cell_style.bg_color = Color(0.1, 0.1, 0.15, 0.5)
			cell_style.border_color = Color(0.2, 0.2, 0.3, 0.5)
			cell_style.set_border_width_all(1)
			cell.add_theme_stylebox_override("panel", cell_style)
	containers.clear()

func set_colors(new_grid_color: Color, new_border_color: Color, new_item_color: Color):
	grid_color = new_grid_color
	border_color = new_border_color
	item_color = new_item_color

	# Update background
	if get_child_count() > 0:
		var bg = get_child(0)
		if bg is Panel:
			var style = bg.get_theme_stylebox("panel")
			if style:
				style.bg_color = grid_color
				style.border_color = border_color
