extends SceneTree
# Test that inventory persists between battles

func _init():
	print("\n=== Testing Inventory Persistence ===")

	var test_passed = true

	# Test 1: Save inventory to GameStateManager
	print("Test 1: Saving inventory...")
	var test_items = [
		{"id": "item1", "type": "cpu", "position": Vector2i(0, 0)},
		{"id": "item2", "type": "ram", "position": Vector2i(1, 0)}
	]
	var test_servers = [
		{"id": "server1", "type": "rack_2x3", "position": Vector2i(2, 2)}
	]

	GameStateManager.save_inventory_state(test_items, test_servers)

	var saved = GameStateManager.get_inventory_state()
	if not saved.has("items") or saved.items.size() != 2:
		print("❌ FAIL: Items not saved correctly")
		test_passed = false
	elif not saved.has("servers") or saved.servers.size() != 1:
		print("❌ FAIL: Servers not saved correctly")
		test_passed = false
	else:
		print("✓ Inventory saved correctly")

	# Test 2: Persist through battle
	print("\nTest 2: Checking persistence after battle...")

	# Simulate battle result
	var mock_battle_result = {
		"battle_result": {
			"winner": 1,
			"duration": 10.0,
			"player1_quota": 10,
			"player2_quota": 0,
			"actions": []
		},
		"session_update": {
			"round": 2,
			"gold": 20
		}
	}

	GameStateManager.update_after_battle(mock_battle_result)

	# Check if inventory still exists
	var after_battle = GameStateManager.get_inventory_state()
	if not after_battle.has("items") or after_battle.items.size() != 2:
		print("❌ FAIL: Items lost after battle")
		test_passed = false
	elif not after_battle.has("servers") or after_battle.servers.size() != 1:
		print("❌ FAIL: Servers lost after battle")
		test_passed = false
	else:
		print("✓ Inventory persisted through battle")

	# Test 3: Check if shop screen would reload inventory
	print("\nTest 3: Testing shop reload...")

	# The shop should check for existing inventory
	if GameStateManager.current_inventory.is_empty():
		print("❌ FAIL: GameStateManager.current_inventory is empty")
		test_passed = false
	else:
		print("✓ Inventory available for reload")

	if test_passed:
		print("\n✅ All inventory persistence tests passed!")
		quit(0)
	else:
		print("\n❌ Inventory persistence tests FAILED")
		print("Issue: Inventory is not properly persisted between scenes")
		quit(1)
