extends Control
class_name BattleVisualization

signal battle_finished(winner: int)

const HEALTH_BAR_SIZE = Vector2(300, 30)
const LOG_MAX_LINES = 20

var player_health: int = 100
var player_max_health: int = 100
var opponent_health: int = 100
var opponent_max_health: int = 100

var battle_log_entries: Array[String] = []
var battle_events: Array[Dictionary] = []
var current_event_index: int = 0
var event_timer: float = 0.0
var battle_active: bool = false
var playback_speed: float = 1.0

@onready var player_health_bar: ProgressBar = ProgressBar.new()
@onready var opponent_health_bar: ProgressBar = ProgressBar.new()
@onready var battle_log: RichTextLabel = RichTextLabel.new()
@onready var event_display: Label = Label.new()

func _ready():
	_setup_ui()

func _setup_ui():
	# Main container
	var main_vbox = VBoxContainer.new()
	main_vbox.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	main_vbox.add_theme_constant_override("separation", 20)
	add_child(main_vbox)

	# Title
	var title = Label.new()
	title.text = "BATTLE IN PROGRESS"
	title.add_theme_font_size_override("font_size", 28)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	main_vbox.add_child(title)

	# Health bars container
	var health_container = VBoxContainer.new()
	health_container.add_theme_constant_override("separation", 30)
	main_vbox.add_child(health_container)

	# Player health
	var player_health_container = VBoxContainer.new()
	health_container.add_child(player_health_container)

	var player_label = Label.new()
	player_label.text = "Your Health"
	player_label.add_theme_font_size_override("font_size", 16)
	player_health_container.add_child(player_label)

	player_health_bar.custom_minimum_size = HEALTH_BAR_SIZE
	player_health_bar.max_value = 100
	player_health_bar.value = 100
	player_health_bar.show_percentage = false
	_style_health_bar(player_health_bar, Color(0.2, 0.8, 0.2))
	player_health_container.add_child(player_health_bar)

	var player_health_text = Label.new()
	player_health_text.name = "PlayerHealthText"
	player_health_text.text = "100 / 100"
	player_health_text.add_theme_font_size_override("font_size", 14)
	player_health_container.add_child(player_health_text)

	# Opponent health
	var opponent_health_container = VBoxContainer.new()
	health_container.add_child(opponent_health_container)

	var opponent_label = Label.new()
	opponent_label.text = "Opponent Health"
	opponent_label.add_theme_font_size_override("font_size", 16)
	opponent_health_container.add_child(opponent_label)

	opponent_health_bar.custom_minimum_size = HEALTH_BAR_SIZE
	opponent_health_bar.max_value = 100
	opponent_health_bar.value = 100
	opponent_health_bar.show_percentage = false
	_style_health_bar(opponent_health_bar, Color(0.8, 0.2, 0.2))
	opponent_health_container.add_child(opponent_health_bar)

	var opponent_health_text = Label.new()
	opponent_health_text.name = "OpponentHealthText"
	opponent_health_text.text = "100 / 100"
	opponent_health_text.add_theme_font_size_override("font_size", 14)
	opponent_health_container.add_child(opponent_health_text)

	# Event display
	event_display.add_theme_font_size_override("font_size", 18)
	event_display.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	event_display.modulate = Color(1.0, 1.0, 0.8)
	main_vbox.add_child(event_display)

	# Battle log
	var log_container = VBoxContainer.new()
	main_vbox.add_child(log_container)

	var log_label = Label.new()
	log_label.text = "Battle Log"
	log_label.add_theme_font_size_override("font_size", 14)
	log_container.add_child(log_label)

	battle_log.custom_minimum_size = Vector2(600, 200)
	battle_log.bbcode_enabled = true
	battle_log.scroll_following = true

	var log_style = StyleBoxFlat.new()
	log_style.bg_color = Color(0.1, 0.1, 0.15, 0.9)
	log_style.border_color = Color(0.3, 0.3, 0.4, 1.0)
	log_style.set_border_width_all(2)
	battle_log.add_theme_stylebox_override("panel", log_style)

	log_container.add_child(battle_log)

	# Speed controls
	var speed_container = HBoxContainer.new()
	speed_container.add_theme_constant_override("separation", 10)
	main_vbox.add_child(speed_container)

	var speed_label = Label.new()
	speed_label.text = "Playback Speed:"
	speed_container.add_child(speed_label)

	for speed in [0.5, 1.0, 2.0, 4.0]:
		var speed_button = Button.new()
		speed_button.text = str(speed) + "x"
		speed_button.toggle_mode = true
		speed_button.button_group = ButtonGroup.new()
		if speed == 1.0:
			speed_button.button_pressed = true
		speed_button.pressed.connect(_on_speed_changed.bind(speed))
		speed_container.add_child(speed_button)

func _style_health_bar(bar: ProgressBar, color: Color):
	var fg_style = StyleBoxFlat.new()
	fg_style.bg_color = color
	fg_style.corner_radius_top_left = 4
	fg_style.corner_radius_top_right = 4
	fg_style.corner_radius_bottom_left = 4
	fg_style.corner_radius_bottom_right = 4
	bar.add_theme_stylebox_override("fill", fg_style)

	var bg_style = StyleBoxFlat.new()
	bg_style.bg_color = Color(0.2, 0.2, 0.25, 0.8)
	bg_style.border_color = Color(0.4, 0.4, 0.5, 1.0)
	bg_style.set_border_width_all(2)
	bg_style.corner_radius_top_left = 4
	bg_style.corner_radius_top_right = 4
	bg_style.corner_radius_bottom_left = 4
	bg_style.corner_radius_bottom_right = 4
	bar.add_theme_stylebox_override("background", bg_style)

func start_battle(battle_result: Dictionary):
	battle_active = true
	current_event_index = 0
	event_timer = 0.0
	battle_log.clear()

	# Extract initial states
	var initial_state = battle_result.get("initial_state", {})
	player_max_health = initial_state.get("player_health", 100)
	opponent_max_health = initial_state.get("opponent_health", 100)
	player_health = player_max_health
	opponent_health = opponent_max_health

	# Set up health bars
	player_health_bar.max_value = player_max_health
	player_health_bar.value = player_health
	opponent_health_bar.max_value = opponent_max_health
	opponent_health_bar.value = opponent_health

	_update_health_displays()

	# Parse events
	battle_events = battle_result.get("events", [])

	_add_log_entry("[color=yellow]Battle Started![/color]")
	_add_log_entry("Player Health: %d | Opponent Health: %d" % [player_health, opponent_health])

func _process(delta: float):
	if not battle_active or battle_events.is_empty():
		return

	event_timer += delta * playback_speed

	# Process events that should have occurred by now
	while current_event_index < battle_events.size():
		var event = battle_events[current_event_index]
		var event_time = event.get("time", 0.0)

		if event_time <= event_timer:
			_process_event(event)
			current_event_index += 1
		else:
			break

	# Check if battle is complete
	if current_event_index >= battle_events.size() and battle_active:
		_end_battle()

func _process_event(event: Dictionary):
	var event_type = event.get("type", "")

	match event_type:
		"attack":
			_process_attack_event(event)
		"heal":
			_process_heal_event(event)
		"buff":
			_process_buff_event(event)
		"debuff":
			_process_debuff_event(event)
		"shield_block":
			_process_shield_event(event)
		"special":
			_process_special_event(event)
		_:
			_process_generic_event(event)

func _process_attack_event(event: Dictionary):
	var attacker = event.get("attacker", "")
	var target = event.get("target", "")
	var damage = event.get("damage", 0)
	var item_name = event.get("item", "Unknown")
	var hit = event.get("hit", true)

	if hit:
		var color = "red" if attacker == "player" else "lime"
		_add_log_entry("[color=%s]%s[/color] attacks with [color=cyan]%s[/color] for [color=yellow]%d damage[/color]" % [color, attacker.capitalize(), item_name, damage])

		if target == "player":
			player_health = max(0, player_health - damage)
		else:
			opponent_health = max(0, opponent_health - damage)

		_update_health_displays()
		_show_event_popup("-%d" % damage, target == "player")
	else:
		_add_log_entry("[color=gray]%s missed with %s[/color]" % [attacker.capitalize(), item_name])
		_show_event_popup("MISS", target == "player")

func _process_heal_event(event: Dictionary):
	var target = event.get("target", "")
	var amount = event.get("amount", 0)
	var source = event.get("source", "Unknown")

	_add_log_entry("[color=lime]%s[/color] healed for [color=green]%d HP[/color] from %s" % [target.capitalize(), amount, source])

	if target == "player":
		player_health = min(player_max_health, player_health + amount)
	else:
		opponent_health = min(opponent_max_health, opponent_health + amount)

	_update_health_displays()
	_show_event_popup("+%d" % amount, target == "player")

func _process_buff_event(event: Dictionary):
	var target = event.get("target", "")
	var buff = event.get("buff", "")
	var stacks = event.get("stacks", 1)

	_add_log_entry("[color=cyan]%s[/color] gained [color=yellow]%s x%d[/color]" % [target.capitalize(), buff, stacks])

func _process_debuff_event(event: Dictionary):
	var target = event.get("target", "")
	var debuff = event.get("debuff", "")
	var stacks = event.get("stacks", 1)

	_add_log_entry("[color=orange]%s[/color] afflicted with [color=red]%s x%d[/color]" % [target.capitalize(), debuff, stacks])

func _process_shield_event(event: Dictionary):
	var defender = event.get("defender", "")
	var blocked = event.get("blocked", 0)
	var shield_name = event.get("shield", "Shield")

	_add_log_entry("[color=cyan]%s's %s[/color] blocked [color=yellow]%d damage[/color]" % [defender.capitalize(), shield_name, blocked])
	_show_event_popup("BLOCKED", defender == "player")

func _process_special_event(event: Dictionary):
	var description = event.get("description", "Special event occurred")
	_add_log_entry("[color=magenta]%s[/color]" % description)

func _process_generic_event(event: Dictionary):
	var description = event.get("description", "")
	if description != "":
		_add_log_entry(description)

func _update_health_displays():
	player_health_bar.value = player_health
	opponent_health_bar.value = opponent_health

	var player_text = get_node_or_null("VBoxContainer/VBoxContainer/VBoxContainer/PlayerHealthText")
	if player_text:
		player_text.text = "%d / %d" % [player_health, player_max_health]

	var opponent_text = get_node_or_null("VBoxContainer/VBoxContainer/VBoxContainer2/OpponentHealthText")
	if opponent_text:
		opponent_text.text = "%d / %d" % [opponent_health, opponent_max_health]

func _show_event_popup(text: String, is_player: bool):
	event_display.text = text
	event_display.modulate = Color(1.0, 0.5, 0.5) if text.begins_with("-") else Color(0.5, 1.0, 0.5) if text.begins_with("+") else Color(1.0, 1.0, 0.5)

	# Fade out animation
	var tween = create_tween()
	tween.tween_property(event_display, "modulate:a", 1.0, 0.1)
	tween.tween_property(event_display, "modulate:a", 0.0, 0.5).set_delay(0.5)

func _add_log_entry(text: String):
	battle_log.append_text(text + "\n")

	# Keep log size manageable
	if battle_log.get_line_count() > LOG_MAX_LINES * 2:
		var lines = battle_log.text.split("\n")
		lines = lines.slice(lines.size() - LOG_MAX_LINES, lines.size())
		battle_log.clear()
		for line in lines:
			battle_log.append_text(line + "\n")

func _end_battle():
	battle_active = false

	var winner = 0
	if player_health > 0 and opponent_health <= 0:
		winner = 1
		_add_log_entry("\n[color=green][b]VICTORY![/b][/color]")
	elif opponent_health > 0 and player_health <= 0:
		winner = -1
		_add_log_entry("\n[color=red][b]DEFEAT![/b][/color]")
	else:
		_add_log_entry("\n[color=yellow]DRAW![/color]")

	battle_finished.emit(winner)

func _on_speed_changed(speed: float):
	playback_speed = speed

func simulate_test_battle():
	# Test battle for development
	var test_result = {
		"initial_state": {
			"player_health": 100,
			"opponent_health": 100
		},
		"events": [
			{"type": "attack", "time": 1.0, "attacker": "player", "target": "opponent", "damage": 8, "item": "Null Pointer", "hit": true},
			{"type": "attack", "time": 2.5, "attacker": "opponent", "target": "player", "damage": 6, "item": "Memory Leak", "hit": true},
			{"type": "shield_block", "time": 3.0, "defender": "player", "blocked": 5, "shield": "Error Monitoring"},
			{"type": "buff", "time": 3.5, "target": "player", "buff": "Optimized", "stacks": 2},
			{"type": "attack", "time": 4.0, "attacker": "player", "target": "opponent", "damage": 12, "item": "SQL Injection", "hit": true},
			{"type": "heal", "time": 5.0, "target": "player", "amount": 5, "source": "Redis Cache"},
			{"type": "debuff", "time": 5.5, "target": "opponent", "debuff": "Throttled", "stacks": 1},
			{"type": "attack", "time": 6.0, "attacker": "player", "target": "opponent", "damage": 15, "item": "Stack Overflow", "hit": true},
			{"type": "special", "time": 7.0, "description": "Chaos Engineering activated!"},
			{"type": "attack", "time": 8.0, "attacker": "player", "target": "opponent", "damage": 20, "item": "Kernel Panic", "hit": true}
		],
		"winner": 1
	}

	start_battle(test_result)
