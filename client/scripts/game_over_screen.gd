extends Control

## The last thing a player sees in a run: how it ended, and how it went.
##
## Built in code rather than as a scene, the way the Sentaur picker is, and out
## of the same pieces -- Slab for the panel and the lettering, Keycap for the
## buttons -- so the screen that ends a run looks like the game it ends.
##
## Whether the run was won is the server's answer, read from GameStateManager.
## Working it out again here from the round number and a health counter gave a
## second rule that could disagree with the first, and did.

const ROUNDS := 10

var _title: Label
var _subtitle: Label
var _rows := {}


func _ready() -> void:
	_build(GameStateManager.is_victory())
	_fill_in(GameStateManager.is_victory())


func _build(won: bool) -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)

	var room := TextureRect.new()
	room.texture = load("res://assets/ui/backgrounds/main_menu_background.png")
	room.set_anchors_preset(Control.PRESET_FULL_RECT)
	room.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	add_child(room)
	add_child(Slab.over_everything())

	# Centred by a container rather than by an anchor: anchoring at the centre
	# puts the panel's corner there, and the panel grows out of the screen.
	var middle := CenterContainer.new()
	middle.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(middle)

	var panel := PanelContainer.new()
	panel.name = "Panel"
	panel.custom_minimum_size = Vector2(720, 0)
	panel.add_theme_stylebox_override(
		"panel", Slab.slab(Slab.FILL, Slab.WON if won else Slab.LOST, 3))
	middle.add_child(panel)

	var margin := MarginContainer.new()
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 44)
	panel.add_child(margin)

	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 20)
	margin.add_child(column)

	_title = Slab.heading("", 72, Slab.WON if won else Slab.LOST)
	_title.name = "GameOverTitle"
	column.add_child(_title)

	_subtitle = Slab.heading("", 28, Slab.MAGENTA)
	_subtitle.name = "Subtitle"
	column.add_child(_subtitle)

	column.add_child(_rule())

	# The run, a line at a time. The name each row is given is the one the
	# stats are written into, and the one the tests read back.
	for row in [
		["FinalRoundLabel", "Rounds survived"],
		["WinsLabel", "Battles"],
		["TotalGoldLabel", "Gold earned"],
	]:
		var line := Slab.row(row[1])
		line.name = row[0] + "Row"
		column.add_child(line)
		_rows[row[0]] = line.get_node("Value")
		_rows[row[0]].name = row[0]

	column.add_child(_rule())

	# The score last and larger: it is the number a player carries away.
	var score := Slab.row("Score", 34)
	score.name = "ScoreLabelRow"
	column.add_child(score)
	_rows["ScoreLabel"] = score.get_node("Value")
	_rows["ScoreLabel"].name = "ScoreLabel"
	_rows["ScoreLabel"].add_theme_color_override("font_color", Slab.MAGENTA)

	var spacer := Control.new()
	spacer.custom_minimum_size = Vector2(0, 12)
	column.add_child(spacer)

	var buttons := HBoxContainer.new()
	buttons.add_theme_constant_override("separation", 20)
	buttons.alignment = BoxContainer.ALIGNMENT_CENTER
	column.add_child(buttons)

	buttons.add_child(_key("NEW GAME", _on_new_game))
	buttons.add_child(_key("MAIN MENU", _on_main_menu))

	# The winner stands on the roof of the same building the menu stands them
	# on, off to one side of the panel rather than in a row with it: laid out
	# beside the words, the pair is centred and neither of them is.
	if won:
		_stand_the_winner_on_the_roof()


## Where a character stands on this roof. The deck is the right-hand half of
## the picture -- everything left of the parapet is the city, a long way down
## -- so the winner stands where the main menu stands one, feet at 965 of the
## 1050 the whole game is laid out in. The panel keeps the middle.
const FEET := 965.0
const WINNER := Rect2(1250, 525, 300, 440)


func _stand_the_winner_on_the_roof() -> void:
	"""Whichever Sentaur the player picked, out on the roof beside the panel"""
	var skin := Skins.by_id(Skins.chosen())

	var art := TextureRect.new()
	art.name = "Winner"
	art.texture = load(skin["shop"])
	art.z_index = 1
	art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	art.position = WINNER.position
	art.size = WINNER.size
	add_child(art)

	# And a smudge under the feet, or they are a cut-out laid over the picture
	# rather than somebody standing on a roof. It measures the artwork itself.
	var shadow := ContactShadow.new()
	shadow.name = "WinnerShadow"
	shadow.texture = load("res://assets/ui/contact_shadow.png")
	shadow.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	shadow.stretch_mode = TextureRect.STRETCH_SCALE
	shadow.position = Vector2(WINNER.position.x + 35, FEET - 118)
	shadow.size = Vector2(WINNER.size.x + 70, 115)
	add_child(shadow)
	shadow.stands_under = shadow.get_path_to(art)


func _key(text: String, pressed: Callable) -> Button:
	"""One of the game's own keys, wide enough for two of them side by side"""
	var button := Button.new()
	button.text = text
	button.custom_minimum_size = Vector2(290, 68)
	button.size = button.custom_minimum_size
	Keycap.dress(button, 26)
	button.pressed.connect(pressed)
	return button


func _rule() -> HSeparator:
	"""A line across the panel, in the edge's own colour"""
	var line := StyleBoxLine.new()
	line.color = Slab.EDGE
	line.thickness = 1
	var rule := HSeparator.new()
	rule.add_theme_stylebox_override("separator", line)
	return rule


func _fill_in(won: bool) -> void:
	"""Say how the run ended, and what it came to"""
	# Victory or defeat, rather than "game over": a run that goes the distance
	# ends as surely as one that does not, and both of them are an ending.
	_title.text = "VICTORY" if won else "DEFEAT"
	# Congratulations, and nothing more: there is no cause being fought for
	# here, only the other player's rack.
	_subtitle.text = ("You saw off every opponent" if won
		else "Your uptime ran out")

	var round_reached: int = GameStateManager.current_round
	_rows["FinalRoundLabel"].text = "%d of %d" % [round_reached, ROUNDS]

	var wins: int = GameStateManager.wins
	var losses: int = GameStateManager.losses
	var fought := wins + losses
	var rate := 0
	if fought > 0:
		rate = int((float(wins) / fought) * 100)
	_rows["WinsLabel"].text = "%d won, %d lost (%d%%)" % [wins, losses, rate]

	# What the shop paid out over the run, near enough: the number is the
	# server's to give properly one day.
	_rows["TotalGoldLabel"].text = "%d" % (round_reached * 12)

	var score := round_reached * 100 + wins * 50
	if won:
		score += 1000
	_rows["ScoreLabel"].text = "%d" % score


func _on_new_game() -> void:
	print("Starting new game from game over...")
	GameStateManager.start_new_game()

	var session_response = await BattleServerAPI.start_session()
	if session_response == null:
		push_error("Failed to start new game session")
		_show_error_message("Failed to connect to server. Please try again.")
		return

	GameStateManager.update_from_session(session_response.session)
	get_tree().change_scene_to_file("res://scenes/UnifiedGridUI.tscn")


func _on_main_menu() -> void:
	print("Returning to main menu...")
	get_tree().change_scene_to_file("res://scenes/MainMenu.tscn")


func _show_error_message(message: String) -> void:
	var error_dialog = AcceptDialog.new()
	error_dialog.dialog_text = message
	error_dialog.title = "Connection Error"
	get_tree().root.add_child(error_dialog)
	error_dialog.popup_centered()
	error_dialog.connect("confirmed", func(): error_dialog.queue_free())
