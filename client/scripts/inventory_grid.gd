extends Control
class_name InventoryGrid

# Grid component that handles all inventory display and interaction
# Used by UnifiedGridUI for the main game and BattleScreen for replays


# A container on the grid: what the server says it is, and what is drawn for it.
class PlacedContainer extends RefCounted:
	var container: APITypes.PlacedItem
	var visual: ItemVisual

	func _init(server_container: APITypes.PlacedItem, drawn: ItemVisual):
		container = server_container
		visual = drawn

	func position() -> Vector2i:
		return Vector2i(container.position.x, container.position.y)


# An item travelling with a container while it is dragged: the drawing, and
# where it sits relative to the container carrying it. One thing rather than
# two lists that have to be kept the same length and the same order.
class Rider extends RefCounted:
	var visual: ItemVisual
	var offset: Vector2

	func _init(item_visual: ItemVisual, container_at: Vector2):
		visual = item_visual
		offset = item_visual.position - container_at

	func follow(container_at: Vector2) -> void:
		visual.position = container_at + offset

	func id() -> String:
		return visual.get_meta("item_data").id

const APITypes = preload("res://scripts/api_types.gd")
const ItemVisual = preload("res://scripts/item_visual.gd")
const ItemPlaceholder = preload("res://scripts/item_placeholder.gd")

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

## Whether to draw the empty squares behind the containers.
##
## They are placement guides: they say where a thing could go. In a battle
## nothing can be placed, so they say nothing, and drawing them turns two
## builds into two sheets of graph paper. Set this before configure().
var show_base_grid: bool = true

# The grid, as rows of columns, indexed [y][x]. Godot has no nested typed
# collections, so the element type is written here.
var active_grid: Array = []  # Array[Array[bool]]: is this cell on a container?
var item_grid: Array = []    # Array[Array[Control]]: the item here, or null
var grid_cells: Array = []   # Array[Array[Panel]]: the cell's background panel

# Stored objects
var items: Array[Control] = []  # The item visuals on the grid
var containers: Array[PlacedContainer] = []

# Where an item can be dropped to sell it. The parent owns the chest and
# hands it over; the grid only needs somewhere to test the pointer against.
var sell_zone: Control = null
var storage_zone: Control = null
# The grid an item dragged out of this one goes to. It draws its own hover
# preview while the pointer is over it, because the square under the pointer is
# one of its squares and not one of ours.
var grid_zone: InventoryGrid = null
# Whether a square in this grid is a place the server knows about. The chest
# lays itself out from scratch every time, so moving something inside it means
# nothing and must not be sent anywhere.
var saves_positions: bool = true

# Drag and drop state
var dragging_object = null
# A container being dragged, and the items riding on it. They travel together,
# because that is what the move does.
var dragging_container: PlacedContainer = null
var container_riders: Array[Rider] = []
var drag_offset = Vector2.ZERO
## Which of the item's own squares the player has hold of.
##
## A spear is four squares long, and the mark that says where it would land
## goes under the square its corner is on -- not under the pointer. Picked up
## by its tip, those are three squares apart: the mark sat a spear's length
## from the spear, and the drop followed the mark rather than the artwork.
##
## The corner square when the pointer is not on the item at all, which is where
## a pointer is in a test: there is no mouse to put on it.
var grab_cell := Vector2i.ZERO
var original_position = Vector2.ZERO
var original_grid_pos = Vector2i(-1, -1)
# Which way the item was facing when it was picked up. Turning it and putting
# it back down on the same square is a change, even though it has not moved.
var original_facing := 0
var hover_preview: Panel = null
## What the mark is drawn as at the moment, so it is only drawn again when it
## has something else to say. See mark_square().
var _marked_squares: Array[Vector2i] = []
var _marked_allowed := false
var valid_placement = false

## What the mark under a held item looks like. Green is "let go here", red is
## "not here" -- one glance, no reading.
## Which layer the mark is drawn on. Above everything the grid holds, held
## containers included. A container is a picture with a background of its own
## now, so a mark drawn under one is a mark nobody sees -- and that is worst
## while a container is in hand, because the thing hiding the mark is the very
## thing being placed. The fill is faint and the edge is not, so on top it
## reads as a highlight over the artwork rather than a patch across it.
const MARK_LAYER := 20
## How solid a container is drawn. A little short of solid, so the squares it
## covers, and anything marked on them, show through the picture.
const CONTAINER_ALPHA := 0.8
const MARK_ALLOWED_FILL := Color(0.25, 1.0, 0.45, 0.3)
const MARK_ALLOWED_EDGE := Color(0.45, 1.0, 0.6, 0.9)
const MARK_REFUSED_FILL := Color(1.0, 0.2, 0.3, 0.28)
const MARK_REFUSED_EDGE := Color(1.0, 0.35, 0.45, 0.9)

# Signals
signal item_clicked(item)
signal item_placed(item_data, grid_pos)
signal item_removed(item_data, grid_pos)
signal item_sold(item_data)
signal drag_started(item_data)
signal drag_ended()
signal item_moved(item_id, from_pos, to_pos)
signal item_stored(item_data: APITypes.PlacedItem)
# Dragged out of the chest and dropped on the main grid. Carries where it was
# dropped, because the chest cannot work out a square on someone else's grid.
signal item_unstored(item_data: APITypes.PlacedItem, global_pos: Vector2)
# A container has been dropped somewhere it can stand. Whoever owns the grid
# asks the server, because what comes back is the whole board: the container
# carries its items, and any it cannot carry are set down in the chest.
signal container_dropped(container_data: APITypes.PlacedItem, grid_pos: Vector2i, rider_ids: Array[String])
# The server answers a move with the whole inventory, the chest included. The
# grid draws only the grid, so it passes the rest on rather than keeping it.
signal inventory_returned(response)

## An item was put down on squares other items already hold. What becomes of
## them is more than a grid can arrange -- one goes into the player's hand and
## the rest into the chest -- so the screen answers this.
##
## Each entry of `displaced` is the item and where on screen it was, which is
## where it is thrown into the chest from.
signal items_displaced(item_data: APITypes.Item, grid_pos: Vector2i, displaced: Array)

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
	style.bg_color = Color(0.05, 0.1, 0.15, 0.2) if show_base_grid else Color.TRANSPARENT
	style.border_color = border_color if show_base_grid else Color.TRANSPARENT
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
	# An empty square is only worth drawing while something is being placed on
	# it. Where nothing can be placed, the containers are the whole picture.
	cell.visible = show_base_grid

	var cell_style = StyleBoxFlat.new()
	cell_style.bg_color = Color(0.1, 0.1, 0.15, 0.3)
	cell_style.border_color = Color(0.2, 0.2, 0.3, 0.3)
	cell_style.set_border_width_all(1)
	cell.add_theme_stylebox_override("panel", cell_style)

	add_child(cell)
	return cell

func _create_hover_preview():
	"""Create the hover preview panel for placement feedback.

	It draws nothing itself: the mark is one patch per square the shape covers,
	and this is what holds them and puts them where the pointer is.
	"""
	hover_preview = Panel.new()
	hover_preview.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hover_preview.visible = false
	hover_preview.z_index = MARK_LAYER
	hover_preview.add_theme_stylebox_override("panel", StyleBoxEmpty.new())
	add_child(hover_preview)
	# A new mark has nothing drawn on it, whatever the old one was showing.
	_marked_squares = []

func item_visual(item_id: String) -> ItemVisual:
	"""The drawing of one item, by the id the server calls it.

	The battle timeline names the item behind every action by its own uid, so
	this is what turns "something happened" into "that one, there".
	"""
	for visual in items:
		var data = visual.get_meta("item_data")
		if data != null and data.id == item_id:
			return visual
	return null


func grid_to_pixel(grid_pos: Vector2i) -> Vector2:
	"""Convert grid coordinates to pixel position"""
	return Vector2(
		grid_pos.x * (cell_size + cell_spacing) + cell_spacing,
		grid_pos.y * (cell_size + cell_spacing) + cell_spacing
	)

func square_grabbed(corner: Vector2, item_shape: Array[Vector2i],
		pointer: Vector2) -> Vector2i:
	"""Which of a body's own squares this pointer is on.

	Takes the corner and the shape rather than a node, so a container can ask
	it as readily as an item: the two are drawn by different things and held
	the same way.

	The corner square where the pointer is not on the body, so something taken
	hold of from nowhere in particular is held the way it always was.
	"""
	var within := pointer - corner
	if within.x < 0 or within.y < 0:
		return Vector2i.ZERO
	var step := cell_size + cell_spacing
	var square := Vector2i(int(within.x / step), int(within.y / step))
	return square if item_shape.has(square) else Vector2i.ZERO


func carried_corner(pointer_local: Vector2, item_shape: Array[Vector2i]) -> Vector2:
	"""Where the corner of a carried item goes, for a pointer at this place.

	Under the middle of its own artwork, because nobody chose a square to hold
	it by: it came off a shelf, out of the chest, or was handed back when a
	container moved.

	Held by its middle SQUARE instead -- which is what this did for a while --
	the artwork sat off the pointer by up to a whole cell for 129 of the 222
	items, every shape whose box is an even number of squares across. Turning
	one then swung the picture about a point that was not under the hand.
	"""
	return pointer_local - _shape_extent(item_shape) / 2.0


func square_for_corner(local_corner: Vector2) -> Vector2i:
	"""The square an item drawn with its corner here would land on.

	Rounded rather than floored: a carried item floats between squares, and
	the one it lands on is the one it is nearest. This is the exact inverse of
	grid_to_pixel, so the mark can never disagree with the artwork -- it is
	worked out from where the artwork is.
	"""
	var step := cell_size + cell_spacing
	return Vector2i(
		roundi((local_corner.x - cell_spacing) / step),
		roundi((local_corner.y - cell_spacing) / step))


func square_held_over(pointer: Vector2, held_by: Vector2i) -> Vector2i:
	"""The square the corner of a held item is over, for a pointer here.

	The pointer's own square, less the square the item is held by. Held by its
	corner those are the same; held by the tip of a spear they are a spear
	apart, and it is the corner that says where the item goes.

	Off the board stays off the board: there is no square to count back from.
	"""
	var here := pixel_to_grid(get_global_transform().affine_inverse() * pointer)
	if here.x < 0 or here.y < 0:
		return here
	return here - held_by


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

func _add_container(container: APITypes.PlacedItem):
	"""Add a server container to the grid"""
	if not container.position:
		return

	var x = container.position.x
	var y = container.position.y

	# Create container visual using ItemVisual
	var container_visual = ItemVisual.new()
	container_visual.position = grid_to_pixel(Vector2i(x, y))

	# A container is hovered only where nothing stands on it. Items are added
	# to the grid after containers, so an item is the later sibling and takes
	# the hover for the squares it covers. That is what stops an item and the
	# container under it from both describing themselves at once.
	#
	# The mouse filter is not set here: setup() below decides it, the same way
	# it does for an item.
	container_visual.enable_tooltip = true

	# Set up the visual
	container_visual.setup(container, cell_size, cell_spacing)
	container_visual.modulate.a = CONTAINER_ALPHA

	# Update grid cells to show server pattern and mark as active
	for square in container.covered_squares():
		var grid_x = square.x
		var grid_y = square.y
		if grid_x >= 0 and grid_x < grid_width and grid_y >= 0 and grid_y < grid_height:
			# Mark as active for placement
			active_grid[grid_y][grid_x] = true

			# Update visual. A container's own squares are drawn whether or
			# not the empty grid behind them is.
			var cell = grid_cells[grid_y][grid_x]
			if cell:
				cell.visible = true
				var style = StyleBoxFlat.new()
				style.bg_color = Color(0.2, 0.3, 0.5, 0.3)
				style.border_color = Color(0.3, 0.5, 0.8, 0.6)
				style.set_border_width_all(1)
				cell.add_theme_stylebox_override("panel", style)

	add_child(container_visual)
	var placed = PlacedContainer.new(container, container_visual)
	containers.append(placed)

	if not read_only:
		container_visual.gui_input.connect(_on_container_input.bind(placed))

func _add_item(item: APITypes.PlacedItem):
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
	for offset in item.turned_shape():
		var cell_x = x + offset[0]
		var cell_y = y + offset[1]
		if cell_x >= 0 and cell_y >= 0 and cell_x < grid_width and cell_y < grid_height:
			item_grid[cell_y][cell_x] = item_visual

	# Connect input if not read-only
	if not read_only:
		item_visual.gui_input.connect(_on_item_input.bind(item_visual))

	add_child(item_visual)
	items.append(item_visual)

func turn_dragged(quarters: int, pointer: Vector2) -> bool:
	"""Turn the item being dragged, and say whether there was one.

	The pointer is told, not read. A turn that does not know where the hand is
	cannot say where the item went, and a drag nobody could place is how the
	mark came to be drawn a spear's length from the spear.

	A container is not turned. Turning one would have to turn everything
	standing on it about its anchor, which is a different thing from turning
	an item and is not built.
	"""
	if not dragging_object:
		return false

	var was: Array[Vector2i] = dragging_object.get_meta("item_data").turned_shape()
	var turned = dragging_object.get_meta("item_data").turned(quarters)
	dragging_object.set_meta("item_data", turned)

	# Drawn again, because the squares it covers have changed.
	dragging_object.redraw_as(turned)

	# It swings about the square in hand rather than about its corner. Turned
	# about the corner, a spear held by its tip throws itself a length across
	# the board and leaves the mark behind: the player is holding one end of it
	# and the game has moved the other one.
	#
	# Keeping that square under the pointer means moving the corner by however
	# far the square moved, which needs no pointer to work out -- and so a turn
	# looks the same to a test as it does to a hand.
	var swung := APITypes.turn_within(was, posmod(quarters * 90, 360), grab_cell)
	var step := cell_size + cell_spacing
	var moved := Vector2(grab_cell - swung) * step
	grab_cell = swung
	drag_offset += moved
	dragging_object.position += moved

	# And the mark, which is a different set of squares now and in a different
	# place. Left to the next frame, a turn showed the shape the item had
	# before it until the pointer moved.
	update_drag_preview(pointer)
	return true


func _on_container_input(event: InputEvent, placed: PlacedContainer):
	"""Handle input on containers for dragging"""
	if read_only:
		return

	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		if event.pressed:
			# Taken hold of where the click landed, so a rack grabbed by its
			# far corner is carried by that corner.
			_start_container_drag(placed,
				placed.visual.get_global_transform() * event.position)
		else:
			_end_container_drag()


func can_place_container(container: APITypes.Item, grid_pos: Vector2i) -> bool:
	"""Whether a container may stand with its anchor on this square.

	A container needs squares that are free, where an item needs squares that a
	container has made usable. That is why this is not _can_place_item: the two
	ask opposite questions of the same board.
	"""
	if grid_pos.x < 0 or grid_pos.y < 0:
		return false

	var taken: Dictionary[Vector2i, bool] = {}
	for placed in containers:
		if placed.container.id == container.id:
			continue  # It is no obstacle to itself.
		for square in placed.container.covered_squares():
			taken[square] = true

	for offset in container.turned_shape():
		var square := Vector2i(grid_pos.x + int(offset[0]), grid_pos.y + int(offset[1]))
		if square.x < 0 or square.x >= grid_width:
			return false
		if square.y < 0 or square.y >= grid_height:
			return false
		if taken.has(square):
			return false
	return true


func _start_container_drag(placed: PlacedContainer, taken_at: Vector2) -> void:
	"""Pick a container up, and everything standing on it with it.

	Where it was taken hold of is told, not read, the same as for an item:
	which of its own squares is in hand decides where the mark goes.
	"""
	if read_only or dragging_object:
		return

	dragging_container = placed
	original_grid_pos = placed.position()
	var taken := get_global_transform().affine_inverse() * taken_at
	drag_offset = placed.visual.position - taken
	# By one of its own squares, the same as an item. Marked at the pointer's
	# square instead, a rack grabbed by any square but its corner was drawn in
	# one place and marked in another -- and dropped where the mark was.
	grab_cell = square_grabbed(
		placed.visual.position, placed.container.turned_shape(), taken)
	move_child(placed.visual, get_child_count() - 1)
	placed.visual.z_index = 10

	# Whatever has a square on it travels with it, which is the same rule the
	# server uses when it works out what the move carries.
	var covered: Dictionary[Vector2i, bool] = {}
	for square in placed.container.covered_squares():
		covered[square] = true

	container_riders = []
	for item_visual in items:
		for square in item_visual.get_meta("item_data").covered_squares():
			if covered.has(square):
				container_riders.append(Rider.new(item_visual, placed.visual.position))
				move_child(item_visual, get_child_count() - 1)
				item_visual.z_index = 11
				break


func _end_container_drag() -> void:
	"""Put a dragged container down where the pointer is"""
	drop_container_at(get_global_mouse_position())


func drop_container_at(pointer: Vector2) -> void:
	"""Put a dragged container down at this place.

	Takes the pointer rather than reading it, so where a container lands can be
	asked about without a mouse.
	"""
	if not dragging_container:
		return

	var placed := dragging_container
	dragging_container = null
	hide_hover_preview()
	placed.visual.z_index = 0
	for rider in container_riders:
		rider.visual.z_index = 0

	var grid_pos := square_held_over(pointer, grab_cell)
	if grid_pos != original_grid_pos and can_place_container(placed.container, grid_pos):
		# The riders go with it, so which of them the move could not find room
		# for is answered by which of these is missing afterwards.
		var rider_ids: Array[String] = []
		for rider in container_riders:
			rider_ids.append(rider.id())
		container_riders = []
		container_dropped.emit(placed.container, grid_pos, rider_ids)
		return

	# Nowhere it can stand, so it and its passengers go back where they were.
	_return_container(placed)


func _return_container(placed: PlacedContainer) -> void:
	"""Put a container and its passengers back where they were picked up"""
	placed.visual.position = grid_to_pixel(original_grid_pos)
	for rider in container_riders:
		rider.follow(placed.visual.position)
	container_riders = []


func _on_item_input(event: InputEvent, item_visual: Control):
	"""Handle input on items for dragging"""
	if read_only:
		return

	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_LEFT:
			if event.pressed:
				# On the item, not merely inside the box around it. The empty
				# corner of an L is where its aura is drawn, and a player
				# aiming at what the aura reaches was picking the item up.
				if not item_visual.covers_point(event.position):
					return
				# Taken hold of where the click landed, so a spear grabbed by
				# the tip is carried by the tip.
				_start_drag(item_visual,
					item_visual.get_global_transform() * event.position)
			else:
				# End dragging
				_end_drag()

func _start_drag(item_visual: Control, taken_at: Vector2):
	"""Start dragging an item, taken hold of at this point.

	Where the hand is decides which of the item's own squares is in hand, and
	that decides where the mark goes. Told, not read: headless has no pointer
	to put on an item, so a drag that read one could not be placed by a test.
	"""
	# Don't allow dragging in read-only mode
	if read_only:
		return

	dragging_object = item_visual
	drag_started.emit(item_visual.get_meta("item_data"))
	original_position = item_visual.position
	original_grid_pos = item_visual.get_meta("grid_pos")
	original_facing = item_visual.get_meta("item_data").facing()
	var taken := get_global_transform().affine_inverse() * taken_at
	drag_offset = item_visual.position - taken
	grab_cell = square_grabbed(item_visual.position,
		item_visual.get_meta("item_data").turned_shape(), taken)

	# Ensure the item visual stays at its proper size while dragging
	item_visual.z_index = 10  # Bring to front

	# Clear item from grid
	var item_data = item_visual.get_meta("item_data")
	for offset in item_data.turned_shape():
		var cell_x = original_grid_pos.x + offset[0]
		var cell_y = original_grid_pos.y + offset[1]
		if cell_x >= 0 and cell_y >= 0 and cell_x < grid_width and cell_y < grid_height:
			item_grid[cell_y][cell_x] = null

	# Move to top for dragging (visual hierarchy)
	move_child(item_visual, get_child_count() - 1)

func _pointer_is_over_grid_zone(pointer: Vector2) -> bool:
	"""Whether the pointer is over the grid this item would move to"""
	if not grid_zone or not grid_zone.is_inside_tree():
		return false
	return grid_zone.get_global_rect().has_point(pointer)


func _grid_zone_square(pointer: Vector2) -> Vector2i:
	"""The square under the pointer, in the other grid's squares"""
	return grid_zone.square_held_over(pointer, grab_cell)


func _end_drag(dropped_at := Vector2.INF):
	"""Finish a drag, at the pointer unless told somewhere else.

	The shop's own drag already takes its drop point as an argument. This one
	read the pointer four times over, which a test cannot place: headless has
	no pointer to warp.
	"""
	if dropped_at == Vector2.INF:
		dropped_at = get_global_mouse_position()

	if not dragging_object:
		return
	if grid_zone:
		grid_zone.hide_hover_preview()

	# The square comes from where the drop landed, not from the pointer. They
	# are the same thing in a real drag, and only the first can be placed by a
	# test -- which is what the drop point is for.
	var grid_pos = square_held_over(dropped_at, grab_cell)
	var item_data = dragging_object.get_meta("item_data")
	var temp_object = dragging_object
	dragging_object = null
	# Through the guarded one: a drag can outlive the preview -- teardown frees
	# it while the drag is still on -- and assigning to a freed object is an
	# error printed on every run, which is how a run nobody reads is made.
	hide_hover_preview()
	drag_ended.emit()

	# Dropped on the chest, so sell it rather than place it. The cells were
	# already cleared when the drag began.
	if sell_zone and sell_zone.get_global_rect().has_point(dropped_at):
		items.erase(temp_object)
		temp_object.queue_free()
		item_sold.emit(item_data)
		return

	# Dropped on the chest, so take it off the grid and let the owner ask the
	# server to store it. The cells were already cleared when the drag began.
	if storage_zone and storage_zone.get_global_rect().has_point(dropped_at):
		items.erase(temp_object)
		temp_object.queue_free()
		item_stored.emit(item_data)
		return

	# Dragged out of the chest onto the main grid. Which square that is belongs
	# to the other grid to decide, so this one only says where the drop landed.
	if grid_zone and grid_zone.get_global_rect().has_point(dropped_at):
		items.erase(temp_object)
		temp_object.queue_free()
		item_unstored.emit(item_data, dropped_at)
		return

	if drop_changes_nothing(grid_pos, item_data):
		# Nothing to tell the server, so it is put back and that is that.
		_place_item_at(temp_object, original_grid_pos, original_facing)
		return

	# Shuffling things around inside the chest changes nothing the server holds,
	# so it is drawn and not sent. Its squares are not places, and sending one
	# would read as a square on the main grid.
	if not saves_positions:
		if _can_place_item(item_data, grid_pos):
			_place_item_at(temp_object, grid_pos)
		else:
			_place_item_at(temp_object, original_grid_pos, original_facing)
		return

	# Check if the new position is valid
	if _can_place_item(item_data, grid_pos):
		var item_id = item_data.id

		# Call API to move item
		var response = await BattleServerAPI.move_item(
			item_id, [grid_pos.x, grid_pos.y], item_data.facing())
		if response:
			print("Move persisted on server")
			# Move succeeded, place at new position
			_place_item_at(temp_object, grid_pos)
			# Emit signal for any listeners
			item_moved.emit(item_id, original_grid_pos, grid_pos)
			inventory_returned.emit(response)
		else:
			print("Failed to persist move on server, reverting")
			# Move failed, return to original position
			_place_item_at(temp_object, original_grid_pos, original_facing)

	else:
		var in_the_way := displaced_by(item_data, grid_pos)
		# Back where it came from, facing the way it was: either there is
		# nothing to make way, or it waits there until the server has agreed
		# to the swap. An item hanging in the air while the answer comes back
		# reads as a game that has stopped listening.
		_place_item_at(temp_object, original_grid_pos, original_facing)
		if not in_the_way.is_empty():
			items_displaced.emit(item_data, grid_pos, in_the_way)

func drop_changes_nothing(grid_pos: Vector2i, item_data: APITypes.Item) -> bool:
	"""Whether putting the held item down here leaves the board as it was.

	The same square facing the same way is nothing to tell the server about. A
	turn is a change even in place, because the item covers other squares
	afterwards, and a server told nothing keeps a board the player has already
	changed -- which is the board the battle is fought on.
	"""
	return grid_pos == original_grid_pos and item_data.facing() == original_facing


func _place_item_at(item_visual: Control, grid_pos: Vector2i, facing := -1):
	"""Place item visual at grid position, facing the way it is asked to.

	`facing` is for putting an item back. A turn during a drag is already on
	the item, so a drop that comes to nothing has to be told the facing to
	return to as well as the square: put back turned, the item covers squares
	it was never checked against, and the server -- which was told nothing --
	goes on holding the placement the player last agreed to. That is an item
	drawn hanging off the grid until the battle starts and puts it back.
	"""
	item_visual.position = grid_to_pixel(grid_pos)
	item_visual.set_meta("grid_pos", grid_pos)
	item_visual.z_index = 0  # Reset z-index after placing

	# The item itself has to know where it now is. Anything asking which
	# squares it covers -- what a container carries, above all -- reads it from
	# here, and would otherwise be told where the item used to be.
	var was_facing: int = item_visual.get_meta("item_data").facing()
	var item_data = item_visual.get_meta("item_data").placed_at(grid_pos, facing)
	item_visual.set_meta("item_data", item_data)
	# A facing put back is a different set of squares, so it is drawn again.
	if item_data.facing() != was_facing:
		item_visual.redraw_as(item_data)
	for offset in item_data.turned_shape():
		var cell_x = grid_pos.x + offset[0]
		var cell_y = grid_pos.y + offset[1]
		if cell_x >= 0 and cell_y >= 0 and cell_x < grid_width and cell_y < grid_height:
			item_grid[cell_y][cell_x] = item_visual

func can_place_item(item_data, grid_pos: Vector2i) -> bool:
	"""Public method to check if item can be placed at position"""
	return _can_place_item(item_data, grid_pos)


func displaced_by(item_data, grid_pos: Vector2i) -> Array:
	"""The items whose squares this one wants, the biggest of them first.

	Nothing at all where it could not be put down there whatever moved -- off
	the board, or on a square no server covers -- because sweeping items aside
	does not make room that was never there. Nothing either where the squares
	are free, which is an ordinary placement and not a swap.

	Biggest first because that is the one the screen puts in the player's
	hand: the hardest of them to find a new home for, and the one they are
	most likely to want to place next. Ties keep the order the grid holds
	them in, so the same drop always gives the same answer.
	"""
	if not _on_the_board(grid_pos):
		return []

	var in_the_way: Array[Control] = []
	for offset in item_data.turned_shape():
		var cell := Vector2i(grid_pos.x + int(offset[0]), grid_pos.y + int(offset[1]))
		if not _on_the_board(cell) or not active_grid[cell.y][cell.x]:
			return []
		var sitting: Control = item_grid[cell.y][cell.x]
		if sitting == null or sitting == dragging_object:
			continue
		if not in_the_way.has(sitting):
			in_the_way.append(sitting)

	in_the_way.sort_custom(func(one, other):
		return _squares_under(one) > _squares_under(other))

	var found: Array = []
	for visual in in_the_way:
		found.append({
			"item": visual.get_meta("item_data"),
			# Where it is now, because that is where it is thrown from.
			"at": visual.get_global_rect().get_center(),
		})
	return found


func _squares_under(item_visual: Control) -> int:
	"""How much of the board an item covers"""
	return item_visual.get_meta("item_data").turned_shape().size()

func _can_place_item(item_data, grid_pos: Vector2i) -> bool:
	"""Check if item can be placed at position"""
	if grid_pos.x < 0 or grid_pos.y < 0:
		return false

	# Check each cell in the item's shape
	for offset in item_data.turned_shape():
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

func place_shop_item(item: APITypes.Item, grid_pos: Vector2i, facing: int = -1) -> bool:
	"""Place a shop item at the given position, facing the way it is asked to"""
	if not can_place_item(item, grid_pos):
		return false

	var placed = item.placed_at(
		grid_pos, item.facing() if facing < 0 else facing)
	_add_item(placed)
	item_placed.emit(placed, grid_pos)

	return true

func mark_square(item_shape: Array, grid_pos: Vector2i, allowed: bool) -> void:
	"""Mark where something of this shape would land, and whether it can.

	The one place that draws the mark. Whether the square is allowed is the
	caller's question to answer, because an item asks whether a container has
	made a square usable and a container asks whether a square is free.

	A square it cannot go in is marked red rather than left blank. Blank says
	only that nothing is happening, and the player is left guessing whether the
	game saw the pointer at all; red says the game saw it and the answer is no.
	Off the board there is nothing to answer about, so nothing is drawn.
	"""
	if not hover_preview or not is_instance_valid(hover_preview):
		_create_hover_preview()

	if not _on_the_board(grid_pos):
		hover_preview.visible = false
		return

	# A shape reaches here as Vector2i from the server and as pairs from a
	# caller that writes one out. Settle that once, here, so everything below
	# is working with squares.
	var squares := ItemPlaceholder.squares_in(item_shape)
	hover_preview.visible = true
	hover_preview.position = grid_to_pixel(grid_pos)
	hover_preview.size = _shape_extent(squares)

	# The mark is asked for on every frame of a drag, and the answer is the
	# same on nearly all of them. Drawing it throws away one Panel per square
	# and builds another, sixty times a second, for a picture that has not
	# changed. The patches move with the mark, so only its shape and its
	# colour are worth watching.
	if squares == _marked_squares and allowed == _marked_allowed:
		return
	_marked_squares = squares.duplicate()
	_marked_allowed = allowed
	_draw_mark(squares, allowed)


func _on_the_board(grid_pos: Vector2i) -> bool:
	"""Whether this square is one of the grid's own"""
	return grid_pos.x >= 0 and grid_pos.y >= 0 \
		and grid_pos.x < grid_width and grid_pos.y < grid_height


func _shape_extent(item_shape: Array[Vector2i]) -> Vector2:
	"""How far a shape reaches from the square it starts on.

	The visual's own measure, so the mark is always exactly the size of the
	thing it marks rather than the same formula written out twice.
	"""
	return ItemVisual.extent_of(item_shape, cell_size, cell_spacing)


func _draw_mark(squares: Array[Vector2i], allowed: bool) -> void:
	"""One patch per square the shape covers.

	An L covers three squares out of the four its corners reach, and a mark
	drawn as one rectangle claims the fourth as well -- which is the square the
	player is trying to work out whether they can use.

	Takes squares rather than a shape: this once took pairs only, and every
	mark drawn for a real item -- whose shape is Vector2i -- came out with no
	patches in it at all, which is a highlight the player never saw.
	"""
	# Taken off the screen now rather than at the end of the frame. queue_free()
	# on its own leaves the patches standing for one more draw, at their old
	# offsets inside a mark that has already moved and resized -- which is a
	# ghost of the old shape, and it shows on exactly the frame a turn happens.
	for old in hover_preview.get_children():
		hover_preview.remove_child(old)
		old.queue_free()


	var style := StyleBoxFlat.new()
	style.bg_color = MARK_ALLOWED_FILL if allowed else MARK_REFUSED_FILL
	style.border_color = MARK_ALLOWED_EDGE if allowed else MARK_REFUSED_EDGE
	style.set_border_width_all(2)
	style.set_corner_radius_all(3)

	for square in squares:
		var patch := Panel.new()
		patch.mouse_filter = Control.MOUSE_FILTER_IGNORE
		patch.position = Vector2(
			square.x * (cell_size + cell_spacing),
			square.y * (cell_size + cell_spacing)
		)
		patch.size = Vector2(cell_size, cell_size)
		patch.add_theme_stylebox_override("panel", style)
		hover_preview.add_child(patch)


func show_hover_preview_for_shop(item_data: APITypes.Item, grid_pos: Vector2i):
	"""Show hover preview for a shop item being dragged"""
	mark_square(item_data.turned_shape(), grid_pos, can_place_item(item_data, grid_pos))

func hide_hover_preview():
	"""Hide the hover preview"""
	if hover_preview and is_instance_valid(hover_preview):
		hover_preview.visible = false

func _remove_item(item_visual: Control):
	"""Remove an item from the grid"""
	var grid_pos = item_visual.get_meta("grid_pos")
	var item_data = item_visual.get_meta("item_data")

	# Clear from grid
	for offset in item_data.turned_shape():
		var cell_x = grid_pos.x + offset[0]
		var cell_y = grid_pos.y + offset[1]
		if cell_x >= 0 and cell_y >= 0 and cell_x < grid_width and cell_y < grid_height:
			item_grid[cell_y][cell_x] = null

	items.erase(item_visual)
	item_visual.queue_free()
	item_removed.emit(item_data, grid_pos)

func _process(_delta):
	"""Carry whatever is in hand to wherever the pointer has got to"""
	carry_to(get_global_mouse_position())


func carry_to(pointer: Vector2) -> void:
	"""Move what is being dragged to this pointer, and mark where it would land.

	Takes the pointer rather than reading it, so a whole drag can be played
	out by a test -- press, carry, carry, drop -- and what is on screen at each
	step can be asked about.

	This is the only thing that moves a dragged item's artwork, and while it
	read the mouse itself no test could drive it. That is how the mark came to
	be drawn a spear's length from the spear and stay that way: every test
	could see where the mark went, and none could see where the item went.
	"""
	var local: Vector2 = get_global_transform().affine_inverse() * pointer

	if dragging_container:
		var visual = dragging_container.visual
		visual.position = local + drag_offset
		for rider in container_riders:
			rider.follow(visual.position)
		update_container_preview(pointer)
		return

	if dragging_object:
		dragging_object.position = local + drag_offset
		if not hover_preview or not is_instance_valid(hover_preview):
			return
		update_drag_preview(pointer)


func update_container_preview(pointer: Vector2) -> void:
	"""Mark where a held container would stand, for a pointer at this place"""
	if not dragging_container:
		return
	var container := dragging_container.container
	var grid_pos := square_held_over(pointer, grab_cell)
	mark_square(container.turned_shape(), grid_pos, can_place_container(container, grid_pos))


func update_drag_preview(pointer: Vector2) -> void:
	"""Mark where the held item would land, for a pointer at this place.

	Takes the pointer rather than reading it, so what it decides can be asked
	about without a mouse.
	"""
	if not dragging_object or not hover_preview or not is_instance_valid(hover_preview):
		return

	var item_data = dragging_object.get_meta("item_data")

	# Held over the grid it would move to, so that grid shows where it would
	# land. Ours would be marking a square of its own, which is not where the
	# item is going.
	if _pointer_is_over_grid_zone(pointer):
		hide_hover_preview()
		grid_zone.show_hover_preview_for_shop(item_data, _grid_zone_square(pointer))
		return
	if grid_zone:
		grid_zone.hide_hover_preview()

	var grid_pos := square_held_over(pointer, grab_cell)
	mark_square(item_data.turned_shape(), grid_pos, _can_place_item(item_data, grid_pos))

func clear_all():
	"""Clear all items and containers"""
	# Nothing survives a clear, including whatever was in the middle of being
	# dragged. Left behind, the reference outlives the node it points at, and
	# the next mouse-up asks a freed item where it landed. The board is redrawn
	# under the player's hand more often than it looks: a move the server
	# refuses, a container that displaces something, and the merge that plays
	# as the shop opens.
	dragging_object = null
	dragging_container = null

	# Remove all item visuals
	for item_visual in items:
		item_visual.queue_free()
	items.clear()

	# Remove all container visuals
	for placed in containers:
		placed.visual.queue_free()
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
		"inventory_grid": [],
		"server_containers": []
	}

	# Save items - convert to dictionaries for persistence
	for item_visual in items:
		var item_data = item_visual.get_meta("item_data")
		var grid_pos = item_visual.get_meta("grid_pos")

		# Items go back to the server as plain data. An item knows where it
		# sits, so nothing overrides its position here any more: two answers to
		# where an item is meant one of them was wrong wherever it was read.
		state.inventory_grid.append(item_data.to_dict())

	for placed in containers:
		state.server_containers.append(placed.container.to_dict())

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
		load_inventory_state(
			APITypes.InventoryState.new(get_inventory_state()))
