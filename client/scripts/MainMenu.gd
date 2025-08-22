extends Control

const APITypes = preload("res://scripts/api_types.gd")

@onready var new_game_button = $"MenuPanel_ButtonContainer#NewGameButton"
@onready var quit_button = $"MenuPanel_ButtonContainer#QuitButton"
@onready var version_label = $VersionLabel
@onready var music_player = $BackgroundMusic

func _ready():
	# Set window size for consistency
	if not OS.has_feature("headless"):  # Only set window size if we have a display
		DisplayServer.window_set_size(Vector2i(2560, 1600))  # Match background image size
		get_window().min_size = Vector2i(2560, 1600)  # Prevent resizing smaller
		get_window().max_size = Vector2i(2560, 1600)  # Prevent resizing larger for fixed size
	_setup_ui()

	# Start playing background music
	if music_player and not music_player.playing:
		music_player.play()

func _setup_ui():
	# Style the buttons
	var button_normal_style = StyleBoxFlat.new()
	button_normal_style.bg_color = Color(0.2, 0.25, 0.35, 0.9)
	button_normal_style.border_color = Color(0.3, 0.6, 1.0, 0.6)
	button_normal_style.set_border_width_all(2)
	button_normal_style.set_corner_radius_all(6)

	var button_hover_style = StyleBoxFlat.new()
	button_hover_style.bg_color = Color(0.25, 0.35, 0.5, 0.95)
	button_hover_style.border_color = Color(0.4, 0.7, 1.0, 1.0)
	button_hover_style.set_border_width_all(3)
	button_hover_style.set_corner_radius_all(6)

	var button_pressed_style = StyleBoxFlat.new()
	button_pressed_style.bg_color = Color(0.15, 0.2, 0.3, 0.95)
	button_pressed_style.border_color = Color(0.3, 0.5, 0.8, 1.0)
	button_pressed_style.set_border_width_all(2)
	button_pressed_style.set_corner_radius_all(6)

	# Apply styles to all buttons
	var buttons = [new_game_button, quit_button]
	for button in buttons:
		button.add_theme_stylebox_override("normal", button_normal_style)
		button.add_theme_stylebox_override("hover", button_hover_style)
		button.add_theme_stylebox_override("pressed", button_pressed_style)
		button.add_theme_font_size_override("font_size", 24)
		button.add_theme_color_override("font_color", Color(0.9, 0.9, 1.0))
		button.add_theme_color_override("font_hover_color", Color(1.0, 1.0, 1.0))
		button.add_theme_color_override("font_pressed_color", Color(0.8, 0.9, 1.0))
		button.add_theme_color_override("font_disabled_color", Color(0.4, 0.4, 0.5))

	version_label.add_theme_font_size_override("font_size", 14)
	version_label.add_theme_color_override("font_color", Color(0.4, 0.4, 0.5, 0.8))
	new_game_button.pressed.connect(_on_start_game)
	quit_button.pressed.connect(_on_exit)

func _on_start_game():
	print("Starting new game...")

	# Fade out music before transitioning
	if music_player and music_player.playing:
		var tween = get_tree().create_tween()
		tween.tween_property(music_player, "volume_db", -80.0, 1.0)  # Fade to silence over 1 second
		await tween.finished
		music_player.stop()

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
