extends Node
# Singleton for managing persistent game state across scenes

const APITypes = preload("res://scripts/api_types.gd")
const Combining = preload("res://scripts/combining.gd")

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

# Combining (GDD 5.3). What the rack is on the way to, and what goes with what.
var combining := Combining.new()
# What combined as this shop phase began, waiting to be played. The shop screen
# takes them, plays them and clears the list, so they are shown once.
var combinations_to_play: Array[APITypes.Combination] = []
# The rack as it fought, which is the rack before any of that combining. What
# the merge starts from; see GDD 5.3.
var rack_that_fought: APITypes.InventoryState = null

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
	combining.forget_the_rack()
	combinations_to_play.clear()
	rack_that_fought = null

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
	note_pending(session.pending)

	# Store server containers
	server_containers.clear()
	for container in session.server_containers:
		server_containers.append(container.to_dict())

	# Update current_inventory to include the server containers
	current_inventory["servers"] = server_containers.duplicate()
	# Items start empty for new session
	if not current_inventory.has("items"):
		current_inventory["items"] = []


func note_pending(waiting: Array) -> void:
	"""Hold what the server says the rack is on the way to combining.

	Every response that can change the rack carries it, so this is called from
	each of them rather than worked out here: the rules for what combines live
	on the server, and a second set of them over here would drift and start
	promising combinations that do not happen.
	"""
	var typed: Array[APITypes.Pending] = []
	typed.assign(waiting)
	combining.pending = typed


func fetch_combining_catalogue() -> void:
	"""Learn which item types go together. Asked for once a run."""
	if combining.knows_the_catalogue():
		return
	var catalogue = await BattleServerAPI.combining_catalogue()
	if catalogue != null:
		combining.catalogue = catalogue


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

	# The rack changed without the player touching it: items combine as the
	# shop phase begins (GDD 5.3). What is held here is what the shop screen
	# draws, so it has to be the rack the server just answered with and not the
	# one the player last moved something on.
	var now := response.inventory
	var grid: Array = []
	for item in now.inventory_grid:
		grid.append(item.to_dict())
	var servers: Array = []
	for container in now.server_containers:
		servers.append(container.to_dict())
	save_inventory_state(grid, servers)
	inventory_storage = now.inventory_storage

	# Kept apart so the shop screen can play the change rather than cut to it:
	# the rack that fought, then each combining, then the rack as it is now.
	rack_that_fought = response.battle_result.player_inventory
	combinations_to_play = response.session_update.combinations
	note_pending(response.session_update.pending)

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

func is_game_over() -> bool:
	return game_over or player_lives <= 0

func is_victory() -> bool:
	return victory

func update_gold(amount: int) -> bool:
	# Safely update gold with validation
	if gold + amount < 0:
		last_error = "Not enough gold"
		return false
	gold += amount
	return true
