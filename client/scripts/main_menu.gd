extends Control

const APITypes = preload("res://scripts/api_types.gd")
const Presentation = preload("res://scripts/presentation.gd")

## The keycap a menu button is cut from, and the one it lights up as. The logo
## is a broken keyboard, so the menu is the keys that still work.
const KEYCAP := preload("res://assets/ui/menu_button.png")
const KEYCAP_LIT := preload("res://assets/ui/menu_button_magenta.png")
## How much of each end of the keycap is drawn at its own size rather than
## stretched with the rest of it.
##
## None of it, which wants saying. Slicing the ends off is what lets one
## picture of a key serve buttons of different widths, and these buttons are
## all one width -- so the only thing it does here is draw the ends at three
## times the detail of the stretched middle, which reads as two chunky blocks
## bolted to a thin key. The whole picture is squashed instead, near enough
## evenly: a menu button is about a third of the artwork either way.
##
## Give it 60 or so if the menu ever holds buttons of different widths.
const KEYCAP_END := 0.0
## How much of the bottom of a button is the lit lip, as a share of its height.
## Nothing is sliced off the top or the bottom: a menu button is drawn about a
## third of the height of the artwork, and slices of the size the lip is drawn
## at would not fit inside it. So the key is squashed whole, and this only says
## how far up the lettering has to sit to stay on the face of it.
const KEYCAP_LIP := 0.3
## The lettering. The same dark the logo's keycaps are lettered in.
const KEYCAP_INK := Color("#2d2034")

@onready var new_game_button = $"MenuPanel_ButtonContainer#NewGameButton"
@onready var continue_button = $"MenuPanel_ButtonContainer#ContinueButton"
@onready var quit_button = $"MenuPanel_ButtonContainer#QuitButton"
@onready var version_label = $VersionLabel
@onready var music_player = $BackgroundMusic
@onready var name_input = $NameInputContainer/NameInput

func _ready():
	# The window is free to be any size. Every screen is laid out in one
	# 1680 by 1050 space, and the canvas_items stretch mode scales that space
	# to whatever the window is, so nothing here has to know the real size.
	_setup_ui()

	# Load saved player name if it exists
	_load_saved_name()

	# Start playing background music
	if music_player and not music_player.playing:
		music_player.play()

func _setup_ui():
	# Every button is the same keycap, lit magenta under the pointer. The
	# magenta key is the other half of the logo, so it reads as the same
	# keyboard rather than as a second style.
	for button in [new_game_button, continue_button, quit_button]:
		var tall: float = max(button.custom_minimum_size.y, button.size.y)
		button.add_theme_stylebox_override("normal", _keycap(KEYCAP, tall))
		button.add_theme_stylebox_override("hover", _keycap(KEYCAP_LIT, tall))
		button.add_theme_stylebox_override(
			"pressed", _keycap(KEYCAP_LIT, tall, Color(0.82, 0.82, 0.82)))
		button.add_theme_stylebox_override(
			"focus", _keycap(KEYCAP_LIT, tall))
		button.add_theme_stylebox_override(
			"disabled", _keycap(KEYCAP, tall, Color(0.62, 0.6, 0.66)))

		button.add_theme_font_size_override("font_size", 30)
		button.add_theme_color_override("font_color", KEYCAP_INK)
		button.add_theme_color_override("font_hover_color", KEYCAP_INK)
		button.add_theme_color_override("font_pressed_color", KEYCAP_INK)
		button.add_theme_color_override("font_focus_color", KEYCAP_INK)
		button.add_theme_color_override("font_disabled_color", Color(0.35, 0.3, 0.38, 0.7))

	_dress_name_field()

	version_label.add_theme_font_size_override("font_size", 14)
	version_label.add_theme_color_override("font_color", Color(0.4, 0.4, 0.5, 0.8))
	new_game_button.pressed.connect(_on_start_game)
	quit_button.pressed.connect(_on_exit)


func _dress_name_field() -> void:
	"""Make the name field look like it belongs on the roof.

	A default line edit is a grey box, and a grey box over a sunset reads as
	part of the operating system rather than part of the game. It stays plain
	all the same: it is a place to type, not another key on the keyboard.
	"""
	var field := StyleBoxFlat.new()
	field.bg_color = Color(0.16, 0.11, 0.18, 0.72)
	field.border_color = Color(0.85, 0.73, 0.55, 0.45)
	field.set_border_width_all(2)
	field.set_corner_radius_all(4)
	field.content_margin_left = 16.0
	field.content_margin_right = 16.0

	var typing := field.duplicate()
	typing.border_color = Color(1.0, 0.45, 0.85, 0.8)

	name_input.add_theme_stylebox_override("normal", field)
	name_input.add_theme_stylebox_override("focus", typing)
	name_input.add_theme_color_override("font_color", Color(0.94, 0.89, 0.8))
	name_input.add_theme_color_override(
		"font_placeholder_color", Color(0.94, 0.89, 0.8, 0.45))
	name_input.add_theme_color_override("caret_color", Color(1.0, 0.45, 0.85))


func _keycap(art: Texture2D, tall: float, tint := Color.WHITE) -> StyleBoxTexture:
	"""One menu button, cut from the keycap artwork.

	Only the ends are kept at their own size. Everything between them stretches
	to whatever width the button is, which is what lets one picture of a key
	serve buttons with different words on them.
	"""
	var cap := StyleBoxTexture.new()
	cap.texture = art
	cap.texture_margin_left = KEYCAP_END
	cap.texture_margin_right = KEYCAP_END
	cap.modulate_color = tint

	# The lettering sits on the face of the key rather than in the middle of
	# the picture, because the bottom of the picture is the lip the key glows
	# through and a word across that is a word nobody can read.
	cap.content_margin_left = 24.0
	cap.content_margin_right = 24.0
	cap.content_margin_top = 0.0
	cap.content_margin_bottom = tall * KEYCAP_LIP
	return cap


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
