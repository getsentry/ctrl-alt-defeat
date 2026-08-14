extends Node
# Global constants for the entire game

# Grid dimensions
const ROOM_WIDTH = 9
const ROOM_HEIGHT = 7
const CELL_SIZE = 45
const CELL_SPACING = 1

# Storage dimensions
const STORAGE_WIDTH = 12
const STORAGE_HEIGHT = 2

# Game rules
const STARTING_GOLD = 12
const STARTING_LIVES = 5
const STARTING_HEALTH = 100
const MAX_PLAYER_HEALTH = 100

# Shop
const SHOP_SIZE = 5
const SHOP_REFRESH_COST = 1

# Battle
const BATTLE_MAX_DURATION = 30.0  # seconds


# Network
const API_BASE_URL = "http://localhost:8000"
const API_TIMEOUT = 10.0
const API_RETRY_COUNT = 3

# UI
const DRAG_THRESHOLD = 5  # pixels before drag starts
const ROTATION_COOLDOWN = 0.3  # seconds between rotations
const HOVER_PREVIEW_ALPHA = 0.5

# Colors
const COLOR_VALID_PLACEMENT = Color(0.3, 0.8, 0.3, 0.5)
const COLOR_INVALID_PLACEMENT = Color(0.8, 0.3, 0.3, 0.5)
const COLOR_GRID_ACTIVE = Color(0.3, 0.4, 0.5, 0.3)
const COLOR_GRID_INACTIVE = Color(0.2, 0.2, 0.2, 0.3)

# Item categories colors
const CATEGORY_COLORS = {
	"problem": Color(1.0, 0.3, 0.3),
	"defense": Color(0.3, 0.6, 1.0),
	"infrastructure": Color(0.3, 1.0, 0.3),
	"consumable": Color(1.0, 0.8, 0.3),
	"container": Color(0.6, 0.6, 0.8),
	"unknown": Color(0.5, 0.5, 0.5)
}

# Rarity colors
const RARITY_COLORS = {
	"common": Color(1.0, 1.0, 1.0),
	"uncommon": Color(0.5, 1.0, 0.5),
	"rare": Color(0.5, 0.5, 1.0),
	"epic": Color(0.8, 0.5, 1.0),
	"legendary": Color(1.0, 0.7, 0.2),
	"godly": Color(1.0, 0.3, 0.3)
}

# Round quotas (from Game Design Document)
static func get_round_quota(round: int) -> int:
	if round <= 3:
		return 25
	elif round <= 6:
		return 35
	elif round <= 9:
		return 50
	elif round <= 12:
		return 75
	elif round <= 15:
		return 100
	else:
		return 150

# Gold per round (from Game Design Document)
static func get_round_gold(round: int) -> int:
	if round <= 3:
		return 12
	elif round <= 6:
		return 14
	elif round <= 9:
		return 16
	elif round <= 12:
		return 18
	else:
		return 20

# Shop cost based on rarity
static func get_shop_cost(rarity: String, tier: int = 1) -> int:
	var base_costs = {
		"common": 3,
		"uncommon": 5,
		"rare": 8,
		"epic": 12,
		"legendary": 20,
		"godly": 30
	}
	return base_costs.get(rarity.to_lower(), 3) * tier
