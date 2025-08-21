extends Control

const APITypes = preload("res://scripts/api_types.gd")

# Battle result display
var result_data: APITypes.BattleResult = null
var gold_earned: int = 0
var health_lost: int = 0

func _ready():
	_setup_ui()
	# Get battle result from GameStateManager
	if GameStateManager.last_battle_result:
		set_battle_result(GameStateManager.last_battle_result)
		_display_results()

# Store references to UI elements
var title_label: Label
var round_label: Label
var gold_label: Label
var health_label: Label
var current_health_label: Label
var continue_button: Button

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
	title_label = Label.new()
	title_label.name = "ResultTitle"
	title_label.add_theme_font_size_override("font_size", 64)
	main_container.add_child(title_label)

	# Stats container
	var stats_container = VBoxContainer.new()
	stats_container.add_theme_constant_override("separation", 15)
	main_container.add_child(stats_container)

	# Round label
	round_label = Label.new()
	round_label.name = "RoundLabel"
	round_label.add_theme_font_size_override("font_size", 24)
	round_label.add_theme_color_override("font_color", Color(0.8, 0.8, 0.8))
	stats_container.add_child(round_label)

	# Gold earned
	gold_label = Label.new()
	gold_label.name = "GoldLabel"
	gold_label.add_theme_font_size_override("font_size", 28)
	gold_label.add_theme_color_override("font_color", Color(1.0, 0.85, 0.0))
	stats_container.add_child(gold_label)

	# Health lost (only shown on defeat)
	health_label = Label.new()
	health_label.name = "HealthLabel"
	health_label.add_theme_font_size_override("font_size", 24)
	health_label.add_theme_color_override("font_color", Color(1.0, 0.3, 0.3))
	health_label.visible = false
	stats_container.add_child(health_label)

	# Current health
	current_health_label = Label.new()
	current_health_label.name = "CurrentHealthLabel"
	current_health_label.add_theme_font_size_override("font_size", 20)
	current_health_label.add_theme_color_override("font_color", Color(0.6, 0.6, 0.6))
	stats_container.add_child(current_health_label)

	# Spacer
	var spacer = Control.new()
	spacer.custom_minimum_size = Vector2(0, 50)
	main_container.add_child(spacer)

	# Continue button
	continue_button = Button.new()
	continue_button.name = "ContinueButton"
	continue_button.text = "CONTINUE TO SHOP"
	continue_button.custom_minimum_size = Vector2(600, 70)
	continue_button.add_theme_font_size_override("font_size", 28)
	continue_button.pressed.connect(_on_continue_pressed)
	main_container.add_child(continue_button)

func set_battle_result(data: APITypes.BattleResult):
	"""Called before scene loads to set battle data"""
	result_data = data

	# Get gold earned from GameStateManager (it was stored from session_update)
	gold_earned = GameStateManager.last_gold_earned
	# Calculate health lost based on winner
	health_lost = 1 if data.winner == 2 else 0

	# GameStateManager already has all the updated values from session_update
	# (current_round, gold, wins, losses were updated in update_after_battle)

	# Apply health loss
	if health_lost > 0:
		GameStateManager.player_health -= health_lost

func _display_results():
	"""Update UI with battle results"""
	if not result_data:
		return

	var won = result_data.winner == 1

	# Update title
	if title_label:
		if won:
			title_label.text = "VICTORY!"
			title_label.add_theme_color_override("font_color", Color(0.3, 1.0, 0.3))
		else:
			title_label.text = "DEFEAT"
			title_label.add_theme_color_override("font_color", Color(1.0, 0.3, 0.3))

	# Update round
	if round_label:
		round_label.text = "Round %d Complete" % (GameStateManager.current_round - 1)

	# Update gold
	if gold_label:
		gold_label.text = "+%d Gold" % gold_earned

	# Update health lost (only on defeat)
	if health_label and not won and health_lost > 0:
		health_label.text = "-%d Health" % health_lost
		health_label.visible = true

	# Update current health
	if current_health_label:
		current_health_label.text = "Health: %d / 100" % GameStateManager.player_health

	# Check for game over
	if GameStateManager.is_game_over() and continue_button:
		continue_button.text = "GAME OVER"
		continue_button.add_theme_color_override("font_color", Color(1.0, 0.3, 0.3))

func _on_continue_pressed():
	print("Continuing from post-battle...")

	# Check if game is over
	if GameStateManager.is_game_over():
		# Go to game over screen
		get_tree().change_scene_to_file("res://scenes/GameOverScreen.tscn")
	else:
		# Return to shop/inventory
		get_tree().change_scene_to_file("res://scenes/UnifiedGridUI.tscn")
