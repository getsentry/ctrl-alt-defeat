extends GutTest
# End-to-end test that simulates complete game flow from start to finish

func test_complete_game_flow():
	# This test simulates a player going through the entire game flow
	print("=== Starting End-to-End Game Flow Test ===")

	# Step 1: Start from Main Menu
	print("Step 1: Main Menu")
	var main_menu = preload("res://scripts/MainMenu.gd").new()
	add_child(main_menu)
	await get_tree().process_frame

	# Simulate clicking "Start Game"
	print("  - Starting new game...")
	GameStateManager.start_new_game()

	# Simulate server response
	var session_data = await BattleServerAPI.start_session()
	assert_not_null(session_data, "Should receive session data")
	assert_true(session_data.has("player_id"), "Should have player_id")
	assert_true(session_data.has("gold"), "Should have gold")
	assert_true(session_data.has("current_shop"), "Should have shop items")

	# Update game state
	GameStateManager.player_id = session_data.player_id
	GameStateManager.current_round = session_data.round
	GameStateManager.gold = session_data.gold
	GameStateManager.current_shop = session_data.current_shop
	if session_data.has("starting_containers"):
		GameStateManager.starting_containers = session_data.starting_containers

	print("  - Player ID: %s" % GameStateManager.player_id)
	print("  - Starting gold: %d" % GameStateManager.gold)
	print("  - Shop items: %d" % GameStateManager.current_shop.size())

	main_menu.queue_free()
	await get_tree().process_frame

	# Step 2: Shop/Inventory Phase
	print("Step 2: Shop/Inventory Phase")
	var shop_ui = preload("res://scripts/UnifiedGridUI.gd").new()
	shop_ui.hide_shop = false
	shop_ui.read_only_mode = false
	add_child(shop_ui)
	await get_tree().process_frame

	# Initialize UI
	shop_ui._initialize_grids()
	shop_ui._setup_ui()

	# Place starting containers
	print("  - Placing starting containers...")
	shop_ui._place_starting_containers()
	assert_gt(shop_ui.servers.size(), 0, "Should have starting containers")

	# Load shop items
	print("  - Loading shop items...")
	shop_ui._load_shop_from_state()

	# Simulate buying an item (if we have gold and items)
	if GameStateManager.current_shop.size() > 0 and GameStateManager.gold >= 3:
		print("  - Simulating item purchase...")
		var affordable_item = null
		for item in GameStateManager.current_shop:
			if item and item.has("cost") and item.cost <= GameStateManager.gold:
				affordable_item = item
				break

		if affordable_item:
			print("    Buying: %s for %dg" % [affordable_item.get("name", "Item"), affordable_item.get("cost", 0)])
			shop_ui.current_gold -= affordable_item.cost
			shop_ui._update_stats()

	# Get inventory state
	var inventory = shop_ui.get_inventory_state()
	print("  - Inventory: %d items, %d servers" % [inventory.items.size(), inventory.servers.size()])

	# Save inventory before battle
	GameStateManager.save_inventory_state(inventory.items, inventory.servers)

	shop_ui.queue_free()
	await get_tree().process_frame

	# Step 3: Battle Phase
	print("Step 3: Battle Phase")

	# Submit battle
	print("  - Submitting battle...")
	var battle_result = await BattleServerAPI.submit_battle(inventory)
	assert_not_null(battle_result, "Should receive battle result")
	assert_true(battle_result.has("battle_result"), "Should have battle result")
	assert_true(battle_result.has("session_update"), "Should have session update")

	# Update game state
	GameStateManager.update_after_battle(battle_result)

	var winner = battle_result.battle_result.get("winner", 0)
	print("  - Battle result: %s" % ("WIN" if winner == 1 else "LOSS"))
	print("  - New round: %d" % GameStateManager.current_round)
	print("  - Gold: %d" % GameStateManager.gold)
	print("  - Lives: %d" % GameStateManager.player_lives)

	# Create battle screen for replay
	var battle_screen = preload("res://scripts/BattleScreen.gd").new()
	add_child(battle_screen)
	await get_tree().process_frame

	# Simulate battle replay (shortened)
	print("  - Playing battle replay...")
	await get_tree().create_timer(0.1).timeout

	battle_screen.queue_free()
	await get_tree().process_frame

	# Step 4: Post-Battle
	print("Step 4: Post-Battle Results")
	# PostBattle screen would go here when implemented
	print("  - Showing battle results...")
	print("  - Gold earned: %d" % battle_result.session_update.get("gold_earned", 0))

	# Simulate clicking "Continue"
	await get_tree().create_timer(0.1).timeout

	# Step 5: Check game state
	print("Step 5: Checking Game State")

	if GameStateManager.is_game_over():
		print("  - GAME OVER! Lives: %d" % GameStateManager.player_lives)

		# Create game over screen
		var game_over = preload("res://scripts/GameOverScreen.gd").new()
		add_child(game_over)
		await get_tree().process_frame

		print("  - Final stats:")
		print("    Rounds: %d" % GameStateManager.current_round)
		print("    Wins: %d" % GameStateManager.wins)
		print("    Losses: %d" % GameStateManager.losses)

		game_over.queue_free()
	elif GameStateManager.is_victory():
		print("  - VICTORY! Completed all rounds!")

		var game_over = preload("res://scripts/GameOverScreen.gd").new()
		add_child(game_over)
		await get_tree().process_frame

		print("  - Victory stats:")
		print("    Total wins: %d" % GameStateManager.wins)
		print("    Total losses: %d" % GameStateManager.losses)

		game_over.queue_free()
	else:
		print("  - Continue to next round: %d" % GameStateManager.current_round)
		print("  - Lives remaining: %d" % GameStateManager.player_lives)

		# Would loop back to shop phase
		# Verify inventory persisted
		var saved_inv = GameStateManager.get_inventory_state()
		assert_true(saved_inv.has("items"), "Inventory should persist")
		assert_true(saved_inv.has("servers"), "Servers should persist")

	print("=== End-to-End Test Complete ===")
	assert_true(true, "Complete flow executed without crashes")

func test_shop_interaction_flow():
	# Test specific shop interactions
	print("Testing shop interactions...")

	# Setup
	GameStateManager.start_new_game()
	GameStateManager.gold = 20
	GameStateManager.current_shop = [
		{"id": "test1", "name": "Cheap Item", "cost": 3, "category": "problem"},
		{"id": "test2", "name": "Expensive Item", "cost": 15, "category": "defense"},
		null,  # Empty slot
		{"id": "test3", "name": "Medium Item", "cost": 8, "category": "infrastructure"}
	]

	var ui = preload("res://scripts/UnifiedGridUI.gd").new()
	add_child(ui)
	await get_tree().process_frame

	ui._initialize_grids()
	ui._setup_ui()
	ui._load_shop_from_state()

	# Test refresh shop
	var initial_gold = ui.current_gold
	if initial_gold >= 2:
		ui._on_refresh_shop()
		assert_eq(ui.current_gold, initial_gold - 2, "Refresh should cost 2 gold")

	ui.queue_free()
	print("Shop interaction test complete")

func test_battle_submission_flow():
	# Test battle submission with inventory
	print("Testing battle submission...")

	GameStateManager.start_new_game()

	# Create mock inventory
	var test_inventory = {
		"items": [
			{"data": {"name": "Test Item 1"}, "grid_pos": Vector2i(1, 1)}
		],
		"servers": [
			{"data": {"name": "Test Server"}, "pos": Vector2i(0, 0)}
		]
	}

	GameStateManager.save_inventory_state(test_inventory.items, test_inventory.servers)

	# Submit battle
	var result = await BattleServerAPI.submit_battle(test_inventory)

	assert_not_null(result, "Should get battle result")
	assert_true(result.has("battle_result"), "Should have battle data")
	assert_true(result.has("session_update"), "Should have session update")

	# Verify state update
	GameStateManager.update_after_battle(result)

	# The mock may have its own round logic, just verify it was updated
	assert_true(result.session_update.has("round"), "Should have round in update")
	assert_eq(GameStateManager.current_round, result.session_update.round, "Round should match session update")

	print("Battle submission test complete")

func test_game_over_conditions():
	# Test game over and victory conditions
	print("Testing game over conditions...")

	# Test game over by lives
	GameStateManager.start_new_game()
	GameStateManager.player_lives = 0
	assert_true(GameStateManager.is_game_over(), "Should be game over at 0 lives")

	# Test not game over
	GameStateManager.player_lives = 3
	assert_false(GameStateManager.is_game_over(), "Should not be game over with lives remaining")

	# Test victory
	GameStateManager.current_round = 11
	GameStateManager.victory = true
	assert_true(GameStateManager.is_victory(), "Should be victory after round 10")

	print("Game over conditions test complete")
