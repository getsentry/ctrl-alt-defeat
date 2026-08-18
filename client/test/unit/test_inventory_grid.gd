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
