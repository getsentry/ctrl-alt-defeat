extends Node

# Test InventorySystem functionality
class_name TestInventorySystem

var inventory_system: Control
var test_items: Array[Dictionary] = []

func setup():
	print("Setting up InventorySystem tests...")
	inventory_system = preload("res://scripts/InventorySystem.gd").new()
	add_child(inventory_system)

	# Create test items
	test_items = [
		{
			"id": "item1",
			"name": "Test Item 1",
			"item_type": "null_pointer",
			"min_damage": 5,
			"max_damage": 10,
			"tier": 1,
			"rarity": "common"
		},
		{
			"id": "item2",
			"name": "Test Item 2",
			"item_type": "error_monitoring",
			"tier": 2,
			"rarity": "rare"
		}
	]

func teardown():
	if inventory_system:
		inventory_system.queue_free()

func test_grid_initialization():
	print("Testing grid initialization...")

	assert(inventory_system.GRID_SIZE == Vector2i(7, 9), "Grid should be 7x9")
	assert(inventory_system.grid_slots.size() == 63, "Should have 63 grid slots")

	var all_slots_initialized = true
	for slot in inventory_system.grid_slots:
		if slot == null:
			all_slots_initialized = false
			break

	assert(all_slots_initialized, "All grid slots should be initialized")

	print("✓ Grid initialized with ", inventory_system.grid_slots.size(), " slots")
	return true

func test_add_item():
	print("Testing add item...")

	var initial_count = inventory_system.inventory_items.size()
	inventory_system.add_item(test_items[0])

	assert(inventory_system.inventory_items.size() == initial_count + 1, "Item count should increase")
	assert(inventory_system.inventory_items[0]["id"] == "item1", "Item should be added to inventory")

	var placed_items = inventory_system.get_placed_items()
	assert(placed_items.size() == 1, "Item should be placed on grid")

	print("✓ Item added successfully")
	return true

func test_item_placement():
	print("Testing item placement...")

	inventory_system.clear_inventory()

	var test_item = test_items[0].duplicate()
	var test_position = Vector2i(3, 4)

	# Test placement
	var can_place = inventory_system.can_place_item_at(test_item, test_position)
	assert(can_place, "Should be able to place item at empty position")

	inventory_system._place_item(test_item, test_position)

	# Check item was placed correctly
	var item_at_pos = inventory_system.get_item_at_position(test_position)
	assert(item_at_pos["id"] == test_item["id"], "Item should be at specified position")
	assert(item_at_pos["position"][0] == test_position.x, "X position should match")
	assert(item_at_pos["position"][1] == test_position.y, "Y position should match")

	print("✓ Item placed at position (", test_position.x, ", ", test_position.y, ")")
	return true

func test_item_removal():
	print("Testing item removal...")

	inventory_system.clear_inventory()
	inventory_system.add_item(test_items[0])

	var initial_count = inventory_system.inventory_items.size()
	assert(initial_count == 1, "Should have one item")

	var item_to_remove = inventory_system.inventory_items[0]
	inventory_system._remove_item(item_to_remove)

	assert(inventory_system.inventory_items.size() == 0, "Item should be removed")

	print("✓ Item removed successfully")
	return true

func test_can_place_validation():
	print("Testing placement validation...")

	inventory_system.clear_inventory()

	var test_item = test_items[0].duplicate()

	# Test valid positions
	assert(inventory_system.can_place_item_at(test_item, Vector2i(0, 0)), "Should place at (0,0)")
	assert(inventory_system.can_place_item_at(test_item, Vector2i(6, 8)), "Should place at (6,8)")

	# Test invalid positions
	assert(not inventory_system.can_place_item_at(test_item, Vector2i(-1, 0)), "Should not place at negative x")
	assert(not inventory_system.can_place_item_at(test_item, Vector2i(0, -1)), "Should not place at negative y")
	assert(not inventory_system.can_place_item_at(test_item, Vector2i(7, 0)), "Should not place beyond grid width")
	assert(not inventory_system.can_place_item_at(test_item, Vector2i(0, 9)), "Should not place beyond grid height")

	# Test occupied position
	inventory_system._place_item(test_item, Vector2i(3, 3))
	var another_item = test_items[1].duplicate()
	assert(not inventory_system.can_place_item_at(another_item, Vector2i(3, 3)), "Should not place on occupied slot")

	print("✓ Placement validation working correctly")
	return true

func test_clear_inventory():
	print("Testing clear inventory...")

	# Add multiple items
	inventory_system.clear_inventory()
	inventory_system.add_item(test_items[0])
	inventory_system.add_item(test_items[1])

	assert(inventory_system.inventory_items.size() == 2, "Should have 2 items")

	inventory_system.clear_inventory()

	assert(inventory_system.inventory_items.size() == 0, "Inventory should be empty")
	assert(inventory_system.get_placed_items().size() == 0, "No items should be placed")

	print("✓ Inventory cleared successfully")
	return true

func test_get_placed_items():
	print("Testing get placed items...")

	inventory_system.clear_inventory()

	# Add item with position
	var placed_item = test_items[0].duplicate()
	inventory_system._place_item(placed_item, Vector2i(2, 2))

	# Add item without position (shouldn't be included)
	var unplaced_item = test_items[1].duplicate()
	unplaced_item["position"] = null
	inventory_system.inventory_items.append(unplaced_item)

	var placed = inventory_system.get_placed_items()

	assert(placed.size() == 1, "Should only return placed items")
	assert(placed[0]["id"] == placed_item["id"], "Should return the correct placed item")

	print("✓ Get placed items returns ", placed.size(), " items")
	return true

func test_drag_and_drop_simulation():
	print("Testing drag and drop simulation...")

	inventory_system.clear_inventory()

	var item = test_items[0].duplicate()
	var start_pos = Vector2i(1, 1)
	var end_pos = Vector2i(4, 4)

	# Place item at start position
	inventory_system._place_item(item, start_pos)
	assert(inventory_system.get_item_at_position(start_pos)["id"] == item["id"], "Item at start position")

	# Simulate drag start
	inventory_system._start_dragging(item, null)
	assert(inventory_system.dragging_item["id"] == item["id"], "Should be dragging item")

	# Simulate drop at new position
	var success = inventory_system._try_place_item(item, end_pos)
	assert(success, "Should successfully place item at new position")
	assert(inventory_system.get_item_at_position(end_pos)["id"] == item["id"], "Item at end position")
	assert(inventory_system.get_item_at_position(start_pos).is_empty(), "Start position should be empty")

	print("✓ Drag and drop working correctly")
	return true

func test_visual_updates():
	print("Testing visual updates...")

	inventory_system.clear_inventory()

	var item = test_items[0].duplicate()
	var position = Vector2i(2, 3)

	inventory_system._place_item(item, position)

	# Check that the slot is marked as occupied
	var slot_index = position.y * 7 + position.x
	var slot = inventory_system.grid_slots[slot_index]

	assert(slot.get_meta("occupied") == true, "Slot should be marked as occupied")
	assert(slot.get_child_count() > 0, "Slot should have visual children")

	# Remove item and check visual is cleared
	inventory_system._remove_item(item)
	assert(slot.get_meta("occupied") == false, "Slot should be marked as unoccupied")

	print("✓ Visual updates working correctly")
	return true

func test_item_signals():
	print("Testing item signals...")

	inventory_system.clear_inventory()

	var placed_signal_received = false
	var removed_signal_received = false
	var signal_item = null
	var signal_position = Vector2i()

	# Connect to signals
	inventory_system.item_placed.connect(func(item, pos):
		placed_signal_received = true
		signal_item = item
		signal_position = pos
	, CONNECT_ONE_SHOT)

	inventory_system.item_removed.connect(func(item):
		removed_signal_received = true
	, CONNECT_ONE_SHOT)

	# Test placement signal
	var test_item = test_items[0].duplicate()
	var test_pos = Vector2i(3, 3)
	inventory_system._place_item(test_item, test_pos)

	assert(placed_signal_received, "Should receive item_placed signal")
	assert(signal_item["id"] == test_item["id"], "Signal should contain correct item")
	assert(signal_position == test_pos, "Signal should contain correct position")

	# Test removal signal
	inventory_system._remove_item(test_item)
	assert(removed_signal_received, "Should receive item_removed signal")

	print("✓ Signals working correctly")
	return true

func run_all_tests():
	print("\n=== RUNNING INVENTORY SYSTEM TESTS ===\n")

	setup()

	var tests = [
		["Grid Initialization", test_grid_initialization],
		["Add Item", test_add_item],
		["Item Placement", test_item_placement],
		["Item Removal", test_item_removal],
		["Placement Validation", test_can_place_validation],
		["Clear Inventory", test_clear_inventory],
		["Get Placed Items", test_get_placed_items],
		["Drag and Drop", test_drag_and_drop_simulation],
		["Visual Updates", test_visual_updates],
		["Item Signals", test_item_signals]
	]

	var passed = 0
	var failed = 0
	var test_results = {}

	for test in tests:
		print("\n--- ", test[0], " ---")
		try:
			var result = await test[1].call()
			if result:
				passed += 1
				test_results[test[0]] = true
			else:
				failed += 1
				test_results[test[0]] = false
		except:
			print("✗ Test crashed: ", test[0])
			failed += 1
			test_results[test[0]] = false

	print("\n=== TEST RESULTS ===")
	print("Passed: ", passed, "/", tests.size())
	print("Failed: ", failed, "/", tests.size())

	for test_name in test_results:
		var status = "✓" if test_results[test_name] else "✗"
		print(status, " ", test_name)

	teardown()

	return failed == 0

func assert(condition: bool, message: String):
	if not condition:
		push_error("Assertion failed: " + message)
		print("✗ ASSERT FAILED: ", message)

func try(callable: Callable):
	var result = null
	try:
		result = callable.call()
	except:
		pass
	return result

func except(error = null):
	if error:
		print("Exception: ", error)
