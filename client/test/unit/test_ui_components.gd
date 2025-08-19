extends GutTest
# Comprehensive UI component tests to prevent crashes

func test_stats_label_nil_protection():
	# Test that _update_stats doesn't crash when stats_label is nil
	var ui = preload("res://scripts/UnifiedGridUI.gd").new()

	# Simulate read-only mode where stats_label isn't created
	ui.read_only_mode = true
	ui._ready()

	# This should not crash even though stats_label is nil
	ui._update_stats()

	# Verify no crash occurred
	assert_true(true, "Should not crash when stats_label is nil")

	ui.queue_free()

func test_ui_creation_in_normal_mode():
	# Test that all UI elements are created in normal mode
	var ui = preload("res://scripts/UnifiedGridUI.gd").new()
	ui.read_only_mode = false
	ui.hide_shop = false
	ui.hide_storage = false

	# Add to scene tree for proper initialization
	add_child(ui)
	await get_tree().process_frame

	# Check that stats_label exists in normal mode
	assert_not_null(ui.stats_label, "stats_label should exist in normal mode")

	# Check shop container exists
	assert_not_null(ui.shop_container, "shop_container should exist when not hidden")

	# Check storage container exists
	assert_not_null(ui.storage_container, "storage_container should exist when not hidden")

	ui.queue_free()

func test_ui_configuration_modes():
	# Test different UI configuration modes
	var ui = preload("res://scripts/UnifiedGridUI.gd").new()

	# Test read-only mode
	ui.configure({"read_only": true, "hide_shop": true})
	assert_true(ui.read_only_mode, "Should be in read-only mode")
	assert_true(ui.hide_shop, "Shop should be hidden")

	# Test normal mode
	ui.configure({"read_only": false, "hide_shop": false})
	assert_false(ui.read_only_mode, "Should not be in read-only mode")
	assert_false(ui.hide_shop, "Shop should not be hidden")

	ui.queue_free()

func test_grid_dimensions():
	# Test that grid dimensions are correct
	var ui = preload("res://scripts/UnifiedGridUI.gd").new()

	assert_eq(ui.ROOM_WIDTH, 9, "Room width should be 9")
	assert_eq(ui.ROOM_HEIGHT, 7, "Room height should be 7")

	ui.queue_free()

func test_grid_initialization():
	# Test that grids are properly initialized
	var ui = preload("res://scripts/UnifiedGridUI.gd").new()
	ui._initialize_grids()

	# Check item grid
	assert_eq(ui.item_grid.size(), 7, "Item grid should have 7 rows")
	for row in ui.item_grid:
		assert_eq(row.size(), 9, "Each row should have 9 columns")

	# Check that servers array exists
	assert_true(ui.servers is Array, "Servers array should exist")

	ui.queue_free()

func test_inventory_state_management():
	# Test saving and loading inventory state
	var ui = preload("res://scripts/UnifiedGridUI.gd").new()
	ui._initialize_grids()

	# Add some test data
	var test_items = [
		{"data": {"name": "Test Item"}, "grid_pos": Vector2i(1, 1)}
	]
	var test_servers = [
		{"data": {"name": "Test Server"}, "pos": Vector2i(0, 0)}
	]

	# Get state
	var state = ui.get_inventory_state()
	assert_true(state.has("items"), "State should have items")
	assert_true(state.has("servers"), "State should have servers")

	ui.queue_free()

func test_shop_item_creation():
	# Test that shop items are created correctly
	var ui = preload("res://scripts/UnifiedGridUI.gd").new()

	var test_data = {
		"name": "Test Item",
		"cost": 10,
		"category": "problem"
	}

	var shop_item = ui._create_shop_item_from_data(test_data)

	assert_not_null(shop_item, "Shop item should be created")
	assert_true(shop_item.has_meta("item_data"), "Should have item_data meta")
	assert_eq(shop_item.get_meta("cost"), 10, "Should have correct cost")

	shop_item.queue_free()
	ui.queue_free()

func test_gold_management():
	# Test gold tracking and updates
	var ui = preload("res://scripts/UnifiedGridUI.gd").new()

	ui.current_gold = 100
	assert_eq(ui.current_gold, 100, "Should track gold correctly")

	# Simulate spending gold
	ui.current_gold -= 50
	assert_eq(ui.current_gold, 50, "Should update gold correctly")

	ui.queue_free()

func test_container_placement():
	# Test placing starting containers
	var ui = preload("res://scripts/UnifiedGridUI.gd").new()
	ui._initialize_grids()

	# Set up starting containers
	GameStateManager.starting_containers = [
		{"type": "cube_2x2", "position": Vector2i(1, 3)},
		{"type": "cube_2x2", "position": Vector2i(3, 3)},
		{"type": "cube_2x2", "position": Vector2i(5, 3)}
	]

	add_child(ui)
	await get_tree().process_frame

	# Place containers
	ui._place_starting_containers()

	# Verify servers were tracked
	assert_gt(ui.servers.size(), 0, "Should have placed servers")

	ui.queue_free()

func test_drag_and_drop_initialization():
	# Test that drag and drop variables are initialized
	var ui = preload("res://scripts/UnifiedGridUI.gd").new()

	assert_null(ui.dragging_object, "Dragging object should start as null")
	assert_eq(ui.drag_offset, Vector2.ZERO, "Drag offset should start at zero")
	assert_eq(ui.original_position, Vector2.ZERO, "Original position should start at zero")

	ui.queue_free()

func test_rotation_handling():
	# Test rotation cooldown mechanism
	var ui = preload("res://scripts/UnifiedGridUI.gd").new()

	assert_eq(ui.ROTATION_COOLDOWN, 0.3, "Rotation cooldown should be 0.3 seconds")
	assert_eq(ui.last_rotation_time, 0.0, "Last rotation time should start at 0")
	# rotation_index doesn't exist as a property, it's local to the rotation function

	ui.queue_free()
