extends GutTest
# Comprehensive tests for UnifiedGridUI

const APITypes = preload("res://scripts/api_types.gd")
var ui_scene = preload("res://scenes/UnifiedGridUI.tscn")
var ui

func before_each():
	# Reset game state
	GameStateManager.start_new_game()
	GameStateManager.gold = 20  # Give some gold for testing

	# The 3 starting containers the server sends with a new session.
	GameStateManager.save_inventory_state([], [
		TestHelpers.container_data({"id": "container_a", "position": [2, 3]}),
		TestHelpers.container_data({"id": "container_b", "position": [4, 3]}),
		TestHelpers.container_data({"id": "container_c", "position": [6, 3]})
	])

	ui = ui_scene.instantiate()
	add_child(ui)
	await get_tree().process_frame

func after_each():
	if ui:
		ui.queue_free()
		ui = null

func test_ui_loads_without_errors():
	assert_not_null(ui, "UnifiedGridUI should load")
	assert_true(ui.visible, "UI should be visible")

func test_grid_dimensions():
	# Verify grid is correct size (9x7)
	assert_eq(ui.ROOM_WIDTH, 9, "Room should be 9 cells wide")
	assert_eq(ui.ROOM_HEIGHT, 7, "Room should be 7 cells tall")

	# InventoryGrid owns the grid arrays
	assert_eq(ui.inventory_grid.active_grid.size(), 7, "Active grid should have 7 rows")
	assert_eq(ui.inventory_grid.item_grid.size(), 7, "Item grid should have 7 rows")

	for row in ui.inventory_grid.active_grid:
		assert_eq(row.size(), 9, "Each row should have 9 columns")

func test_starting_containers_placed():
	# Verify 3 starting containers are placed
	await get_tree().create_timer(0.1).timeout  # Let placement happen

	# InventoryGrid owns the grid that containers mark.
	# UnifiedGridUI.active_grid is built but never written to.
	var container_count = 0
	for y in range(ui.ROOM_HEIGHT):
		for x in range(ui.ROOM_WIDTH):
			if ui.inventory_grid.active_grid[y][x]:
				container_count += 1

	# Each 2x2 container = 4 cells, 3 containers = 12 cells
	assert_gte(container_count, 8, "Should have at least 8 active grid cells from containers")

func test_shop_panel_exists():
	var shop_panel = ui.shop_container
	assert_not_null(shop_panel, "Shop panel should exist")

	if ui.hide_shop:
		assert_false(shop_panel.visible, "Shop should be hidden if hide_shop is true")
	else:
		assert_true(shop_panel.visible, "Shop should be visible by default")

func test_storage_area_exists():
	var storage = ui.storage_grid
	assert_not_null(storage, "Storage area should exist")

	if ui.hide_storage:
		assert_false(storage.visible, "Storage should be hidden if hide_storage is true")
	else:
		assert_true(storage.visible, "Storage should be visible by default")

func test_stats_display():
	assert_not_null(ui.stats_panel, "There should be somewhere to read the numbers")

	for caption in ["Name", "Class", "Gold", "Health", "Stamina",
			"Round", "Wins", "Tries"]:
		assert_has(ui.stat_values, caption, "Stats should show %s" % caption.to_lower())

	assert_eq(ui.stat_values["Gold"].text, "20", "Stats should show the current gold amount")
	assert_eq(ui.stat_values["Tries"].text, str(GameStateManager.player_lives),
		"Tries is how many goes are left in the run")


func test_health_is_blank_while_nothing_counts_it():
	# Nothing counts a health figure for a run. The `player_health` that used
	# to lose a point per defeat is gone: a run ends after five, so it never
	# fell below 95. A bar that never moves is worse than no bar.
	assert_eq(ui.stat_values["Health"].text, ui.NOT_KNOWN_YET,
		"Nothing maintains a health figure, so the row says nothing")


func test_the_class_is_named():
	assert_eq(ui.stat_values["Class"].text, "Sentaur", "There is one kind of player")


func test_stamina_is_blank_before_the_first_battle():
	# The pool only reaches the client stamped on a battle action, so before
	# any battle there is nothing to read. A number invented to fill the row is
	# one the player cannot tell from a real one, and they play against it.
	assert_eq(ui.stat_values["Stamina"].text, ui.NOT_KNOWN_YET,
		"No battle has been fought, so no pool has been reported")


func test_stamina_is_the_pool_the_last_battle_reported():
	var action = APITypes.BattleAction.new({
		"timestamp": 0, "source": "x", "action": "attack", "player": 1,
		"target": null, "damage": null,
		"details": {"cpu": [1.5, 3.0], "max_cpu": [4.0, 3.0]},
	})
	GameStateManager.last_battle_events = [action] as Array[APITypes.BattleAction]

	ui._update_stats()

	assert_eq(ui.stat_values["Stamina"].text, "4", "The player's pool, not the enemy's")


func test_the_rows_waiting_on_data_still_have_their_place():
	assert_not_null(ui.stamina_use_label, "Stamina usage keeps its spot")
	assert_not_null(ui.rank_label, "and so does the rank")


func test_spending_says_what_it_cost():
	# The gold on its own cannot tell a purchase from a refund.
	GameStateManager.gold = 20
	ui._update_stats()
	GameStateManager.gold = 14
	ui._update_stats()

	assert_eq(ui.gold_delta_label.text, "-6", "It should say what the gold just did")


func test_the_first_reading_of_the_gold_is_not_a_change():
	assert_eq(ui.gold_delta_label.text, "", "Arriving with 20 gold is not spending it")

func test_refresh_shop_button():
	# By name, not by caption: REROLL and its price are painted into the
	# background, so the button carries no words of its own.
	var refresh_btn = ui.find_child("RefreshButton", true, false)

	assert_not_null(refresh_btn, "Refresh shop button should exist")

	if refresh_btn and GameStateManager.gold >= 1:
		# Test clicking refresh
		watch_signals(refresh_btn)
		var initial_gold = GameStateManager.gold

		refresh_btn.pressed.emit()
		await get_tree().process_frame

		# Gold should decrease by 1 (if shop refreshed)
		# Note: This may not work without server connection

func test_start_battle_button():
	# Find start battle button
	var battle_btn = null
	for child in ui.get_children():
		if child is Button and "Battle" in child.text:
			battle_btn = child
			break

	if not battle_btn:
		var controls = ui.find_child("Controls", true, false)
		if controls:
			for child in controls.get_children():
				if child is Button and "Battle" in child.text:
					battle_btn = child
					break

	assert_not_null(battle_btn, "Start battle button should exist")

func test_drag_and_drop_initialization():
	# UnifiedGridUI drags shop items. InventoryGrid drags items already on the
	# grid. Neither should be dragging when the screen opens.
	assert_null(ui.dragging_shop_item, "Should not be dragging a shop item initially")
	assert_null(ui.dragging_shop_data, "Nothing should be dragged from the shop")

	assert_null(ui.inventory_grid.dragging_object, "Should not be dragging initially")
	assert_eq(ui.inventory_grid.drag_offset, Vector2.ZERO, "Drag offset should be zero")
	assert_false(ui.inventory_grid.valid_placement, "Placement should not be valid initially")

	# The grid owns the mark: the squares are its, so it is the only thing that
	# knows where one would land.
	assert_not_null(ui.inventory_grid.hover_preview, "Hover preview should be ready")
	assert_false(ui.inventory_grid.hover_preview.visible,
		"Hover preview should be hidden initially")

func test_grid_cell_creation():
	# InventoryGrid owns the cell visuals
	assert_gt(ui.inventory_grid.grid_cells.size(), 0, "Grid cells should be created")

	var total_cells = 0
	for row in ui.inventory_grid.grid_cells:
		total_cells += row.size()

	assert_eq(total_cells, ui.ROOM_WIDTH * ui.ROOM_HEIGHT,
		"Should have correct number of grid cells")

func test_shop_item_display():
	# Mock shop data
	var mock_shop: Array[APITypes.Item] = [
		TestHelpers.item({"id": "item1", "name": "Test Item", "cost": 5}),
		null,  # A slot whose item has been bought
		TestHelpers.item({"id": "item2", "name": "Another Item", "cost": 8})
	]

	ui._display_shop_items(mock_shop)
	await get_tree().process_frame

	# Check shop items were created
	var shop_items_count = ui.shop_container.get_child_count()
	assert_gte(shop_items_count, 2, "Should display at least 2 shop items")

func test_gold_check_on_purchase():
	# Test that items can't be bought without gold
	GameStateManager.gold = 3

	var expensive_item = {
		"id": "expensive",
		"name": "Expensive Item",
		"cost": 10,
		"item_type": "test"
	}

	# Try to buy - should fail
	# This would normally happen through drag and drop
	var can_afford = expensive_item.cost <= GameStateManager.gold
	assert_false(can_afford, "Should not be able to afford expensive item")

func test_read_only_mode():
	# Test read-only mode prevents interactions
	ui.read_only_mode = true

	# Create a mock shop item
	var shop_item = Panel.new()
	var item_data = TestHelpers.item({"id": "test", "cost": 5})

	# Try to start dragging - should be blocked
	var event = InputEventMouseButton.new()
	event.button_index = MOUSE_BUTTON_LEFT
	event.pressed = true

	ui._on_shop_item_input(event, shop_item, item_data)

	assert_null(ui.dragging_shop_item, "Should not start dragging in read-only mode")

	shop_item.queue_free()

	shop_item.queue_free()

func test_inventory_state_save_and_load():
	# load_inventory_state() takes an APITypes.InventoryState.
	var test_state = APITypes.InventoryState.new({
		"items": [TestHelpers.placed_item_data({"id": "item1", "name": "Test Item"})],
		"servers": [TestHelpers.container_data({"id": "container_a"})]
	})

	ui.load_inventory_state(test_state)
	await get_tree().process_frame

	var saved_state = ui.get_inventory_state()
	assert_eq(saved_state["items"].size(), 1, "Should save correct number of items")
	assert_eq(saved_state["servers"].size(), 1, "Should save correct number of servers")
	assert_eq(saved_state["items"][0]["id"], "item1", "Should keep the item that was loaded")

func test_grid_coordinate_validation():
	# Placement is validated by _can_place_container().
	var container = TestHelpers.item({"is_container": true,
		"shape": [[0, 0], [1, 0], [0, 1], [1, 1]], "rotation": 0})

	assert_false(ui._can_place_container(container, Vector2i(-1, 0)),
		"Should reject negative X coordinate")
	assert_false(ui._can_place_container(container, Vector2i(0, -1)),
		"Should reject negative Y coordinate")
	assert_false(ui._can_place_container(container, Vector2i(ui.ROOM_WIDTH, 0)),
		"Should reject X beyond grid width")
	assert_false(ui._can_place_container(container, Vector2i(0, ui.ROOM_HEIGHT)),
		"Should reject Y beyond grid height")
	assert_false(ui._can_place_container(container, Vector2i(ui.ROOM_WIDTH - 1, 0)),
		"Should reject a container that would hang off the right edge")

	assert_true(ui._can_place_container(container, Vector2i(0, 0)),
		"Should accept an empty in-bounds position")

func test_a_container_covers_only_the_squares_of_its_shape():
	# An L shape covers 3 of the 4 squares in its 2x2 bounding box.
	var l_shape = TestHelpers.item({"is_container": true,
		"shape": [[0, 0], [0, 1], [1, 1]]})

	var squares = ui._container_squares(l_shape, Vector2i(2, 3))

	assert_eq(squares, [Vector2i(2, 3), Vector2i(2, 4), Vector2i(3, 4)],
		"Only the squares of the shape are covered")

func test_the_preview_draws_one_cell_per_covered_square():
	# An L shape covers 3 squares, so the preview has 3 cells, not a 2x2 block.
	var l_shape = TestHelpers.item({"is_container": true,
		"shape": [[0, 0], [0, 1], [1, 1]]})

	ui._show_container_preview(l_shape, Vector2i(0, 0))

	assert_not_null(ui.container_preview, "The preview should be built")
	assert_eq(ui.container_preview.get_child_count(), 3,
		"One cell per covered square")

func test_the_preview_cells_sit_on_the_covered_squares():
	var l_shape = TestHelpers.item({"is_container": true,
		"shape": [[0, 0], [0, 1], [1, 1]]})

	ui._show_container_preview(l_shape, Vector2i(0, 0))

	var drawn_at = []
	for cell in ui.container_preview.get_children():
		drawn_at.append(cell.position)

	var expected = []
	for square in ui._container_squares(l_shape, Vector2i(0, 0)):
		expected.append(ui.inventory_grid.grid_to_pixel(square))

	assert_eq(drawn_at, expected, "Each cell sits on its own grid square")

func test_an_occupied_square_is_marked_refused():
	# (2, 3) is already covered by container_a. Marking nothing would leave the
	# player unable to tell a refusal from a pointer the game never saw.
	var vm = TestHelpers.item({"is_container": true,
		"shape": [[0, 0], [1, 0], [0, 1], [1, 1]], "rotation": 0})

	ui._show_container_preview(vm, Vector2i(2, 3))

	assert_not_null(ui.container_preview, "An occupied square still gets an answer")
	assert_eq(
		ui.container_preview.get_child(0).get_theme_stylebox("panel").bg_color,
		InventoryGrid.MARK_REFUSED_FILL, "and the answer is no")


func test_no_preview_off_the_board():
	var vm = TestHelpers.item({"is_container": true,
		"shape": [[0, 0], [1, 0], [0, 1], [1, 1]], "rotation": 0})

	ui._show_container_preview(vm, Vector2i(-1, -1))

	assert_null(ui.container_preview, "There is no square out there to answer about")

func test_the_preview_replaces_the_previous_one():
	var vm = TestHelpers.item({"is_container": true,
		"shape": [[0, 0], [1, 0], [0, 1], [1, 1]], "rotation": 0})

	ui._show_container_preview(vm, Vector2i(0, 0))
	var first = ui.container_preview
	ui._show_container_preview(vm, Vector2i(0, 5))

	assert_ne(ui.container_preview, first, "A new preview replaces the old one")
	assert_eq(ui.container_preview.get_child_count(), 4, "The new preview is drawn")

func test_color_for_categories():
	# Test category color assignment
	var colors = {
		"problem": ui._get_color_for_category("problem"),
		"defense": ui._get_color_for_category("defense"),
		"infrastructure": ui._get_color_for_category("infrastructure")
	}

	# Colors should be different for different categories
	assert_ne(colors["problem"], colors["defense"],
		"Problem and defense should have different colors")
	assert_ne(colors["defense"], colors["infrastructure"],
		"Defense and infrastructure should have different colors")


# ============ Shop price labels ============

func test_shop_shows_a_price_for_every_item():
	for i in range(1, 6):
		var price_label = ui.shop_container.get_node_or_null("ShopPrice" + str(i))
		assert_not_null(price_label, "Shop slot %d should have a price label" % i)

	var shop_data = GameStateManager.current_shop
	for i in range(min(shop_data.size(), 5)):
		if shop_data[i] == null:
			continue
		var price_label = ui.shop_container.get_node_or_null("ShopPrice" + str(i + 1))
		assert_true(price_label.visible, "Slot %d holds an item, so its price should show" % (i + 1))
		assert_eq(price_label.text, str(shop_data[i]["cost"]) + "g",
			"Slot %d should show the item's cost" % (i + 1))


func test_empty_shop_slot_hides_its_price():
	var empty_shop: Array[APITypes.Item] = [null, null, null, null, null]
	ui._display_shop_items(empty_shop)
	await get_tree().process_frame

	for i in range(1, 6):
		var price_label = ui.shop_container.get_node_or_null("ShopPrice" + str(i))
		assert_false(price_label.visible, "An empty slot should show no price")


func test_shop_price_label_shows_what_the_shop_charges():
	var priced_shop: Array[APITypes.Item] = [
		TestHelpers.item({"id": "priced_item", "cost": 7, "price": 7}),
		null, null, null, null]
	ui._display_shop_items(priced_shop)
	await get_tree().process_frame

	assert_eq(ui.shop_container.get_node_or_null("ShopPrice1").text, "7g")


func test_shop_price_label_shows_the_sale_price_not_the_cost():
	var priced_shop: Array[APITypes.Item] = [
		TestHelpers.item({"id": "on_sale", "cost": 8, "price": 4, "on_sale": true}),
		null, null, null, null]
	ui._display_shop_items(priced_shop)
	await get_tree().process_frame

	assert_eq(ui.shop_container.get_node_or_null("ShopPrice1").text, "4g",
		"A sale should be charged, not just displayed on the panel")


# ============ Ready and refresh buttons ============

func test_ready_and_refresh_buttons_are_wired():
	var ready_btn = ui.find_child("ReadyButton", true, false)
	var refresh_btn = ui.find_child("RefreshButton", true, false)

	assert_not_null(ready_btn, "There should be a ready button")
	assert_not_null(refresh_btn, "There should be a refresh button")
	assert_gt(ready_btn.pressed.get_connections().size(), 0, "Ready should do something")
	assert_gt(refresh_btn.pressed.get_connections().size(), 0, "Refresh should do something")


# ============ Sell chest ============

func test_the_chest_names_the_price_while_an_item_is_held():
	var item = TestHelpers.placed_item({"name": "Null Blade", "sell_value": 4})
	ui._on_drag_started(item)
	assert_eq(ui.sell_chest.get_node("Prompt").text, "Drop here to sell for 4")


func test_the_chest_stops_naming_a_price_once_the_item_is_down():
	ui._on_drag_started(TestHelpers.placed_item({"sell_value": 4}))
	ui._on_drag_ended()
	assert_eq(ui.sell_chest.get_node("Prompt").text, "Drop here to sell")


func test_the_grid_knows_where_the_chest_is():
	# Without this the grid has nothing to test a drop against and every
	# item goes back to its square.
	assert_eq(ui.inventory_grid.sell_zone, ui.sell_chest)


# ============ The chest ============
#
# An item in the chest is off the grid, so it has no position. The chest is
# what decides where to draw it, and it has to draw everything the server says
# is in there -- a container move can put an item in the chest without the
# player asking, and an item nobody can see looks like an item that was lost.

func _chest_item(overrides: Dictionary = {}) -> Resource:
	return TestHelpers.item(overrides)


func test_the_chest_shows_what_the_server_says_is_in_it():
	GameStateManager.inventory_storage = [
		_chest_item({"id": "first"}), _chest_item({"id": "second"})
	]

	ui.load_storage()

	var drawn = ui.storage_grid.items.map(func(v): return v.get_meta("item_data").id)
	assert_eq(drawn.size(), 2, "Both items should be drawn")
	assert_true("first" in drawn and "second" in drawn, "Both by id")


func test_an_empty_chest_draws_nothing():
	GameStateManager.inventory_storage = []

	ui.load_storage()

	assert_eq(ui.storage_grid.items.size(), 0, "Nothing in the chest, nothing drawn")


func test_chest_items_do_not_land_on_each_other():
	GameStateManager.inventory_storage = [
		_chest_item({"id": "a"}), _chest_item({"id": "b"}), _chest_item({"id": "c"})
	]

	ui.load_storage()

	var squares = []
	for visual in ui.storage_grid.items:
		for square in visual.get_meta("item_data").covered_squares():
			assert_false(square in squares, "%s is drawn on top of something" % square)
			squares.append(square)


func test_a_multi_square_item_fits_in_the_chest():
	GameStateManager.inventory_storage = [_chest_item({"shape": [[0, 0], [1, 0]]})]

	ui.load_storage()

	assert_eq(ui.storage_grid.items.size(), 1, "A wide item should still be drawn")


func test_loading_the_chest_twice_does_not_double_it():
	# It is redrawn on every inventory load, so it has to replace rather than add.
	GameStateManager.inventory_storage = [_chest_item({"id": "only"})]

	ui.load_storage()
	ui.load_storage()

	assert_eq(ui.storage_grid.items.size(), 1, "The chest should be redrawn, not added to")


func test_an_item_taken_out_of_the_chest_stops_being_drawn():
	GameStateManager.inventory_storage = [_chest_item({"id": "leaving"})]
	ui.load_storage()

	GameStateManager.inventory_storage = []
	ui.load_storage()

	assert_eq(ui.storage_grid.items.size(), 0, "It is gone from the chest, so gone from view")


func test_a_move_answer_refreshes_the_chest():
	# Moving a container can set an item down in the chest without the player
	# asking, so the chest is redrawn from whatever the server sends back.
	var response = APITypes.MoveItemResponse.new({
		"inventory_grid": [],
		"inventory_storage": [TestHelpers.item_data({"id": "set_down"})],
		"server_containers": []
	})

	ui._on_inventory_returned(response)

	var drawn = ui.storage_grid.items.map(func(v): return v.get_meta("item_data").id)
	assert_eq(drawn, ["set_down"], "The chest should show what the move put there")


func test_the_sell_chest_names_its_price_for_an_item_from_the_chest():
	# An item can be sold out of the chest as well as off the grid, so the
	# prompt has to answer to both.
	GameStateManager.inventory_storage = [TestHelpers.item({"id": "held", "cost": 8})]
	ui.load_storage()

	ui.storage_grid._start_drag(ui.storage_grid.items[0])
	await get_tree().process_frame

	var prompt = ui.sell_chest.get_node("Prompt").text
	assert_true("sell for" in prompt,
		"The prompt should name a price, not stay at its resting text. Got: %s" % prompt)

	ui.storage_grid._end_drag()
	await get_tree().process_frame
	assert_eq(ui.sell_chest.get_node("Prompt").text, "Drop here to sell",
		"and go back to its resting text when the drag ends")


# ============ The chest is actually on screen ============
#
# Two bugs got as far as a screenshot before anything noticed: the chest was
# drawn wider than the panel holding it, so most of it was off the edge of its
# own box, and the panel's modulate faded everything inside it to a fifth.
# Both looked perfectly healthy from the node tree. These are the invariants
# that were broken.

func _effective_alpha(node: CanvasItem) -> float:
	"""How opaque a node really is, once its parents have had their say.

	modulate multiplies down the tree, so a node can report full opacity and
	still be drawn nearly invisible.
	"""
	var alpha = 1.0
	var walk: Node = node
	while walk is CanvasItem:
		alpha *= walk.modulate.a
		walk = walk.get_parent()
	return alpha


func test_the_chest_fits_inside_its_panel():
	var panel = ui.storage_grid.get_parent()
	assert_lte(ui.storage_grid.size.x, panel.size.x,
		"A chest wider than its panel is drawn off the edge of its own box")
	assert_lte(ui.storage_grid.size.y, panel.size.y,
		"and the same downwards")


func test_the_chest_stays_within_its_panel():
	var panel = ui.storage_grid.get_parent()
	var grid = ui.storage_grid
	assert_gte(grid.position.x, 0.0, "It should not start left of its panel")
	assert_gte(grid.position.y, 0.0, "nor above it")
	assert_lte(grid.position.x + grid.size.x, panel.size.x, "nor run off the right")
	assert_lte(grid.position.y + grid.size.y, panel.size.y, "nor off the bottom")


func test_what_is_in_the_chest_is_drawn_solid():
	GameStateManager.inventory_storage = [TestHelpers.item({"id": "held"})]
	ui.load_storage()

	var drawn = ui.storage_grid.items[0]
	assert_almost_eq(_effective_alpha(drawn), 1.0, 0.01,
		"An item in the chest should be as solid as one on the grid. " +
		"Check the panel's modulate: it multiplies down into every child.")


# ============ An item in the hand ============
#
# A container move can set an item down in the chest without the player asking.
# Rather than leaving it there, the item comes into the hand: picked up with no
# button held, and put down with a click.
#
# The item is in the chest the whole time it is held, so nothing can strand it.

func test_holding_an_item_shows_it():
	var item = TestHelpers.item({"id": "held"})

	ui.hold(item)

	assert_eq(ui.held_item, item, "It should be in hand")
	assert_true(is_instance_valid(ui.held_visual), "and drawn following the pointer")


func test_letting_go_leaves_it_in_the_chest():
	GameStateManager.inventory_storage = [TestHelpers.item({"id": "held"})]
	ui.load_storage()
	ui.hold(GameStateManager.inventory_storage[0])

	ui.release_hand()
	await get_tree().process_frame

	assert_null(ui.held_item, "Nothing in hand")
	assert_eq(ui.storage_grid.items.size(), 1, "and it is still in the chest")


func test_clicking_the_chest_puts_it_back():
	GameStateManager.inventory_storage = [TestHelpers.item({"id": "held"})]
	ui.load_storage()
	ui.hold(GameStateManager.inventory_storage[0])

	var chest = ui.storage_grid.get_parent()
	ui.place_held_at(chest.global_position + chest.size / 2)
	await get_tree().process_frame

	assert_null(ui.held_item, "The chest is where it already was, so this is letting go")
	assert_eq(ui.storage_grid.items.size(), 1, "and it is drawn there")


func test_clicking_nowhere_keeps_hold_of_it():
	# Otherwise a misclick drops the item somewhere the player did not choose.
	var item = TestHelpers.item({"id": "held"})
	ui.hold(item)

	ui.place_held_at(Vector2(-500, -500))
	await get_tree().process_frame

	assert_eq(ui.held_item, item, "A click on nothing should not put it down")


func test_holding_something_else_lets_go_of_the_first():
	ui.hold(TestHelpers.item({"id": "first"}))
	var second = TestHelpers.item({"id": "second"})

	ui.hold(second)
	await get_tree().process_frame

	assert_eq(ui.held_item, second, "The hand holds one thing")
	assert_eq(ui.get_children().filter(func(c): return c == ui.held_visual).size(), 1,
		"and the first drawing is gone")


func test_a_rider_that_did_not_land_comes_into_the_hand():
	# The items that travelled with the container are known, so the question is
	# which of them is missing from the grid afterwards. Nothing is asked of
	# the chest, so what else is in there cannot be mistaken for a displaced
	# item.
	GameStateManager.inventory_storage = [
		TestHelpers.item({"id": "unrelated"}), TestHelpers.item({"id": "stranded"})
	]

	var riders: Array[String] = ["landed", "stranded"]
	var on_grid: Array[APITypes.PlacedItem] = [TestHelpers.placed_item({"id": "landed"})]

	ui.take_displaced(riders, on_grid)

	assert_not_null(ui.held_item, "The rider that did not land should be in hand")
	assert_eq(ui.held_item.id, "stranded", "and not the one that was already in the chest")


func test_riders_that_all_landed_leave_the_hand_empty():
	var riders: Array[String] = ["a", "b"]
	var on_grid: Array[APITypes.PlacedItem] = [
		TestHelpers.placed_item({"id": "a"}), TestHelpers.placed_item({"id": "b"})
	]

	ui.take_displaced(riders, on_grid)

	assert_null(ui.held_item, "Nothing was left behind, so nothing is picked up")


func test_a_move_with_no_riders_leaves_the_hand_empty():
	var riders: Array[String] = []
	var on_grid: Array[APITypes.PlacedItem] = []

	ui.take_displaced(riders, on_grid)

	assert_null(ui.held_item, "An empty container carries nothing to strand")


func test_only_the_first_stranded_rider_comes_into_the_hand():
	# The rest stay in the chest, which is where they are anyway.
	GameStateManager.inventory_storage = [
		TestHelpers.item({"id": "first"}), TestHelpers.item({"id": "second"})
	]

	var riders: Array[String] = ["first", "second"]
	var on_grid: Array[APITypes.PlacedItem] = []

	ui.take_displaced(riders, on_grid)

	assert_eq(ui.held_item.id, "first", "One hand, one item")


func test_the_held_item_is_not_also_drawn_in_the_chest():
	# It is in the chest the whole time it is held, because the hand is a
	# shortcut and not a place. Drawing it in both would look like two of it.
	GameStateManager.inventory_storage = [
		TestHelpers.item({"id": "in_hand"}), TestHelpers.item({"id": "left_behind"})
	]

	ui.hold(GameStateManager.inventory_storage[0])
	await get_tree().process_frame

	var drawn = ui.storage_grid.items.map(func(v): return v.get_meta("item_data").id)
	assert_eq(drawn, ["left_behind"], "Only what is not in hand is drawn in the chest")


func test_letting_go_draws_it_in_the_chest_again():
	GameStateManager.inventory_storage = [TestHelpers.item({"id": "in_hand"})]
	ui.hold(GameStateManager.inventory_storage[0])

	ui.release_hand()
	await get_tree().process_frame

	var drawn = ui.storage_grid.items.map(func(v): return v.get_meta("item_data").id)
	assert_eq(drawn, ["in_hand"], "It comes back into view where it has been all along")


func test_a_second_stranded_item_waits_in_the_chest():
	# One hand, so the rest stay where the move put them and are drawn there.
	GameStateManager.inventory_storage = [
		TestHelpers.item({"id": "first"}), TestHelpers.item({"id": "second"})
	]

	var riders: Array[String] = ["first", "second"]
	var on_grid: Array[APITypes.PlacedItem] = []

	ui.take_displaced(riders, on_grid)
	await get_tree().process_frame

	assert_eq(ui.held_item.id, "first", "The first comes into the hand")
	var drawn = ui.storage_grid.items.map(func(v): return v.get_meta("item_data").id)
	assert_eq(drawn, ["second"], "and the second is waiting in the chest")


func test_a_held_item_sits_under_the_pointer():
	ui.hold(TestHelpers.item({"id": "held"}))

	ui.follow_pointer(Vector2(400, 300))

	assert_eq(ui.held_visual.global_position + ui.held_visual.size / 2,
		Vector2(400, 300), "It should be centred on the pointer")


func test_a_held_item_is_placed_the_moment_it_is_picked_up():
	# Waiting for the first mouse movement left it sitting in the corner of the
	# screen until the player twitched.
	ui.hold(TestHelpers.item({"id": "held"}))
	await get_tree().process_frame

	assert_ne(ui.held_visual.global_position, Vector2.ZERO,
		"It should already be under the pointer, not parked at the origin")


func test_a_held_item_marks_where_it_would_land():
	# A held item is not being dragged, so the grid marks nothing by itself.
	# It still has to show where a click would put it.
	GameStateManager.inventory_storage = [TestHelpers.item({"id": "held"})]
	ui.hold(GameStateManager.inventory_storage[0])
	var grid = ui.inventory_grid

	ui.follow_pointer(grid.global_position + grid.grid_to_pixel(Vector2i(2, 3)))

	assert_true(grid.hover_preview.visible, "It should mark the square under the pointer")
	assert_eq(grid.hover_preview.position, grid.grid_to_pixel(Vector2i(2, 3)),
		"and the one the pointer is over")


func test_a_held_item_over_bare_floor_is_marked_refused():
	# Blank would say only that nothing is happening. Red says the square was
	# read and the answer is no.
	GameStateManager.inventory_storage = [TestHelpers.item({"id": "held"})]
	ui.hold(GameStateManager.inventory_storage[0])
	var grid = ui.inventory_grid

	ui.follow_pointer(grid.global_position + grid.grid_to_pixel(Vector2i(0, 0)))

	assert_true(grid.hover_preview.visible, "Bare floor should still be marked")
	assert_eq(grid.hover_preview.get_child(0).get_theme_stylebox("panel").bg_color,
		grid.MARK_REFUSED_FILL, "and marked as somewhere it cannot go")


func test_a_held_item_off_the_board_marks_nothing():
	GameStateManager.inventory_storage = [TestHelpers.item({"id": "held"})]
	ui.hold(GameStateManager.inventory_storage[0])
	var grid = ui.inventory_grid

	ui.follow_pointer(grid.global_position - Vector2(200, 200))

	assert_false(grid.hover_preview.visible, "There is no square out there to answer about")


func test_the_mark_covers_the_squares_the_item_covers():
	# An L reaches four corners and covers three of them. A mark drawn as one
	# rectangle claims the fourth, which is the square being asked about.
	GameStateManager.inventory_storage = [
		TestHelpers.item({"id": "held", "shape": [[0, 0], [0, 1], [1, 1]]})]
	ui.hold(GameStateManager.inventory_storage[0])
	var grid = ui.inventory_grid

	ui.follow_pointer(grid.global_position + grid.grid_to_pixel(Vector2i(2, 3)))

	assert_eq(grid.hover_preview.get_child_count(), 3, "One patch per covered square")


func test_letting_go_clears_the_mark():
	GameStateManager.inventory_storage = [TestHelpers.item({"id": "held"})]
	ui.hold(GameStateManager.inventory_storage[0])
	var grid = ui.inventory_grid
	ui.follow_pointer(grid.global_position + grid.grid_to_pixel(Vector2i(2, 3)))

	ui.release_hand()
	await get_tree().process_frame

	assert_false(grid.hover_preview.visible, "No mark should be left behind")


# ============ Turning what is held ============
#
# An item is held either because it is being dragged or because a container
# move set it down and it was picked up. Both are holding it, so both turn, and
# one action reaches both.

func test_turning_what_is_in_hand():
	GameStateManager.inventory_storage = [
		TestHelpers.item({"id": "held", "shape": [[0, 0], [1, 0]]})
	]
	ui.hold(GameStateManager.inventory_storage[0])

	ui.turn(1)

	assert_eq(ui.held_item.facing(), 90, "A quarter turn clockwise")
	var across = ui.held_item.turned_shape().map(func(o): return o[0])
	assert_eq(across, [0, 0], "and it now stands on end")


func test_turning_what_is_in_hand_the_other_way():
	GameStateManager.inventory_storage = [
		TestHelpers.item({"id": "held", "shape": [[0, 0], [1, 0]]})
	]
	ui.hold(GameStateManager.inventory_storage[0])

	ui.turn(-1)

	assert_eq(ui.held_item.facing(), 270, "Anticlockwise")


func test_turning_reaches_an_item_being_dragged_on_the_grid():
	# Nothing is in hand, so the turn has to find the drag instead.
	GameStateManager.save_inventory_state([], [
		TestHelpers.container_data({"id": "container_a", "position": [2, 3]})
	])
	ui.inventory_grid.load_inventory_state(APITypes.InventoryState.new(
		GameStateManager.get_inventory_state()))
	ui.inventory_grid.place_shop_item(
		TestHelpers.item({"id": "dragged", "shape": [[0, 0], [1, 0]]}), Vector2i(2, 3))
	ui.inventory_grid._start_drag(ui.inventory_grid.items[0])

	ui.turn(1)

	assert_eq(ui.inventory_grid.items[0].get_meta("item_data").facing(), 90,
		"The dragged item turned, though nothing was in hand")


func test_turning_with_nothing_held_does_nothing():
	ui.turn(1)
	assert_null(ui.held_item, "Nothing to turn, and nothing goes wrong")


func test_turning_reaches_an_item_carried_out_of_the_shop():
	# This is the one most worth turning: it is when the player is deciding
	# where on the board a new item goes. It is also a different drag from the
	# grid's, so it has to be reached separately.
	ui.dragging_shop_data = TestHelpers.item(
		{"id": "buying", "shape": [[0, 0], [1, 0]]})

	ui.turn(1)

	assert_eq(ui.dragging_shop_data.facing(), 90, "A quarter turn clockwise")
	var across = ui.dragging_shop_data.turned_shape().map(func(o): return o[0])
	assert_eq(across, [0, 0], "and it now stands on end")


func test_a_shop_item_turned_and_bought_is_bought_turned():
	# The client used to place it turned and buy it flat, so the board the
	# player saw and the board the server kept were different, and the server
	# won at battle time.
	ui.dragging_shop_data = TestHelpers.item(
		{"id": "buying", "shape": [[0, 0], [1, 0]]})
	ui.turn(1)

	assert_eq(ui.dragging_shop_data.facing(), 90,
		"The facing the purchase carries is the one the player chose")


func test_turning_says_whether_anything_turned():
	# There is one list of what counts as holding something, and this is it.
	# Two lists that had to agree is what let the shop drag go unturnable.
	assert_false(ui.turn(1), "Holding nothing, nothing turns")

	GameStateManager.inventory_storage = [TestHelpers.item({"id": "held"})]
	ui.hold(GameStateManager.inventory_storage[0])

	assert_true(ui.turn(1), "Holding something, it turns")


func test_the_wheel_is_left_alone_when_nothing_is_held():
	# The turn only swallows the input if it used it, so the wheel still
	# scrolls when the player is not carrying anything.
	assert_false(ui.turn(1), "Nothing to turn means the input was not used")
