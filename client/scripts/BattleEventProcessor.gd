class_name BattleEventProcessor
extends Node
# Processes battle events from server and triggers animations/updates

const APITypes = preload("res://scripts/api_types.gd")

signal event_processed(event: APITypes.BattleAction)
signal battle_started()
signal damage_dealt(player: int, amount: int, remaining_hp: int, source: String)
signal healing_done(player: int, amount: int, remaining_hp: int)
signal block_activated(player: int, amount: int)
signal item_activated(item_id: String, player: int)
signal buff_applied(player: int, buff_name: String)
signal debuff_applied(player: int, debuff_name: String)
signal player_died(player: int)
signal battle_ended(winner: int)
signal log_message(message: String, color: Color)

var events: Array = []
var current_event_index: int = 0
var start_time: float = 0.0
var playback_speed: float = 1.0
var is_playing: bool = false
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

	var current_time = (Time.get_ticks_msec() / 1000.0 - start_time) * playback_speed

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
		"a":
			log_msg = "[%.1fs] Player %d activates %s" % [event_time, player, item_name]
			log_color = Color(0.7, 0.7, 1.0)  # Light blue for activations
		"d", "damage":
			var attacker = 1 if player == 2 else 2  # Player who TAKES damage is opposite of attacker
			log_msg = "[%.1fs] Player %d's %s deals %d damage → Player %d" % [event_time, attacker, item_name, event.damage, player]
			log_color = Color(1.0, 0.5, 0.5) if player == 1 else Color(1.0, 0.7, 0.7)  # Red for damage
		"h", "heal":
			log_msg = "[%.1fs] Player %d's %s heals %d HP" % [event_time, player, item_name, event.damage]
			log_color = Color(0.5, 1.0, 0.5)  # Green for healing
		"x", "player_defeated":
			log_msg = "[%.1fs] Player %d DIES!" % [event_time, player]
			log_color = Color(1.0, 0.2, 0.2)  # Dark red for death
		"s", "battle_start":
			log_msg = "[%.1fs] Battle starts!" % [event_time]
			log_color = Color(1.0, 1.0, 0.5)  # Yellow for battle start
		"b", "block":
			var attacker = 1 if player == 2 else 2
			log_msg = "[%.1fs] Player %d's attack BLOCKED by Player %d's %s (%d damage blocked)" % [event_time, attacker, player, item_name, event.damage]
			log_color = Color(0.5, 0.8, 1.0)  # Light blue for blocks
		"m", "miss":
			var attacker = 1 if player == 2 else 2
			log_msg = "[%.1fs] Player %d's %s MISSES Player %d" % [event_time, attacker, item_name, player]
			log_color = Color(0.7, 0.7, 0.7)  # Gray for misses
		"c", "critical_hit":
			var attacker = 1 if player == 2 else 2
			log_msg = "[%.1fs] CRITICAL! Player %d's %s deals %d damage → Player %d" % [event_time, attacker, item_name, event.damage, player]
			log_color = Color(1.0, 0.8, 0.2)  # Orange for crits
		_:
			log_msg = "[%.1fs] Player %d: Action=%s, Source=%s, Damage=%d" % [event_time, player, action, item_name, event.damage]
			log_color = Color.WHITE

	# Emit both to console and UI
	print(log_msg)
	log_message.emit(log_msg, log_color)

	match action:
		"s", "battle_start":  # Start
			battle_started.emit()

		"a":  # Activate
			var item_id = event.source
			item_activated.emit(item_id, player)

		"d", "damage":  # Damage
			var damage = event.damage
			var damage_source = event.source if event.source else "Unknown"
			# Calculate remaining HP based on current HP
			var remaining = (player1_hp if player == 1 else player2_hp) - damage
			if player == 1:
				player1_hp = remaining
			else:
				player2_hp = remaining
			damage_dealt.emit(player, damage, remaining, damage_source)

		"h":  # Heal
			# Get heal amount from damage field
			var amount = event.damage
			var remaining = (player1_hp if player == 1 else player2_hp) + amount
			if player == 1:
				player1_hp = min(remaining, player1_max_hp)
			else:
				player2_hp = min(remaining, player2_max_hp)
			healing_done.emit(player, amount, remaining)

		"b", "block":  # Block
			var amount = event.damage
			block_activated.emit(player, amount)

		"bf":  # Buff
			var buff_name = ""
			if not event.details.is_empty():
				buff_name = event.details.get("buff", "")
			buff_applied.emit(player, buff_name)

		"df":  # Debuff
			var debuff_name = ""
			if not event.details.is_empty():
				debuff_name = event.details.get("debuff", "")
			debuff_applied.emit(player, debuff_name)

		"cf":  # CPU Fail
			# Visual indicator that item couldn't activate due to CPU
			pass

		"x", "player_defeated":  # Death
			player_died.emit(player)
			if player == 1:
				player1_hp = 0
			else:
				player2_hp = 0

		"m", "miss":  # Miss
			# Show miss animation
			pass

		"c":  # Crit
			# Show critical hit effect
			pass

		"dt":  # DoT (damage over time)
			var damage = event.damage
			var dot_source = event.source if event.source else "DoT"
			if player == 1:
				player1_hp = max(0, player1_hp - damage)
			else:
				player2_hp = max(0, player2_hp - damage)
			damage_dealt.emit(player, damage, player1_hp if player == 1 else player2_hp, dot_source)

		"r":  # Reflect
			# Show reflect animation
			pass

	event_processed.emit(event)

func _finish_battle():
	is_playing = false
	set_process(false)

	# Determine winner
	var winner = 1 if player1_hp > player2_hp else 2
	battle_ended.emit(winner)

func get_current_time() -> float:
	"""Get current playback time in seconds"""
	if not is_playing:
		return 0.0
	return (Time.get_ticks_msec() / 1000.0 - start_time) * playback_speed

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
