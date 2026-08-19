extends Node
# Singleton for managing persistent game state across scenes

const APITypes = preload("res://scripts/api_types.gd")

# The run, as section 6.3 of the Game Design Document sets it out: bank this
# many wins and the run is won, spend this many tries and it is over.
const WINS_TO_VICTORY := 10
const STARTING_LIVES := 5

# Player info
var player_id: String = ""
var player_name: String = "Player"

# Game progression
var current_round: int = 1
var player_lives: int = STARTING_LIVES  # Tries left in the run
var battle_health: int = 25  # Health for the current battle (quota)
var gold: int = 12  # Start with 12 gold
var wins: int = 0
var losses: int = 0
var game_over: bool = false
var victory: bool = false

# Inventory state
var current_inventory: Dictionary = {}  # Stores placed items and servers
var server_containers: Array = []  # Array[Dictionary]: containers as plain data
# The chest. Items here are off the grid, so they have no position and the
# chest decides where to draw them.
var inventory_storage: Array[APITypes.Item] = []

# Shop state
var current_shop: Array[APITypes.Item] = []  # null in a slot whose item was bought
var shop_rerolls: int = 0

# Battle state
var last_battle_result: APITypes.BattleResult = null
var last_battle_events: Array[APITypes.BattleAction] = []
var last_gold_earned: int = 0

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
	player_lives = STARTING_LIVES
	battle_health = get_round_quota()  # Set based on round
	gold = 12  # Starting gold
	wins = 0
	losses = 0
	game_over = false
	victory = false
	current_inventory.clear()
	server_containers.clear()
	inventory_storage.clear()
	current_shop.clear()
	shop_rerolls = 0
	last_battle_result = null  # Reset to null instead of clear
	last_battle_events.clear()

# items is Array[Dictionary] and servers is Array[Dictionary], both plain data.
func save_inventory_state(items: Array, servers: Array):
	# Save the current inventory configuration
	print("DEBUG GameStateManager: Saving inventory with %d items and %d servers" % [items.size(), servers.size()])
	current_inventory = {
		"items": items.duplicate(true),
		"servers": servers.duplicate(true)
	}
	server_containers = servers.duplicate(true)

func update_from_session(session: APITypes.GameSession):
	current_round = session.round
	player_id = session.player_id
	gold = session.gold
	current_shop = session.current_shop

	inventory_storage = session.inventory_storage

	# Store server containers
	server_containers.clear()
	for container in session.server_containers:
		server_containers.append(container.to_dict())

	# Update current_inventory to include the server containers
	current_inventory["servers"] = server_containers.duplicate()
	# Items start empty for new session
	if not current_inventory.has("items"):
		current_inventory["items"] = []


func get_inventory_state() -> Dictionary:
	# Ensure we always return both items and servers
	if not current_inventory.has("servers") and server_containers.size() > 0:
		current_inventory["servers"] = server_containers.duplicate()
	if not current_inventory.has("items"):
		current_inventory["items"] = []
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

	# Store gold earned separately for PostBattleScreen
	last_gold_earned = update.gold_earned

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

func update_gold(amount: int) -> bool:
	# Safely update gold with validation
	if gold + amount < 0:
		last_error = "Not enough gold"
		return false
	gold += amount
	return true
