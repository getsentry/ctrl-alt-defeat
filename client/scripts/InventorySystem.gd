extends Control
class_name InventorySystem

signal item_placed(item: Dictionary, position: Vector2i)
signal item_removed(item: Dictionary)
signal item_selected(item: Dictionary)

const GRID_SIZE = Vector2i(7, 9)
const CELL_SIZE = Vector2(80, 80)
const GRID_SPACING = 2

var grid_slots: Array[Control] = []
var inventory_items: Array[Dictionary] = []
var dragging_item: Dictionary = {}
var drag_preview: Control = null
var hovered_slot: Control = null

@onready var grid_container: GridContainer = GridContainer.new()

func _ready():
	custom_minimum_size = GRID_SIZE * CELL_SIZE + Vector2(GRID_SPACING * (GRID_SIZE.x - 1), GRID_SPACING * (GRID_SIZE.y - 1))
	_setup_grid()

func _setup_grid():
	grid_container.columns = GRID_SIZE.x
	grid_container.add_theme_constant_override("h_separation", GRID_SPACING)
	grid_container.add_theme_constant_override("v_separation", GRID_SPACING)
	add_child(grid_container)

	for y in range(GRID_SIZE.y):
		for x in range(GRID_SIZE.x):
			var slot = _create_slot(Vector2i(x, y))
			grid_slots.append(slot)
			grid_container.add_child(slot)

func _create_slot(grid_pos: Vector2i) -> Control:
	var slot = Panel.new()
	slot.custom_minimum_size = CELL_SIZE
	slot.set_meta("grid_pos", grid_pos)
	slot.set_meta("occupied", false)

	var style = StyleBoxFlat.new()
	style.bg_color = Color(0.2, 0.2, 0.25, 0.8)
	style.border_color = Color(0.4, 0.4, 0.5, 1.0)
	style.set_border_width_all(2)
	style.corner_radius_top_left = 4
	style.corner_radius_top_right = 4
	style.corner_radius_bottom_left = 4
	style.corner_radius_bottom_right = 4
	slot.add_theme_stylebox_override("panel", style)

	slot.gui_input.connect(_on_slot_input.bind(slot))
	slot.mouse_entered.connect(_on_slot_hover_start.bind(slot))
	slot.mouse_exited.connect(_on_slot_hover_end.bind(slot))

	return slot

func _on_slot_input(event: InputEvent, slot: Control):
	var grid_pos = slot.get_meta("grid_pos")

	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_LEFT:
			if event.pressed:
				_handle_slot_click(slot, grid_pos)
			else:
				_handle_slot_release(slot, grid_pos)
		elif event.button_index == MOUSE_BUTTON_RIGHT and event.pressed:
			_handle_slot_right_click(slot, grid_pos)

func _handle_slot_click(slot: Control, grid_pos: Vector2i):
	var item = get_item_at_position(grid_pos)
	if item != null:
		_start_dragging(item, slot)
	elif not dragging_item.is_empty():
		_try_place_item(dragging_item, grid_pos)

func _handle_slot_release(slot: Control, grid_pos: Vector2i):
	if not dragging_item.is_empty():
		_try_place_item(dragging_item, grid_pos)

func _handle_slot_right_click(slot: Control, grid_pos: Vector2i):
	var item = get_item_at_position(grid_pos)
	if item != null:
		_remove_item(item)

func _on_slot_hover_start(slot: Control):
	hovered_slot = slot
	_update_slot_highlight(slot, true)

func _on_slot_hover_end(slot: Control):
	if hovered_slot == slot:
		hovered_slot = null
	_update_slot_highlight(slot, false)

func _update_slot_highlight(slot: Control, highlighted: bool):
	var style = slot.get_theme_stylebox("panel") as StyleBoxFlat
	if style:
		var new_style = style.duplicate() as StyleBoxFlat
		if highlighted:
			new_style.border_color = Color(0.8, 0.8, 0.2, 1.0)
			new_style.set_border_width_all(3)
		else:
			new_style.border_color = Color(0.4, 0.4, 0.5, 1.0)
			new_style.set_border_width_all(2)
		slot.add_theme_stylebox_override("panel", new_style)

func _start_dragging(item: Dictionary, from_slot: Control):
	dragging_item = item
	_create_drag_preview(item)
	_remove_item_visual(item)

func _create_drag_preview(item: Dictionary):
	if drag_preview:
		drag_preview.queue_free()

	drag_preview = Panel.new()
	drag_preview.custom_minimum_size = CELL_SIZE * 0.9
	drag_preview.modulate.a = 0.7

	var style = StyleBoxFlat.new()
	style.bg_color = Color(0.3, 0.5, 0.8, 0.8)
	style.border_color = Color(0.5, 0.7, 1.0, 1.0)
	style.set_border_width_all(2)
	drag_preview.add_theme_stylebox_override("panel", style)

	var label = Label.new()
	label.text = item.get("name", "Item").substr(0, 8)
	label.add_theme_font_size_override("font_size", 12)
	drag_preview.add_child(label)

	get_viewport().add_child(drag_preview)

func _process(_delta):
	if drag_preview:
		drag_preview.global_position = get_global_mouse_position() - drag_preview.size / 2

func _try_place_item(item: Dictionary, grid_pos: Vector2i):
	if can_place_item_at(item, grid_pos):
		_place_item(item, grid_pos)
		_stop_dragging()
		return true
	else:
		_restore_item(item)
		_stop_dragging()
		return false

func _place_item(item: Dictionary, grid_pos: Vector2i):
	item["position"] = [grid_pos.x, grid_pos.y]
	if not item in inventory_items:
		inventory_items.append(item)
	_update_item_visual(item)
	item_placed.emit(item, grid_pos)

func _remove_item(item: Dictionary):
	inventory_items.erase(item)
	_remove_item_visual(item)
	item_removed.emit(item)

func _restore_item(item: Dictionary):
	if item.has("position") and item["position"] != null:
		_update_item_visual(item)

func _stop_dragging():
	dragging_item = {}
	if drag_preview:
		drag_preview.queue_free()
		drag_preview = null

func _update_item_visual(item: Dictionary):
	if not item.has("position") or item["position"] == null:
		return

	var pos = item["position"]
	var index = pos[1] * GRID_SIZE.x + pos[0]
	if index < grid_slots.size():
		var slot = grid_slots[index]
		slot.set_meta("occupied", true)

		# Clear existing children
		for child in slot.get_children():
			child.queue_free()

		# Add item visual
		var item_visual = VBoxContainer.new()
		item_visual.mouse_filter = Control.MOUSE_FILTER_IGNORE

		var name_label = Label.new()
		name_label.text = item.get("name", "Item").substr(0, 10)
		name_label.add_theme_font_size_override("font_size", 11)
		name_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
		item_visual.add_child(name_label)

		if item.has("min_damage") and item.get("min_damage", 0) > 0:
			var dmg_label = Label.new()
			dmg_label.text = "%d-%d" % [item.get("min_damage", 0), item.get("max_damage", 0)]
			dmg_label.add_theme_font_size_override("font_size", 10)
			dmg_label.modulate = Color(1.0, 0.5, 0.5)
			dmg_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
			item_visual.add_child(dmg_label)

		var tier_label = Label.new()
		tier_label.text = "T" + str(item.get("tier", 1))
		tier_label.add_theme_font_size_override("font_size", 9)
		tier_label.modulate = Color(0.8, 0.8, 0.8)
		tier_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
		item_visual.add_child(tier_label)

		slot.add_child(item_visual)

		# Update slot style based on item rarity
		var style = slot.get_theme_stylebox("panel") as StyleBoxFlat
		if style:
			var new_style = style.duplicate() as StyleBoxFlat
			match item.get("rarity", "common"):
				"common":
					new_style.bg_color = Color(0.25, 0.25, 0.3, 0.9)
				"uncommon":
					new_style.bg_color = Color(0.2, 0.35, 0.25, 0.9)
				"rare":
					new_style.bg_color = Color(0.2, 0.25, 0.45, 0.9)
				"epic":
					new_style.bg_color = Color(0.35, 0.2, 0.4, 0.9)
				"legendary":
					new_style.bg_color = Color(0.45, 0.35, 0.2, 0.9)
			slot.add_theme_stylebox_override("panel", new_style)

func _remove_item_visual(item: Dictionary):
	if not item.has("position") or item["position"] == null:
		return

	var pos = item["position"]
	var index = pos[1] * GRID_SIZE.x + pos[0]
	if index < grid_slots.size():
		var slot = grid_slots[index]
		slot.set_meta("occupied", false)

		for child in slot.get_children():
			child.queue_free()

		# Reset slot style
		var style = StyleBoxFlat.new()
		style.bg_color = Color(0.2, 0.2, 0.25, 0.8)
		style.border_color = Color(0.4, 0.4, 0.5, 1.0)
		style.set_border_width_all(2)
		style.corner_radius_top_left = 4
		style.corner_radius_top_right = 4
		style.corner_radius_bottom_left = 4
		style.corner_radius_bottom_right = 4
		slot.add_theme_stylebox_override("panel", style)

func get_item_at_position(grid_pos: Vector2i) -> Dictionary:
	for item in inventory_items:
		if item.has("position") and item["position"] != null:
			var pos = item["position"]
			if pos[0] == grid_pos.x and pos[1] == grid_pos.y:
				return item
	return {}

func can_place_item_at(item: Dictionary, grid_pos: Vector2i) -> bool:
	if grid_pos.x < 0 or grid_pos.x >= GRID_SIZE.x:
		return false
	if grid_pos.y < 0 or grid_pos.y >= GRID_SIZE.y:
		return false

	# Check if slot is occupied by another item
	var existing = get_item_at_position(grid_pos)
	if not existing.is_empty() and existing != item:
		return false

	return true

func add_item(item: Dictionary):
	# Find first empty slot
	for y in range(GRID_SIZE.y):
		for x in range(GRID_SIZE.x):
			var pos = Vector2i(x, y)
			if get_item_at_position(pos).is_empty():
				_place_item(item, pos)
				return

	# No space, add to unplaced items
	item["position"] = null
	inventory_items.append(item)

func clear_inventory():
	for item in inventory_items:
		_remove_item_visual(item)
	inventory_items.clear()

func get_placed_items() -> Array[Dictionary]:
	var placed = []
	for item in inventory_items:
		if item.has("position") and item["position"] != null:
			placed.append(item)
	return placed

func refresh_display():
	# Clear all visuals
	for slot in grid_slots:
		slot.set_meta("occupied", false)
		for child in slot.get_children():
			child.queue_free()

	# Redraw all items
	for item in inventory_items:
		if item.has("position") and item["position"] != null:
			_update_item_visual(item)
