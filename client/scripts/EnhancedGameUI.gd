extends Control
class_name EnhancedGameUI

# Visual Constants
const ITEM_SIZE = Vector2(90, 110)
const INVENTORY_SLOT_SIZE = Vector2(76, 76)
const SHOP_ITEM_SIZE = Vector2(240, 80)
const ANIMATION_DURATION = 0.3

# UI Components
var shop_panel: Panel
var holding_area: ScrollContainer
var inventory_panel: Panel
var inventory_grid: GridContainer
var gold_label: RichTextLabel
var round_label: Label
var health_label: Label

# Containers for items
var shop_slots: Array[Panel] = []
var holding_slots: Array[Panel] = []
var inventory_slots: Array[Panel] = []
var purchased_items_container: VBoxContainer

# Game State
var current_gold: int = 25
var current_round: int = 1
var current_health: int = 100
var shop_items: Array = []
var purchased_items: Array = []

# Visual Effects
var hover_tween: Tween
var purchase_particles: CPUParticles2D

# Item Templates (Dummy Data)
var ITEM_TEMPLATES = [
	{
		"name": "Null Pointer",
		"category": "problem",
		"rarity": "common",
		"cost": 3,
		"damage": "4-8",
		"cooldown": 2.5,
		"cpu": 3,
		"icon": "⚠️",
		"color": Color(0.9, 0.3, 0.3)
	},
	{
		"name": "Error Shield",
		"category": "defense",
		"rarity": "uncommon",
		"cost": 5,
		"block": 8,
		"icon": "🛡️",
		"color": Color(0.3, 0.5, 0.9)
	},
	{
		"name": "Memory Leak",
		"category": "problem",
		"rarity": "rare",
		"cost": 8,
		"damage": "2-4",
		"special": "Stacks damage",
		"icon": "💧",
		"color": Color(0.7, 0.3, 0.7)
	},
	{
		"name": "Load Balancer",
		"category": "infrastructure",
		"rarity": "uncommon",
		"cost": 6,
		"cpu_regen": 2,
		"icon": "⚖️",
		"color": Color(0.3, 0.8, 0.3)
	},
	{
		"name": "Redis Cache",
		"category": "infrastructure",
		"rarity": "rare",
		"cost": 9,
		"cpu_regen": 3,
		"special": "Adjacent speed +10%",
		"icon": "💾",
		"color": Color(0.5, 0.8, 0.5)
	},
	{
		"name": "SQL Injection",
		"category": "problem",
		"rarity": "epic",
		"cost": 12,
		"damage": "8-12",
		"special": "Bypass shields",
		"icon": "💉",
		"color": Color(0.8, 0.3, 0.8)
	},
	{
		"name": "Firewall",
		"category": "defense",
		"rarity": "epic",
		"cost": 14,
		"block": 12,
		"special": "Reflect damage",
		"icon": "🔥",
		"color": Color(0.9, 0.5, 0.2)
	},
	{
		"name": "Coffee",
		"category": "food",
		"rarity": "common",
		"cost": 2,
		"cpu_regen": 1,
		"icon": "☕",
		"color": Color(0.6, 0.4, 0.2)
	}
]

func _ready():
	_setup_main_ui()
	_generate_initial_shop()
	_update_displays()

	# Start with welcome animation
	_play_welcome_animation()

func _setup_main_ui():
	# Main background with gradient
	var bg_gradient = GradientTexture2D.new()
	var gradient = Gradient.new()
	gradient.colors = PackedColorArray([Color(0.05, 0.05, 0.1), Color(0.1, 0.1, 0.2)])
	bg_gradient.gradient = gradient
	bg_gradient.fill_from = Vector2(0, 0)
	bg_gradient.fill_to = Vector2(0, 1)

	var bg = TextureRect.new()
	bg.texture = bg_gradient
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(bg)

	# Create main panels
	_create_top_bar()
	_create_shop_panel()
	_create_holding_area()
	_create_inventory_panel()
	_create_action_buttons()
	_create_tooltip_system()

func _create_top_bar():
	var top_bar = Panel.new()
	top_bar.position = Vector2(0, 0)
	top_bar.size = Vector2(1280, 70)

	var bar_style = StyleBoxFlat.new()
	bar_style.bg_color = Color(0.08, 0.08, 0.12, 0.95)
	bar_style.border_color = Color(0.2, 0.2, 0.3, 1.0)
	bar_style.set_border_width(SIDE_BOTTOM, 3)
	bar_style.shadow_color = Color(0, 0, 0, 0.3)
	bar_style.shadow_size = 5
	top_bar.add_theme_stylebox_override("panel", bar_style)
	add_child(top_bar)

	# Stats with icons
	var stats_container = HBoxContainer.new()
	stats_container.position = Vector2(30, 20)
	stats_container.add_theme_constant_override("separation", 60)
	top_bar.add_child(stats_container)

	# Round
	round_label = _create_stat_label("🏆 Round %d" % current_round, Color(0.7, 0.7, 0.9))
	stats_container.add_child(round_label)

	# Gold with animation
	gold_label = RichTextLabel.new()
	gold_label.bbcode_enabled = true
	gold_label.fit_content = true
	gold_label.text = "[color=#FFD700]💰 Gold: %d[/color]" % current_gold
	gold_label.add_theme_font_size_override("normal_font_size", 24)
	stats_container.add_child(gold_label)

	# Health
	health_label = _create_stat_label("❤️ Health: %d" % current_health, Color(0.3, 0.9, 0.3))
	stats_container.add_child(health_label)

func _create_stat_label(text: String, color: Color) -> Label:
	var label = Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", 22)
	label.modulate = color
	return label

func _create_shop_panel():
	shop_panel = Panel.new()
	shop_panel.position = Vector2(20, 90)
	shop_panel.size = Vector2(320, 600)

	var panel_style = _create_panel_style(Color(0.12, 0.10, 0.15, 0.95), Color(0.8, 0.7, 0.3, 0.8))
	shop_panel.add_theme_stylebox_override("panel", panel_style)
	add_child(shop_panel)

	# Animated title
	var title = Label.new()
	title.text = "✨ SHOP ✨"
	title.position = Vector2(110, 15)
	title.add_theme_font_size_override("font_size", 28)
	title.modulate = Color(1.0, 0.9, 0.3)
	shop_panel.add_child(title)

	# Shop slots with better spacing
	var shop_container = VBoxContainer.new()
	shop_container.position = Vector2(15, 60)
	shop_container.size = Vector2(290, 520)
	shop_container.add_theme_constant_override("separation", 8)
	shop_panel.add_child(shop_container)

	for i in range(5):
		var slot = _create_enhanced_shop_slot(i)
		shop_container.add_child(slot)
		shop_slots.append(slot)

func _create_enhanced_shop_slot(index: int) -> Panel:
	var slot = Panel.new()
	slot.custom_minimum_size = Vector2(280, 96)
	slot.set_meta("slot_type", "shop")
	slot.set_meta("slot_index", index)

	var style = StyleBoxFlat.new()
	style.bg_color = Color(0.15, 0.15, 0.18, 0.9)
	style.border_color = Color(0.3, 0.3, 0.35, 1.0)
	style.set_border_width_all(2)
	style.set_corner_radius_all(8)
	slot.add_theme_stylebox_override("panel", style)

	# Hover effect
	slot.mouse_entered.connect(_on_slot_hover.bind(slot, true))
	slot.mouse_exited.connect(_on_slot_hover.bind(slot, false))

	return slot

func _create_holding_area():
	var holding_panel = Panel.new()
	holding_panel.position = Vector2(360, 90)
	holding_panel.size = Vector2(280, 600)

	var panel_style = _create_panel_style(Color(0.10, 0.12, 0.10, 0.95), Color(0.3, 0.8, 0.3, 0.6))
	holding_panel.add_theme_stylebox_override("panel", panel_style)
	add_child(holding_panel)

	# Title
	var title = Label.new()
	title.text = "📦 PURCHASED"
	title.position = Vector2(70, 15)
	title.add_theme_font_size_override("font_size", 24)
	title.modulate = Color(0.5, 1.0, 0.5)
	holding_panel.add_child(title)

	# Scrollable area for items
	holding_area = ScrollContainer.new()
	holding_area.position = Vector2(10, 60)
	holding_area.size = Vector2(260, 520)
	holding_area.set_meta("slot_type", "holding")
	holding_panel.add_child(holding_area)

	purchased_items_container = VBoxContainer.new()
	purchased_items_container.add_theme_constant_override("separation", 5)
	holding_area.add_child(purchased_items_container)

func _create_inventory_panel():
	inventory_panel = Panel.new()
	inventory_panel.position = Vector2(660, 90)
	inventory_panel.size = Vector2(600, 600)

	var panel_style = _create_panel_style(Color(0.10, 0.10, 0.15, 0.95), Color(0.3, 0.3, 0.8, 0.6))
	inventory_panel.add_theme_stylebox_override("panel", panel_style)
	add_child(inventory_panel)

	# Title
	var title = Label.new()
	title.text = "🎮 BATTLE GRID (7×9)"
	title.position = Vector2(180, 15)
	title.add_theme_font_size_override("font_size", 24)
	title.modulate = Color(0.6, 0.6, 1.0)
	inventory_panel.add_child(title)

	# Grid
	inventory_grid = GridContainer.new()
	inventory_grid.position = Vector2(25, 60)
	inventory_grid.columns = 7
	inventory_grid.add_theme_constant_override("h_separation", 3)
	inventory_grid.add_theme_constant_override("v_separation", 3)
	inventory_panel.add_child(inventory_grid)

	# Create animated grid
	for y in range(9):
		for x in range(7):
			var slot = _create_enhanced_inventory_slot(x, y)
			inventory_grid.add_child(slot)
			inventory_slots.append(slot)

			# Stagger animation
			var delay = (x + y) * 0.02
			_animate_slot_appearance(slot, delay)

func _create_enhanced_inventory_slot(x: int, y: int) -> Panel:
	var slot = Panel.new()
	slot.custom_minimum_size = INVENTORY_SLOT_SIZE
	slot.set_meta("slot_type", "inventory")
	slot.set_meta("grid_pos", Vector2i(x, y))
	slot.set_meta("occupied", false)

	var style = StyleBoxFlat.new()
	style.bg_color = Color(0.12, 0.12, 0.16, 0.7)
	style.border_color = Color(0.25, 0.25, 0.35, 0.6)
	style.set_border_width_all(1)
	style.set_corner_radius_all(6)
	slot.add_theme_stylebox_override("panel", style)

	# Grid pattern overlay
	var overlay = ColorRect.new()
	overlay.color = Color(1, 1, 1, 0.02)
	overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	overlay.mouse_filter = Control.MOUSE_FILTER_IGNORE
	slot.add_child(overlay)

	return slot

func _create_action_buttons():
	# Refresh button with icon
	var refresh_btn = _create_action_button("🔄 Refresh Shop (2g)", Vector2(30, 700))
	refresh_btn.pressed.connect(_on_refresh_shop)
	add_child(refresh_btn)

	# Battle button with glow effect
	var battle_btn = _create_action_button("⚔️ START BATTLE", Vector2(1050, 700))
	battle_btn.modulate = Color(1.2, 1.0, 1.0)
	battle_btn.pressed.connect(_on_start_battle)
	add_child(battle_btn)

	# Add pulse animation to battle button
	var pulse_tween = create_tween()
	pulse_tween.set_loops()
	pulse_tween.tween_property(battle_btn, "scale", Vector2(1.05, 1.05), 0.5)
	pulse_tween.tween_property(battle_btn, "scale", Vector2(1.0, 1.0), 0.5)

func _create_action_button(text: String, pos: Vector2) -> Button:
	var btn = Button.new()
	btn.text = text
	btn.position = pos
	btn.size = Vector2(180, 45)
	btn.add_theme_font_size_override("font_size", 16)

	var style_normal = StyleBoxFlat.new()
	style_normal.bg_color = Color(0.2, 0.25, 0.35, 0.9)
	style_normal.border_color = Color(0.4, 0.5, 0.7, 1.0)
	style_normal.set_border_width_all(2)
	style_normal.set_corner_radius_all(8)
	btn.add_theme_stylebox_override("normal", style_normal)

	var style_hover = style_normal.duplicate()
	style_hover.bg_color = Color(0.25, 0.3, 0.45, 1.0)
	style_hover.border_color = Color(0.6, 0.7, 0.9, 1.0)
	btn.add_theme_stylebox_override("hover", style_hover)

	return btn

func _create_tooltip_system():
	# Create floating tooltip that follows mouse
	var tooltip = Panel.new()
	tooltip.name = "Tooltip"
	tooltip.visible = false
	tooltip.mouse_filter = Control.MOUSE_FILTER_IGNORE
	tooltip.size = Vector2(200, 100)

	var tooltip_style = StyleBoxFlat.new()
	tooltip_style.bg_color = Color(0.1, 0.1, 0.15, 0.95)
	tooltip_style.border_color = Color(0.5, 0.5, 0.6, 1.0)
	tooltip_style.set_border_width_all(2)
	tooltip_style.set_corner_radius_all(6)
	tooltip.add_theme_stylebox_override("panel", tooltip_style)

	var tooltip_text = RichTextLabel.new()
	tooltip_text.name = "TooltipText"
	tooltip_text.bbcode_enabled = true
	tooltip_text.fit_content = true
	tooltip_text.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	tooltip.add_child(tooltip_text)

	add_child(tooltip)

func _create_panel_style(bg_color: Color, border_color: Color) -> StyleBoxFlat:
	var style = StyleBoxFlat.new()
	style.bg_color = bg_color
	style.border_color = border_color
	style.set_border_width_all(3)
	style.set_corner_radius_all(12)
	style.shadow_color = Color(0, 0, 0, 0.4)
	style.shadow_size = 8
	style.shadow_offset = Vector2(4, 4)
	return style

func _generate_initial_shop():
	for i in range(5):
		if randf() > 0.15:  # 85% chance of item
			_add_item_to_shop(i)

func _add_item_to_shop(slot_index: int):
	var slot = shop_slots[slot_index]

	# Clear slot
	for child in slot.get_children():
		child.queue_free()

	# Pick random item
	var template = ITEM_TEMPLATES[randi() % ITEM_TEMPLATES.size()]
	var item_data = template.duplicate()
	item_data["id"] = "item_" + str(randi())

	# Create visual item card
	var item_card = _create_item_card(item_data)
	slot.add_child(item_card)

	# Add buy button
	var buy_btn = _create_buy_button(item_data)
	buy_btn.position = Vector2(200, 30)
	buy_btn.pressed.connect(_on_buy_item.bind(item_data, slot_index))
	slot.add_child(buy_btn)

func _create_item_card(item_data: Dictionary) -> Panel:
	var card = Panel.new()
	card.size = Vector2(190, 80)
	card.position = Vector2(5, 8)

	var card_style = StyleBoxFlat.new()
	card_style.bg_color = item_data.get("color", Color.WHITE).darkened(0.7)
	card_style.border_color = item_data.get("color", Color.WHITE)
	card_style.set_border_width_all(2)
	card_style.set_corner_radius_all(6)
	card.add_theme_stylebox_override("panel", card_style)

	# Icon
	var icon = Label.new()
	icon.text = item_data.get("icon", "?")
	icon.position = Vector2(10, 20)
	icon.add_theme_font_size_override("font_size", 32)
	card.add_child(icon)

	# Name
	var name = Label.new()
	name.text = item_data.get("name", "Unknown")
	name.position = Vector2(55, 5)
	name.add_theme_font_size_override("font_size", 14)
	card.add_child(name)

	# Stats
	var stats_text = ""
	if item_data.has("damage"):
		stats_text = "⚔ " + item_data.damage
	elif item_data.has("block"):
		stats_text = "🛡 " + str(item_data.block)
	elif item_data.has("cpu_regen"):
		stats_text = "⚡ +" + str(item_data.cpu_regen)

	if stats_text != "":
		var stats = Label.new()
		stats.text = stats_text
		stats.position = Vector2(55, 25)
		stats.add_theme_font_size_override("font_size", 12)
		stats.modulate = Color(0.8, 0.8, 0.8)
		card.add_child(stats)

	# Special
	if item_data.has("special"):
		var special = Label.new()
		special.text = item_data.special
		special.position = Vector2(55, 45)
		special.add_theme_font_size_override("font_size", 10)
		special.modulate = Color(0.7, 0.7, 0.9)
		card.add_child(special)

	return card

func _create_buy_button(item_data: Dictionary) -> Button:
	var btn = Button.new()
	btn.text = str(item_data.cost) + "g"
	btn.size = Vector2(70, 35)
	btn.add_theme_font_size_override("font_size", 18)

	if item_data.cost > current_gold:
		btn.disabled = true
		btn.modulate = Color(0.5, 0.5, 0.5)

	return btn

func _create_draggable_item(item_data: Dictionary) -> Control:
	var item = preload("res://scripts/DraggableItem.gd").new()
	item.setup_item(item_data)
	item.dropped_on_slot.connect(_on_item_dropped_on_slot)
	return item

func _on_buy_item(item_data: Dictionary, slot_index: int):
	if current_gold >= item_data.cost:
		# Deduct gold with animation
		var old_gold = current_gold
		current_gold -= item_data.cost
		_animate_gold_change(old_gold, current_gold)

		# Create purchased item
		var item = _create_draggable_item(item_data)
		purchased_items_container.add_child(item)
		purchased_items.append(item)

		# Clear shop slot
		var slot = shop_slots[slot_index]
		for child in slot.get_children():
			child.queue_free()

		# Play purchase animation
		_play_purchase_animation(slot.global_position)

		# Add "SOLD" label
		var sold_label = Label.new()
		sold_label.text = "SOLD"
		sold_label.position = Vector2(100, 35)
		sold_label.add_theme_font_size_override("font_size", 24)
		sold_label.modulate = Color(0.5, 0.5, 0.5, 0.7)
		slot.add_child(sold_label)

func _on_item_dropped_on_slot(item: Control, slot: Panel):
	var slot_type = slot.get_meta("slot_type", "")

	if slot_type == "inventory" and not slot.get_meta("occupied", false):
		# Move to inventory
		item.get_parent().remove_child(item)
		slot.add_child(item)
		item.position = Vector2.ZERO
		item.size = INVENTORY_SLOT_SIZE
		slot.set_meta("occupied", true)

		# Visual feedback
		_play_place_animation(slot)

func _on_refresh_shop():
	if current_gold >= 2:
		var old_gold = current_gold
		current_gold -= 2
		_animate_gold_change(old_gold, current_gold)

		# Animate shop refresh
		for i in range(5):
			var slot = shop_slots[i]
			var tween = create_tween()
			tween.tween_property(slot, "modulate:a", 0.0, 0.2)
			tween.tween_callback(_add_item_to_shop.bind(i))
			tween.tween_property(slot, "modulate:a", 1.0, 0.2)

func _on_start_battle():
	# Count placed items
	var placed = 0
	for slot in inventory_slots:
		if slot.get_meta("occupied", false):
			placed += 1

	# Show battle start animation
	var battle_text = Label.new()
	battle_text.text = "⚔️ BATTLE STARTING! ⚔️\n%d items placed" % placed
	battle_text.position = Vector2(640, 360)
	battle_text.add_theme_font_size_override("font_size", 36)
	battle_text.modulate = Color(1.0, 0.8, 0.3)
	add_child(battle_text)

	var tween = create_tween()
	tween.tween_property(battle_text, "scale", Vector2(1.5, 1.5), 0.5)
	tween.parallel().tween_property(battle_text, "modulate:a", 0.0, 0.5)
	tween.tween_callback(battle_text.queue_free)

func _on_slot_hover(slot: Panel, hovering: bool):
	if hover_tween:
		hover_tween.kill()

	hover_tween = create_tween()
	if hovering:
		hover_tween.tween_property(slot, "scale", Vector2(1.02, 1.02), 0.1)
	else:
		hover_tween.tween_property(slot, "scale", Vector2(1.0, 1.0), 0.1)

func _animate_slot_appearance(slot: Panel, delay: float):
	slot.modulate.a = 0.0
	slot.scale = Vector2(0.8, 0.8)

	var tween = create_tween()
	tween.set_trans(Tween.TRANS_BACK)
	tween.set_ease(Tween.EASE_OUT)
	tween.tween_interval(delay)
	tween.parallel().tween_property(slot, "modulate:a", 1.0, 0.3)
	tween.parallel().tween_property(slot, "scale", Vector2(1.0, 1.0), 0.3)

func _animate_gold_change(from: int, to: int):
	var tween = create_tween()
	var dummy = {"value": from}
	tween.tween_property(dummy, "value", to, 0.5)
	tween.tween_method(func(val):
		gold_label.text = "[color=#FFD700]💰 Gold: %d[/color]" % int(val)
	, from, to, 0.5)

func _play_purchase_animation(pos: Vector2):
	var particles = CPUParticles2D.new()
	particles.position = pos
	particles.amount = 20
	particles.lifetime = 1.0
	particles.texture = preload("res://icon.svg") if FileAccess.file_exists("res://icon.svg") else null
	particles.emission_shape = CPUParticles2D.EMISSION_SHAPE_SPHERE
	particles.initial_velocity_min = 50
	particles.initial_velocity_max = 150
	particles.angular_velocity_min = -180
	particles.angular_velocity_max = 180
	particles.scale_amount_min = 0.1
	particles.scale_amount_max = 0.3
	particles.color = Color(1.0, 0.9, 0.3)
	particles.emitting = true
	add_child(particles)

	await get_tree().create_timer(2.0).timeout
	particles.queue_free()

func _play_place_animation(slot: Panel):
	var tween = create_tween()
	tween.set_trans(Tween.TRANS_ELASTIC)
	tween.tween_property(slot, "scale", Vector2(1.2, 1.2), 0.1)
	tween.tween_property(slot, "scale", Vector2(1.0, 1.0), 0.2)

func _play_welcome_animation():
	var welcome = Label.new()
	welcome.text = "Welcome to Sentry Autobattler!"
	welcome.position = Vector2(640, 300)
	welcome.add_theme_font_size_override("font_size", 48)
	welcome.modulate = Color(1.0, 0.9, 0.3, 0.0)
	add_child(welcome)

	var tween = create_tween()
	tween.tween_property(welcome, "modulate:a", 1.0, 0.5)
	tween.tween_interval(1.0)
	tween.tween_property(welcome, "modulate:a", 0.0, 0.5)
	tween.tween_callback(welcome.queue_free)

func _update_displays():
	gold_label.text = "[color=#FFD700]💰 Gold: %d[/color]" % current_gold
	round_label.text = "🏆 Round %d" % current_round
	health_label.text = "❤️ Health: %d" % current_health
