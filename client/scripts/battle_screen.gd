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

	# What the fighters stand on before anything has happened to them. Put up
	# now rather than when playback starts: the scene's bars are Godot's own,
	# which read a hundred out of a hundred, and the wait below is long enough
	# to see it.
	_stand_them_up()

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

## How far the parapet settles past the line the roof starts on. That line is
## read off a painting rather than measured, and a wall standing exactly on it
## leaves a hair of city showing under the join. A few pixels of overlap puts
## the wall's foot into the roof and closes it for good.
const PARAPET_SETTLE := 8.0
func _place_battle_art() -> void:
	"""Put the scenery where the room and the fighters actually are.

	The parapet takes its shape from its own picture and its place from the
	roof painted in the background, rather than from anything measured out in
	the scene. The numbers the scene carries are only so the node can be seen
	while it is being edited.
	"""
	_lay_the_parapet()


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
	# As big as the room allows, and the room is decided across the middle of
	# the window rather than down it: nine cells have to fit between the edge
	# of the window and the row of buttons under the clock, and seven of the
	# same cells then have height to spare. This is the one number that decides
	# how big an item is drawn, so it is worth every pixel it can have.
	const CELL_SIZE = 75

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
	event_processor.nightfall_began.connect(_on_nightfall)
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

func _stand_them_up() -> void:
	"""Put both fighters on screen as they were before the battle began.

	The quota is the one the battle was actually fought for, which the
	processor has read off the battle itself. Everything else waits: the first
	action carries where the CPU really stood, and it arrives at the battle's
	own timestamp zero. Naming a number here is what put a static ten out of
	ten on screen for a whole battle.
	"""
	player_data = {
		"health": event_processor.player1_max_hp,
		"max_health": event_processor.player1_max_hp,
		"stamina": 0.0,
		"max_stamina": 0.0,
		"buffs": []
	}
	enemy_data = {
		"health": event_processor.player2_max_hp,
		"max_health": event_processor.player2_max_hp,
		"stamina": 0.0,
		"max_stamina": 0.0,
		"buffs": []
	}
	_update_stats_display()


func _start_battle_playback():
	print("Starting battle playback...")
	battle_active = true
	current_time = 0.0

	# Clear battle log
	battle_log_container.clear()

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


## What a blow looks like when it lands: a red ghost of the item that swung,
## fired at whoever it hit.
##
## The item rather than a bolt, because a build is a set of items and the
## question the player is asking is which of theirs is doing the work. Red
## because it is being done to somebody. Its own size, because that is the size
## the same item is in the rack and a player has to recognise it.
const STRIKE_TINT := Color(1.0, 0.22, 0.3, 0.92)
## Where it comes from: in front of the fighter, between the two of them, and
## above. The height varies with every shot, so a build firing four items a
## second does not fire all of them along one line.
const STRIKE_AHEAD := 230.0
const STRIKE_HIGH := Vector2(90.0, 300.0)
## How far it turns on the way in. Enough to read as thrown rather than slid,
## not so much that it becomes a spinning coin.
const STRIKE_SPIN := 1.6
const STRIKE_TIME := 0.4


func _strike_with(visual: ItemVisual, at_player: int) -> void:
	"""Fire a red copy of an item at the fighter it just hit."""
	if not Presentation.request("item_strike", {"player": at_player}):
		return

	var ghost := visual.artwork_copy()
	if ghost == null:
		return

	ghost.modulate = STRIKE_TINT
	ghost.z_index = 58
	ghost.mouse_filter = Control.MOUSE_FILTER_IGNORE
	# Turned about its own middle, or a spinning item swings around its corner.
	ghost.pivot_offset = ghost.size / 2.0
	add_child(ghost)

	var drawn: Vector2 = ghost.size * ghost.scale
	var lands_on: Vector2 = hud.fighter_at(at_player) - drawn / 2.0
	# In front of them is towards the middle of the screen, which is the other
	# side of them depending on which corner they stand in.
	var ahead := STRIKE_AHEAD if at_player == 1 else -STRIKE_AHEAD
	ghost.position = lands_on + Vector2(
		ahead, -randf_range(STRIKE_HIGH.x, STRIKE_HIGH.y))

	var spin: float = ghost.rotation + randf_range(-STRIKE_SPIN, STRIKE_SPIN)
	var tween = _effect_tween()
	tween.tween_property(ghost, "position", lands_on, STRIKE_TIME) \
		.set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	tween.parallel().tween_property(ghost, "rotation", spin, STRIKE_TIME)
	tween.parallel().tween_property(ghost, "modulate:a", 0.0, STRIKE_TIME * 0.35) \
		.set_delay(STRIKE_TIME * 0.7)
	tween.chain().tween_callback(ghost.queue_free)


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

func _on_damage_dealt(player: int, amount: int, remaining_hp: int, source: String,
		kind: String = "damage"):
	# Player parameter indicates who TAKES damage
	if player == 1:
		player_data.health = remaining_hp
	else:
		enemy_data.health = remaining_hp

	_show_damage_number(player, amount, kind)
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

## How long the music takes to go. Shorter than the wait before the result, so
## it is gone by the time the overlay speaks rather than still going under it.
const MUSIC_FADE := 0.9


func _fade_out_music() -> void:
	"""Take the music down now the fighting has stopped.

	The round result arrives with a win or a loss sting, and a sting over a
	battle track in full flow is two things saying different at once. Down
	first, and the sting has the room to itself.
	"""
	var music := get_node_or_null("BattleMusic") as AudioStreamPlayer
	if music == null or not music.playing:
		return
	# With animations off there is nothing watching, and a tween that has to
	# run its length would hold a test up for no reason.
	if not Presentation.request("music_fade_out"):
		music.stop()
		return
	var fade := create_tween()
	fade.tween_property(music, "volume_db", -80.0, MUSIC_FADE)
	fade.tween_callback(music.stop)


func _on_battle_ended(winner: int):
	battle_active = false
	# Log is handled by BattleEventProcessor

	_fade_out_music()

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

## What is happening to somebody, said in the colour it is written in. A
## player watching a battle reads the numbers before they read anything else,
## so the colour has to carry the meaning on its own.
const HURT := Color(1.0, 0.36, 0.42)
## Poison is not a blow. It arrives on its own clock, off an item that struck
## some time ago, and a player who cannot tell the two apart cannot tell why
## their health is still falling.
const POISON := Color(0.78, 0.45, 1.0)
## Fatigue is nobody's blow. It lands on both fighters at once, every second,
## from no item at all, and the same argument poison makes applies harder: a
## player who reads it as a hit goes looking for what hit them. The twilight
## blue the battle log writes nightfall in, so the two read as one thing.
const TIRED := Color(0.55, 0.5, 0.95)
const MENDED := Color(0.45, 1.0, 0.6)
const SHIELDED := Color(0.5, 0.85, 1.0)


static func hurt_colour(kind: String) -> Color:
	"""What colour a number is written in, for the thing that caused it.

	Its own function because the number itself is only drawn where animations
	run, and what a colour means is worth being sure of either way.
	"""
	if kind == "dot":
		return POISON
	if kind == "fatigue":
		return TIRED
	return HURT


func _show_damage_number(player: int, amount: int, kind: String = "damage"):
	if not Presentation.request("damage_number",
			{"player": player, "amount": amount, "kind": kind}):
		return
	_throw_number(player, "-%d" % amount, hurt_colour(kind), 44)

func _show_heal_effect(player: int, amount: int):
	if not Presentation.request("heal_effect", {"player": player, "amount": amount}):
		return
	_throw_number(player, "+%d" % amount, MENDED, 40)


## How a number arrives, holds and goes. Short and quick: several of them land
## in a second in a busy build, and anything slower turns into a queue.
const NUMBER_IN := 0.12
const NUMBER_FALL := 34.0
const NUMBER_HOLD := 0.85
const NUMBER_OUT := 0.3


func _throw_number(player: int, text: String, tint: Color, size: int):
	"""Throw a number off the fighter it happened to.

	It fades up as it swells, falls a little way, and fades out again. Falling
	rather than rising: a number that rises reads as something being gained,
	and most of these are not.
	"""
	var label = hud.combat_number(player, text, tint, size)
	label.scale = Vector2(0.55, 0.55)
	label.modulate.a = 0.0

	var tween = _effect_tween()
	tween.tween_property(label, "modulate:a", 1.0, NUMBER_IN)
	tween.parallel().tween_property(label, "scale", Vector2.ONE, NUMBER_IN + 0.04) \
		.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tween.parallel().tween_property(label, "position:y",
		label.position.y + NUMBER_FALL, NUMBER_HOLD) \
		.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	tween.chain().tween_property(label, "modulate:a", 0.0, NUMBER_OUT)
	tween.chain().tween_callback(label.queue_free)

## What the city dims to when night falls, and how long it takes to get there.
## Dark and blue rather than simply dark: the roof is lit from the windows
## below it, and taking the light out without cooling it reads as a dead
## monitor rather than as evening.
const NIGHT_TINT := Color(0.44, 0.47, 0.74)
const NIGHT_FALLS_OVER := 1.4


func _on_nightfall():
	"""Say that fatigue has started, in the two ways it needs saying.

	The city dimming is the state -- it holds for the rest of the battle, so
	a player who looks up late still knows where they are. The line across the
	middle is the moment, and it goes away again.

	Neither is load-bearing: every payout is in the log either way. So both go
	through Presentation and are simply skipped when animations are off.
	"""
	if not Presentation.request("nightfall"):
		return

	var dimming = _effect_tween()
	dimming.set_parallel(true)
	for scenery in [$Background, $Parapet]:
		dimming.tween_property(scenery, "modulate", NIGHT_TINT,
			Presentation.delay(NIGHT_FALLS_OVER))

	_announce("Fatigue sets in...", Color(0.74, 0.75, 1.0))


func _announce(text: String, tint: Color):
	"""Put a line across the middle of the screen, and take it away again.

	For something that happened to the battle rather than to a fighter, which
	is why it is centred rather than thrown off one of them.
	"""
	var label := Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", 52)
	label.add_theme_color_override("font_color", tint)
	label.add_theme_color_override("font_outline_color", Color(0.02, 0.01, 0.06, 0.9))
	label.add_theme_constant_override("outline_size", 10)
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	label.z_index = 70

	var window := get_viewport_rect().size
	label.size = Vector2(window.x, 70)
	label.pivot_offset = label.size / 2.0
	label.position = Vector2(0.0, window.y * 0.42 - 35.0)
	label.modulate.a = 0.0
	label.scale = Vector2(0.8, 0.8)
	add_child(label)

	var tween = _effect_tween()
	tween.tween_property(label, "modulate:a", 1.0, 0.3)
	tween.parallel().tween_property(label, "scale", Vector2.ONE, 0.45) \
		.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tween.tween_interval(1.3)
	tween.tween_property(label, "modulate:a", 0.0, 0.6)
	tween.tween_callback(label.queue_free)


func _show_block_effect(player: int):
	if not Presentation.request("block_effect", {"player": player}):
		return
	_throw_number(player, "BLOCK", SHIELDED, 32)

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
	var racks := {1: player_inventory, 2: enemy_inventory}
	for side in [1, 2]:
		var visual = racks[side].item_visual(item_id)
		if visual == null:
			continue
		# Each effect asks for itself. Asking once for the lot of them and
		# giving up on a no would mean the item is never even looked up where
		# animations are off, and then nothing here can be tested.
		if Presentation.request("item_activation",
				{"item": item_id, "action": action}):
			visual.fire(visual.item_data.cooldown)
		if action in ATTACKS:
			hud.item_fired()
			# Whose rack it stands in says who swung it, and a blow lands on
			# the other one. The action's own player cannot be asked: it is
			# the one hurt on a hit and the one swinging on a miss, so a miss
			# used to be thrown at the fighter who threw it.
			_strike_with(visual, 2 if side == 1 else 1)
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
