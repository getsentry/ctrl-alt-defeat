class_name BattleEventProcessor
extends Node
# Processes battle events from server and triggers animations/updates

signal event_processed(event: Dictionary)
signal battle_started()
signal damage_dealt(player: int, amount: int, remaining_hp: int)
signal healing_done(player: int, amount: int, remaining_hp: int)
signal block_activated(player: int, amount: int)
signal item_activated(item_id: String, player: int)
signal buff_applied(player: int, buff_name: String)
signal debuff_applied(player: int, debuff_name: String)
signal player_died(player: int)
signal battle_ended(winner: int)

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

func _ready():
	set_process(false)

func load_battle_events(battle_data: Dictionary):
	# Load events from battle result
	# Handle both direct battle_result and nested structure
	var battle_result = battle_data
	if battle_data.has("battle_result"):
		battle_result = battle_data.battle_result

	if battle_result.has("actions"):
		events = battle_result.actions
		print("Loaded %d battle events" % events.size())
	else:
		events = []
		print("Warning: No battle events found in battle data")

	# Set initial HP from round quota
	player1_max_hp = GameStateManager.get_round_quota()
	player2_max_hp = GameStateManager.get_round_quota()
	player1_hp = player1_max_hp
	player2_hp = player2_max_hp

	# Set final HP if provided
	if battle_result.has("player1_quota"):
		# These will be the ending values
		pass

	if battle_result.has("duration"):
		battle_duration = battle_result.duration
	else:
		battle_duration = 20.0  # Default duration

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
		var event = events[current_event_index]
		var event_time = event.get("t", 0.0)

		if event_time <= current_time:
			_process_event(event)
			current_event_index += 1
		else:
			break  # Wait for next frame

func _process_event(event: Dictionary):
	var action = event.get("a", "")
	var player = event.get("p", 0)

	print("Processing event: %s at time %.1f" % [action, event.get("t", 0.0)])

	match action:
		"s":  # Start
			battle_started.emit()

		"a":  # Activate
			var item_id = event.get("item", "")
			item_activated.emit(item_id, player)

		"d":  # Damage
			var damage = event.get("dmg", 0)
			var remaining = event.get("hp", 0)
			if player == 1:
				player1_hp = remaining
			else:
				player2_hp = remaining
			damage_dealt.emit(player, damage, remaining)

		"h":  # Heal
			var amount = event.get("amount", 0)
			var remaining = event.get("hp", 0)
			if player == 1:
				player1_hp = min(remaining, player1_max_hp)
			else:
				player2_hp = min(remaining, player2_max_hp)
			healing_done.emit(player, amount, remaining)

		"b":  # Block
			var amount = event.get("amount", 0)
			block_activated.emit(player, amount)

		"bf":  # Buff
			var buff_name = event.get("buff", "")
			buff_applied.emit(player, buff_name)

		"df":  # Debuff
			var debuff_name = event.get("debuff", "")
			debuff_applied.emit(player, debuff_name)

		"cf":  # CPU Fail
			# Visual indicator that item couldn't activate due to CPU
			pass

		"x":  # Death
			player_died.emit(player)
			if player == 1:
				player1_hp = 0
			else:
				player2_hp = 0

		"m":  # Miss
			# Show miss animation
			pass

		"c":  # Crit
			# Show critical hit effect
			pass

		"dt":  # DoT (damage over time)
			var damage = event.get("dmg", 0)
			if player == 1:
				player1_hp = max(0, player1_hp - damage)
			else:
				player2_hp = max(0, player2_hp - damage)
			damage_dealt.emit(player, damage, player1_hp if player == 1 else player2_hp)

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

	print("Battle finished. Winner: Player %d" % winner)

func skip_to_end():
	# Fast forward to the end
	if events.is_empty():
		return

	# Process all remaining events instantly
	while current_event_index < events.size():
		_process_event(events[current_event_index])
		current_event_index += 1

	_finish_battle()

func get_current_time() -> float:
	if not is_playing:
		return 0.0
	return (Time.get_ticks_msec() / 1000.0 - start_time) * playback_speed

func get_progress() -> float:
	if events.is_empty() or battle_duration <= 0:
		return 0.0

	var current_time = get_current_time()
	return min(1.0, current_time / battle_duration)
