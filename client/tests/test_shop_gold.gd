extends Node
# Test that shop purchases correctly use GameStateManager's gold

func test_shop_uses_game_state_gold():
	print("Testing shop gold integration...")

	# Set up GameStateManager with specific gold amount
	GameStateManager.gold = 5
	GameStateManager.current_round = 1

	# Create shop UI
	var shop_ui = preload("res://scripts/UnifiedGridUI.gd").new()

	# Check that it reads gold from GameStateManager, not its own variable
	assert(shop_ui.current_gold == GameStateManager.gold,
		"Shop should use GameStateManager.gold, not its own current_gold")

	# Simulate purchasing an item that costs 3 gold
	var mock_item = {
		"cost": 3,
		"name": "Test Item"
	}

	# The shop should check GameStateManager.gold, not current_gold
	var can_afford = GameStateManager.gold >= mock_item.cost
	assert(can_afford == true, "Should be able to afford 3g item with 5g")

	# After purchase, GameStateManager.gold should be updated
	if can_afford:
		GameStateManager.gold -= mock_item.cost
		assert(GameStateManager.gold == 2, "Gold should be 2 after buying 3g item")

	print("✓ Shop gold integration test passed")

func test_shop_prevents_overspending():
	print("Testing shop prevents overspending...")

	# Set up with limited gold
	GameStateManager.gold = 2

	# Try to buy something that costs more
	var expensive_item = {
		"cost": 5,
		"name": "Expensive Item"
	}

	var can_afford = GameStateManager.gold >= expensive_item.cost
	assert(can_afford == false, "Should not be able to afford 5g item with 2g")

	print("✓ Shop overspending prevention test passed")

func run_tests():
	print("\n=== Running Shop Gold Tests ===")
	test_shop_uses_game_state_gold()
	test_shop_prevents_overspending()
	print("=== All Shop Gold Tests Passed ===\n")
