extends GutTest
# Everything the player can pick up, wherever they picked it up from.
#
# Three times now the same fault has landed in different clothes: the mark that
# says where a thing will go was drawn somewhere the thing was not. A spear
# three squares from its mark, a carried item half a cell off the pointer, an
# item that leapt a length away when it was turned. Each was found by hand,
# fixed by hand, and covered by a test naming the case that broke.
#
# This file names no cases. It states the invariant --
#
#     THE MARK IS DRAWN OVER THE THING IT IS ABOUT
#
# -- and sweeps it across every footprint the catalogue holds, every rotation,
# and every way of carrying something. New item shapes are covered the day they
# are added, because the shapes are read from the catalogue rather than listed
# here.
#
#     server/tests/fixtures/footprints.json   the shapes, from the catalogue
#     tools/dump_footprints.py                what writes them down
#     server/tests/test_items.py              fails when the two disagree

const APITypes = preload("res://scripts/api_types.gd")
const InventoryGrid = preload("res://scripts/inventory_grid.gd")
const ItemVisual = preload("res://scripts/item_visual.gd")
const StorageBin = preload("res://scripts/storage_bin.gd")

## Every shape the catalogue holds, written down by the server.
const FOOTPRINTS_PATH := "../server/tests/fixtures/footprints.json"
## Where the list of ways to carry something is kept in the code itself.
const UNIFIED_PATH := "scripts/unified_grid_ui.gd"

var ui_scene = preload("res://scenes/UnifiedGridUI.tscn")
var ui


func before_each():
	GameStateManager.start_new_game()
	GameStateManager.gold = 99
	GameStateManager.save_inventory_state([], [
		TestHelpers.container_data({"id": "a", "position": [0, 0]}),
		TestHelpers.container_data({"id": "b", "position": [2, 0]}),
		TestHelpers.container_data({"id": "c", "position": [4, 0]}),
		TestHelpers.container_data({"id": "d", "position": [0, 2]}),
		TestHelpers.container_data({"id": "e", "position": [2, 2]}),
		TestHelpers.container_data({"id": "f", "position": [4, 2]}),
	])
	ui = ui_scene.instantiate()
	add_child(ui)
	await get_tree().process_frame


func after_each():
	if ui:
		ui.queue_free()
		ui = null
	await get_tree().process_frame


# ============ What the catalogue holds ============

func _footprints() -> Array:
	"""Every distinct shape in the catalogue, read off the shared fixture."""
	var path := ProjectSettings.globalize_path("res://").path_join(FOOTPRINTS_PATH)
	var file := FileAccess.open(path, FileAccess.READ)
	assert_not_null(file, "Should be able to read %s" % FOOTPRINTS_PATH)
	if file == null:
		return []
	var written = JSON.parse_string(file.get_as_text())
	file.close()
	assert_true(written is Array and written.size() > 0,
		"%s should hold a list of shapes" % FOOTPRINTS_PATH)
	return written if written is Array else []


func _an_item(squares: Array, facing: int = 0) -> Resource:
	return TestHelpers.item({
		"id": "carried", "shape": squares, "rotation": facing})


# ============ The invariant ============

func _the_mark_is_over(artwork: Control, mark: Control, what: String) -> void:
	"""The one question. Everything in this file is a way of asking it.

	Within half a square, and half a square exactly is allowed: a thing carried
	by the middle of an even-sided shape sits on the boundary between two
	squares, and the mark has to pick one of them. The pixel of slack past that
	is for the float, not for the rule. A whole square out is the fault this
	file is here for.
	"""
	assert_true(mark.visible, "%s: the mark should be drawn at all" % what)
	if not mark.visible:
		return
	var slack: float = (ui.inventory_grid.cell_size
		+ ui.inventory_grid.cell_spacing) / 2.0 + 1.0
	var drawn: Vector2 = artwork.global_position
	var marked: Vector2 = mark.global_position

	assert_almost_eq(marked.x, drawn.x, slack,
		"%s: the mark is at x %.0f and the artwork at x %.0f" % [what, marked.x, drawn.x])
	assert_almost_eq(marked.y, drawn.y, slack,
		"%s: the mark is at y %.0f and the artwork at y %.0f" % [what, marked.y, drawn.y])
	assert_almost_eq(mark.size.x, artwork.size.x, 1.0,
		"%s: the mark is %.0f wide and the artwork %.0f" % [what, mark.size.x, artwork.size.x])
	assert_almost_eq(mark.size.y, artwork.size.y, 1.0,
		"%s: the mark is %.0f tall and the artwork %.0f" % [what, mark.size.y, artwork.size.y])


func _the_pointer_holds_it(artwork: Control, pointer: Vector2, what: String) -> void:
	"""The other half of the invariant: the thing is under your hand.

	"The mark is over the artwork" is not enough on its own. Move both of them
	the same distance and they still agree with each other while sitting a cell
	away from the pointer -- which is the fault a player reported as "it does
	not rotate around the held point". Found by breaking the fix and watching
	this file not notice.

	Carried by the middle, so the middle is what the pointer is on.
	"""
	var middle: Vector2 = artwork.global_position + artwork.size / 2.0
	assert_almost_eq(middle.x, pointer.x, 1.0,
		"%s: the artwork's middle is at x %.0f and the pointer at x %.0f"
			% [what, middle.x, pointer.x])
	assert_almost_eq(middle.y, pointer.y, 1.0,
		"%s: the artwork's middle is at y %.0f and the pointer at y %.0f"
			% [what, middle.y, pointer.y])


func _the_pointer_is_on_the_square_in_hand(
		artwork: Control, held: Vector2i, pointer: Vector2, what: String) -> void:
	"""Dragged off the grid, the hand is on the square it took hold of.

	Not the middle: a spear picked up by its tip is held by its tip, and stays
	held by its tip however it is turned.
	"""
	var grid = ui.inventory_grid
	var step: float = grid.cell_size + grid.cell_spacing
	var square := Rect2(
		artwork.global_position + Vector2(held) * step,
		Vector2(grid.cell_size, grid.cell_size))

	assert_true(square.grow(1.0).has_point(pointer),
		"%s: the square in hand is at %s and the pointer at %s"
			% [what, square.position, pointer])


func _a_bare_rack() -> void:
	"""Six racks and nothing on them, drawn straight onto the grid.

	Reloaded between shapes rather than cleared: clear_all() takes the racks
	with it, and a shape with nowhere to stand is not a test of anything.
	"""
	var servers := []
	for at in [[0, 0], [2, 0], [4, 0], [0, 2], [2, 2], [4, 2]]:
		servers.append(TestHelpers.container_data(
			{"id": "rack_%d_%d" % [at[0], at[1]], "position": at}))
	ui.inventory_grid.load_inventory_state(
		APITypes.InventoryState.new({"inventory_grid": [], "server_containers": servers}))


func _middle_of(square: Vector2i) -> Vector2:
	var grid = ui.inventory_grid
	return grid.global_position + grid.grid_to_pixel(square) \
		+ Vector2(grid.cell_size, grid.cell_size) / 2.0


# ============ Carried, every way there is ============
#
# One test per way of carrying something. The list they cover is the one
# carrying_something() keeps, and the last test in this file fails if a fifth
# way is added without a sweep of its own.

func test_an_item_in_hand_is_marked_where_it_is_drawn():
	for entry in _footprints():
		for facing in [0, 90, 180, 270]:
			var item := _an_item(entry["squares"], facing)
			ui.hold(item, _middle_of(Vector2i(2, 1)))
			await get_tree().process_frame

			ui.follow_pointer(_middle_of(Vector2i(2, 1)))

			var what := "%s facing %d, in hand" % [entry["example"], facing]
			_the_mark_is_over(ui.held_visual, ui.inventory_grid.hover_preview, what)
			_the_pointer_holds_it(ui.held_visual, _middle_of(Vector2i(2, 1)), what)
			ui.release_hand()


func test_an_item_off_the_shelf_is_marked_where_it_is_drawn():
	for entry in _footprints():
		for facing in [0, 90, 180, 270]:
			var item := _an_item(entry["squares"], facing)
			ui.dragging_shop_item = Panel.new()
			add_child_autofree(ui.dragging_shop_item)
			ui.dragging_shop_data = item
			ui.drag_preview = ItemVisual.new()
			add_child_autofree(ui.drag_preview)
			ui.drag_preview.setup(item, ui.inventory_grid.cell_size,
				ui.inventory_grid.cell_spacing)
			var pointer := _middle_of(Vector2i(2, 1))

			ui._hang_the_shop_drag(pointer)
			ui.mark_where_the_shop_item_would_land(pointer)

			var what := "%s facing %d, off the shelf" % [entry["example"], facing]
			_the_mark_is_over(ui.drag_preview, ui.inventory_grid.hover_preview, what)
			_the_pointer_holds_it(ui.drag_preview, pointer, what)
			ui.dragging_shop_data = null
			ui.dragging_shop_item = null
			ui.drag_preview = null


func test_an_item_out_of_the_chest_is_marked_where_it_is_drawn():
	var bin: StorageBin = ui.storage_bin
	assert_not_null(bin, "setup: the chest is on the screen")
	for entry in _footprints():
		for facing in [0, 90, 180, 270]:
			var item := _an_item(entry["squares"], facing)
			bin.show_items([item])
			await get_tree().process_frame
			bin.pick_up(bin.item_at(bin.global_position + bin.where_is("carried")),
				bin.global_position + Vector2(20, 20))
			var pointer := _middle_of(Vector2i(2, 1))

			bin._follow(pointer)

			var what := "%s facing %d, out of the chest" % [entry["example"], facing]
			_the_mark_is_over(bin.dragged_visual(),
				ui.inventory_grid.hover_preview, what)
			_the_pointer_holds_it(bin.dragged_visual(), pointer, what)
			bin.release_at(bin.global_position + Vector2(20, 20))
			await get_tree().process_frame


func test_an_item_dragged_on_the_grid_is_marked_where_it_is_drawn():
	var grid: InventoryGrid = ui.inventory_grid
	for entry in _footprints():
		_a_bare_rack()
		await get_tree().process_frame
		var squares: Array = entry["squares"]
		var placed := TestHelpers.placed_item({
			"id": "dragged", "position": [0, 0], "shape": squares})
		grid.place_shop_item(placed, Vector2i(0, 0))
		await get_tree().process_frame
		var visual: Control = grid.item_visual("dragged")
		assert_not_null(visual, "setup: %s is on the rack" % entry["example"])
		if visual == null:
			continue

		# Held by each of its own squares in turn, and turned all the way round
		# from each. The square in hand is the thing a turn has to keep hold of.
		for held in APITypes.squares(squares):
			grid._start_drag(visual, grid.global_position
				+ grid.grid_to_pixel(held)
				+ Vector2(grid.cell_size, grid.cell_size) / 2.0)
			for quarter in range(4):
				# Turned first, because a turn changes which square is in hand
				# and so where the pointer has to be to keep the item on the
				# board at all. Aimed to put its corner on the top left square,
				# where every shape in the game fits.
				grid.turn_dragged(1, _middle_of(grid.grab_cell))
				var pointer := _middle_of(grid.grab_cell)
				grid.carry_to(pointer)
				var what := "%s held by %s, %d turns in, dragged on the rack" \
					% [entry["example"], held, quarter + 1]
				_the_mark_is_over(grid.dragging, grid.hover_preview, what)
				_the_pointer_is_on_the_square_in_hand(
					grid.dragging, grid.grab_cell, pointer, what)
			grid._end_drag(grid.global_position - Vector2(500, 500))
			await get_tree().process_frame


func test_a_rack_dragged_on_the_grid_is_marked_where_it_is_drawn():
	"""A rack is carried by one of its own squares too. It was marked at the
	pointer's square while its artwork hung from wherever it was grabbed, so a
	two by two picked up by its far corner was drawn in one place, marked in
	another, and dropped where the mark was."""
	var grid: InventoryGrid = ui.inventory_grid
	for shape in [[[0, 0]], [[0, 0], [1, 0]], [[0, 0], [0, 1]],
			[[0, 0], [1, 0], [0, 1], [1, 1]], [[0, 0], [0, 1], [0, 2]]]:
		grid.load_inventory_state(APITypes.InventoryState.new({
			"inventory_grid": [],
			"server_containers": [TestHelpers.container_data(
				{"id": "rack", "position": [0, 0], "shape": shape})],
		}))
		await get_tree().process_frame
		var placed = grid.containers[0]

		for held in APITypes.squares(shape):
			grid._start_container_drag(placed, grid.global_position
				+ grid.grid_to_pixel(held)
				+ Vector2(grid.cell_size, grid.cell_size) / 2.0)
			var pointer := _middle_of(Vector2i(2, 1) + held)
			grid.carry_to(pointer)

			var what := "a rack of %s held by %s" % [shape, held]
			_the_mark_is_over(placed, grid.hover_preview, what)
			_the_pointer_is_on_the_square_in_hand(
				placed, grid.grab_cell, pointer, what)
			grid.drop_container_at(grid.global_position - Vector2(500, 500))
			await get_tree().process_frame


# ============ The sweep keeps up with the code ============

func test_every_way_of_carrying_something_is_swept():
	"""UnifiedGridUI.WAYS_TO_CARRY is the list of them. Add a way to it and
	this fails until the sweep above has a test for that way too, which is the
	only thing keeping this file honest as the game grows."""
	var swept := 0
	for method in get_method_list():
		if str(method["name"]).ends_with("_is_marked_where_it_is_drawn"):
			swept += 1

	assert_eq(swept, ui.WAYS_TO_CARRY.size(),
		("There are %d ways to carry something and this file sweeps %d of "
		+ "them. A way nobody sweeps is a way the mark can drift away from "
		+ "the artwork without anything noticing: %s")
			% [ui.WAYS_TO_CARRY.size(), swept, ui.WAYS_TO_CARRY])


# ============ Where a passenger lands ============
#
# Both sides carry an item round with a turning rack, and they have to give
# the same answer. They did not: this side mapped the item's corner square
# through the turn, which is right for a single square and wrong for anything
# longer, because the corner of a turned body is not the turned corner. A
# two-square item on a two-by-two rack came out one square off, and at the edge
# of the board that put it outside the rack it was riding.
#
# So the answers are written down once and both sides are held to them, the
# same way the direction of a turn is.
#
#     server/tests/fixtures/carried_round.json   what the server makes of it
#     tools/dump_carried_round.py                what writes it down

const CARRIED_ROUND_PATH := "../server/tests/fixtures/carried_round.json"


func _carried_round() -> Array:
	var path := ProjectSettings.globalize_path("res://").path_join(CARRIED_ROUND_PATH)
	var file := FileAccess.open(path, FileAccess.READ)
	assert_not_null(file, "Should be able to read %s" % CARRIED_ROUND_PATH)
	if file == null:
		return []
	var written = JSON.parse_string(file.get_as_text())
	file.close()
	assert_true(written is Array and written.size() > 0,
		"%s should hold a list of cases" % CARRIED_ROUND_PATH)
	return written if written is Array else []


func test_this_side_lands_a_passenger_where_the_server_does():
	for case in _carried_round():
		var tray := APITypes.squares(case["tray"])
		var sits_on := APITypes.squares([case["sits_on"]])[0]
		var covers: Array[Vector2i] = []
		for offset in APITypes.squares(case["rider"]):
			covers.append(sits_on + offset)

		for facing in case["lands_on"]:
			var body := APITypes.Turned.new(tray, int(facing))
			var landed := body.corner_of(covers)
			var expected := APITypes.squares([case["lands_on"][facing]])[0]

			assert_eq(landed, expected,
				("%s turned %s: this side says %s and the file says %s. "
				+ "Run `python tools/dump_carried_round.py` if that is meant.")
					% [case["name"], facing, landed, expected])


func test_a_passenger_never_leaves_the_tray_it_rides():
	"""The property the numbers are there to keep. A turn maps a tray's squares
	onto themselves, so nothing sitting wholly on one can fall off it."""
	for case in _carried_round():
		var tray := APITypes.squares(case["tray"])
		var rider := APITypes.squares(case["rider"])
		var sits_on := APITypes.squares([case["sits_on"]])[0]
		var covers: Array[Vector2i] = []
		for offset in rider:
			covers.append(sits_on + offset)

		for facing in case["lands_on"]:
			var turn := int(facing)
			var corner := APITypes.Turned.new(tray, turn).corner_of(covers)
			var turned_tray := {}
			for square in APITypes.turn(tray, turn):
				turned_tray[square] = true

			for offset in APITypes.turn(rider, turn):
				assert_true(turned_tray.has(corner + offset),
					"%s turned %s puts %s off the tray"
						% [case["name"], facing, corner + offset])
