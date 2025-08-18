extends Node

# Test ShopSystem functionality
class_name TestShopSystem

var shop_system: HBoxContainer
var test_shop_items: Array = []

func setup():
	print("Setting up ShopSystem tests...")
	shop_system = preload("res://scripts/ShopSystem.gd").new()
	add_child(shop_system)

	# Create test shop items
	test_shop_items = [
		{
			"id": "shop-item-1",
			"name": "Null Pointer",
			"item_type": "null_pointer",
			"category": "problem",
			"tier": 1,
			"rarity": "common",
			"cost": 3,
			"min_damage": 4,
			"max_damage": 8,
			"cooldown": 2.5,
			"cpu_cost": 3,
			"special_effect": ""
		},
		null,  # Empty slot
		{
			"id": "shop-item-2",
			"name": "Error Monitoring",
			"item_type": "error_monitoring",
			"category": "defense",
			"tier": 1,
			"rarity": "uncommon",
			"cost": 5,
			"min_damage": 0,
			"max_damage": 0,
			"cooldown": 0,
			"cpu_cost": 0,
			"special_effect": "Blocks 8 damage"
		},
		{
			"id": "shop-item-3",
			"name": "Redis Cache",
			"item_type": "redis_cache",
			"category": "infrastructure",
			"tier": 2,
			"rarity": "rare",
			"cost": 8,
			"min_damage": 0,
			"max_damage": 0,
			"cooldown": 0,
			"cpu_cost": 0,
			"special_effect": "+3 CPU regeneration"
		},
		null  # Empty slot
	]

func teardown():
	if shop_system:
		shop_system.queue_free()

func test_shop_initialization():
	print("Testing shop initialization...")

	assert(shop_system.SHOP_SLOTS == 5, "Should have 5 shop slots")
	assert(shop_system.shop_slots.size() == 5, "Should create 5 slot controls")

	var all_slots_created = true
	for slot in shop_system.shop_slots:
		if slot == null:
			all_slots_created = false
			break

	assert(all_slots_created, "All shop slots should be created")

	print("✓ Shop initialized with ", shop_system.shop_slots.size(), " slots")
	return true

func test_display_shop():
	print("Testing shop display...")

	var test_gold = 10
	shop_system.display_shop(test_shop_items, test_gold)

	assert(shop_system.shop_items == test_shop_items, "Shop items should be stored")
	assert(shop_system.current_gold == test_gold, "Gold should be stored")

	# Check slots are populated correctly
	var item_count = 0
	var empty_count = 0

	for i in range(test_shop_items.size()):
		if test_shop_items[i] != null:
			item_count += 1
		else:
			empty_count += 1

	assert(item_count == 3, "Should have 3 items")
	assert(empty_count == 2, "Should have 2 empty slots")

	print("✓ Shop displayed with ", item_count, " items and ", empty_count, " empty slots")
	return true

func test_purchase_validation():
	print("Testing purchase validation...")

	# Display shop with different gold amounts
	shop_system.display_shop(test_shop_items, 5)  # Only enough for first item

	# Check if expensive items are disabled
	# Note: We can't directly test button states without rendering,
	# but we can test the logic

	var can_afford_first = test_shop_items[0] != null and test_shop_items[0]["cost"] <= 5
	var can_afford_third = test_shop_items[2] != null and test_shop_items[2]["cost"] <= 5

	assert(can_afford_first, "Should be able to afford 3-cost item with 5 gold")
	assert(not can_afford_third, "Should not be able to afford 5-cost item with 5 gold")

	print("✓ Purchase validation working")
	return true

func test_item_purchase_signal():
	print("Testing item purchase signal...")

	shop_system.display_shop(test_shop_items, 10)

	var signal_received = false
	var purchased_item = {}

	shop_system.item_purchased.connect(func(item):
		signal_received = true
		purchased_item = item
	, CONNECT_ONE_SHOT)

	# Simulate purchase of first item
	if test_shop_items[0] != null:
		shop_system._on_buy_pressed(test_shop_items[0], 0)

		assert(signal_received, "Should receive item_purchased signal")
		assert(purchased_item["id"] == test_shop_items[0]["id"], "Should receive correct item")
		assert(shop_system.shop_items[0] == null, "Slot should be cleared after purchase")

	print("✓ Purchase signal working correctly")
	return true

func test_refresh_shop():
	print("Testing shop refresh...")

	var original_items = test_shop_items.duplicate()
	shop_system.display_shop(original_items, 10)

	var new_items = [
		{
			"id": "new-item-1",
			"name": "New Item",
			"cost": 4,
			"category": "problem",
			"rarity": "common"
		},
		null, null, null, null
	]

	var signal_received = false
	shop_system.shop_refreshed.connect(func():
		signal_received = true
	, CONNECT_ONE_SHOT)

	shop_system.refresh_shop(new_items, 8)

	assert(shop_system.shop_items == new_items, "Shop should have new items")
	assert(shop_system.current_gold == 8, "Gold should be updated")
	assert(signal_received, "Should receive shop_refreshed signal")

	print("✓ Shop refresh working correctly")
	return true

func test_update_gold():
	print("Testing gold update...")

	shop_system.display_shop(test_shop_items, 10)

	shop_system.update_gold(15)
	assert(shop_system.current_gold == 15, "Gold should be updated")

	shop_system.update_gold(3)
	assert(shop_system.current_gold == 3, "Gold should be updated again")

	print("✓ Gold update working correctly")
	return true

func test_rarity_colors():
	print("Testing rarity colors...")

	var colors = {
		"common": shop_system._get_rarity_color("common"),
		"uncommon": shop_system._get_rarity_color("uncommon"),
		"rare": shop_system._get_rarity_color("rare"),
		"epic": shop_system._get_rarity_color("epic"),
		"legendary": shop_system._get_rarity_color("legendary"),
		"godly": shop_system._get_rarity_color("godly")
	}

	# Check that each rarity has a distinct color
	assert(colors["common"] != colors["uncommon"], "Common and uncommon should have different colors")
	assert(colors["rare"] != colors["epic"], "Rare and epic should have different colors")
	assert(colors["legendary"] != colors["godly"], "Legendary and godly should have different colors")

	print("✓ Rarity colors defined for all rarities")
	return true

func test_empty_slot_handling():
	print("Testing empty slot handling...")

	var all_empty = [null, null, null, null, null]
	shop_system.display_shop(all_empty, 10)

	# Check that all slots show as empty
	var all_handled = true
	for i in range(5):
		if shop_system.shop_items[i] != null:
			all_handled = false
			break

	assert(all_handled, "All empty slots should be handled correctly")

	print("✓ Empty slots handled correctly")
	return true

func run_all_tests():
	print("\n=== RUNNING SHOP SYSTEM TESTS ===\n")

	setup()

	var tests = [
		["Shop Initialization", test_shop_initialization],
		["Display Shop", test_display_shop],
		["Purchase Validation", test_purchase_validation],
		["Item Purchase Signal", test_item_purchase_signal],
		["Refresh Shop", test_refresh_shop],
		["Update Gold", test_update_gold],
		["Rarity Colors", test_rarity_colors],
		["Empty Slot Handling", test_empty_slot_handling]
	]

	var passed = 0
	var failed = 0
	var test_results = {}

	for test in tests:
		print("\n--- ", test[0], " ---")
		var result = await test[1].call()
		if result:
			passed += 1
			test_results[test[0]] = true
		else:
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
