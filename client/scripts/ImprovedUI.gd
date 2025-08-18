extends Control
class_name ImprovedUI

# Game state
var current_gold: int = 30
var current_round: int = 1
var current_health: int = 100
var shop_items: Array = []
var inventory_items: Array = []
var dragging_item: Control = null
var drag_offset: Vector2

func _ready():
	print("ImprovedUI starting...")
	custom_minimum_size = Vector2(1280, 720)
	_setup_ui()
	_generate_shop()

func _setup_ui():
	# Main background
	var bg = ColorRect.new()
	bg.color = Color(0.05, 0.05, 0.08, 1.0)
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(bg)

	# Header Panel
	var header_panel = ColorRect.new()
	header_panel.color = Color(0.08, 0.08, 0.12, 1.0)
	header_panel.position = Vector2(0, 0)
	header_panel.size = Vector2(1280, 120)
	add_child(header_panel)

	# Title
	var title = Label.new()
	title.text = "SENTRY AUTOBATTLER"
	title.position = Vector2(490, 20)
	title.add_theme_font_size_override("font_size", 36)
	title.add_theme_color_override("font_color", Color(0.9, 0.9, 1.0))
	title.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.5))
	title.add_theme_constant_override("shadow_offset_x", 2)
	title.add_theme_constant_override("shadow_offset_y", 2)
	add_child(title)

	# Stats Container
	var stats_bg = ColorRect.new()
	stats_bg.color = Color(0.1, 0.1, 0.15, 0.8)
	stats_bg.position = Vector2(400, 60)
	stats_bg.size = Vector2(480, 50)
	add_child(stats_bg)

	var stats = Label.new()
	stats.name = "StatsLabel"
	stats.text = "💰 %d Gold  |  Round %d  |  ❤️ %d HP" % [current_gold, current_round, current_health]
	stats.position = Vector2(480, 70)
	stats.add_theme_font_size_override("font_size", 22)
	stats.add_theme_color_override("font_color", Color(1.0, 1.0, 1.0))
	add_child(stats)

	# Shop Container
	var shop_container = ColorRect.new()
	shop_container.name = "ShopContainer"
	shop_container.color = Color(0.08, 0.08, 0.12, 0.95)
	shop_container.position = Vector2(20, 140)
	shop_container.size = Vector2(550, 480)
	add_child(shop_container)

	# Shop Title
	var shop_title_bg = ColorRect.new()
	shop_title_bg.color = Color(0.2, 0.15, 0.3, 1.0)
	shop_title_bg.position = Vector2(20, 140)
	shop_title_bg.size = Vector2(550, 40)
	add_child(shop_title_bg)

	var shop_title = Label.new()
	shop_title.text = "SHOP"
	shop_title.position = Vector2(250, 147)
	shop_title.add_theme_font_size_override("font_size", 24)
	shop_title.add_theme_color_override("font_color", Color(1.0, 1.0, 1.0))
	add_child(shop_title)

	# Shop Items Panel
	var shop_panel = Control.new()
	shop_panel.name = "ShopPanel"
	shop_panel.position = Vector2(30, 190)
	shop_panel.size = Vector2(530, 380)
	add_child(shop_panel)

	# Inventory Container
	var inv_container = ColorRect.new()
	inv_container.name = "InventoryContainer"
	inv_container.color = Color(0.08, 0.12, 0.08, 0.95)
	inv_container.position = Vector2(590, 140)
	inv_container.size = Vector2(670, 480)
	add_child(inv_container)

	# Inventory Title
	var inv_title_bg = ColorRect.new()
	inv_title_bg.color = Color(0.15, 0.25, 0.15, 1.0)
	inv_title_bg.position = Vector2(590, 140)
	inv_title_bg.size = Vector2(670, 40)
	add_child(inv_title_bg)

	var inv_title = Label.new()
	inv_title.text = "INVENTORY"
	inv_title.position = Vector2(880, 147)
	inv_title.add_theme_font_size_override("font_size", 24)
	inv_title.add_theme_color_override("font_color", Color(1.0, 1.0, 1.0))
	add_child(inv_title)

	# Inventory Grid Background
	var inv_grid = Control.new()
	inv_grid.name = "InventoryGrid"
	inv_grid.position = Vector2(600, 190)
	inv_grid.size = Vector2(650, 420)
	inv_grid.set_meta("drop_zone", true)
	add_child(inv_grid)

	# Draw grid lines
	for x in range(7):
		var line = ColorRect.new()
		line.color = Color(0.2, 0.25, 0.2, 0.3)
		line.position = Vector2(600 + x * 90, 190)
		line.size = Vector2(1, 420)
		add_child(line)

	for y in range(9):
		var line = ColorRect.new()
		line.color = Color(0.2, 0.25, 0.2, 0.3)
		line.position = Vector2(600, 190 + y * 46)
		line.size = Vector2(630, 1)
		add_child(line)

	# Bottom Controls Panel
	var controls_bg = ColorRect.new()
	controls_bg.color = Color(0.08, 0.08, 0.12, 0.95)
	controls_bg.position = Vector2(0, 630)
	controls_bg.size = Vector2(1280, 90)
	add_child(controls_bg)

	# Refresh Button
	var refresh_btn = Button.new()
	refresh_btn.text = "🔄 Refresh Shop (2g)"
	refresh_btn.position = Vector2(50, 650)
	refresh_btn.size = Vector2(180, 50)
	refresh_btn.add_theme_font_size_override("font_size", 16)
	var btn_style = StyleBoxFlat.new()
	btn_style.bg_color = Color(0.2, 0.2, 0.3, 1.0)
	btn_style.set_corner_radius_all(5)
	refresh_btn.add_theme_stylebox_override("normal", btn_style)
	var btn_hover = btn_style.duplicate()
	btn_hover.bg_color = Color(0.25, 0.25, 0.35, 1.0)
	refresh_btn.add_theme_stylebox_override("hover", btn_hover)
	refresh_btn.pressed.connect(_on_refresh_shop)
	add_child(refresh_btn)

	# Battle Button
	var battle_btn = Button.new()
	battle_btn.text = "⚔️ Start Battle"
	battle_btn.position = Vector2(1050, 650)
	battle_btn.size = Vector2(180, 50)
	battle_btn.add_theme_font_size_override("font_size", 18)
	var battle_style = StyleBoxFlat.new()
	battle_style.bg_color = Color(0.3, 0.15, 0.15, 1.0)
	battle_style.set_corner_radius_all(5)
	battle_btn.add_theme_stylebox_override("normal", battle_style)
	var battle_hover = battle_style.duplicate()
	battle_hover.bg_color = Color(0.4, 0.2, 0.2, 1.0)
	battle_btn.add_theme_stylebox_override("hover", battle_hover)
	battle_btn.pressed.connect(_on_start_battle)
	add_child(battle_btn)

	# Help text
	var help_text = Label.new()
	help_text.text = "Buy items → Drag to inventory → Battle → Repeat"
	help_text.position = Vector2(450, 665)
	help_text.add_theme_font_size_override("font_size", 14)
	help_text.add_theme_color_override("font_color", Color(0.6, 0.6, 0.7))
	add_child(help_text)

	print("UI setup complete")

func _generate_shop():
	shop_items.clear()
	var shop_panel = get_node("ShopPanel")

	# Clear existing items
	for child in shop_panel.get_children():
		child.queue_free()

	# Item data
	var items = [
		{"name": "Bug Tracker", "cost": 3, "desc": "Finds and fixes errors", "color": Color(0.8, 0.3, 0.3)},
		{"name": "Memory Guard", "cost": 5, "desc": "Prevents memory leaks", "color": Color(0.3, 0.5, 0.8)},
		{"name": "Error Shield", "cost": 4, "desc": "Blocks incoming damage", "color": Color(0.5, 0.3, 0.8)},
		{"name": "Load Balancer", "cost": 6, "desc": "Distributes damage", "color": Color(0.3, 0.8, 0.5)},
		{"name": "Coffee Script", "cost": 2, "desc": "Quick energy boost", "color": Color(0.6, 0.4, 0.2)}
	]

	for i in range(items.size()):
		var item_data = items[i]

		# Item Card Background
		var item_card = ColorRect.new()
		item_card.color = Color(0.12, 0.12, 0.18, 1.0)
		item_card.position = Vector2(5, 5 + i * 75)
		item_card.size = Vector2(520, 70)
		shop_panel.add_child(item_card)

		# Item Color Stripe
		var stripe = ColorRect.new()
		stripe.color = item_data.color
		stripe.position = Vector2(0, 0)
		stripe.size = Vector2(5, 70)
		item_card.add_child(stripe)

		# Item Icon Background
		var icon_bg = ColorRect.new()
		icon_bg.color = Color(0.15, 0.15, 0.2, 1.0)
		icon_bg.position = Vector2(15, 10)
		icon_bg.size = Vector2(50, 50)
		item_card.add_child(icon_bg)

		# Item Name
		var name_label = Label.new()
		name_label.text = item_data.name
		name_label.position = Vector2(75, 8)
		name_label.add_theme_font_size_override("font_size", 18)
		name_label.add_theme_color_override("font_color", Color(1.0, 1.0, 1.0))
		item_card.add_child(name_label)

		# Item Description
		var desc_label = Label.new()
		desc_label.text = item_data.desc
		desc_label.position = Vector2(75, 32)
		desc_label.add_theme_font_size_override("font_size", 12)
		desc_label.add_theme_color_override("font_color", Color(0.7, 0.7, 0.8))
		item_card.add_child(desc_label)

		# Cost Label
		var cost_label = Label.new()
		cost_label.text = "💰 %d" % item_data.cost
		cost_label.position = Vector2(350, 20)
		cost_label.add_theme_font_size_override("font_size", 20)
		cost_label.add_theme_color_override("font_color", Color(1.0, 0.85, 0.3))
		item_card.add_child(cost_label)

		# Buy Button
		var buy_btn = Button.new()
		buy_btn.text = "BUY"
		buy_btn.position = Vector2(420, 15)
		buy_btn.size = Vector2(80, 40)
		buy_btn.add_theme_font_size_override("font_size", 16)

		var buy_style = StyleBoxFlat.new()
		buy_style.bg_color = Color(0.2, 0.4, 0.2, 1.0)
		buy_style.set_corner_radius_all(3)
		buy_btn.add_theme_stylebox_override("normal", buy_style)

		var buy_hover = buy_style.duplicate()
		buy_hover.bg_color = Color(0.25, 0.5, 0.25, 1.0)
		buy_btn.add_theme_stylebox_override("hover", buy_hover)

		var buy_disabled = buy_style.duplicate()
		buy_disabled.bg_color = Color(0.15, 0.15, 0.15, 1.0)
		buy_btn.add_theme_stylebox_override("disabled", buy_disabled)

		buy_btn.pressed.connect(_on_buy_item.bind(item_data, buy_btn))
		item_card.add_child(buy_btn)

		shop_items.append({
			"data": item_data,
			"button": buy_btn,
			"card": item_card
		})

	print("Shop generated with %d items" % shop_items.size())

func _on_buy_item(item_data: Dictionary, button: Button):
	if current_gold >= item_data.cost:
		current_gold -= item_data.cost
		print("Bought: %s for %d gold" % [item_data.name, item_data.cost])

		# Update stats
		var stats = get_node("StatsLabel")
		stats.text = "💰 %d Gold  |  Round %d  |  ❤️ %d HP" % [current_gold, current_round, current_health]

		# Create draggable item
		var item = _create_draggable_item(item_data)
		var inv_grid = get_node("InventoryGrid")
		inv_grid.add_child(item)
		inventory_items.append(item)

		# Disable button
		button.disabled = true
		button.text = "SOLD"
	else:
		print("Not enough gold!")

func _create_draggable_item(item_data: Dictionary) -> Control:
	var item = ColorRect.new()
	item.color = item_data.color
	item.size = Vector2(80, 40)
	item.position = Vector2(10 + (inventory_items.size() % 7) * 90, 10 + (inventory_items.size() / 7) * 50)

	var label = Label.new()
	label.text = item_data.name.substr(0, 8)
	label.position = Vector2(5, 10)
	label.add_theme_font_size_override("font_size", 12)
	label.add_theme_color_override("font_color", Color(1.0, 1.0, 1.0))
	item.add_child(label)

	item.gui_input.connect(_on_item_input.bind(item))
	item.set_meta("draggable", true)
	item.set_meta("item_data", item_data)

	return item

func _on_item_input(event: InputEvent, item: Control):
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_LEFT:
			if event.pressed:
				dragging_item = item
				drag_offset = item.global_position - event.global_position
				item.modulate.a = 0.6
				# Move to front
				item.get_parent().move_child(item, -1)
			else:
				if dragging_item:
					dragging_item.modulate.a = 1.0
					dragging_item = null

func _process(_delta):
	if dragging_item:
		dragging_item.global_position = get_global_mouse_position() + drag_offset

func _on_refresh_shop():
	if current_gold >= 2:
		current_gold -= 2
		var stats = get_node("StatsLabel")
		stats.text = "💰 %d Gold  |  Round %d  |  ❤️ %d HP" % [current_gold, current_round, current_health]
		_generate_shop()
		print("Shop refreshed!")
	else:
		print("Not enough gold to refresh!")

func _on_start_battle():
	print("Starting battle with %d items!" % inventory_items.size())

	# Simulate battle
	if randf() > 0.4:  # 60% win rate
		print("Victory! +5 gold")
		current_gold += 5
		current_round += 1
	else:
		print("Defeat! -10 HP")
		current_health -= 10

	var stats = get_node("StatsLabel")
	stats.text = "💰 %d Gold  |  Round %d  |  ❤️ %d HP" % [current_gold, current_round, current_health]

	if current_health <= 0:
		print("GAME OVER! You survived %d rounds." % current_round)
		# Could show game over screen here
