extends Control

# Preload the BattleEventProcessor class since class_name might not be available yet
const BattleEventProcessor = preload("res://scripts/battle_event_processor.gd")
const APITypes = preload("res://scripts/api_types.gd")
const Presentation = preload("res://scripts/presentation.gd")
const ROUND_RESULT_OVERLAY = preload("res://scenes/RoundResultOverlay.tscn")
const BattleHud = preload("res://scripts/battle_hud.gd")

# Event processor for battle replay
var event_processor

# Battle state
var player_data: Dictionary = {}
var enemy_data: Dictionary = {}
var current_time: float = 0.0
var battle_active: bool = false
var max_battle_duration: float = 20.0  # 20 second battles max
var battle_speed_multiplier: float = _starting_playback_speed()


const TEST_PLAYBACK_SPEED := 50.0


static func _starting_playback_speed() -> float:
	"""Playback speed for the battle timeline.

	The server returns the whole battle at once. This is how fast the client
	replays it, so at 1x a 15 second battle takes 15 seconds of real time.

	Headless means a test run, where watching the battle has no value, so it
	plays at TEST_PLAYBACK_SPEED. Set BATTLE_PLAYBACK_SPEED to override either
	default, for instance to slow a failing test down and watch it.
	"""
	var override := OS.get_environment("BATTLE_PLAYBACK_SPEED")
	if override != "" and override.is_valid_float():
		return maxf(float(override), 0.1)
	if DisplayServer.get_name() == "headless":
		return TEST_PLAYBACK_SPEED
	return 1.0

# UI References
var player_inventory: Control
var enemy_inventory: Control
var player_stats_panel: Panel
var enemy_stats_panel: Panel
var battle_log_container: RichTextLabel
var time_label: Label

# Stats labels
var player_health_bar: ProgressBar
var player_stamina_bar: ProgressBar
var player_health_label: Label
var player_stamina_label: Label

var enemy_health_bar: ProgressBar
var enemy_stamina_bar: ProgressBar
var enemy_health_label: Label
var enemy_stamina_label: Label

# The run scoreboard shown once the battle is over. Null until then.
var round_result: Control = null

# Everything about how the screen looks, kept out of the way of the battle.
var hud

# Held rather than looked up. The HUD moves these out of the scene tree paths
# they were declared at, so a stale $ControlButtons/SpeedButton, or
# $Player2Container/Player2NameLabel, is null.
var speed_button: Button
var player_name_label: Label
var opponent_name_label: Label

# Battle effects

func _ready():
	print("BattleScreen starting...")

	# Create event processor
	event_processor = BattleEventProcessor.new()
	add_child(event_processor)
	_connect_event_signals()

	_setup_ui_references()

	# Wait for child nodes to be ready
	await get_tree().process_frame
	if not is_inside_tree():
		return

	# Load battle data from GameStateManager
	if GameStateManager.last_battle_events.size() > 0:
		_load_battle_from_state()
	else:
		push_error("No battle events to play - this is a bug!")
		assert(false, "Battle started with no events - server did not return battle actions")

	# Start battle playback automatically
	await get_tree().create_timer(Presentation.delay(0.5)).timeout
	# Leaving the screen during that wait frees this node while the coroutine is
	# still suspended. Resuming on a freed node crashes the engine.
	if not is_inside_tree():
		return
	_start_battle_playback()

func _setup_ui_references():
	# Get references to the nodes from the scene
	time_label = $TopBar/TimeLabel

	# Player stats references
	player_health_bar = $Player1Container/StatusPanel/HealthBar
	player_health_label = $Player1Container/StatusPanel/HealthValue
	player_stamina_bar = $Player1Container/StatusPanel/StaminaBar
	player_stamina_label = $Player1Container/StatusPanel/StaminaValue

	# Enemy stats references
	enemy_health_bar = $Player2Container/StatusPanel/HealthBar
	enemy_health_label = $Player2Container/StatusPanel/HealthValue
	enemy_stamina_bar = $Player2Container/StatusPanel/StaminaBar
	enemy_stamina_label = $Player2Container/StatusPanel/StaminaValue

	# Battle log - correct path
	battle_log_container = $BattleLog/LogScroll/LogText

	# Name labels
	player_name_label = $Player1Container/Player1NameLabel
	opponent_name_label = $Player2Container/Player2NameLabel

	# Set player name from GameStateManager
	player_name_label.text = GameStateManager.player_name if GameStateManager.player_name != "" else "Player"

	speed_button = $ControlButtons/SpeedButton
	speed_button.pressed.connect(_on_toggle_speed)
	# The scene hardcodes a label that has nothing to do with the speed the
	# battle actually starts at.
	speed_button.text = "%.0fx" % battle_speed_multiplier

	# Load inventories into the grid containers
	_setup_inventories()

	# The scene puts the clock over the floor, the speed button off the top of
	# the window and the log across the middle. Hand them all over.
	hud = BattleHud.new(self)
	hud.build($TopBar/TimeLabel, speed_button, $BattleLog, {
		"player_health": player_health_bar,
		"enemy_health": enemy_health_bar,
		"player_stamina": player_stamina_bar,
		"enemy_stamina": enemy_stamina_bar,
		"player_health_value": player_health_label,
		"enemy_health_value": enemy_health_label,
		"player_stamina_value": player_stamina_label,
		"enemy_stamina_value": enemy_stamina_label,
		"player_name": player_name_label,
		"enemy_name": opponent_name_label,
	}, {"player": player_inventory, "enemy": enemy_inventory}, {
		"player": $Player1Container/CharacterDisplay,
		"enemy": $Player2Container/CharacterDisplay,
		"player_art": $Player1Container/StatusPanel/TextureRect,
		"enemy_art": $Player2Container/StatusPanel/TextureRect,
	})
	hud.pause_button.pressed.connect(_on_toggle_pause)

func _setup_inventories():
	# Constants for grid configuration
	const GRID_WIDTH = 9
	const GRID_HEIGHT = 7
	const CELL_SPACING = 1
	# Fixed, not fitted to the panel it sits in. A cell sized to fill whatever
	# space was left over came out at 48 pixels, and an item drawn that small
	# is a smudge - and the racks are what the battle is decided by, so they
	# are what there has to be room for.
	const CELL_SIZE = 60

	# Create inventory grids using InventoryGrid class (not scene)
	# Player inventory - standard 9x7 grid like UnifiedGridUI
	var player_panel = $Player1Inventory
	player_inventory = InventoryGrid.new()

	# Calculate cell size based on panel size
	player_inventory.position = Vector2.ZERO

	# Only the racks and what is in them. Nothing can be placed during a
	# battle, so the empty squares behind them are guides to nothing.
	player_inventory.show_base_grid = false
	player_inventory.configure(GRID_WIDTH, GRID_HEIGHT, CELL_SIZE, CELL_SPACING)
	player_inventory.read_only = true
	player_inventory.title = "Player Inventory"
	player_inventory.set_colors(
		Color(0.1, 0.1, 0.15, 0.8),  # grid color
		Color(0.3, 0.6, 1.0, 0.15),  # border color, faint: the HUD frames it
		Color(0.2, 0.5, 1.0, 1.0)    # item color - full opacity
	)
	player_panel.add_child(player_inventory)

	# Enemy inventory - standard 9x7 grid like UnifiedGridUI
	var enemy_panel = $Player2Inventory
	enemy_inventory = InventoryGrid.new()

	enemy_inventory.position = Vector2.ZERO
	enemy_inventory.show_base_grid = false
	enemy_inventory.configure(GRID_WIDTH, GRID_HEIGHT, CELL_SIZE, CELL_SPACING)
	enemy_inventory.read_only = true
	enemy_inventory.title = "Enemy Inventory"
	enemy_inventory.set_colors(
		Color(0.15, 0.1, 0.1, 0.8),  # grid color
		Color(1.0, 0.3, 0.3, 0.15),  # border color, faint: the HUD frames it
		Color(1.0, 0.3, 0.3, 1.0)    # item color - full opacity
	)
	enemy_panel.add_child(enemy_inventory)

func _on_toggle_speed():
	# Toggle between different playback speeds
	if battle_speed_multiplier == 1.0:
		battle_speed_multiplier = 2.0
	elif battle_speed_multiplier == 2.0:
		battle_speed_multiplier = 3.0
	else:
		battle_speed_multiplier = 1.0

	# Update button text
	speed_button.text = "%.0fx" % battle_speed_multiplier

	# Whether or not it is playing: a speed set while the battle is held should
	# be the speed it runs at when it is let go.
	if is_instance_valid(event_processor):
		event_processor.set_playback_speed(battle_speed_multiplier)


func _on_toggle_pause():
	"""Hold the battle where it is, or let it run on."""
	if not is_instance_valid(event_processor):
		return
	event_processor.set_paused(not event_processor.paused)
	hud.show_paused(event_processor.paused)

func _update_stats_display():
	# Update player stats
	player_health_bar.max_value = player_data.max_health
	player_health_bar.value = player_data.health
	player_health_label.text = "%d/%d" % [player_data.health, player_data.max_health]

	hud.health_changed(player_health_bar)

	player_stamina_bar.max_value = player_data.max_stamina
	player_stamina_bar.value = player_data.stamina
	player_stamina_label.text = "%.0f/%.0f" % [player_data.stamina, player_data.max_stamina]

	# Update enemy stats
	enemy_health_bar.max_value = enemy_data.max_health
	enemy_health_bar.value = enemy_data.health
	enemy_health_label.text = "%d/%d" % [enemy_data.health, enemy_data.max_health]

	hud.health_changed(enemy_health_bar)

	enemy_stamina_bar.max_value = enemy_data.max_stamina
	enemy_stamina_bar.value = enemy_data.stamina
	enemy_stamina_label.text = "%.0f/%.0f" % [enemy_data.stamina, enemy_data.max_stamina]



func _connect_event_signals():
	# Connect all event processor signals
	event_processor.battle_started.connect(_on_battle_started)
	event_processor.damage_dealt.connect(_on_damage_dealt)
	event_processor.healing_done.connect(_on_healing_done)
	event_processor.block_activated.connect(_on_block_activated)
	event_processor.buff_applied.connect(_on_buff_applied)
	event_processor.debuff_applied.connect(_on_debuff_applied)
	event_processor.item_activated.connect(_on_item_activated)
	event_processor.player_died.connect(_on_player_died)
	event_processor.battle_ended.connect(_on_battle_ended)
	event_processor.log_message.connect(_on_log_message)

func _load_battle_from_state():
	# Load battle data from GameStateManager - always typed BattleResult
	var battle_result: APITypes.BattleResult = GameStateManager.last_battle_result

	# Load battle events
	event_processor.load_battle_events(battle_result)

	# Load inventories - these are guaranteed to exist in BattleResult
	print("Loading player inventory with %d items and %d containers" % [
		battle_result.player_inventory.items.size(),
		battle_result.player_inventory.containers.size()
	])
	player_inventory.load_inventory_state(battle_result.player_inventory)

	print("Loading enemy inventory with %d items and %d containers" % [
		battle_result.enemy_inventory.items.size(),
		battle_result.enemy_inventory.containers.size()
	])
	enemy_inventory.load_inventory_state(battle_result.enemy_inventory)

	# Set opponent name and style based on type
	opponent_name_label.text = battle_result.opponent_name

	# Different color for ghost players vs AI
	if battle_result.opponent_type == "player_ghost":
		opponent_name_label.add_theme_color_override("font_color", Color(0.8, 0.5, 1.0))  # Purple for ghost players
	else:
		opponent_name_label.add_theme_color_override("font_color", Color(1.0, 0.3, 0.3))  # Red for AI

func _start_battle_playback():
	print("Starting battle playback...")
	battle_active = true
	current_time = 0.0

	# Clear battle log
	battle_log_container.clear()

	# Initialize player stats
	var quota = GameStateManager.get_round_quota()
	player_data = {
		"health": quota,
		"max_health": quota,
		"stamina": 10.0,
		"max_stamina": 10.0,
		"buffs": []
	}

	enemy_data = {
		"health": quota,
		"max_health": quota,
		"stamina": 10.0,
		"max_stamina": 10.0,
		"buffs": []
	}

	_update_stats_display()

	# Start event playback with configurable speed
	event_processor.start_playback(battle_speed_multiplier)

func _process(delta):
	if battle_active and event_processor.is_playing:
		current_time = event_processor.get_current_time()
		time_label.text = "%.1f / %.0fs" % [current_time, max_battle_duration]
		hud.tick(current_time, max_battle_duration)

		_update_stats_display()

var _effect_tweens: Array[Tween] = []


func _effect_tween() -> Tween:
	"""A tween for a cosmetic effect, tracked so _exit_tree() can kill it."""
	var tween = create_tween()
	_effect_tweens = _effect_tweens.filter(func(t): return is_instance_valid(t) and t.is_running())
	_effect_tweens.append(tween)
	return tween


func _exit_tree():
	"""Stop everything that would otherwise resume against a freed node.

	Battle playback, the effect tweens and their queue_free callbacks all
	outlive this node otherwise, and leaving the screen mid-battle then takes
	the engine down.
	"""
	battle_active = false

	for tween in _effect_tweens:
		if is_instance_valid(tween):
			tween.kill()
	_effect_tweens.clear()

	if is_instance_valid(event_processor):
		event_processor.stop_playback()
		event_processor.set_process(false)


func _show_attack_animation(from_player: bool):
	if not Presentation.request("attack_animation", {"from_player": from_player}):
		return
	# A bolt crossing from whoever swung to whoever is about to be hit.
	var effect = ColorRect.new()
	effect.size = Vector2(26, 4)
	effect.color = Color(0.6, 0.95, 1.0) if from_player else Color(1.0, 0.45, 0.5)
	effect.z_index = 55

	var from: Vector2 = hud.fighter_at(1 if from_player else 2)
	var to: Vector2 = hud.fighter_at(2 if from_player else 1)
	effect.position = from
	add_child(effect)

	var tween = _effect_tween()
	tween.tween_property(effect, "position", to, 0.22) \
		.set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	tween.parallel().tween_property(effect, "scale", Vector2(3.0, 1.0), 0.22)
	tween.tween_property(effect, "modulate:a", 0.0, 0.12)
	tween.tween_callback(effect.queue_free)

func _on_log_message(message: String, color: Color):
	# Add colored message to battle log
	battle_log_container.push_color(color)
	battle_log_container.append_text(message + "\n")
	battle_log_container.pop()

	# Auto-scroll to bottom
	battle_log_container.scroll_to_line(battle_log_container.get_line_count() - 1)

# Event handler functions for battle events
func _on_battle_started():
	# Log is handled by BattleEventProcessor
	pass

func _on_damage_dealt(player: int, amount: int, remaining_hp: int, source: String):
	# Player parameter indicates who TAKES damage
	if player == 1:
		player_data.health = remaining_hp
	else:
		enemy_data.health = remaining_hp

	_show_damage_number(player, amount)
	_update_stats_display()

func _on_healing_done(player: int, amount: int, remaining_hp: int):
	if player == 1:
		player_data.health = remaining_hp
	else:
		enemy_data.health = remaining_hp

	_show_heal_effect(player, amount)
	_update_stats_display()

func _on_block_activated(player: int, amount: int):
	# Log is handled by BattleEventProcessor
	_show_block_effect(player)

func _on_buff_applied(player: int, buff_name: String):
	hud.add_effect(player, buff_name, true)

func _on_debuff_applied(player: int, debuff_name: String):
	hud.add_effect(player, debuff_name, false)

func _on_item_activated(item_id: String, player: int, action: String):
	# Log is handled by BattleEventProcessor
	# Show item activation visual
	_show_item_activation(item_id, player, action)

func _on_player_died(player: int):
	# Log is handled by BattleEventProcessor
	pass

func _on_battle_ended(winner: int):
	battle_active = false
	# Log is handled by BattleEventProcessor

	# Let the last blow land before the result covers it.
	await get_tree().create_timer(Presentation.delay(1.0)).timeout
	# Leaving the screen during that wait frees this node while the coroutine is
	# still suspended. Building the overlay on a freed node crashes the engine.
	if not is_inside_tree():
		return
	_show_round_result(winner == 1)


func _show_round_result(won: bool):
	"""Drop the run scoreboard over the finished battle.

	The overlay reports the run rather than the round, and the server has
	already applied this round to GameStateManager, so it is given the totals
	from after it and works the animation out from there.
	"""
	round_result = ROUND_RESULT_OVERLAY.instantiate()
	add_child(round_result)
	round_result.continued.connect(_go_to_round_over)
	round_result.show_result(won, GameStateManager.wins, GameStateManager.player_lives,
		GameStateManager.last_gold_earned)

func _show_damage_number(player: int, amount: int):
	if not Presentation.request("damage_number", {"player": player, "amount": amount}):
		return
	_throw_number(player, "-%d" % amount, Color(1.0, 0.86, 0.86), 44)

func _show_heal_effect(player: int, amount: int):
	if not Presentation.request("heal_effect", {"player": player, "amount": amount}):
		return
	_throw_number(player, "+%d" % amount, Color(0.45, 1.0, 0.6), 40)


func _throw_number(player: int, text: String, tint: Color, size: int):
	"""Throw a number off the fighter it happened to.

	It lands, holds for a beat and drifts up as it fades, so a hit reads even
	when several land close together.
	"""
	var label = hud.combat_number(player, text, tint, size)
	label.scale = Vector2(0.4, 0.4)

	var tween = _effect_tween()
	tween.tween_property(label, "scale", Vector2.ONE, 0.14) \
		.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tween.parallel().tween_property(label, "position:y", label.position.y - 78.0, 1.1) \
		.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	tween.parallel().tween_property(label, "modulate:a", 0.0, 1.1) \
		.set_delay(0.35)
	tween.chain().tween_callback(label.queue_free)

func _show_block_effect(player: int):
	if not Presentation.request("block_effect", {"player": player}):
		return
	_throw_number(player, "BLOCK", Color(0.5, 0.85, 1.0), 32)

## What an item does that counts as swinging at someone. A buff or a heal is an
## item doing its job too, but it is not a blow, and giving everything the same
## knock would turn a busy build into one long rattle.
const ATTACKS := ["damage", "critical_hit", "miss"]


func _show_item_activation(item_id: String, _player: int, action: String):
	"""Mark on screen that an item went off.

	Which rack it is in is a lookup rather than a deduction: the id is the
	item's own uid, and the player on the action is whoever it happened *to*,
	which for an attack is the other one.
	"""
	if not Presentation.request("item_activation",
			{"item": item_id, "action": action}):
		return

	for grid in [player_inventory, enemy_inventory]:
		var visual = grid.item_visual(item_id)
		if visual == null:
			continue
		visual.fire(visual.item_data.cooldown)
		if action in ATTACKS:
			hud.item_fired()
		return

func _go_to_round_over():
	"""Leave the finished battle.

	Straight to the shop. There used to be a screen in between that named the
	result, counted the gold and asked for another click, all of which the
	round result overlay now does over the battle itself - so it was a second
	screen and a second click saying what the first one had just said.
	"""
	if GameStateManager.is_game_over():
		get_tree().change_scene_to_file("res://scenes/GameOverScreen.tscn")
	else:
		get_tree().change_scene_to_file("res://scenes/UnifiedGridUI.tscn")
