extends Control
class_name SimpleTestUI

# Game state
var current_gold: int = 30
var current_round: int = 1
var current_health: int = 100
var shop_items: Array = []
var inventory_items: Array = []

func _ready():
	print("SimpleTestUI starting...")
	_setup_ui()
	_generate_dummy_shop()

func _setup_ui():
	# Background
	var bg = ColorRect.new()
	bg.color = Color(0.1, 0.1, 0.15, 1.0)
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(bg)

	# Title
	var title = Label.new()
	title.text = "Sentry Autobattler - Test UI"
	title.position = Vector2(500, 20)
	title.add_theme_font_size_override("font_size", 32)
	add_child(title)

	# Stats
	var stats = Label.new()
	stats.text = "Gold: %d | Round: %d | Health: %d" % [current_gold, current_round, current_health]
	stats.position = Vector2(50, 80)
	stats.add_theme_font_size_override("font_size", 20)
	add_child(stats)

	# Shop area
	var shop_label = Label.new()
	shop_label.text = "=== SHOP ==="
	shop_label.position = Vector2(50, 150)
	shop_label.add_theme_font_size_override("font_size", 24)
	add_child(shop_label)

	# Inventory area
	var inv_label = Label.new()
	inv_label.text = "=== INVENTORY (Drag items here) ==="
	inv_label.position = Vector2(650, 150)
	inv_label.add_theme_font_size_override("font_size", 24)
	add_child(inv_label)

	# Create shop panel
	var shop_panel = Panel.new()
	shop_panel.position = Vector2(50, 200)
	shop_panel.size = Vector2(500, 400)
	var shop_style = StyleBoxFlat.new()
	shop_style.bg_color = Color(0.15, 0.15, 0.2, 0.9)
	shop_style.border_color = Color(0.4, 0.4, 0.5, 1.0)
	shop_style.set_border_width_all(2)
	shop_panel.add_theme_stylebox_override("panel", shop_style)
	add_child(shop_panel)

	# Create inventory panel
	var inv_panel = Panel.new()
	inv_panel.position = Vector2(650, 200)
	inv_panel.size = Vector2(500, 400)
	inv_panel.set_meta("drop_zone", true)
	var inv_style = StyleBoxFlat.new()
	inv_style.bg_color = Color(0.15, 0.2, 0.15, 0.9)
	inv_style.border_color = Color(0.4, 0.5, 0.4, 1.0)
	inv_style.set_border_width_all(2)
	inv_panel.add_theme_stylebox_override("panel", inv_style)
	add_child(inv_panel)

	# Instructions
	var instructions = Label.new()
	instructions.text = "Buy items from shop -> Drag to inventory -> Start battle"
	instructions.position = Vector2(400, 650)
	instructions.add_theme_font_size_override("font_size", 16)
	instructions.modulate = Color(0.7, 0.7, 0.8)
	add_child(instructions)

	# Buttons
	var refresh_btn = Button.new()
	refresh_btn.text = "Refresh Shop (2g)"
	refresh_btn.position = Vector2(50, 620)
	refresh_btn.size = Vector2(150, 40)
	refresh_btn.pressed.connect(_on_refresh_shop)
	add_child(refresh_btn)

	var battle_btn = Button.new()
	battle_btn.text = "Start Battle"
	battle_btn.position = Vector2(1000, 620)
	battle_btn.size = Vector2(150, 40)
	battle_btn.pressed.connect(_on_start_battle)
	add_child(battle_btn)

	print("UI setup complete")

func _generate_dummy_shop():
	shop_items.clear()

	var shop_container = get_node_or_null("Panel")
	if not shop_container:
		shop_container = get_children()[3] # Shop panel

	# Clear existing items
	for child in shop_container.get_children():
		child.queue_free()

	# Generate 5 items
	var item_names = ["Null Pointer", "Memory Leak", "Error Shield", "Load Balancer", "Coffee"]
	var item_costs = [3, 5, 4, 6, 2]

	for i in range(5):
		var item_container = Control.new()
		item_container.position = Vector2(10, 10 + i * 75)
		item_container.size = Vector2(480, 70)
		shop_container.add_child(item_container)

		# Item background
		var item_bg = Panel.new()
		item_bg.size = Vector2(480, 65)
		var item_style = StyleBoxFlat.new()
		item_style.bg_color = Color(0.2, 0.2, 0.25, 0.8)
		item_style.border_color = Color(0.5, 0.5, 0.6, 1.0)
		item_style.set_border_width_all(1)
		item_bg.add_theme_stylebox_override("panel", item_style)
		item_container.add_child(item_bg)

		# Item name
		var name_label = Label.new()
		name_label.text = item_names[i]
		name_label.position = Vector2(10, 10)
		name_label.add_theme_font_size_override("font_size", 18)
		item_container.add_child(name_label)

		# Item cost
		var cost_label = Label.new()
		cost_label.text = "Cost: %d gold" % item_costs[i]
		cost_label.position = Vector2(10, 35)
		cost_label.add_theme_font_size_override("font_size", 14)
		cost_label.modulate = Color(1.0, 0.9, 0.3)
		item_container.add_child(cost_label)

		# Buy button
		var buy_btn = Button.new()
		buy_btn.text = "Buy"
		buy_btn.position = Vector2(400, 15)
		buy_btn.size = Vector2(70, 35)
		buy_btn.set_meta("item_name", item_names[i])
		buy_btn.set_meta("item_cost", item_costs[i])
		buy_btn.pressed.connect(_on_buy_item.bind(item_names[i], item_costs[i], item_container))
		item_container.add_child(buy_btn)

		shop_items.append({
			"name": item_names[i],
			"cost": item_costs[i],
			"container": item_container
		})

	print("Shop generated with %d items" % shop_items.size())

func _on_buy_item(item_name: String, cost: int, container: Control):
	if current_gold >= cost:
		current_gold -= cost
		print("Bought: %s for %d gold" % [item_name, cost])

		# Update stats display
		get_child(2).text = "Gold: %d | Round: %d | Health: %d" % [current_gold, current_round, current_health]

		# Create draggable item
		var item = _create_draggable_item(item_name)
		var inv_panel = get_children()[4] # Inventory panel
		inv_panel.add_child(item)
		inventory_items.append(item)

		# Disable buy button
		for child in container.get_children():
			if child is Button:
				child.disabled = true
				child.text = "Sold"
	else:
		print("Not enough gold!")

func _create_draggable_item(item_name: String) -> Panel:
	var item = Panel.new()
	item.size = Vector2(120, 60)
	item.position = Vector2(10 + (inventory_items.size() * 130), 10)

	var style = StyleBoxFlat.new()
	style.bg_color = Color(0.3, 0.3, 0.4, 0.9)
	style.border_color = Color(0.6, 0.6, 0.8, 1.0)
	style.set_border_width_all(2)
	item.add_theme_stylebox_override("panel", style)

	var label = Label.new()
	label.text = item_name
	label.position = Vector2(10, 20)
	item.add_child(label)

	# Make draggable
	item.gui_input.connect(_on_item_input.bind(item))
	item.set_meta("draggable", true)
	item.set_meta("item_name", item_name)

	return item

var dragging_item: Panel = null
var drag_offset: Vector2

func _on_item_input(event: InputEvent, item: Panel):
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_LEFT:
			if event.pressed:
				dragging_item = item
				drag_offset = item.position - event.position
				item.modulate.a = 0.7
			else:
				if dragging_item:
					dragging_item.modulate.a = 1.0
					dragging_item = null

func _process(_delta):
	if dragging_item:
		dragging_item.position = get_local_mouse_position() + drag_offset

func _on_refresh_shop():
	if current_gold >= 2:
		current_gold -= 2
		get_child(2).text = "Gold: %d | Round: %d | Health: %d" % [current_gold, current_round, current_health]
		_generate_dummy_shop()
		print("Shop refreshed!")

func _on_start_battle():
	print("Starting battle with %d items!" % inventory_items.size())

	# Simulate battle
	if randf() > 0.5:
		print("Victory!")
		current_gold += 5
		current_round += 1
	else:
		print("Defeat!")
		current_health -= 10

	get_child(2).text = "Gold: %d | Round: %d | Health: %d" % [current_gold, current_round, current_health]

	if current_health <= 0:
		print("Game Over!")
