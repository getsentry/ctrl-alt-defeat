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

	# The racks are built and the window has settled, so the scenery has
	# something real to measure itself against.
	_place_battle_art()

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

## How much of itself a rack's frame shows around the rack.
const FRAME_MARGIN := 12.0
## How far the parapet settles past the line the roof starts on. That line is
## read off a painting rather than measured, and a wall standing exactly on it
## leaves a hair of city showing under the join. A few pixels of overlap puts
## the wall's foot into the roof and closes it for good.
const PARAPET_SETTLE := 8.0
func _place_battle_art() -> void:
	"""Put the scenery where the room and the fighters actually are.

	None of it is measured out in the scene. The parapet takes its shape from
	its own picture and its place from the roof painted in the background; the
	frames take theirs from the racks they sit behind. The numbers the scene
	carries are only so the nodes can be seen while it is being edited.
	"""
	_lay_the_parapet()
	_frame_the_rack(player_inventory, $Player1Inventory/GridFrame)
	_frame_the_rack(enemy_inventory, $Player2Inventory/GridFrame)


func _lay_the_parapet() -> void:
	"""Across the whole window, standing on the roof painted behind it.

	Not on the bottom of the window: the background already has a roof in it,
	a dark strip running from the foot of the city down to the bottom edge,
	and the wall belongs at the back of that strip rather than at the front.

	That line is as high as the wall can go. Anything higher and the strip of
	city between the foot of the buildings and the base of the wall shows
	underneath it, which reads as a wall floating in the air.
	"""
	var parapet: TextureRect = $Parapet
	var art: Vector2 = parapet.texture.get_size()
	if art.x <= 0.0:
		return
	var window := get_viewport_rect().size
	var tall: float = window.x * art.y / art.x
	# The wall's own base, not the bottom of its picture. Only the corner
	# returns reach that, and standing the picture's bottom on the roof leaves
	# the wall itself hanging a strip of lit city underneath it.
	var base: float = _wall_base_of(parapet.texture)
	var bottom: float = _roof_line() + tall * (1.0 - base) + PARAPET_SETTLE
	parapet.anchor_left = 0.0
	parapet.anchor_right = 1.0
	parapet.anchor_top = 0.0
	parapet.anchor_bottom = 0.0
	parapet.offset_left = 0.0
	parapet.offset_right = 0.0
	parapet.offset_top = bottom - tall
	parapet.offset_bottom = bottom
	parapet.size = Vector2(window.x, tall)


static func _wall_base_of(texture: Texture2D) -> float:
	"""How far down its picture the parapet's wall stands, as a fraction.

	The corner returns run to the very bottom of the picture, but the wall
	between them stops well short of it -- that space is the near side of the
	roof, drawn as nothing so the floor behind shows through. So the bottom of
	the picture is not the line the wall stands on, and standing the picture
	on the roof puts the wall a good way above it.
	"""
	if texture == null:
		return 1.0
	var image := texture.get_image()
	if image == null:
		return 1.0
	if image.is_compressed():
		if image.decompress() != OK:
			return 1.0
	var high := image.get_height()
	var wide := image.get_width()
	if high < 4 or wide < 4:
		return 1.0
	# The middle of the picture, well clear of the returns at either end.
	var lowest := 0
	for x in range(int(wide * 0.35), int(wide * 0.65), 8):
		for y in range(high - 1, -1, -1):
			if image.get_pixel(x, y).a > 0.25:
				lowest = maxi(lowest, y)
				break
	if lowest < 1:
		return 1.0
	return float(lowest + 1) / float(high)


func _roof_line() -> float:
	"""Where the city stops and the roof starts, down the window.

	Read off the background rather than measured out here, so it still lands
	on the roof if the picture is repainted or the window changes shape. The
	background is drawn to cover the window, so part of it is off the edges,
	and where a line of it comes out on screen has to be worked out from what
	is actually shown rather than from the picture's own height.
	"""
	var back: TextureRect = $Background
	var window := get_viewport_rect().size
	if back == null or back.texture == null:
		return window.y
	var art: Vector2 = back.texture.get_size()
	if art.x <= 0.0 or art.y <= 0.0:
		return window.y
	var down := _roof_line_of(back.texture)
	# Covering the window scales the picture up until neither side falls
	# short, so the overflow hangs off both edges evenly.
	var cover: float = maxf(window.x / art.x, window.y / art.y)
	var shown := art * cover
	return (shown.y - window.y) / -2.0 + down * shown.y


static func _roof_line_of(texture: Texture2D) -> float:
	"""Where the lit city gives way to the dark roof, as a fraction down.

	The roof is much darker than the city standing on it, so the line between
	them is the sharpest drop in brightness in the lower part of the picture.
	The middle is skipped: the seam of fire runs up it and is brighter than
	anything else, which would drag the reading around with it.
	"""
	var image := texture.get_image()
	if image == null:
		return 1.0
	if image.is_compressed():
		if image.decompress() != OK:
			return 1.0
	var high := image.get_height()
	var wide := image.get_width()
	if high < 32 or wide < 32:
		return 1.0

	var rows := PackedFloat32Array()
	rows.resize(high)
	for y in high:
		var lit := 0.0
		var counted := 0
		for x in range(0, wide, 16):
			# The fire seam is brighter than the city and would drown the
			# reading, so the middle of the picture is left out of it.
			if absf(float(x) / float(wide) - 0.5) < 0.08:
				continue
			var pixel := image.get_pixel(x, y)
			lit += pixel.r + pixel.g + pixel.b
			counted += 1
		rows[y] = lit / float(maxi(counted, 1))

	# The sharpest fall between the eight rows above a line and the eight
	# below it, looked for only in the bottom third where a roof can be.
	var step := 8
	var sharpest := 0.0
	var found := high
	for y in range(int(high * 0.6), high - step):
		var above := 0.0
		var below := 0.0
		for i in step:
			above += rows[y - step + i]
			below += rows[y + i]
		var fall := (above - below) / float(step)
		if fall > sharpest:
			sharpest = fall
			found = y
	if found >= high:
		return 1.0
	return float(found) / float(high)


func _frame_the_rack(rack: Control, frame: TextureRect) -> void:
	"""Sit a frame behind a rack, showing a margin of itself all round."""
	if rack == null or not is_instance_valid(rack) or frame == null:
		return
	var margin := Vector2(FRAME_MARGIN, FRAME_MARGIN)
	frame.position = rack.position - margin
	frame.size = rack.size + margin * 2.0


func _setup_inventories():
	# Constants for grid configuration
	const GRID_WIDTH = 9
	const GRID_HEIGHT = 7
	const CELL_SPACING = 1
	# Fixed, not fitted to the panel it sits in. A cell sized to fill whatever
	# space was left over came out at 48 pixels, and an item drawn that small
	# is a smudge - and the racks are what the battle is decided by, so they
	# are what there has to be room for.
	#
	# As big as the room allows: the racks stand clear of the clock above them
	# and the stats below, and leave the middle of the screen to the seam of
	# fire and what is written over it. Everything else about a rack -- where
	# it stands, its backdrop, the frame behind it -- is measured off the grid,
	# so this is the one number that decides how big an item is drawn.
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
	player_stamina_label.text = "%.1f/%.0f" % [player_data.stamina, player_data.max_stamina]

	# Update enemy stats
	enemy_health_bar.max_value = enemy_data.max_health
	enemy_health_bar.value = enemy_data.health
	enemy_health_label.text = "%d/%d" % [enemy_data.health, enemy_data.max_health]

	hud.health_changed(enemy_health_bar)

	enemy_stamina_bar.max_value = enemy_data.max_stamina
	enemy_stamina_bar.value = enemy_data.stamina
	enemy_stamina_label.text = "%.1f/%.0f" % [enemy_data.stamina, enemy_data.max_stamina]



func _connect_event_signals():
	# Connect all event processor signals
	event_processor.battle_started.connect(_on_battle_started)
	event_processor.damage_dealt.connect(_on_damage_dealt)
	event_processor.healing_done.connect(_on_healing_done)
	event_processor.block_activated.connect(_on_block_activated)
	event_processor.cpu_changed.connect(_on_cpu_changed)
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
		# Nothing yet. The first action carries where the CPU really stood, and
		# it arrives at the battle's own timestamp zero. Naming a number here
		# is what put a static 10 out of 10 on screen for the whole battle.
		"stamina": 0.0,
		"max_stamina": 0.0,
		"buffs": []
	}

	enemy_data = {
		"health": quota,
		"max_health": quota,
		# Nothing yet. The first action carries where the CPU really stood, and
		# it arrives at the battle's own timestamp zero. Naming a number here
		# is what put a static 10 out of 10 on screen for the whole battle.
		"stamina": 0.0,
		"max_stamina": 0.0,
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

func _on_cpu_changed(player: int, cpu: float, max_cpu: float):
	"""Take the CPU level from the battle rather than making one up."""
	var side = player_data if player == 1 else enemy_data
	side.stamina = cpu
	side.max_stamina = max_cpu


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
