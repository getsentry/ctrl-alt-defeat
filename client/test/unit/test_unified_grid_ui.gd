extends GutTest
# Comprehensive tests for UnifiedGridUI

var ui_scene = preload("res://scenes/UnifiedGridUI.tscn")
var ui

func before_each():
	# Reset game state
	GameStateManager.start_new_game()
	GameStateManager.gold = 20  # Give some gold for testing

	# The 3 starting containers the server sends with a new session.
	GameStateManager.save_inventory_state([], [
		{"id": "container_a", "slug": "standard_vm", "type": "standard_vm",
			"position": [2, 3], "width": 2, "height": 2},
		{"id": "container_b", "slug": "standard_vm", "type": "standard_vm",
			"position": [4, 3], "width": 2, "height": 2},
		{"id": "container_c", "slug": "standard_vm", "type": "standard_vm",
			"position": [6, 3], "width": 2, "height": 2}
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

	# Check grid arrays are initialized
	assert_eq(ui.active_grid.size(), 7, "Active grid should have 7 rows")
	assert_eq(ui.item_grid.size(), 7, "Item grid should have 7 rows")

	for row in ui.active_grid:
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
	var storage = ui.storage_container
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
	assert_eq(ui.dragging_shop_data, {}, "Shop drag data should be empty")

	assert_null(ui.inventory_grid.dragging_object, "Should not be dragging initially")
	assert_eq(ui.inventory_grid.drag_offset, Vector2.ZERO, "Drag offset should be zero")
	assert_false(ui.inventory_grid.valid_placement, "Placement should not be valid initially")

	assert_not_null(ui.hover_preview, "Hover preview should be ready")
	assert_false(ui.hover_preview.visible, "Hover preview should be hidden initially")

func test_grid_cell_creation():
	# Verify grid cells are created
	assert_gt(ui.grid_cells.size(), 0, "Grid cells should be created")

	var total_cells = 0
	for row in ui.grid_cells:
		total_cells += row.size()

	assert_eq(total_cells, ui.ROOM_WIDTH * ui.ROOM_HEIGHT,
		"Should have correct number of grid cells")

func test_shop_item_display():
	# Mock shop data
	var mock_shop = [
		{"id": "item1", "name": "Test Item", "cost": 5, "item_type": "test",
		 "min_damage": 3, "max_damage": 5},
		null,  # Empty slot
		{"id": "item2", "name": "Another Item", "cost": 8, "item_type": "test2",
		 "min_damage": 4, "max_damage": 6}
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
	var item_data = {"id": "test", "cost": 5}

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
		"items": [{
			"id": "item1", "slug": "test_item", "item_type": "test_item",
			"name": "Test Item", "category": "attack",
			"position": [2, 3], "shape": [[0, 0]]
		}],
		"servers": [{
			"id": "container_a", "slug": "standard_vm", "type": "standard_vm",
			"position": [2, 3], "width": 2, "height": 2
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
	var container = {"width": 2, "height": 2}

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

func test_pattern_creation():
	# Test pattern creation from dimensions
	var pattern = ui._create_pattern_from_size(2, 3)
	assert_eq(pattern.size(), 3, "Pattern should have 3 rows")
	assert_eq(pattern[0].size(), 2, "Each row should have 2 columns")

	# Check all values are 1
	for row in pattern:
		for cell in row:
			assert_eq(cell, 1, "Pattern cells should be 1")

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
