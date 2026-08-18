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
var item_shape: Array = [[0, 0]]  # Array[Array[int]]: the [x, y] offsets it covers

# Tooltip
var tooltip_panel: Panel = null
var is_hovering: bool = false

func setup(data, size: float = 45.0, spacing: float = 1.0):
	"""Initialize the visual from an APITypes.Item or APITypes.ServerContainer"""
	item_data = data
	cell_size = size
	cell_spacing = spacing
	item_shape = data.shape

	_create_visual()

func _is_container() -> bool:
	"""A container is drawn as the ground the items sit on, not as an item.

	Both the shop's Item and the grid's ServerContainer answer this, so the
	drawing does not have to know which of the two it was handed.
	"""
	return item_data.is_container

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
	slug = item_data.slug

	# Build path based on type
	var texture_path = "res://assets/items/" + slug + ".png"
	if ResourceLoader.exists(texture_path):
		return texture_path
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
	"""Draw the item as a coloured shape, for as long as it has no artwork.

	One ItemPlaceholder draws the whole item, so the outline goes around the
	outside of the shape rather than around each of its cells.
	"""
	var placeholder = ItemPlaceholder.new()
	placeholder.setup(item_shape, _placeholder_color(), cell_size, cell_spacing)
	placeholder.size = custom_minimum_size
	add_child(placeholder)


func _placeholder_color() -> Color:
	"""The fill for an item with no artwork.

	A container keeps its own quiet colour. It is the ground the items sit on,
	and giving it one of the palette colours would make the grid too busy to
	read.
	"""
	if _is_container():
		return container_color
	return Color.html(item_data.color)

func _on_mouse_entered():
	"""Show tooltip on hover"""
	if not enable_tooltip or not item_data:
		return

	# Check if this is a server container without real item data
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

	# Load and instantiate the tooltip scene
	var tooltip_scene = preload("res://scenes/ItemTooltip.tscn")
	tooltip_panel = tooltip_scene.instantiate()
	tooltip_panel.z_index = 100  # Show above everything

	# Add to the tree first so @onready variables are initialized
	get_tree().root.add_child(tooltip_panel)

	# Setup the tooltip with item data
	tooltip_panel.setup_tooltip(item_data)

	# Let the scene determine its own size
	await get_tree().process_frame

	# The item can be freed during that wait. Everything below reads
	# get_viewport() and global_position, which are only valid inside the tree.
	if not is_inside_tree() or not is_instance_valid(tooltip_panel):
		_hide_tooltip()
		return

	tooltip_panel.size = tooltip_panel.get_combined_minimum_size()

	# Position tooltip to the left of the item to avoid covering it
	tooltip_panel.position = global_position + Vector2(-tooltip_panel.size.x - 30, 0)

	# Make sure it stays on screen
	var viewport_size = get_viewport().size

	# If tooltip would go off the left edge, show it on the right instead
	if tooltip_panel.position.x < 0:
		tooltip_panel.position.x = global_position.x + size.x + 30

	# If tooltip would go off the right edge (when positioned on the right), adjust
	if tooltip_panel.position.x + tooltip_panel.size.x > viewport_size.x:
		tooltip_panel.position.x = viewport_size.x - tooltip_panel.size.x - 10

	# Vertical positioning - center with the item, but adjust if it goes off screen
	if tooltip_panel.position.y < 0:
		tooltip_panel.position.y = 10
	if tooltip_panel.position.y + tooltip_panel.size.y > viewport_size.y:
		tooltip_panel.position.y = viewport_size.y - tooltip_panel.size.y - 10

func _hide_tooltip():
	"""Remove the tooltip"""
	# is_instance_valid, not a truthiness check: tooltip_panel can be a
	# reference to an already freed node, and calling queue_free() on that
	# takes the engine down.
	if is_instance_valid(tooltip_panel):
		tooltip_panel.queue_free()
	tooltip_panel = null

func _notification(what):
	"""Handle cleanup when node is removed"""
	# The tooltip is parented to the tree root, not to this node, so it has to
	# be taken down explicitly. Leaving the tree counts: the item is gone from
	# the screen, so its tooltip must go too.
	if what == NOTIFICATION_PREDELETE or what == NOTIFICATION_EXIT_TREE:
		_hide_tooltip()

# Static helper function for creating shop item previews
static func create_shop_preview(item_data: Dictionary, size: Vector2 = Vector2(60, 60)) -> Control:
	"""Create a simplified visual for shop display"""
	var ItemVisualClass = preload("res://scripts/item_visual.gd")
	var preview = ItemVisualClass.new()
	preview.show_border = false  # Cleaner look in shop
	preview.enable_tooltip = false  # Shop items have their own hover behavior
	preview.setup(item_data, size.x, 1)
	return preview
