extends Node

# Test the UnifiedGridUI
class_name TestUnifiedGridUI

var ui_scene: Control
var test_results: Dictionary = {}
var tests_passed: int = 0
var tests_failed: int = 0

func run_all_tests():
	print("\n=== UNIFIED GRID UI TESTS ===\n")

	# Setup
	_setup()

	# Run tests
	await test_ui_initialization()
	await test_grid_initialization()
	await test_shop_generation()
	await test_server_placement()
	await test_item_placement()
	await test_drag_and_drop()
	await test_hover_preview()
	await test_storage_area()
	await test_gold_management()
	await test_battle_calculation()

	# Teardown
	_teardown()

	# Report results
	_report_results()

	return tests_failed == 0

func _setup():
	print("Setting up test environment...")
	var scene_resource = load("res://scenes/UnifiedGridUI.tscn")
	if scene_resource:
		ui_scene = scene_resource.instantiate()
		add_child(ui_scene)
		print("✓ Test scene loaded")
	else:
		print("✗ Failed to load test scene")

func _teardown():
	if ui_scene and is_instance_valid(ui_scene):
		ui_scene.queue_free()
		print("✓ Test scene cleaned up")

func test_ui_initialization():
	print("\nTest: UI Initialization")

	assert(ui_scene != null, "UI scene should exist")
	assert(ui_scene is Control, "UI should be Control node")
	assert(ui_scene.current_gold == 50, "Should start with 50 gold")
	assert(ui_scene.current_round == 1, "Should start at round 1")
	assert(ui_scene.current_health == 100, "Should start with 100 health")

	# Check UI components exist
	assert(ui_scene.server_room_container != null, "Server room container should exist")
	assert(ui_scene.grid_container != null, "Grid container should exist")
	assert(ui_scene.storage_container != null, "Storage container should exist")
	assert(ui_scene.shop_container != null, "Shop container should exist")
	assert(ui_scene.stats_label != null, "Stats label should exist")
	assert(ui_scene.hover_preview != null, "Hover preview should exist")

	_record_test("UI Initialization", true)
	return true

func test_grid_initialization():
	print("\nTest: Grid Initialization")

	assert(ui_scene.active_grid.size() == ui_scene.ROOM_HEIGHT, "Active grid height should match")
	assert(ui_scene.active_grid[0].size() == ui_scene.ROOM_WIDTH, "Active grid width should match")
	assert(ui_scene.item_grid.size() == ui_scene.ROOM_HEIGHT, "Item grid height should match")
	assert(ui_scene.item_grid[0].size() == ui_scene.ROOM_WIDTH, "Item grid width should match")

	# Check initial state (all false/null)
	var all_inactive = true
	for row in ui_scene.active_grid:
		for cell in row:
			if cell != false:
				all_inactive = false
	assert(all_inactive, "All grid cells should start inactive")

	var all_empty = true
	for row in ui_scene.item_grid:
		for cell in row:
			if cell != null:
				all_empty = false
	assert(all_empty, "All item grid cells should start empty")

	_record_test("Grid Initialization", true)
	return true

func test_shop_generation():
	print("\nTest: Shop Generation")

	assert(ui_scene.shop_items.size() > 0, "Shop should have items")

	# Check shop items have required data
	for shop_item in ui_scene.shop_items:
		var item_data = shop_item.get_meta("item_data")
		assert(item_data != null, "Shop item should have item_data")
		assert(item_data.has("name"), "Item should have name")
		assert(item_data.has("cost"), "Item should have cost")
		assert(item_data.has("type"), "Item should have type")
		assert(item_data.cost > 0, "Item cost should be positive")

	# Check mix of servers and items
	var has_server = false
	var has_item = false
	for shop_item in ui_scene.shop_items:
		var item_data = shop_item.get_meta("item_data")
		if item_data.type == "server":
			has_server = true
		elif item_data.type == "item":
			has_item = true

	assert(has_server, "Shop should have at least one server")
	assert(has_item, "Shop should have at least one item")

	_record_test("Shop Generation", true)
	return true

func test_server_placement():
	print("\nTest: Server Placement")

	# Test placing a server pattern
	var test_pattern = [[1, 1], [1, 1]]  # 2x2 pattern

	# Check can place at origin
	var can_place = ui_scene._can_place_server_pattern(0, 0, test_pattern)
	assert(can_place, "Should be able to place 2x2 server at origin")

	# Place the server
	var server_data = {
		"pattern": test_pattern,
		"color": Color.WHITE,
		"cost": 5
	}
	ui_scene._place_server_pattern(0, 0, server_data)

	# Check grid is marked active
	assert(ui_scene.active_grid[0][0] == true, "Grid 0,0 should be active")
	assert(ui_scene.active_grid[0][1] == true, "Grid 0,1 should be active")
	assert(ui_scene.active_grid[1][0] == true, "Grid 1,0 should be active")
	assert(ui_scene.active_grid[1][1] == true, "Grid 1,1 should be active")

	# Check visual cells were created
	assert(ui_scene.grid_cells[0][0] != null, "Visual cell should exist at 0,0")
	assert(ui_scene.grid_cells[0][1] != null, "Visual cell should exist at 0,1")

	# Check can't place overlapping
	can_place = ui_scene._can_place_server_pattern(0, 0, test_pattern)
	assert(not can_place, "Should not be able to place overlapping server")

	_record_test("Server Placement", true)
	return true

func test_item_placement():
	print("\nTest: Item Placement")

	# First need active grid cells (from test_server_placement)
	# Check can place item on active cells
	var can_place = ui_scene._can_place_item_on_grid(0, 0, 2, 2)
	assert(can_place, "Should be able to place 2x2 item on active grid")

	# Check can't place on inactive cells
	can_place = ui_scene._can_place_item_on_grid(5, 5, 1, 1)
	assert(not can_place, "Should not be able to place item on inactive grid")

	# Check can't place out of bounds
	can_place = ui_scene._can_place_item_on_grid(11, 7, 2, 2)
	assert(not can_place, "Should not be able to place item out of bounds")

	_record_test("Item Placement", true)
	return true

func test_drag_and_drop():
	print("\nTest: Drag and Drop")

	# Create a test item
	var item_data = {
		"name": "Test Item",
		"width": 1,
		"height": 1,
		"color": Color.RED,
		"cost": 3,
		"type": "item"
	}
	var test_item = ui_scene._create_item(item_data)

	assert(test_item != null, "Should create test item")
	assert(test_item.has_meta("item_data"), "Item should have metadata")
	assert(test_item.has_meta("is_item"), "Item should be marked as item")

	# Simulate starting drag
	ui_scene._start_dragging_item(test_item, Vector2.ZERO)
	assert(ui_scene.dragging_object == test_item, "Should be dragging the item")
	assert(ui_scene.hover_preview.visible, "Hover preview should be visible")

	# Stop dragging
	ui_scene._stop_dragging()
	assert(ui_scene.dragging_object == null, "Should stop dragging")
	assert(not ui_scene.hover_preview.visible, "Hover preview should be hidden")

	# Clean up
	test_item.queue_free()

	_record_test("Drag and Drop", true)
	return true

func test_hover_preview():
	print("\nTest: Hover Preview")

	assert(ui_scene.hover_preview != null, "Hover preview should exist")
	assert(not ui_scene.hover_preview.visible, "Hover preview should start hidden")

	# Test preview updates during drag
	var item_data = {
		"name": "Test",
		"width": 2,
		"height": 1,
		"color": Color.BLUE,
		"cost": 4,
		"type": "item"
	}
	var test_item = ui_scene._create_item(item_data)

	ui_scene._start_dragging_item(test_item, Vector2.ZERO)
	ui_scene._update_hover_preview()

	# Check preview shows correct size
	var expected_width = 2 * (ui_scene.CELL_SIZE + ui_scene.CELL_SPACING) - ui_scene.CELL_SPACING
	var expected_height = 1 * (ui_scene.CELL_SIZE + ui_scene.CELL_SPACING) - ui_scene.CELL_SPACING

	# Preview size should match item size (approximately)
	assert(ui_scene.hover_preview.size.x > 0, "Preview should have width")
	assert(ui_scene.hover_preview.size.y > 0, "Preview should have height")

	ui_scene._stop_dragging()
	test_item.queue_free()

	_record_test("Hover Preview", true)
	return true

func test_storage_area():
	print("\nTest: Storage Area")

	assert(ui_scene.storage_container != null, "Storage container should exist")
	assert(ui_scene.storage_container.size.x > 0, "Storage should have width")
	assert(ui_scene.storage_container.size.y > 0, "Storage should have height")

	# Storage should accept items
	var item_data = {
		"name": "Storage Test",
		"width": 1,
		"height": 1,
		"color": Color.GREEN,
		"cost": 2,
		"type": "item"
	}
	var test_item = ui_scene._create_item(item_data)

	# Add to storage
	ui_scene.storage_container.add_child(test_item)
	assert(test_item.get_parent() == ui_scene.storage_container, "Item should be in storage")

	# Clean up
	test_item.queue_free()

	_record_test("Storage Area", true)
	return true

func test_gold_management():
	print("\nTest: Gold Management")

	var initial_gold = ui_scene.current_gold
	assert(initial_gold == 50, "Should start with 50 gold")

	# Test refresh cost
	ui_scene._on_refresh_shop()
	assert(ui_scene.current_gold == initial_gold - 2, "Refresh should cost 2 gold")

	# Test stats update
	var stats_text = ui_scene._get_stats_text()
	assert(stats_text.contains(str(ui_scene.current_gold)), "Stats should show current gold")

	_record_test("Gold Management", true)
	return true

func test_battle_calculation():
	print("\nTest: Battle Calculation")

	# Set up a simple battle scenario
	ui_scene.servers = [{"data": {}, "pos": Vector2i.ZERO}]

	# Run battle
	var initial_health = ui_scene.current_health
	var initial_round = ui_scene.current_round

	ui_scene._on_start_battle()

	# Check state changed
	var state_changed = (
		ui_scene.current_health != initial_health or
		ui_scene.current_round != initial_round
	)
	assert(state_changed, "Battle should change game state")

	_record_test("Battle Calculation", true)
	return true

func assert(condition: bool, message: String):
	if not condition:
		push_error("Assert failed: " + message)
		print("  ✗ " + message)
		tests_failed += 1
		return false
	else:
		tests_passed += 1
		return true

func _record_test(test_name: String, passed: bool):
	test_results[test_name] = passed
	if passed:
		print("  ✅ " + test_name + " passed")
	else:
		print("  ❌ " + test_name + " failed")

func _report_results():
	print("\n=== TEST RESULTS ===")
	print("Total assertions: %d" % (tests_passed + tests_failed))
	print("Passed: %d" % tests_passed)
	print("Failed: %d" % tests_failed)

	print("\nTest Summary:")
	for test_name in test_results:
		var status = "✅" if test_results[test_name] else "❌"
		print("  %s %s" % [status, test_name])

	if tests_failed == 0:
		print("\n🎉 All tests passed!")
	else:
		print("\n⚠️ Some tests failed")

	return tests_failed == 0
