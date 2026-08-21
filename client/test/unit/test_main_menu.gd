extends GutTest
# Tests for MainMenu UI
#
# Node lookups go through the script's own references (main_menu.new_game_button
# and so on) rather than find_child() with a literal name, because the scene
# names nodes with a "Parent_Child#Name" convention. A scene rename then breaks
# MainMenu.gd and these tests together.
#
# The menu has two buttons: New Game and Quit.

const Presentation = preload("res://scripts/presentation.gd")

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
	# The menu is three keys. Carrying on from where you left off is not built,
	# so the key is there and dead rather than missing: the shape of the menu
	# is the shape of the game.
	assert_not_null(main_menu.continue_button, "There should be a Continue button")
	assert_true(main_menu.continue_button.disabled,
		"and it should be dead until save and resume exist")


func test_settings_button_exists_but_disabled():
	pending("No Settings button exists. Settings are not implemented.")


func test_new_game_button_enabled():
	assert_false(main_menu.new_game_button.disabled, "New Game button should be enabled")


func test_new_game_button_click():
	# Set junk values first, so passing cannot be an accident of fresh state.
	GameStateManager.current_round = 7
	GameStateManager.gold = 999
	GameStateManager.player_lives = 2
	Presentation.clear_requests()

	main_menu.new_game_button.pressed.emit()
	await get_tree().process_frame

	assert_eq(GameStateManager.current_round, 1, "Should reset to round 1")
	assert_eq(GameStateManager.gold, 12, "Should have starting gold")
	assert_eq(GameStateManager.player_lives, 5, "Should have full lives")


func test_new_game_asks_to_fade_the_music():
	# Asked for and left to run. It used to be waited on -- a full second of a
	# menu that had plainly already been left, the key pressed and nothing
	# happening -- and the screen it was fading out of is gone the moment the
	# server answers anyway.
	Presentation.clear_requests()

	main_menu._fade_the_music()

	assert_eq(Presentation.request_count("music_fade_out"), 1,
		"Starting a game should fade the menu music")
	assert_lt(main_menu.MUSIC_FADE, 0.5,
		"and it should be most of the way gone before the next screen arrives")


func test_quit_button_functionality():
	# Do NOT emit pressed. The handler is _on_exit(), which calls
	# get_tree().quit() and would end the whole test run.
	assert_true(
		main_menu.quit_button.pressed.is_connected(main_menu._on_exit),
		"Quit button should be connected to _on_exit"
	)


func test_the_menu_says_nothing_about_a_version():
	"""It read "v0.1.0 - Alpha" in the corner. A version number is for
	somebody filing a bug, and there is nobody to file one to."""
	assert_null(main_menu.get_node_or_null("VersionLabel"),
		"Nothing on the menu should be about the build")


func test_title_displayed():
	# The game name is artwork, not a text label, so the check is on the art.
	var logo = main_menu.find_child("LogoContainer", true, false)
	assert_not_null(logo, "Title should be displayed")
	assert_not_null(logo.texture, "Title artwork should have a texture")
	assert_true(logo.visible, "Title artwork should be visible")
	assert_gt(logo.texture.get_width(), 0, "Title artwork should have loaded")
	assert_true("logo" in logo.texture.resource_path,
		"Title artwork should be the logo asset, got: " + logo.texture.resource_path)


func test_the_buttons_are_cut_from_the_keycap_artwork():
	# The logo is a broken keyboard, so the menu is the keys that still work.
	for button in [main_menu.new_game_button, main_menu.continue_button,
			main_menu.skin_button, main_menu.quit_button]:
		var normal = button.get_theme_stylebox("normal")
		assert_true(normal is StyleBoxTexture,
			"%s should be drawn from artwork, not a flat slab" % button.name)
		assert_true("menu_button" in normal.texture.resource_path,
			"%s should wear the keycap, got: %s"
			% [button.name, normal.texture.resource_path])


func test_a_button_lights_up_under_the_pointer():
	# The magenta key is the other half of the logo, so a lit key reads as the
	# same keyboard rather than as a second style.
	var lit = main_menu.new_game_button.get_theme_stylebox("hover")
	assert_true("magenta" in lit.texture.resource_path,
		"A key under the pointer should light magenta, got: %s"
		% lit.texture.resource_path)


func test_the_menu_shows_the_sentaur():
	# Whichever one the player chose. This used to look for "sentaur" in the
	# path and broke the day skins arrived, because a skin is a different file
	# with a different name (GDD 11).
	var who = main_menu.find_child("PlayerCharacter", true, false)
	assert_not_null(who, "The menu should show a character")
	var theirs: Array = []
	for skin in Skins.ALL:
		theirs.append(skin["shop"])
	assert_has(theirs, who.texture.resource_path,
		"and it should be one of the Sentaurs, got: %s" % who.texture.resource_path)


func test_the_menu_shows_the_chosen_sentaur():
	# The point of the picker: what you chose is what greets you.
	var existed := FileAccess.file_exists(Skins.SETTINGS)
	var kept := FileAccess.get_file_as_string(Skins.SETTINGS) if existed else ""

	Skins.choose("neko")
	var menu = main_menu_scene.instantiate()
	add_child_autofree(menu)
	await get_tree().process_frame
	var who = menu.find_child("PlayerCharacter", true, false)
	assert_eq(who.texture.resource_path, Skins.by_id("neko")["shop"])

	if existed:
		var file := FileAccess.open(Skins.SETTINGS, FileAccess.WRITE)
		file.store_string(kept)
		file.close()
	elif FileAccess.file_exists(Skins.SETTINGS):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(Skins.SETTINGS))


func test_the_sentaur_stands_on_a_shadow():
	# Without one it is a cut-out laid over the rooftop rather than standing on
	# it.
	var shadow = main_menu.find_child("CharacterShadow", true, false)
	var who = main_menu.find_child("PlayerCharacter", true, false)
	assert_not_null(shadow, "There should be a shadow under the character")
	assert_lt(shadow.get_index(), who.get_index(),
		"and it should be drawn before the character, or it lies on top of it")

	var feet = shadow.stands_on(who).end.y
	assert_almost_eq(shadow.get_rect().get_center().y, feet, 1.0,
		"It should lie across the feet")


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

	# Press it the way the focus ring says it would be pressed. Button has no
	# _gui_input of its own to call -- calling one was an error printed on
	# every run -- and its own handler is what turns the key into this.
	new_game_btn.pressed.emit()


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


func test_the_menu_offers_to_change_the_sentaur():
	# The picker lives here rather than in the shop: that screen is full, and
	# every empty-looking corner of it turned out to have something in it.
	assert_not_null(main_menu.skin_button, "There should be a key for the skins")
	assert_false(main_menu.skin_button.disabled)
	assert_true(
		main_menu.skin_button.pressed.is_connected(main_menu._open_skin_picker),
		"and it should open the picker")


func test_the_picker_opens_over_the_menu():
	main_menu.skin_button.pressed.emit()
	await get_tree().process_frame
	var opened := false
	for child in main_menu.get_children():
		if child is Control and child.get_script() != null \
				and child.get_script().resource_path.ends_with("skin_picker.gd"):
			opened = true
	assert_true(opened, "Pressing the key should put a picker on the screen")
