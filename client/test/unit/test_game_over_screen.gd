extends GutTest
# Tests for GameOverScreen.
#
# The whole screen is built in code by _setup_ui(), then filled in by
# _display_final_stats(). It is the last thing a player sees in a run, so the
# numbers on it have to be right.

var game_over_scene = preload("res://scenes/GameOverScreen.tscn")
var screen


func _open_screen() -> Node:
	var instance = game_over_scene.instantiate()
	add_child(instance)
	await get_tree().process_frame
	return instance


func after_each():
	if is_instance_valid(screen):
		remove_child(screen)
		screen.queue_free()
	screen = null
	await get_tree().process_frame


func _label(node_name: String) -> Label:
	return screen.find_child(node_name, true, false)


# ============ Structure ============

func test_screen_loads():
	GameStateManager.start_new_game()
	screen = await _open_screen()

	assert_not_null(screen, "Game over screen should load")
	assert_true(screen.visible, "Game over screen should be visible")


func test_has_the_three_buttons():
	GameStateManager.start_new_game()
	screen = await _open_screen()

	var labels = []
	for button in _find_buttons(screen):
		labels.append(button.text)

	assert_true("NEW GAME" in labels, "Should offer a new game")
	assert_true("MAIN MENU" in labels, "Should offer the main menu")
	assert_true("EXIT" in labels, "Should offer exit")


func _find_buttons(node: Node) -> Array:
	var found = []
	for child in node.get_children():
		if child is Button:
			found.append(child)
		found.append_array(_find_buttons(child))
	return found


func test_buttons_are_wired():
	# Do NOT press EXIT: _on_exit() calls get_tree().quit().
	GameStateManager.start_new_game()
	screen = await _open_screen()

	var by_text = {}
	for button in _find_buttons(screen):
		by_text[button.text] = button

	assert_true(by_text["NEW GAME"].pressed.is_connected(screen._on_new_game),
		"New game button should be wired")
	assert_true(by_text["MAIN MENU"].pressed.is_connected(screen._on_main_menu),
		"Main menu button should be wired")
	assert_true(by_text["EXIT"].pressed.is_connected(screen._on_exit),
		"Exit button should be wired")


# ============ Final stats ============

func test_shows_the_final_round():
	GameStateManager.start_new_game()
	GameStateManager.current_round = 7
	screen = await _open_screen()

	assert_eq(_label("FinalRoundLabel").text, "Final Round: 7", "Should show the round reached")


func test_shows_the_battle_record_and_win_rate():
	GameStateManager.start_new_game()
	GameStateManager.wins = 3
	GameStateManager.losses = 1
	screen = await _open_screen()

	var text = _label("WinsLabel").text
	assert_true("3 Wins" in text, "Should show the wins")
	assert_true("1 Losses" in text, "Should show the losses")
	assert_true("75%" in text, "Should work out the win rate")


func test_win_rate_with_no_battles_does_not_divide_by_zero():
	GameStateManager.start_new_game()
	GameStateManager.wins = 0
	GameStateManager.losses = 0
	screen = await _open_screen()

	assert_true("0%" in _label("WinsLabel").text, "No battles should read as 0%")


func test_shows_the_score():
	GameStateManager.start_new_game()
	GameStateManager.current_round = 4
	GameStateManager.wins = 2
	screen = await _open_screen()

	# rounds * 100 + wins * 50, with no victory bonus below round 11
	assert_eq(_label("ScoreLabel").text, "Final Score: 500", "Should work out the score")


func test_shows_total_gold():
	GameStateManager.start_new_game()
	GameStateManager.current_round = 5
	screen = await _open_screen()

	assert_eq(_label("TotalGoldLabel").text, "Total Gold Earned: 60", "Should estimate gold earned")


# ============ Defeat and victory ============

func test_defeat_says_game_over():
	GameStateManager.start_new_game()
	GameStateManager.current_round = 3
	screen = await _open_screen()

	assert_eq(_label("GameOverTitle").text, "GAME OVER", "A defeat should say GAME OVER")
	assert_false(_label("VictorySubtitle").visible, "A defeat should show no victory subtitle")


func test_victory_past_round_ten_says_victory():
	GameStateManager.start_new_game()
	GameStateManager.current_round = 11
	GameStateManager.player_health = 50
	screen = await _open_screen()

	assert_eq(_label("GameOverTitle").text, "VICTORY!", "Surviving past round 10 should be a victory")
	assert_true(_label("VictorySubtitle").visible, "A victory should show its subtitle")


func test_victory_adds_a_score_bonus():
	GameStateManager.start_new_game()
	GameStateManager.current_round = 11
	GameStateManager.player_health = 50
	GameStateManager.wins = 0
	screen = await _open_screen()

	# 11 * 100, plus the 1000 victory bonus
	assert_eq(_label("ScoreLabel").text, "Final Score: 2100", "A victory should add its bonus")
