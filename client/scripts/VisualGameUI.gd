extends Control
class_name VisualGameUI

# Asset paths
const ITEM_ICONS = {
	"problem": preload("res://assets/sprites/items/bug_icon.png"),
	"defense": preload("res://assets/sprites/items/shield_icon.png"),
	"infrastructure": preload("res://assets/sprites/items/gear_icon.png"),
	"memory_leak": preload("res://assets/sprites/items/memory_leak.png"),
	"database": preload("res://assets/sprites/items/database.png"),
	"firewall": preload("res://assets/sprites/items/firewall.png"),
	"coffee": preload("res://assets/sprites/items/coffee.png"),
	"network": preload("res://assets/sprites/items/network.png")
}

const UI_ASSETS = {
	"panel_bg": preload("res://assets/sprites/ui/panel_bg.png"),
	"slot_empty": preload("res://assets/sprites/ui/slot_empty.png"),
	"button": preload("res://assets/sprites/ui/button.png"),
	"main_bg": preload("res://assets/sprites/backgrounds/main_bg.png")
}

# Visual Constants
const ITEM_SIZE = Vector2(80, 100)
const INVENTORY_SLOT_SIZE = Vector2(76, 76)
const SHOP_ITEM_SIZE = Vector2(240, 90)

# UI Components
var shop_panel: Panel
var holding_area: ScrollContainer
var inventory_panel: Panel
var inventory_grid: GridContainer
var gold_label: RichTextLabel
var round_label: Label
var health_label: Label

# Containers
var shop_slots: Array[Panel] = []
var inventory_slots: Array[Panel] = []
var purchased_items_container: VBoxContainer

# Game State
var current_gold: int = 30
var current_round: int = 1
var current_health: int = 100
var purchased_items: Array = []

# Item Templates with graphics
var ITEM_TEMPLATES = [
	{
		"name": "Null Pointer",
		"category": "problem",
		"icon_key": "problem",
		"rarity": "common",
		"cost": 3,
		"damage": "4-8",
		"cooldown": 2.5,
		"cpu": 3,
		"description": "Basic bug that crashes systems"
	},
	{
		"name": "Error Shield",
		"category": "defense",
		"icon_key": "defense",
		"rarity": "uncommon",
		"cost": 5,
		"block": 8,
		"description": "Monitors and blocks errors"
	},
	{
		"name": "Memory Leak",
		"category": "problem",
		"icon_key": "memory_leak",
		"rarity": "rare",
		"cost": 8,
		"damage": "2-4",
		"special": "Damage increases each turn",
		"description": "Slowly drains resources"
	},
	{
		"name": "Load Balancer",
		"category": "infrastructure",
		"icon_key": "network",
		"rarity": "uncommon",
		"cost": 6,
		"cpu_regen": 2,
		"description": "Distributes load efficiently"
	},
	{
		"name": "Redis Cache",
		"category": "infrastructure",
		"icon_key": "database",
		"rarity": "rare",
		"cost": 9,
		"cpu_regen": 3,
		"special": "Adjacent items +10% speed",
		"description": "Fast memory storage"
	},
	{
		"name": "SQL Injection",
		"category": "problem",
		"icon_key": "database",
		"rarity": "epic",
		"cost": 12,
		"damage": "8-12",
		"special": "Bypasses shields",
		"description": "Exploits database vulnerabilities"
	},
	{
		"name": "Firewall",
		"category": "defense",
		"icon_key": "firewall",
		"rarity": "epic",
		"cost": 14,
		"block": 12,
		"special": "Reflects 30% damage",
		"description": "Advanced network protection"
	},
	{
		"name": "Coffee",
		"category": "food",
		"icon_key": "coffee",
		"rarity": "common",
		"cost": 2,
		"cpu_regen": 1,
		"description": "Essential developer fuel"
	},
	{
		"name": "Server Rack",
		"category": "infrastructure",
		"icon_key": "gear",
		"rarity": "uncommon",
		"cost": 7,
		"special": "+5 max CPU",
		"description": "Increases processing capacity"
	}
]

func _ready():
	_setup_main_ui()
	_generate_initial_shop()
	_update_displays()
	_play_welcome_animation()

func _setup_main_ui():
	# Background image
	var bg = TextureRect.new()
	bg.texture = UI_ASSETS["main_bg"]
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	bg.stretch_mode = TextureRect.STRETCH_SCALE
	add_child(bg)

	# Create panels
	_create_top_bar()
	_create_shop_panel()
	_create_holding_area()
	_create_inventory_panel()
	_create_action_buttons()

func _create_top_bar():
	var top_bar = Panel.new()
	top_bar.position = Vector2(0, 0)
	top_bar.size = Vector2(1280, 70)

	var bar_style = StyleBoxFlat.new()
	bar_style.bg_color = Color(0.08, 0.08, 0.15, 0.95)
	bar_style.border_color = Color(0.3, 0.3, 0.5, 1.0)
	bar_style.set_border_width(SIDE_BOTTOM, 3)
	bar_style.shadow_color = Color(0, 0, 0, 0.5)
	bar_style.shadow_size = 5
	top_bar.add_theme_stylebox_override("panel", bar_style)
	add_child(top_bar)

	# Stats container
	var stats_container = HBoxContainer.new()
	stats_container.position = Vector2(40, 20)
	stats_container.add_theme_constant_override("separation", 80)
	top_bar.add_child(stats_container)

	# Round with icon
	var round_icon = TextureRect.new()
	round_icon.texture = ITEM_ICONS["infrastructure"]
	round_icon.custom_minimum_size = Vector2(32, 32)
	round_icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	stats_container.add_child(round_icon)

	round_label = Label.new()
	round_label.text = "Round %d" % current_round
	round_label.add_theme_font_size_override("font_size", 24)
	round_label.modulate = Color(0.8, 0.8, 1.0)
	stats_container.add_child(round_label)

	# Gold
	gold_label = RichTextLabel.new()
	gold_label.bbcode_enabled = true
	gold_label.fit_content = true
	gold_label.text = "[color=#FFD700]Gold: %d[/color]" % current_gold
	gold_label.add_theme_font_size_override("normal_font_size", 24)
	stats_container.add_child(gold_label)

	# Health with shield icon
	var health_icon = TextureRect.new()
	health_icon.texture = ITEM_ICONS["defense"]
	health_icon.custom_minimum_size = Vector2(32, 32)
	health_icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	stats_container.add_child(health_icon)

	health_label = Label.new()
	health_label.text = "Health: %d" % current_health
	health_label.add_theme_font_size_override("font_size", 24)
	health_label.modulate = Color(0.3, 1.0, 0.3)
	stats_container.add_child(health_label)

func _create_shop_panel():
	shop_panel = Panel.new()
	shop_panel.position = Vector2(20, 90)
	shop_panel.size = Vector2(340, 600)

	# Use custom panel texture
	var panel_style = StyleBoxFlat.new()
	panel_style.bg_color = Color(0.1, 0.1, 0.15, 0.9)
	panel_style.border_color = Color(0.4, 0.4, 0.6, 1.0)
	panel_style.set_border_width_all(3)
	panel_style.set_corner_radius_all(12)
	shop_panel.add_theme_stylebox_override("panel", panel_style)
	add_child(shop_panel)

	# Title with icon
	var title_container = HBoxContainer.new()
	title_container.position = Vector2(100, 15)
	shop_panel.add_child(title_container)

	var shop_icon = TextureRect.new()
	shop_icon.texture = ITEM_ICONS["database"]
	shop_icon.custom_minimum_size = Vector2(32, 32)
	title_container.add_child(shop_icon)

	var title = Label.new()
	title.text = " SHOP"
	title.add_theme_font_size_override("font_size", 28)
	title.modulate = Color(1.0, 0.9, 0.3)
	title_container.add_child(title)

	# Shop slots
	var shop_container = VBoxContainer.new()
	shop_container.position = Vector2(20, 65)
	shop_container.size = Vector2(300, 520)
	shop_container.add_theme_constant_override("separation", 10)
	shop_panel.add_child(shop_container)

	for i in range(5):
		var slot = _create_shop_slot(i)
		shop_container.add_child(slot)
		shop_slots.append(slot)

func _create_shop_slot(index: int) -> Panel:
	var slot = Panel.new()
	slot.custom_minimum_size = Vector2(290, 100)
	slot.set_meta("slot_type", "shop")
	slot.set_meta("slot_index", index)

	# Use slot background
	var slot_bg = TextureRect.new()
	slot_bg.texture = UI_ASSETS["slot_empty"]
	slot_bg.stretch_mode = TextureRect.STRETCH_SCALE
	slot_bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	slot_bg.modulate = Color(1.0, 1.0, 1.0, 0.3)
	slot.add_child(slot_bg)

	var style = StyleBoxFlat.new()
	style.bg_color = Color(0.12, 0.12, 0.16, 0.7)
	style.border_color = Color(0.3, 0.3, 0.4, 0.8)
	style.set_border_width_all(2)
	style.set_corner_radius_all(8)
	slot.add_theme_stylebox_override("panel", style)

	return slot

func _create_holding_area():
	var holding_panel = Panel.new()
	holding_panel.position = Vector2(380, 90)
	holding_panel.size = Vector2(280, 600)

	var panel_style = StyleBoxFlat.new()
	panel_style.bg_color = Color(0.1, 0.12, 0.1, 0.9)
	panel_style.border_color = Color(0.3, 0.5, 0.3, 1.0)
	panel_style.set_border_width_all(3)
	panel_style.set_corner_radius_all(12)
	holding_panel.add_theme_stylebox_override("panel", panel_style)
	add_child(holding_panel)

	# Title with icon
	var title_container = HBoxContainer.new()
	title_container.position = Vector2(60, 15)
	holding_panel.add_child(title_container)

	var hold_icon = TextureRect.new()
	hold_icon.texture = ITEM_ICONS["infrastructure"]
	hold_icon.custom_minimum_size = Vector2(32, 32)
	title_container.add_child(hold_icon)

	var title = Label.new()
	title.text = " INVENTORY"
	title.add_theme_font_size_override("font_size", 24)
	title.modulate = Color(0.5, 1.0, 0.5)
	title_container.add_child(title)

	# Scrollable area
	holding_area = ScrollContainer.new()
	holding_area.position = Vector2(10, 65)
	holding_area.size = Vector2(260, 520)
	holding_area.set_meta("slot_type", "holding")
	holding_panel.add_child(holding_area)

	purchased_items_container = VBoxContainer.new()
	purchased_items_container.add_theme_constant_override("separation", 10)
	holding_area.add_child(purchased_items_container)

func _create_inventory_panel():
	inventory_panel = Panel.new()
	inventory_panel.position = Vector2(680, 90)
	inventory_panel.size = Vector2(580, 600)

	var panel_style = StyleBoxFlat.new()
	panel_style.bg_color = Color(0.1, 0.1, 0.15, 0.9)
	panel_style.border_color = Color(0.3, 0.3, 0.6, 1.0)
	panel_style.set_border_width_all(3)
	panel_style.set_corner_radius_all(12)
	inventory_panel.add_theme_stylebox_override("panel", panel_style)
	add_child(inventory_panel)

	# Title
	var title_container = HBoxContainer.new()
	title_container.position = Vector2(180, 15)
	inventory_panel.add_child(title_container)

	var grid_icon = TextureRect.new()
	grid_icon.texture = ITEM_ICONS["network"]
	grid_icon.custom_minimum_size = Vector2(32, 32)
	title_container.add_child(grid_icon)

	var title = Label.new()
	title.text = " BATTLE GRID"
	title.add_theme_font_size_override("font_size", 24)
	title.modulate = Color(0.6, 0.6, 1.0)
	title_container.add_child(title)

	# Grid
	inventory_grid = GridContainer.new()
	inventory_grid.position = Vector2(20, 65)
	inventory_grid.columns = 7
	inventory_grid.add_theme_constant_override("h_separation", 3)
	inventory_grid.add_theme_constant_override("v_separation", 3)
	inventory_panel.add_child(inventory_grid)

	# Create grid with slot graphics
	for y in range(9):
		for x in range(7):
			var slot = _create_inventory_slot(x, y)
			inventory_grid.add_child(slot)
			inventory_slots.append(slot)

func _create_inventory_slot(x: int, y: int) -> Panel:
	var slot = Panel.new()
	slot.custom_minimum_size = INVENTORY_SLOT_SIZE
	slot.set_meta("slot_type", "inventory")
	slot.set_meta("grid_pos", Vector2i(x, y))
	slot.set_meta("occupied", false)

	# Add slot background texture
	var slot_bg = TextureRect.new()
	slot_bg.texture = UI_ASSETS["slot_empty"]
	slot_bg.stretch_mode = TextureRect.STRETCH_SCALE
	slot_bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	slot_bg.modulate = Color(0.6, 0.6, 0.8, 0.4)
	slot.add_child(slot_bg)

	var style = StyleBoxFlat.new()
	style.bg_color = Color(0.0, 0.0, 0.0, 0.0)
	slot.add_theme_stylebox_override("panel", style)

	return slot

func _create_action_buttons():
	# Refresh button with custom style
	var refresh_btn = Button.new()
	refresh_btn.text = "  Refresh Shop (2g)"
	refresh_btn.position = Vector2(40, 700)
	refresh_btn.size = Vector2(200, 45)
	refresh_btn.add_theme_font_size_override("font_size", 18)

	var refresh_icon = TextureRect.new()
	refresh_icon.texture = ITEM_ICONS["network"]
	refresh_icon.position = Vector2(10, 7)
	refresh_icon.size = Vector2(30, 30)
	refresh_btn.add_child(refresh_icon)

	refresh_btn.pressed.connect(_on_refresh_shop)
	add_child(refresh_btn)

	# Battle button
	var battle_btn = Button.new()
	battle_btn.text = "  START BATTLE"
	battle_btn.position = Vector2(1040, 700)
	battle_btn.size = Vector2(200, 45)
	battle_btn.add_theme_font_size_override("font_size", 18)

	var battle_icon = TextureRect.new()
	battle_icon.texture = ITEM_ICONS["problem"]
	battle_icon.position = Vector2(10, 7)
	battle_icon.size = Vector2(30, 30)
	battle_btn.add_child(battle_icon)

	battle_btn.pressed.connect(_on_start_battle)
	add_child(battle_btn)

func _generate_initial_shop():
	for i in range(5):
		if randf() > 0.1:
			_add_item_to_shop(i)

func _add_item_to_shop(slot_index: int):
	var slot = shop_slots[slot_index]

	# Clear slot
	for child in slot.get_children():
		if not child is TextureRect:  # Keep background
			child.queue_free()

	# Pick random item
	var template = ITEM_TEMPLATES[randi() % ITEM_TEMPLATES.size()]
	var item_data = template.duplicate()
	item_data["id"] = "item_" + str(randi())

	# Create item display
	var item_container = Control.new()
	item_container.position = Vector2(10, 10)
	item_container.size = Vector2(270, 80)
	slot.add_child(item_container)

	# Item icon
	var icon = TextureRect.new()
	icon.texture = ITEM_ICONS[item_data.get("icon_key", "problem")]
	icon.position = Vector2(0, 10)
	icon.size = Vector2(60, 60)
	icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	item_container.add_child(icon)

	# Item name
	var name_label = Label.new()
	name_label.text = item_data.get("name", "Unknown")
	name_label.position = Vector2(70, 5)
	name_label.add_theme_font_size_override("font_size", 16)
	name_label.modulate = _get_rarity_color(item_data.get("rarity", "common"))
	item_container.add_child(name_label)

	# Item stats
	var stats_text = ""
	if item_data.has("damage"):
		stats_text = "DMG: " + item_data.damage
	elif item_data.has("block"):
		stats_text = "Block: " + str(item_data.block)
	elif item_data.has("cpu_regen"):
		stats_text = "CPU: +" + str(item_data.cpu_regen)

	if stats_text != "":
		var stats_label = Label.new()
		stats_label.text = stats_text
		stats_label.position = Vector2(70, 28)
		stats_label.add_theme_font_size_override("font_size", 13)
		stats_label.modulate = Color(0.8, 0.8, 0.8)
		item_container.add_child(stats_label)

	# Description
	var desc_label = Label.new()
	desc_label.text = item_data.get("description", "")
	desc_label.position = Vector2(70, 48)
	desc_label.add_theme_font_size_override("font_size", 10)
	desc_label.modulate = Color(0.6, 0.6, 0.7)
	item_container.add_child(desc_label)

	# Buy button
	var buy_btn = _create_buy_button(item_data)
	buy_btn.position = Vector2(210, 25)
	buy_btn.pressed.connect(_on_buy_item.bind(item_data, slot_index))
	slot.add_child(buy_btn)

func _create_buy_button(item_data: Dictionary) -> Button:
	var btn = Button.new()
	btn.text = "%dg" % item_data.cost
	btn.size = Vector2(70, 35)
	btn.add_theme_font_size_override("font_size", 18)

	if item_data.cost > current_gold:
		btn.disabled = true
		btn.modulate = Color(0.5, 0.5, 0.5)
	else:
		btn.modulate = Color(1.0, 0.9, 0.3)

	return btn

func _create_draggable_item(item_data: Dictionary) -> Panel:
	var item = Panel.new()
	item.custom_minimum_size = Vector2(250, 80)
	item.gui_input.connect(_on_item_input.bind(item, item_data))

	var style = StyleBoxFlat.new()
	style.bg_color = Color(0.15, 0.15, 0.2, 0.95)
	style.border_color = _get_rarity_color(item_data.get("rarity", "common"))
	style.set_border_width_all(2)
	style.set_corner_radius_all(6)
	item.add_theme_stylebox_override("panel", style)

	# Icon
	var icon = TextureRect.new()
	icon.texture = ITEM_ICONS[item_data.get("icon_key", "problem")]
	icon.position = Vector2(5, 10)
	icon.size = Vector2(60, 60)
	icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	item.add_child(icon)

	# Name
	var name = Label.new()
	name.text = item_data.get("name", "Unknown")
	name.position = Vector2(70, 10)
	name.add_theme_font_size_override("font_size", 14)
	name.mouse_filter = Control.MOUSE_FILTER_IGNORE
	item.add_child(name)

	# Stats
	var stats = Label.new()
	if item_data.has("damage"):
		stats.text = "DMG: " + item_data.damage
	elif item_data.has("block"):
		stats.text = "Block: " + str(item_data.block)
	stats.position = Vector2(70, 35)
	stats.add_theme_font_size_override("font_size", 12)
	stats.modulate = Color(0.8, 0.8, 0.8)
	stats.mouse_filter = Control.MOUSE_FILTER_IGNORE
	item.add_child(stats)

	item.set_meta("item_data", item_data)
	item.set_meta("draggable", true)

	return item

var dragging_item: Panel = null
var drag_offset: Vector2

func _on_item_input(event: InputEvent, item: Panel, item_data: Dictionary):
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_LEFT:
			if event.pressed:
				dragging_item = item
				drag_offset = item.global_position - event.global_position
				item.modulate.a = 0.7
			else:
				if dragging_item:
					_drop_item()
					dragging_item.modulate.a = 1.0
					dragging_item = null

func _process(_delta):
	if dragging_item:
		dragging_item.global_position = get_global_mouse_position() + drag_offset

func _drop_item():
	if not dragging_item:
		return

	# Check if dropped on inventory slot
	var mouse_pos = get_global_mouse_position()
	for slot in inventory_slots:
		var slot_rect = Rect2(slot.global_position, slot.size)
		if slot_rect.has_point(mouse_pos) and not slot.get_meta("occupied", false):
			# Place item in slot
			dragging_item.get_parent().remove_child(dragging_item)
			slot.add_child(dragging_item)
			dragging_item.position = Vector2.ZERO
			dragging_item.size = INVENTORY_SLOT_SIZE
			slot.set_meta("occupied", true)

			# Update item display for grid
			for child in dragging_item.get_children():
				if child is Label:
					child.add_theme_font_size_override("font_size", 10)
				elif child is TextureRect:
					child.size = Vector2(40, 40)

			return

func _on_buy_item(item_data: Dictionary, slot_index: int):
	if current_gold >= item_data.cost:
		current_gold -= item_data.cost
		_update_displays()

		# Create draggable item
		var item = _create_draggable_item(item_data)
		purchased_items_container.add_child(item)
		purchased_items.append(item)

		# Clear shop slot
		var slot = shop_slots[slot_index]
		for child in slot.get_children():
			if not child is TextureRect:
				child.queue_free()

		# Add sold label
		var sold = Label.new()
		sold.text = "SOLD"
		sold.position = Vector2(110, 35)
		sold.add_theme_font_size_override("font_size", 24)
		sold.modulate = Color(0.5, 0.5, 0.5, 0.5)
		slot.add_child(sold)

func _on_refresh_shop():
	if current_gold >= 2:
		current_gold -= 2
		_update_displays()

		for i in range(5):
			_add_item_to_shop(i)

func _on_start_battle():
	var placed = 0
	for slot in inventory_slots:
		if slot.get_meta("occupied", false):
			placed += 1

	print("Starting battle with %d items!" % placed)

func _get_rarity_color(rarity: String) -> Color:
	match rarity:
		"common": return Color(0.7, 0.7, 0.7)
		"uncommon": return Color(0.3, 0.8, 0.3)
		"rare": return Color(0.3, 0.5, 1.0)
		"epic": return Color(0.7, 0.3, 0.9)
		"legendary": return Color(1.0, 0.6, 0.1)
		_: return Color.WHITE

func _play_welcome_animation():
	var welcome = Label.new()
	welcome.text = "Welcome to Sentry Autobattler!"
	welcome.position = Vector2(400, 300)
	welcome.size = Vector2(480, 60)
	welcome.add_theme_font_size_override("font_size", 42)
	welcome.modulate = Color(1.0, 0.9, 0.3, 0.0)
	welcome.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	add_child(welcome)

	var tween = create_tween()
	tween.tween_property(welcome, "modulate:a", 1.0, 0.5)
	tween.tween_interval(1.5)
	tween.tween_property(welcome, "modulate:a", 0.0, 0.5)
	tween.tween_callback(welcome.queue_free)

func _update_displays():
	gold_label.text = "[color=#FFD700]Gold: %d[/color]" % current_gold
	round_label.text = "Round %d" % current_round
	health_label.text = "Health: %d" % current_health
