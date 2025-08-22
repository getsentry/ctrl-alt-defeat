extends Control
class_name ItemVisual

const APITypes = preload("res://scripts/api_types.gd")

# Reusable class for rendering items and containers with textures or fallback colors

# Visual settings
var cell_size: float = 45.0
var cell_spacing: float = 1.0
var item_color: Color = Color(0.2, 0.5, 1.0, 1.0)  # Full opacity for items
var container_color: Color = Color(0.3, 0.4, 0.5, 0.3)  # Transparent for containers
var border_color: Color = Color(0.4, 0.7, 1.0, 1.0)
var show_border: bool = false  # No border by default - cleaner look
var enable_tooltip: bool = false  # Tooltip disabled by default

# Item data
var item_data
var item_shape: Array = [[0, 0]]  # Default single cell

# Tooltip
var tooltip_panel: Panel = null
var is_hovering: bool = false

func setup(data, size: float = 45.0, spacing: float = 1.0):
	"""Initialize the item visual with data"""
	item_data = data
	cell_size = size
	cell_spacing = spacing

	# Extract shape
	if data is Dictionary:
		item_shape = data.get("shape", [[0, 0]])
	elif "shape" in data:
		item_shape = data.shape
	else:
		item_shape = [[0, 0]]

	_create_visual()

func _create_visual():
	"""Create the item visual representation"""
	# Clear existing children
	for child in get_children():
		child.queue_free()

	# Calculate size from shape
	var max_x = 0
	var max_y = 0
	for offset in item_shape:
		if offset is Array and offset.size() >= 2:
			max_x = max(max_x, offset[0])
			max_y = max(max_y, offset[1])

	var width = max_x + 1
	var height = max_y + 1
	var calculated_size = Vector2(
		width * (cell_size + cell_spacing) - cell_spacing,
		height * (cell_size + cell_spacing) - cell_spacing
	)
	custom_minimum_size = calculated_size
	size = calculated_size
	# Ensure we clip children to our bounds so textures don't overflow
	clip_contents = true
	mouse_filter = Control.MOUSE_FILTER_PASS  # Allow mouse events to pass through

	# Try to get texture path
	var texture_path = _get_texture_path()

	if texture_path and ResourceLoader.exists(texture_path):
		_create_texture_visual(texture_path)
	else:
		_create_colored_visual()

	# Set up input handling for tooltip
	if enable_tooltip:
		mouse_filter = Control.MOUSE_FILTER_PASS
		mouse_entered.connect(_on_mouse_entered)
		mouse_exited.connect(_on_mouse_exited)

func _get_texture_path() -> String:
	"""Get the texture path for this item based on slug"""
	# Get the slug from the data
	var slug = ""
	if item_data is APITypes.InventoryItem:
		slug = item_data.slug
		print("ItemVisual: Got slug '%s' from InventoryItem" % slug)
	elif item_data is Dictionary:
		slug = item_data["slug"]
		print("ItemVisual: Got slug '%s' from Dictionary" % slug)
	else:
		push_error("Unknown item_data type: " + str(typeof(item_data)))
		return ""

	# Check if it's a container/server
	var is_container = false
	if item_data is Dictionary:
		is_container = item_data.get("is_container", false) or item_data.get("type", "") == "server"
	elif "is_container" in item_data:
		is_container = item_data.is_container

	# Build path based on type
	var texture_path = "res://assets/items/" + slug + ".png"
	print("ItemVisual: Looking for texture at: %s" % texture_path)

	# Check if the file exists
	if ResourceLoader.exists(texture_path):
		print("ItemVisual: Texture found!")
		return texture_path

	print("ItemVisual: Texture not found, will use colored visual")
	return ""

func _create_texture_visual(texture_path: String):
	"""Create visual using texture"""
	var texture = load(texture_path)
	if not texture:
		push_error("Failed to load texture: " + texture_path)
		_create_colored_visual()  # Fallback to colored visual
		return

	var texture_rect = TextureRect.new()
	texture_rect.texture = texture

	# Calculate scale factor to fit the texture in our cell size
	var texture_size = texture.get_size()
	var scale_x = custom_minimum_size.x / texture_size.x
	var scale_y = custom_minimum_size.y / texture_size.y
	var scale_factor = min(scale_x, scale_y)  # Use smaller scale to fit

	# Apply the scale
	texture_rect.scale = Vector2(scale_factor, scale_factor)

	# Calculate scaled size for centering
	var scaled_size = texture_size * scale_factor

	# Center the texture within the cell
	var center_offset = (custom_minimum_size - scaled_size) / 2.0
	texture_rect.position = center_offset
	texture_rect.size = texture_size  # Keep original size, let scale handle it
	texture_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(texture_rect)

	# Add subtle background/border for better visibility
	if show_border:
		var bg = Panel.new()
		bg.size = custom_minimum_size
		bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
		bg.show_behind_parent = true
		var bg_style = StyleBoxFlat.new()
		bg_style.bg_color = Color(0.1, 0.1, 0.15, 0.3)
		bg_style.border_color = border_color
		bg_style.set_border_width_all(2)
		bg_style.set_corner_radius_all(4)
		bg.add_theme_stylebox_override("panel", bg_style)
		add_child(bg)
		move_child(bg, 0)  # Move background behind texture

func _create_colored_visual():
	"""Create visual using colored cells (fallback)"""
	# Determine if this is a container
	var is_container = false
	if item_data is Dictionary:
		is_container = item_data.get("is_container", false) or item_data.get("type", "") == "server"
	elif "is_container" in item_data:
		is_container = item_data.is_container

	# Use different colors for containers vs items
	var color_to_use = container_color if is_container else item_color

	for offset in item_shape:
		if offset is Array and offset.size() >= 2:
			var cell = Panel.new()
			cell.position = Vector2(
				offset[0] * (cell_size + cell_spacing),
				offset[1] * (cell_size + cell_spacing)
			)
			cell.size = Vector2(cell_size, cell_size)
			cell.mouse_filter = Control.MOUSE_FILTER_IGNORE

			var style = StyleBoxFlat.new()
			style.bg_color = color_to_use
			style.border_color = border_color
			style.set_border_width_all(2)
			style.set_corner_radius_all(4)
			cell.add_theme_stylebox_override("panel", style)
			add_child(cell)

func _on_mouse_entered():
	"""Show tooltip on hover"""
	if not enable_tooltip or not item_data:
		return

	is_hovering = true
	_show_tooltip()

func _on_mouse_exited():
	"""Hide tooltip when mouse leaves"""
	is_hovering = false
	_hide_tooltip()

func _show_tooltip():
	"""Create and display the tooltip"""
	if tooltip_panel:
		return  # Already showing

	# Create tooltip panel
	tooltip_panel = Panel.new()
	tooltip_panel.z_index = 100  # Show above everything
	tooltip_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE

	# Style the tooltip
	var style = StyleBoxFlat.new()
	style.bg_color = Color(0.1, 0.1, 0.15, 0.95)
	style.border_color = Color(0.4, 0.7, 1.0, 1.0)
	style.set_border_width_all(2)
	style.set_corner_radius_all(4)
	tooltip_panel.add_theme_stylebox_override("panel", style)

	# Create content
	var vbox = VBoxContainer.new()
	vbox.position = Vector2(8, 8)

	# Item name
	var name_label = Label.new()
	var item_name = ""
	if item_data is Dictionary:
		item_name = item_data.get("name", item_data.get("item_type", "Unknown"))
	elif "name" in item_data:
		item_name = item_data.name
	elif "item_type" in item_data:
		item_name = item_data.item_type

	name_label.text = item_name
	name_label.add_theme_font_size_override("font_size", 14)
	name_label.add_theme_color_override("font_color", Color(1.0, 0.85, 0.3))
	vbox.add_child(name_label)

	# Category/Type
	var category = ""
	if item_data is Dictionary:
		category = item_data.get("category", "")
	elif "category" in item_data:
		category = item_data.category

	if category:
		var category_label = Label.new()
		category_label.text = category.capitalize()
		category_label.add_theme_font_size_override("font_size", 11)
		category_label.add_theme_color_override("font_color", Color(0.7, 0.7, 0.8))
		vbox.add_child(category_label)

	# Effects/Description (if available)
	var description = ""
	if item_data is Dictionary:
		description = item_data.get("description", item_data.get("effect", ""))
	elif "description" in item_data:
		description = item_data.description
	elif "effect" in item_data:
		description = item_data.effect

	if description:
		var desc_label = Label.new()
		desc_label.text = description
		desc_label.add_theme_font_size_override("font_size", 10)
		desc_label.add_theme_color_override("font_color", Color(0.8, 0.8, 0.9))
		desc_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		desc_label.custom_minimum_size.x = 200
		vbox.add_child(desc_label)

	tooltip_panel.add_child(vbox)

	# Size the tooltip
	tooltip_panel.custom_minimum_size = vbox.get_combined_minimum_size() + Vector2(16, 16)
	tooltip_panel.size = tooltip_panel.custom_minimum_size

	# Position tooltip above the item
	tooltip_panel.position = global_position + Vector2(0, -tooltip_panel.size.y - 10)

	# Make sure it stays on screen
	var viewport_size = get_viewport().size
	if tooltip_panel.position.x + tooltip_panel.size.x > viewport_size.x:
		tooltip_panel.position.x = viewport_size.x - tooltip_panel.size.x - 10
	if tooltip_panel.position.y < 0:
		tooltip_panel.position.y = global_position.y + size.y + 10  # Show below instead

	# Add to the root so it appears above everything
	get_tree().root.add_child(tooltip_panel)

func _hide_tooltip():
	"""Remove the tooltip"""
	if tooltip_panel:
		tooltip_panel.queue_free()
		tooltip_panel = null

func _notification(what):
	"""Handle cleanup when node is removed"""
	if what == NOTIFICATION_PREDELETE:
		_hide_tooltip()

func _refresh_visual():
	"""Refresh the visual after color changes"""
	_create_visual()

func get_item_data():
	"""Get the item data associated with this visual"""
	return item_data

# Static helper function for creating shop item previews
static func create_shop_preview(item_data: Dictionary, size: Vector2 = Vector2(60, 60)) -> Control:
	"""Create a simplified visual for shop display"""
	var ItemVisualClass = preload("res://scripts/ItemVisual.gd")
	var preview = ItemVisualClass.new()
	preview.show_border = false  # Cleaner look in shop
	preview.enable_tooltip = false  # Shop items have their own hover behavior
	preview.setup(item_data, size.x, 1)
	return preview
