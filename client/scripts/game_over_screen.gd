extends Control

# Game over screen - shows final stats and allows restart

func _ready():
	_setup_ui()
	_display_final_stats()

func _setup_ui():
	# Dark background
	var bg = ColorRect.new()
	bg.color = Color(0.02, 0.02, 0.03, 1.0)
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(bg)

	# Main container
	var main_container = VBoxContainer.new()
	main_container.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	main_container.position = Vector2(-350, -300)
	main_container.add_theme_constant_override("separation", 25)
	add_child(main_container)

	# Game Over title
	var title = Label.new()
	title.name = "GameOverTitle"
	title.text = "GAME OVER"
	title.add_theme_font_size_override("font_size", 72)
	title.add_theme_color_override("font_color", Color(1.0, 0.3, 0.3))
	main_container.add_child(title)

	# Victory subtitle (if won)
	var subtitle = Label.new()
	subtitle.name = "VictorySubtitle"
	subtitle.text = ""
	subtitle.add_theme_font_size_override("font_size", 36)
	subtitle.add_theme_color_override("font_color", Color(1.0, 0.85, 0.0))
	subtitle.visible = false
	main_container.add_child(subtitle)

	# Spacer
	var spacer1 = Control.new()
	spacer1.custom_minimum_size = Vector2(0, 30)
	main_container.add_child(spacer1)

	# Stats container
	var stats_container = VBoxContainer.new()
	stats_container.add_theme_constant_override("separation", 15)
	main_container.add_child(stats_container)

	# Final Round
	var round_label = Label.new()
	round_label.name = "FinalRoundLabel"
	round_label.add_theme_font_size_override("font_size", 28)
	round_label.add_theme_color_override("font_color", Color(0.8, 0.8, 0.8))
	stats_container.add_child(round_label)

	# Wins/Losses
	var wins_label = Label.new()
	wins_label.name = "WinsLabel"
	wins_label.add_theme_font_size_override("font_size", 24)
	wins_label.add_theme_color_override("font_color", Color(0.7, 0.7, 0.7))
	stats_container.add_child(wins_label)

	# Total Gold Earned
	var gold_label = Label.new()
	gold_label.name = "TotalGoldLabel"
	gold_label.add_theme_font_size_override("font_size", 24)
	gold_label.add_theme_color_override("font_color", Color(1.0, 0.85, 0.0))
	stats_container.add_child(gold_label)

	# Score
	var score_label = Label.new()
	score_label.name = "ScoreLabel"
	score_label.add_theme_font_size_override("font_size", 32)
	score_label.add_theme_color_override("font_color", Color(0.3, 0.8, 1.0))
	stats_container.add_child(score_label)

	# Spacer
	var spacer2 = Control.new()
	spacer2.custom_minimum_size = Vector2(0, 50)
	main_container.add_child(spacer2)

	# Button container
	var button_container = HBoxContainer.new()
	button_container.add_theme_constant_override("separation", 20)
	main_container.add_child(button_container)

	# New Game button
	var new_game_btn = Button.new()
	new_game_btn.text = "NEW GAME"
	new_game_btn.custom_minimum_size = Vector2(250, 60)
	new_game_btn.add_theme_font_size_override("font_size", 24)
	new_game_btn.pressed.connect(_on_new_game)
	button_container.add_child(new_game_btn)

	# Main Menu button
	var menu_btn = Button.new()
	menu_btn.text = "MAIN MENU"
	menu_btn.custom_minimum_size = Vector2(250, 60)
	menu_btn.add_theme_font_size_override("font_size", 24)
	menu_btn.pressed.connect(_on_main_menu)
	button_container.add_child(menu_btn)

	# Exit button
	var exit_btn = Button.new()
	exit_btn.text = "EXIT"
	exit_btn.custom_minimum_size = Vector2(250, 60)
	exit_btn.add_theme_font_size_override("font_size", 24)
	exit_btn.pressed.connect(_on_exit)
	button_container.add_child(exit_btn)

func _display_final_stats():
	"""Display final game statistics"""

	# The server decides this and says so. Working it out again from the round
	# number and a health counter gave a second rule that could disagree with
	# the first - and did, since the run ends on tries rather than on health,
	# so that health was never anything but 100.
	var is_victory = GameStateManager.is_victory()

	# Update title for victory
	var title = find_child("GameOverTitle", true, false)
	if title and is_victory:
		title.text = "VICTORY!"
		title.add_theme_color_override("font_color", Color(0.3, 1.0, 0.3))

		var subtitle = find_child("VictorySubtitle", true, false)
		if subtitle:
			subtitle.text = "You defended the server room!"
			subtitle.visible = true

	# Display stats
	var round_label = find_child("FinalRoundLabel", true, false)
	if round_label:
		round_label.text = "Final Round: %d" % GameStateManager.current_round

	var wins_label = find_child("WinsLabel", true, false)
	if wins_label:
		var total_battles = GameStateManager.wins + GameStateManager.losses
		var win_rate = 0
		if total_battles > 0:
			win_rate = int((float(GameStateManager.wins) / total_battles) * 100)
		wins_label.text = "Battles: %d Wins / %d Losses (%d%% Win Rate)" % [
			GameStateManager.wins,
			GameStateManager.losses,
			win_rate
		]

	var gold_label = find_child("TotalGoldLabel", true, false)
	if gold_label:
		# Estimate total gold earned (rough calculation)
		var total_gold = GameStateManager.current_round * 12
		gold_label.text = "Total Gold Earned: %d" % total_gold

	var score_label = find_child("ScoreLabel", true, false)
	if score_label:
		# Calculate score: rounds * 100 + wins * 50 + bonus for victory
		var score = GameStateManager.current_round * 100 + GameStateManager.wins * 50
		if is_victory:
			score += 1000
		score_label.text = "Final Score: %d" % score

func _on_new_game():
	print("Starting new game from game over...")

	# Reset game state
	GameStateManager.start_new_game()

	# Start new session with server
	var session_response = await BattleServerAPI.start_session()

	if session_response == null:
		push_error("Failed to start new game session")
		# Show error to user
		_show_error_message("Failed to connect to server. Please try again.")
		return

	GameStateManager.update_from_session(session_response.session)

	# Go to shop
	get_tree().change_scene_to_file("res://scenes/UnifiedGridUI.tscn")

func _on_main_menu():
	print("Returning to main menu...")
	get_tree().change_scene_to_file("res://scenes/MainMenu.tscn")

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
