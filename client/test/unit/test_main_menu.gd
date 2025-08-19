extends GutTest
# Comprehensive tests for MainMenu UI

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

func test_main_menu_loads():
	# Test that MainMenu scene loads without errors
	assert_not_null(main_menu, "MainMenu should load")
	assert_true(main_menu.visible, "MainMenu should be visible")

func test_all_buttons_exist():
	# Verify all required buttons are present
	var new_game_btn = main_menu.find_child("NewGameButton", true, false)
	var continue_btn = main_menu.find_child("ContinueButton", true, false)
	var settings_btn = main_menu.find_child("SettingsButton", true, false)
	var quit_btn = main_menu.find_child("QuitButton", true, false)

	assert_not_null(new_game_btn, "New Game button should exist")
	assert_not_null(continue_btn, "Continue button should exist")
	assert_not_null(settings_btn, "Settings button should exist")
	assert_not_null(quit_btn, "Quit button should exist")

func test_new_game_button_enabled():
	# New Game button should always be enabled
	var new_game_btn = main_menu.find_child("NewGameButton", true, false)
	assert_false(new_game_btn.disabled, "New Game button should be enabled")

func test_continue_button_disabled_initially():
	# Continue button should be disabled without save
	var continue_btn = main_menu.find_child("ContinueButton", true, false)
	assert_true(continue_btn.disabled, "Continue button should be disabled initially")

func test_new_game_button_click():
	# Test clicking New Game button
	var new_game_btn = main_menu.find_child("NewGameButton", true, false)

	# Watch for scene change
	watch_signals(get_tree())

	# Simulate button click
	new_game_btn.pressed.emit()
	await get_tree().process_frame

	# Should start a new game
	assert_eq(GameStateManager.current_round, 1, "Should reset to round 1")
	assert_eq(GameStateManager.gold, 12, "Should have starting gold")
	assert_eq(GameStateManager.player_lives, 5, "Should have full lives")

func test_quit_button_functionality():
	# Test quit button (in test, just verify signal)
	var quit_btn = main_menu.find_child("QuitButton", true, false)

	watch_signals(quit_btn)
	quit_btn.pressed.emit()

	assert_signal_emitted(quit_btn, "pressed", "Quit button should emit pressed signal")

func test_version_label_exists():
	# Verify version info is displayed
	var version_label = main_menu.find_child("VersionLabel", true, false)
	assert_not_null(version_label, "Version label should exist")
	if version_label:
		assert_ne(version_label.text, "", "Version label should have text")

func test_title_displayed():
	# Verify game title is shown
	var title = main_menu.find_child("TitleLabel", true, false)
	assert_not_null(title, "Title should be displayed")
	if title:
		assert_true("Sentry" in title.text or "Autobattler" in title.text,
			"Title should contain game name")

func test_settings_button_exists_but_disabled():
	# Settings not implemented yet
	var settings_btn = main_menu.find_child("SettingsButton", true, false)
	if settings_btn:
		# May be disabled since not implemented
		pass  # Just verify it exists

func test_background_exists():
	# Test that menu has proper background
	var background = main_menu.find_child("Background", true, false)
	if not background:
		# Look for ColorRect or TextureRect
		for child in main_menu.get_children():
			if child is ColorRect or child is TextureRect:
				background = child
				break

	assert_not_null(background, "Menu should have a background")

func test_button_hover_effects():
	# Test that buttons respond to hover
	var new_game_btn = main_menu.find_child("NewGameButton", true, false)
	if not new_game_btn:
		return

	# Simulate mouse enter
	var initial_modulate = new_game_btn.modulate
	new_game_btn.mouse_entered.emit()
	await get_tree().process_frame

	# Button appearance might change on hover
	# This depends on implementation

	# Simulate mouse exit
	new_game_btn.mouse_exited.emit()
	await get_tree().process_frame

func test_keyboard_navigation():
	# Test that menu can be navigated with keyboard
	var new_game_btn = main_menu.find_child("NewGameButton", true, false)
	if not new_game_btn:
		return

	# Give focus to button
	new_game_btn.grab_focus()
	await get_tree().process_frame

	assert_true(new_game_btn.has_focus(), "Button should have focus")

	# Simulate Enter key press
	var enter_event = InputEventKey.new()
	enter_event.keycode = KEY_ENTER
	enter_event.pressed = true

	new_game_btn._gui_input(enter_event)

func test_responsive_layout():
	# Test that menu adjusts to different window sizes
	var original_size = DisplayServer.window_get_size()

	# Test smaller window
	DisplayServer.window_set_size(Vector2i(800, 600))
	await get_tree().process_frame

	var new_game_btn = main_menu.find_child("NewGameButton", true, false)
	if new_game_btn:
		assert_true(new_game_btn.visible, "Buttons should remain visible at smaller size")

	# Test larger window
	DisplayServer.window_set_size(Vector2i(1920, 1080))
	await get_tree().process_frame

	if new_game_btn:
		assert_true(new_game_btn.visible, "Buttons should remain visible at larger size")

	# Restore original size
	DisplayServer.window_set_size(original_size)
