extends GridContainer
class_name ServerRackInventory

const MIN_GRID_SIZE = 4
const MAX_GRID_SIZE = 8
const SLOT_SIZE = 80

var current_grid_size: int = 4
var slots: Array[Control] = []
var items: Dictionary = {}
var server_api: ServerAPI

signal item_placed(item: Item, position: Vector2i)
signal item_removed(item: Item, position: Vector2i)
signal items_merged(item1: Item, item2: Item, result: Item)
signal rack_expanded(new_size: int)

func _ready():
	server_api = ServerAPI.new()
	add_child(server_api)
	setup_grid(current_grid_size)

func setup_grid(size: int):
	current_grid_size = size
	columns = size
	custom_minimum_size = Vector2(size * SLOT_SIZE, size * SLOT_SIZE)
	
	for child in get_children():
		if child != server_api:
			child.queue_free()
	
	slots.clear()
	
	for y in range(size):
		for x in range(size):
			var slot = create_server_slot(Vector2i(x, y))
			add_child(slot)
			slots.append(slot)

func create_server_slot(grid_pos: Vector2i) -> Control:
	var slot = Panel.new()
	slot.custom_minimum_size = Vector2(SLOT_SIZE, SLOT_SIZE)
	slot.set_meta("grid_position", grid_pos)
	slot.gui_input.connect(_on_slot_input.bind(slot))
	
	var style = StyleBoxFlat.new()
	style.bg_color = Color(0.1, 0.1, 0.15, 0.9)
	style.border_color = Color(0.0, 0.8, 1.0, 0.3)
	style.set_border_width_all(2)
	style.set_corner_radius_all(4)
	slot.add_theme_stylebox_override("panel", style)
	
	var grid_lines = Control.new()
	grid_lines.name = "GridLines"
	grid_lines.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	slot.add_child(grid_lines)
	
	grid_lines.draw.connect(func():
		var line_color = Color(0.0, 0.6, 0.8, 0.2)
		grid_lines.draw_line(Vector2(0, SLOT_SIZE/2), Vector2(SLOT_SIZE, SLOT_SIZE/2), line_color)
		grid_lines.draw_line(Vector2(SLOT_SIZE/2, 0), Vector2(SLOT_SIZE/2, SLOT_SIZE), line_color)
	)
	
	var slot_label = Label.new()
	slot_label.name = "SlotLabel"
	slot_label.text = "Rack %d-%d" % [grid_pos.x, grid_pos.y]
	slot_label.add_theme_color_override("font_color", Color(0.3, 0.5, 0.6, 0.5))
	slot_label.add_theme_font_size_override("font_size", 10)
	slot_label.position = Vector2(4, 4)
	slot.add_child(slot_label)
	
	return slot

func _on_slot_input(event: InputEvent, slot: Control):
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_LEFT:
			if event.pressed:
				var pos = slot.get_meta("grid_position")
				handle_slot_click(pos, event.shift_pressed)
			elif event.is_released():
				handle_drop(slot)
		elif event.button_index == MOUSE_BUTTON_RIGHT and event.pressed:
			var pos = slot.get_meta("grid_position")
			handle_slot_right_click(pos)

var dragging_item: Item = null
var drag_preview: Control = null

func handle_slot_click(position: Vector2i, shift_pressed: bool):
	var item = get_item_at(position)
	if item:
		if shift_pressed:
			sell_item(item, position)
		else:
			start_drag(item, position)

func start_drag(item: Item, position: Vector2i):
	dragging_item = item
	remove_item(position)
	
	if drag_preview:
		drag_preview.queue_free()
	
	drag_preview = create_drag_preview(item)
	get_viewport().add_child(drag_preview)

func create_drag_preview(item: Item) -> Control:
	var preview = Panel.new()
	preview.custom_minimum_size = Vector2(SLOT_SIZE - 10, SLOT_SIZE - 10)
	preview.mouse_filter = Control.MOUSE_FILTER_IGNORE
	
	var style = StyleBoxFlat.new()
	style.bg_color = get_item_color(item)
	style.bg_color.a = 0.8
	style.set_corner_radius_all(8)
	preview.add_theme_stylebox_override("panel", style)
	
	var label = Label.new()
	label.text = item.item_name
	label.add_theme_font_size_override("font_size", 12)
	label.position = Vector2(8, 8)
	preview.add_child(label)
	
	return preview

func _input(event: InputEvent):
	if drag_preview and event is InputEventMouseMotion:
		drag_preview.global_position = event.position - Vector2(SLOT_SIZE/2, SLOT_SIZE/2)

func handle_drop(slot: Control):
	if not dragging_item:
		return
	
	var position = slot.get_meta("grid_position")
	
	if add_item(dragging_item, position):
		server_api.place_item(dragging_item.get_instance_id(), position)
	
	dragging_item = null
	if drag_preview:
		drag_preview.queue_free()
		drag_preview = null

func handle_slot_right_click(position: Vector2i):
	var item = get_item_at(position)
	if item:
		show_item_tooltip(item)

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
	apply_network_effects(item)
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

func sell_item(item: Item, position: Vector2i):
	remove_item(position)
	var sell_value = 1 + item.tier
	if server_api.player_id != "":
		pass

func position_to_key(position: Vector2i) -> String:
	return str(position.x) + "," + str(position.y)

func get_slot_at(position: Vector2i) -> Control:
	var index = position.y * current_grid_size + position.x
	if index >= 0 and index < slots.size():
		return slots[index]
	return null

func get_item_at(position: Vector2i) -> Item:
	var key = position_to_key(position)
	return items.get(key, null)

func update_slot_visual(position: Vector2i, item: Item):
	var slot = get_slot_at(position)
	if not slot:
		return
	
	for child in slot.get_children():
		if child.name == "ItemVisual":
			child.queue_free()
	
	var item_visual = Panel.new()
	item_visual.name = "ItemVisual"
	item_visual.custom_minimum_size = Vector2(SLOT_SIZE - 16, SLOT_SIZE - 16)
	item_visual.position = Vector2(8, 8)
	item_visual.mouse_filter = Control.MOUSE_FILTER_IGNORE
	
	var style = StyleBoxFlat.new()
	style.bg_color = get_item_color(item)
	style.set_corner_radius_all(6)
	
	if item.item_type == Item.ItemType.DISTRIBUTED_TRACING:
		style.border_color = Color(1.0, 0.8, 0.0, 0.8)
		style.set_border_width_all(3)
	
	item_visual.add_theme_stylebox_override("panel", style)
	
	var vbox = VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 2)
	item_visual.add_child(vbox)
	
	var name_label = Label.new()
	name_label.text = item.item_name
	name_label.add_theme_font_size_override("font_size", 11)
	name_label.add_theme_color_override("font_color", Color.WHITE)
	vbox.add_child(name_label)
	
	var tier_label = Label.new()
	tier_label.text = "Tier " + str(item.tier)
	tier_label.add_theme_font_size_override("font_size", 9)
	tier_label.add_theme_color_override("font_color", Color(0.8, 0.8, 0.8))
	vbox.add_child(tier_label)
	
	var stats_label = Label.new()
	stats_label.text = "⚔%d ❤%d" % [item.get_total_damage(), item.get_total_health()]
	stats_label.add_theme_font_size_override("font_size", 10)
	vbox.add_child(stats_label)
	
	slot.add_child(item_visual)
	
	animate_placement(item_visual)

func animate_placement(visual: Control):
	var tween = create_tween()
	visual.modulate.a = 0
	visual.scale = Vector2(0.8, 0.8)
	tween.set_parallel()
	tween.tween_property(visual, "modulate:a", 1.0, 0.3)
	tween.tween_property(visual, "scale", Vector2.ONE, 0.3).set_ease(Tween.EASE_OUT).set_trans(Tween.TRANS_BACK)

func clear_slot_visual(position: Vector2i):
	var slot = get_slot_at(position)
	if slot:
		for child in slot.get_children():
			if child.name == "ItemVisual":
				var tween = create_tween()
				tween.tween_property(child, "modulate:a", 0.0, 0.2)
				tween.tween_callback(child.queue_free)

func get_item_color(item: Item) -> Color:
	match item.rarity:
		Item.Rarity.COMMON:
			return Color(0.5, 0.5, 0.5)
		Item.Rarity.UNCOMMON:
			return Color(0.2, 0.8, 0.2)
		Item.Rarity.RARE:
			return Color(0.2, 0.4, 1.0)
		Item.Rarity.EPIC:
			return Color(0.6, 0.2, 0.8)
		Item.Rarity.LEGENDARY:
			return Color(1.0, 0.6, 0.0)
		_:
			return Color.GRAY

func apply_network_effects(item: Item):
	var adjacent_items = get_adjacent_items(item.grid_position)
	
	for adj_item in adjacent_items:
		create_network_connection_visual(item.grid_position, adj_item.grid_position)
	
	if item.item_type == Item.ItemType.DISTRIBUTED_TRACING:
		connect_all_tracing_items()

func get_adjacent_items(position: Vector2i) -> Array[Item]:
	var adjacent: Array[Item] = []
	var positions = [
		position + Vector2i.UP,
		position + Vector2i.DOWN,
		position + Vector2i.LEFT,
		position + Vector2i.RIGHT
	]
	
	for pos in positions:
		if pos.x >= 0 and pos.x < current_grid_size and pos.y >= 0 and pos.y < current_grid_size:
			var item = get_item_at(pos)
			if item:
				adjacent.append(item)
	
	return adjacent

func create_network_connection_visual(from_pos: Vector2i, to_pos: Vector2i):
	pass

func connect_all_tracing_items():
	pass

func expand_rack():
	if current_grid_size >= MAX_GRID_SIZE:
		return
	
	var expansion_cost = 10 * (current_grid_size - 3)
	
	server_api.http_request.request_completed.connect(_on_expand_complete, CONNECT_ONE_SHOT)
	server_api.http_request.request(
		ServerAPI.BASE_URL + "/inventory/expand/" + server_api.player_id,
		[],
		HTTPClient.METHOD_POST
	)

func _on_expand_complete(result: int, response_code: int, headers: PackedStringArray, body: PackedByteArray):
	if response_code == 200:
		var json = JSON.new()
		var parse_result = json.parse(body.get_string_from_utf8())
		if parse_result == OK:
			var new_size = json.data["new_size"]
			setup_grid(new_size)
			rack_expanded.emit(new_size)

func show_item_tooltip(item: Item):
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