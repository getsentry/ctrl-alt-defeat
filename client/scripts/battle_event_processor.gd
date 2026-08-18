class_name BattleEventProcessor
extends Node
# Processes battle events from server and triggers animations/updates

const APITypes = preload("res://scripts/api_types.gd")

signal event_processed(event: APITypes.BattleAction)
signal battle_started()
signal damage_dealt(player: int, amount: int, remaining_hp: int, source: String)
signal healing_done(player: int, amount: int, remaining_hp: int)
signal block_activated(player: int, amount: int)
signal item_activated(item_id: String, player: int, action: String)
signal buff_applied(player: int, buff_name: String)
signal debuff_applied(player: int, debuff_name: String)
signal cpu_changed(player: int, cpu: float, max_cpu: float)
signal player_died(player: int)
signal battle_ended(winner: int)
signal log_message(message: String, color: Color)

var events: Array[APITypes.BattleAction] = []
var current_event_index: int = 0
var start_time: float = 0.0
var playback_speed: float = 1.0
var is_playing: bool = false
## Battle seconds already played, at whatever speeds they were played at.
##
## The playhead used to be the wall clock since the start times the speed,
## which works only while the speed never changes. Change it half way and every
## second already played is rescaled with it: eight seconds in, going from 1x
## to 2x moved the playhead to sixteen and fired everything in between at once.
## So the seconds are banked here as they are played, and the wall clock only
## ever measures the stretch since the last change.
var played: float = 0.0
var paused: bool = false
var battle_duration: float = 0.0

# Player states for visualization
var player1_hp: int = 100
var player2_hp: int = 100
var player1_max_hp: int = 100
var player2_max_hp: int = 100
var player1_cpu: float = 10.0
var player2_cpu: float = 10.0

# Item lookup maps for better logging
var item_lookup: Dictionary = {}  # UUID -> item name

func _ready():
	set_process(false)

func load_battle_events(battle_data: APITypes.BattleResult):
	# Load events directly from typed battle result
	events = battle_data.actions
	print("Loaded %d battle events" % events.size())

	# Build item lookup from both inventories
	_build_item_lookup(battle_data.player_inventory, battle_data.enemy_inventory)

	# Set battle duration from typed result
	battle_duration = battle_data.duration if battle_data.duration > 0 else 20.0

	# Set initial HP from round quota
	player1_max_hp = GameStateManager.get_round_quota()
	player2_max_hp = GameStateManager.get_round_quota()
	player1_hp = player1_max_hp
	player2_hp = player2_max_hp

	current_event_index = 0
	is_playing = false

func start_playback(speed: float = 1.0):
	if events.is_empty():
		print("No events to play")
		return

	playback_speed = speed
	current_event_index = 0
	played = 0.0
	paused = false
	start_time = Time.get_ticks_msec() / 1000.0
	is_playing = true
	set_process(true)

	print("Starting battle playback with %d events" % events.size())

func stop_playback():
	is_playing = false
	set_process(false)

func _process(_delta):
	if not is_playing or current_event_index >= events.size():
		if current_event_index >= events.size():
			_finish_battle()
		return

	var current_time = get_current_time()

	# Process all events that should have happened by now
	while current_event_index < events.size():
		var event: APITypes.BattleAction = events[current_event_index]
		var event_time = event.timestamp / 1000.0  # Convert ms to seconds

		if event_time <= current_time:
			_process_event(event)
			current_event_index += 1
		else:
			break  # Wait for next frame

func _process_event(event: APITypes.BattleAction):
	var action = event.action
	var player = event.player
	var event_time = event.timestamp / 1000.0
	var source = event.source if event.source else "none"

	# More descriptive logging based on action type
	var item_name = _get_item_name(source)
	var log_msg = ""
	var log_color = Color.WHITE

	match action:
		"damage":
			var attacker = 1 if player == 2 else 2  # Player who TAKES damage is opposite of attacker
			log_msg = "[%.1fs] Player %d's %s deals %d damage → Player %d" % [event_time, attacker, item_name, event.damage, player]
			log_color = Color(1.0, 0.5, 0.5) if player == 1 else Color(1.0, 0.7, 0.7)  # Red for damage
		"heal":
			log_msg = "[%.1fs] Player %d's %s heals %d HP" % [event_time, player, item_name, event.damage]
			log_color = Color(0.5, 1.0, 0.5)  # Green for healing
		"player_defeated":
			log_msg = "[%.1fs] Player %d DIES!" % [event_time, player]
			log_color = Color(1.0, 0.2, 0.2)  # Dark red for death
		"battle_start":
			log_msg = "[%.1fs] Battle starts!" % [event_time]
			log_color = Color(1.0, 1.0, 0.5)  # Yellow for battle start
		"block":
			var attacker = 1 if player == 2 else 2
			log_msg = "[%.1fs] Player %d's attack BLOCKED by Player %d's %s (%d damage blocked)" % [event_time, attacker, player, item_name, event.damage]
			log_color = Color(0.5, 0.8, 1.0)  # Light blue for blocks
		"miss":
			var attacker = 1 if player == 2 else 2
			log_msg = "[%.1fs] Player %d's %s MISSES Player %d" % [event_time, attacker, item_name, player]
			log_color = Color(0.7, 0.7, 0.7)  # Gray for misses
		"critical_hit":
			var attacker = 1 if player == 2 else 2
			log_msg = "[%.1fs] CRITICAL! Player %d's %s deals %d damage → Player %d" % [event_time, attacker, item_name, event.damage, player]
			log_color = Color(1.0, 0.8, 0.2)  # Orange for crits
		"buff":
			log_msg = "[%.1fs] Player %d's %s grants %s" % [event_time, player, item_name, event.details["buff_name"]]
			log_color = Color(0.6, 1.0, 0.8)  # Mint for buffs
		"debuff":
			log_msg = "[%.1fs] Player %d is afflicted with %s" % [event_time, player, event.details["debuff_name"]]
			log_color = Color(0.8, 0.5, 1.0)  # Purple for debuffs
		"dot":
			log_msg = "[%.1fs] Player %d takes %d damage from %s" % [event_time, player, event.damage, event.details["debuff_name"]]
			log_color = Color(0.8, 0.4, 0.6)  # Sickly pink for damage over time
		"consume":
			log_msg = "[%.1fs] Player %d's %s is used up" % [event_time, player, item_name]
			log_color = Color(0.7, 0.7, 0.7)  # Gray, the item is spent
		"cpu_fail":
			log_msg = "[%.1fs] Player %d's %s could not run: not enough CPU" % [event_time, player, item_name]
			log_color = Color(1.0, 0.6, 0.2)  # Amber for a throttle
		"cpu_drain":
			log_msg = "[%.1fs] Player %d loses %s CPU to %s" % [event_time, player, event.details["amount"], item_name]
			log_color = Color(1.0, 0.6, 0.2)  # Amber, same as a throttle
		"cleanse":
			# One cleanse can take several kinds at once, so name them rather
			# than just counting. details.removed is {name: how many}.
			var taken: Array[String] = []
			for status_name in event.details["removed"]:
				taken.append("%d %s" % [event.details["removed"][status_name], status_name])
			log_msg = "[%.1fs] Player %d's %s cleanses %s" % [event_time, player, item_name, ", ".join(taken)]
			log_color = Color(0.6, 1.0, 0.8)  # Mint, the same as a buff
		_:
			log_msg = "[%.1fs] Player %d: Action=%s, Source=%s, Damage=%d" % [event_time, player, action, item_name, event.damage]
			log_color = Color.WHITE

	# Emit both to console and UI
	print(log_msg)
	log_message.emit(log_msg, log_color)

	match action:
		"battle_start":
			battle_started.emit()

		"damage":
			var damage = event.damage
			var damage_source = event.source if event.source else "Unknown"
			# Calculate remaining HP based on current HP
			var remaining = (player1_hp if player == 1 else player2_hp) - damage
			if player == 1:
				player1_hp = remaining
			else:
				player2_hp = remaining
			damage_dealt.emit(player, damage, remaining, damage_source)

		"heal":
			# Get heal amount from damage field
			var amount = event.damage
			var remaining = (player1_hp if player == 1 else player2_hp) + amount
			if player == 1:
				player1_hp = min(remaining, player1_max_hp)
			else:
				player2_hp = min(remaining, player2_max_hp)
			healing_done.emit(player, amount, remaining)

		"block":
			var amount = event.damage
			block_activated.emit(player, amount)

		"buff":
			buff_applied.emit(player, event.details["buff_name"])

		"debuff":
			debuff_applied.emit(player, event.details["debuff_name"])

		"cpu_fail":
			# Nothing to show yet: the item simply did not activate
			pass

		"cpu_drain":
			# The CPU bar is not driven from the log yet
			pass

		"cleanse":
			# Nothing to show yet: the debuff icons are not driven from the log
			pass

		"player_defeated":
			player_died.emit(player)
			if player == 1:
				player1_hp = 0
			else:
				player2_hp = 0

		"miss":
			# Show miss animation
			pass

		"critical_hit":
			# Show critical hit effect
			pass

		"dot":
			var damage = event.damage
			var dot_source = event.source if event.source else "DoT"
			if player == 1:
				player1_hp = max(0, player1_hp - damage)
			else:
				player2_hp = max(0, player2_hp - damage)
			damage_dealt.emit(player, damage, player1_hp if player == 1 else player2_hp, dot_source)

	# Where both fighters' CPU stood at this moment. Every action carries it,
	# because time passes for both of them, so an action by one is also a
	# moment at which the other's pool has refilled a little.
	if event.details != null and event.details.has("cpu"):
		var levels = event.details["cpu"]
		var pools = event.details.get("max_cpu", [0, 0])
		for side in [0, 1]:
			cpu_changed.emit(side + 1, float(levels[side]), float(pools[side]))

	# Every action with an item behind it is that item firing, and the source
	# is that item's own uid. This signal has been declared and connected since
	# the class was written and never once emitted, so nothing on screen has
	# ever known which item did anything.
	if source != "system" and source != "none":
		item_activated.emit(source, player, action)

	event_processed.emit(event)

func _finish_battle():
	is_playing = false
	set_process(false)

	# Determine winner
	var winner = 1 if player1_hp > player2_hp else 2
	battle_ended.emit(winner)

func get_current_time() -> float:
	"""How far into the battle the playhead is, in battle seconds."""
	if not is_playing and played == 0.0:
		return 0.0
	if paused or not is_playing:
		return played
	return played + (Time.get_ticks_msec() / 1000.0 - start_time) * playback_speed


func _bank() -> void:
	"""Put the stretch since the last change into the total, and re-anchor.

	Every change of pace goes through this. Miss it and the playhead jumps.
	"""
	if not paused and is_playing:
		played += (Time.get_ticks_msec() / 1000.0 - start_time) * playback_speed
	start_time = Time.get_ticks_msec() / 1000.0


func set_playback_speed(speed: float) -> void:
	"""Play faster or slower from here on, without moving the playhead."""
	_bank()
	playback_speed = maxf(speed, 0.01)


func set_paused(wanted: bool) -> void:
	"""Hold the battle where it is, or let it run on from there."""
	if wanted == paused:
		return
	if wanted:
		_bank()
		paused = true
		set_process(false)
	else:
		paused = false
		start_time = Time.get_ticks_msec() / 1000.0
		if is_playing:
			set_process(true)

func get_progress() -> float:
	"""Get battle progress as percentage (0-1)"""
	if battle_duration <= 0:
		return 0.0
	return min(get_current_time() / battle_duration, 1.0)

func skip_to_end():
	# Fast forward to the end
	if events.is_empty():
		return

	# Process all remaining events instantly
	while current_event_index < events.size():
		_process_event(events[current_event_index])
		current_event_index += 1

	_finish_battle()

func _build_item_lookup(player_inventory: APITypes.InventoryState, enemy_inventory: APITypes.InventoryState):
	"""Build lookup table from item UUID to item name"""
	item_lookup.clear()

	# Add player items
	for item in player_inventory.items:
		if item.id and item.name:
			item_lookup[item.id] = item.name
		elif item.id and item.item_type:
			item_lookup[item.id] = item.item_type

	# Add enemy items
	for item in enemy_inventory.items:
		if item.id and item.name:
			item_lookup[item.id] = item.name
		elif item.id and item.item_type:
			item_lookup[item.id] = item.item_type

	print("Built item lookup with %d items" % item_lookup.size())

func _get_item_name(source: String) -> String:
	"""Get readable item name from UUID or source string"""
	# Check if it's a UUID in our lookup
	if item_lookup.has(source):
		return item_lookup[source]

	# If it starts with "ghost_" it's probably already a name
	if source.begins_with("ghost_"):
		return source.replace("ghost_", "").replace("_", " ").capitalize()

	# If it's "system" or similar, return as-is
	if source in ["system", "none", ""]:
		return source

	# Otherwise return first 8 chars of UUID for brevity
	if source.length() > 8:
		return source.substr(0, 8) + "..."

	return source
