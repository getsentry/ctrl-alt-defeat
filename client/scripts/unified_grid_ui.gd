extends Control

const APITypes = preload("res://scripts/api_types.gd")
const ItemVisual = preload("res://scripts/item_visual.gd")
const InventoryGrid = preload("res://scripts/inventory_grid.gd")
const Presentation = preload("res://scripts/presentation.gd")
const PriceTag = preload("res://scripts/price_tag.gd")

# Game state is pulled from GameStateManager - no local copies

# Grid settings
const ROOM_WIDTH = 9   # Fixed grid width
const ROOM_HEIGHT = 7  # Fixed grid height
const CELL_SIZE = 45  # Default cell size, actual size calculated from container
const CELL_SPACING = 1

# Storage settings
#
# Twenty-four squares either way, but eight by three fills the shelf painted
# inside the chest, where twelve by two left it a band across the middle with
# empty chest above and below.
const STORAGE_WIDTH = 8
const STORAGE_HEIGHT = 3
const STORAGE_PADDING = 4
## The shelf inside the chest, measured from the corner of the chest's panel.
## The rest of the panel is the frame drawn around it and the word STORAGE
## across the bottom, and squares drawn there sit on the picture.
const STORAGE_SHELF := Rect2(39, 31, 320, 130)

# Runtime calculated cell size
var actual_cell_size: float = CELL_SIZE
var actual_cell_spacing: float = CELL_SPACING

# Signal handlers for InventoryGrid
func _on_item_placed(item_data, grid_pos: Vector2i):
	"""Called when an item is placed in the inventory grid"""
	# Save the inventory state
	_save_current_state()


func _on_item_removed(item_data, grid_pos: Vector2i):
	"""Called when an item is removed from the inventory grid"""
	# Save the inventory state
	_save_current_state()


func _on_item_sold(item_data: APITypes.PlacedItem):
	"""Called when an item is dropped on the sell chest"""
	# The grid has already taken the item off, so put it back if the server
	# refuses the sale. Otherwise the player loses the item and gets nothing.
	var response = await BattleServerAPI.sell_item(item_data.id)
	if response == null:
		print("Sell refused by the server, putting the item back")
		inventory_grid._add_item(item_data)
		_save_current_state()
		return

	GameStateManager.gold = response.gold
	_update_stats()
	_save_current_state()
	print("Sold %s for %d gold" % [item_data.name, response.gold_gained])

func _on_drag_started(item_data: APITypes.PlacedItem):
	"""Name the price while the item is in hand, as the shop does.

	The chest only offers to buy while there is something to sell it. Standing
	there asking the whole time reads as an instruction rather than an offer,
	and there is nothing the player can do about it until they pick something
	up.
	"""
	var prompt: Label = sell_chest.get_node("Prompt")
	prompt.text = "Drop here to sell for %d" % item_data.sell_value
	prompt.visible = true
	sell_chest.modulate = Color(1.15, 1.15, 1.15)


func _on_drag_ended():
	var prompt: Label = sell_chest.get_node("Prompt")
	prompt.text = "Drop here to sell"
	prompt.visible = false
	sell_chest.modulate = Color.WHITE


func _on_item_stored(item_data: APITypes.PlacedItem):
	"""Called when an item is dropped on the chest"""
	# The grid has already taken the item off, so put it back if the server
	# refuses. Otherwise the item is gone from the grid and not in the chest.
	var response = await BattleServerAPI.move_item(item_data.id, "storage")
	if response == null:
		print("The server refused to store it, putting the item back")
		inventory_grid._add_item(item_data)
		_save_current_state()
		return

	_on_inventory_returned(response)
	_save_current_state()
	print("Put %s in the chest" % item_data.name)


func put_on_grid(item: APITypes.Item, grid_pos: Vector2i) -> bool:
	"""Move an item out of the chest onto a square of the grid."""
	if not inventory_grid.can_place_item(item, grid_pos):
		return false

	var response = await BattleServerAPI.move_item(
		item.id, [grid_pos.x, grid_pos.y], item.facing())
	if response == null:
		print("The server refused to put %s at %s" % [item.name, grid_pos])
		return false

	inventory_grid.place_shop_item(item, grid_pos, item.facing())
	_on_inventory_returned(response)
	_save_current_state()
	return true


func _on_item_unstored(item_data: APITypes.Item, global_pos: Vector2):
	"""Called when an item is dragged out of the chest onto the grid"""
	# The chest has already let go of it on screen, so a move that does not
	# happen has to draw the chest again with the item still in it.
	if await put_on_grid(item_data, _global_to_grid(global_pos)):
		print("Took %s out of the chest" % item_data.name)
	else:
		load_storage()


func _on_chest_item_sold(item_data: APITypes.Item):
	"""Called when an item is dragged from the chest onto the sell chest"""
	var response = await BattleServerAPI.sell_item(item_data.id)
	if response == null:
		print("Sell refused by the server, so it stays in the chest")
		load_storage()
		return

	GameStateManager.gold = response.gold
	GameStateManager.inventory_storage = GameStateManager.inventory_storage.filter(
		func(held): return held.id != item_data.id)
	load_storage()
	_update_stats()
	print("Sold %s out of the chest for %d gold" % [item_data.name, response.gold_gained])


func _on_container_dropped(
	container_data: APITypes.PlacedItem,
	grid_pos: Vector2i,
	rider_ids: Array[String],
):
	"""Called when a container is dropped somewhere it can stand"""
	var response = await BattleServerAPI.move_item(
		container_data.id, [grid_pos.x, grid_pos.y])
	if response == null:
		print("The server refused to move the container")
		_reload_board()
		return

	# The whole board comes back, and it has to: the container carries its
	# items, and any it could not carry have been set down in the chest.
	GameStateManager.inventory_storage = response.inventory_storage
	inventory_grid.load_inventory_state(response.as_inventory_state())
	load_storage()
	_save_current_state()
	print("Moved %s to %s" % [container_data.name, grid_pos])

	take_displaced(rider_ids, response.inventory_grid)


func take_displaced(
	rider_ids: Array[String], grid_now: Array[APITypes.PlacedItem]
) -> void:
	"""Take into the hand whatever the container could not carry.

	The items that travelled with a container are known: the grid picked them
	up with it. One that is not on the grid afterwards had nowhere to stand,
	and is in the chest now. Asking it this way needs nothing of the chest, so
	whatever else is in there cannot be mistaken for a displaced item.

	Only the first comes into the hand. The rest stay in the chest, which is
	where they are anyway.
	"""
	var landed: Dictionary[String, bool] = {}
	for item in grid_now:
		landed[item.id] = true

	for rider_id in rider_ids:
		if not landed.has(rider_id):
			var displaced = _in_chest(rider_id)
			if displaced:
				hold(displaced)
			return


func _in_chest(item_id: String) -> APITypes.Item:
	"""The item with this id, if the chest holds it"""
	for item in GameStateManager.inventory_storage:
		if item.id == item_id:
			return item
	return null


func hold(item: APITypes.Item) -> void:
	"""Take an item into the hand, to be put down with a click.

	It is in the chest already, so this is a shortcut and not a place of its
	own: whatever happens next, the item has somewhere safe to be.
	"""
	if is_instance_valid(held_visual):
		held_visual.queue_free()

	held_item = item
	held_visual = ItemVisual.new()
	held_visual.mouse_filter = Control.MOUSE_FILTER_IGNORE
	held_visual.setup(item, inventory_grid.cell_size, inventory_grid.cell_spacing)
	add_child(held_visual)

	# Put where the pointer already is. Waiting for the pointer to move would
	# leave it sitting in the corner of the screen until the player twitched.
	follow_pointer(get_global_mouse_position())

	# Drawn last, so the chest knows what is in hand and leaves its square empty.
	load_storage()
	print("Holding %s. Click to put it down, or click the chest to leave it there."
		% item.name)


func follow_pointer(pointer: Vector2) -> void:
	"""Put the held item under the pointer, and mark where it would land.

	A held item is not being dragged, so the grid is not marking anything of
	its own accord. It still has to show where a click would put the item, the
	same as a drag does.
	"""
	if not held_item:
		return
	if is_instance_valid(held_visual):
		held_visual.global_position = pointer - held_visual.size / 2

	var grid_pos := _global_to_grid(pointer)
	inventory_grid.mark_square(
		held_item.turned_shape(), grid_pos,
		inventory_grid.can_place_item(held_item, grid_pos))


func turn(quarters: int) -> bool:
	"""Turn whatever is held, however it came to be held.

	An item is held for four different reasons -- dragged off the grid, taken
	out of the chest, carried off the shop shelf, or picked up after a
	container move set it down -- and all four are holding it. Says whether
	anything was, so the caller knows whether the input was used, and there is
	only one list of what counts as holding something.
	"""
	if held_item:
		held_item = held_item.turned(quarters)
		if is_instance_valid(held_visual):
			held_visual.redraw_as(held_item)
		follow_pointer(get_global_mouse_position())
		return true

	if dragging_shop_data:
		dragging_shop_data = dragging_shop_data.turned(quarters)
		if is_instance_valid(drag_preview):
			drag_preview.redraw_as(dragging_shop_data)
		return true

	return inventory_grid.turn_dragged(quarters) \
		or storage_grid.turn_dragged(quarters)


func release_hand() -> void:
	"""Let go of whatever is in the hand, leaving it in the chest"""
	held_item = null
	inventory_grid.hide_hover_preview()
	if is_instance_valid(held_visual):
		held_visual.queue_free()
	held_visual = null
	load_storage()


func place_held_at(pointer: Vector2) -> void:
	"""Put the held item down at this place.

	Takes the pointer rather than reading it, so where a held item lands can be
	asked about without a mouse.
	"""
	if not held_item:
		return

	# The chest is where it already is, so this is simply letting go.
	if storage_grid and storage_grid.get_parent().get_global_rect().has_point(pointer):
		print("Left %s in the chest" % held_item.name)
		release_hand()
		return

	# It stays in hand unless it lands, so a misclick cannot put it somewhere
	# the player did not choose.
	var item = held_item
	if await put_on_grid(item, _global_to_grid(pointer)):
		release_hand()
		print("Put %s down" % item.name)


func _reload_board():
	"""Draw the grid again from what is held, after something came to nothing"""
	inventory_grid.load_inventory_state(
		APITypes.InventoryState.new(GameStateManager.get_inventory_state()))
	load_storage()


func _on_inventory_returned(response: APITypes.MoveItemResponse):
	"""The server has answered a move with the whole inventory.

	The chest is the part the grid cannot draw, and a move can put something in
	it without the player asking: moving a container sets down any item left
	with nowhere to stand.
	"""
	GameStateManager.inventory_storage = response.inventory_storage
	load_storage()


func _on_item_moved(item_id: String, from_pos: Vector2i, to_pos: Vector2i):
	"""Called after an item has been successfully moved within the inventory"""
	print("Item %s successfully moved from %s to %s" % [item_id, from_pos, to_pos])
	# Save the current state to GameStateManager
	_save_current_state()


func _save_current_state():
	"""Save the current inventory state to GameStateManager"""
	var state = inventory_grid.get_inventory_state()
	GameStateManager.save_inventory_state(state.items, state.servers)

func _input(event):
	# Turning works on anything held, dragged or in hand. R and the wheel
	# forward go clockwise, E and the wheel back the other way. The input is
	# only swallowed if something actually turned, so the wheel still scrolls
	# when the player is holding nothing.
	var quarters := _turn_asked_for(event)
	if quarters != 0 and turn(quarters):
		get_viewport().set_input_as_handled()
		return

	# An item in hand follows the pointer and is put down with a press, which
	# is the other way round from a drag. The press is marked handled so that
	# the click which puts the item down cannot also pick something else up.
	if held_item:
		if event is InputEventMouseMotion:
			follow_pointer(event.global_position)
		elif event is InputEventMouseButton and event.pressed \
				and event.button_index == MOUSE_BUTTON_LEFT:
			get_viewport().set_input_as_handled()
			place_held_at(event.global_position)
		return

	# Handle shop item dragging
	if dragging_shop_item:
		if event is InputEventMouseButton:
			if event.button_index == MOUSE_BUTTON_LEFT and not event.pressed:
				_end_shop_drag(event.global_position)
		elif event is InputEventMouseMotion:
			# Update drag preview position
			if drag_preview:
				drag_preview.global_position = event.global_position - drag_preview.size / 2

			var grid_pos = _global_to_grid(event.global_position)

			# Show container preview if dragging a container
			if dragging_shop_data.is_container:
				_show_container_preview(dragging_shop_data, grid_pos)
			else:
				# For normal items, use the inventory grid's hover preview
				inventory_grid.show_hover_preview_for_shop(dragging_shop_data, grid_pos)


func _turn_asked_for(event: InputEvent) -> int:
	"""How many quarter turns this input asks for, clockwise, or none"""
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_R:
			return 1
		if event.keycode == KEY_E:
			return -1
	if event is InputEventMouseButton and event.pressed:
		if event.button_index == MOUSE_BUTTON_WHEEL_UP:
			return 1
		if event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			return -1
	return 0


func _global_to_grid(global_pos: Vector2) -> Vector2i:
	"""Convert a global screen position to an inventory grid cell.

	Takes the position from the InputEvent rather than the cursor, so drag and
	drop works headless as well as on screen. Control has no to_local(), so the
	conversion goes through the global transform.
	"""
	if not inventory_grid or not inventory_grid.is_inside_tree():
		return Vector2i(-1, -1)
	var local_pos = inventory_grid.get_global_transform().affine_inverse() * global_pos
	return inventory_grid.pixel_to_grid(local_pos)

# Grid managers
var inventory_grid: InventoryGrid  # Main inventory grid
var storage_grid: InventoryGrid    # Storage grid

# Game state tracking

var server_room_container: Node  # Points to inventory_grid

# Shop
var shop_items: Array[Panel] = []

# Mode settings
var read_only_mode: bool = false
var hide_shop: bool = false
var hide_storage: bool = false

# An item in hand: picked up without a button being held, and put down with a
# click. It is in the chest the whole time, so the hand is a shortcut rather
# than a place of its own.
var held_item: APITypes.Item = null
var held_visual: ItemVisual = null

# UI References
var shop_container: Control
var sell_chest: Control
## The box the five numbers are written in, one row each.
var stats_panel: Control
## The value label of each row, by the caption beside it.
var stat_values: Dictionary[String, Label] = {}
## What the last change to the gold was, shown beside it and then faded out.
var gold_delta_label: Label = null
## How hard the build leans on its stamina. Waiting on a server that says.
var stamina_use_label: Label = null
## Where the player stands against everyone else. Waiting on a ranking.
var rank_label: Label = null
## The gold the panel last showed, so a change can be named. Below zero until
## the panel has shown anything at all.
var _gold_shown: int = -1

func _ready():
	print("UnifiedGridUI starting...")

	# Set window size for consistency (scaling to 1680x1050)
	if not OS.has_feature("headless"):
		DisplayServer.window_set_size(Vector2i(1680, 1050))
		get_window().min_size = Vector2i(1680, 1050)
		get_window().max_size = Vector2i(1680, 1050)

	# Connect to API signals for typed responses
	BattleServerAPI.purchase_completed.connect(_on_purchase_completed)

	# State is read directly from GameStateManager, no local copies

	# Initialize UI first
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
	for item in saved_inventory["items"]:
		print("    Item: %s at %s" % [item["name"], item["position"]])
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
	# The chest is not part of an InventoryState, but whatever changed the grid
	# may well have put something in it.
	load_storage()

func get_inventory_state() -> Dictionary:
	# Delegate to InventoryGrid
	if inventory_grid:
		return inventory_grid.get_inventory_state()
	return {"servers": [], "items": []}

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

	_dress_buttons()

	print("UI setup complete")

func _create_header():
	if read_only_mode:
		return
	stats_panel = $CharacterStats
	_build_stat_rows()
	_update_stats()


# ============ Character stats ============
#
# Five numbers the player checks between every purchase. They are read far more
# often than they are read *about*, so each gets a line of its own with the
# caption on the left and the number on the right: the eye goes down the right
# hand column and finds gold without reading a word.

## Who the player is, and then how the run is going. Two groups, because they
## are asked about at different moments: the first before a purchase, the
## second between rounds.
const WHO_YOU_ARE := ["Name", "Class", "Gold", "Health", "Stamina"]
const HOW_THE_RUN_GOES := ["Round", "Wins", "Tries"]
const STAT_FONT_SIZE := 21
const STAT_CAPTION_COLOR := Color(0.62, 0.66, 0.82)
const STAT_VALUE_COLOR := Color(0.95, 0.96, 1.0)
const GOLD_COLOR := Color(1.0, 0.85, 0.3)
const HEALTH_COLOR := Color(1.0, 0.5, 0.55)
const SPENT_COLOR := Color(1.0, 0.45, 0.45)
const EARNED_COLOR := Color(0.45, 1.0, 0.55)

## What a row shows when the game does not yet know the number. A dash rather
## than a plausible figure: a made-up stat is worse than a missing one, because
## the player cannot tell it is made up and plays against it.
const NOT_KNOWN_YET := "—"
const NOT_KNOWN_COLOR := Color(0.45, 0.48, 0.6)
## The column kept clear to the right of every value.
const STAT_ASIDE_WIDTH := 58.0
## What the player is. There is one kind, so it is written here rather than
## carried on a session that has nothing to choose between.
const PLAYER_CLASS := "Sentaur"


func _build_stat_rows() -> void:
	"""One row per number, built once and written to from then on"""
	for old in stats_panel.get_children():
		old.queue_free()
	stat_values.clear()

	for caption in WHO_YOU_ARE:
		stats_panel.add_child(_stat_row(caption))

	# A gap, so the two groups read as two groups.
	var gap := Control.new()
	gap.custom_minimum_size = Vector2(0, 10)
	stats_panel.add_child(gap)

	for caption in HOW_THE_RUN_GOES:
		stats_panel.add_child(_stat_row(caption))

	stats_panel.add_child(_rank_plate())


func _stat_row(caption: String) -> HBoxContainer:
	"""One line of the panel: what it is, what it reads, and room beside it.

	The room on the right is for whatever only one row has to say -- what the
	gold just did, how hard the build leans on its stamina -- and it is kept on
	every row, so that the values stay in one column down the page.
	"""
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	# The rows share out the pane between them, so the block is as tall as the
	# frame painted around it rather than a huddle at the top of it.
	row.size_flags_vertical = Control.SIZE_EXPAND_FILL

	var name_label := Label.new()
	name_label.text = caption
	name_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	name_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	name_label.add_theme_font_size_override("font_size", STAT_FONT_SIZE)
	name_label.add_theme_color_override("font_color", STAT_CAPTION_COLOR)
	row.add_child(name_label)

	var value := Label.new()
	value.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	value.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	value.add_theme_font_size_override("font_size", STAT_FONT_SIZE)
	value.add_theme_color_override("font_color", _stat_colour(caption))
	row.add_child(value)
	stat_values[caption] = value

	row.add_child(_beside(caption))
	return row


func _stat_colour(caption: String) -> Color:
	match caption:
		"Gold":
			return GOLD_COLOR
		"Health":
			return HEALTH_COLOR
		_:
			return STAT_VALUE_COLOR


func _beside(caption: String) -> Control:
	"""The narrow column to the right of the values.

	Gold uses it to say what the last purchase cost -- it is the only number
	here that moves for a reason the player chose, and the reason is worth
	confirming. Stamina keeps it for how hard the build leans on it. The rest
	hold the column open so nothing below shifts sideways.
	"""
	if caption == "Gold":
		gold_delta_label = Label.new()
		gold_delta_label.custom_minimum_size = Vector2(STAT_ASIDE_WIDTH, 0)
		gold_delta_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		gold_delta_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		gold_delta_label.add_theme_font_size_override("font_size", STAT_FONT_SIZE - 3)
		gold_delta_label.modulate = Color(1, 1, 1, 0)
		return gold_delta_label

	if caption == "Stamina":
		stamina_use_label = Label.new()
		stamina_use_label.custom_minimum_size = Vector2(STAT_ASIDE_WIDTH, 0)
		stamina_use_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		stamina_use_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		stamina_use_label.add_theme_font_size_override("font_size", STAT_FONT_SIZE - 4)
		stamina_use_label.add_theme_color_override("font_color", NOT_KNOWN_COLOR)
		# Held open and silent. A caption with no reading under it is worse
		# than a gap: it asks the player to look for something that is not
		# there. The room is what is being kept, not the words.
		stamina_use_label.text = ""
		return stamina_use_label

	var spacer := Control.new()
	spacer.custom_minimum_size = Vector2(STAT_ASIDE_WIDTH, 0)
	return spacer


func _rank_plate() -> Label:
	"""Where the player stands against everyone else.

	There is no ranking yet, so every player is unranked, and the plate says
	so rather than standing empty: the word is the whole of the news.
	"""
	rank_label = Label.new()
	rank_label.text = "Unranked"
	rank_label.custom_minimum_size = Vector2(0, 32)
	rank_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	rank_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	rank_label.add_theme_font_size_override("font_size", STAT_FONT_SIZE - 2)
	rank_label.add_theme_color_override("font_color", Color(0.72, 0.78, 0.95))

	var plate := StyleBoxFlat.new()
	plate.bg_color = Color(0.16, 0.2, 0.42, 0.75)
	plate.border_color = Color(0.4, 0.5, 0.85, 0.7)
	plate.set_border_width_all(2)
	plate.set_corner_radius_all(6)
	rank_label.add_theme_stylebox_override("normal", plate)
	return rank_label


func _create_shop_panel():
	if hide_shop:
		return
	shop_container = $ShopContainer
	sell_chest = $SellChest
	# The chest is a picture, not a box. A panel behind it is a black rectangle
	# cut out of the wall.
	sell_chest.add_theme_stylebox_override("panel", StyleBoxEmpty.new())
	# Nothing is in hand yet, so there is nothing to sell.
	sell_chest.get_node("Prompt").visible = false

func _create_server_room():
	# The background already draws a frame around the inventory, so the panel
	# adds only a second one a few pixels inside the first.
	var room_bg = $InventoryPanel
	room_bg.add_theme_stylebox_override("panel", StyleBoxEmpty.new())

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
	inventory_grid.inventory_returned.connect(_on_inventory_returned)
	inventory_grid.item_stored.connect(_on_item_stored)
	inventory_grid.container_dropped.connect(_on_container_dropped)
	inventory_grid.item_moved.connect(_on_item_moved)
	inventory_grid.drag_started.connect(_on_drag_started)
	inventory_grid.drag_ended.connect(_on_drag_ended)
	inventory_grid.sell_zone = sell_chest

	# Set legacy references for compatibility
	server_room_container = inventory_grid

func _create_storage_area():
	if hide_storage:
		return

	# Use existing nodes from scene if available
	if has_node("StoragePanel"):
		# The chest is painted into the background, frame and all.
		var storage_bg = $StoragePanel
		storage_bg.add_theme_stylebox_override("panel", StyleBoxEmpty.new())

		# The panel is faded in the scene, and modulate multiplies down into
		# children, so everything in the chest was drawn at a fifth opacity.
		# self_modulate fades the panel alone, and the style above is already
		# see-through, so the chest keeps its look and its contents are solid.
		storage_bg.modulate = Color.WHITE

		# Create storage grid
		storage_grid = InventoryGrid.new()
		# The chest is drawn in the scene, so the squares are sized to the
		# shelf inside it rather than to the grid's own cell size. At 45 they
		# are wider than the chest and most of it is drawn off the edge.
		storage_grid.configure(
			STORAGE_WIDTH, STORAGE_HEIGHT,
			_storage_cell_size(STORAGE_SHELF.size), CELL_SPACING
		)
		# The background already paints STORAGE across the front of the chest,
		# so a title here is the word twice.
		storage_grid.title = ""
		storage_grid.read_only = read_only_mode
		storage_bg.add_child(storage_grid)

		# Sit it in the middle of the shelf rather than of the whole panel, so
		# it fills the chest and not the frame drawn around it.
		storage_grid.position = (STORAGE_SHELF.position
			+ (STORAGE_SHELF.size - storage_grid.size) / 2).floor()

		# The whole panel takes a drop, not only the squares, so a drop that
		# lands on the frame still goes in the chest.
		if inventory_grid:
			inventory_grid.storage_zone = storage_bg

		# The chest lays itself out, so its squares are not places the server
		# knows about and a move inside it is never sent.
		storage_grid.saves_positions = false
		storage_grid.sell_zone = sell_chest
		storage_grid.grid_zone = inventory_grid
		storage_grid.item_sold.connect(_on_chest_item_sold)
		storage_grid.item_unstored.connect(_on_item_unstored)
		# An item out of the chest can be sold just as one off the grid can, so
		# the sell chest names its price while it is in hand either way.
		storage_grid.drag_started.connect(_on_drag_started)
		storage_grid.drag_ended.connect(_on_drag_ended)

		# Set legacy reference

		# Storage is always active (no servers needed)
		for y in range(STORAGE_HEIGHT):
			for x in range(STORAGE_WIDTH):
				storage_grid.active_grid[y][x] = true

		load_storage()


static func _storage_cell_size(shelf: Vector2) -> float:
	"""How big a chest square can be and still fit on the chest's shelf.

	Eight across and three down, with a gap between each pair and a little
	padding all round. Whichever way runs out first decides, so the squares
	stay square. Never larger than a grid square, so the chest cannot end up
	drawing items bigger than the inventory does.
	"""
	var across = shelf.x - 2 * STORAGE_PADDING - (STORAGE_WIDTH - 1) * CELL_SPACING
	var down = shelf.y - 2 * STORAGE_PADDING - (STORAGE_HEIGHT - 1) * CELL_SPACING
	return min(CELL_SIZE, floor(across / STORAGE_WIDTH), floor(down / STORAGE_HEIGHT))


func load_storage():
	"""Lay the chest out from what the server says is in it.

	An item in the chest is off the grid, so it has no position of its own and
	the chest decides where to draw it: the first square it fits in, reading
	left to right and then down. Nothing is remembered between calls, so the
	same contents always draw the same way.
	"""
	if hide_storage or not storage_grid:
		return

	storage_grid.clear_all()
	for y in range(STORAGE_HEIGHT):
		for x in range(STORAGE_WIDTH):
			storage_grid.active_grid[y][x] = true

	for item in GameStateManager.inventory_storage:
		# What is in hand is in the chest as well, because the hand is a
		# shortcut and not a place. Drawing it in both would look like two of
		# it, so the chest leaves its square empty until it is let go of.
		if held_item and item.id == held_item.id:
			continue
		if not _put_in_chest(item):
			# The chest holds 24 squares and the server holds no such limit, so
			# a full chest is a thing the player has to be able to see happen.
			push_warning("No room in the chest to draw %s" % item.name)


func _put_in_chest(item: APITypes.Item) -> bool:
	"""Put an item in the first square of the chest it fits in"""
	for y in range(STORAGE_HEIGHT):
		for x in range(STORAGE_WIDTH):
			if storage_grid.place_shop_item(item, Vector2i(x, y)):
				return true
	return false

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


func _load_shop_from_state():
	# Load shop from GameStateManager
	print("Loading shop from state, current_shop size: %d" % GameStateManager.current_shop.size())
	print("Displaying %d shop items from server" % GameStateManager.current_shop.size())
	_display_shop_items(GameStateManager.current_shop)


const SALE_COLOR := Color(0.35, 0.9, 0.4)
const FULL_PRICE_COLOR := Color(1.0, 1.0, 0.0)
const STRUCK_PRICE_COLOR := Color(0.78, 0.78, 0.84)
const PRICE_TAG_COLOR := Color(1, 0.85, 0.3)
## What a price reads as when there is not enough gold for it. The item is
## still on the shelf and still worth reading about; it just cannot be bought.
const UNAFFORDABLE_COLOR := Color(1.0, 0.42, 0.45)
## How dim a shelf goes when its price is out of reach.
const OUT_OF_REACH := Color(0.5, 0.5, 0.58, 1.0)

## The room one shelf slot has, and how the item sits in it: the artwork above,
## the price tag on the front of the shelf below it. The item is not named
## here -- the card the shelf puts out under the pointer names it, and a
## caption on every slot is five names to read past to find one item.
const SLOT_SIZE := Vector2(200, 150)
const SHELF_CELL := 45.0
## The line every item stands on, whatever its height.
const ART_FLOOR := 112.0
const TAG_TOP := 118.0
const TAG_SIZE := Vector2(88, 34)
## A sale plate carries a word as well as a number, so it is the wider of the
## two. Both stay centred on the same point, so the shelf still reads as a row.
const SALE_TAG_SIZE := Vector2(118, 34)
## How far a shelf lifts under the pointer.
const SHELF_LIFT := 6.0


func _dress_buttons() -> void:
	"""Let the painted signs show through the buttons standing on them.

	Both buttons sit on artwork that already draws the sign -- the neon slab
	for the battle, the reroll plate for the shop -- and a default button
	covers it with a grey slab of its own.
	"""
	var ready_button := get_node_or_null("ReadyButton")
	if ready_button:
		_make_button_transparent(ready_button, Color(1.0, 0.85, 0.45), 30)

	var refresh_button := get_node_or_null("RefreshButton")
	if refresh_button:
		# REROLL and its price are painted into the background, so the button
		# is the plate itself and says nothing of its own.
		_make_button_transparent(refresh_button, PRICE_TAG_COLOR, 17)


func _make_button_transparent(
	button: Button, ink: Color, font_size: int, text_top: int = 0
) -> void:
	for state in ["normal", "hover", "pressed", "focus", "disabled"]:
		var style := StyleBoxFlat.new()
		style.bg_color = Color(1, 1, 1, 0.07) if state == "hover" else Color.TRANSPARENT
		style.set_corner_radius_all(10)
		style.content_margin_top = text_top
		button.add_theme_stylebox_override(state, style)

	button.add_theme_font_size_override("font_size", font_size)
	button.add_theme_color_override("font_color", ink)
	button.add_theme_color_override("font_hover_color", Color(1, 1, 1))
	button.add_theme_color_override("font_pressed_color", Color(1, 1, 1))
	button.add_theme_color_override("font_disabled_color", Color(ink, 0.35))
	button.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.8))
	button.add_theme_constant_override("shadow_offset_x", 2)
	button.add_theme_constant_override("shadow_offset_y", 2)
	button.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND


func _display_shop_items(shop_data: Array[APITypes.Item]):
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
		print("  Slot %d: %s (%dg%s)" % [
			i, item_data.name, item_data.price, " on sale" if item_data.on_sale else ""
		])

		# Create shop item and add to the specific position container
		var shop_item = _create_shop_item_from_data(item_data)
		shop_item.position = Vector2.ZERO  # Position relative to container
		shop_positions[i].item.add_child(shop_item)
		shop_items.append(shop_item)

		# The price belongs to the item, so it hangs off the front of the shelf
		# the item stands on rather than wherever the scene happened to put it.
		var tag: Label = shop_positions[i].price
		tag.text = str(item_data.price) + "g"
		_hang_price_tag(tag, shop_positions[i].item, item_data)
		_dress_price_tag(tag, item_data)
		tag.visible = true
		shop_item.set_meta("price_tag", tag)

	print("Added %d shop items to container" % shop_items.size())

func _create_shop_item_from_data(data: APITypes.Item) -> Control:
	"""One slot of the shelf: what the item is, what it looks like, what it costs.

	The whole slot answers the pointer, not just the few squares the artwork
	covers. A player reaching for an item aims at the item, and a picture 45
	pixels across is a small thing to have to hit before the shop will say
	anything about what is on it.
	"""
	var slot = Panel.new()
	slot.custom_minimum_size = SLOT_SIZE
	slot.size = SLOT_SIZE
	slot.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	slot.add_theme_stylebox_override("panel", _shelf_style(data, false))

	var art = ItemVisual.new()
	art.show_border = false  # Cleaner look in shop
	art.enable_tooltip = true
	art.tooltip_shows_price = true
	art.setup(data, SHELF_CELL, 1)
	# Standing on the shelf, not floating above it. A tall item grows upwards
	# from the same line a short one rests on, which is how a shelf of things
	# of different heights actually looks.
	art.position = Vector2(
		floor((SLOT_SIZE.x - art.size.x) / 2.0),
		floor(ART_FLOOR - art.size.y)
	)
	# The slot reads the item, so the artwork inside it must not answer the
	# pointer as well, or leaving the picture would take the card away while
	# the pointer is still on the shelf.
	art.mouse_filter = Control.MOUSE_FILTER_IGNORE
	art.tooltip_anchor = slot
	slot.add_child(art)

	# Store data and connect input
	slot.set_meta("shop_item", true)
	slot.set_meta("item_data", data)
	slot.set_meta("art", art)

	slot.gui_input.connect(_on_shop_item_input.bind(slot, data))
	slot.mouse_entered.connect(_on_shelf_entered.bind(slot))
	slot.mouse_exited.connect(_on_shelf_left.bind(slot))

	return slot


func _shelf_style(data: APITypes.Item, lit: bool) -> StyleBoxFlat:
	"""The glow behind an item on the shelf, in the colour of its rarity.

	Nothing at all until the pointer arrives. The shelves are painted into the
	background, and a box drawn around every item standing on one turns a shop
	into a row of cards floating in front of the furniture.
	"""
	var style := StyleBoxFlat.new()
	style.set_corner_radius_all(10)
	if not lit:
		style.bg_color = Color.TRANSPARENT
		return style

	var accent: Color = ItemTooltip.RARITY_COLORS.get(data.rarity, Color.WHITE)
	style.bg_color = Color(accent, 0.14)
	style.border_color = Color(accent, 0.65)
	style.set_border_width_all(2)
	return style


func _hang_price_tag(tag: Label, slot_node: Control, data: APITypes.Item) -> void:
	"""Put the tag on the front of the shelf the item stands on"""
	tag.size = SALE_TAG_SIZE if data.on_sale else TAG_SIZE
	tag.position = slot_node.position + Vector2(
		floor((SLOT_SIZE.x - tag.size.x) / 2.0), TAG_TOP)


func _dress_price_tag(tag: Label, data: APITypes.Item) -> void:
	"""Make the price look like a price, and say whether it is within reach.

	Gold ordinarily, green for a sale, red for a price there is not enough gold
	to meet. A sale says so on the plate itself rather than beside it, so that
	the shelf carries one number and not the same money written twice.
	"""
	var affordable: bool = GameStateManager.gold >= data.price
	var ink := SALE_COLOR if data.on_sale else PRICE_TAG_COLOR
	if not affordable:
		ink = UNAFFORDABLE_COLOR

	var plate: PriceTag = tag.get_node_or_null("Plate")
	if plate == null:
		plate = PriceTag.new()
		plate.name = "Plate"
		plate.mouse_filter = Control.MOUSE_FILTER_IGNORE
		# Behind the number it is written on.
		plate.show_behind_parent = true
		tag.add_child(plate)
	plate.size = tag.size
	plate.sale = data.on_sale
	plate.ink = ink

	tag.add_theme_color_override("font_color", ink.darkened(0.78))
	tag.add_theme_font_size_override("font_size", 20)
	tag.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	tag.vertical_alignment = VERTICAL_ALIGNMENT_CENTER

	# The number is centred in what the plate leaves it, so it clears the coin
	# stamped on the left rather than sitting across it.
	var room := StyleBoxEmpty.new()
	room.content_margin_left = plate.text_inset()
	room.content_margin_right = 8.0
	tag.add_theme_stylebox_override("normal", room)


# ============ The shelf under the pointer ============

func _on_shelf_entered(slot: Panel) -> void:
	"""Lift the item off the shelf and say what it is"""
	if slot.get_meta("sold", false):
		return
	slot.add_theme_stylebox_override("panel", _shelf_style(slot.get_meta("item_data"), true))
	_lift_shelf(slot, -SHELF_LIFT)

	var art = slot.get_meta("art")
	if is_instance_valid(art):
		art.hover_started()


func _on_shelf_left(slot: Panel) -> void:
	if slot.get_meta("sold", false):
		return
	slot.add_theme_stylebox_override("panel", _shelf_style(slot.get_meta("item_data"), false))
	_lift_shelf(slot, 0.0)

	var art = slot.get_meta("art")
	if is_instance_valid(art):
		art.hover_ended()


func _lift_shelf(slot: Panel, to: float) -> void:
	"""Raise or settle a slot. Instant where animations are off."""
	if not Presentation.request("shelf_lift", {"to": to}):
		slot.position.y = to
		return
	var tween := create_tween()
	tween.tween_property(slot, "position:y", to, 0.08) \
		.set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)


func _price_what_can_be_afforded() -> void:
	"""Dim whatever there is not enough gold for.

	Spending changes what is buyable, and the shelf is where the player looks
	next. Left alone it goes on offering things that cannot be bought, and the
	only way to find out is to try dragging each one.
	"""
	var refresh_button := get_node_or_null("RefreshButton")
	if refresh_button:
		refresh_button.disabled = GameStateManager.gold < 1

	for slot in shop_items:
		if not is_instance_valid(slot) or slot.get_meta("sold", false):
			continue
		var data: APITypes.Item = slot.get_meta("item_data")
		var affordable: bool = GameStateManager.gold >= data.price
		slot.modulate = Color.WHITE if affordable else OUT_OF_REACH

		var tag = slot.get_meta("price_tag", null)
		if is_instance_valid(tag):
			_dress_price_tag(tag, data)


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

func _on_shop_item_input(event: InputEvent, shop_item: Panel, item_data: APITypes.Item):
	if read_only_mode:
		return
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_LEFT:
			if event.pressed:
				# Start dragging the shop item
				_start_shop_drag(shop_item, item_data)

var dragging_shop_item: Panel = null
var dragging_shop_data: APITypes.Item = null
var drag_preview: Control = null
var container_preview: Control = null  # Holds one preview panel per covered square

func _start_shop_drag(shop_item: Panel, item_data: APITypes.Item):
	"""Start dragging a shop item"""
	# Don't allow dragging sold items
	if shop_item.modulate.a < 1.0:
		print("This item has already been sold")
		return

	# Check if player has enough gold
	var cost = item_data.price
	if GameStateManager.gold < cost:
		print("Not enough gold! Need %d, have %d" % [cost, GameStateManager.gold])
		return

	# Start dragging
	dragging_shop_item = shop_item
	dragging_shop_data = item_data

	# Create drag preview using ItemVisual for consistency
	drag_preview = ItemVisual.new()
	drag_preview.mouse_filter = Control.MOUSE_FILTER_IGNORE
	# Keep drag preview fully opaque
	# drag_preview.modulate.a = 0.7  # Removed transparency
	drag_preview.setup(item_data, inventory_grid.cell_size, inventory_grid.cell_spacing)

	# Add to scene
	add_child(drag_preview)

func _end_shop_drag(drop_position: Vector2):
	"""End dragging a shop item and try to purchase/place it"""
	if not dragging_shop_item or not drag_preview:
		return

	# Check if we're over the inventory grid
	var grid_pos = _global_to_grid(drop_position)

	# Check if this is a container/server
	var is_container = dragging_shop_data.is_container

	if is_container:
		# Containers need special handling - they can only go in the main grid area
		# They also define their own active area, not fit within existing containers
		if _can_place_container(dragging_shop_data, grid_pos):
			print("Placing container at position [%d, %d]" % [grid_pos.x, grid_pos.y])

			# Tell the server about the container purchase
			var item_id = dragging_shop_data.id
			if item_id:
				print("Purchasing container %s at position [%d, %d]" % [item_id, grid_pos.x, grid_pos.y])
				var response = await BattleServerAPI.purchase_item(
					item_id, [grid_pos.x, grid_pos.y])
				# Check if purchase was actually successful
				if response != null:
					# Add the container to our grid
					_add_container_from_purchase(response, grid_pos)
					_mark_shop_item_sold(dragging_shop_item)
				else:
					print("Failed to purchase container - server rejected placement")
		else:
			print("Cannot place container at this position")
	else:
		# Regular item placement
		if inventory_grid.can_place_item(dragging_shop_data, grid_pos):
			# Place the item in the grid immediately (optimistic update)
			if inventory_grid.place_shop_item(dragging_shop_data, grid_pos):
				print("Placed item at position [%d, %d]" % [grid_pos.x, grid_pos.y])

				# Now tell the server about the purchase
				var item_id = dragging_shop_data.id
				if item_id:
					print("Purchasing item %s at position [%d, %d]" % [item_id, grid_pos.x, grid_pos.y])
					BattleServerAPI.purchase_item(
						item_id, [grid_pos.x, grid_pos.y],
						dragging_shop_data.facing())
					_mark_shop_item_sold(dragging_shop_item)
			else:
				print("Failed to place item at position")
		else:
			print("Cannot place item at this position")

	# Hide the hover preview
	inventory_grid.hide_hover_preview()

	# Clean up container preview if it exists
	if container_preview:
		container_preview.queue_free()
		container_preview = null

	# Clean up drag state
	if drag_preview:
		drag_preview.queue_free()
		drag_preview = null
	dragging_shop_item = null
	dragging_shop_data = null

func _mark_shop_item_sold(shop_item: Panel):
	"""Mark a shop item as sold"""
	shop_item.set_meta("sold", true)
	shop_item.position.y = 0.0
	shop_item.add_theme_stylebox_override("panel", StyleBoxEmpty.new())

	# What was on the shelf fades, but the word saying so must not fade with
	# it, so the dimming goes on the artwork and the name rather than on the
	# whole slot.
	for child in shop_item.get_children():
		child.modulate = Color(0.45, 0.45, 0.55, 0.5)

	# The shelf is empty now, so the tag on the front of it has nothing to
	# price. Leaving it there is the shop asking for gold for a gap.
	var tag = shop_item.get_meta("price_tag", null)
	if is_instance_valid(tag):
		tag.visible = false

	var sold_label = Label.new()
	sold_label.text = "SOLD"
	sold_label.position = Vector2(0, TAG_TOP)
	sold_label.size = Vector2(SLOT_SIZE.x, 26)
	sold_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	sold_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	sold_label.add_theme_font_size_override("font_size", 18)
	sold_label.add_theme_color_override("font_color", Color(1.0, 0.3, 0.3))
	shop_item.add_child(sold_label)

# The grid squares a container of this shape would cover at grid_pos.
func _container_squares(container_data: APITypes.Item, grid_pos: Vector2i) -> Array[Vector2i]:
	var squares: Array[Vector2i] = []
	for offset in container_data.turned_shape():
		squares.append(Vector2i(grid_pos.x + int(offset[0]), grid_pos.y + int(offset[1])))
	return squares

func _can_place_container(container_data: APITypes.Item, grid_pos: Vector2i) -> bool:
	"""Check if a container can be placed at the given position"""
	var squares = _container_squares(container_data, grid_pos)

	# Check if it fits within the main grid bounds
	for square in squares:
		if square.x < 0 or square.y < 0:
			return false
		if square.x >= ROOM_WIDTH or square.y >= ROOM_HEIGHT:
			return false

	# Check for overlap with existing containers
	for placed in inventory_grid.containers:
		for square in placed.container.covered_squares():
			if square in squares:
				return false  # Overlapping

	return true

func _add_container_from_purchase(response: APITypes.PurchaseResponse, grid_pos: Vector2i):
	"""Add a purchased container to the inventory grid"""
	# The server sends every container the player owns, so this replaces the set.
	var as_data = []
	for container in response.server_containers:
		as_data.append(container.to_dict())
	GameStateManager.server_containers = as_data

	var current_state = GameStateManager.get_inventory_state()
	inventory_grid.load_inventory_state(APITypes.InventoryState.new({
		"servers": as_data,
		"items": current_state["items"]
	}))

func _show_container_preview(container_data: APITypes.Item, grid_pos: Vector2i):
	"""Show preview for container placement"""
	# Remove old preview if it exists
	if container_preview:
		container_preview.queue_free()
		container_preview = null

	# Nowhere on the board to answer about, so nothing is drawn. Anywhere on it
	# gets an answer, even when the answer is no.
	if grid_pos.x < 0 or grid_pos.y < 0 \
			or grid_pos.x >= ROOM_WIDTH or grid_pos.y >= ROOM_HEIGHT:
		inventory_grid.hide_hover_preview()
		return

	var allowed := _can_place_container(container_data, grid_pos)
	var style = StyleBoxFlat.new()
	style.bg_color = Color(0.3, 0.6, 1.0, 0.3) if allowed \
		else InventoryGrid.MARK_REFUSED_FILL
	style.border_color = Color(0.3, 0.6, 1.0, 0.8) if allowed \
		else InventoryGrid.MARK_REFUSED_EDGE
	style.set_border_width_all(3)
	style.set_corner_radius_all(4)

	# One panel per covered square, so the preview follows the container's shape
	container_preview = Control.new()
	container_preview.mouse_filter = Control.MOUSE_FILTER_IGNORE
	for square in _container_squares(container_data, grid_pos):
		# A container hanging over the edge covers squares that are not there.
		# Drawing them puts the preview outside the grid it is a preview of.
		if square.x < 0 or square.y < 0 \
				or square.x >= ROOM_WIDTH or square.y >= ROOM_HEIGHT:
			continue
		var cell = Panel.new()
		cell.mouse_filter = Control.MOUSE_FILTER_IGNORE
		cell.position = inventory_grid.grid_to_pixel(square)
		cell.size = Vector2(inventory_grid.cell_size, inventory_grid.cell_size)
		cell.add_theme_stylebox_override("panel", style)
		container_preview.add_child(cell)

	inventory_grid.add_child(container_preview)

func _on_ready_for_battle():
	# Get the actual inventory from the grid
	var grid_state = inventory_grid.get_inventory_state()

	# Check if player has any items
	if grid_state.items.size() == 0:
		print("Cannot start battle without any items!")
		_show_error_message("You need at least one item to start a battle!")
		return

	# Save current inventory state
	var inventory_state = get_inventory_state()

	print("DEBUG: Saving inventory before battle:")
	print("  Items to save: %d" % grid_state.items.size())
	for item in grid_state.items:
		print("    - %s at %s" % [item["name"], item["position"]])

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

func _update_stats():
	"""Write the numbers again, and say what changed about the gold"""
	if stat_values.is_empty():
		return

	for caption in stat_values:
		_write_stat(caption, _reading(caption))

	_show_gold_change()
	_price_what_can_be_afforded()


func _reading(caption: String) -> String:
	"""What the game can honestly say about this stat right now.

	Four of these rows have nothing behind them yet. The game has no classes,
	and no CPU level ever reaches the client -- a battle action carries none,
	so not even replaying a whole battle rebuilds the curve. Those rows read as
	a dash until a server sends something, because a number invented to fill
	the space is one the player cannot tell from a real one.
	"""
	match caption:
		"Name":
			return GameStateManager.player_name
		"Class":
			return PLAYER_CLASS
		"Gold":
			return str(GameStateManager.gold)
		"Health":
			# Nothing counts a health figure for a run. There was a
			# `player_health` that lost a point per defeat, but a run ends
			# after five, so it never fell below 95 and it is gone now.
			# Drawing it would be a bar that never moves.
			return NOT_KNOWN_YET
		"Stamina":
			return _stamina_pool()
		"Round":
			return str(GameStateManager.current_round)
		"Wins":
			return str(GameStateManager.wins)
		"Tries":
			return str(GameStateManager.player_lives)
		_:
			return NOT_KNOWN_YET


func _stamina_pool() -> String:
	"""How big a CPU pool the player fought with last.

	Every battle action carries where both pools stood, and that is the only
	place a level reaches the client: nothing on the session or the shop says
	it. So this is last battle's pool, which is right at the top of every shop
	phase and stops being right the moment something bought since raises it.
	Before the first battle there is nothing to read at all.
	"""
	var events := GameStateManager.last_battle_events
	for i in range(events.size() - 1, -1, -1):
		var details: Dictionary = events[i].details
		if details.has("max_cpu"):
			return _tidy(float(details["max_cpu"][0]))
	return NOT_KNOWN_YET


func _tidy(number: float) -> String:
	"""A number as a player would write it, with no tail of zeroes"""
	if is_equal_approx(number, roundf(number)):
		return str(int(roundf(number)))
	return str(snappedf(number, 0.1))


func _write_stat(caption: String, reading: String) -> void:
	"""Put a reading in its row, dimmed when there is no reading to put"""
	var value: Label = stat_values[caption]
	value.text = reading
	value.add_theme_color_override("font_color",
		NOT_KNOWN_COLOR if reading == NOT_KNOWN_YET else _stat_colour(caption))


func _show_gold_change() -> void:
	"""Flash what the gold just did, beside the gold itself.

	The number alone cannot say it: a player who spent four and earned two
	sees the same 'gold went down by two' either way.
	"""
	var gold: int = GameStateManager.gold
	var was: int = _gold_shown
	_gold_shown = gold
	# The first reading is not a change, and a new game is not a purchase.
	if was < 0 or was == gold or not gold_delta_label:
		return

	var change := gold - was
	gold_delta_label.text = ("+%d" % change) if change > 0 else str(change)
	gold_delta_label.add_theme_color_override(
		"font_color", EARNED_COLOR if change > 0 else SPENT_COLOR)

	if not Presentation.request("gold_change", {"change": change}):
		gold_delta_label.modulate.a = 0.0
		return

	gold_delta_label.modulate.a = 1.0
	var tween := create_tween()
	tween.tween_interval(0.7)
	tween.tween_property(gold_delta_label, "modulate:a", 0.0, 0.5)

func _on_purchase_completed(response: APITypes.PurchaseResponse):
	# Update gold from server response
	if response != null:
		GameStateManager.gold = response.gold
		_update_stats()

		# The item is bought but not yet placed, so the grid gets it when the
		# player drops it.
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

func _show_error_message(message: String):
	# Create error dialog
	var error_dialog = AcceptDialog.new()
	error_dialog.dialog_text = message
	error_dialog.title = "Notice"
	add_child(error_dialog)
	error_dialog.popup_centered()
	error_dialog.connect("confirmed", func(): error_dialog.queue_free())
