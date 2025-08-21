extends GutTest
# Tests for PostBattleScreen to ensure no node errors

const APITypes = preload("res://scripts/api_types.gd")

func test_post_battle_screen_creation():
	# Test that PostBattleScreen can be created without errors
	var screen = preload("res://scripts/PostBattleScreen.gd").new()
	add_child(screen)
	await get_tree().process_frame

	# Verify all UI elements are created
	assert_not_null(screen.title_label, "Title label should be created")
	assert_not_null(screen.round_label, "Round label should be created")
	assert_not_null(screen.gold_label, "Gold label should be created")
	assert_not_null(screen.health_label, "Health label should be created")
	assert_not_null(screen.current_health_label, "Current health label should be created")
	assert_not_null(screen.continue_button, "Continue button should be created")

	screen.queue_free()

func test_victory_display():
	# Test displaying victory results
	var screen = preload("res://scripts/PostBattleScreen.gd").new()
	add_child(screen)
	await get_tree().process_frame

	# Set up victory data
	var victory_data = {
		"battle_result": {
			"winner": 1,  # Player won
			"duration": 15.0
		},
		"session_update": {
			"round": 2,
			"gold": 25,
			"gold_earned": 12,
			"wins": 1,
			"losses": 0
		},
		"health_lost": 0
	}

	screen.set_battle_result(victory_data)
	screen._display_results()

	# Check victory display
	assert_eq(screen.title_label.text, "VICTORY!", "Should show VICTORY!")
	assert_eq(screen.gold_label.text, "+12 Gold", "Should show gold earned")
	assert_false(screen.health_label.visible, "Health lost should not be visible on victory")

	screen.queue_free()

func test_defeat_display():
	# Test displaying defeat results
	var screen = preload("res://scripts/PostBattleScreen.gd").new()
	add_child(screen)
	await get_tree().process_frame

	# Set up defeat data
	var defeat_data = {
		"battle_result": {
			"winner": 2,  # Enemy won
			"duration": 20.0
		},
		"session_update": {
			"round": 3,
			"gold": 30,
			"gold_earned": 10,
			"wins": 2,
			"losses": 1
		},
		"health_lost": 15
	}

	screen.set_battle_result(defeat_data)
	screen._display_results()

	# Check defeat display
	assert_eq(screen.title_label.text, "DEFEAT", "Should show DEFEAT")
	assert_eq(screen.gold_label.text, "+10 Gold", "Should show gold earned")
	assert_true(screen.health_label.visible, "Health lost should be visible on defeat")
	assert_eq(screen.health_label.text, "-15 Health", "Should show health lost")

	screen.queue_free()

func test_game_state_update():
	# Test that battle results update GameStateManager
	var screen = preload("res://scripts/PostBattleScreen.gd").new()

	# Store initial state
	GameStateManager.start_new_game()
	var initial_round = GameStateManager.current_round
	var initial_gold = GameStateManager.gold
	var initial_health = GameStateManager.player_health

	# Set battle result
	var result_data = {
		"battle_result": {
			"winner": 1
		},
		"session_update": {
			"round": initial_round + 1,
			"gold": initial_gold + 15,
			"gold_earned": 15,
			"wins": 1,
			"losses": 0
		},
		"health_lost": 0,
		"new_shop": [
			{"id": "item1", "name": "Test Item", "cost": 5}
		]
	}

	screen.set_battle_result(result_data)

	# Verify GameStateManager was updated
	assert_eq(GameStateManager.current_round, initial_round + 1, "Round should be updated")
	assert_eq(GameStateManager.gold, initial_gold + 15, "Gold should be updated")
	assert_eq(GameStateManager.wins, 1, "Wins should be updated")
	assert_eq(GameStateManager.current_shop.size(), 1, "Shop should be updated")

	screen.queue_free()

func test_health_loss_on_defeat():
	# Test that health is properly reduced on defeat
	var screen = preload("res://scripts/PostBattleScreen.gd").new()

	GameStateManager.start_new_game()
	var initial_health = GameStateManager.player_health

	var defeat_data = {
		"battle_result": {
			"winner": 2  # Enemy won
		},
		"session_update": {
			"round": 1,
			"gold": 20,
			"losses": 1
		},
		"health_lost": 10
	}

	screen.set_battle_result(defeat_data)

	# Verify health was reduced
	assert_eq(GameStateManager.player_health, initial_health - 10, "Health should be reduced by health_lost")

	screen.queue_free()

func test_game_over_button_state():
	# Test that continue button changes when game is over
	var screen = preload("res://scripts/PostBattleScreen.gd").new()
	add_child(screen)
	await get_tree().process_frame

	# Set game over state
	GameStateManager.player_lives = 0

	var result_data = {
		"battle_result": {"winner": 2},
		"session_update": {"round": 5}
	}

	screen.set_battle_result(result_data)
	screen._display_results()

	# Check button text changed
	assert_eq(screen.continue_button.text, "GAME OVER", "Button should show GAME OVER")

	# Reset game state
	GameStateManager.start_new_game()
	screen.queue_free()

func test_round_display():
	# Test that round number is displayed correctly
	var screen = preload("res://scripts/PostBattleScreen.gd").new()
	add_child(screen)
	await get_tree().process_frame

	GameStateManager.current_round = 5

	var result_data = {
		"battle_result": {"winner": 1},
		"session_update": {"round": 5}
	}

	screen.set_battle_result(result_data)
	screen._display_results()

	# Round label should show completed round (current - 1)
	assert_eq(screen.round_label.text, "Round 4 Complete", "Should show completed round number")

	screen.queue_free()

func test_empty_result_handling():
	# Test that empty/null results don't crash
	var screen = preload("res://scripts/PostBattleScreen.gd").new()
	add_child(screen)
	await get_tree().process_frame

	# Try with minimal valid result data
	var minimal_data = {
		"winner": 1,
		"duration": 0.0,
		"player1_quota": 0,
		"player2_quota": 0,
		"seed": 0,
		"actions": [],
		"player_inventory": {"items": [], "servers": []},
		"enemy_inventory": {"items": [], "servers": []}
	}
	screen.set_battle_result(APITypes.BattleResult.new(minimal_data))
	screen._display_results()

	# Should not crash
	assert_true(true, "Should handle empty results without crashing")

	# Try with null (shouldn't happen but test anyway)
	screen.result_data = {}
	screen._display_results()

	assert_true(true, "Should handle null results without crashing")

	screen.queue_free()

func test_current_health_display():
	# Test that current health is displayed correctly
	var screen = preload("res://scripts/PostBattleScreen.gd").new()
	add_child(screen)
	await get_tree().process_frame

	GameStateManager.player_health = 75

	var result_data = {
		"battle_result": {"winner": 1},
		"session_update": {}
	}

	screen.set_battle_result(result_data)
	screen._display_results()

	assert_eq(screen.current_health_label.text, "Health: 75 / 100", "Should show current health")

	screen.queue_free()
