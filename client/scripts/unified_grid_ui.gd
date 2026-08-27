extends Control

const APITypes = preload("res://scripts/api_types.gd")
const ItemVisual = preload("res://scripts/item_visual.gd")
const InventoryGrid = preload("res://scripts/inventory_grid.gd")
const StorageBin = preload("res://scripts/storage_bin.gd")
const Presentation = preload("res://scripts/presentation.gd")
const PriceTag = preload("res://scripts/price_tag.gd")
const CombiningOverlay = preload("res://scripts/combining_overlay.gd")
const AuraOverlay = preload("res://scripts/aura_overlay.gd")
const RotateHint = preload("res://scripts/rotate_hint.gd")
const SellLure = preload("res://scripts/sell_lure.gd")
const Aura = preload("res://scripts/aura.gd")

# Game state is pulled from GameStateManager - no local copies

# Grid settings
const ROOM_WIDTH = 9   # Fixed grid width
const ROOM_HEIGHT = 7  # Fixed grid height
const CELL_SIZE = 45  # Default cell size, actual size calculated from container
const CELL_SPACING = 1

# Storage settings
#
# The tray holds no squares, and what is in it is drawn at the size it is drawn
# on the grid. An item that changed size on the way into the chest and back
# read as a different item.
## The opening of the tray, measured from the corner of the storage panel.
## Everything outside it is the tray's own walls -- the two posts either side
## and the lit lip along the front -- and squares drawn there sit on the
## picture rather than inside it.
##
## The tray is deeper than three rows need. That room is deliberate: items are
## meant to drop into it later, and they need somewhere to fall from. It is as
## big as it can be and still stand clear of the shelving above it, which
## reaches down to the floor on the right of the room.
const STORAGE_SHELF := Rect2(40, 21, 240, 214)

# Runtime calculated cell size
var actual_cell_size: float = CELL_SIZE
var actual_cell_spacing: float = CELL_SPACING

# Signal handlers for InventoryGrid
func _on_item_placed(item_data, grid_pos: Vector2i):
	"""Called when an item is placed in the inventory grid"""
	# Save the inventory state
	_save_current_state()
	# An item has landed, so its aura says what it caught, and anything that
	# has started being acted on says so too.
	if aura_overlay != null:
		aura_overlay.swell()
	if item_data != null:
		pop_what_took_effect(item_data.id)


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

func _on_drag_started(item_data: APITypes.Item):
	"""Name the price while the item is in hand, as the shop does.

	The chest only offers to buy while there is something to sell it. Standing
	there asking the whole time reads as an instruction rather than an offer,
	and there is nothing the player can do about it until they pick something
	up. What the chest does about being offered something is sell_lure.gd.
	"""
	if sell_lure != null:
		sell_lure.offer(item_data.sell_value)


func _on_drag_ended():
	if sell_lure != null:
		sell_lure.rest()


func _on_item_stored(item_data: APITypes.PlacedItem):
	"""Called when an item is dropped on the chest"""
	# It falls in from where it was let go of, before the server has answered.
	# Waiting would have it appear out of nowhere a moment later, and the drop
	# is the one moment the player is watching the tray.
	if storage_bin:
		storage_bin.catch(item_data, get_global_mouse_position())

	# The grid has already taken the item off, so put it back if the server
	# refuses. Otherwise the item is gone from the grid and not in the chest.
	var response = await BattleServerAPI.move_item(item_data.id, "storage")
	if response == null:
		print("The server refused to store it, putting the item back")
		inventory_grid._add_item(item_data)
		# It never reached the chest, so it must not be left lying in the tray.
		load_storage()
		_save_current_state()
		return

	_on_inventory_returned(response)
	_save_current_state()
	print("Put %s in the chest" % item_data.name)


func put_on_grid(item: APITypes.Item, grid_pos: Vector2i) -> bool:
	"""Move an item out of the chest onto a square of the grid."""
	if not inventory_grid.can_place_item(item, grid_pos):
		# Something is already there. If it can be moved out of the way, the
		# drop is a swap rather than a refusal -- the same as one square of
		# the grid to another.
		var in_the_way := inventory_grid.displaced_by(item, grid_pos)
		if in_the_way.is_empty():
			return false
		return await make_way_for(item, grid_pos, in_the_way)

	var response = await BattleServerAPI.move_item(
		item.id, [grid_pos.x, grid_pos.y], item.facing())
	if response == null:
		print("The server refused to put %s at %s" % [item.name, grid_pos])
		return false

	inventory_grid.place_shop_item(item, grid_pos, item.facing())
	_on_inventory_returned(response)
	_save_current_state()
	# The zone answers the question the player just asked by letting go.
	if aura_overlay != null:
		aura_overlay.swell()
	return true


func _on_items_displaced(
	item_data: APITypes.Item, grid_pos: Vector2i, displaced: Array
) -> void:
	"""An item was put down on the grid where others already stood"""
	await make_way_for(item_data, grid_pos, displaced)


func make_way_for(
	item_data: APITypes.Item, grid_pos: Vector2i, displaced: Array,
	buying: bool = false
) -> bool:
	"""Clear the squares an item was put down on, and put it there.

	The biggest of what stood there goes into the player's hand, since it is
	the hardest to find a new home for and the likeliest thing to be placed
	next. The rest are thrown in the chest, from where they were standing.

	Every step is the server's to agree to, and every answer carries the whole
	board back, so what is drawn afterwards is what the server holds rather
	than what this hoped for.
	"""
	var pointer := get_global_mouse_position()

	# They leave the board first. Asked the other way round, the square the
	# held item wants is still taken and the server rightly refuses.
	var answer = null
	for one in displaced:
		var moved = await BattleServerAPI.move_item(one["item"].id, "storage")
		if moved == null:
			print("The server would not clear the way for %s" % item_data.name)
			_draw_whole_board(answer)
			return false
		answer = moved

	# Buying names the same square by a different call, and answers with what
	# was bought rather than with the whole board.
	var landed = null
	if buying:
		landed = await BattleServerAPI.purchase_item(
			item_data.id, [grid_pos.x, grid_pos.y], item_data.facing())
	else:
		landed = await BattleServerAPI.move_item(
			item_data.id, [grid_pos.x, grid_pos.y], item_data.facing())
	if landed == null:
		print("The server refused to put %s down" % item_data.name)
		# Whatever made way is in the chest now, and that is the truth to draw.
		_draw_whole_board(answer)
		return false

	# The board as the server now has it -- but not the chest, which is drawn
	# below by the items falling into it. Drawn from the answer as well, they
	# would be lying in the tray before they had been thrown there.
	if buying:
		# The board the last move answered with, which is the one they left,
		# and then the bought item on top of it.
		if answer != null:
			inventory_grid.load_inventory_state(answer.as_inventory_state())
			GameStateManager.inventory_storage = answer.inventory_storage
		GameStateManager.gold = landed.gold
		inventory_grid.place_shop_item(item_data, grid_pos, item_data.facing())
		_update_stats()
	else:
		inventory_grid.load_inventory_state(landed.as_inventory_state())
		GameStateManager.inventory_storage = landed.inventory_storage
	_save_current_state()

	for one in displaced.slice(1):
		storage_bin.catch(one["item"], one["at"])
	# The biggest is in the hand rather than the chest, so it never reaches the
	# tray to be drawn there.
	storage_bin.pick_up(displaced[0]["item"], pointer)

	if aura_overlay != null:
		aura_overlay.swell()
	return true


func _draw_whole_board(inventory) -> void:
	"""Draw the board and the chest as the server last described them"""
	if inventory == null:
		# Nothing moved, so nothing on screen is out of date except the chest,
		# which a refused move may still have been drawn against.
		load_storage()
		return
	inventory_grid.load_inventory_state(inventory.as_inventory_state())
	GameStateManager.inventory_storage = inventory.inventory_storage
	load_storage()
	_save_current_state()


func _on_item_unstored(item_data: APITypes.Item, global_pos: Vector2):
	"""Called when an item is dragged out of the chest onto the grid"""
	# The chest has already let go of it on screen, so a move that does not
	# happen has to draw the chest again with the item still in it.
	if await put_on_grid(item_data, square_carried_to(item_data, global_pos)):
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
		container_data.id, [grid_pos.x, grid_pos.y], container_data.facing())
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


func hold(item: APITypes.Item, at := Vector2.INF) -> void:
	"""Take an item into the hand, to be put down with a click.

	It is in the chest already, so this is a shortcut and not a place of its
	own: whatever happens next, the item has somewhere safe to be.

	Takes where the pointer is, so that what it does with it can be asked about
	without a mouse. Told nothing, it reads the pointer itself.
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
	follow_pointer(get_global_mouse_position() if at == Vector2.INF else at)

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
	var body := held_item.turned_shape()
	if is_instance_valid(held_visual):
		# Under the middle of its own artwork, which is where a hand holds a
		# thing nobody picked a square on.
		var corner := inventory_grid.carried_corner(pointer, body)
		# And on the screen. The pointer can leave the window while an item is
		# in hand, and an item that goes with it is being carried where the
		# player cannot see it.
		var view := get_viewport_rect()
		held_visual.global_position = corner.clamp(
			view.position, (view.end - held_visual.size).max(view.position))

	# The mark goes where the artwork is, worked out from the artwork's own
	# corner rather than from a square the item is said to be held by. Two
	# answers to where a carried item is meant one of them was wrong.
	var grid_pos := square_carried_to(held_item, pointer)
	inventory_grid.mark_square(
		body, grid_pos, inventory_grid.can_place_item(held_item, grid_pos))


func square_carried_to(item: APITypes.Item, pointer: Vector2) -> Vector2i:
	"""The square this item lands on, carried by the middle of it to here.

	Asked of where the artwork is drawn, so the mark and the picture cannot
	give different answers.
	"""
	var local: Vector2 = \
		inventory_grid.get_global_transform().affine_inverse() * pointer
	return inventory_grid.square_for_corner(
		inventory_grid.carried_corner(local, item.turned_shape()))


## Every way something can be in hand, one per way the artwork is put under the
## pointer and the mark drawn for it. A rack dragged on the board is its own
## way, because the mark for a rack asks a different question of the board --
## free squares rather than squares a rack has made usable -- even though
## picking one up and carrying it is the same in every other respect.
##
## test_carrying.gd sweeps each of these, and fails if the list grows without a
## sweep to match. It is written down here rather than counted out of the code
## because a way of carrying is a decision, not a branch.
const WAYS_TO_CARRY := [
	"in hand",
	"off the shelf",
	"out of the chest",
	"dragged on the rack",
	"a rack dragged on the board",
]


func carrying_something() -> bool:
	"""Whether anything is in hand, however it came to be there.

	A rack counts. It is an item that other items stand on, and that is the
	only thing that separates the two: it is bought from the same shop, built
	from the same catalogue, stands on the same board and is carried by one of
	its own squares in exactly the same way. The server has said so all along
	-- Container extends PlacedItem and adds nothing to it -- and every place
	the client keeps a second answer for racks is a place the two can drift.
	"""
	return held_item != null \
		or dragging_shop_data != null \
		or (inventory_grid != null and inventory_grid.carrying() != null) \
		or (storage_bin != null and storage_bin.dragged() != null)


func turn(quarters: int, pointer := Vector2.INF) -> bool:
	"""Turn whatever is held, however it came to be held.

	Takes the pointer rather than reading it, so what a turn draws can be asked
	about without a mouse.

	An item is held for four different reasons -- dragged off the grid, taken
	out of the chest, carried off the shop shelf, or picked up after a
	container move set it down -- and all four are holding it. Says whether
	anything was, so the caller knows whether the input was used, and there is
	only one list of what counts as holding something. carrying_something()
	asks that same list.
	"""
	var at := get_global_mouse_position() if pointer == Vector2.INF else pointer
	if held_item:
		held_item = held_item.turned(quarters)
		if is_instance_valid(held_visual):
			held_visual.redraw_as(held_item)
		# Which hangs it from its new middle square as well as drawing the mark.
		follow_pointer(at)
		return true

	if dragging_shop_data:
		dragging_shop_data = dragging_shop_data.turned(quarters)
		if is_instance_valid(drag_preview):
			drag_preview.redraw_as(dragging_shop_data)
			# Turned, its middle square is somewhere else, so the artwork is
			# hung again or it swings away from the pointer holding it.
			_hang_the_shop_drag(at)
		# And the mark under it, which is a different set of squares now. The
		# mark used to be drawn only when the pointer moved, so a turn showed
		# the shape the item had before it, until the player moved off the
		# square and back to see what they had actually asked for.
		mark_where_the_shop_item_would_land(at)
		return true

	return inventory_grid.turn_dragged(quarters, at) \
		or (storage_bin != null and storage_bin.turn_dragged(quarters, at))


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

	# The chest is where it already is, so this is simply letting go. It falls
	# in from the pointer, because that is where the player let go of it.
	if storage_bin and storage_bin.catches(pointer):
		print("Left %s in the chest" % held_item.name)
		storage_bin.catch(held_item, pointer)
		release_hand()
		return

	# It stays in hand unless it lands, so a misclick cannot put it somewhere
	# the player did not choose.
	var item = held_item
	if await put_on_grid(item, square_carried_to(item, pointer)):
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
	# Moved into a zone, or moved a zone over something: either way, whatever
	# has started being acted on says so.
	pop_what_took_effect(item_id)


func _save_current_state():
	"""Save the current inventory state to GameStateManager"""
	var state = inventory_grid.get_inventory_state()
	GameStateManager.save_inventory_state(state.inventory_grid, state.server_containers)

func _input(event):
	# Turning works on anything held, dragged or in hand. R and the wheel
	# forward go clockwise, E and the wheel back the other way. The input is
	# only swallowed if something actually turned, so the wheel still scrolls
	# when the player is holding nothing.
	var quarters := _turn_asked_for(event)
	if quarters != 0 and turn(quarters):
		get_viewport().set_input_as_handled()
		return

	# Letting go of the button asks the aura to answer again. Every click, not
	# only the ones that place something: it is how a player asks "and what is
	# this one worth?" without having to pick the item up and put it back.
	# The overlay ignores a second ask too soon after the first, so a placement
	# -- which is also a click -- swells once.
	if event is InputEventMouseButton \
			and event.button_index == MOUSE_BUTTON_LEFT and not event.pressed \
			and aura_overlay != null:
		aura_overlay.swell()

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
				_hang_the_shop_drag(event.global_position)

			mark_where_the_shop_item_would_land(event.global_position)


func _hang_the_shop_drag(pointer: Vector2) -> void:
	"""Put the artwork of a shop item under the pointer, by its middle square.

	The same hold an item in hand is carried by, so the two look the same to
	the player and the mark under either one is under the artwork.
	"""
	if not is_instance_valid(drag_preview) or dragging_shop_data == null:
		return
	drag_preview.global_position = inventory_grid.carried_corner(
		pointer, dragging_shop_data.turned_shape())


func mark_where_the_shop_item_would_land(pointer := Vector2.INF) -> void:
	"""Mark the square an item carried off the shelf would land on.

	Takes the pointer rather than reading it, so what it decides can be asked
	about without a mouse. Called on every movement and on every turn: both
	change which squares the item would cover.
	"""
	if dragging_shop_data == null:
		return
	var at := get_global_mouse_position() if pointer == Vector2.INF else pointer
	var grid_pos := square_carried_to(dragging_shop_data, at)
	if dragging_shop_data.is_container:
		_show_container_preview(dragging_shop_data, grid_pos)
	else:
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
var storage_bin: StorageBin        # The chest, which is a box and not a grid

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
# The arcs, the glow and the progress label (GDD 5.3). Drawn over the shelf,
# the rack and the chest at once, because it joins one to another.
var combining_overlay: Control
# The zone an item reaches into (GDD 4.3). A child of the grid, because every
# square it draws is a grid square.
var aura_overlay: Control
## Says how to turn an item, while one is in hand. See rotate_hint.gd.
var rotate_hint: Control
## What the sell chest does about an item being carried. See sell_lure.gd.
var sell_lure: Node
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

	# The player wears their own Sentaur here. Choosing it happens on the main
	# menu -- this screen has no room for another control (GDD 11).
	_wear_skin()

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

	# Which items go together never changes, so it is asked for once and
	# answered from here after that. Nothing waits on it: until it arrives the
	# screen simply draws no arcs.
	GameStateManager.fetch_combining_catalogue()
	# And what the buffs do, for the chips beside each fighter in the battle
	# that comes after this shop. Asked for here rather than there because the
	# shop is where a player spends their time, so it has arrived long before
	# anything is hovered.
	GameStateManager.fetch_status_rules()

	# Then load saved inventory if it exists
	var saved_inventory = GameStateManager.get_inventory_state()
	print("DEBUG: Loading saved inventory on UnifiedGridUI startup:")
	print("  Items: %d" % saved_inventory.get("inventory_grid", []).size())
	print("  Racks: %d" % saved_inventory.get("server_containers", []).size())
	for item in saved_inventory["inventory_grid"]:
		print("    Item: %s at %s" % [item["name"], item["position"]])
	_load_saved_inventory(saved_inventory)


	if not hide_shop:
		_load_shop_from_state()

	# Last, because it draws the rack twice: as it fought, and as it is now.
	await play_combining()

func configure(settings: Dictionary):
	read_only_mode = settings.get("read_only", false)
	hide_shop = settings.get("hide_shop", false)
	hide_storage = settings.get("hide_storage", false)

	# Settings will be applied in _ready() if not ready yet
	if not is_node_ready():
		return

func _load_saved_inventory(saved_data: Dictionary):
	# Wrapper to load saved inventory from GameStateManager
	if saved_data.has("inventory_grid") and saved_data.has("server_containers"):
		print("Loading saved inventory with %d racks and %d items" % [
			saved_data.server_containers.size(),
			saved_data.inventory_grid.size()
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
	return {"server_containers": [], "inventory_grid": []}

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
	_build_the_hints()

	print("UI setup complete")

func _create_header():
	if read_only_mode:
		return
	stats_panel = $CharacterStats
	_dress_stats_plate()
	_build_stat_rows()
	_update_stats()


func _dress_stats_plate() -> void:
	"""Give the numbers something to stand on.

	The wall behind them used to have a panel painted on it with CHARACTER
	STATS across the top. The wall that replaced it is bare above and lockers
	below, so the numbers ran off the wall and onto the drawers halfway down
	the list and the last of them could barely be read at all.
	"""
	var plate := get_node_or_null("StatsPlate") as Panel
	if plate == null:
		return
	var style := StyleBoxFlat.new()
	# Nearly solid. The drawers behind the lower half of the list are busy
	# enough to read through, which was the trouble in the first place.
	style.bg_color = Color(0.05, 0.05, 0.07, 0.93)
	style.border_color = Color(PRICE_TAG_COLOR, 0.35)
	style.set_border_width_all(2)
	style.set_corner_radius_all(10)
	plate.add_theme_stylebox_override("panel", style)


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
	rank_label.add_theme_color_override("font_color", Color(PRICE_TAG_COLOR, 0.85))

	# The same plate the rest of the screen's controls carry. In blue it was
	# the one thing on the wall that had come from somewhere else.
	var plate := StyleBoxFlat.new()
	plate.bg_color = Color(0.09, 0.09, 0.12, 0.85)
	plate.border_color = Color(PRICE_TAG_COLOR, 0.4)
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

	# The wall behind the grid is bare, so this outline is the only thing
	# saying where things may be put. It stays, but in the light the room is
	# lit by rather than the blue it arrived in.
	inventory_grid.border_color = Color(0.72, 0.82, 0.25, 0.4)
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
	inventory_grid.items_displaced.connect(_on_items_displaced)
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
	if not has_node("StoragePanel"):
		return

	# The tray is its own picture, hung behind the chest by the scene. The
	# panel is only the box it and the chest are measured from, so it draws
	# nothing itself.
	var storage_bg = $StoragePanel
	storage_bg.add_theme_stylebox_override("panel", StyleBoxEmpty.new())

	# modulate multiplies down into children, so anything less than white here
	# fades the tray and everything lying in it together.
	storage_bg.modulate = Color.WHITE

	# The chest is a box things are thrown into. It covers the whole panel,
	# because it answers the pointer for everything lying in the tray and a
	# thrown item can come to rest anywhere in it.
	storage_bin = StorageBin.new()
	storage_bin.name = "StorageBin"
	storage_bin.read_only = read_only_mode
	storage_bg.add_child(storage_bin)
	storage_bin.position = Vector2.ZERO
	storage_bin.size = storage_bg.size
	storage_bin.configure(
		STORAGE_SHELF, inventory_grid.cell_size, inventory_grid.cell_spacing)

	# Everything between the walls takes a drop, all the way up the screen, and
	# not only the tray itself. The walls reach that high as well, so a thing
	# let go of up there has nowhere to fall but into the chest.
	if inventory_grid:
		inventory_grid.storage_zone = storage_bin.catch_zone()

	storage_bin.sell_zone = sell_chest
	storage_bin.grid_zone = inventory_grid
	storage_bin.item_sold.connect(_on_chest_item_sold)
	storage_bin.item_unstored.connect(_on_item_unstored)
	# An item out of the chest can be sold just as one off the grid can, so the
	# sell chest names its price while it is in hand either way.
	storage_bin.drag_started.connect(_on_drag_started)
	storage_bin.drag_ended.connect(_on_drag_ended)

	load_storage()


func load_storage():
	"""Draw what the server says is in the chest.

	An item in the chest is off the grid, so it has no place of its own and
	nothing here gives it one: it lies where it landed. This only adds what has
	arrived and takes away what has gone, because the server answers every move
	with the whole chest and tidying the tray up behind the player on each of
	those answers would undo every throw.
	"""
	if hide_storage or not storage_bin:
		return

	storage_bin.show_items(
		GameStateManager.inventory_storage,
		held_item.id if held_item else "")


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
				refresh_btn.text = "REROLL 1g"  # _update_stats writes the real price
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
## the price tag on the lip of the shelf below it. The item is not named here
## -- the card the shelf puts out under the pointer names it, and a caption on
## every slot is five names to read past to find one item.
##
## Tall enough to hold the artwork and reach a little past the item's feet,
## and no taller: the bottom shelf ends where the floor furniture begins, and
## a slot that overhangs it lights up over the tray when the pointer is
## nowhere near the shelf.
const SLOT_SIZE := Vector2(200, 180)
## The biggest a square is drawn on a shelf, when the alcove is not what
## decides. Only a fallback: the answer is the size the grid draws a square,
## so that an item is the same size on the shelf as it is once it is bought.
## The grid works its own size out from the room it is given, and there is no
## grid at all while a screen is only being read from.
const SHELF_CELL := 45.0
## The most room an item's artwork may take on a shelf.
##
## Not the painted alcove, which is about 190 by 162: an item three squares
## tall wants 182 and a shelf is 220 from its floor to the floor of the one
## above, so it fits in the room a shelf has without reaching the next one --
## it simply stands taller than the opening it is in, the way something too
## big for a shelf actually does. Held to the alcove instead, a three-square
## item was drawn at 49 pixels a square beside a one-square item at 60, which
## is what a player notices.
##
## Four squares tall wants 243 and there is no honest way to fit that, so
## those are still drawn smaller -- but at 52 rather than 36.
##
## Across, it is the space between one slot and the next: only one item in the
## catalogue is four squares wide, and it has the room.
const SHELF_ROOM := Vector2(284, 212)
## The line every item stands on, whatever its height.
const ART_FLOOR := 150.0
## Far enough below the line to clear the light along the front of the shelf,
## so the plate hangs on the lip rather than over the lamp.
const TAG_TOP := 166.0
## How far a tag with no lip to hang from drops past the item's feet instead.
## Far enough to clear the item and land on the lit strip it stands on, so it
## reads as a label clipped to the shelf rail rather than a plate over the
## goods, and still stops short of the bottom edge of the shelving.
const TAG_ON_SHELF := 28.0
const TAG_SIZE := Vector2(88, 34)
## A sale plate carries a word as well as a number, so it is the wider of the
## two. Both stay centred on the same point, so the shelf still reads as a row.
const SALE_TAG_SIZE := Vector2(118, 34)
## How far a shelf lifts under the pointer.
const SHELF_LIFT := 6.0


func _dress_buttons() -> void:
	"""Give the two buttons a look the wall behind them does not supply.

	Both used to stand on artwork that drew the sign for them -- the neon slab
	for the battle, the reroll plate for the shop -- and wanted nothing of
	their own. The wall that replaced it is bare panelling and lit shelves, so
	each carries its own faint plate instead.
	"""
	# The battle key is a picture of a key, with what it says painted on it, so
	# it wants nothing from here at all -- a plate behind it would be a second
	# button drawn around the first.

	# Above the battle key, where a player looking at the rack and wondering
	# what "for each sentinel star item" means will find it. The same page the
	# menu opens; it is wanted here more, since here they have items in front
	# of them to ask about.
	var guide := get_node_or_null("HowToPlayButton")
	if guide:
		_dress_button(guide, PRICE_TAG_COLOR, 18, 0, true)
		if not guide.pressed.is_connected(_open_how_to_play):
			guide.pressed.connect(_open_how_to_play)

	var refresh_button := get_node_or_null("RefreshButton")
	if refresh_button:
		# The wall used to have REROLL and its price painted on it, and the
		# button was that plate and said nothing of its own. The shelves that
		# replaced the painting carry no writing, so a button with nothing on
		# it is a button nobody can see. It stands on the top shelf now and
		# says what it is.
		_dress_button(refresh_button, PRICE_TAG_COLOR, 20, 0, true)


func _open_how_to_play() -> void:
	"""What every word in the game means, over the shop rather than instead
	of it: the rack stays behind the page, and closing it puts everything
	back where it was."""
	add_child((load("res://scripts/how_to_play.gd") as GDScript).new())


func _dress_button(
	button: Button, ink: Color, font_size: int, text_top: int = 0,
	plate: bool = false
) -> void:
	"""Give a button its look: its ink, and either a plate or nothing at all.

	A button standing on painted artwork wants nothing of its own, or it
	covers the sign it is meant to be. A button standing on bare panelling
	wants a plate, or there is nothing there to press. `plate` says which.
	"""
	for state in ["normal", "hover", "pressed", "focus", "disabled"]:
		var style := StyleBoxFlat.new()
		if plate:
			# Faint on purpose: enough of an edge to read as a control, not
			# enough to become another lit box competing with the shelves.
			style.bg_color = Color(0.05, 0.05, 0.07, 0.75 if state == "hover" else 0.55)
			style.border_color = Color(ink, 0.2 if state == "disabled" else 0.55)
			style.set_border_width_all(2)
		else:
			style.bg_color = (
				Color(1, 1, 1, 0.07) if state == "hover" else Color.TRANSPARENT
			)
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
	art.setup(data, _shelf_cell(data), 1)
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
	slot.add_child(art)

	# Store data and connect input
	slot.set_meta("shop_item", true)
	slot.set_meta("item_data", data)
	slot.set_meta("art", art)

	slot.gui_input.connect(_on_shop_item_input.bind(slot, data))
	slot.mouse_entered.connect(_on_shelf_entered.bind(slot))
	slot.mouse_exited.connect(_on_shelf_left.bind(slot))

	return slot


func _shelf_cell(data: APITypes.Item) -> float:
	"""How big a square this item's artwork is drawn at on the shelf.

	The size the grid draws a square, so that an item does not change size the
	moment it is bought -- it used to be drawn a quarter smaller on the shelf
	than it would be on the board.

	A shelf has room between its own floor and the floor of the one above, and
	that is what an item is fitted to -- not the painted alcove, which is
	shorter. An item that stands taller than its opening reads as too big for
	the shelf, which is true and is what a shop looks like; one drawn smaller
	than the same item on the board reads as a different item. Whichever way
	runs out first decides, so the item keeps its shape.
	"""
	var across := 0
	var down := 0
	for offset in data.turned_shape():
		across = max(across, offset[0] + 1)
		down = max(down, offset[1] + 1)
	var grid_cell: float = inventory_grid.cell_size if inventory_grid else SHELF_CELL
	if across < 1 or down < 1:
		return grid_cell
	return min(
		grid_cell,
		floor((SHELF_ROOM.x - (across - 1) * CELL_SPACING) / across),
		floor((SHELF_ROOM.y - (down - 1) * CELL_SPACING) / down)
	)


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
	"""Put the tag on the lip of the shelf the item stands on.

	Below the item's feet wherever the shelving has a front to hang it from.
	The bottom shelf has none: the floor is what is under it, and the tray and
	the de-rez bay stand there, so a tag hung below that shelf lands on the
	furniture. There the tag stands on the shelf in front of the item instead.
	"""
	tag.size = SALE_TAG_SIZE if data.on_sale else TAG_SIZE
	var across: float = floor((SLOT_SIZE.x - tag.size.x) / 2.0)
	var below: float = slot_node.position.y + TAG_TOP
	if below + tag.size.y <= shop_container.size.y:
		tag.position = Vector2(slot_node.position.x + across, below)
		return
	tag.position = Vector2(
		slot_node.position.x + across,
		slot_node.position.y + ART_FLOOR - tag.size.y + TAG_ON_SHELF)


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
		var price: int = GameStateManager.shop_refresh_cost
		refresh_button.disabled = GameStateManager.gold < price
		# The sign says the price the server will charge. It said "1g" whatever
		# the price was, and the fifth roll of a round costs two.
		refresh_button.text = "REROLL %dg" % price
		refresh_button.tooltip_text = "Reroll the shop for %d gold" % price

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

	# Let go anywhere over the chest, so it is bought and falls in. A container
	# is the one thing that cannot go there: it is the ground other items stand
	# on, and the server keeps none in the chest.
	if storage_bin and storage_bin.catches(drop_position):
		if dragging_shop_data.is_container:
			print("A container cannot go in the chest")
		else:
			await _buy_into_the_chest(drop_position)
		_finish_shop_drag()
		return

	# Check if we're over the inventory grid
	var grid_pos = square_carried_to(dragging_shop_data, drop_position)

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
					item_id, [grid_pos.x, grid_pos.y],
					dragging_shop_data.facing())
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
			# Something is already there. If it can be moved out of the way,
			# buying it is a swap rather than a refusal, the same as moving
			# one square of the grid to another.
			var in_the_way := inventory_grid.displaced_by(
				dragging_shop_data, grid_pos)
			if in_the_way.is_empty():
				print("Cannot place item at this position")
			else:
				var slot := dragging_shop_item
				var buying := dragging_shop_data
				# The drag is over either way, and what follows waits on the
				# server, which is no reason to keep carrying the item.
				_finish_shop_drag()
				if await make_way_for(buying, grid_pos, in_the_way, true):
					_mark_shop_item_sold(slot)
				return

	_finish_shop_drag()


func _buy_into_the_chest(pointer: Vector2) -> void:
	"""Buy what is being carried out of the shop and let it fall in the chest.

	The chest is a place the server knows about, so this is a purchase like any
	other -- it simply names the chest rather than a square. Nothing is drawn
	until the server has answered, because there is no square being covered and
	so nothing for a refusal to have to undo.
	"""
	var data = dragging_shop_data
	var slot = dragging_shop_item

	var response = await BattleServerAPI.purchase_item(data.id, "storage")
	if response == null:
		print("The server would not sell %s into the chest" % data.name)
		return

	GameStateManager.gold = response.gold
	GameStateManager.inventory_storage.append(response.purchased_item)
	storage_bin.catch(response.purchased_item, pointer)
	_mark_shop_item_sold(slot)
	_update_stats()
	print("Bought %s into the chest" % data.name)


func _finish_shop_drag() -> void:
	"""Put down whatever the shop drag was drawing, however it ended"""
	inventory_grid.hide_hover_preview()

	if container_preview:
		container_preview.queue_free()
		container_preview = null

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
	"""Whether a rack may stand here. The grid's own rule, not a second one.

	This was the same walk written out again against ROOM_WIDTH and
	ROOM_HEIGHT rather than against the grid's own size, and without the rule
	that a rack is no obstacle to itself. Two opinions about what fits is the
	shape that let a container be sold hanging off the edge of the board and
	then refused by the engine at every battle after.
	"""
	return inventory_grid.can_place_container(container_data, grid_pos)

func _add_container_from_purchase(response: APITypes.PurchaseResponse, grid_pos: Vector2i):
	"""Add a purchased container to the inventory grid"""
	# The server sends every container the player owns, so this replaces the set.
	var as_data = []
	for container in response.server_containers:
		as_data.append(container.to_dict())
	GameStateManager.server_containers = as_data

	var current_state = GameStateManager.get_inventory_state()
	inventory_grid.load_inventory_state(APITypes.InventoryState.new({
		"server_containers": as_data,
		"inventory_grid": current_state["inventory_grid"]
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
	if grid_state.inventory_grid.size() == 0:
		print("Cannot start battle without any items!")
		_show_error_message("You need at least one item to start a battle!")
		return

	# Save current inventory state
	var inventory_state = get_inventory_state()

	print("DEBUG: Saving inventory before battle:")
	print("  Items to save: %d" % grid_state.inventory_grid.size())
	for item in grid_state.inventory_grid:
		print("    - %s at %s" % [item["name"], item["position"]])

	# Save to GameStateManager so it persists across scene changes
	GameStateManager.save_inventory_state(grid_state.inventory_grid, grid_state.server_containers)

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
	if GameStateManager.gold >= GameStateManager.shop_refresh_cost:
		print("Refreshing shop from server...")
		# Call the real server to refresh shop
		var response = await BattleServerAPI.refresh_shop(GameStateManager.current_round)
		if response != null and response.current_shop.size() > 0:
			GameStateManager.gold = response.gold  # Server manages gold deduction
			# The next one costs what the server says it will, which is not
			# what this one cost: the price climbs through the round.
			GameStateManager.shop_refresh_cost = response.next_refresh_cost
			_update_stats()
			_display_shop_items(response.current_shop)
			GameStateManager.current_shop = response.current_shop
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


# ============= Combining: the arcs, the glow and the label (GDD 5.3) =============
#
# Three places hold items -- the shelf, the rack and the chest -- and combining
# does not care which of them an item is in. So the drawing is one node over
# the lot of them, and what is under the pointer is asked of all three.
#
# Worked out each frame rather than kept. Every one of these answers depends on
# where a thing is on screen, and the shop redraws, the chest settles and an
# item being dragged moves every frame anyway; state kept beside that would
# only be a second copy that goes stale.


func _build_the_hints() -> void:
	"""Everything drawn over the board to help a player decide: the combining
	arcs and glow, the aura a held item reaches with, and the merge cues."""
	if read_only_mode:
		# A rack being watched cannot be changed, so there is nothing to warn
		# about, nothing to reach for and nowhere to put anything.
		return
	combining_overlay = CombiningOverlay.new()
	combining_overlay.name = "CombiningOverlay"
	add_child(combining_overlay)

	aura_overlay = AuraOverlay.new()
	aura_overlay.name = "AuraOverlay"
	aura_overlay.grid = inventory_grid
	# Beside the grid, not inside it: the grid frees every child it has each
	# time the board is redrawn.
	add_child(aura_overlay)

	rotate_hint = RotateHint.new()
	rotate_hint.name = "RotateHint"
	add_child(rotate_hint)

	if sell_chest != null:
		sell_lure = SellLure.new()
		sell_lure.name = "SellLure"
		add_child(sell_lure)
		sell_lure.watch(sell_chest)

	_build_merge_sounds()


func _build_merge_sounds() -> void:
	"""One player per cue, made once. They never overlap each other."""
	for beat in MERGE_SOUNDS:
		var path: String = MERGE_SOUNDS[beat]
		if not ResourceLoader.exists(path):
			continue
		var voice := AudioStreamPlayer.new()
		voice.name = "Merge" + beat.capitalize()
		voice.stream = load(path)
		voice.volume_db = MERGE_VOLUME[beat]
		add_child(voice)
		_merge_voices[beat] = voice


func _merge_sound(beat: String) -> void:
	"""Sound one beat of a merge. Silent where animations are off, which is
	where there is no audio driver to sound it on either.

	Once for the round, not once for each merge: two racks combining at the
	same moment is one event to look at, and two copies of the same cue over
	each other is a flam.
	"""
	if not Presentation.animations_enabled():
		return
	var voice = _merge_voices.get(beat)
	if voice != null:
		voice.play()


func _process(_delta: float) -> void:
	refresh_combining()
	refresh_aura()
	if rotate_hint != null:
		rotate_hint.carrying(carrying_something())
	if sell_lure != null:
		sell_lure.pointing_at_it(get_global_mouse_position())


func refresh_combining(pointer := Vector2.INF) -> void:
	"""Draw what the player is reaching for, and what is about to happen.

	Takes where the pointer is, so that what the screen would draw can be asked
	about without a mouse. Told nothing, it reads the pointer itself.
	"""
	if combining_overlay == null:
		return

	_show_the_glow()

	var reaching := combining_source(pointer)
	if reaching.is_empty():
		combining_overlay.no_lines()
		combining_overlay.no_progress()
		return

	var item: APITypes.Item = reaching["item"]
	combining_overlay.lines_from(reaching["node"], partner_nodes(item))
	combining_overlay.progress(
		GameStateManager.combining.progress_label(item.id), reaching["node"])


func _show_the_glow() -> void:
	"""Light the items that will combine when the battle starts.

	Only the rack: an item in the chest or on the shelf is not in the rack, and
	nothing combines anywhere else.
	"""
	var groups := []
	for ids in GameStateManager.combining.groups_about_to_combine():
		var lit := []
		for item_id in ids:
			var visual = inventory_grid.item_visual(item_id)
			if is_instance_valid(visual):
				lit.append(visual)
		if lit.size() > 1:
			groups.append(lit)
	combining_overlay.glow_around(groups)


func combining_source(pointer := Vector2.INF) -> Dictionary:
	"""The item the arcs come from: whatever is in hand, else what is hovered.

	Empty when the player is neither holding nor pointing at anything, which is
	when nothing is drawn -- the arcs answer a question, and nobody asked one.

	What is held wins over what is under the pointer. An item in hand is drawn
	under the pointer, so the two are usually the same thing anyway, and where
	they differ the one in the hand is the one being decided about.
	"""
	if held_item != null and is_instance_valid(held_visual):
		return {"item": held_item, "node": held_visual}
	if dragging_shop_data != null and is_instance_valid(drag_preview):
		return {"item": dragging_shop_data, "node": drag_preview}
	if inventory_grid != null and inventory_grid.dragging_object != null:
		var dragged = inventory_grid.dragging_object
		return {"item": dragged.item_data, "node": dragged}
	if storage_bin != null and storage_bin.dragged() != null:
		return {"item": storage_bin.dragged(), "node": storage_bin.dragged_visual()}
	return item_under(
		get_global_mouse_position() if pointer == Vector2.INF else pointer)


func item_under(pointer: Vector2) -> Dictionary:
	"""What the pointer is on, wherever it is, as {item, node}. Empty for none.

	The shelf answers with the whole slot rather than the picture on it: a
	player reaching for an item aims at the item, and 45 pixels of artwork is a
	small thing to have to hit.
	"""
	for slot in shop_items:
		if not is_instance_valid(slot) or slot.get_meta("sold", false):
			continue
		if slot.get_global_rect().has_point(pointer):
			return {"item": slot.get_meta("item_data"), "node": slot.get_meta("art")}

	if inventory_grid != null:
		var visual := inventory_grid.standing_under(pointer)
		if visual != null:
			return {"item": visual.item_data, "node": visual}

	if storage_bin != null:
		# The chest is asked rather than measured: what lies in it lies at
		# whatever angle it landed at, and only the chest knows that.
		var lying = storage_bin.item_at(pointer)
		if lying != null:
			return {"item": lying, "node": storage_bin.drawn(lying.id)}

	return {}


func partner_nodes(item: APITypes.Item) -> Array:
	"""Every item on screen this one could combine with, as its drawing.

	Answered from the catalogue, which the client holds, rather than by asking
	the server: this is wanted on every frame of a drag.

	By id, not by type. A Long Poll eats two Edge Caches, so one Edge Cache
	draws an arc to another -- but never to itself.
	"""
	var partners := GameStateManager.combining.partners_of(item.item_type)
	var reaches := []
	if partners.is_empty():
		return reaches

	for other in items_on_screen():
		var its: APITypes.Item = other["item"]
		if its.id != item.id and partners.has(its.item_type):
			reaches.append(other["node"])
	return reaches


func items_on_screen() -> Array:
	"""Everything the player can see, as [{item, node}], wherever it stands."""
	var seen := []
	for slot in shop_items:
		if is_instance_valid(slot) and not slot.get_meta("sold", false):
			seen.append({
				"item": slot.get_meta("item_data"), "node": slot.get_meta("art")})

	if inventory_grid != null:
		for visual in inventory_grid.items:
			if is_instance_valid(visual):
				seen.append({"item": visual.item_data, "node": visual})

	if storage_bin != null:
		for item in GameStateManager.inventory_storage:
			var visual = storage_bin.drawn(item.id)
			if is_instance_valid(visual):
				seen.append({"item": item, "node": visual})

	return seen


# ============= Playing back what combined (GDD 5.3) =============
#
# Combining happens the moment the battle ends, but the player does not see the
# rack again until they have watched the battle and closed the result. So the
# shop screen plays it forwards, and never shows the result before the merge.


## How long each beat of a merge takes. The rules say nothing about this; what
## it has to do is read as one event -- the rack notices, the items commit, and
## the result arrives -- rather than as items disappearing.
const MERGE_SHAKE := 0.55
const MERGE_FLY := 0.42
const MERGE_FLASH := 0.16
const MERGE_ARRIVE := 0.65

## One cue per beat rather than one long one. The middle of it has to land on
## the frame the items go out on, and a cue that has to stay in step with an
## animation is a cue that drifts. Made by tools/create_sounds.py.
const MERGE_SOUNDS := {
	"charge": "res://assets/audio/merge_charge.wav",
	"flash": "res://assets/audio/merge_flash.wav",
	"done": "res://assets/audio/merge_done.wav",
}
## The pull sits under the strike, and both sit under the music.
const MERGE_VOLUME := {"charge": -13.0, "flash": -7.0, "done": -9.0}

var _merge_voices: Dictionary = {}


func play_combining() -> void:
	"""Show what the rack did while the player was watching the battle.

	Three steps, and the last is what makes the rest of it safe:

	1. the rack that fought, which is the rack before anything combined;
	2. each combining, all of them at once -- an ingredient is never used twice
	   and a result never feeds another combination in the same shop phase, so
	   none of them waits on another;
	3. what the player holds now, from the server's own answer.

	Ending on step 3 means a bug in step 2, an interruption, or a player who
	clicks straight through cannot leave the wrong rack on the screen.
	"""
	var combinations := GameStateManager.combinations_to_play
	var fought_with := GameStateManager.rack_that_fought
	# Taken rather than read: this is shown once, on the way into the shop.
	GameStateManager.combinations_to_play = []
	GameStateManager.rack_that_fought = null
	if combinations.is_empty() or fought_with == null:
		return

	inventory_grid.load_inventory_state(fought_with)
	await get_tree().process_frame
	# Starting a battle is one keypress, and the merge takes most of a second.
	# A player who leaves in that time takes this screen with them, and what is
	# left of this is a coroutine drawing on a screen that is gone.
	if not is_inside_tree():
		return

	_merge_sound("charge")
	for made in combinations:
		# Written down as well as drawn. When a player says "that ate the wrong
		# thing", what was actually eaten is the first question, and the items
		# are gone from the rack by the time it is asked.
		print("Combining %s from %s" % [made.made,
			", ".join(made.consumed.map(func(item): return item.name))])
		_play_one_combining(made)

	await _pause(MERGE_SHAKE + MERGE_FLY)
	if not is_inside_tree():
		return
	_merge_sound("flash")
	# One for the round, whatever combined. The board is drawn again while it
	# is at its brightest, so the swap happens where it cannot be seen.
	if combining_overlay != null:
		combining_overlay.whiteout()

	await _pause(MERGE_FLASH)
	if not is_inside_tree():
		return

	# The board is drawn again inside the flash, which is what hides the swap.
	_reload_board()
	_merge_sound("done")
	for made in combinations:
		_welcome_the_result(made)
	await _pause(MERGE_ARRIVE)


func _pause(seconds: float) -> void:
	"""Wait out a beat of the merge. A frame of it where animations are off."""
	await get_tree().create_timer(Presentation.delay(seconds) + 0.01).timeout


func _play_one_combining(made: APITypes.Combination) -> void:
	"""One merge, in four beats.

	The items rattle where they stand, fly into the middle, go out in a white
	flash, and what they became stands up on the squares they left. The rattle
	is what makes it read as something happening to the items rather than to
	the screen: they are pulled at before they move.

	Catalysts rattle with the rest and then stay where they are. They are not
	eaten, and an animation that swept them up as well would say they were.
	"""
	if not Presentation.request("item_combined",
			{"made": made.made, "ate": made.consumed.size()}):
		return

	var lands_on := _where_the_result_lands(made)
	var which := 0
	for eaten in made.consumed:
		var visual = inventory_grid.item_visual(eaten.id)
		if is_instance_valid(visual):
			_rattle(visual, which)
			_fly_in(visual, lands_on)
		which += 1

	for kept in made.kept:
		var visual = inventory_grid.item_visual(kept.id)
		if is_instance_valid(visual):
			_rattle(visual, which)
			_flare(visual)
		which += 1

	# The flash belongs to the moment they arrive, not the moment they set off.
	var flash := create_tween()
	flash.tween_interval(MERGE_SHAKE + MERGE_FLY)
	flash.tween_callback(_flash_at.bind(
		inventory_grid.get_global_transform() * lands_on))


func _rattle(visual: Control, which: int) -> void:
	"""Shake an item where it stands, harder as it goes.

	Each one on its own path. Four items shaken the same way read as one block
	sliding about; shaken differently they read as four things being pulled at.
	"""
	var home := visual.position
	visual.pivot_offset = visual.size / 2.0

	var tween := create_tween()
	var steps := 12
	for step in range(steps):
		var how_far := 1.0 + 5.5 * float(step) / steps
		# Turning by a fraction of a full circle each step, so the item never
		# repeats a direction and never falls into a straight wobble.
		var away := Vector2(how_far, 0).rotated(which * 1.7 + step * 2.39996)
		tween.tween_property(visual, "position", home + away,
			MERGE_SHAKE / steps).set_trans(Tween.TRANS_SINE)
	tween.tween_property(visual, "position", home, 0.02)


func _fly_in(visual: Control, lands_on: Vector2) -> void:
	"""Off to the middle, once the shaking has done its work."""
	var tween := create_tween().set_parallel(true)
	tween.tween_property(visual, "position", lands_on - visual.size / 2.0,
		MERGE_FLY).set_delay(MERGE_SHAKE) \
		.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_IN)
	tween.tween_property(visual, "scale", Vector2(0.35, 0.35), MERGE_FLY) \
		.set_delay(MERGE_SHAKE).set_trans(Tween.TRANS_CUBIC)
	tween.tween_property(visual, "modulate", Color(2.2, 2.0, 1.6, 1.0),
		MERGE_FLY * 0.7).set_delay(MERGE_SHAKE)
	# Gone as the flash covers them, rather than left underneath it.
	tween.tween_property(visual, "modulate:a", 0.0, 0.08) \
		.set_delay(MERGE_SHAKE + MERGE_FLY - 0.04)


func _flare(visual: Control) -> void:
	"""One bright pulse on a catalyst, at the moment the others go."""
	var tween := create_tween()
	tween.tween_interval(MERGE_SHAKE + MERGE_FLY - 0.1)
	tween.tween_property(visual, "modulate", Color(1.9, 1.6, 1.1), 0.14)
	tween.tween_property(visual, "modulate", Color.WHITE, 0.35)


func _welcome_the_result(made: APITypes.Combination) -> void:
	"""What they became stands up, named, and the rack is struck around it.

	A result too big for the squares it was made on goes to the chest, so there
	may be nothing on the rack to stand up. The name and the rings still happen
	where the items met: that is where the player is looking.
	"""
	var lands_on := inventory_grid.get_global_transform() * _where_the_result_lands(made)
	var visual = inventory_grid.item_visual(made.made_id)
	if is_instance_valid(visual):
		lands_on = visual.get_global_rect().get_center()

	# Said whether or not there is an animation to say it over. The name is
	# not decoration: two items have become a third the player has never held,
	# and the thing they were watching a moment ago was the other two.
	if combining_overlay != null:
		combining_overlay.announce(
			GameStateManager.combining.name_of(made.made), lands_on)

	if not Presentation.request("item_arrived", {"made": made.made}):
		return

	if is_instance_valid(visual):
		visual.pivot_offset = visual.size / 2.0
		visual.scale = Vector2(0.25, 0.25)
		visual.modulate = Color(2.4, 2.2, 1.8, 0.0)
		var tween := create_tween().set_parallel(true)
		# Overshooting, so it lands rather than fades up.
		tween.tween_property(visual, "scale", Vector2.ONE, MERGE_ARRIVE) \
			.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
		tween.tween_property(visual, "modulate:a", 1.0, MERGE_ARRIVE * 0.25)
		tween.tween_property(visual, "modulate", Color.WHITE, MERGE_ARRIVE) \
			.set_delay(MERGE_ARRIVE * 0.25)

	if combining_overlay != null:
		combining_overlay.burst_at(lands_on)


func _where_the_result_lands(made: APITypes.Combination) -> Vector2:
	"""The middle of the squares the ingredients were standing on.

	Those squares, whether or not the result fits in them: a result too big for
	them goes to the chest, and the merge still happened where they stood.
	"""
	if made.freed.is_empty():
		return inventory_grid.size / 2.0

	var middle := Vector2.ZERO
	for square in made.freed:
		middle += inventory_grid.grid_to_pixel(square)
	middle /= made.freed.size()
	var cell := inventory_grid.cell_size / 2.0
	return middle + Vector2(cell, cell)


func _flash_at(spot_on_screen: Vector2) -> void:
	"""A bloom of light where the ingredients met.

	Drawn by the overlay, which is already above the rack, the shelf and the
	chest. A node of its own would have to be put somewhere, and a result that
	flies to the chest merges on the rack and lands off it.
	"""
	if combining_overlay != null:
		combining_overlay.flash_at(spot_on_screen)


# ============= What an item reaches into (GDD 4.3) =============
#
# The same item the arcs come from: whatever is under the pointer or in hand.
# Where the zone is drawn from differs, though. An item being moved draws its
# zone around the square under the pointer, because the question is where to
# put it; an item standing still draws it around where it stands.


func refresh_aura(pointer := Vector2.INF) -> void:
	"""Draw the zone of whatever the player is reaching for.

	Takes where the pointer is, so what the screen would draw can be asked
	about without a mouse. Told nothing, it reads the pointer itself.
	"""
	if aura_overlay == null:
		return

	var where := get_global_mouse_position() if pointer == Vector2.INF else pointer
	var reaching := combining_source(where)
	if reaching.is_empty():
		aura_overlay.no_zones()
		_light_up([])
		return

	var item: APITypes.Item = reaching["item"]
	var at := _aura_square(item, where)
	if at.x < 0 or at.y < 0:
		# Not over the board, so there are no squares to draw on.
		aura_overlay.no_zones()
		_light_up([])
		return

	var standing := _standing_on()
	var star := Aura.markers(_zone_at(item.turned_star(), at), standing,
		item.aura.get("star", []))
	var diamond := Aura.markers(_zone_at(item.turned_diamond(), at), standing,
		item.aura.get("diamond", []))
	aura_overlay.show_zones(star, diamond)
	_light_up(Aura.lit_by(star) + Aura.lit_by(diamond))


func _aura_square(item: APITypes.Item, pointer: Vector2) -> Vector2i:
	"""Which square the zone is drawn around.

	Under the pointer while the item is being moved: that is the whole question
	being asked, and the answer has to follow the hand. Where it stands
	otherwise.
	"""
	if _something_is_being_moved():
		# The square the item itself would land on. A zone drawn around the
		# pointer rather than around the item reaches out of the wrong place
		# for anything more than one square across.
		if inventory_grid.dragging_object != null:
			# Dragged off the grid, so it is held by the square it was picked
			# up on rather than by the middle of its artwork.
			return inventory_grid.square_held_over(
				pointer, inventory_grid.grab_cell)
		return square_carried_to(item, pointer)

	# Where the board says it is, not where the item says it is. An item put
	# in the chest is still the object that was on the grid, remembering the
	# square it used to stand on, and it would draw its zone back there.
	var visual = inventory_grid.item_visual(item.id)
	if is_instance_valid(visual):
		return visual.where()

	# On a shelf or lying in the chest, so it is nowhere on the board.
	return Vector2i(-1, -1)


func _something_is_being_moved() -> bool:
	"""The same question carrying_something() answers, asked from the zone.

	It was the same four conditions written out again, two thousand lines
	away. Two lists that have to agree is what let the shop drag go unturnable
	the first time round.
	"""
	return carrying_something()


func _zone_at(offsets: Array[Vector2i], at: Vector2i) -> Array[Vector2i]:
	"""A zone's offsets, put down on the board.

	The offsets are already turned and already have the item's own squares
	taken out of them, because an aura never reaches the item projecting it.
	"""
	var squares: Array[Vector2i] = []
	for offset in offsets:
		squares.append(at + offset)
	return squares


func _standing_on() -> Callable:
	"""What covers a square, or nothing.

	An item being dragged is not on the board while it is in the air -- the
	grid clears its squares when the drag starts -- so it never counts itself,
	and the squares it came from read as empty while the player is deciding.
	"""
	return func(square: Vector2i):
		var visual = inventory_grid.standing_on(square)
		return visual.item_data if visual != null else null


## How much brighter an item is drawn while an aura is acting on it. Slight:
## it is a second way of saying what the filled marker over it already says,
## and the item still has to look like itself.
const LIT_BY_AN_AURA := Color(1.32, 1.32, 1.32)

# The items lit this way, by id, so they can be put back as the pointer moves.
var _lit: Dictionary = {}


func _light_up(ids: Array) -> void:
	"""Brighten the items an aura is acting on, and dim the rest back.

	The marker says which square. This says which item, which is the thing the
	player actually cares about when the zone covers half a board.
	"""
	var wanted := {}
	for id in ids:
		wanted[id] = true

	for id in _lit.keys():
		if not wanted.has(id):
			var visual = inventory_grid.item_visual(id)
			if is_instance_valid(visual):
				visual.modulate = Color.WHITE
	for id in wanted:
		if not _lit.has(id):
			var visual = inventory_grid.item_visual(id)
			if is_instance_valid(visual):
				visual.modulate = LIT_BY_AN_AURA
	_lit = wanted


func lit_by_an_aura() -> Array:
	"""Which items are lit, for a test to read."""
	return _lit.keys()


## How much an item swells when an aura starts acting on it, and for how long.
## Slighter than the marker's answer on purpose: the marker is the answer, and
## this is the item nodding.
const POP := 1.12
const POP_OUT := 0.10
const POP_BACK := 0.16


func pop_what_took_effect(item_id: String) -> void:
	"""An item has landed. Every aura it has just set going says so.

	The item that pops is the one projecting the aura, because that is the one
	something has just happened to: an item dropped into a zone is not changed
	by landing there, and the item whose zone it is has just gained a Star
	something. It works from both ends of the same event -- a thing put into a
	zone, and a zone put over a thing -- because the player may have been
	watching either.
	"""
	for id in _took_effect(item_id):
		_pop(id)


func _took_effect(item_id: String) -> Array[String]:
	"""The items whose auras this placement has set going, by id."""
	var set_going: Array[String] = []
	var landed = inventory_grid.item_visual(item_id)
	if not is_instance_valid(landed):
		return set_going

	# A zone put over something: the item that was moved is the projector.
	if not _aura_reaches(landed).is_empty():
		set_going.append(item_id)

	# Something put into a zone: the projector is whoever owns that zone.
	for visual in inventory_grid.items:
		if visual != landed and _aura_reaches(visual).has(item_id):
			set_going.append(visual.item_data.id)
	return set_going


func _aura_reaches(visual: Control) -> Array[String]:
	"""The items this one's zones are acting on, where it stands."""
	var item: APITypes.Item = visual.item_data
	var lit: Array[String] = []
	if item.aura.is_empty():
		return lit

	var at: Vector2i = visual.where()
	var standing := _standing_on()
	lit.append_array(Aura.lit_by(Aura.markers(
		_zone_at(item.turned_star(), at), standing, item.aura.get("star", []))))
	lit.append_array(Aura.lit_by(Aura.markers(
		_zone_at(item.turned_diamond(), at), standing, item.aura.get("diamond", []))))
	return lit


func _pop(item_id: String) -> void:
	"""One small swell and back, on the item itself."""
	var visual = inventory_grid.item_visual(item_id)
	if not is_instance_valid(visual):
		return
	if not Presentation.request("aura_took_effect", {"item": item_id}):
		return

	visual.pivot_offset = visual.size / 2.0
	var tween := create_tween()
	tween.tween_property(visual, "scale", Vector2(POP, POP), POP_OUT) \
		.set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	tween.tween_property(visual, "scale", Vector2.ONE, POP_BACK) \
		.set_trans(Tween.TRANS_QUAD)


# ---------------------------------------------------------------- skins

func _wear_skin() -> void:
	Skins.wear(get_node_or_null("PlayerCharacter"), "shop")
