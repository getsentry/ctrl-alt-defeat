extends Control

const APITypes = preload("res://scripts/api_types.gd")
const Presentation = preload("res://scripts/presentation.gd")

@onready var new_game_button = $"MenuPanel_ButtonContainer#NewGameButton"
@onready var continue_button = $"MenuPanel_ButtonContainer#ContinueButton"
@onready var quit_button = $"MenuPanel_ButtonContainer#QuitButton"
@onready var skin_button = $"MenuPanel_ButtonContainer#SkinButton"
@onready var music_player = $BackgroundMusic
@onready var name_input = $NameInputContainer/NameInput

func _ready():
	# The window is free to be any size. Every screen is laid out in one
	# 1680 by 1050 space, and the canvas_items stretch mode scales that space
	# to whatever the window is, so nothing here has to know the real size.
	_setup_ui()

	# Load saved player name if it exists
	_load_saved_name()

	# Only the player's own Sentaur wears the skin. RobotCharacter is the
	# opponent and always stays the default one (GDD 11).
	_wear_skin()

	# Start playing background music
	if music_player and not music_player.playing:
		music_player.play()

func _setup_ui():
	# Every button is the same keycap, lit magenta under the pointer. The
	# magenta key is the other half of the logo, so it reads as the same
	# keyboard rather than as a second style.
	for button in [new_game_button, continue_button, skin_button, quit_button]:
		Keycap.dress(button)

	_dress_name_field()

	new_game_button.pressed.connect(_on_start_game)
	skin_button.pressed.connect(_open_skin_picker)
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


func _on_start_game():
	print("Starting new game...")

	_fade_the_music()

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
	var session_response = await BattleServerAPI.start_session()

	# Check if server connection failed
	if session_response == null:
		push_error("Failed to start game session - server connection failed")
		_show_error_message("Cannot connect to server. Please check your connection and try again.")
		return

	GameStateManager.update_from_session(session_response.session)
	# Go to shop/inventory screen
	get_tree().change_scene_to_file("res://scenes/UnifiedGridUI.tscn")

## How long the music takes to go once the game has been started. Short: it is
## covering the moment between the key going down and the next screen arriving,
## and the menu is gone the instant the server answers.
const MUSIC_FADE := 0.3


func _fade_the_music() -> void:
	"""Start the music fading, and carry straight on.

	Waiting for it was a second of a menu that had plainly already been left --
	the key pressed, nothing happening, then the screen finally changing. The
	fade runs while the session is being asked for, and whatever is left of it
	goes when this screen does.
	"""
	if not music_player:
		return
	if not Presentation.request("music_fade_out"):
		music_player.stop()
		return

	var tween = create_tween()
	tween.tween_property(music_player, "volume_db", -80.0, MUSIC_FADE)


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
	# Load before setting: the skin lives in this same file, and saving a
	# fresh ConfigFile would take it with the old name.
	var config = ConfigFile.new()
	config.load("user://player_settings.cfg")
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


# ---------------------------------------------------------------- skins

func _wear_skin() -> void:
	Skins.wear(get_node_or_null("PlayerCharacter"), "shop")


func _open_skin_picker() -> void:
	"""The picker belongs here rather than in the shop.

	The shop screen is full -- a rack, a store, a sell bay, a stats plate and
	the character -- and every empty-looking corner of it turned out to have
	something in it. Here there is already a column of keys, and choosing who
	you are sits naturally beside starting a game as them.
	"""
	var picker: Control = (load("res://scripts/skin_picker.gd") as GDScript).new()
	picker.picked.connect(func(_id: String) -> void: _wear_skin())
	add_child(picker)
