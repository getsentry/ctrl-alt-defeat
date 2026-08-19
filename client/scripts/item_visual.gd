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
## Whether the tooltip should say what the shop charges. Only a shelf sets it.
var tooltip_shows_price: bool = false
## What the tooltip stands beside, when that is not the artwork itself. A shelf
## is a slot much wider than the picture in it, and a card measured from the
## picture ends up drawn across the rest of the slot.
var tooltip_anchor: Control = null

# Item data
var item_data
var item_shape: Array = [[0, 0]]  # Array[Array[int]]: the [x, y] offsets it covers

# Tooltip
var tooltip_panel: ItemTooltip = null
var is_hovering: bool = false

# What the item is doing right now, as opposed to what it is.
var _cooldown: Cooldown = null
var _fire_tween: Tween = null

func setup(data, size: float = 45.0, spacing: float = 1.0):
	"""Initialize the visual from an APITypes.Item"""
	item_data = data
	cell_size = size
	cell_spacing = spacing
	# Turned, if it is facing anywhere but its default.
	item_shape = data.turned_shape()

	_create_visual()

func redraw_as(data) -> void:
	"""Draw this again for an item that has changed.

	Turning one is a redraw: it covers different squares. The size it is drawn
	at is already known here, so a caller does not have to carry it about.
	"""
	setup(data, cell_size, cell_spacing)


func _is_container() -> bool:
	"""A container is drawn as the ground the items sit on, not as an item.

	A container is an item that provides squares rather than filling them,
	and it says so whether it is still in the shop or already on the grid.
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

	# Set up input handling for tooltip. Drawn again whenever the item changes
	# -- turning one is a redraw -- so the connection is made once and not once
	# per redraw.
	if enable_tooltip:
		mouse_filter = Control.MOUSE_FILTER_PASS
		if not mouse_entered.is_connected(_on_mouse_entered):
			mouse_entered.connect(_on_mouse_entered)
		if not mouse_exited.is_connected(_on_mouse_exited):
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
	placeholder.setup(item_shape, _placeholder_color(), cell_size, cell_spacing,
		_placeholder_pattern(), _placeholder_category())
	placeholder.size = custom_minimum_size
	add_child(placeholder)


func _placeholder_pattern() -> String:
	"""The pattern name for an item with no artwork.

	A container has none. It is the ground the items stand on, and a pattern
	there would fight with the items standing on it.
	"""
	if _is_container():
		return ""
	return item_data.pattern


func _placeholder_category() -> String:
	"""The category whose icon this item wears.

	A container wears none. It is the ground, and an icon on it would compete
	with the items standing on top.
	"""
	if _is_container():
		return ""
	return item_data.category


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
	hover_started()

func _on_mouse_exited():
	"""Hide tooltip when mouse leaves"""
	hover_ended()


func hover_started() -> void:
	"""The pointer has come to rest on this item.

	Public because the artwork is not always what the pointer meets: a shelf is
	a whole panel around a small picture, and hovering anywhere on it should
	read the item, not just the few squares the picture covers.
	"""
	if not enable_tooltip or not item_data:
		return
	is_hovering = true
	_show_tooltip()


func hover_ended() -> void:
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
	tooltip_panel.show_price = tooltip_shows_price
	tooltip_panel.setup_tooltip(item_data)

	# Let the scene determine its own size
	await get_tree().process_frame

	# The item can be freed during that wait. Everything below reads
	# get_viewport() and global_position, which are only valid inside the tree.
	if not is_inside_tree() or not is_instance_valid(tooltip_panel):
		_hide_tooltip()
		return

	tooltip_panel.size = tooltip_panel.get_combined_minimum_size()

	# Beside the item and level with the middle of it, so the card reads as
	# belonging to the thing under the pointer rather than to the row above it.
	var beside := _tooltip_anchor_rect()
	tooltip_panel.position = Vector2(
		beside.position.x - tooltip_panel.size.x - 24,
		beside.get_center().y - tooltip_panel.size.y / 2.0
	)

	# Make sure it stays on screen
	var viewport_size = get_viewport().size

	# If tooltip would go off the left edge, show it on the right instead
	if tooltip_panel.position.x < 0:
		tooltip_panel.position.x = beside.end.x + 24

	# If tooltip would go off the right edge (when positioned on the right), adjust
	if tooltip_panel.position.x + tooltip_panel.size.x > viewport_size.x:
		tooltip_panel.position.x = viewport_size.x - tooltip_panel.size.x - 10

	# Vertical positioning - center with the item, but adjust if it goes off screen
	if tooltip_panel.position.y < 0:
		tooltip_panel.position.y = 10
	if tooltip_panel.position.y + tooltip_panel.size.y > viewport_size.y:
		tooltip_panel.position.y = viewport_size.y - tooltip_panel.size.y - 10

func _tooltip_anchor_rect() -> Rect2:
	"""What the tooltip has to stand clear of"""
	if is_instance_valid(tooltip_anchor) and tooltip_anchor.is_inside_tree():
		return tooltip_anchor.get_global_rect()
	return Rect2(global_position, size)


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


# ============ Firing ============

## How much bigger an item gets at the top of its swell.
const FIRE_SCALE := 1.35
const FIRE_UP := 0.07
const FIRE_DOWN := 0.16


func fire(cooldown_seconds: float = 0.0) -> void:
	"""Mark that this item just went off.

	It swells and settles, and if it has a cooldown it goes dark and fills back
	up over it. Between them they say which item is carrying a build, which is
	the question a player watching a battle is actually asking - the log says
	it too, but not fast enough to watch.
	"""
	_swell()
	if cooldown_seconds > 0.0:
		_start_cooldown(cooldown_seconds)


func _swell() -> void:
	# From the middle, not the corner, or a growing item slides as it grows.
	pivot_offset = size / 2.0
	if _fire_tween != null and _fire_tween.is_valid():
		_fire_tween.kill()
	scale = Vector2.ONE

	_fire_tween = create_tween()
	_fire_tween.tween_property(self, "scale", Vector2(FIRE_SCALE, FIRE_SCALE), FIRE_UP) \
		.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	_fire_tween.tween_property(self, "scale", Vector2.ONE, FIRE_DOWN) \
		.set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)


func _start_cooldown(seconds: float) -> void:
	if _cooldown == null:
		_cooldown = Cooldown.new()
		_cooldown.mouse_filter = Control.MOUSE_FILTER_IGNORE
		# Over the artwork, under the tooltip.
		_cooldown.z_index = 1
		add_child(_cooldown)
	_cooldown.size = size
	_cooldown.run(seconds)


func is_cooling() -> bool:
	return _cooldown != null and _cooldown.filling


## The dark that covers an item while it is not ready, retreating downwards as
## the cooldown runs out.
##
## Drawn from the top so the lit part grows from the bottom up, which reads as
## filling rather than draining. An item ready to go is not covered at all.
class Cooldown extends Control:
	const DARK := Color(0.02, 0.02, 0.07, 0.72)

	var filling: bool = false
	var _left: float = 0.0
	var _total: float = 0.0

	func run(seconds: float) -> void:
		_total = maxf(seconds, 0.01)
		_left = _total
		filling = true
		set_process(true)
		queue_redraw()

	func _ready() -> void:
		set_process(false)

	func _process(delta: float) -> void:
		_left -= delta
		if _left <= 0.0:
			_left = 0.0
			filling = false
			set_process(false)
		queue_redraw()

	func _draw() -> void:
		if not filling:
			return
		var covered := size.y * (_left / _total)
		draw_rect(Rect2(Vector2.ZERO, Vector2(size.x, covered)), DARK)
		# A line at the waterline, so the movement is visible on a small item.
		draw_line(Vector2(0, covered), Vector2(size.x, covered),
			Color(0.6, 0.9, 1.0, 0.5), 1.0)
