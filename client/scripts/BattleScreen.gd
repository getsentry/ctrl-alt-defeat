extends Control

# Preload the BattleEventProcessor class since class_name might not be available yet
const BattleEventProcessor = preload("res://scripts/BattleEventProcessor.gd")

# Event processor for battle replay
var event_processor

# Battle state
var player_data: Dictionary = {}
var enemy_data: Dictionary = {}
var battle_log: Array = []
var current_time: float = 0.0
var battle_active: bool = false
var max_battle_duration: float = 20.0  # 20 second battles max

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

# Battle effects
var attack_particles: Array = []

func _ready():
	print("BattleScreen starting...")

	# Create event processor
	event_processor = BattleEventProcessor.new()
	add_child(event_processor)
	_connect_event_signals()

	_setup_ui()

	# Load battle data from GameStateManager
	if GameStateManager.last_battle_events.size() > 0:
		_load_battle_from_state()
	else:
		_load_mock_battle_data()

	# Start battle playback automatically
	await get_tree().create_timer(0.5).timeout
	_start_battle_playback()

func _setup_ui():
	# Background
	var bg = ColorRect.new()
	bg.color = Color(0.02, 0.02, 0.03, 1.0)
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(bg)

	# Player inventory (left side)
	_create_player_inventory()

	# Enemy inventory (right side)
	_create_enemy_inventory()

	# Player stats (center-left)
	_create_player_stats()

	# Enemy stats (center-right)
	_create_enemy_stats()

	# Battle log (bottom center)
	_create_battle_log()

	# Control buttons
	_create_control_buttons()

func _create_player_inventory():
	var inventory_scene = preload("res://scenes/UnifiedGridUI.tscn")
	player_inventory = inventory_scene.instantiate()
	player_inventory.position = Vector2(20, 20)  # Move to top left
	player_inventory.scale = Vector2(0.65, 0.65)  # Larger scale for better visibility

	# Configure as read-only
	player_inventory.configure({
		"read_only": true,
		"hide_shop": true,
		"hide_storage": true
	})

	add_child(player_inventory)

func _create_enemy_inventory():
	var inventory_scene = preload("res://scenes/UnifiedGridUI.tscn")
	enemy_inventory = inventory_scene.instantiate()
	enemy_inventory.position = Vector2(750, 20)  # Position on right side, at top
	enemy_inventory.scale = Vector2(0.65, 0.65)  # Larger scale for better visibility

	# Configure as read-only
	enemy_inventory.configure({
		"read_only": true,
		"hide_shop": true,
		"hide_storage": true
	})

	add_child(enemy_inventory)

func _create_player_stats():
	# Timer in center middle
	time_label = Label.new()
	time_label.text = "0.0s"
	time_label.position = Vector2(780, 420)  # Center between health bars
	time_label.add_theme_font_size_override("font_size", 24)
	time_label.add_theme_color_override("font_color", Color(1.0, 1.0, 0.5))
	add_child(time_label)

	player_stats_panel = Panel.new()
	player_stats_panel.position = Vector2(500, 460)  # Bottom center-left
	player_stats_panel.size = Vector2(180, 100)

	var panel_style = StyleBoxFlat.new()
	panel_style.bg_color = Color(0.1, 0.15, 0.2, 0.9)
	panel_style.border_color = Color(0.3, 0.8, 1.0, 0.8)
	panel_style.set_border_width_all(2)
	panel_style.set_corner_radius_all(8)
	player_stats_panel.add_theme_stylebox_override("panel", panel_style)
	add_child(player_stats_panel)

	# Player name
	var name_label = Label.new()
	name_label.text = "PLAYER"
	name_label.position = Vector2(10, 5)
	name_label.add_theme_font_size_override("font_size", 14)
	name_label.add_theme_color_override("font_color", Color(0.3, 0.8, 1.0))
	player_stats_panel.add_child(name_label)

	# Health
	var health_title = Label.new()
	health_title.text = "Quota:"
	health_title.position = Vector2(10, 30)
	health_title.add_theme_font_size_override("font_size", 12)
	player_stats_panel.add_child(health_title)

	player_health_bar = ProgressBar.new()
	player_health_bar.position = Vector2(10, 50)
	player_health_bar.size = Vector2(160, 20)
	player_health_bar.value = 100
	player_health_bar.modulate = Color(0.3, 1.0, 0.3)
	player_stats_panel.add_child(player_health_bar)

	player_health_label = Label.new()
	player_health_label.text = "100/100"
	player_health_label.position = Vector2(65, 48)
	player_health_label.add_theme_font_size_override("font_size", 12)
	player_health_label.add_theme_color_override("font_color", Color(0.3, 1.0, 0.3))  # Match bar color
	player_stats_panel.add_child(player_health_label)

	# Stamina (CPU)
	var stamina_title = Label.new()
	stamina_title.text = "CPU:"
	stamina_title.position = Vector2(10, 75)
	stamina_title.add_theme_font_size_override("font_size", 12)
	player_stats_panel.add_child(stamina_title)

	player_stamina_bar = ProgressBar.new()
	player_stamina_bar.position = Vector2(10, 95)
	player_stamina_bar.size = Vector2(160, 20)
	player_stamina_bar.value = 100
	player_stamina_bar.modulate = Color(0.3, 0.6, 1.0)
	player_stats_panel.add_child(player_stamina_bar)

	player_stamina_label = Label.new()
	player_stamina_label.text = "10/10"
	player_stamina_label.position = Vector2(70, 93)
	player_stamina_label.add_theme_font_size_override("font_size", 12)
	player_stamina_label.add_theme_color_override("font_color", Color(0.3, 0.6, 1.0))  # Match bar color
	player_stats_panel.add_child(player_stamina_label)

	# Buffs - removed to save space in smaller panel

func _create_enemy_stats():
	enemy_stats_panel = Panel.new()
	enemy_stats_panel.position = Vector2(900, 460)  # Bottom center-right
	enemy_stats_panel.size = Vector2(180, 100)

	var panel_style = StyleBoxFlat.new()
	panel_style.bg_color = Color(0.2, 0.1, 0.1, 0.9)
	panel_style.border_color = Color(1.0, 0.3, 0.3, 0.8)
	panel_style.set_border_width_all(2)
	panel_style.set_corner_radius_all(8)
	enemy_stats_panel.add_theme_stylebox_override("panel", panel_style)
	add_child(enemy_stats_panel)

	# Enemy name
	var name_label = Label.new()
	name_label.text = "ENEMY"
	name_label.position = Vector2(10, 5)
	name_label.add_theme_font_size_override("font_size", 14)
	name_label.add_theme_color_override("font_color", Color(1.0, 0.3, 0.3))
	enemy_stats_panel.add_child(name_label)

	# Health
	var health_title = Label.new()
	health_title.text = "Quota:"
	health_title.position = Vector2(10, 30)
	health_title.add_theme_font_size_override("font_size", 12)
	enemy_stats_panel.add_child(health_title)

	enemy_health_bar = ProgressBar.new()
	enemy_health_bar.position = Vector2(10, 50)
	enemy_health_bar.size = Vector2(160, 20)
	enemy_health_bar.value = 100
	enemy_health_bar.modulate = Color(1.0, 0.3, 0.3)
	enemy_stats_panel.add_child(enemy_health_bar)

	enemy_health_label = Label.new()
	enemy_health_label.text = "100/100"
	enemy_health_label.position = Vector2(65, 48)
	enemy_health_label.add_theme_font_size_override("font_size", 12)
	enemy_health_label.add_theme_color_override("font_color", Color(1.0, 0.3, 0.3))  # Match bar color
	enemy_stats_panel.add_child(enemy_health_label)

	# Stamina (CPU)
	var stamina_title = Label.new()
	stamina_title.text = "CPU:"
	stamina_title.position = Vector2(10, 75)
	stamina_title.add_theme_font_size_override("font_size", 12)
	enemy_stats_panel.add_child(stamina_title)

	enemy_stamina_bar = ProgressBar.new()
	enemy_stamina_bar.position = Vector2(10, 95)
	enemy_stamina_bar.size = Vector2(160, 20)
	enemy_stamina_bar.value = 100
	enemy_stamina_bar.modulate = Color(1.0, 0.6, 0.3)
	enemy_stats_panel.add_child(enemy_stamina_bar)

	enemy_stamina_label = Label.new()
	enemy_stamina_label.text = "10/10"
	enemy_stamina_label.position = Vector2(70, 93)
	enemy_stamina_label.add_theme_font_size_override("font_size", 12)
	enemy_stamina_label.add_theme_color_override("font_color", Color(1.0, 0.6, 0.3))  # Match bar color
	enemy_stats_panel.add_child(enemy_stamina_label)

	# Buffs - removed to save space in smaller panel

func _create_battle_log():
	var log_panel = Panel.new()
	log_panel.position = Vector2(200, 580)  # Bottom of screen
	log_panel.size = Vector2(1200, 80)  # Wide and short

	var panel_style = StyleBoxFlat.new()
	panel_style.bg_color = Color(0.05, 0.05, 0.08, 0.9)
	panel_style.border_color = Color(0.3, 0.3, 0.4, 0.6)
	panel_style.set_border_width_all(2)
	panel_style.set_corner_radius_all(6)
	log_panel.add_theme_stylebox_override("panel", panel_style)
	add_child(log_panel)

	var log_title = Label.new()
	log_title.text = "Battle Log"
	log_title.position = Vector2(10, 5)
	log_title.add_theme_font_size_override("font_size", 14)
	log_panel.add_child(log_title)

	battle_log_container = RichTextLabel.new()
	battle_log_container.position = Vector2(10, 20)
	battle_log_container.size = Vector2(1180, 50)
	battle_log_container.bbcode_enabled = true
	battle_log_container.scroll_following = true
	battle_log_container.add_theme_font_size_override("normal_font_size", 10)
	log_panel.add_child(battle_log_container)

func _create_control_buttons():
	var start_btn = Button.new()
	start_btn.text = "Start Battle"
	start_btn.position = Vector2(720, 460)
	start_btn.size = Vector2(120, 30)
	start_btn.pressed.connect(_on_start_battle)
	add_child(start_btn)

	var back_btn = Button.new()
	back_btn.text = "Back to Inventory"
	back_btn.position = Vector2(720, 500)
	back_btn.size = Vector2(120, 30)
	back_btn.pressed.connect(_on_back_to_inventory)
	add_child(back_btn)

func _load_mock_battle_data():
	# Load mock player inventory
	var player_inventory_data = {
		"servers": [
			{"data": {"name": "Rack 2x3", "pattern": [[1,1],[1,1],[1,1]], "color": Color(0.3, 0.4, 0.5, 0.3)}, "pos": Vector2i(1, 1)},
			{"data": {"name": "Cube 2x2", "pattern": [[1,1],[1,1]], "color": Color(0.45, 0.35, 0.4, 0.3)}, "pos": Vector2i(5, 2)}
		],
		"items": [
			{"data": {"name": "CPU", "width": 1, "height": 1, "color": Color(0.9, 0.3, 0.3)}, "grid_pos": Vector2i(1, 1)},
			{"data": {"name": "RAM", "width": 2, "height": 1, "color": Color(0.3, 0.6, 0.9)}, "grid_pos": Vector2i(1, 2)},
			{"data": {"name": "Firewall", "width": 1, "height": 2, "color": Color(0.6, 0.3, 0.9)}, "grid_pos": Vector2i(5, 2)}
		]
	}

	# Load mock enemy inventory
	var enemy_inventory_data = {
		"servers": [
			{"data": {"name": "Tower 1x4", "pattern": [[1],[1],[1],[1]], "color": Color(0.35, 0.45, 0.4, 0.3)}, "pos": Vector2i(3, 1)},
			{"data": {"name": "Blade 3x2", "pattern": [[1,1,1],[1,1,1]], "color": Color(0.4, 0.3, 0.5, 0.3)}, "pos": Vector2i(6, 3)}
		],
		"items": [
			{"data": {"name": "Balancer", "width": 2, "height": 2, "color": Color(0.3, 0.9, 0.6)}, "grid_pos": Vector2i(6, 3)},
			{"data": {"name": "CPU", "width": 1, "height": 1, "color": Color(0.9, 0.3, 0.3)}, "grid_pos": Vector2i(3, 1)},
			{"data": {"name": "CPU", "width": 1, "height": 1, "color": Color(0.9, 0.3, 0.3)}, "grid_pos": Vector2i(3, 2)}
		]
	}

	player_inventory.load_inventory_state(player_inventory_data)
	enemy_inventory.load_inventory_state(enemy_inventory_data)

	# Set initial stats
	player_data = {
		"health": 100,
		"max_health": 100,
		"stamina": 10.0,
		"max_stamina": 10.0,
		"buffs": []
	}

	enemy_data = {
		"health": 100,
		"max_health": 100,
		"stamina": 10.0,
		"max_stamina": 10.0,
		"buffs": []
	}

	_update_stats_display()

func _update_stats_display():
	# Update player stats
	player_health_bar.value = (player_data.health / float(player_data.max_health)) * 100
	player_health_label.text = "%d/%d" % [player_data.health, player_data.max_health]

	player_stamina_bar.value = (player_data.stamina / player_data.max_stamina) * 100
	player_stamina_label.text = "%.0f/%.0f" % [player_data.stamina, player_data.max_stamina]

	# Update enemy stats
	enemy_health_bar.value = (enemy_data.health / float(enemy_data.max_health)) * 100
	enemy_health_label.text = "%d/%d" % [enemy_data.health, enemy_data.max_health]

	enemy_stamina_bar.value = (enemy_data.stamina / enemy_data.max_stamina) * 100
	enemy_stamina_label.text = "%.0f/%.0f" % [enemy_data.stamina, enemy_data.max_stamina]

	# Buffs removed from display to save space

func _connect_event_signals():
	# Connect all event processor signals
	event_processor.battle_started.connect(_on_battle_started)
	event_processor.damage_dealt.connect(_on_damage_dealt)
	event_processor.healing_done.connect(_on_healing_done)
	event_processor.block_activated.connect(_on_block_activated)
	event_processor.item_activated.connect(_on_item_activated)
	event_processor.player_died.connect(_on_player_died)
	event_processor.battle_ended.connect(_on_battle_ended)

func _load_battle_from_state():
	# Load battle data from GameStateManager
	var battle_result = GameStateManager.last_battle_result
	event_processor.load_battle_events(battle_result)

	# Load inventories
	var saved_inventory = GameStateManager.get_inventory_state()
	if saved_inventory.has("items"):
		player_inventory.load_inventory_state(saved_inventory)

	# TODO: Load enemy inventory from server data
	_load_mock_enemy_inventory()

func _start_battle_playback():
	print("Starting battle playback...")
	battle_active = true
	current_time = 0.0

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

	# Start event playback
	event_processor.start_playback(GameStateManager.battle_speed)

func _process(delta):
	if battle_active and event_processor.is_playing:
		current_time = event_processor.get_current_time()
		time_label.text = "%.1fs / %.1fs" % [current_time, max_battle_duration]

		# Update progress bar if we add one
		var progress = event_processor.get_progress()
		# TODO: Update progress bar

		_update_stats_display()

func _simulate_attack(is_player: bool):
	if is_player:
		if player_data.stamina >= 3:
			player_data.stamina -= 3
			var damage = randi_range(5, 10)
			enemy_data.health = max(0, enemy_data.health - damage)
			_add_to_log("[color=aqua]Player[/color] attacks for [color=yellow]%d[/color] damage!" % damage)
			_show_attack_animation(true)
	else:
		if enemy_data.stamina >= 3:
			enemy_data.stamina -= 3
			var damage = randi_range(4, 8)
			player_data.health = max(0, player_data.health - damage)
			_add_to_log("[color=red]Enemy[/color] attacks for [color=yellow]%d[/color] damage!" % damage)
			_show_attack_animation(false)

func _show_attack_animation(from_player: bool):
	# Simple visual effect for attacks
	var effect = ColorRect.new()
	effect.size = Vector2(30, 30)
	effect.color = Color(1.0, 1.0, 0.0, 0.8) if from_player else Color(1.0, 0.3, 0.3, 0.8)

	if from_player:
		effect.position = Vector2(400, 250)  # Adjusted for new inventory positions
	else:
		effect.position = Vector2(1000, 250)  # Adjusted for new inventory positions

	add_child(effect)

	# Animate the effect
	var tween = create_tween()
	var target_pos = Vector2(800, 250)  # Center between inventories
	tween.tween_property(effect, "position", target_pos, 0.3)
	tween.tween_property(effect, "modulate:a", 0.0, 0.2)
	tween.tween_callback(effect.queue_free)

func _add_to_log(text: String):
	battle_log_container.append_text(text + "\n")

func _on_start_battle():
	if not battle_active:
		battle_active = true
		current_time = 0.0
		_add_to_log("[color=green]Battle Started![/color]")

func _end_battle():
	battle_active = false

	if player_data.health <= 0:
		_add_to_log("[color=red]DEFEAT! You have been eliminated.[/color]")
	elif enemy_data.health <= 0:
		_add_to_log("[color=green]VICTORY! Enemy destroyed![/color]")
	else:
		_add_to_log("[color=yellow]TIME OUT! Battle ended.[/color]")

func _on_back_to_inventory():
	get_tree().change_scene_to_file("res://scenes/UnifiedGridUI.tscn")

# Event handler functions for battle events
func _on_battle_started():
	_add_to_log("[color=green]Battle Started![/color]")

func _on_damage_dealt(player: int, amount: int, remaining_hp: int):
	if player == 1:
		player_data.health = remaining_hp
		_add_to_log("[color=red]You[/color] take [color=yellow]%d[/color] damage!" % amount)
	else:
		enemy_data.health = remaining_hp
		_add_to_log("[color=aqua]You[/color] deal [color=yellow]%d[/color] damage!" % amount)

	_show_damage_number(player, amount)
	_update_stats_display()

func _on_healing_done(player: int, amount: int, remaining_hp: int):
	if player == 1:
		player_data.health = remaining_hp
		_add_to_log("[color=aqua]You[/color] heal for [color=green]%d[/color]" % amount)
	else:
		enemy_data.health = remaining_hp
		_add_to_log("[color=red]Enemy[/color] heals for [color=green]%d[/color]" % amount)

	_show_heal_effect(player, amount)
	_update_stats_display()

func _on_block_activated(player: int, amount: int):
	var who = "You" if player == 1 else "Enemy"
	_add_to_log("[color=cyan]%s[/color] blocks [color=yellow]%d[/color] damage!" % [who, amount])
	_show_block_effect(player)

func _on_item_activated(item_id: String, player: int):
	# Show item activation visual
	_show_item_activation(item_id, player)

func _on_player_died(player: int):
	if player == 1:
		_add_to_log("[color=red]You have been defeated![/color]")
	else:
		_add_to_log("[color=green]Enemy destroyed![/color]")

func _on_battle_ended(winner: int):
	battle_active = false

	if winner == 1:
		_add_to_log("[color=green]VICTORY![/color]")
	else:
		_add_to_log("[color=red]DEFEAT![/color]")

	# Wait a moment then go to post-battle screen
	await get_tree().create_timer(2.0).timeout
	_go_to_post_battle()

func _load_mock_enemy_inventory():
	# Create mock enemy inventory
	var enemy_inventory_data = {
		"servers": [
			{"data": {"name": "Tower 1x4", "pattern": [[1],[1],[1],[1]], "color": Color(0.35, 0.45, 0.4, 0.3)}, "pos": Vector2i(3, 1)},
		],
		"items": [
			{"data": {"name": "CPU", "width": 1, "height": 1, "color": Color(0.9, 0.3, 0.3)}, "grid_pos": Vector2i(3, 1)},
		]
	}
	enemy_inventory.load_inventory_state(enemy_inventory_data)

func _show_damage_number(player: int, amount: int):
	var label = Label.new()
	label.text = "-%d" % amount
	label.add_theme_font_size_override("font_size", 24)
	label.add_theme_color_override("font_color", Color(1.0, 0.3, 0.3))

	if player == 1:
		label.position = Vector2(590, 500)
	else:
		label.position = Vector2(990, 500)

	add_child(label)

	# Animate floating up and fading
	var tween = create_tween()
	tween.parallel().tween_property(label, "position:y", label.position.y - 50, 1.0)
	tween.parallel().tween_property(label, "modulate:a", 0.0, 1.0)
	tween.tween_callback(label.queue_free)

func _show_heal_effect(player: int, amount: int):
	var label = Label.new()
	label.text = "+%d" % amount
	label.add_theme_font_size_override("font_size", 24)
	label.add_theme_color_override("font_color", Color(0.3, 1.0, 0.3))

	if player == 1:
		label.position = Vector2(590, 500)
	else:
		label.position = Vector2(990, 500)

	add_child(label)

	var tween = create_tween()
	tween.parallel().tween_property(label, "position:y", label.position.y - 50, 1.0)
	tween.parallel().tween_property(label, "modulate:a", 0.0, 1.0)
	tween.tween_callback(label.queue_free)

func _show_block_effect(player: int):
	var effect = ColorRect.new()
	effect.size = Vector2(60, 60)
	effect.color = Color(0.3, 0.6, 1.0, 0.6)

	if player == 1:
		effect.position = Vector2(570, 480)
	else:
		effect.position = Vector2(970, 480)

	add_child(effect)

	var tween = create_tween()
	tween.tween_property(effect, "scale", Vector2(1.5, 1.5), 0.3)
	tween.tween_property(effect, "modulate:a", 0.0, 0.2)
	tween.tween_callback(effect.queue_free)

func _show_item_activation(item_id: String, player: int):
	# Visual feedback for item activation
	pass

func _go_to_post_battle():
	# Go to post-battle results screen
	get_tree().change_scene_to_file("res://scenes/PostBattleScreen.tscn")
