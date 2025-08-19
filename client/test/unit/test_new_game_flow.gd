extends GutTest
# Test the actual new game flow to catch real bugs

func test_all_required_properties_exist():
	# This test should catch missing properties like player_health
	print("Testing all required GameStateManager properties...")

	# All properties that the game actually uses
	var required_properties = [
		"player_id",
		"player_name",
		"current_round",
		"player_lives",
		"player_health",  # This was missing!
		"max_player_health",  # This might be missing too!
		"battle_health",
		"gold",
		"wins",
		"losses",
		"game_over",
		"victory",
		"current_inventory",
		"server_containers",
		"starting_containers",
		"current_shop",
		"shop_rerolls",
		"last_battle_result",
		"last_battle_events",
		"opponent_inventory",
		"battle_speed",
		"auto_ready"
	]

	for prop in required_properties:
		assert_true(prop in GameStateManager,
			"GameStateManager missing required property: %s" % prop)

func test_new_game_initializes_all_values():
	# Test that start_new_game sets all required values
	GameStateManager.start_new_game()

	# These are all accessed by the actual game code
	assert_not_null(GameStateManager.player_id, "player_id should not be null")
	assert_not_null(GameStateManager.current_round, "current_round should not be null")
	assert_not_null(GameStateManager.player_lives, "player_lives should not be null")
	assert_not_null(GameStateManager.gold, "gold should not be null")

	# This is what's failing - player_health is accessed but not defined!
	assert_true("player_health" in GameStateManager, "player_health property must exist")
	if "player_health" in GameStateManager:
		assert_not_null(GameStateManager.player_health, "player_health should not be null")
		assert_gt(GameStateManager.player_health, 0, "player_health should be > 0")

	# Check max_player_health too
	assert_true("max_player_health" in GameStateManager, "max_player_health property must exist")

func test_unified_grid_ui_accesses():
	# Test properties that UnifiedGridUI.gd actually accesses
	GameStateManager.start_new_game()

	# Line 160-162 in UnifiedGridUI
	var gold = GameStateManager.gold
	var round = GameStateManager.current_round

	# Line 162 - THIS IS THE BUG - player_health is accessed but doesn't exist!
	assert_true("player_health" in GameStateManager,
		"UnifiedGridUI accesses player_health but it doesn't exist!")

	# Line 1131 in _get_stats_text()
	assert_true("max_player_health" in GameStateManager,
		"UnifiedGridUI accesses max_player_health but it doesn't exist!")

func test_main_menu_to_shop_flow():
	# Simulate the actual flow that's failing
	print("Simulating MainMenu -> Shop flow...")

	# 1. Start new game (what MainMenu does)
	GameStateManager.start_new_game()

	# 2. Simulate session start
	var session_data = {
		"player_id": "test-123",
		"round": 1,
		"gold": 10,
		"current_shop": [],
		"starting_containers": []
	}

	GameStateManager.player_id = session_data.player_id
	GameStateManager.current_round = session_data.round
	GameStateManager.gold = session_data.gold
	GameStateManager.current_shop = session_data.current_shop

	if session_data.has("starting_containers"):
		GameStateManager.starting_containers = session_data.starting_containers

	# 3. What UnifiedGridUI will try to access in _ready()
	print("Testing what UnifiedGridUI._ready() accesses...")

	# These lines from UnifiedGridUI._ready() - lines 160-162
	var test_gold = GameStateManager.gold
	var test_round = GameStateManager.current_round

	# THIS IS THE FAILING LINE - UnifiedGridUI.gd line 162
	assert_true("player_health" in GameStateManager,
		"UnifiedGridUI tries to access player_health but it doesn't exist!")

	if "player_health" in GameStateManager:
		var test_health = GameStateManager.player_health  # This would crash without the property
		assert_not_null(test_health, "player_health should not be null")
