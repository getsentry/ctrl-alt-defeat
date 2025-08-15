extends GridContainer
class_name Inventory

const GRID_SIZE = 6
const SLOT_SIZE = 64

var slots: Array[Node] = []
var items: Dictionary = {}

signal item_placed(item: Item, position: Vector2i)
signal item_removed(item: Item, position: Vector2i)
signal items_merged(item1: Item, item2: Item, result: Item)

func _ready():
	columns = GRID_SIZE
	custom_minimum_size = Vector2(GRID_SIZE * SLOT_SIZE, GRID_SIZE * SLOT_SIZE)
	
	for y in range(GRID_SIZE):
		for x in range(GRID_SIZE):
			var slot = create_slot(Vector2i(x, y))
			add_child(slot)
			slots.append(slot)

func create_slot(grid_pos: Vector2i) -> Control:
	var slot = Control.new()
	slot.custom_minimum_size = Vector2(SLOT_SIZE, SLOT_SIZE)
	slot.set_meta("grid_position", grid_pos)
	slot.gui_input.connect(_on_slot_input.bind(slot))
	
	var bg = ColorRect.new()
	bg.color = Color(0.2, 0.2, 0.2, 0.8)
	bg.size = Vector2(SLOT_SIZE - 2, SLOT_SIZE - 2)
	bg.position = Vector2(1, 1)
	slot.add_child(bg)
	
	return slot

func _on_slot_input(event: InputEvent, slot: Control):
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
			var pos = slot.get_meta("grid_position")
			handle_slot_click(pos)

func handle_slot_click(position: Vector2i):
	pass

func add_item(item: Item, position: Vector2i) -> bool:
	var key = position_to_key(position)
	
	if items.has(key):
		var existing_item = items[key]
		if existing_item.can_merge_with(item):
			var merged = existing_item.merge()
			remove_item(position)
			add_item(merged, position)
			items_merged.emit(existing_item, item, merged)
			return true
		return false
	
	items[key] = item
	item.grid_position = position
	item_placed.emit(item, position)
	update_slot_visual(position, item)
	check_adjacency_bonuses(item)
	return true

func remove_item(position: Vector2i) -> Item:
	var key = position_to_key(position)
	if items.has(key):
		var item = items[key]
		items.erase(key)
		item.grid_position = Vector2i(-1, -1)
		item_removed.emit(item, position)
		clear_slot_visual(position)
		return item
	return null

func move_item(from_pos: Vector2i, to_pos: Vector2i) -> bool:
	var item = remove_item(from_pos)
	if item:
		if add_item(item, to_pos):
			return true
		else:
			add_item(item, from_pos)
			return false
	return false

func get_item_at(position: Vector2i) -> Item:
	var key = position_to_key(position)
	return items.get(key, null)

func position_to_key(position: Vector2i) -> String:
	return str(position.x) + "," + str(position.y)

func get_slot_at(position: Vector2i) -> Control:
	var index = position.y * GRID_SIZE + position.x
	if index >= 0 and index < slots.size():
		return slots[index]
	return null

func update_slot_visual(position: Vector2i, item: Item):
	var slot = get_slot_at(position)
	if slot:
		for child in slot.get_children():
			if child.name == "ItemVisual":
				child.queue_free()
		
		var item_visual = ColorRect.new()
		item_visual.name = "ItemVisual"
		item_visual.size = Vector2(SLOT_SIZE - 8, SLOT_SIZE - 8)
		item_visual.position = Vector2(4, 4)
		
		match item.rarity:
			Item.Rarity.COMMON:
				item_visual.color = Color.GRAY
			Item.Rarity.UNCOMMON:
				item_visual.color = Color.GREEN
			Item.Rarity.RARE:
				item_visual.color = Color.BLUE
			Item.Rarity.EPIC:
				item_visual.color = Color.PURPLE
			Item.Rarity.LEGENDARY:
				item_visual.color = Color.ORANGE
		
		var label = Label.new()
		label.text = item.item_name.left(3)
		label.add_theme_font_size_override("font_size", 12)
		item_visual.add_child(label)
		
		slot.add_child(item_visual)

func clear_slot_visual(position: Vector2i):
	var slot = get_slot_at(position)
	if slot:
		for child in slot.get_children():
			if child.name == "ItemVisual":
				child.queue_free()

func check_adjacency_bonuses(item: Item):
	var adjacent_items = []
	for adj_pos in item.get_adjacent_positions():
		if adj_pos.x >= 0 and adj_pos.x < GRID_SIZE and adj_pos.y >= 0 and adj_pos.y < GRID_SIZE:
			var adj_item = get_item_at(adj_pos)
			if adj_item:
				adjacent_items.append(adj_item)
	
	apply_adjacency_effects(item, adjacent_items)

func apply_adjacency_effects(item: Item, adjacent_items: Array):
	pass

func get_all_items() -> Array[Item]:
	var all_items: Array[Item] = []
	for item in items.values():
		all_items.append(item)
	return all_items

func clear_inventory():
	for key in items.keys():
		var parts = key.split(",")
		var pos = Vector2i(int(parts[0]), int(parts[1]))
		remove_item(pos)
	items.clear()