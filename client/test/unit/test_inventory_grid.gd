extends GutTest
# Tests for inventory_grid.gd, the grid that holds server containers and the
# items placed on them.
#
# These check grid rules: where an item may go, what a container makes
# available, and that loading a state and reading it back gives the same thing.
# They are written against behaviour rather than field names, so a change to the
# fields leaves them standing.

const InventoryGridScript = preload("res://scripts/inventory_grid.gd")
const APITypes = preload("res://scripts/api_types.gd")

const WIDTH := 9
const HEIGHT := 7

var grid


func before_each():
	grid = InventoryGridScript.new()
	add_child(grid)
	grid.configure(WIDTH, HEIGHT, 45.0, 1.0)
	await get_tree().process_frame


func after_each():
	if is_instance_valid(grid):
		remove_child(grid)
		grid.queue_free()
	grid = null
	await get_tree().process_frame


func _item(overrides: Dictionary = {}) -> Resource:
	return TestHelpers.placed_item(overrides)


func _container(overrides: Dictionary = {}) -> Resource:
	return TestHelpers.container(overrides)


func _state(items: Array, containers: Array) -> APITypes.InventoryState:
	# The grid loads plain data, the same as it arrives from the server.
	var item_data = []
	for item in items:
		item_data.append(item.to_dict())
	var container_data = []
	for container in containers:
		container_data.append(container.to_dict())
	return APITypes.InventoryState.new(
		{"items": item_data, "servers": container_data})


func _load_default_containers() -> void:
	# The three starting containers, 2x2 each at (2,3), (4,3) and (6,3)
	grid.load_inventory_state(_state([], [
		_container({"id": "container_a", "position": [2, 3]}),
		_container({"id": "container_b", "position": [4, 3]}),
		_container({"id": "container_c", "position": [6, 3]})
	]))


# ============ Configuration ============

func test_configure_sizes_the_grid_and_its_arrays():
	assert_eq(grid.grid_width, WIDTH, "Width should be what it was configured with")
	assert_eq(grid.grid_height, HEIGHT, "Height should be what it was configured with")
	assert_eq(grid.active_grid.size(), HEIGHT, "There should be one row per grid row")
	assert_eq(grid.active_grid[0].size(), WIDTH, "There should be one cell per grid column")
	assert_eq(grid.item_grid.size(), HEIGHT, "The item grid should match the grid size")


func test_a_new_grid_has_nothing_on_it():
	for y in range(HEIGHT):
		for x in range(WIDTH):
			assert_false(grid.active_grid[y][x], "No cell is usable before a container is placed")
			assert_null(grid.item_grid[y][x], "No cell holds an item before one is placed")


# ============ Coordinates ============

func test_pixel_and_grid_coordinates_round_trip():
	for pos in [Vector2i(0, 0), Vector2i(4, 3), Vector2i(WIDTH - 1, HEIGHT - 1)]:
		var pixel = grid.grid_to_pixel(pos)
		assert_eq(grid.pixel_to_grid(pixel), pos,
			"Converting %s to pixels and back should give the same cell" % pos)


func test_negative_pixels_are_off_the_grid():
	assert_eq(grid.pixel_to_grid(Vector2(-10, -10)), Vector2i(-1, -1),
		"A position left of or above the grid is not a cell")


# ============ Containers decide what is usable ============

func test_loading_a_container_makes_its_cells_usable():
	grid.load_inventory_state(_state([], [_container({"position": [2, 3]})]))

	for y in range(3, 5):
		for x in range(2, 4):
			assert_true(grid.active_grid[y][x], "(%d,%d) is inside the container" % [x, y])


func test_cells_outside_a_container_stay_unusable():
	grid.load_inventory_state(_state([], [_container({"position": [2, 3]})]))

	assert_false(grid.active_grid[0][0], "The top-left corner is bare floor")
	assert_false(grid.active_grid[3][1], "The cell left of the container is bare floor")
	assert_false(grid.active_grid[5][2], "The cell below the container is bare floor")


func test_three_containers_make_twelve_cells_usable():
	_load_default_containers()

	var usable = 0
	for y in range(HEIGHT):
		for x in range(WIDTH):
			if grid.active_grid[y][x]:
				usable += 1

	assert_eq(usable, 12, "Three 2x2 containers should make 12 cells usable")


func test_loading_a_state_replaces_the_previous_one():
	_load_default_containers()
	assert_eq(grid.containers.size(), 3, "Setup: three containers loaded")

	grid.load_inventory_state(_state([], [_container({"position": [2, 3]})]))

	assert_eq(grid.containers.size(), 1, "Loading a state should replace, not add to, the old one")


# ============ Placement rules ============

func test_an_item_may_only_go_on_a_container():
	# A cell is unusable until a container makes it available. That is the core
	# inventory rule.
	_load_default_containers()

	assert_true(grid.can_place_item(_item(), Vector2i(2, 3)), "A container cell should accept an item")
	assert_true(grid.can_place_item(_item(), Vector2i(5, 4)), "Any container cell should accept an item")
	assert_false(grid.can_place_item(_item(), Vector2i(0, 0)), "Bare floor should not accept an item")
	assert_false(grid.can_place_item(_item(), Vector2i(4, 6)), "Bare floor below a container is still bare")


func test_an_item_cannot_go_outside_the_grid():
	_load_default_containers()

	assert_false(grid.can_place_item(_item(), Vector2i(-1, 3)), "Left of the grid is not placeable")
	assert_false(grid.can_place_item(_item(), Vector2i(3, -1)), "Above the grid is not placeable")
	assert_false(grid.can_place_item(_item(), Vector2i(WIDTH, 3)), "Right of the grid is not placeable")
	assert_false(grid.can_place_item(_item(), Vector2i(3, HEIGHT)), "Below the grid is not placeable")


func test_a_multi_square_item_needs_every_square_on_a_container():
	_load_default_containers()
	var wide = _item({"shape": [[0, 0], [1, 0]]})

	assert_true(grid.can_place_item(wide, Vector2i(2, 3)),
		"Both squares sit on container A, so it fits")
	assert_false(grid.can_place_item(wide, Vector2i(7, 3)),
		"The second square would land on bare floor past container C, so it does not fit")


func test_an_item_may_straddle_two_touching_containers():
	# The three starting containers are adjacent, covering x 2-3, 4-5 and 6-7,
	# so a two-wide item at x=3 sits half on container A and half on B.
	_load_default_containers()
	var wide = _item({"shape": [[0, 0], [1, 0]]})

	assert_true(grid.can_place_item(wide, Vector2i(3, 3)),
		"Touching containers form one usable surface")


func test_a_multi_square_item_cannot_hang_off_the_edge():
	grid.load_inventory_state(_state([], [_container({"position": [7, 3]})]))
	var wide = _item({"shape": [[0, 0], [1, 0]]})

	assert_false(grid.can_place_item(wide, Vector2i(8, 3)),
		"The second square would be outside the grid")


func test_items_cannot_overlap():
	_load_default_containers()
	grid.place_shop_item(_item({"id": "first"}), Vector2i(2, 3))

	assert_false(grid.can_place_item(_item({"id": "second"}), Vector2i(2, 3)),
		"An occupied cell should not accept a second item")
	assert_true(grid.can_place_item(_item({"id": "second"}), Vector2i(3, 3)),
		"A free cell on the same container should still accept an item")


# ============ Placing and reading back ============

func test_placing_an_item_puts_it_on_the_grid():
	_load_default_containers()

	var placed = grid.place_shop_item(_item({"id": "placed"}), Vector2i(4, 3))

	assert_true(placed, "Placing on a free container cell should succeed")
	assert_eq(grid.items.size(), 1, "The item should be on the grid")
	assert_not_null(grid.item_grid[3][4], "The cell should now be occupied")


func test_placing_on_bare_floor_is_refused():
	_load_default_containers()

	var placed = grid.place_shop_item(_item(), Vector2i(0, 0))

	assert_false(placed, "Placing on bare floor should be refused")
	assert_eq(grid.items.size(), 0, "Nothing should be added to the grid")


func test_state_read_back_matches_what_was_loaded():
	grid.load_inventory_state(_state(
		[_item({"id": "a", "position": [2, 3]}), _item({"id": "b", "position": [4, 3]})],
		[_container({"id": "c1", "position": [2, 3]}), _container({"id": "c2", "position": [4, 3]})]
	))

	var state = grid.get_inventory_state()

	assert_eq(state["items"].size(), 2, "Both items should come back")
	assert_eq(state["servers"].size(), 2, "Both containers should come back")


func test_state_survives_a_save_and_reload():
	# The game saves this state between screens and reloads it, every round.
	grid.load_inventory_state(_state(
		[_item({"id": "keeper", "position": [6, 3]})],
		[_container({"id": "c3", "position": [6, 3]})]
	))
	var saved = grid.get_inventory_state()

	grid.load_inventory_state(APITypes.InventoryState.new(saved))
	var reloaded = grid.get_inventory_state()

	assert_eq(reloaded["items"].size(), 1, "The item should survive a save and reload")
	assert_eq(reloaded["servers"].size(), 1, "The container should survive a save and reload")


func test_clear_all_empties_the_grid():
	_load_default_containers()
	grid.place_shop_item(_item(), Vector2i(2, 3))

	grid.clear_all()

	assert_eq(grid.items.size(), 0, "Clearing should remove the items")
	assert_eq(grid.containers.size(), 0, "Clearing should remove the containers")
	assert_false(grid.active_grid[3][2], "Clearing should make every cell unusable again")


# ============ Tooltips ============
#
# A container and the item standing on it must never both describe themselves
# at once. Godot hands the hover to one control, the last one in the child
# order whose rectangle holds the mouse, so the rule comes down to two things:
# a container has to be hoverable at all, and items have to come after
# containers in that order.

func test_a_container_describes_itself():
	_load_default_containers()

	var drawn = grid.containers[0].visual
	assert_true(drawn.enable_tooltip, "A container should have a tooltip")
	assert_ne(drawn.mouse_filter, Control.MOUSE_FILTER_IGNORE,
		"A container that ignores the mouse can never be hovered")


func test_an_item_is_hovered_before_the_container_it_stands_on():
	# The item is the later sibling, so it takes the hover for the squares it
	# covers and the container keeps the squares nothing stands on.
	_load_default_containers()
	grid.place_shop_item(_item(), Vector2i(2, 3))

	var container_order = grid.get_children().find(grid.containers[0].visual)
	var item_order = grid.get_children().find(grid.items[0])

	assert_gt(item_order, container_order,
		"An item should come after the container it stands on")


func test_dragging_an_item_keeps_it_above_the_containers():
	# _start_drag moves the item to the end of the child order. It must not be
	# able to land behind a container.
	_load_default_containers()
	grid.place_shop_item(_item(), Vector2i(2, 3))

	grid._start_drag(grid.items[0])

	var container_order = grid.get_children().find(grid.containers[0].visual)
	var item_order = grid.get_children().find(grid.items[0])
	assert_gt(item_order, container_order,
		"A dragged item should still be above the containers")


func test_a_read_only_container_still_describes_itself():
	# The battle screens are read-only, and being able to read what is on the
	# grid is the point of them. Items describe themselves there, so containers
	# do too.
	grid.read_only = true
	grid.load_inventory_state(_state(
		[_item({"position": [2, 3]})],
		[_container({"position": [2, 3]})]
	))

	assert_true(grid.containers[0].visual.enable_tooltip,
		"A read-only container should still have a tooltip")
	assert_eq(grid.containers[0].visual.mouse_filter, grid.items[0].mouse_filter,
		"A container should take the mouse the same way its items do")


# ============ Read-only mode ============

func test_read_only_grids_still_show_their_contents():
	# The battle screen shows both inventories read-only.
	grid.read_only = true
	grid.load_inventory_state(_state(
		[_item({"position": [2, 3]})],
		[_container({"position": [2, 3]})]
	))

	assert_eq(grid.items.size(), 1, "A read-only grid should still display its items")
	assert_eq(grid.containers.size(), 1, "A read-only grid should still display its containers")


# ============ Dropping on the chest ============

func test_dropping_on_the_chest_takes_the_item_off_the_grid():
	# The grid does not talk to the server. It takes the item off and says so,
	# and whoever owns it asks for the move and puts it back if that fails.
	_load_default_containers()
	grid.place_shop_item(_item({"id": "stored"}), Vector2i(2, 3))
	var zone = Control.new()
	zone.size = Vector2(100, 100)
	add_child(zone)
	autofree(zone)
	grid.storage_zone = zone

	watch_signals(grid)
	grid._start_drag(grid.items[0])
	grid._end_drag()
	await get_tree().process_frame

	assert_signal_emitted(grid, "item_stored", "Should say the item went to the chest")
	assert_eq(grid.items.size(), 0, "It should be off the grid")
	assert_null(grid.item_grid[3][2], "Its square should be free again")


func test_a_drop_away_from_the_chest_is_an_ordinary_move():
	_load_default_containers()
	grid.place_shop_item(_item({"id": "staying"}), Vector2i(2, 3))
	var zone = Control.new()
	zone.position = Vector2(5000, 5000)  # nowhere near the drop
	zone.size = Vector2(10, 10)
	add_child(zone)
	autofree(zone)
	grid.storage_zone = zone

	watch_signals(grid)
	grid._start_drag(grid.items[0])
	grid._end_drag()
	await get_tree().process_frame

	assert_signal_not_emitted(grid, "item_stored", "The chest was not the target")
	assert_eq(grid.items.size(), 1, "The item stays on the grid")


func test_a_grid_with_no_chest_still_drops():
	# The battle screens have no chest, so the zone is never set there.
	_load_default_containers()
	grid.place_shop_item(_item({"id": "no_chest"}), Vector2i(2, 3))
	assert_null(grid.storage_zone, "Setup: no chest on this grid")

	grid._start_drag(grid.items[0])
	grid._end_drag()
	await get_tree().process_frame

	assert_eq(grid.items.size(), 1, "It should still be on the grid, not lost")


# ============ Dragging out of the chest ============

func _grid_under_the_drop() -> InventoryGrid:
	# The grid an item would move to, sitting where the drop will land so the
	# hit test finds it.
	return _other_grid(Vector2.ZERO)


func test_dropping_on_the_main_grid_hands_the_item_over():
	# The chest cannot say which square of someone else's grid was hit, so it
	# says where the drop landed and lets that grid work it out.
	_load_default_containers()
	grid.place_shop_item(_item({"id": "leaving"}), Vector2i(2, 3))
	grid.grid_zone = _grid_under_the_drop()

	watch_signals(grid)
	grid._start_drag(grid.items[0])
	grid._end_drag()
	await get_tree().process_frame

	assert_signal_emitted(grid, "item_unstored", "Should hand the item over")
	assert_eq(grid.items.size(), 0, "The chest lets go of it")


func test_a_grid_that_saves_positions_is_unaffected_by_the_chest_rule():
	assert_true(grid.saves_positions, "An ordinary grid sends its moves")


# ============ A chest does not send its moves ============

func test_shuffling_inside_a_chest_is_not_sent_anywhere():
	# The chest lays itself out from scratch, so its squares are not places.
	# A square number from the chest would read as a square on the main grid.
	grid.saves_positions = false
	for y in range(grid.grid_height):
		for x in range(grid.grid_width):
			grid.active_grid[y][x] = true
	grid.place_shop_item(_item({"id": "shuffled"}), Vector2i(0, 0))

	watch_signals(grid)
	grid._start_drag(grid.items[0])
	grid._end_drag()
	await get_tree().process_frame

	assert_signal_not_emitted(grid, "item_moved", "Nothing to tell the server")
	assert_eq(grid.items.size(), 1, "The item is still in the chest")


# ============ Marking where a held item would land ============
#
# update_drag_preview takes the pointer rather than reading it, so these can
# put the pointer anywhere without a mouse. That is the whole reason it takes
# an argument: the hover mark is the kind of thing that only ever broke where
# no test could see it.

func _other_grid(at: Vector2 = Vector2(1000, 0)) -> InventoryGrid:
	var other = InventoryGridScript.new()
	add_child(other)
	autofree(other)
	other.configure(WIDTH, HEIGHT, 45.0, 1.0)
	other.position = at
	other.load_inventory_state(_state([], [
		_container({"id": "far_a", "position": [2, 3]})
	]))
	return other


func test_the_grid_marks_where_a_held_item_would_land():
	_load_default_containers()
	grid.place_shop_item(_item(), Vector2i(2, 3))
	grid._start_drag(grid.items[0])

	grid.update_drag_preview(grid.global_position + grid.grid_to_pixel(Vector2i(4, 3)))

	assert_true(grid.hover_preview.visible, "It should mark the square under the pointer")
	assert_eq(grid.hover_preview.position, grid.grid_to_pixel(Vector2i(4, 3)),
		"and mark the one the pointer is over")


func test_a_pointer_off_the_containers_is_marked_refused():
	_load_default_containers()
	grid.place_shop_item(_item(), Vector2i(2, 3))
	grid._start_drag(grid.items[0])

	grid.update_drag_preview(grid.global_position + grid.grid_to_pixel(Vector2i(0, 0)))

	assert_true(grid.hover_preview.visible, "Bare floor is still a square worth answering about")
	assert_eq(grid.hover_preview.get_child(0).get_theme_stylebox("panel").bg_color,
		grid.MARK_REFUSED_FILL, "and the answer is no")


func test_the_other_grid_marks_the_square_when_the_pointer_is_over_it():
	# Dragging out of the chest: the square under the pointer is one of the
	# main grid's squares, so the main grid is what marks it.
	var other = _other_grid()
	_load_default_containers()
	grid.place_shop_item(_item(), Vector2i(2, 3))
	grid.grid_zone = other
	grid._start_drag(grid.items[0])

	grid.update_drag_preview(other.global_position + other.grid_to_pixel(Vector2i(2, 3)))

	assert_true(other.hover_preview.visible, "The grid it would move to marks the square")
	assert_eq(other.hover_preview.position, other.grid_to_pixel(Vector2i(2, 3)),
		"and marks the right one")
	assert_false(grid.hover_preview.visible,
		"The grid it is leaving should not mark a square of its own")


func test_bringing_the_pointer_back_clears_the_other_grid():
	var other = _other_grid()
	_load_default_containers()
	grid.place_shop_item(_item(), Vector2i(2, 3))
	grid.grid_zone = other
	grid._start_drag(grid.items[0])

	grid.update_drag_preview(other.global_position + other.grid_to_pixel(Vector2i(2, 3)))
	grid.update_drag_preview(grid.global_position + grid.grid_to_pixel(Vector2i(4, 3)))

	assert_false(other.hover_preview.visible, "The other grid should stop marking")
	assert_true(grid.hover_preview.visible, "and this one should take over")


func test_letting_go_clears_the_other_grid():
	var other = _other_grid()
	_load_default_containers()
	grid.place_shop_item(_item(), Vector2i(2, 3))
	grid.grid_zone = other
	grid._start_drag(grid.items[0])
	grid.update_drag_preview(other.global_position + other.grid_to_pixel(Vector2i(2, 3)))

	grid._end_drag()
	await get_tree().process_frame

	assert_false(other.hover_preview.visible, "No mark should be left behind")


# ============ Moving a container ============
#
# A container needs squares that are free, where an item needs squares a
# container has made usable. The two ask opposite questions of the same board,
# which is why a container has a check of its own.

func test_a_container_may_stand_on_empty_floor():
	_load_default_containers()
	var moving = grid.containers[0].container

	assert_true(grid.can_place_container(moving, Vector2i(0, 0)),
		"Bare floor is exactly where a container goes")


func test_a_container_may_not_stand_on_another():
	_load_default_containers()
	var moving = grid.containers[0].container

	assert_false(grid.can_place_container(moving, Vector2i(4, 3)),
		"Container B is already there")


func test_a_container_is_no_obstacle_to_itself():
	# Its own squares must not count against it, or it could never stay put
	# nor shuffle by one.
	_load_default_containers()
	var moving = grid.containers[0].container

	assert_true(grid.can_place_container(moving, Vector2i(2, 3)),
		"Where it already stands is somewhere it can stand")

	# A shifts onto B if it moves right, so the one-square shift is C's, which
	# has nothing to its right but the edge.
	var rightmost = grid.containers[2].container
	assert_true(grid.can_place_container(rightmost, Vector2i(7, 3)),
		"It can shift by one onto squares that are its own")


func test_a_container_may_not_hang_off_the_grid():
	_load_default_containers()
	var moving = grid.containers[0].container

	assert_false(grid.can_place_container(moving, Vector2i(8, 3)),
		"A 2x2 at the last column would hang off the right")
	assert_false(grid.can_place_container(moving, Vector2i(2, 6)),
		"and at the last row it would hang off the bottom")


func test_picking_a_container_up_takes_its_items_with_it():
	_load_default_containers()
	grid.place_shop_item(_item({"id": "riding"}), Vector2i(2, 3))
	grid.place_shop_item(_item({"id": "elsewhere"}), Vector2i(4, 3))

	grid._start_container_drag(grid.containers[0])

	var riding = grid.container_riders.map(func(r): return r.id())
	assert_eq(riding, ["riding"], "Only what stands on it comes with it")


func test_dropping_a_container_somewhere_it_fits_asks_for_the_move():
	_load_default_containers()
	watch_signals(grid)

	grid._start_container_drag(grid.containers[0])
	grid.drop_container_at(grid.global_position + grid.grid_to_pixel(Vector2i(0, 0)))
	await get_tree().process_frame

	assert_signal_emitted_with_parameters(grid, "container_dropped",
		[grid.containers[0].container, Vector2i(0, 0)],
		"It should ask for the square it was dropped on")


func test_dropping_a_container_back_where_it_started_asks_for_nothing():
	_load_default_containers()
	watch_signals(grid)

	grid._start_container_drag(grid.containers[0])
	grid.drop_container_at(grid.global_position + grid.grid_to_pixel(Vector2i(2, 3)))
	await get_tree().process_frame

	assert_signal_not_emitted(grid, "container_dropped",
		"A container put back where it was has not moved")


func test_a_container_dropped_where_it_cannot_stand_goes_back():
	_load_default_containers()
	grid.place_shop_item(_item({"id": "riding"}), Vector2i(2, 3))
	var placed = grid.containers[0]
	var was_at = placed.visual.position
	var rider_was_at = grid.items[0].position

	grid._start_container_drag(placed)
	placed.visual.position = Vector2(-500, -500)  # dragged off the board
	grid.drop_container_at(grid.global_position + Vector2(-500, -500))
	await get_tree().process_frame

	assert_eq(placed.visual.position, was_at, "The container goes back")
	assert_eq(grid.items[0].position, rider_was_at, "and so does what stood on it")


func test_a_read_only_grid_does_not_pick_containers_up():
	# The battle screens show a board that cannot be rearranged.
	grid.read_only = true
	grid.load_inventory_state(_state([], [_container({"position": [2, 3]})]))

	grid._start_container_drag(grid.containers[0])

	assert_null(grid.dragging_container, "A read-only board holds still")


func test_an_item_that_has_been_moved_knows_where_it_is():
	# What a container carries is worked out from the squares its items cover,
	# so an item still reporting where it used to be gets picked up by the
	# wrong container.
	_load_default_containers()
	grid.place_shop_item(_item({"id": "wanderer"}), Vector2i(2, 3))

	grid._place_item_at(grid.items[0], Vector2i(4, 3))

	var item_data = grid.items[0].get_meta("item_data")
	assert_eq(item_data.position.to_array(), [4, 3], "It should know its new square")
	assert_eq(item_data.covered_squares(), [Vector2i(4, 3)], "and cover it")


func test_a_container_does_not_carry_an_item_that_has_moved_away():
	# Moving an item from one container to another and then dragging the first
	# used to take the item along, because it still said it was there.
	_load_default_containers()
	grid.place_shop_item(_item({"id": "moved_away"}), Vector2i(2, 3))
	grid._place_item_at(grid.items[0], Vector2i(4, 3))

	grid._start_container_drag(grid.containers[0])

	assert_eq(grid.container_riders.size(), 0,
		"Container A carries nothing: the item is on B now")


# ============ Turning a dragged item ============
#
# An item is turned while it is held. R and the wheel forward go clockwise, E
# and the wheel back the other way, and where that input is read is the UI's
# business -- the grid only knows how to turn what it is dragging.

func test_turning_a_dragged_item_changes_the_squares_it_covers():
	_load_default_containers()
	grid.place_shop_item(_item({"id": "wide", "shape": [[0, 0], [1, 0]]}), Vector2i(2, 3))
	grid._start_drag(grid.items[0])

	grid.turn_dragged(1)

	var item_data = grid.items[0].get_meta("item_data")
	assert_eq(item_data.facing(), 90, "A quarter turn clockwise")
	assert_eq(item_data.turned_shape().size(), 2, "It still covers two squares")
	var across = item_data.turned_shape().map(func(o): return o[0])
	assert_eq(across, [0, 0], "but both in the same column, standing on end")


func test_turning_the_other_way_goes_the_other_way():
	_load_default_containers()
	grid.place_shop_item(_item({"id": "wide", "shape": [[0, 0], [1, 0]]}), Vector2i(2, 3))
	grid._start_drag(grid.items[0])

	grid.turn_dragged(-1)

	assert_eq(grid.items[0].get_meta("item_data").facing(), 270,
		"Anticlockwise from square on is three quarters round")


func test_four_turns_bring_a_dragged_item_back():
	_load_default_containers()
	grid.place_shop_item(_item({"id": "wide", "shape": [[0, 0], [1, 0]]}), Vector2i(2, 3))
	grid._start_drag(grid.items[0])

	for i in 4:
		grid.turn_dragged(1)

	assert_eq(grid.items[0].get_meta("item_data").facing(), 0, "Back where it started")


func test_turning_nothing_is_harmless():
	# Nothing is being dragged, so there is nothing to turn.
	_load_default_containers()
	grid.turn_dragged(1)
	assert_null(grid.dragging_object, "Still nothing in hand")


func test_a_turned_item_is_placed_where_it_fits_turned():
	# The containers run from x 2 to x 7, so at the last column a two-wide item
	# hangs off the end and the same item stood on end does not. This is the
	# whole point of turning: it is what makes an item fit where it would not.
	_load_default_containers()
	var wide = _item({"id": "wide", "shape": [[0, 0], [1, 0]]})

	assert_false(grid.can_place_item(wide.placed_at(Vector2i(7, 3), 0), Vector2i(7, 3)),
		"Lying flat its right half is past the last container")
	assert_true(grid.can_place_item(wide.placed_at(Vector2i(7, 3), 90), Vector2i(7, 3)),
		"Stood on end it fits down the last column")


func test_a_turned_item_loaded_from_the_server_is_drawn_turned():
	# The battle screens and the shop screen both load a board the server sent.
	# An item that arrives turned has to be drawn turned, or the player is
	# looking at a different board from the one the battle was fought on.
	grid.load_inventory_state(_state(
		[_item({"id": "turned", "shape": [[0, 0], [1, 0]], "position": [2, 3],
			"rotation": 90})],
		[_container({"position": [2, 3]})]
	))

	var drawn = grid.items[0]
	var across = drawn.item_shape.map(func(o): return o[0])
	assert_eq(across, [0, 0], "It should be drawn on end, both squares in a column")
	assert_eq(drawn.size, Vector2(45, 91), "so it is one square wide and two tall")


func test_a_turned_item_occupies_the_squares_it_covers_turned():
	grid.load_inventory_state(_state(
		[_item({"id": "turned", "shape": [[0, 0], [1, 0]], "position": [2, 3],
			"rotation": 90})],
		[_container({"position": [2, 3]})]
	))

	assert_not_null(grid.item_grid[3][2], "It stands on its own square")
	assert_not_null(grid.item_grid[4][2], "and the one below, being on end")
	assert_null(grid.item_grid[3][3], "not the one beside it, which is where it would lie flat")


func test_saving_the_board_keeps_which_way_an_item_faces():
	# The board goes back to GameStateManager between screens. A turn dropped
	# here is a turn the player loses on the next screen.
	grid.load_inventory_state(_state(
		[_item({"id": "turned", "shape": [[0, 0], [1, 0]], "position": [2, 3],
			"rotation": 90})],
		[_container({"position": [2, 3]})]
	))

	var saved = grid.get_inventory_state()

	assert_eq(saved["items"][0]["rotation"], 90, "It should still be facing that way")


func test_putting_an_item_back_unchanged_tells_the_server_nothing():
	_load_default_containers()
	grid.place_shop_item(_item({"id": "unmoved", "shape": [[0, 0], [1, 0]]}), Vector2i(2, 3))
	grid._start_drag(grid.items[0])
	var item_data = grid.items[0].get_meta("item_data")

	assert_true(grid.drop_changes_nothing(Vector2i(2, 3), item_data),
		"Same square, same way round, nothing to tell")


func test_turning_an_item_in_place_is_a_change():
	# Picking an item up, turning it and setting it down where it was is the
	# obvious way to turn something. It covers different squares afterwards, so
	# the server has to hear about it -- its board is the one the battle uses.
	_load_default_containers()
	grid.place_shop_item(_item({"id": "turned", "shape": [[0, 0], [1, 0]]}), Vector2i(2, 3))
	grid._start_drag(grid.items[0])

	grid.turn_dragged(1)

	var item_data = grid.items[0].get_meta("item_data")
	assert_false(grid.drop_changes_nothing(Vector2i(2, 3), item_data),
		"It has not moved, but it is not the same board")


func test_moving_an_item_without_turning_it_is_a_change():
	_load_default_containers()
	grid.place_shop_item(_item({"id": "moved", "shape": [[0, 0], [1, 0]]}), Vector2i(2, 3))
	grid._start_drag(grid.items[0])
	var item_data = grid.items[0].get_meta("item_data")

	assert_false(grid.drop_changes_nothing(Vector2i(4, 3), item_data),
		"A different square is a change, turned or not")


# ============ The mark can be seen ============
#
# Containers used to be flat colour and the mark was drawn under them without
# anyone noticing. They are pictures with backgrounds now, and the mark went
# under the artwork: the highlight showing where an item would land was gone,
# and picking a container up hid its own mark behind the container in hand.

func test_the_mark_is_drawn_above_the_containers():
	_load_default_containers()
	grid.mark_square([[0, 0]], Vector2i(2, 3), true)

	assert_gt(grid.hover_preview.z_index, grid.containers[0].visual.z_index,
		"A mark under a container's artwork is a mark nobody sees")


func test_the_mark_is_drawn_above_a_container_in_hand():
	# The worst case: what hides the mark is the very thing being placed.
	_load_default_containers()
	grid._start_container_drag(grid.containers[0])

	assert_gt(grid.hover_preview.z_index, grid.containers[0].visual.z_index,
		"The container being carried should not cover its own mark")
	grid.drop_container_at(Vector2.ZERO)


func test_carrying_a_container_marks_where_it_would_stand():
	_load_default_containers()
	var held = grid.containers[0]
	grid._start_container_drag(held)

	grid.update_container_preview(
		grid.get_global_transform() * grid.grid_to_pixel(Vector2i(5, 1)))

	assert_true(grid.hover_preview.visible,
		"Carrying a container should mark where it would go")
	assert_gt(grid.hover_preview.get_child_count(), 0,
		"and the mark should have a patch per square the container covers")
	grid.drop_container_at(Vector2.ZERO)


func test_a_container_is_drawn_a_little_short_of_solid():
	# So the squares it covers, and anything marked on them, show through.
	_load_default_containers()
	var drawn = grid.containers[0].visual

	assert_lt(drawn.modulate.a, 1.0,
		"A solid container hides the grid and the marks underneath it")
	assert_gt(drawn.modulate.a, 0.5,
		"but it is furniture, not a ghost")
