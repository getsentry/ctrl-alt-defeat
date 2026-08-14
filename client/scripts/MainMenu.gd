extends Control

const APITypes = preload("res://scripts/api_types.gd")
const Presentation = preload("res://scripts/Presentation.gd")

@onready var new_game_button = $"MenuPanel_ButtonContainer#NewGameButton"
@onready var quit_button = $"MenuPanel_ButtonContainer#QuitButton"
@onready var version_label = $VersionLabel
@onready var music_player = $BackgroundMusic
@onready var name_input = $NameInputContainer/NameInput

func _ready():
	# Set window size for consistency
	if not OS.has_feature("headless"):  # Only set window size if we have a display
		DisplayServer.window_set_size(Vector2i(1680, 1050))  # Match new target resolution
		get_window().min_size = Vector2i(1680, 1050)  # Prevent resizing smaller
		get_window().max_size = Vector2i(1680, 1050)  # Prevent resizing larger for fixed size
	_setup_ui()

	# Load saved player name if it exists
	_load_saved_name()

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
		if Presentation.request("music_fade_out"):
			var tween = get_tree().create_tween()
			tween.tween_property(music_player, "volume_db", -80.0, 1.0)  # Fade to silence over 1 second
			await tween.finished
		music_player.stop()

	# Get player name from input (default to "Player" if empty)
	var player_name = name_input.text.strip_edges()
	if player_name == "":
		player_name = "Player"

	# Save the player name for next time
	_save_player_name(player_name)

	# Reset game state and set player name
	GameStateManager.start_new_game()
	GameStateManager.player_name = player_name

	# Start new session with server
	var session_response = await BattleServerAPI.start_session(player_name)

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

func _save_player_name(player_name: String):
	"""Save player name to user settings (works in browser localStorage too)"""
	var config = ConfigFile.new()
	config.set_value("player", "name", player_name)
	var save_result = config.save("user://player_settings.cfg")
	if save_result == OK:
		print("Saved player name: ", player_name)
	else:
		print("Failed to save player name")

func _load_saved_name():
	"""Load saved player name from user settings"""
	var config = ConfigFile.new()
	var load_result = config.load("user://player_settings.cfg")

	if load_result == OK:
		var saved_name = config.get_value("player", "name", "")
		if saved_name != "":
			name_input.text = saved_name
			print("Loaded saved player name: ", saved_name)
	else:
		print("No saved player name found")
