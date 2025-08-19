extends Node
# Manages item assets with fallback system for missing icons

const ICON_PATH = "res://assets/items/icons/"
const PLACEHOLDER_PATH = "res://assets/items/placeholders/"

var icon_cache = {}
var missing_icons = []  # Track which icons are missing for reporting

func _ready():
	# Singleton pattern
	pass

func get_item_icon(item_data: Dictionary) -> Texture:
	"""Get icon for an item, with intelligent fallbacks"""
	var icon_name = item_data.get("icon", item_data.get("item_type", "unknown"))

	# Remove file extension if present
	icon_name = icon_name.replace(".png", "").replace("res://assets/items/icons/", "")

	# Check cache first
	if icon_cache.has(icon_name):
		return icon_cache[icon_name]

	# Try loading specific icon
	var icon_path = ICON_PATH + icon_name + ".png"
	if ResourceLoader.exists(icon_path):
		icon_cache[icon_name] = load(icon_path)
		return icon_cache[icon_name]

	# Icon not found - use fallback system
	if not icon_name in missing_icons:
		missing_icons.append(icon_name)
		push_warning("Missing icon for item: " + icon_name + ", using placeholder")

	# Get fallback based on category
	var category = item_data.get("category", "unknown")
	var fallback_texture = get_category_placeholder(category)

	# Apply visual modifications to make it unique
	if item_data.has("rarity"):
		fallback_texture = apply_rarity_tint(fallback_texture, item_data.rarity)

	# Cache the generated placeholder
	icon_cache[icon_name] = fallback_texture
	return fallback_texture

func get_category_placeholder(category: String) -> Texture:
	"""Get placeholder icon for a category"""
	var placeholder_map = {
		"problem": "placeholder_problem.png",
		"defense": "placeholder_defense.png",
		"infrastructure": "placeholder_infrastructure.png",
		"consumable": "placeholder_consumable.png"
	}

	var placeholder_file = placeholder_map.get(category, "placeholder_unknown.png")
	var placeholder_path = PLACEHOLDER_PATH + placeholder_file

	if ResourceLoader.exists(placeholder_path):
		return load(placeholder_path)

	# Ultimate fallback - create a simple colored square
	return create_color_placeholder(category)

func create_color_placeholder(category: String) -> ImageTexture:
	"""Create a simple colored placeholder texture"""
	var colors = {
		"problem": Color(1.0, 0.3, 0.3),      # Red
		"defense": Color(0.3, 0.6, 1.0),      # Blue
		"infrastructure": Color(0.3, 1.0, 0.3), # Green
		"consumable": Color(1.0, 0.8, 0.3),    # Yellow
		"unknown": Color(0.5, 0.5, 0.5)        # Gray
	}

	var color = colors.get(category, colors["unknown"])

	# Create 64x64 image
	var image = Image.create(64, 64, false, Image.FORMAT_RGBA8)
	image.fill(color)

	# Add border
	for x in range(64):
		for y in range(64):
			if x < 2 or x >= 62 or y < 2 or y >= 62:
				image.set_pixel(x, y, Color(0.2, 0.2, 0.2))

	return ImageTexture.create_from_image(image)

func apply_rarity_tint(texture: Texture, rarity: String) -> Texture:
	"""Apply a subtle tint based on rarity"""
	var tints = {
		"common": Color(1.0, 1.0, 1.0),       # White (no tint)
		"uncommon": Color(0.5, 1.0, 0.5),     # Green
		"rare": Color(0.5, 0.5, 1.0),         # Blue
		"epic": Color(0.8, 0.5, 1.0),         # Purple
		"legendary": Color(1.0, 0.7, 0.2),    # Gold
		"godly": Color(1.0, 0.3, 0.3)         # Red
	}

	var tint = tints.get(rarity.to_lower(), Color.WHITE)

	if tint == Color.WHITE:
		return texture

	# For now, return texture as-is
	# In a real implementation, you'd apply the tint to the image
	return texture

func get_item_animation(item_data: Dictionary, anim_type: String) -> String:
	"""Get animation name for an item"""
	var animations = item_data.get("animations", {})

	if animations.has(anim_type):
		return animations[anim_type]

	# Fallback to category-based animation
	var category = item_data.get("category", "unknown")
	return category + "_" + anim_type

func preload_common_icons():
	"""Preload frequently used icons at startup"""
	var common_items = [
		"null_pointer",
		"memory_leak",
		"firewall",
		"error_monitoring",
		"health_check"
	]

	for item_name in common_items:
		var path = ICON_PATH + item_name + ".png"
		if ResourceLoader.exists(path):
			icon_cache[item_name] = load(path)

func get_missing_icons() -> Array:
	"""Get list of icons that were requested but not found"""
	return missing_icons

func clear_cache():
	"""Clear the icon cache (useful for development)"""
	icon_cache.clear()
	missing_icons.clear()
