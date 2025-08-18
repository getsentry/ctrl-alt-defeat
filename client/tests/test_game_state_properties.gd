extends SceneTree
# Test all GameStateManager properties exist

func _init():
	print("\n=== Testing GameStateManager Properties ===")

	# Test that all required properties exist
	var required_properties = [
		"player_id",
		"player_name",
		"current_round",
		"player_lives",
		"battle_health",
		"gold",
		"wins",
		"losses",
		"game_over",
		"victory",
		"current_inventory",
		"server_containers",
		"starting_containers",  # The one that was missing
		"current_shop",
		"shop_rerolls",
		"last_battle_result",
		"last_battle_events",
		"opponent_inventory",
		"battle_speed",
		"auto_ready"
	]

	print("Checking for %d required properties..." % required_properties.size())
	var missing = []

	for prop in required_properties:
		if not prop in GameStateManager:
			missing.append(prop)
			print("  ✗ Missing: %s" % prop)
		else:
			print("  ✓ Found: %s" % prop)

	if missing.size() > 0:
		print("\n❌ FAILED: Missing %d properties: %s" % [missing.size(), missing])
		assert(false, "Missing required properties")
	else:
		print("\n✅ All %d required properties are present!" % required_properties.size())

	# Test that methods exist
	print("\nTesting required methods...")
	assert(GameStateManager.has_method("start_new_game"), "Should have start_new_game method")
	assert(GameStateManager.has_method("save_inventory_state"), "Should have save_inventory_state method")
	assert(GameStateManager.has_method("get_inventory_state"), "Should have get_inventory_state method")
	assert(GameStateManager.has_method("update_after_battle"), "Should have update_after_battle method")
	assert(GameStateManager.has_method("is_game_over"), "Should have is_game_over method")
	assert(GameStateManager.has_method("is_victory"), "Should have is_victory method")
	assert(GameStateManager.has_method("get_round_quota"), "Should have get_round_quota method")
	print("✓ All required methods exist")

	print("\n✅ GameStateManager is properly configured!")
	quit(0)
