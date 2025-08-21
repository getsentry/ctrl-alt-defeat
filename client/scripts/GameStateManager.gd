extends Node
# Singleton for managing persistent game state across scenes

const APITypes = preload("res://scripts/api_types.gd")

# Player info
var player_id: String = ""
var player_name: String = "Player"

# Game progression
var current_round: int = 1
var player_lives: int = 5  # Player has 5 lives/tries
var player_health: int = 100  # Player's health (different from lives)
var max_player_health: int = 100  # Maximum player health
var battle_health: int = 25  # Health for the current battle (quota)
var gold: int = 12  # Start with 12 gold
var wins: int = 0
var losses: int = 0
var game_over: bool = false
var victory: bool = false

# Inventory state
var current_inventory: Dictionary = {}  # Stores placed items and servers
var server_containers: Array = []  # Server rack configurations
var starting_containers: Array = []  # Starting containers for new games

# Shop state
var current_shop: Array = []
var shop_rerolls: int = 0

# Battle state
var last_battle_result = null  # Can be Dictionary or APITypes.BattleResult
var last_battle_events: Array = []
var opponent_inventory: Dictionary = {}

# Settings
var battle_speed: float = 1.0  # Speed multiplier for battle playback
var auto_ready: bool = false  # Auto-submit for battle when ready

# Server integration
var session_id: String = ""
var last_error: String = ""
var is_connected: bool = false

func _ready():
	# Make this a singleton
	process_mode = Node.PROCESS_MODE_ALWAYS

func start_new_game():
	# Reset all game state
	player_id = ""
	session_id = ""
	last_error = ""
	is_connected = false
	current_round = 1
	player_lives = 5
	player_health = 100  # Reset player health
	max_player_health = 100
	battle_health = get_round_quota()  # Set based on round
	gold = 12  # Starting gold
	wins = 0
	losses = 0
	game_over = false
	victory = false
	current_inventory.clear()
	server_containers.clear()
	starting_containers.clear()
	current_shop.clear()
	shop_rerolls = 0
	last_battle_result = null  # Reset to null instead of clear
	last_battle_events.clear()
	opponent_inventory.clear()

func save_inventory_state(items: Array, servers: Array):
	# Save the current inventory configuration
	current_inventory = {
		"items": items.duplicate(true),
		"servers": servers.duplicate(true)
	}
	server_containers = servers.duplicate(true)

func get_inventory_state() -> Dictionary:
	return current_inventory

func update_after_battle(response: APITypes.BattleResponse):
	# Store the COMPLETE battle response for PostBattle screen
	last_battle_result = response.battle_result
	current_shop = response.new_shop

	# Update from typed SessionUpdate
	var update = response.session_update
	current_round = update.round
	gold = update.gold
	wins = update.wins
	losses = update.losses
	player_lives = update.lives
	game_over = update.game_over
	victory = update.victory

	# Store battle actions directly as typed objects from battle_result
	last_battle_events = response.battle_result.actions

	# Update battle health for next round
	battle_health = get_round_quota()

func is_game_over() -> bool:
	return game_over or player_lives <= 0

func is_victory() -> bool:
	return victory

func get_round_quota() -> int:
	# Get quota (enemy health) based on round number
	# From Game Design Document section 1.1
	if current_round <= 3:
		return 25
	elif current_round <= 6:
		return 35
	elif current_round <= 9:
		return 50
	elif current_round <= 12:
		return 75
	elif current_round <= 15:
		return 100
	else:
		return 150

func get_gold_per_round() -> int:
	# Get gold reward based on round
	# From Game Design Document section 5.1
	if current_round <= 3:
		return 12
	elif current_round <= 6:
		return 14
	elif current_round <= 9:
		return 16
	elif current_round <= 12:
		return 18
	else:
		return 20

func calculate_health_loss(enemy_remaining_hp: int) -> int:
	# Calculate health loss based on remaining enemy HP
	# Simple formula: 10 base + % of remaining enemy HP
	var base_loss = 10
	var percent_loss = int(enemy_remaining_hp * 0.2)  # 20% of remaining HP
	return min(base_loss + percent_loss, 20)  # Cap at 20 damage

func update_gold(amount: int) -> bool:
	# Safely update gold with validation
	if gold + amount < 0:
		last_error = "Not enough gold"
		return false
	gold += amount
	return true
