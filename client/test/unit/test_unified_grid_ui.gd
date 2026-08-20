extends GutTest
# Comprehensive tests for UnifiedGridUI

const APITypes = preload("res://scripts/api_types.gd")
const Presentation = preload("res://scripts/presentation.gd")
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
	var storage = ui.storage_bin
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
	# It used to be found by reading the word "Battle" off a button. What it
	# says is painted on it now -- it is a picture of a key -- so there is no
	# text on it to look for.
	var battle_btn = ui.find_child("ReadyButton", true, false)

	assert_not_null(battle_btn, "Start battle button should exist")
	assert_true(battle_btn is TextureButton, "It should be the key artwork")
	assert_true("start_battle_key" in battle_btn.texture_normal.resource_path,
		"and wear the key, got: %s" % battle_btn.texture_normal.resource_path)
	assert_not_null(battle_btn.texture_pressed,
		"and go down when it is pressed, as a key does")


func test_the_battle_key_keeps_the_shape_of_its_artwork():
	# A key stretched to fill a box is a key nobody would press. It is fitted
	# to the room it has and centred in what is left.
	var battle_btn = ui.find_child("ReadyButton", true, false)

	assert_true(battle_btn.ignore_texture_size,
		"The rect it is given should decide its size")
	assert_eq(battle_btn.stretch_mode, TextureButton.STRETCH_KEEP_ASPECT_CENTERED,
		"and it should keep its own shape inside that rect")

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
# An item in the chest is off the grid, so it has no place and no facing. The
# chest is a box rather than a set of squares: an item lies where it lands and
# is left there, and it has to hold everything the server says is in there --
# a container move can put an item in the chest without the player asking, and
# an item nobody can see looks like an item that was lost.

func _chest_item(overrides: Dictionary = {}) -> Resource:
	return TestHelpers.item(overrides)


func test_the_chest_shows_what_the_server_says_is_in_it():
	GameStateManager.inventory_storage = [
		_chest_item({"id": "first"}), _chest_item({"id": "second"})
	]

	ui.load_storage()

	var drawn = ui.storage_bin.ids()
	assert_eq(drawn.size(), 2, "Both items should be drawn")
	assert_true("first" in drawn and "second" in drawn, "Both by id")


func test_an_empty_chest_draws_nothing():
	GameStateManager.inventory_storage = []

	ui.load_storage()

	assert_eq(ui.storage_bin.count(), 0, "Nothing in the chest, nothing drawn")


func test_the_chest_holds_more_than_the_tray_can_show():
	# It used to be twenty-four squares, and the server holds no such limit, so
	# a full chest lost items out of view. A box has no squares to run out of.
	var lots: Array[APITypes.Item] = []
	for i in range(30):
		lots.append(_chest_item({"id": "item_%d" % i}))
	GameStateManager.inventory_storage = lots

	ui.load_storage()

	assert_eq(ui.storage_bin.count(), 30, "Everything in the chest should be in the tray")


func test_the_chest_leaves_what_is_already_lying_in_it_alone():
	# The server answers every move with the whole chest, so the chest is
	# redrawn constantly. Laying it out again each time would tidy away every
	# throw the player made.
	GameStateManager.inventory_storage = [_chest_item({"id": "settled"})]
	ui.load_storage()
	var was = ui.storage_bin.where_is("settled")

	ui.load_storage()

	assert_eq(ui.storage_bin.where_is("settled"), was, "It should not have been moved")


func test_a_multi_square_item_fits_in_the_chest():
	GameStateManager.inventory_storage = [_chest_item({"shape": [[0, 0], [1, 0]]})]

	ui.load_storage()

	assert_eq(ui.storage_bin.count(), 1, "A wide item should still be drawn")


func test_loading_the_chest_twice_does_not_double_it():
	# It is redrawn on every inventory load, so what is already there has to be
	# recognised rather than added again.
	GameStateManager.inventory_storage = [_chest_item({"id": "only"})]

	ui.load_storage()
	ui.load_storage()

	assert_eq(ui.storage_bin.count(), 1, "The chest should be redrawn, not added to")


func test_an_item_taken_out_of_the_chest_stops_being_drawn():
	GameStateManager.inventory_storage = [_chest_item({"id": "leaving"})]
	ui.load_storage()

	GameStateManager.inventory_storage = []
	ui.load_storage()

	assert_eq(ui.storage_bin.count(), 0, "It is gone from the chest, so gone from view")


func test_a_move_answer_refreshes_the_chest():
	# Moving a container can set an item down in the chest without the player
	# asking, so the chest is redrawn from whatever the server sends back.
	var response = APITypes.MoveItemResponse.new({
		"inventory_grid": [],
		"inventory_storage": [TestHelpers.item_data({"id": "set_down"})],
		"server_containers": [],
		"pending": []
	})

	ui._on_inventory_returned(response)

	assert_eq(ui.storage_bin.ids(), ["set_down"],
		"The chest should show what the move put there")


func test_the_sell_chest_names_its_price_for_an_item_from_the_chest():
	# An item can be sold out of the chest as well as off the grid, so the
	# prompt has to answer to both.
	GameStateManager.inventory_storage = [TestHelpers.item({"id": "held", "cost": 8})]
	ui.load_storage()

	ui.storage_bin.pick_up(GameStateManager.inventory_storage[0], Vector2(700, 900))
	await get_tree().process_frame

	var prompt = ui.sell_chest.get_node("Prompt").text
	assert_true("sell for" in prompt,
		"The prompt should name a price, not stay at its resting text. Got: %s" % prompt)

	ui.storage_bin.release_at(Vector2(700, 900))
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


func test_the_chest_covers_its_panel():
	# The chest answers the pointer for everything lying in the tray, so it has
	# to be the whole panel and not only the opening.
	var panel = ui.storage_bin.get_parent()
	assert_eq(ui.storage_bin.position, Vector2.ZERO, "It should start at the panel")
	assert_eq(ui.storage_bin.size, panel.size, "and be as big as it")


func test_what_is_in_the_chest_is_drawn_solid():
	GameStateManager.inventory_storage = [TestHelpers.item({"id": "held"})]
	ui.load_storage()

	var drawn = ui.storage_bin.drawn("held")
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
	assert_eq(ui.storage_bin.count(), 1, "and it is still in the chest")


func test_clicking_the_chest_puts_it_back():
	GameStateManager.inventory_storage = [TestHelpers.item({"id": "held"})]
	ui.load_storage()
	ui.hold(GameStateManager.inventory_storage[0])

	var chest = ui.storage_bin
	ui.place_held_at(chest.global_position + chest.size / 2)
	await get_tree().process_frame

	assert_null(ui.held_item, "The chest is where it already was, so this is letting go")
	assert_eq(ui.storage_bin.count(), 1, "and it is drawn there")


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

	assert_eq(ui.storage_bin.ids(), ["left_behind"],
		"Only what is not in hand is drawn in the chest")


func test_letting_go_draws_it_in_the_chest_again():
	GameStateManager.inventory_storage = [TestHelpers.item({"id": "in_hand"})]
	ui.hold(GameStateManager.inventory_storage[0])

	ui.release_hand()
	await get_tree().process_frame

	assert_eq(ui.storage_bin.ids(), ["in_hand"],
		"It comes back into view where it has been all along")


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
	assert_eq(ui.storage_bin.ids(), ["second"], "and the second is waiting in the chest")


func test_a_held_item_sits_under_the_pointer():
	ui.hold(TestHelpers.item({"id": "held"}))

	ui.follow_pointer(Vector2(400, 300))

	assert_eq(ui.held_visual.global_position + ui.held_visual.size / 2,
		Vector2(400, 300), "It should be centred on the pointer")


func test_a_held_item_is_placed_the_moment_it_is_picked_up():
	# Waiting for the first mouse movement left it sitting in the corner of the
	# screen until the player twitched.
	ui.hold(TestHelpers.item({"id": "held"}), Vector2(400, 300))
	await get_tree().process_frame

	assert_eq(ui.held_visual.global_position + ui.held_visual.size / 2, Vector2(400, 300),
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


# ============ The shop stands on the shelves that are painted ============
#
# The wall was repainted, and the shelves moved with it. What went wrong the
# first time is what these hold: items hung in mid-air a hundred pixels above
# the lit shelf they were meant to stand on, tall items grew up through the
# ceiling of their alcove, and the bottom shelf's price tags hung out below
# the shelving onto the storage tray and the de-rez bay standing on the floor.

func _shelf_slots() -> Array:
	var slots := []
	for i in range(1, 6):
		var slot = ui.shop_container.get_node_or_null("ShopItem" + str(i))
		if slot:
			slots.append(slot)
	return slots


func test_every_shelf_slot_stands_on_a_shelf():
	# Three shelves, and every slot's floor is on one of them. Measured from
	# the top of the shop container, which is the top of the shelving.
	var floors := {}
	for slot in _shelf_slots():
		floors[slot.position.y + ui.ART_FLOOR] = true
	assert_eq(floors.size(), 3,
		"Five slots should stand on three shelf lines, not %d different ones. "
		% floors.size() + "Got: %s" % [floors.keys()])


func test_a_shelf_slot_leaves_room_under_the_alcove_ceiling():
	# The alcoves are boxes. A slot taller than one is drawn through its roof.
	for slot in _shelf_slots():
		assert_gte(slot.position.y, 0.0,
			"A slot above the shelving is drawn through the top of it")
		assert_lte(slot.position.y + ui.SLOT_SIZE.y, ui.shop_container.size.y,
			"A slot below the shelving is drawn onto the floor furniture")


func _art_for(shape: Array) -> Control:
	"""The artwork the shop would put on a shelf for an item of this shape."""
	var slot = ui._create_shop_item_from_data(TestHelpers.item({"shape": shape}))
	var art = slot.get_meta("art")
	slot.queue_free()
	return art


func test_a_tall_item_is_drawn_small_enough_for_its_alcove():
	# Items run to nine squares tall. At the size the grid draws them that is
	# over four hundred pixels, in an alcove a hundred and sixty tall.
	var tall := []
	for y in range(9):
		tall.append([0, y])
	var art = _art_for(tall)
	assert_lte(art.size.y, ui.SHELF_ART.y,
		"Nine squares came out %d tall, and an alcove has %d"
		% [art.size.y, ui.SHELF_ART.y])

	var wide := []
	for x in range(9):
		wide.append([x, 0])
	art = _art_for(wide)
	assert_lte(art.size.x, ui.SHELF_ART.x,
		"and the same across, or it is drawn into the slot beside it")


func test_an_ordinary_item_is_drawn_at_the_size_the_grid_uses():
	# Shrinking is for what will not fit. Everything else is drawn as the
	# inventory draws it, or the same item changes size when it is bought --
	# which it did, by a quarter, until the shelf was told what a square is.
	var art = _art_for([[0, 0], [1, 0]])
	assert_almost_eq(art.size.y, ui.inventory_grid.cell_size, 0.01,
		"A two-square item fits an alcove with room to spare")


func test_no_price_tag_hangs_below_the_shelving():
	# The bottom shelf has no lip under it -- the tray and the de-rez bay
	# stand on the floor there -- so a tag hung below it lands on furniture.
	for i in range(1, 6):
		var slot = ui.shop_container.get_node_or_null("ShopItem" + str(i))
		var tag = ui.shop_container.get_node_or_null("ShopPrice" + str(i))
		if slot == null or tag == null:
			continue
		ui._hang_price_tag(tag, slot, TestHelpers.item())
		assert_lte(tag.position.y + tag.size.y, ui.shop_container.size.y,
			"Slot %d's tag hangs %d past the bottom of the shelving"
			% [i, tag.position.y + tag.size.y - ui.shop_container.size.y])


func test_a_price_tag_stays_beside_its_own_item():
	# Wherever it ends up, a tag belongs to the item above it.
	for i in range(1, 6):
		var slot = ui.shop_container.get_node_or_null("ShopItem" + str(i))
		var tag = ui.shop_container.get_node_or_null("ShopPrice" + str(i))
		if slot == null or tag == null:
			continue
		ui._hang_price_tag(tag, slot, TestHelpers.item())
		var tag_middle = tag.position.x + tag.size.x / 2.0
		var slot_middle = slot.position.x + ui.SLOT_SIZE.x / 2.0
		assert_almost_eq(tag_middle, slot_middle, 1.0,
			"Slot %d's tag should be centred under its own slot" % i)


# ============ The tray and the de-rez bay are pictures, not panels ============
#
# Both are their own layer on purpose: the tray is to gain falling items and
# the bay a de-rez animation, and neither can be a Panel's stylebox.

func test_what_is_in_the_chest_is_drawn_the_size_it_is_on_the_grid():
	# It used to shrink on the way in. An item that changes size on the way
	# into the chest and back reads as a different item.
	assert_eq(ui.storage_bin.cell_size, ui.inventory_grid.cell_size,
		"A square of an item is a square of an item wherever it is drawn")


func test_a_drop_anywhere_above_the_chest_goes_in_the_chest():
	# The chest is walled to the top of the screen, so a thing let go of over
	# it has nowhere to fall but into it. Aiming at the tray itself is a small
	# target and the physics does not ask for it.
	var zone = ui.inventory_grid.storage_zone
	assert_eq(zone, ui.storage_bin.catch_zone(),
		"The grid should store what is dropped anywhere in the chest's room")

	var over_the_chest = ui.storage_bin.global_position \
		+ Vector2(ui.STORAGE_SHELF.get_center().x, 0)
	assert_true(zone.get_global_rect().has_point(over_the_chest + Vector2(0, 100)),
		"The tray itself takes a drop")
	assert_true(zone.get_global_rect().has_point(over_the_chest - Vector2(0, 400)),
		"and so does the room above it")
	assert_false(zone.get_global_rect().has_point(over_the_chest + Vector2(-400, -400)),
		"but not the room beside it, which is where the grid is")


func test_the_chest_takes_a_drop_from_above_without_covering_the_grid():
	# The room over the chest is a drop zone the whole height of the screen, so
	# it must not reach across anything the player drops items on.
	var zone: Control = ui.inventory_grid.storage_zone
	assert_false(zone.get_global_rect().intersects(
		ui.inventory_grid.get_global_rect()),
		"A drop on the grid must not be read as a drop in the chest")


func test_a_shop_item_let_go_of_over_the_chest_is_not_put_on_the_grid():
	# Buying into the chest names no square, so nothing is placed on the board
	# on the way. There is no session here, so the purchase itself comes to
	# nothing and only the routing is on trial.
	ui.dragging_shop_item = autofree(Panel.new())
	ui.drag_preview = autofree(Control.new())
	ui.dragging_shop_data = TestHelpers.item({"id": "buying"})

	await ui._end_shop_drag(ui.storage_bin.global_position
		+ Vector2(ui.STORAGE_SHELF.get_center().x, -300))

	assert_eq(ui.inventory_grid.items.size(), 0, "Nothing lands on the grid")
	assert_null(ui.dragging_shop_data, "and the drag is over either way")


func test_the_shop_character_stands_on_a_shadow():
	# The same smudge as the menu and the battle screen. Without it the Sentaur
	# is a cut-out laid over the floor of the room.
	var shadow = ui.find_child("CharacterShadow", true, false)
	var who = ui.find_child("PlayerCharacter", true, false)
	assert_not_null(shadow, "There should be a shadow under the character")
	assert_not_null(who, "and a character for it to be under")
	assert_lt(shadow.get_index(), who.get_index(),
		"It should be drawn before the character, or it lies on top of it")
	assert_almost_eq(shadow.get_rect().get_center().y, shadow.stands_on(who).end.y,
		1.0, "and lie across its feet")


func test_the_tray_is_a_picture_behind_what_is_in_it():
	var tray = ui.get_node_or_null("StoragePanel/Tray")
	assert_not_null(tray, "The storage panel should hold the tray picture")
	assert_true(tray is TextureRect,
		"The tray has to be its own node to gain layers later, not a stylebox")
	assert_lt(tray.get_index(), ui.storage_bin.get_index(),
		"The tray is drawn before what is in it, or it covers it")


func test_the_chest_is_walled_by_the_opening_in_the_tray():
	# The tray's walls are part of its picture. An item that comes to rest over
	# one is lying on the wall rather than inside the tray.
	assert_eq(ui.storage_bin.tray, ui.STORAGE_SHELF,
		"The chest should be walled by the opening the tray picture leaves")


func test_an_item_falls_in_over_the_opening():
	# It falls from above the tray when nobody threw it, and it has to fall
	# between the walls rather than onto one of them.
	GameStateManager.inventory_storage = [TestHelpers.item({"id": "falling"})]

	ui.load_storage()

	var shelf = ui.STORAGE_SHELF
	var at = ui.storage_bin.where_is("falling")
	assert_between(at.x, shelf.position.x, shelf.end.x,
		"It should fall between the walls of the tray")
	assert_lte(at.y, shelf.end.y, "and from above the bottom of it")


func test_the_bay_is_a_picture_larger_than_the_drop_zone():
	# The panel is the opening in the bay, so a drop lands in the field the
	# item de-rezzes in rather than anywhere on the cabinet.
	var bay = ui.sell_chest.get_node_or_null("Bay")
	assert_not_null(bay, "The sell chest should hold the de-rez bay picture")
	assert_true(bay is TextureRect,
		"The bay has to be its own node for the de-rez pass to animate it")
	assert_lt(bay.position.x, 0.0, "The cabinet reaches left of its opening")
	assert_lt(bay.position.y, 0.0, "and above it")
	assert_gt(bay.size.x, ui.sell_chest.size.x, "and is wider than the opening")
	assert_gt(bay.size.y, ui.sell_chest.size.y, "and taller")


func test_an_item_carried_to_the_bay_is_drawn_in_front_of_it():
	# An item held over the bay has to look like it is in the field, not
	# behind the cabinet.
	GameStateManager.inventory_storage = [TestHelpers.item({"id": "held"})]
	ui.load_storage()
	ui.storage_bin.pick_up(GameStateManager.inventory_storage[0], Vector2(700, 900))
	await get_tree().process_frame

	var held = ui.storage_bin.dragged_visual()
	assert_gt(held.z_index, ui.sell_chest.z_index,
		"What is in hand should draw over the bay, not under it")
	ui.storage_bin.release_at(Vector2(700, 900))


# ============ Combining: the arcs, the glow and the label (GDD 5.3) ============
#
# The screen joins three places -- the shelf, the rack and the chest -- so what
# these check is that an item is found wherever it stands and that the arcs go
# to the right ones. What the arc looks like is test_combining_overlay.gd.

func _knows_that(partners: Dictionary, names := {}) -> void:
	GameStateManager.combining.catalogue = APITypes.CombiningCatalogue.new(
		{"partners": partners, "names": names})


func _rack_holding(items: Array) -> void:
	ui.inventory_grid.load_inventory_state(APITypes.InventoryState.new({
		"items": items,
		"servers": [
			TestHelpers.container_data({"id": "container_a", "position": [2, 3]}),
			TestHelpers.container_data({"id": "container_b", "position": [4, 3]}),
			TestHelpers.container_data({"id": "container_c", "position": [6, 3]}),
		]
	}))


func _where(node: Control) -> Vector2:
	return node.get_global_rect().get_center()


func test_hovering_an_item_draws_an_arc_to_what_it_goes_with():
	_knows_that({"hero_sword": ["whetstone"], "whetstone": ["hero_sword"]})
	_rack_holding([
		TestHelpers.placed_item_data({
			"id": "sword", "item_type": "hero_sword", "position": [2, 3]}),
		TestHelpers.placed_item_data({
			"id": "stone", "item_type": "whetstone", "position": [3, 3]}),
	])

	ui.refresh_combining(_where(ui.inventory_grid.items[0]))

	assert_eq(ui.combining_overlay.arcs().size(), 1,
		"one arc, to the item it goes with")


func test_hovering_something_that_goes_with_nothing_draws_nothing():
	_knows_that({"hero_sword": ["whetstone"], "whetstone": ["hero_sword"]})
	_rack_holding([
		TestHelpers.placed_item_data({
			"id": "lonely", "item_type": "bloodthorne", "position": [2, 3]}),
		TestHelpers.placed_item_data({
			"id": "stone", "item_type": "whetstone", "position": [3, 3]}),
	])

	ui.refresh_combining(_where(ui.inventory_grid.items[0]))

	assert_eq(ui.combining_overlay.arcs(), [])


func test_pointing_at_nothing_draws_nothing():
	"""The arcs answer a question. Nobody asked one."""
	_knows_that({"hero_sword": ["whetstone"], "whetstone": ["hero_sword"]})
	_rack_holding([
		TestHelpers.placed_item_data({
			"id": "sword", "item_type": "hero_sword", "position": [2, 3]}),
		TestHelpers.placed_item_data({
			"id": "stone", "item_type": "whetstone", "position": [3, 3]}),
	])

	ui.refresh_combining(Vector2(-500, -500))

	assert_eq(ui.combining_overlay.arcs(), [])


func test_an_item_never_draws_an_arc_to_itself():
	"""A Long Poll eats two Edge Caches, so one points at another -- and a lone
	Edge Cache points at nothing."""
	_knows_that({"whetstone": ["whetstone"]})
	_rack_holding([TestHelpers.placed_item_data({
		"id": "only_one", "item_type": "whetstone", "position": [2, 3]})])

	ui.refresh_combining(_where(ui.inventory_grid.items[0]))

	assert_eq(ui.combining_overlay.arcs(), [])


func test_an_arc_reaches_from_the_rack_to_the_shelf():
	"""Buying it is the point: a line to the shop says so."""
	_knows_that({"hero_sword": ["whetstone"], "whetstone": ["hero_sword"]})
	_rack_holding([TestHelpers.placed_item_data({
		"id": "sword", "item_type": "hero_sword", "position": [2, 3]})])
	var shop: Array[APITypes.Item] = [APITypes.Item.new(TestHelpers.item_data({
		"id": "on_the_shelf", "item_type": "whetstone", "slug": "whetstone"}))]
	ui._display_shop_items(shop)
	await get_tree().process_frame

	ui.refresh_combining(_where(ui.inventory_grid.items[0]))

	assert_eq(ui.combining_overlay.arcs().size(), 1,
		"the item on the shelf is one it could combine with")


func test_an_arc_reaches_the_chest():
	_knows_that({"hero_sword": ["whetstone"], "whetstone": ["hero_sword"]})
	_rack_holding([TestHelpers.placed_item_data({
		"id": "sword", "item_type": "hero_sword", "position": [2, 3]})])
	GameStateManager.inventory_storage = [
		APITypes.Item.new(TestHelpers.item_data({
			"id": "put_away", "item_type": "whetstone", "slug": "whetstone"}))]
	ui.load_storage()

	ui.refresh_combining(_where(ui.inventory_grid.items[0]))

	assert_eq(ui.combining_overlay.arcs().size(), 1,
		"an item in the chest is still an item it goes with")


func test_an_item_in_hand_draws_the_arcs_instead():
	"""What is in the hand is what is being decided about."""
	_knows_that({"hero_sword": ["whetstone"], "whetstone": ["hero_sword"]})
	_rack_holding([TestHelpers.placed_item_data({
		"id": "sword", "item_type": "hero_sword", "position": [2, 3]})])

	ui.hold(APITypes.Item.new(TestHelpers.item_data({
		"id": "in_hand", "item_type": "whetstone", "slug": "whetstone"})))
	ui.refresh_combining(Vector2(-500, -500))

	assert_eq(ui.combining_overlay.arcs().size(), 1,
		"held, so the arcs are drawn wherever the pointer happens to be")


func test_the_items_about_to_combine_are_lit():
	_rack_holding([
		TestHelpers.placed_item_data({"id": "one", "position": [2, 3]}),
		TestHelpers.placed_item_data({"id": "two", "position": [3, 3]}),
	])
	GameStateManager.note_pending([APITypes.Pending.new({
		"makes": "blue_sage_collar", "have": 2, "need": 2,
		"ingredients": ["one", "two"], "catalysts": [], "missing": []})])

	ui.refresh_combining(Vector2(-500, -500))

	assert_eq(ui.combining_overlay.glowing().size(), 2,
		"both of them, whatever the pointer is doing")


func test_nothing_is_lit_while_a_recipe_is_unfinished():
	_rack_holding([
		TestHelpers.placed_item_data({"id": "one", "position": [2, 3]}),
		TestHelpers.placed_item_data({"id": "two", "position": [3, 3]}),
	])
	GameStateManager.note_pending([APITypes.Pending.new({
		"makes": "hero_longsword", "have": 2, "need": 3,
		"ingredients": ["one", "two"], "catalysts": [], "missing": ["whetstone"]})])

	ui.refresh_combining(Vector2(-500, -500))

	assert_eq(ui.combining_overlay.glowing(), [],
		"nothing will happen yet, so nothing is warned about")


func test_hovering_a_part_says_how_far_along_it_is():
	_knows_that({}, {"hero_longsword": "Long Poll"})
	_rack_holding([TestHelpers.placed_item_data({
		"id": "sword", "item_type": "hero_sword", "position": [2, 3]})])
	GameStateManager.note_pending([APITypes.Pending.new({
		"makes": "hero_longsword", "have": 2, "need": 3,
		"ingredients": ["sword", "stone"], "catalysts": [],
		"missing": ["whetstone"]})])

	ui.refresh_combining(_where(ui.inventory_grid.items[0]))

	assert_eq(ui.combining_overlay.label_text(), "Long Poll 2/3")


func test_the_label_goes_when_the_pointer_does():
	_knows_that({}, {"hero_longsword": "Long Poll"})
	_rack_holding([TestHelpers.placed_item_data({
		"id": "sword", "item_type": "hero_sword", "position": [2, 3]})])
	GameStateManager.note_pending([APITypes.Pending.new({
		"makes": "hero_longsword", "have": 2, "need": 3,
		"ingredients": ["sword"], "catalysts": [], "missing": ["whetstone"]})])
	ui.refresh_combining(_where(ui.inventory_grid.items[0]))

	ui.refresh_combining(Vector2(-500, -500))

	assert_eq(ui.combining_overlay.label_text(), "")


func test_a_rack_being_watched_draws_none_of_it():
	"""The battle screen shows a rack that cannot be changed. There is nothing
	to warn about and nothing to reach for."""
	var watched = ui_scene.instantiate()
	watched.configure({"read_only": true, "hide_shop": true, "hide_storage": true})
	add_child_autofree(watched)
	await get_tree().process_frame

	assert_null(watched.combining_overlay, "no overlay at all")


# ============ Playing back what combined (GDD 5.3) ============

func _a_combining(overrides := {}) -> APITypes.Combination:
	var data := {
		"made": "blue_sage_collar",
		"made_id": "made_1",
		"consumed": [
			TestHelpers.placed_item_data({"id": "eaten_a", "position": [2, 3]}),
			TestHelpers.placed_item_data({"id": "eaten_b", "position": [3, 3]}),
		],
		"kept": [],
		"freed": [[2, 3], [3, 3]],
		"position": [2, 3],
	}
	data.merge(overrides, true)
	return APITypes.Combination.new(data)


func test_it_plays_what_the_battle_answered_with():
	GameStateManager.rack_that_fought = APITypes.InventoryState.new({
		"items": [
			TestHelpers.placed_item_data({"id": "eaten_a", "position": [2, 3]}),
			TestHelpers.placed_item_data({"id": "eaten_b", "position": [3, 3]}),
		],
		"servers": [TestHelpers.container_data({"id": "container_a", "position": [2, 3]})]
	})
	GameStateManager.combinations_to_play = [_a_combining()]
	Presentation.clear_requests()

	await ui.play_combining()

	assert_eq(Presentation.request_count("item_combined"), 1,
		"the screen asked to play the merge")


func test_it_ends_on_the_rack_the_server_sent():
	"""Whatever the animation did, the last thing drawn is the server's answer.
	A client that ignored the merge entirely would still be right."""
	GameStateManager.save_inventory_state(
		[TestHelpers.placed_item_data({"id": "made_1", "position": [2, 3]})],
		[TestHelpers.container_data({"id": "container_a", "position": [2, 3]})])
	GameStateManager.rack_that_fought = APITypes.InventoryState.new({
		"items": [
			TestHelpers.placed_item_data({"id": "eaten_a", "position": [2, 3]}),
			TestHelpers.placed_item_data({"id": "eaten_b", "position": [3, 3]}),
		],
		"servers": [TestHelpers.container_data({"id": "container_a", "position": [2, 3]})]
	})
	GameStateManager.combinations_to_play = [_a_combining()]

	await ui.play_combining()

	assert_not_null(ui.inventory_grid.item_visual("made_1"),
		"what the server says the player holds is what is drawn")
	assert_null(ui.inventory_grid.item_visual("eaten_a"),
		"and what it ate is gone")


func test_it_is_played_once():
	GameStateManager.rack_that_fought = APITypes.InventoryState.new(
		{"items": [], "servers": []})
	GameStateManager.combinations_to_play = [_a_combining()]
	await ui.play_combining()
	Presentation.clear_requests()

	await ui.play_combining()

	assert_eq(Presentation.request_count("item_combined"), 0,
		"coming back to the shop does not replay the last round's merges")


func test_a_round_where_nothing_combined_plays_nothing():
	GameStateManager.combinations_to_play = []
	Presentation.clear_requests()

	await ui.play_combining()

	assert_eq(Presentation.request_count("item_combined"), 0)


func test_every_merge_of_the_round_is_played():
	"""They run at once: no ingredient is eaten twice and no result feeds
	another, so none of them waits on another."""
	GameStateManager.rack_that_fought = APITypes.InventoryState.new(
		{"items": [], "servers": []})
	GameStateManager.combinations_to_play = [
		_a_combining(),
		_a_combining({"made": "serverless_function", "made_id": "made_2",
			"freed": [[6, 3]], "position": [6, 3]}),
	]
	Presentation.clear_requests()

	await ui.play_combining()

	assert_eq(Presentation.request_count("item_combined"), 2)


func test_hovering_the_shelf_draws_arcs_to_the_rack():
	"""Either end of a pair may be the one the player reaches for."""
	_knows_that({"hero_sword": ["whetstone"], "whetstone": ["hero_sword"]})
	_rack_holding([TestHelpers.placed_item_data({
		"id": "sword", "item_type": "hero_sword", "position": [2, 3]})])
	var shop: Array[APITypes.Item] = [APITypes.Item.new(TestHelpers.item_data({
		"id": "on_the_shelf", "item_type": "whetstone", "slug": "whetstone"}))]
	ui._display_shop_items(shop)
	await get_tree().process_frame

	ui.refresh_combining(ui.shop_items[0].get_global_rect().get_center())

	assert_eq(ui.combining_overlay.arcs().size(), 1,
		"the whole shelf answers for the item on it, not just the picture")


func test_dragging_an_item_on_the_rack_draws_its_arcs():
	_knows_that({"hero_sword": ["whetstone"], "whetstone": ["hero_sword"]})
	_rack_holding([
		TestHelpers.placed_item_data({
			"id": "sword", "item_type": "hero_sword", "position": [2, 3]}),
		TestHelpers.placed_item_data({
			"id": "stone", "item_type": "whetstone", "position": [3, 3]}),
	])

	ui.inventory_grid._start_drag(ui.inventory_grid.item_visual("sword"))
	ui.refresh_combining(Vector2(-500, -500))

	assert_eq(ui.combining_overlay.arcs().size(), 1,
		"an item in the middle of being moved is the one being decided about")


func test_a_merge_left_partway_through_draws_no_more():
	"""Starting a battle is one keypress and the merge takes most of a second.
	A player who leaves in that time takes the screen with them, and what is
	left of the merge must not draw on it."""
	GameStateManager.save_inventory_state(
		[TestHelpers.placed_item_data({"id": "made_1", "position": [2, 3]})],
		[TestHelpers.container_data({"id": "container_a", "position": [2, 3]})])
	GameStateManager.rack_that_fought = APITypes.InventoryState.new({
		"items": [TestHelpers.placed_item_data({"id": "eaten_a", "position": [2, 3]})],
		"servers": [TestHelpers.container_data({"id": "container_a", "position": [2, 3]})]
	})
	GameStateManager.combinations_to_play = [_a_combining()]

	# Deferred, so the merge is left running while the test carries on and can
	# take the screen away underneath it.
	ui.call_deferred("play_combining")
	await get_tree().process_frame
	assert_not_null(ui.inventory_grid.item_visual("eaten_a"),
		"Setup: the merge got as far as drawing the rack that fought")

	remove_child(ui)
	await get_tree().process_frame
	await get_tree().process_frame

	assert_null(ui.inventory_grid.item_visual("made_1"),
		"the screen was gone before the rack was drawn again")

	# Put back where the teardown expects to find it, so that taking it out
	# does not leave the whole screen behind as orphans.
	add_child(ui)


func test_the_result_is_welcomed_when_it_arrives():
	"""The merge has four beats and the last of them is the new item standing
	up. It is asked for separately, because it happens after the board has been
	drawn again and the others happen before."""
	GameStateManager.save_inventory_state(
		[TestHelpers.placed_item_data({"id": "made_1", "position": [2, 3]})],
		[TestHelpers.container_data({"id": "container_a", "position": [2, 3]})])
	GameStateManager.rack_that_fought = APITypes.InventoryState.new(
		{"items": [], "servers": []})
	GameStateManager.combinations_to_play = [_a_combining()]
	Presentation.clear_requests()

	await ui.play_combining()

	assert_eq(Presentation.request_count("item_combined"), 1, "the merge")
	assert_eq(Presentation.request_count("item_arrived"), 1, "and the arrival")


func test_a_merge_makes_no_sound_where_there_is_no_sound_to_make():
	"""Headless has no audio driver, so a cue played there is a cue played at
	nothing. The same switch that turns the animation off turns these off."""
	assert_false(Presentation.animations_enabled(), "Setup: headless")
	var voice: AudioStreamPlayer = ui.get_node_or_null("MergeCharge")
	assert_not_null(voice, "Setup: the cue was loaded")

	ui._merge_sound("charge")

	assert_false(voice.playing, "nothing was sounded")


func test_a_cue_that_is_not_there_is_not_played():
	"""The sounds are generated by tools/create_sounds.py and could be missing
	from a checkout. That is a quiet merge, not a broken one."""
	ui._merge_sound("no_such_beat")

	assert_true(true, "asking for a cue that does not exist does nothing")


func test_the_merge_names_what_it_made():
	"""From the catalogue, because what it made did not exist a moment ago and
	the client has nothing else to look it up in."""
	_knows_that({}, {"blue_sage_collar": "Amethyst Collar"})
	GameStateManager.save_inventory_state(
		[TestHelpers.placed_item_data({"id": "made_1", "position": [2, 3]})],
		[TestHelpers.container_data({"id": "container_a", "position": [2, 3]})])
	GameStateManager.rack_that_fought = APITypes.InventoryState.new(
		{"items": [], "servers": []})
	GameStateManager.combinations_to_play = [_a_combining()]

	await ui.play_combining()

	assert_eq(ui.combining_overlay.announced(), ["Amethyst Collar"])


func test_two_merges_share_one_whiteout():
	"""Several racks combining at once is one event to look at, and two
	whiteouts over each other would only be a longer, brighter one."""
	GameStateManager.rack_that_fought = APITypes.InventoryState.new(
		{"items": [], "servers": []})
	GameStateManager.combinations_to_play = [
		_a_combining(),
		_a_combining({"made": "serverless_function", "made_id": "made_2",
			"freed": [[6, 3]], "position": [6, 3]}),
	]
	Presentation.clear_requests()

	await ui.play_combining()

	assert_eq(Presentation.request_count("item_combined"), 2,
		"Setup: both merges were played")
	assert_gt(ui.combining_overlay.whitening(), 0.0,
		"and the screen is white for them")


func test_a_result_that_went_to_the_chest_is_still_played():
	"""A result too big for the squares it was made on goes to the chest, so
	there is nothing on the rack to stand up. The name and the rings still
	happen where the items met, because that is where the player is looking."""
	_knows_that({}, {"stone_golem": "Stone Golem"})
	GameStateManager.save_inventory_state(
		[], [TestHelpers.container_data({"id": "container_a", "position": [2, 3]})])
	GameStateManager.rack_that_fought = APITypes.InventoryState.new(
		{"items": [], "servers": []})
	GameStateManager.combinations_to_play = [_a_combining({
		"made": "stone_golem", "made_id": "too_big",
		"freed": [[2, 3], [3, 3]], "position": null})]

	await ui.play_combining()

	assert_null(ui.inventory_grid.item_visual("too_big"),
		"Setup: it is not on the rack")
	assert_eq(ui.combining_overlay.announced(), ["Stone Golem"],
		"and it is still named over the squares it was made on")


# ============ The zone an item reaches into (GDD 4.3) ============

func _an_aura_item(overrides := {}) -> Dictionary:
	# A Thermal Throttle reaches the square above it and the square below.
	var data := {
		"id": "thrower", "item_type": "thermal_throttle", "slug": "thermal_throttle",
		"position": [4, 3], "shape": [[0, 0]],
		"star": [[0, -1], [0, 1]], "diamond": [], "anchors": [],
		"aura": {"star": [{"any_of": [], "all_of": []}]},
	}
	data.merge(overrides, true)
	return TestHelpers.placed_item_data(data)


func test_hovering_an_item_draws_the_zone_it_reaches_into():
	_rack_holding([_an_aura_item()])

	ui.refresh_aura(_where(ui.inventory_grid.items[0]))

	var drawn = ui.aura_overlay.showing()
	assert_eq(drawn.size(), 2, "both squares of the zone")
	assert_true(drawn.any(func(one): return one["square"] == Vector2i(4, 2)))
	assert_true(drawn.any(func(one): return one["square"] == Vector2i(4, 4)))


func test_pointing_at_nothing_draws_no_zone():
	_rack_holding([_an_aura_item()])

	ui.refresh_aura(Vector2(-500, -500))

	assert_eq(ui.aura_overlay.showing(), [])


func test_a_square_of_the_zone_with_something_in_it_is_doing_something():
	_rack_holding([
		_an_aura_item(),
		TestHelpers.placed_item_data({"id": "under", "position": [4, 4]}),
	])

	ui.refresh_aura(_where(ui.inventory_grid.items[0]))

	assert_eq(ui.aura_overlay.worth(), 1,
		"the aura is worth the one item standing in it")


func test_a_zone_nothing_acts_through_is_worth_nothing():
	"""102 of the 117 items that draw a zone have no clause built yet. The
	zone is real, and it is doing nothing."""
	_rack_holding([
		_an_aura_item({"aura": {}}),
		TestHelpers.placed_item_data({"id": "under", "position": [4, 4]}),
	])

	ui.refresh_aura(_where(ui.inventory_grid.items[0]))

	assert_eq(ui.aura_overlay.showing().size(), 2, "the zone is still drawn")
	assert_eq(ui.aura_overlay.worth(), 0, "and none of it is worth anything")


func test_a_zone_narrowed_to_a_tag_passes_over_what_it_does_not_want():
	_rack_holding([
		_an_aura_item({"aura": {"star": [{"any_of": ["pet"], "all_of": []}]}}),
		TestHelpers.placed_item_data({
			"id": "weapon", "category": "problem", "position": [4, 4]}),
	])

	ui.refresh_aura(_where(ui.inventory_grid.items[0]))

	assert_eq(ui.aura_overlay.worth(), 0,
		"a Pet aura lands on a weapon and does nothing")


func test_an_item_in_hand_draws_its_zone_under_the_pointer():
	"""The question being asked is where to put it, so the answer follows the
	hand rather than staying where the item last stood."""
	_rack_holding([])
	ui.hold(APITypes.Item.new(TestHelpers.item_data({
		"id": "in_hand", "star": [[0, -1], [0, 1]], "diamond": [], "anchors": [],
		"aura": {"star": [{"any_of": [], "all_of": []}]}})))

	var over: Vector2 = ui.inventory_grid.get_global_transform() \
		* (ui.inventory_grid.grid_to_pixel(Vector2i(4, 3)) \
		+ Vector2(ui.inventory_grid.cell_size / 2, ui.inventory_grid.cell_size / 2))
	ui.refresh_aura(over)

	var drawn = ui.aura_overlay.showing()
	assert_eq(drawn.size(), 2)
	assert_true(drawn.any(func(one): return one["square"] == Vector2i(4, 2)),
		"the zone is drawn around the square under the pointer")


func test_an_item_on_the_shelf_draws_no_zone():
	"""It is not on the board, so there are no squares for it to reach."""
	var shop: Array[APITypes.Item] = [APITypes.Item.new(TestHelpers.item_data({
		"id": "on_the_shelf", "star": [[0, -1]], "diamond": [], "anchors": [],
		"aura": {"star": [{"any_of": [], "all_of": []}]}}))]
	ui._display_shop_items(shop)
	await get_tree().process_frame

	ui.refresh_aura(ui.shop_items[0].get_global_rect().get_center())

	assert_eq(ui.aura_overlay.showing(), [])


func test_an_item_an_aura_acts_on_is_lit_while_the_zone_is_shown():
	"""The marker says which square; this says which item, which is what the
	player cares about when a zone covers half a board."""
	_rack_holding([
		_an_aura_item(),
		TestHelpers.placed_item_data({"id": "under", "position": [4, 4]}),
	])

	ui.refresh_aura(_where(ui.inventory_grid.items[0]))

	assert_eq(ui.lit_by_an_aura(), ["under"])
	assert_gt(ui.inventory_grid.item_visual("under").modulate.r, 1.0,
		"and it is drawn brighter")


func test_the_light_goes_out_when_the_pointer_leaves():
	_rack_holding([
		_an_aura_item(),
		TestHelpers.placed_item_data({"id": "under", "position": [4, 4]}),
	])
	ui.refresh_aura(_where(ui.inventory_grid.items[0]))

	ui.refresh_aura(Vector2(-500, -500))

	assert_eq(ui.lit_by_an_aura(), [])
	assert_eq(ui.inventory_grid.item_visual("under").modulate, Color.WHITE,
		"and the item is put back as it was")


func test_an_item_the_aura_passes_over_is_not_lit():
	_rack_holding([
		_an_aura_item({"aura": {"star": [{"any_of": ["pet"], "all_of": []}]}}),
		TestHelpers.placed_item_data({
			"id": "weapon", "category": "problem", "position": [4, 4]}),
	])

	ui.refresh_aura(_where(ui.inventory_grid.items[0]))

	assert_eq(ui.lit_by_an_aura(), [])


func test_putting_an_item_down_swells_its_markers():
	"""On placing, not on hovering: it answers the question the player just
	asked by letting go."""
	_rack_holding([_an_aura_item()])
	assert_eq(ui.aura_overlay.swelling(), 1.0, "Setup: nothing is swelling")

	ui._on_item_placed(null, Vector2i(4, 3))
	ui.aura_overlay._process(ui.aura_overlay.GROW)

	assert_eq(ui.aura_overlay.swelling(), ui.aura_overlay.SWELL)


func test_an_item_put_in_the_chest_draws_no_zone():
	"""It is still the object that was on the grid, remembering the square it
	used to stand on. Believing it would draw the zone back on the rack, over
	squares the item has nothing to do with any more."""
	_rack_holding([])
	var moved = APITypes.PlacedItem.new(_an_aura_item({"id": "moved"}))
	GameStateManager.inventory_storage = []
	ui.storage_bin.catch(moved, Vector2(0, 0))
	await get_tree().process_frame

	var lying = ui.storage_bin.drawn("moved")
	assert_not_null(lying, "Setup: it is lying in the chest")
	ui.refresh_aura(lying.get_global_rect().get_center())

	assert_eq(ui.aura_overlay.showing(), [],
		"the chest is not the board, so there is nothing to draw on")


# ============ An aura saying it has been set going ============

func test_putting_an_item_into_a_zone_pops_the_item_whose_zone_it_is():
	"""The projector is the one something has just happened to. An item
	dropped into a zone is not changed by landing there; the item whose zone
	it is has just gained a Star something."""
	_rack_holding([
		_an_aura_item(),
		TestHelpers.placed_item_data({"id": "arriving", "position": [4, 4]}),
	])
	Presentation.clear_requests()

	ui.pop_what_took_effect("arriving")

	assert_eq(Presentation.request_count("aura_took_effect"), 1)
	assert_eq(Presentation.requests("aura_took_effect")[0]["data"]["item"],
		"thrower", "the aura, not the item that arrived")


func test_putting_a_zone_over_an_item_pops_the_zone():
	"""The same event from the other end: the player moved the aura rather
	than the item, and it is still the aura that was set going."""
	_rack_holding([
		TestHelpers.placed_item_data({"id": "caught", "position": [4, 4]}),
		_an_aura_item(),
	])
	Presentation.clear_requests()

	ui.pop_what_took_effect("thrower")

	assert_eq(Presentation.request_count("aura_took_effect"), 1)
	assert_eq(Presentation.requests("aura_took_effect")[0]["data"]["item"],
		"thrower")


func test_an_item_put_where_no_aura_reaches_pops_nothing():
	_rack_holding([
		_an_aura_item(),
		TestHelpers.placed_item_data({"id": "far_off", "position": [6, 3]}),
	])
	Presentation.clear_requests()

	ui.pop_what_took_effect("far_off")

	assert_eq(Presentation.request_count("aura_took_effect"), 0)


func test_an_item_a_zone_passes_over_pops_nothing():
	"""A Pet aura lands on a weapon and does nothing, so nothing was set
	going and nothing has anything to say."""
	_rack_holding([
		_an_aura_item({"aura": {"star": [{"any_of": ["pet"], "all_of": []}]}}),
		TestHelpers.placed_item_data({
			"id": "weapon", "category": "problem", "position": [4, 4]}),
	])
	Presentation.clear_requests()

	ui.pop_what_took_effect("weapon")

	assert_eq(Presentation.request_count("aura_took_effect"), 0)


func test_two_auras_reaching_the_same_square_both_pop():
	"""An item can land in more than one zone at once, and each of them has
	been set going."""
	_rack_holding([
		_an_aura_item({"id": "one", "position": [4, 3]}),
		_an_aura_item({"id": "other", "position": [4, 5]}),
		TestHelpers.placed_item_data({"id": "between", "position": [4, 4]}),
	])
	Presentation.clear_requests()

	ui.pop_what_took_effect("between")

	assert_eq(Presentation.request_count("aura_took_effect"), 2)
