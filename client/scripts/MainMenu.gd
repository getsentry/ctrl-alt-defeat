extends Control

const APITypes = preload("res://scripts/api_types.gd")

func _ready():
	# Set window size for consistency
	if not OS.has_feature("headless"):  # Only set window size if we have a display
		DisplayServer.window_set_size(Vector2i(2560, 1600))  # Match background image size
		get_window().min_size = Vector2i(2560, 1600)  # Prevent resizing smaller
		get_window().max_size = Vector2i(2560, 1600)  # Prevent resizing larger for fixed size
#		DisplayServer.window_set_position(DisplayServer.window_get_position() - Vector2i(268, 100))
	_setup_ui()

func _setup_ui():
	# Dark background
	var bg = ColorRect.new()
	bg.color = Color(0.02, 0.02, 0.03, 1.0)
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(bg)

	# Center container
	var center_container = VBoxContainer.new()
	center_container.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	center_container.position = Vector2(-200, -200)
	center_container.add_theme_constant_override("separation", 20)
	add_child(center_container)

	# Title
	var title = Label.new()
	title.name = "TitleLabel"
	title.text = "SENTRY AUTOBATTLER"
	title.add_theme_font_size_override("font_size", 48)
	title.add_theme_color_override("font_color", Color(0.3, 0.8, 1.0))
	center_container.add_child(title)

	# Subtitle
	var subtitle = Label.new()
	subtitle.text = "Server Room Battles"
	subtitle.add_theme_font_size_override("font_size", 20)
	subtitle.add_theme_color_override("font_color", Color(0.6, 0.6, 0.7))
	center_container.add_child(subtitle)

	# Spacer
	var spacer = Control.new()
	spacer.custom_minimum_size = Vector2(0, 50)
	center_container.add_child(spacer)

	# Buttons container
	var button_container = VBoxContainer.new()
	button_container.add_theme_constant_override("separation", 10)
	center_container.add_child(button_container)

	# Start Game button
	var start_btn = Button.new()
	start_btn.name = "NewGameButton"
	start_btn.text = "START NEW GAME"
	start_btn.custom_minimum_size = Vector2(400, 60)
	start_btn.add_theme_font_size_override("font_size", 24)
	start_btn.pressed.connect(_on_start_game)
	button_container.add_child(start_btn)

	# Continue button (disabled if no save)
	var continue_btn = Button.new()
	continue_btn.name = "ContinueButton"
	continue_btn.text = "CONTINUE"
	continue_btn.custom_minimum_size = Vector2(400, 60)
	continue_btn.add_theme_font_size_override("font_size", 24)
	continue_btn.disabled = true  # TODO: Check for saved game
	button_container.add_child(continue_btn)

	# Settings button
	var settings_btn = Button.new()
	settings_btn.name = "SettingsButton"
	settings_btn.text = "SETTINGS"
	settings_btn.custom_minimum_size = Vector2(400, 60)
	settings_btn.add_theme_font_size_override("font_size", 24)
	settings_btn.pressed.connect(_on_settings)
	button_container.add_child(settings_btn)

	# Exit button
	var exit_btn = Button.new()
	exit_btn.name = "QuitButton"
	exit_btn.text = "EXIT"
	exit_btn.custom_minimum_size = Vector2(400, 60)
	exit_btn.add_theme_font_size_override("font_size", 24)
	exit_btn.pressed.connect(_on_exit)
	button_container.add_child(exit_btn)

	# Version label
	var version_label = Label.new()
	version_label.name = "VersionLabel"
	version_label.text = "v0.1.0 - Alpha"
	version_label.add_theme_font_size_override("font_size", 14)
	version_label.add_theme_color_override("font_color", Color(0.4, 0.4, 0.5))
	version_label.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_RIGHT)
	version_label.position = Vector2(-120, -30)
	add_child(version_label)

func _on_start_game():
	print("Starting new game...")

	# Reset game state
	GameStateManager.start_new_game()

	# Start new session with server
	var session_response = await BattleServerAPI.start_session()

	# Check if server connection failed
	if session_response == null:
		push_error("Failed to start game session - server connection failed")
		_show_error_message("Cannot connect to server. Please check your connection and try again.")
		return

	GameStateManager.update_from_session(session_response.session)
	# Go to shop/inventory screen
	get_tree().change_scene_to_file("res://scenes/UnifiedGridUI.tscn")

func _on_settings():
	print("Settings not implemented yet")
	# TODO: Create settings menu

func _on_exit():
	get_tree().quit()

func _show_error_message(message: String):
	# Create error dialog
	var error_dialog = AcceptDialog.new()
	error_dialog.dialog_text = message
	error_dialog.title = "Connection Error"
	get_tree().root.add_child(error_dialog)
	error_dialog.popup_centered()
	error_dialog.connect("confirmed", func(): error_dialog.queue_free())
