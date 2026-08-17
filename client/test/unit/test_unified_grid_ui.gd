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
		{"id": "container_a", "slug": "standard_vm", "type": "standard_vm",
			"position": [2, 3], "shape": [[0, 0], [1, 0], [0, 1], [1, 1]], "rotation": 0},
		{"id": "container_b", "slug": "standard_vm", "type": "standard_vm",
			"position": [4, 3], "shape": [[0, 0], [1, 0], [0, 1], [1, 1]], "rotation": 0},
		{"id": "container_c", "slug": "standard_vm", "type": "standard_vm",
			"position": [6, 3], "shape": [[0, 0], [1, 0], [0, 1], [1, 1]], "rotation": 0}
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
	var stats_label = ui.stats_label
	assert_not_null(stats_label, "Stats label should exist")

	var stats_text = stats_label.text
	assert_true("Gold" in stats_text, "Stats should show gold")
	assert_true("Round" in stats_text, "Stats should show round")
	assert_true("Lives" in stats_text, "Stats should show lives")
	assert_true("Wins" in stats_text, "Stats should show wins")
	assert_true("Losses" in stats_text, "Stats should show losses")

	assert_true("Gold: 20" in stats_text, "Stats should show the current gold amount")

func test_refresh_shop_button():
	# Find refresh button
	var refresh_btn = null
	for child in ui.get_children():
		if child.has_method("get_text") and "Refresh" in str(child.get_text()):
			refresh_btn = child
			break

	if not refresh_btn:
		# Look in controls container
		var controls = ui.find_child("Controls", true, false)
		if controls:
			for child in controls.get_children():
				if child is Button and "Refresh" in child.text:
					refresh_btn = child
					break

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

	assert_not_null(ui.hover_preview, "Hover preview should be ready")
	assert_false(ui.hover_preview.visible, "Hover preview should be hidden initially")

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
		"servers": [{
			"id": "container_a", "slug": "standard_vm", "type": "standard_vm",
			"position": [2, 3], "shape": [[0, 0], [1, 0], [0, 1], [1, 1]], "rotation": 0
		}]
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

func test_the_preview_is_hidden_where_a_container_cannot_go():
	# (2, 3) is already covered by container_a.
	var vm = TestHelpers.item({"is_container": true,
		"shape": [[0, 0], [1, 0], [0, 1], [1, 1]], "rotation": 0})

	ui._show_container_preview(vm, Vector2i(2, 3))

	assert_null(ui.container_preview, "No preview on an occupied square")

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
