extends Node

enum GameState {
	MENU,
	SHOP,
	BATTLE,
	GAME_OVER
}

var current_state: GameState = GameState.MENU
var current_round: int = 1
var player_gold: int = 10
var player_health: int = 100
var opponent_health: int = 100

signal state_changed(new_state: GameState)
signal gold_changed(new_amount: int)
signal health_changed(player_hp: int, opponent_hp: int)
signal round_complete(won: bool)

func _ready():
	pass

func start_game():
	current_round = 1
	player_gold = 10
	player_health = 100
	transition_to_shop()

func transition_to_shop():
	current_state = GameState.SHOP
	player_gold += 5 + current_round
	gold_changed.emit(player_gold)
	state_changed.emit(current_state)

func transition_to_battle():
	current_state = GameState.BATTLE
	opponent_health = 100
	state_changed.emit(current_state)

func end_battle(player_won: bool):
	if player_won:
		player_gold += 3
	else:
		player_health -= 20
		
	health_changed.emit(player_health, opponent_health)
	round_complete.emit(player_won)
	
	if player_health <= 0:
		game_over()
	else:
		current_round += 1
		transition_to_shop()

func game_over():
	current_state = GameState.GAME_OVER
	state_changed.emit(current_state)
	print("Game Over! Reached round: ", current_round)

func spend_gold(amount: int) -> bool:
	if player_gold >= amount:
		player_gold -= amount
		gold_changed.emit(player_gold)
		return true
	return false