extends Control
class_name Shop

const SHOP_SLOTS = 5
const REROLL_COST = 2

var available_items: Array[Item] = []
var shop_slots: Array[Control] = []
var game_manager: Node

signal item_purchased(item: Item)
signal shop_rerolled()

func _ready():
	custom_minimum_size = Vector2(800, 200)
	create_shop_ui()
	refresh_shop()

func create_shop_ui():
	var hbox = HBoxContainer.new()
	hbox.add_theme_constant_override("separation", 20)
	add_child(hbox)
	
	for i in range(SHOP_SLOTS):
		var slot = create_shop_slot(i)
		hbox.add_child(slot)
		shop_slots.append(slot)
	
	var vbox = VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 10)
	add_child(vbox)
	vbox.position = Vector2(0, 220)
	
	var reroll_button = Button.new()
	reroll_button.text = "Reroll Shop (Cost: %d gold)" % REROLL_COST
	reroll_button.pressed.connect(_on_reroll_pressed)
	vbox.add_child(reroll_button)
	
	var start_battle_button = Button.new()
	start_battle_button.text = "Start Battle"
	start_battle_button.pressed.connect(_on_start_battle_pressed)
	vbox.add_child(start_battle_button)

func create_shop_slot(index: int) -> Control:
	var slot = Panel.new()
	slot.custom_minimum_size = Vector2(140, 180)
	slot.set_meta("slot_index", index)
	
	var vbox = VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 5)
	slot.add_child(vbox)
	
	var item_display = ColorRect.new()
	item_display.name = "ItemDisplay"
	item_display.custom_minimum_size = Vector2(120, 120)
	item_display.color = Color.DARK_GRAY
	vbox.add_child(item_display)
	
	var name_label = Label.new()
	name_label.name = "NameLabel"
	name_label.text = "Empty"
	name_label.add_theme_font_size_override("font_size", 14)
	vbox.add_child(name_label)
	
	var stats_label = Label.new()
	stats_label.name = "StatsLabel"
	stats_label.text = ""
	stats_label.add_theme_font_size_override("font_size", 12)
	vbox.add_child(stats_label)
	
	var buy_button = Button.new()
	buy_button.name = "BuyButton"
	buy_button.text = "Buy (3 gold)"
	buy_button.pressed.connect(_on_buy_pressed.bind(index))
	buy_button.disabled = true
	vbox.add_child(buy_button)
	
	return slot

func refresh_shop():
	available_items.clear()
	var item_pool = load_item_pool()
	
	for i in range(SHOP_SLOTS):
		if randf() > 0.2:
			var item = create_random_item(item_pool)
			available_items.append(item)
			update_slot_display(i, item)
		else:
			available_items.append(null)
			clear_slot_display(i)

func load_item_pool() -> Array:
	var file = FileAccess.open("res://data/items.json", FileAccess.READ)
	if not file:
		return create_default_items()
	
	var json_text = file.get_as_text()
	file.close()
	
	var json = JSON.new()
	var parse_result = json.parse(json_text)
	if parse_result != OK:
		return create_default_items()
	
	return json.data.get("items", [])

func create_default_items() -> Array:
	return [
		{"name": "Error Monitor", "type": "ERROR_MONITORING", "damage": 5, "health": 10},
		{"name": "Session Replay", "type": "SESSION_REPLAY", "damage": 3, "health": 15},
		{"name": "Performance", "type": "PERFORMANCE", "damage": 4, "health": 8},
		{"name": "Profiler", "type": "PROFILING", "damage": 8, "health": 12},
		{"name": "Cron Monitor", "type": "CRON_MONITORING", "damage": 6, "health": 14}
	]

func create_random_item(item_pool: Array) -> Item:
	var item_data = item_pool[randi() % item_pool.size()]
	var item = Item.new()
	
	item.item_name = item_data.get("name", "Unknown")
	item.base_damage = item_data.get("base_damage", 5)
	item.base_health = item_data.get("base_health", 10)
	item.base_speed = item_data.get("base_speed", 1.0)
	item.ability_description = item_data.get("ability", "")
	item.adjacency_bonus = item_data.get("adjacency", "")
	
	var rarity_roll = randf()
	if rarity_roll < 0.5:
		item.rarity = Item.Rarity.COMMON
	elif rarity_roll < 0.75:
		item.rarity = Item.Rarity.UNCOMMON
	elif rarity_roll < 0.9:
		item.rarity = Item.Rarity.RARE
	elif rarity_roll < 0.98:
		item.rarity = Item.Rarity.EPIC
	else:
		item.rarity = Item.Rarity.LEGENDARY
	
	return item

func update_slot_display(index: int, item: Item):
	if index >= shop_slots.size():
		return
		
	var slot = shop_slots[index]
	var display = slot.get_node("ItemDisplay")
	var name_label = slot.get_node("NameLabel")
	var stats_label = slot.get_node("StatsLabel")
	var buy_button = slot.get_node("BuyButton")
	
	match item.rarity:
		Item.Rarity.COMMON:
			display.color = Color.GRAY
		Item.Rarity.UNCOMMON:
			display.color = Color.GREEN
		Item.Rarity.RARE:
			display.color = Color.BLUE
		Item.Rarity.EPIC:
			display.color = Color.PURPLE
		Item.Rarity.LEGENDARY:
			display.color = Color.ORANGE
	
	name_label.text = item.item_name
	stats_label.text = "DMG: %d HP: %d" % [item.base_damage, item.base_health]
	
	var cost = get_item_cost(item)
	buy_button.text = "Buy (%d gold)" % cost
	buy_button.disabled = false

func clear_slot_display(index: int):
	if index >= shop_slots.size():
		return
		
	var slot = shop_slots[index]
	var display = slot.get_node("ItemDisplay")
	var name_label = slot.get_node("NameLabel")
	var stats_label = slot.get_node("StatsLabel")
	var buy_button = slot.get_node("BuyButton")
	
	display.color = Color.DARK_GRAY
	name_label.text = "Empty"
	stats_label.text = ""
	buy_button.text = "Buy"
	buy_button.disabled = true

func get_item_cost(item: Item) -> int:
	match item.rarity:
		Item.Rarity.COMMON:
			return 3
		Item.Rarity.UNCOMMON:
			return 5
		Item.Rarity.RARE:
			return 8
		Item.Rarity.EPIC:
			return 12
		Item.Rarity.LEGENDARY:
			return 20
		_:
			return 3

func _on_buy_pressed(index: int):
	if index >= available_items.size() or not available_items[index]:
		return
	
	var item = available_items[index]
	var cost = get_item_cost(item)
	
	if game_manager and game_manager.spend_gold(cost):
		item_purchased.emit(item)
		available_items[index] = null
		clear_slot_display(index)

func _on_reroll_pressed():
	if game_manager and game_manager.spend_gold(REROLL_COST):
		refresh_shop()
		shop_rerolled.emit()

func _on_start_battle_pressed():
	if game_manager:
		game_manager.transition_to_battle()

func set_game_manager(gm: Node):
	game_manager = gm