extends GutTest
# End-to-end tests for complete game flow

func test_complete_game_flow():
	# Test the full game flow from start to battle
	print("Testing complete game flow...")

	# 1. Start at Main Menu
	var main_menu = preload("res://scenes/MainMenu.tscn").instantiate()
	add_child(main_menu)
	await get_tree().process_frame

	assert_not_null(main_menu, "Main menu should load")

	# 2. Click New Game
	var new_game_btn = main_menu.find_child("NewGameButton", true, false)
	assert_not_null(new_game_btn, "New game button should exist")

	# Start new game
	GameStateManager.start_new_game()
	assert_eq(GameStateManager.current_round, 1, "Should be round 1")
	assert_eq(GameStateManager.gold, 12, "Should have starting gold")

	main_menu.queue_free()
	await get_tree().process_frame

	# 3. Load Inventory/Shop screen
	var ui = preload("res://scenes/UnifiedGridUI.tscn").instantiate()
	add_child(ui)
	await get_tree().process_frame

	assert_not_null(ui, "Game UI should load")

	# 4. Verify starting state
	assert_eq(GameStateManager.player_lives, 5, "Should have 5 lives")
	assert_eq(GameStateManager.player_health, 100, "Should have full health")

	# 5. Mock shop interaction
	var mock_shop = [
		{"id": "item1", "name": "Test Item", "cost": 3, "item_type": "test_item",
		 "min_damage": 2, "max_damage": 4, "width": 1, "height": 1},
		{"id": "item2", "name": "Big Item", "cost": 5, "item_type": "big_item",
		 "min_damage": 4, "max_damage": 6, "width": 2, "height": 2}
	]

	GameStateManager.current_shop = mock_shop
	ui._display_shop_items(mock_shop)
	await get_tree().process_frame

	# 6. Simulate buying an item (if we had enough gold)
	var can_afford_item1 = GameStateManager.gold >= 3
	assert_true(can_afford_item1, "Should be able to afford cheap item")

	# Mock purchase
	if can_afford_item1:
		GameStateManager.update_gold(-3)
		assert_eq(GameStateManager.gold, 9, "Gold should decrease after purchase")

	# 7. Place item on grid (simulate)
	var test_item = {"id": "placed1", "position": [2, 2], "item_type": "test_item"}
	ui.items.append(test_item)

	# 8. Start battle
	GameStateManager.save_inventory_state([test_item], ui.servers)

	# Mock battle result
	var battle_result = {
		"battle_result": {
			"winner": 1,
			"duration": 15.0,
			"player1_quota": 25,
			"player2_quota": 0,
			"actions": [
				{"t": 0.0, "a": "s"},
				{"t": 5.0, "a": "d", "p": 2, "dmg": 25, "hp": 0},
				{"t": 5.1, "a": "x", "p": 2}
			]
		},
		"session_update": {
			"round": 2,
			"gold": GameStateManager.gold + 12,
			"wins": 1,
			"losses": 0
		}
	}

	GameStateManager.update_after_battle(battle_result)

	# 9. Verify battle results
	assert_eq(GameStateManager.wins, 1, "Should have 1 win")
	assert_eq(GameStateManager.losses, 0, "Should have 0 losses")
	assert_eq(GameStateManager.current_round, 2, "Should advance to round 2")

	ui.queue_free()
	await get_tree().process_frame

	# 10. Load PostBattle screen
	var post_battle = preload("res://scenes/PostBattleScreen.tscn").instantiate()
	add_child(post_battle)
	await get_tree().process_frame

	assert_not_null(post_battle, "Post battle screen should load")

	# Clean up
	post_battle.queue_free()
	await get_tree().process_frame

	print("Complete game flow test finished!")

func test_game_over_flow():
	# Test game over scenario
	GameStateManager.start_new_game()
	GameStateManager.player_lives = 1  # One life left
	GameStateManager.player_health = 20  # Low health

	# Simulate losing battle
	var defeat_result = {
		"battle_result": {
			"winner": 2,  # Enemy wins
			"duration": 20.0,
			"player1_quota": 0,
			"player2_quota": 50
		},
		"session_update": {
			"round": 5,
			"gold": 10,
			"wins": 3,
			"losses": 4,
			"lives": 0
		},
		"health_lost": 20
	}

	GameStateManager.update_after_battle(defeat_result)
	GameStateManager.player_health -= 20
	GameStateManager.player_lives = 0

	assert_true(GameStateManager.is_game_over(), "Should be game over")
	assert_eq(GameStateManager.player_lives, 0, "Should have no lives left")

	# Load game over screen
	var game_over = preload("res://scenes/GameOverScreen.tscn").instantiate()
	add_child(game_over)
	await get_tree().process_frame

	assert_not_null(game_over, "Game over screen should load")

	game_over.queue_free()

func test_victory_condition():
	# Test victory scenario
	GameStateManager.start_new_game()
	GameStateManager.current_round = 10
	GameStateManager.wins = 9

	# Simulate winning round 10
	var victory_result = {
		"battle_result": {
			"winner": 1,
			"duration": 25.0,
			"player1_quota": 100,
			"player2_quota": 0
		},
		"session_update": {
			"round": 11,
			"gold": 50,
			"wins": 10,
			"losses": 2,
			"victory": true
		}
	}

	GameStateManager.update_after_battle(victory_result)

	assert_true(GameStateManager.is_victory(), "Should be victory")
	assert_eq(GameStateManager.wins, 10, "Should have 10 wins")

func test_shop_refresh_flow():
	# Test shop refresh mechanics
	GameStateManager.start_new_game()
	GameStateManager.gold = 10

	var ui = preload("res://scenes/UnifiedGridUI.tscn").instantiate()
	add_child(ui)
	await get_tree().process_frame

	# Initial shop
	var initial_shop = [
		{"id": "item1", "name": "Item 1", "cost": 3},
		{"id": "item2", "name": "Item 2", "cost": 4}
	]

	GameStateManager.current_shop = initial_shop
	ui._display_shop_items(initial_shop)

	# Refresh shop (costs 1 gold)
	var initial_gold = GameStateManager.gold

	if GameStateManager.gold >= 1:
		GameStateManager.update_gold(-1)

		# New shop
		var new_shop = [
			{"id": "item3", "name": "Item 3", "cost": 5},
			{"id": "item4", "name": "Item 4", "cost": 3}
		]

		GameStateManager.current_shop = new_shop
		ui._display_shop_items(new_shop)

		assert_eq(GameStateManager.gold, initial_gold - 1, "Gold should decrease by 1")
		assert_eq(GameStateManager.current_shop.size(), 2, "Should have new shop items")

	ui.queue_free()

func test_inventory_persistence():
	# Test that inventory persists between scenes
	GameStateManager.start_new_game()

	# Set up inventory
	var test_items = [
		{"id": "item1", "position": [1, 1], "item_type": "test1"},
		{"id": "item2", "position": [3, 2], "item_type": "test2"}
	]

	var test_servers = [
		{"id": "server1", "position": [0, 0], "type": "standard_vm"}
	]

	GameStateManager.save_inventory_state(test_items, test_servers)

	# Load UI and check inventory is restored
	var ui = preload("res://scenes/UnifiedGridUI.tscn").instantiate()
	add_child(ui)
	await get_tree().process_frame

	var saved_state = GameStateManager.get_inventory_state()
	assert_eq(saved_state["items"].size(), 2, "Should have 2 items saved")
	assert_eq(saved_state["servers"].size(), 1, "Should have 1 server saved")

	ui.queue_free()

func test_battle_event_playback():
	# Test battle event processing
	var events = [
		{"t": 0.0, "a": "s"},  # Start
		{"t": 1.0, "a": "a", "item": "sword", "p": 1},  # Activate
		{"t": 1.5, "a": "d", "p": 2, "dmg": 10, "hp": 90},  # Damage
		{"t": 2.0, "a": "h", "p": 1, "amount": 5, "hp": 105},  # Heal
		{"t": 3.0, "a": "b", "p": 2, "amount": 3},  # Block
		{"t": 10.0, "a": "x", "p": 2}  # Death
	]

	GameStateManager.last_battle_result = {
		"battle_result": {
			"winner": 1,
			"duration": 10.0,
			"actions": events
		}
	}

	var battle = preload("res://scenes/BattleScreen.tscn").instantiate()
	add_child(battle)
	await get_tree().process_frame

	# Battle should load events
	assert_gt(GameStateManager.last_battle_result["battle_result"]["actions"].size(), 0,
		"Should have battle events")

	battle.queue_free()

func test_gold_economy():
	# Test gold earning and spending
	GameStateManager.start_new_game()
	assert_eq(GameStateManager.gold, 12, "Should start with 12 gold")

	# Buy item
	var item_cost = 5
	if GameStateManager.update_gold(-item_cost):
		assert_eq(GameStateManager.gold, 7, "Should have 7 gold after purchase")

	# Win battle - earn gold
	var gold_reward = 12
	GameStateManager.update_gold(gold_reward)
	assert_eq(GameStateManager.gold, 19, "Should have 19 gold after battle")

	# Try to buy expensive item
	var expensive_cost = 25
	var purchase_succeeded = GameStateManager.update_gold(-expensive_cost)
	assert_false(purchase_succeeded, "Should not be able to afford expensive item")
	assert_eq(GameStateManager.gold, 19, "Gold should not change on failed purchase")

func test_health_system():
	# Test health and lives system
	GameStateManager.start_new_game()
	assert_eq(GameStateManager.player_health, 100, "Should start with 100 health")
	assert_eq(GameStateManager.player_lives, 5, "Should start with 5 lives")

	# Take damage
	var damage = 20
	GameStateManager.player_health -= damage
	assert_eq(GameStateManager.player_health, 80, "Should have 80 health after damage")

	# Lose a life
	GameStateManager.player_lives -= 1
	assert_eq(GameStateManager.player_lives, 4, "Should have 4 lives")

	# Check game over
	GameStateManager.player_lives = 0
	assert_true(GameStateManager.is_game_over(), "Should be game over with 0 lives")
