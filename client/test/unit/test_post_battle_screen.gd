extends GutTest
# Tests for PostBattleScreen
#
# set_battle_result() takes an APITypes.BattleResult, built here by
# _make_battle_result(). Gold earned is read from
# GameStateManager.last_gold_earned, not from the battle result.

const APITypes = preload("res://scripts/api_types.gd")


func _make_battle_result(winner: int) -> APITypes.BattleResult:
	return APITypes.BattleResult.new({
		"winner": winner,
		"duration": 15.0,
		"player1_quota": 80,
		"player2_quota": 0,
		"seed": 12345,
		"actions": [],
		"opponent_name": "AI Opponent",
		"opponent_type": "ai",
		"player_inventory": {"items": [], "servers": []},
		"enemy_inventory": {"items": [], "servers": []}
	})

func test_post_battle_screen_creation():
	# Test that PostBattleScreen can be created without errors
	var screen = preload("res://scripts/post_battle_screen.gd").new()
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
	var screen = preload("res://scripts/post_battle_screen.gd").new()
	add_child(screen)
	await get_tree().process_frame

	# Gold earned comes from GameStateManager, set by update_after_battle()
	GameStateManager.last_gold_earned = 12

	screen.set_battle_result(_make_battle_result(1))  # Player won
	screen._display_results()

	# Check victory display
	assert_eq(screen.title_label.text, "VICTORY!", "Should show VICTORY!")
	assert_eq(screen.gold_label.text, "+12 Gold", "Should show gold earned")
	assert_false(screen.health_label.visible, "Health lost should not be visible on victory")

	screen.queue_free()

func test_defeat_display():
	# Test displaying defeat results
	var screen = preload("res://scripts/post_battle_screen.gd").new()
	add_child(screen)
	await get_tree().process_frame

	GameStateManager.last_gold_earned = 10

	screen.set_battle_result(_make_battle_result(2))  # Enemy won
	screen._display_results()

	# set_battle_result() subtracts a fixed 1 health on a defeat. It takes no
	# amount from the battle result, so the label always reads "-1 Health".
	assert_eq(screen.title_label.text, "DEFEAT", "Should show DEFEAT")
	assert_eq(screen.gold_label.text, "+10 Gold", "Should show gold earned")
	assert_true(screen.health_label.visible, "Health lost should be visible on defeat")
	assert_eq(screen.health_label.text, "-1 Health", "Should show health lost")

	screen.queue_free()

func test_game_state_update():
	# GameStateManager.update_after_battle() applies these when the battle
	# response arrives, before this screen loads. set_battle_result() only reads
	# them back. Covered by
	# test_game_state_manager.gd::test_battle_result_updates_state.
	pending("Round, gold, wins and shop are updated by GameStateManager.update_after_battle().")

func test_health_loss_on_defeat():
	# set_battle_result() subtracts a fixed 1 health on a defeat.
	var screen = preload("res://scripts/post_battle_screen.gd").new()

	GameStateManager.start_new_game()
	var initial_health = GameStateManager.player_health

	screen.set_battle_result(_make_battle_result(2))  # Enemy won

	assert_eq(GameStateManager.player_health, initial_health - 1,
		"Health should be reduced on a defeat")

	screen.queue_free()

func test_no_health_loss_on_victory():
	var screen = preload("res://scripts/post_battle_screen.gd").new()

	GameStateManager.start_new_game()
	var initial_health = GameStateManager.player_health

	screen.set_battle_result(_make_battle_result(1))  # Player won

	assert_eq(GameStateManager.player_health, initial_health,
		"Health should not change on a win")

	screen.queue_free()

func test_game_over_button_state():
	# Test that continue button changes when game is over
	var screen = preload("res://scripts/post_battle_screen.gd").new()
	add_child(screen)
	await get_tree().process_frame

	# Set game over state
	GameStateManager.player_lives = 0

	screen.set_battle_result(_make_battle_result(2))
	screen._display_results()

	# Check button text changed
	assert_eq(screen.continue_button.text, "GAME OVER", "Button should show GAME OVER")

	# Reset game state
	GameStateManager.start_new_game()
	screen.queue_free()

func test_round_display():
	# Test that round number is displayed correctly
	var screen = preload("res://scripts/post_battle_screen.gd").new()
	add_child(screen)
	await get_tree().process_frame

	GameStateManager.current_round = 5

	screen.set_battle_result(_make_battle_result(1))
	screen._display_results()

	# Round label should show completed round (current - 1)
	assert_eq(screen.round_label.text, "Round 4 Complete", "Should show completed round number")

	screen.queue_free()

func test_empty_result_handling():
	# Test that empty/null results don't crash
	var screen = preload("res://scripts/post_battle_screen.gd").new()
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
		"opponent_name": "AI Opponent",
		"opponent_type": "ai",
		"player_inventory": {"items": [], "servers": []},
		"enemy_inventory": {"items": [], "servers": []}
	}
	screen.set_battle_result(APITypes.BattleResult.new(minimal_data))
	screen._display_results()

	# A battle with no actions still shows a result
	assert_eq(screen.title_label.text, "VICTORY!",
		"An empty battle should still show its outcome")

	# _display_results() returns early when there is no result at all
	screen.result_data = null
	screen.title_label.text = "unchanged"
	screen._display_results()

	assert_eq(screen.title_label.text, "unchanged",
		"A null result should leave the display alone, not crash")

	screen.queue_free()

func test_current_health_display():
	# Test that current health is displayed correctly
	var screen = preload("res://scripts/post_battle_screen.gd").new()
	add_child(screen)
	await get_tree().process_frame

	GameStateManager.player_health = 75

	screen.set_battle_result(_make_battle_result(1))
	screen._display_results()

	assert_eq(screen.current_health_label.text, "Health: 75 / 100", "Should show current health")

	screen.queue_free()
