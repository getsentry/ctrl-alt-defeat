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


func _row(node_name: String) -> String:
	# A stat is a caption and a value now, the way an item's card writes one,
	# so what a player reads is both halves of the line.
	var value: Label = _label(node_name)
	var caption: Label = value.get_parent().get_child(0)
	return "%s %s" % [caption.text, value.text]


# ============ Structure ============

func test_screen_loads():
	GameStateManager.start_new_game()
	screen = await _open_screen()

	assert_not_null(screen, "Game over screen should load")
	assert_true(screen.visible, "Game over screen should be visible")


func test_has_the_two_buttons():
	GameStateManager.start_new_game()
	screen = await _open_screen()

	var labels = []
	for button in _find_buttons(screen):
		labels.append(button.text)

	assert_true("NEW GAME" in labels, "Should offer a new game")
	assert_true("MAIN MENU" in labels, "Should offer the main menu")
	assert_false("EXIT" in labels,
		"Quitting the game belongs to the menu, not to the end of a run")


func test_the_buttons_are_the_game_s_own_keys():
	# The screen is built in code, which is how it ended up as a wall of
	# default grey buttons on a flat rectangle.
	GameStateManager.start_new_game()
	screen = await _open_screen()

	for button in _find_buttons(screen):
		assert_true(button.has_theme_stylebox_override("normal"),
			"%s should be a keycap, not a default Button" % button.text)


func test_it_is_built_on_a_panel():
	GameStateManager.start_new_game()
	screen = await _open_screen()

	var panel = screen.find_child("Panel", true, false)
	assert_not_null(panel, "The words should sit on a slab, not on the screen")
	assert_true(panel.has_theme_stylebox_override("panel"), "and it should be dressed")


func _find_buttons(node: Node) -> Array:
	var found = []
	for child in node.get_children():
		if child is Button:
			found.append(child)
		found.append_array(_find_buttons(child))
	return found


func test_buttons_are_wired():
	GameStateManager.start_new_game()
	screen = await _open_screen()

	var by_text = {}
	for button in _find_buttons(screen):
		by_text[button.text] = button

	assert_true(by_text["NEW GAME"].pressed.is_connected(screen._on_new_game),
		"New game button should be wired")
	assert_true(by_text["MAIN MENU"].pressed.is_connected(screen._on_main_menu),
		"Main menu button should be wired")


# ============ Final stats ============

func test_shows_the_final_round():
	GameStateManager.start_new_game()
	GameStateManager.current_round = 7
	screen = await _open_screen()

	assert_eq(_row("FinalRoundLabel"), "Rounds survived 7 of 10",
		"Should show the round reached, and what it was out of")


func test_shows_the_battle_record_and_win_rate():
	GameStateManager.start_new_game()
	GameStateManager.wins = 3
	GameStateManager.losses = 1
	screen = await _open_screen()

	var text = _row("WinsLabel")
	assert_true("3 won" in text, "Should show the wins")
	assert_true("1 lost" in text, "Should show the losses")
	assert_true("75%" in text, "Should work out the win rate")


func test_win_rate_with_no_battles_does_not_divide_by_zero():
	GameStateManager.start_new_game()
	GameStateManager.wins = 0
	GameStateManager.losses = 0
	screen = await _open_screen()

	assert_true("0%" in _row("WinsLabel"), "No battles should read as 0%")


func test_shows_the_score():
	GameStateManager.start_new_game()
	GameStateManager.current_round = 4
	GameStateManager.wins = 2
	screen = await _open_screen()

	# rounds * 100 + wins * 50, with no victory bonus below round 11
	assert_eq(_row("ScoreLabel"), "Score 500", "Should work out the score")


func test_shows_total_gold():
	GameStateManager.start_new_game()
	GameStateManager.current_round = 5
	screen = await _open_screen()

	assert_eq(_row("TotalGoldLabel"), "Gold earned 60", "Should estimate gold earned")


func test_the_winner_stands_beside_the_panel():
	GameStateManager.start_new_game()
	GameStateManager.victory = true
	screen = await _open_screen()

	var winner = screen.find_child("Winner", true, false)
	assert_not_null(winner, "A win should show the Sentaur the player picked")
	assert_not_null(winner.texture, "and it should have their artwork in it")


func test_a_lost_run_is_not_made_to_look_at_itself():
	GameStateManager.start_new_game()
	GameStateManager.victory = false
	screen = await _open_screen()

	assert_null(screen.find_child("Winner", true, false),
		"A defeat is not the moment to put the player's character in front of them")


# ============ Defeat and victory ============

func test_a_lost_run_says_defeat():
	# Not "game over": a run that goes the distance ends too, and both of
	# them are an ending. What a player wants to know is which one it was.
	GameStateManager.start_new_game()
	GameStateManager.current_round = 3
	screen = await _open_screen()

	assert_eq(_label("GameOverTitle").text, "DEFEAT", "A lost run should say DEFEAT")
	assert_eq(_label("Subtitle").text, "Your uptime ran out",
		"and say it in the game's own words")


func test_a_won_run_says_victory():
	GameStateManager.start_new_game()
	GameStateManager.current_round = 11
	GameStateManager.wins = GameStateManager.WINS_TO_VICTORY
	GameStateManager.victory = true
	screen = await _open_screen()

	assert_eq(_label("GameOverTitle").text, "VICTORY",
		"Banking the wins the run is played for should be a victory")
	assert_eq(_label("Subtitle").text, "You saw off every opponent",
		"and congratulate the player without inventing a cause for them")


func test_victory_adds_a_score_bonus():
	GameStateManager.start_new_game()
	GameStateManager.current_round = 11
	GameStateManager.victory = true
	GameStateManager.wins = 0
	screen = await _open_screen()

	# 11 * 100, plus the 1000 victory bonus
	assert_eq(_row("ScoreLabel"), "Score 2100", "A victory should add its bonus")
