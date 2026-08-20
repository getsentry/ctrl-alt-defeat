extends GutTest
# Critical path smoke tests - these MUST always pass

const APITypes = preload("res://scripts/api_types.gd")
const TestHelpers = preload("res://test/utils/test_helpers.gd")

func before_each():
	TestHelpers.reset_game_state()

func after_each():
	TestHelpers.reset_game_state()

func test_game_can_start():
	"""Critical: Game must be able to start"""
	GameStateManager.start_new_game()

	assert_eq(GameStateManager.current_round, 1, "Game should start at round 1")
	assert_eq(GameStateManager.gold, 12, "Should have starting gold")
	assert_eq(GameStateManager.player_lives, 5, "Should have full lives")
	TestHelpers.assert_valid_gold(self, GameStateManager.gold)

func test_can_load_main_menu():
	"""Critical: Main menu must load without errors"""
	var main_menu = load("res://scenes/MainMenu.tscn").instantiate()
	add_child(main_menu)
	await get_tree().process_frame

	assert_not_null(main_menu, "Main menu should load")
	assert_true(main_menu.visible, "Main menu should be visible")

	# Verify critical buttons exist
	var new_game_btn = main_menu.new_game_button
	assert_not_null(new_game_btn, "New Game button must exist")
	assert_false(new_game_btn.disabled, "New Game button should be enabled")

	main_menu.queue_free()
	await get_tree().process_frame

func test_can_load_game_ui():
	"""Critical: Game UI must load without errors"""
	var game_ui = load("res://scenes/UnifiedGridUI.tscn").instantiate()
	add_child(game_ui)
	await get_tree().process_frame

	assert_not_null(game_ui, "Game UI should load")
	assert_true(game_ui.visible, "Game UI should be visible")

	game_ui.queue_free()
	await get_tree().process_frame

func test_can_load_battle_screen():
	"""Critical: Battle screen must load without errors"""
	# Set up minimal battle data
	GameStateManager.last_battle_result = TestHelpers.create_test_battle_result()

	var battle_screen = load("res://scenes/BattleScreen.tscn").instantiate()
	add_child(battle_screen)
	await get_tree().process_frame

	assert_not_null(battle_screen, "Battle screen should load")
	assert_true(battle_screen.visible, "Battle screen should be visible")

	# Verify no script errors occurred
	TestHelpers.assert_no_script_errors(self)

	battle_screen.queue_free()
	await get_tree().process_frame

func test_api_types_can_parse_server_data():
	"""Critical: API types must be able to parse server responses"""
	# Test BattleResult parsing
	var battle_data = {
		"winner": 1,
		"duration": 10.0,
		"player1_quota": 100,
		"player2_quota": 0,
		"seed": 12345,
		"actions": [],
		"opponent_name": "AI Opponent",
		"opponent_type": "ai",
		"player_inventory": {"items": [], "servers": []},
		"enemy_inventory": {"items": [], "servers": []}
	}

	var battle_result = APITypes.BattleResult.new(battle_data)
	assert_not_null(battle_result, "Should create BattleResult from data")
	assert_eq(battle_result.winner, 1, "Winner should be parsed correctly")

	# Test SessionUpdate parsing
	var session_data = {
		"round": 2,
		"gold": 15,
		"gold_earned": 3,
		"wins": 1,
		"losses": 0,
		"lives": 5,
		"game_over": false,
		"victory": false,
		"combinations": [], "pending": []
	}

	var session_update = APITypes.SessionUpdate.new(session_data)
	assert_not_null(session_update, "Should create SessionUpdate from data")
	assert_eq(session_update.round, 2, "Round should be parsed correctly")
	assert_eq(session_update.gold, 15, "Gold should be parsed correctly")

func test_state_persistence():
	"""Critical: Game state must persist correctly"""
	# Set some state
	GameStateManager.current_round = 3
	GameStateManager.gold = 25
	GameStateManager.player_lives = 3

	# Verify it persists
	assert_eq(GameStateManager.current_round, 3, "Round should persist")
	assert_eq(GameStateManager.gold, 25, "Gold should persist")
	assert_eq(GameStateManager.player_lives, 3, "Lives should persist")

	# Reset and verify clean state
	GameStateManager.start_new_game()
	assert_eq(GameStateManager.current_round, 1, "Should reset to round 1")
	assert_eq(GameStateManager.gold, 12, "Should reset to starting gold")
	assert_eq(GameStateManager.player_lives, 5, "Should reset to full lives")

func test_gold_cannot_be_spent_below_zero():
	"""Critical: spending more gold than you hold must be refused"""
	GameStateManager.start_new_game()
	GameStateManager.gold = 10

	assert_false(GameStateManager.update_gold(-11), "Overspending should be refused")
	assert_eq(GameStateManager.gold, 10, "A refused spend should leave gold alone")
	TestHelpers.assert_valid_gold(self, GameStateManager.gold)

	assert_true(GameStateManager.update_gold(-10), "Spending exactly what you hold is allowed")
	assert_eq(GameStateManager.gold, 0, "Gold should reach zero, not go below")
	TestHelpers.assert_valid_gold(self, GameStateManager.gold)

func test_no_negative_values():
	"""Critical: Game values should never go negative"""
	# gold and player_lives are plain properties. Only gold has a guard,
	# update_gold(), covered above. A direct assignment is not clamped, so
	# lives can still be driven negative.
	pending("GameStateManager does not clamp player_lives.")
