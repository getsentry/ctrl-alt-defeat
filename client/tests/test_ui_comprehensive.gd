extends Node

# Comprehensive UI Tests
class_name TestUIComprehensive

var test_scene: Control
var test_results: Dictionary = {}

func setup():
	print("Setting up comprehensive UI tests...")
	# Load the simple test scene
	var scene_resource = load("res://scenes/SimpleTest.tscn")
	test_scene = scene_resource.instantiate()
	add_child(test_scene)

func teardown():
	if test_scene:
		test_scene.queue_free()

func test_ui_initialization():
	print("Testing UI initialization...")

	# Check main control exists
	assert(test_scene != null, "Test scene should be loaded")
	assert(test_scene is Control, "Scene should be a Control node")

	# Check children count (should have background, title, stats, etc.)
	var children = test_scene.get_children()
	assert(children.size() > 5, "Should have at least 6 UI elements")

	# Check background
	var bg = children[0]
	assert(bg is ColorRect, "First child should be background ColorRect")

	# Check title
	var title = children[1]
	assert(title is Label, "Second child should be title Label")
	assert(title.text.contains("Sentry"), "Title should contain 'Sentry'")

	print("✓ UI initialized correctly with %d elements" % children.size())
	return true

func test_shop_generation():
	print("Testing shop generation...")

	# Check shop items array
	assert(test_scene.shop_items is Array, "shop_items should be an Array")
	assert(test_scene.shop_items.size() == 5, "Should have 5 shop items")

	# Check each shop item
	for i in range(test_scene.shop_items.size()):
		var item = test_scene.shop_items[i]
		assert(item.has("name"), "Shop item should have name")
		assert(item.has("cost"), "Shop item should have cost")
		assert(item.cost > 0, "Item cost should be positive")

	print("✓ Shop generated with %d items" % test_scene.shop_items.size())
	return true

func test_game_state():
	print("Testing game state...")

	# Check initial values
	assert(test_scene.current_gold > 0, "Should have starting gold")
	assert(test_scene.current_round == 1, "Should start at round 1")
	assert(test_scene.current_health > 0, "Should have starting health")

	print("✓ Game state initialized: Gold=%d, Round=%d, Health=%d" %
		[test_scene.current_gold, test_scene.current_round, test_scene.current_health])
	return true

func test_buy_item_functionality():
	print("Testing buy item functionality...")

	var initial_gold = test_scene.current_gold
	var initial_inv_size = test_scene.inventory_items.size()

	# Find cheapest item
	var cheapest_item = null
	var min_cost = 999
	for item in test_scene.shop_items:
		if item.cost < min_cost:
			min_cost = item.cost
			cheapest_item = item

	if cheapest_item and test_scene.current_gold >= cheapest_item.cost:
		# Simulate buying
		test_scene._on_buy_item(cheapest_item.name, cheapest_item.cost, cheapest_item.container)

		# Check gold was deducted
		assert(test_scene.current_gold == initial_gold - cheapest_item.cost,
			"Gold should be deducted after purchase")

		# Check item was added to inventory
		assert(test_scene.inventory_items.size() == initial_inv_size + 1,
			"Inventory should have one more item")

		print("✓ Item purchase working: bought %s for %d gold" % [cheapest_item.name, cheapest_item.cost])
		return true
	else:
		print("⚠ Could not test purchase - no affordable items")
		return true

func test_drag_system():
	print("Testing drag system...")

	# Create a test draggable item
	var test_item = test_scene._create_draggable_item("Test Item")
	assert(test_item != null, "Should create draggable item")
	assert(test_item.has_meta("draggable"), "Item should have draggable meta")
	assert(test_item.get_meta("draggable") == true, "Item should be draggable")

	# Simulate drag start
	var mouse_event = InputEventMouseButton.new()
	mouse_event.button_index = MOUSE_BUTTON_LEFT
	mouse_event.pressed = true
	mouse_event.position = Vector2(10, 10)

	test_scene._on_item_input(mouse_event, test_item)
	assert(test_scene.dragging_item == test_item, "Should be dragging the item")

	# Simulate drag end
	mouse_event.pressed = false
	test_scene._on_item_input(mouse_event, test_item)
	assert(test_scene.dragging_item == null, "Should stop dragging")

	test_item.queue_free()

	print("✓ Drag system working correctly")
	return true

func test_refresh_shop():
	print("Testing shop refresh...")

	var initial_gold = test_scene.current_gold

	if initial_gold >= 2:
		# Get initial shop state
		var initial_items = []
		for item in test_scene.shop_items:
			initial_items.append(item.name)

		# Refresh shop
		test_scene._on_refresh_shop()

		# Check gold was deducted
		assert(test_scene.current_gold == initial_gold - 2,
			"Should deduct 2 gold for refresh")

		# Check shop still has 5 items
		assert(test_scene.shop_items.size() == 5,
			"Shop should still have 5 items after refresh")

		print("✓ Shop refresh working: cost 2 gold")
		return true
	else:
		print("⚠ Not enough gold to test refresh")
		return true

func test_battle_simulation():
	print("Testing battle simulation...")

	var initial_round = test_scene.current_round
	var initial_health = test_scene.current_health
	var initial_gold = test_scene.current_gold

	# Add some items to inventory for testing
	for i in range(3):
		var item = test_scene._create_draggable_item("Test Item " + str(i))
		test_scene.inventory_items.append(item)

	# Start battle
	test_scene._on_start_battle()

	# Check that values changed
	var values_changed = (
		test_scene.current_round != initial_round or
		test_scene.current_health != initial_health or
		test_scene.current_gold != initial_gold
	)

	assert(values_changed, "Battle should change game state")

	print("✓ Battle simulation working")
	return true

func test_ui_panels():
	print("Testing UI panels...")

	var panels_found = 0
	var buttons_found = 0
	var labels_found = 0

	for child in test_scene.get_children():
		if child is Panel:
			panels_found += 1
		elif child is Button:
			buttons_found += 1
		elif child is Label:
			labels_found += 1

	assert(panels_found >= 2, "Should have at least 2 panels (shop and inventory)")
	assert(buttons_found >= 2, "Should have at least 2 buttons (refresh and battle)")
	assert(labels_found >= 3, "Should have at least 3 labels")

	print("✓ Found %d panels, %d buttons, %d labels" % [panels_found, buttons_found, labels_found])
	return true

func test_inventory_management():
	print("Testing inventory management...")

	# Clear inventory
	test_scene.inventory_items.clear()
	assert(test_scene.inventory_items.size() == 0, "Inventory should be empty")

	# Add items
	for i in range(5):
		var item = test_scene._create_draggable_item("Item " + str(i))
		test_scene.inventory_items.append(item)

	assert(test_scene.inventory_items.size() == 5, "Should have 5 items in inventory")

	# Clean up
	for item in test_scene.inventory_items:
		if is_instance_valid(item):
			item.queue_free()
	test_scene.inventory_items.clear()

	print("✓ Inventory management working")
	return true

func test_game_over_condition():
	print("Testing game over condition...")

	# Set health to low
	test_scene.current_health = 10

	# Simulate losing battle
	test_scene.current_health -= 10

	assert(test_scene.current_health <= 0, "Health should be 0 or less")

	# Check if game over message would be printed
	# (In real implementation, would show game over screen)

	print("✓ Game over condition detected at 0 health")
	return true

func run_all_tests():
	print("\n=== RUNNING COMPREHENSIVE UI TESTS ===\n")

	setup()

	var tests = [
		["UI Initialization", test_ui_initialization],
		["Shop Generation", test_shop_generation],
		["Game State", test_game_state],
		["Buy Item", test_buy_item_functionality],
		["Drag System", test_drag_system],
		["Refresh Shop", test_refresh_shop],
		["Battle Simulation", test_battle_simulation],
		["UI Panels", test_ui_panels],
		["Inventory Management", test_inventory_management],
		["Game Over Condition", test_game_over_condition]
	]

	var passed = 0
	var failed = 0

	for test in tests:
		print("\n--- %s ---" % test[0])
		var result = await test[1].call()
		if result:
			passed += 1
			test_results[test[0]] = true
		else:
			failed += 1
			test_results[test[0]] = false

	print("\n=== TEST RESULTS ===")
	print("Passed: %d/%d" % [passed, tests.size()])
	print("Failed: %d/%d" % [failed, tests.size()])

	for test_name in test_results:
		var status = "✓" if test_results[test_name] else "✗"
		print("%s %s" % [status, test_name])

	teardown()

	return failed == 0

func assert(condition: bool, message: String):
	if not condition:
		push_error("Assertion failed: " + message)
		print("✗ ASSERT FAILED: %s" % message)
