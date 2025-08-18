class_name DraggableItem
extends Panel

signal drag_started(item: DraggableItem)
signal drag_ended(item: DraggableItem)
signal dropped_on_slot(item: DraggableItem, slot: Control)

var item_data: Dictionary = {}
var is_dragging: bool = false
var drag_offset: Vector2 = Vector2.ZERO
var original_parent: Node = null
var original_position: Vector2 = Vector2.ZERO
var hover_slot: Control = null

# Visual components
@onready var icon_rect: TextureRect = TextureRect.new()
@onready var name_label: Label = Label.new()
@onready var stats_container: VBoxContainer = VBoxContainer.new()
@onready var tier_badge: Panel = Panel.new()

func _ready():
	custom_minimum_size = Vector2(100, 120)
	mouse_filter = Control.MOUSE_FILTER_PASS

	_setup_visuals()
	_apply_item_style()

func _setup_visuals():
	# Main container
	var vbox = VBoxContainer.new()
	vbox.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	vbox.add_theme_constant_override("separation", 2)
	add_child(vbox)

	# Icon placeholder
	icon_rect.custom_minimum_size = Vector2(64, 64)
	icon_rect.expand_mode = TextureRect.EXPAND_FIT_WIDTH_PROPORTIONAL
	icon_rect.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	vbox.add_child(icon_rect)

	# Create placeholder icon
	_create_placeholder_icon()

	# Item name
	name_label.add_theme_font_size_override("font_size", 10)
	name_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	name_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	name_label.custom_minimum_size.y = 20
	vbox.add_child(name_label)

	# Stats
	stats_container.add_theme_constant_override("separation", 1)
	vbox.add_child(stats_container)

	# Tier badge (top-right corner)
	tier_badge.size = Vector2(20, 20)
	tier_badge.position = Vector2(size.x - 25, 5)
	tier_badge.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	add_child(tier_badge)

	var tier_label = Label.new()
	tier_label.name = "TierLabel"
	tier_label.add_theme_font_size_override("font_size", 10)
	tier_label.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	tier_badge.add_child(tier_label)

func _create_placeholder_icon():
	# Create a simple colored square as placeholder
	var image = Image.create(64, 64, false, Image.FORMAT_RGBA8)
	var color = Color(0.3, 0.5, 0.8, 1.0)

	# Fill with base color
	image.fill(color)

	# Add border
	for x in range(64):
		for y in range(64):
			if x < 2 or x >= 62 or y < 2 or y >= 62:
				image.set_pixel(x, y, Color(0.2, 0.3, 0.5, 1.0))

	# Add icon letter based on category
	var texture = ImageTexture.create_from_image(image)
	icon_rect.texture = texture

func setup_item(data: Dictionary):
	item_data = data

	# Update visuals
	name_label.text = data.get("name", "Unknown")

	# Clear and rebuild stats
	for child in stats_container.get_children():
		child.queue_free()

	# Add damage stats if present
	if data.get("min_damage", 0) > 0:
		var dmg_label = Label.new()
		dmg_label.text = "⚔ %d-%d" % [data.get("min_damage"), data.get("max_damage")]
		dmg_label.add_theme_font_size_override("font_size", 9)
		dmg_label.modulate = Color(1.0, 0.6, 0.6)
		stats_container.add_child(dmg_label)

	# Add CPU cost if present
	if data.get("cpu_cost", 0) > 0:
		var cpu_label = Label.new()
		cpu_label.text = "⚡ %d CPU" % data.get("cpu_cost")
		cpu_label.add_theme_font_size_override("font_size", 9)
		cpu_label.modulate = Color(0.6, 0.8, 1.0)
		stats_container.add_child(cpu_label)

	# Add cooldown if present
	if data.get("cooldown", 0) > 0:
		var cd_label = Label.new()
		cd_label.text = "⏱ %.1fs" % data.get("cooldown")
		cd_label.add_theme_font_size_override("font_size", 9)
		cd_label.modulate = Color(0.8, 0.8, 0.8)
		stats_container.add_child(cd_label)

	# Update tier badge
	var tier_label = tier_badge.get_node("TierLabel")
	tier_label.text = "T%d" % data.get("tier", 1)

	# Apply rarity styling
	_apply_item_style()

	# Update icon color based on category
	_update_icon_for_category()

func _update_icon_for_category():
	var category = item_data.get("category", "")
	var color: Color
	var symbol: String = ""

	match category:
		"problem":
			color = Color(0.8, 0.3, 0.3, 1.0)
			symbol = "⚠"
		"defense":
			color = Color(0.3, 0.5, 0.8, 1.0)
			symbol = "🛡"
		"infrastructure":
			color = Color(0.3, 0.7, 0.3, 1.0)
			symbol = "⚙"
		_:
			color = Color(0.5, 0.5, 0.5, 1.0)
			symbol = "?"

	# Create icon with category color
	var image = Image.create(64, 64, false, Image.FORMAT_RGBA8)

	# Fill with gradient
	for x in range(64):
		for y in range(64):
			var dist = Vector2(x - 32, y - 32).length() / 32.0
			var fade = 1.0 - (dist * 0.3)
			var pixel_color = color
			pixel_color.v = pixel_color.v * fade
			image.set_pixel(x, y, pixel_color)

	# Add border
	for x in range(64):
		for y in range(64):
			if x < 2 or x >= 62 or y < 2 or y >= 62:
				image.set_pixel(x, y, color.darkened(0.3))

	var texture = ImageTexture.create_from_image(image)
	icon_rect.texture = texture

func _apply_item_style():
	var rarity = item_data.get("rarity", "common")
	var style = StyleBoxFlat.new()

	# Set border and background based on rarity
	match rarity:
		"common":
			style.bg_color = Color(0.2, 0.2, 0.25, 0.95)
			style.border_color = Color(0.6, 0.6, 0.6, 1.0)
		"uncommon":
			style.bg_color = Color(0.15, 0.25, 0.15, 0.95)
			style.border_color = Color(0.3, 0.8, 0.3, 1.0)
		"rare":
			style.bg_color = Color(0.15, 0.15, 0.3, 0.95)
			style.border_color = Color(0.3, 0.5, 1.0, 1.0)
		"epic":
			style.bg_color = Color(0.25, 0.15, 0.3, 0.95)
			style.border_color = Color(0.7, 0.3, 0.9, 1.0)
		"legendary":
			style.bg_color = Color(0.3, 0.2, 0.1, 0.95)
			style.border_color = Color(1.0, 0.7, 0.2, 1.0)
		"godly":
			style.bg_color = Color(0.3, 0.1, 0.1, 0.95)
			style.border_color = Color(1.0, 0.3, 0.3, 1.0)

	style.set_border_width_all(2)
	style.set_corner_radius_all(6)
	add_theme_stylebox_override("panel", style)

func _gui_input(event: InputEvent):
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_LEFT:
			if event.pressed:
				_start_drag(event.position)
			else:
				_end_drag()
	elif event is InputEventMouseMotion and is_dragging:
		_update_drag(event.global_position)

func _start_drag(local_pos: Vector2):
	is_dragging = true
	drag_offset = local_pos
	original_parent = get_parent()
	original_position = global_position

	# Move to viewport for dragging (stays on top)
	var viewport = get_viewport()
	original_parent.remove_child(self)
	viewport.add_child(self)

	# Keep at mouse position
	global_position = get_global_mouse_position() - drag_offset

	# Make semi-transparent while dragging
	modulate.a = 0.7

	# Disable mouse filter so it doesn't block drops
	mouse_filter = Control.MOUSE_FILTER_IGNORE

	drag_started.emit(self)

func _update_drag(global_pos: Vector2):
	if is_dragging:
		global_position = global_pos - drag_offset

		# Check what we're hovering over
		var space = get_world_2d().direct_space_state
		var params = PhysicsPointQueryParameters2D.new()
		params.position = global_pos
		params.collide_with_areas = true

		# Find slots under mouse
		var viewport = get_viewport()
		var mouse_pos = viewport.get_mouse_position()
		var control_at_pos = _get_control_at_position(mouse_pos)

		if control_at_pos and control_at_pos.has_meta("slot_type"):
			if hover_slot != control_at_pos:
				_unhighlight_slot(hover_slot)
				hover_slot = control_at_pos
				_highlight_slot(hover_slot)
		else:
			if hover_slot:
				_unhighlight_slot(hover_slot)
				hover_slot = null

func _get_control_at_position(pos: Vector2) -> Control:
	var viewport = get_viewport()

	# Get all controls at this position
	var controls = []
	_collect_controls_at_position(viewport, pos, controls)

	# Find the topmost slot
	for control in controls:
		if control != self and control.has_meta("slot_type"):
			return control

	return null

func _collect_controls_at_position(node: Node, pos: Vector2, results: Array):
	if node is Control:
		var control = node as Control
		if control.is_visible_in_tree() and control != self:
			var rect = Rect2(control.global_position, control.size)
			if rect.has_point(pos):
				results.append(control)

	for child in node.get_children():
		_collect_controls_at_position(child, pos, results)

func _highlight_slot(slot: Control):
	if not slot:
		return

	# Store original style
	if not slot.has_meta("original_style"):
		slot.set_meta("original_style", slot.get_theme_stylebox("panel"))

	# Create highlight style
	var highlight_style = StyleBoxFlat.new()
	highlight_style.bg_color = Color(0.3, 0.5, 0.8, 0.3)
	highlight_style.border_color = Color(0.5, 0.8, 1.0, 1.0)
	highlight_style.set_border_width_all(3)
	highlight_style.set_corner_radius_all(4)

	if slot is Panel:
		slot.add_theme_stylebox_override("panel", highlight_style)

func _unhighlight_slot(slot: Control):
	if not slot:
		return

	# Restore original style
	if slot.has_meta("original_style"):
		var original = slot.get_meta("original_style")
		if slot is Panel and original:
			slot.add_theme_stylebox_override("panel", original)

func _end_drag():
	if not is_dragging:
		return

	is_dragging = false
	mouse_filter = Control.MOUSE_FILTER_PASS
	modulate.a = 1.0

	# Check if we're over a valid slot
	if hover_slot:
		dropped_on_slot.emit(self, hover_slot)
		_unhighlight_slot(hover_slot)
		hover_slot = null
	else:
		# Return to original position if not dropped on valid slot
		return_to_original()

	drag_ended.emit(self)

func return_to_original():
	if original_parent:
		get_parent().remove_child(self)
		original_parent.add_child(self)
		position = Vector2.ZERO

func move_to_slot(slot: Control):
	# Remove from current parent
	if get_parent():
		get_parent().remove_child(self)

	# Add to slot
	slot.add_child(self)
	position = Vector2.ZERO

	# Resize to fit slot if needed
	if slot.has_meta("slot_size"):
		custom_minimum_size = slot.get_meta("slot_size")
		size = custom_minimum_size
