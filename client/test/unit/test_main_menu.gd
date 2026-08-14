extends GutTest
# Tests for MainMenu UI
#
# Node lookups go through the script's own references (main_menu.new_game_button
# and so on) rather than find_child() with a literal name, because the scene
# names nodes with a "Parent_Child#Name" convention. A scene rename then breaks
# MainMenu.gd and these tests together.
#
# The menu has two buttons: New Game and Quit.

var main_menu_scene = preload("res://scenes/MainMenu.tscn")
var main_menu

func before_each():
	main_menu = main_menu_scene.instantiate()
	add_child(main_menu)
	await get_tree().process_frame

func after_each():
	if main_menu:
		main_menu.queue_free()
		main_menu = null
	await get_tree().process_frame


func test_main_menu_loads():
	assert_not_null(main_menu, "MainMenu should load")
	assert_true(main_menu.visible, "MainMenu should be visible")


func test_all_buttons_exist():
	assert_not_null(main_menu.new_game_button, "New Game button should exist")
	assert_not_null(main_menu.quit_button, "Quit button should exist")


func test_continue_button_disabled_initially():
	pending("No Continue button exists. Save/resume is not implemented.")


func test_settings_button_exists_but_disabled():
	pending("No Settings button exists. Settings are not implemented.")


func test_new_game_button_enabled():
	assert_false(main_menu.new_game_button.disabled, "New Game button should be enabled")


func test_new_game_button_click():
	# Set junk values first, so passing cannot be an accident of fresh state.
	GameStateManager.current_round = 7
	GameStateManager.gold = 999
	GameStateManager.player_lives = 2

	main_menu.new_game_button.pressed.emit()
	await get_tree().process_frame

	assert_eq(GameStateManager.current_round, 1, "Should reset to round 1")
	assert_eq(GameStateManager.gold, 12, "Should have starting gold")
	assert_eq(GameStateManager.player_lives, 5, "Should have full lives")


func test_quit_button_functionality():
	# Do NOT emit pressed. The handler is _on_exit(), which calls
	# get_tree().quit() and would end the whole test run.
	assert_true(
		main_menu.quit_button.pressed.is_connected(main_menu._on_exit),
		"Quit button should be connected to _on_exit"
	)


func test_version_label_exists():
	var version_label = main_menu.version_label
	assert_not_null(version_label, "Version label should exist")
	assert_ne(version_label.text, "", "Version label should have text")


func test_title_displayed():
	# The game name is artwork, not a text label.
	var logo = main_menu.find_child("LogoContainer", true, false)
	assert_not_null(logo, "Title should be displayed")
	assert_not_null(logo.texture, "Title artwork should have a texture")


func test_name_input_exists():
	var name_input = main_menu.name_input
	assert_not_null(name_input, "Player name input should exist")
	assert_true(name_input is LineEdit, "Player name input should be a LineEdit")


func test_background_exists():
	var background = main_menu.find_child("Background", true, false)
	assert_not_null(background, "Menu should have a background")
	assert_true(background is TextureRect, "Background should be a TextureRect")


func test_button_hover_effects():
	# _setup_ui() applies the button styling.
	for button in [main_menu.new_game_button, main_menu.quit_button]:
		assert_true(
			button.has_theme_stylebox_override("hover"),
			"%s should have a hover style" % button.name
		)
		assert_true(
			button.has_theme_stylebox_override("normal"),
			"%s should have a normal style" % button.name
		)


func test_keyboard_navigation():
	var new_game_btn = main_menu.new_game_button
	new_game_btn.grab_focus()
	await get_tree().process_frame

	assert_true(new_game_btn.has_focus(), "Button should have focus")

	# Simulate Enter key press
	var enter_event = InputEventKey.new()
	enter_event.keycode = KEY_ENTER
	enter_event.pressed = true
	new_game_btn._gui_input(enter_event)


func test_responsive_layout():
	# Test that the menu adjusts to different window sizes
	var original_size = DisplayServer.window_get_size()

	DisplayServer.window_set_size(Vector2i(800, 600))
	await get_tree().process_frame

	var new_game_btn = main_menu.new_game_button
	assert_true(new_game_btn.visible, "Buttons should remain visible at smaller size")

	DisplayServer.window_set_size(Vector2i(1920, 1080))
	await get_tree().process_frame

	assert_true(new_game_btn.visible, "Buttons should remain visible at larger size")

	DisplayServer.window_set_size(original_size)
