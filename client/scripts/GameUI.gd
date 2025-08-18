extends Control
class_name GameUI

# UI Components
@onready var shop_panel: Panel = Panel.new()
@onready var holding_area: Panel = Panel.new()
@onready var inventory_grid: GridContainer = GridContainer.new()
@onready var gold_label: Label = Label.new()
@onready var round_label: Label = Label.new()
@onready var health_label: Label = Label.new()

# Game State
var current_gold: int = 20
var current_round: int = 1
var current_health: int = 100
var shop_items: Array = []
var held_items: Array = []
var inventory_slots: Array = []

# Dummy Data
var DUMMY_ITEMS = [
	{
		"id": "item_1",
		"name": "Null Pointer",
		"category": "problem",
		"rarity": "common",
		"cost": 3,
		"min_damage": 4,
		"max_damage": 8,
		"cpu_cost": 3,
		"cooldown": 2.5,
		"tier": 1
	},
	{
		"id": "item_2",
		"name": "Error Shield",
		"category": "defense",
		"rarity": "uncommon",
		"cost": 5,
		"min_damage": 0,
		"max_damage": 0,
		"cpu_cost": 2,
		"cooldown": 0,
		"tier": 1
	},
	{
		"id": "item_3",
		"name": "Memory Leak",
		"category": "problem",
		"rarity": "rare",
		"cost": 8,
		"min_damage": 2,
		"max_damage": 4,
		"cpu_cost": 2,
		"cooldown": 3.0,
		"tier": 2
	},
	{
		"id": "item_4",
		"name": "Load Balancer",
		"category": "infrastructure",
		"rarity": "uncommon",
		"cost": 6,
		"min_damage": 0,
		"max_damage": 0,
		"cpu_cost": 0,
		"cooldown": 0,
		"tier": 1
	},
	{
		"id": "item_5",
		"name": "Redis Cache",
		"category": "infrastructure",
		"rarity": "rare",
		"cost": 9,
		"min_damage": 0,
		"max_damage": 0,
		"cpu_cost": 0,
		"cooldown": 0,
		"tier": 2
	}
]

func _ready():
	size = Vector2(1280, 720)
	_setup_ui()
	_generate_shop()
	_update_ui()

func _setup_ui():
	# Background
	var bg = ColorRect.new()
	bg.color = Color(0.1, 0.1, 0.15, 1.0)
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(bg)

	# Top Bar
	var top_bar = Panel.new()
	top_bar.position = Vector2(0, 0)
	top_bar.size = Vector2(1280, 60)
	var top_style = StyleBoxFlat.new()
	top_style.bg_color = Color(0.15, 0.15, 0.2, 1.0)
	top_style.border_color = Color(0.3, 0.3, 0.4, 1.0)
	top_style.set_border_width_all(2)
	top_bar.add_theme_stylebox_override("panel", top_style)
	add_child(top_bar)

	# Stats container
	var stats_container = HBoxContainer.new()
	stats_container.position = Vector2(20, 15)
	stats_container.size = Vector2(1240, 30)
	stats_container.add_theme_constant_override("separation", 50)
	top_bar.add_child(stats_container)

	# Round label
	round_label.text = "Round: 1"
	round_label.add_theme_font_size_override("font_size", 20)
	stats_container.add_child(round_label)

	# Gold label
	gold_label.text = "Gold: 20"
	gold_label.add_theme_font_size_override("font_size", 20)
	gold_label.modulate = Color(1.0, 0.9, 0.3)
	stats_container.add_child(gold_label)

	# Health label
	health_label.text = "Health: 100"
	health_label.add_theme_font_size_override("font_size", 20)
	health_label.modulate = Color(0.3, 1.0, 0.3)
	stats_container.add_child(health_label)

	# Shop Panel (Left side)
	_setup_shop_panel()

	# Holding Area (Middle)
	_setup_holding_area()

	# Inventory Grid (Right side)
	_setup_inventory_grid()

	# Instructions
	var instructions = Label.new()
	instructions.text = "Buy items from shop → Drag to holding area → Arrange in inventory grid"
	instructions.position = Vector2(400, 680)
	instructions.add_theme_font_size_override("font_size", 14)
	instructions.modulate = Color(0.7, 0.7, 0.8)
	add_child(instructions)

	# Buttons
	_setup_buttons()

func _setup_shop_panel():
	shop_panel.position = Vector2(20, 80)
	shop_panel.size = Vector2(300, 580)

	var style = StyleBoxFlat.new()
	style.bg_color = Color(0.15, 0.15, 0.2, 0.95)
	style.border_color = Color(0.3, 0.3, 0.4, 1.0)
	style.set_border_width_all(2)
	style.set_corner_radius_all(8)
	shop_panel.add_theme_stylebox_override("panel", style)
	add_child(shop_panel)

	# Shop title
	var title = Label.new()
	title.text = "SHOP"
	title.position = Vector2(120, 10)
	title.add_theme_font_size_override("font_size", 24)
	shop_panel.add_child(title)

	# Shop slots container
	var shop_container = VBoxContainer.new()
	shop_container.position = Vector2(10, 50)
	shop_container.size = Vector2(280, 500)
	shop_container.add_theme_constant_override("separation", 10)
	shop_panel.add_child(shop_container)

	# Create 5 shop slots
	for i in range(5):
		var slot = _create_shop_slot(i)
		shop_container.add_child(slot)

func _create_shop_slot(index: int) -> Panel:
	var slot = Panel.new()
	slot.custom_minimum_size = Vector2(260, 90)
	slot.set_meta("slot_type", "shop")
	slot.set_meta("slot_index", index)

	var style = StyleBoxFlat.new()
	style.bg_color = Color(0.2, 0.2, 0.25, 0.9)
	style.border_color = Color(0.4, 0.4, 0.5, 1.0)
	style.set_border_width_all(2)
	style.set_corner_radius_all(6)
	slot.add_theme_stylebox_override("panel", style)

	return slot

func _setup_holding_area():
	holding_area.position = Vector2(340, 80)
	holding_area.size = Vector2(300, 580)

	var style = StyleBoxFlat.new()
	style.bg_color = Color(0.12, 0.15, 0.12, 0.95)
	style.border_color = Color(0.3, 0.4, 0.3, 1.0)
	style.set_border_width_all(2)
	style.set_corner_radius_all(8)
	holding_area.add_theme_stylebox_override("panel", style)
	holding_area.set_meta("slot_type", "holding")
	add_child(holding_area)

	# Title
	var title = Label.new()
	title.text = "PURCHASED ITEMS"
	title.position = Vector2(70, 10)
	title.add_theme_font_size_override("font_size", 18)
	holding_area.add_child(title)

	# Info text
	var info = Label.new()
	info.text = "Drag items here after purchase\nThen arrange in inventory →"
	info.position = Vector2(20, 250)
	info.add_theme_font_size_override("font_size", 12)
	info.modulate = Color(0.6, 0.6, 0.6)
	info.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	holding_area.add_child(info)

func _setup_inventory_grid():
	var inventory_panel = Panel.new()
	inventory_panel.position = Vector2(660, 80)
	inventory_panel.size = Vector2(600, 580)

	var panel_style = StyleBoxFlat.new()
	panel_style.bg_color = Color(0.12, 0.12, 0.18, 0.95)
	panel_style.border_color = Color(0.3, 0.3, 0.5, 1.0)
	panel_style.set_border_width_all(2)
	panel_style.set_corner_radius_all(8)
	inventory_panel.add_theme_stylebox_override("panel", panel_style)
	add_child(inventory_panel)

	# Title
	var title = Label.new()
	title.text = "INVENTORY GRID (7x9)"
	title.position = Vector2(200, 10)
	title.add_theme_font_size_override("font_size", 20)
	inventory_panel.add_child(title)

	# Grid container
	inventory_grid.position = Vector2(20, 50)
	inventory_grid.size = Vector2(560, 504)
	inventory_grid.columns = 7
	inventory_grid.add_theme_constant_override("h_separation", 2)
	inventory_grid.add_theme_constant_override("v_separation", 2)
	inventory_panel.add_child(inventory_grid)

	# Create 7x9 grid slots
	for y in range(9):
		for x in range(7):
			var slot = _create_inventory_slot(x, y)
			inventory_grid.add_child(slot)
			inventory_slots.append(slot)

func _create_inventory_slot(x: int, y: int) -> Panel:
	var slot = Panel.new()
	slot.custom_minimum_size = Vector2(76, 52)
	slot.set_meta("slot_type", "inventory")
	slot.set_meta("grid_pos", Vector2i(x, y))
	slot.set_meta("slot_size", Vector2(76, 52))

	var style = StyleBoxFlat.new()
	style.bg_color = Color(0.18, 0.18, 0.22, 0.8)
	style.border_color = Color(0.35, 0.35, 0.4, 0.8)
	style.set_border_width_all(1)
	style.set_corner_radius_all(4)
	slot.add_theme_stylebox_override("panel", style)

	# Add coordinate label for debugging
	var coord_label = Label.new()
	coord_label.text = "%d,%d" % [x, y]
	coord_label.add_theme_font_size_override("font_size", 8)
	coord_label.modulate = Color(0.4, 0.4, 0.4, 0.5)
	coord_label.position = Vector2(2, 2)
	slot.add_child(coord_label)

	return slot

func _setup_buttons():
	# Refresh Shop Button
	var refresh_btn = Button.new()
	refresh_btn.text = "Refresh Shop (2 Gold)"
	refresh_btn.position = Vector2(20, 670)
	refresh_btn.size = Vector2(150, 40)
	refresh_btn.pressed.connect(_on_refresh_pressed)
	add_child(refresh_btn)

	# Start Battle Button
	var battle_btn = Button.new()
	battle_btn.text = "Start Battle"
	battle_btn.position = Vector2(1100, 670)
	battle_btn.size = Vector2(150, 40)
	battle_btn.pressed.connect(_on_battle_pressed)
	add_child(battle_btn)

func _generate_shop():
	shop_items.clear()

	# Get shop slots
	var shop_container = shop_panel.get_child(1)  # VBoxContainer

	# Randomly select 5 items (can be duplicates)
	for i in range(5):
		if randf() > 0.2:  # 80% chance of item
			var item_template = DUMMY_ITEMS[randi() % DUMMY_ITEMS.size()]
			var item_data = item_template.duplicate()
			item_data["id"] = "shop_" + str(i) + "_" + str(randi())

			# Create visual item
			var item = preload("res://scripts/DraggableItem.gd").new()
			item.setup_item(item_data)

			# Connect signals
			item.dropped_on_slot.connect(_on_item_dropped)

			# Place in shop slot
			var slot = shop_container.get_child(i)
			_clear_slot(slot)
			slot.add_child(item)

			# Add buy button
			var buy_btn = Button.new()
			buy_btn.text = "Buy (%dg)" % item_data.cost
			buy_btn.position = Vector2(180, 30)
			buy_btn.size = Vector2(70, 30)
			buy_btn.pressed.connect(_on_buy_pressed.bind(item, item_data))
			slot.add_child(buy_btn)

			shop_items.append(item_data)

func _on_buy_pressed(item: DraggableItem, item_data: Dictionary):
	if current_gold >= item_data.cost:
		current_gold -= item_data.cost
		_update_ui()

		# Move item to holding area
		item.get_parent().remove_child(item)
		holding_area.add_child(item)

		# Position in holding area
		var y_offset = 50 + (held_items.size() * 100)
		item.position = Vector2(10, y_offset)

		held_items.append(item)

		# Remove buy button
		for child in item.get_parent().get_children():
			if child is Button and child != item:
				child.queue_free()

		print("Bought: ", item_data.name)

func _on_item_dropped(item: DraggableItem, slot: Control):
	var slot_type = slot.get_meta("slot_type", "")

	match slot_type:
		"inventory":
			# Place in inventory slot
			item.move_to_slot(slot)
			print("Placed in inventory at: ", slot.get_meta("grid_pos"))
		"holding":
			# Return to holding area
			item.move_to_slot(holding_area)
			var y_offset = 50 + (held_items.find(item) * 100)
			item.position = Vector2(10, y_offset)
		"shop":
			# Can't drop back in shop
			item.return_to_original()

func _clear_slot(slot: Control):
	for child in slot.get_children():
		if child.name != "CoordLabel":  # Keep coordinate labels
			child.queue_free()

func _on_refresh_pressed():
	if current_gold >= 2:
		current_gold -= 2
		_update_ui()
		_generate_shop()
		print("Shop refreshed!")

func _on_battle_pressed():
	# Count items in inventory
	var placed_items = 0
	for slot in inventory_slots:
		for child in slot.get_children():
			if child is DraggableItem:
				placed_items += 1

	print("Starting battle with ", placed_items, " items placed!")

	# Simulate battle result
	if randf() > 0.5:
		print("Victory! +5 gold")
		current_gold += 5
		current_round += 1
	else:
		print("Defeat! -10 health")
		current_health -= 10

	_update_ui()

func _update_ui():
	gold_label.text = "Gold: " + str(current_gold)
	round_label.text = "Round: " + str(current_round)
	health_label.text = "Health: " + str(current_health)
