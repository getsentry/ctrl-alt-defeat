extends Control

# Battle result display
var result_data: Dictionary = {}
var gold_earned: int = 0
var health_lost: int = 0

func _ready():
	_setup_ui()
	# Get battle result from GameStateManager
	if GameStateManager.last_battle_result:
		set_battle_result(GameStateManager.last_battle_result)
		_display_results()

func _setup_ui():
	# Dark background
	var bg = ColorRect.new()
	bg.color = Color(0.02, 0.02, 0.03, 1.0)
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(bg)

	# Main container
	var main_container = VBoxContainer.new()
	main_container.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	main_container.position = Vector2(-300, -250)
	main_container.add_theme_constant_override("separation", 30)
	add_child(main_container)

	# Result title (VICTORY or DEFEAT)
	var title_label = Label.new()
	title_label.name = "ResultTitle"
	title_label.add_theme_font_size_override("font_size", 64)
	main_container.add_child(title_label)

	# Stats container
	var stats_container = VBoxContainer.new()
	stats_container.add_theme_constant_override("separation", 15)
	main_container.add_child(stats_container)

	# Round label
	var round_label = Label.new()
	round_label.name = "RoundLabel"
	round_label.add_theme_font_size_override("font_size", 24)
	round_label.add_theme_color_override("font_color", Color(0.8, 0.8, 0.8))
	stats_container.add_child(round_label)

	# Gold earned
	var gold_label = Label.new()
	gold_label.name = "GoldLabel"
	gold_label.add_theme_font_size_override("font_size", 28)
	gold_label.add_theme_color_override("font_color", Color(1.0, 0.85, 0.0))
	stats_container.add_child(gold_label)

	# Health lost (only shown on defeat)
	var health_label = Label.new()
	health_label.name = "HealthLabel"
	health_label.add_theme_font_size_override("font_size", 24)
	health_label.add_theme_color_override("font_color", Color(1.0, 0.3, 0.3))
	health_label.visible = false
	stats_container.add_child(health_label)

	# Current health
	var current_health_label = Label.new()
	current_health_label.name = "CurrentHealthLabel"
	current_health_label.add_theme_font_size_override("font_size", 20)
	current_health_label.add_theme_color_override("font_color", Color(0.6, 0.6, 0.6))
	stats_container.add_child(current_health_label)

	# Spacer
	var spacer = Control.new()
	spacer.custom_minimum_size = Vector2(0, 50)
	main_container.add_child(spacer)

	# Continue button
	var continue_btn = Button.new()
	continue_btn.name = "ContinueButton"
	continue_btn.text = "CONTINUE TO SHOP"
	continue_btn.custom_minimum_size = Vector2(600, 70)
	continue_btn.add_theme_font_size_override("font_size", 28)
	continue_btn.pressed.connect(_on_continue_pressed)
	main_container.add_child(continue_btn)

func set_battle_result(data: Dictionary):
	"""Called before scene loads to set battle data"""
	result_data = data.get("battle_result", {})
	var session_update = data.get("session_update", {})

	gold_earned = session_update.get("gold_earned", 0)
	health_lost = data.get("health_lost", 0)

	# Update GameStateManager with new values
	if session_update.has("round"):
		GameStateManager.current_round = session_update.round
	if session_update.has("gold"):
		GameStateManager.gold = session_update.gold
	if session_update.has("wins"):
		GameStateManager.wins = session_update.wins
	if session_update.has("losses"):
		GameStateManager.losses = session_update.losses

	# Apply health loss
	if health_lost > 0:
		GameStateManager.player_health -= health_lost

	# Store new shop
	if data.has("new_shop"):
		GameStateManager.current_shop = data.new_shop

func _display_results():
	"""Update UI with battle results"""
	if not result_data:
		return

	var won = result_data.get("winner", 1) == 1

	# Update title
	var title = get_node("ResultTitle")
	if title:
		if won:
			title.text = "VICTORY!"
			title.add_theme_color_override("font_color", Color(0.3, 1.0, 0.3))
		else:
			title.text = "DEFEAT"
			title.add_theme_color_override("font_color", Color(1.0, 0.3, 0.3))

	# Update round
	var round_label = get_node("RoundLabel")
	if round_label:
		round_label.text = "Round %d Complete" % (GameStateManager.current_round - 1)

	# Update gold
	var gold_label = get_node("GoldLabel")
	if gold_label:
		gold_label.text = "+%d Gold" % gold_earned

	# Update health lost (only on defeat)
	var health_label = get_node("HealthLabel")
	if health_label and not won and health_lost > 0:
		health_label.text = "-%d Health" % health_lost
		health_label.visible = true

	# Update current health
	var current_health = get_node("CurrentHealthLabel")
	if current_health:
		current_health.text = "Health: %d / 100" % GameStateManager.player_health

		# Check for game over
		if GameStateManager.is_game_over():
			var continue_btn = get_node("ContinueButton")
			if continue_btn:
				continue_btn.text = "GAME OVER"
				continue_btn.add_theme_color_override("font_color", Color(1.0, 0.3, 0.3))

func _on_continue_pressed():
	print("Continuing from post-battle...")

	# Check if game is over
	if GameStateManager.is_game_over():
		# Go to game over screen
		get_tree().change_scene_to_file("res://scenes/GameOverScreen.tscn")
	else:
		# Return to shop/inventory
		get_tree().change_scene_to_file("res://scenes/UnifiedGridUI.tscn")
