extends Node
# Mock server API for battle simulation
# Later can be replaced with real HTTP calls to Python server

signal session_started(data: Dictionary)
signal battle_completed(result: Dictionary)
signal shop_refreshed(items: Array)

# Mock server state
var mock_session_id: String = ""
var mock_round: int = 1

# Action codes from server (matching Python ACTION_CODES)
const ACTION_CODES = {
	"START": "s",
	"ACTIVATE": "a",
	"DAMAGE": "d",
	"MISS": "m",
	"CRIT": "c",
	"HEAL": "h",
	"BLOCK": "b",
	"CPU_FAIL": "cf",
	"BUFF": "bf",
	"DEBUFF": "df",
	"DOT": "dt",
	"REFLECT": "r",
	"DEATH": "x"
}

func start_session() -> Dictionary:
	# Mock starting a new game session
	mock_session_id = _generate_uuid()
	mock_round = 1

	var initial_shop = _generate_mock_shop(1)

	# Starting containers - 3 adjacent 2x2 containers
	var starting_containers = [
		{"type": "cube_2x2", "position": Vector2i(1, 3)},
		{"type": "cube_2x2", "position": Vector2i(3, 3)},
		{"type": "cube_2x2", "position": Vector2i(5, 3)}
	]

	var response = {
		"player_id": mock_session_id,
		"round": 1,
		"gold": 10,
		"current_shop": initial_shop,
		"starting_containers": starting_containers,
		"item_catalog": _get_item_catalog()
	}

	session_started.emit(response)
	return response

func submit_battle(inventory: Dictionary) -> Dictionary:
	# Mock battle simulation
	# In real implementation, this would send to Python server
	await get_tree().create_timer(0.1).timeout  # Simulate network delay

	var battle_result = _simulate_mock_battle(inventory)
	var gold_earned = _calculate_gold_reward(mock_round, battle_result.winner == 1)

	mock_round += 1

	var response = {
		"battle_result": battle_result,
		"session_update": {
			"round": mock_round,
			"gold": GameStateManager.gold + gold_earned,
			"gold_earned": gold_earned,
			"wins": GameStateManager.wins + (1 if battle_result.winner == 1 else 0),
			"losses": GameStateManager.losses + (0 if battle_result.winner == 1 else 1)
		},
		"new_shop": _generate_mock_shop(mock_round),
		"battle_id": _generate_uuid()
	}

	# Calculate health loss if player lost
	if battle_result.winner == 2:
		response["health_lost"] = GameStateManager.calculate_health_loss(battle_result.player2_quota)
	else:
		response["health_lost"] = 0

	battle_completed.emit(response)
	return response

func refresh_shop(player_id: String, round_num: int) -> Array:
	# Mock shop refresh
	var new_shop = _generate_mock_shop(round_num)
	shop_refreshed.emit(new_shop)
	return new_shop

func _simulate_mock_battle(inventory: Dictionary) -> Dictionary:
	# Generate mock battle events
	var events = []
	var current_time = 0.0
	var player1_hp = GameStateManager.get_round_quota()
	var player2_hp = GameStateManager.get_round_quota()
	var max_duration = 20.0  # 20 second battles max

	# Battle start event
	events.append({"t": 0.0, "a": ACTION_CODES.START})

	# Simulate some combat events
	while current_time < max_duration and player1_hp > 0 and player2_hp > 0:
		current_time += randf_range(0.5, 2.0)

		# Random event type
		var event_type = randi() % 4

		if event_type == 0:  # Player attacks
			var damage = randi_range(3, 8)
			events.append({
				"t": current_time,
				"a": ACTION_CODES.ACTIVATE,
				"item": "player_item_" + str(randi() % 3),
				"p": 1
			})
			events.append({
				"t": current_time + 0.1,
				"a": ACTION_CODES.DAMAGE,
				"p": 2,
				"dmg": damage,
				"hp": max(0, player2_hp - damage)
			})
			player2_hp -= damage

		elif event_type == 1:  # Enemy attacks
			var damage = randi_range(2, 6)
			events.append({
				"t": current_time,
				"a": ACTION_CODES.ACTIVATE,
				"item": "enemy_item_" + str(randi() % 3),
				"p": 2
			})
			events.append({
				"t": current_time + 0.1,
				"a": ACTION_CODES.DAMAGE,
				"p": 1,
				"dmg": damage,
				"hp": max(0, player1_hp - damage)
			})
			player1_hp -= damage

		elif event_type == 2:  # Block
			events.append({
				"t": current_time,
				"a": ACTION_CODES.BLOCK,
				"p": randi() % 2 + 1,
				"amount": randi_range(2, 5)
			})

		else:  # Heal
			var heal_target = randi() % 2 + 1
			var heal_amount = randi_range(2, 4)
			if heal_target == 1:
				player1_hp = min(player1_hp + heal_amount, GameStateManager.get_round_quota())
			else:
				player2_hp = min(player2_hp + heal_amount, GameStateManager.get_round_quota())
			events.append({
				"t": current_time,
				"a": ACTION_CODES.HEAL,
				"p": heal_target,
				"amount": heal_amount,
				"hp": player1_hp if heal_target == 1 else player2_hp
			})

	# Death event if someone died
	if player1_hp <= 0:
		events.append({"t": current_time, "a": ACTION_CODES.DEATH, "p": 1})
	elif player2_hp <= 0:
		events.append({"t": current_time, "a": ACTION_CODES.DEATH, "p": 2})

	return {
		"winner": 1 if player1_hp > player2_hp else 2,
		"duration": current_time,
		"player1_quota": max(0, player1_hp),
		"player2_quota": max(0, player2_hp),
		"actions": events,
		"seed": randi()
	}

func _generate_mock_shop(round_num: int) -> Array:
	# Generate 5 mock shop items
	var shop = []
	var item_types = ["Memory Leak", "Null Pointer", "Race Condition", "Buffer Overflow",
					  "Error Monitor", "Load Balancer", "Redis Cache", "Firewall",
					  "Health Potion", "CPU Booster"]

	for i in range(5):
		if randf() > 0.2:  # 80% chance of item, 20% empty slot
			shop.append({
				"id": _generate_uuid(),
				"name": item_types[randi() % item_types.size()],
				"cost": randi_range(3, 8) + round_num,
				"category": ["problem", "defense", "infrastructure", "consumable"][randi() % 4],
				"description": "A useful item for battle"
			})
		else:
			shop.append(null)  # Empty slot

	return shop

func _calculate_gold_reward(round_num: int, won: bool) -> int:
	# Calculate gold based on round (same win or lose in our design)
	if round_num <= 3:
		return 12
	elif round_num <= 6:
		return 14
	elif round_num <= 9:
		return 16
	elif round_num <= 12:
		return 18
	else:
		return 20

func _get_item_catalog() -> Dictionary:
	# Return simplified item catalog for client
	return {
		"Memory Leak": {
			"name": "Memory Leak",
			"category": "problem",
			"base_damage": [2, 4],
			"cooldown": 3.0,
			"cpu_cost": 2,
			"description": "Damage increases each activation"
		},
		"Null Pointer": {
			"name": "Null Pointer Exception",
			"category": "problem",
			"base_damage": [4, 8],
			"cooldown": 2.5,
			"cpu_cost": 3,
			"description": "20% chance to crash for 15 damage"
		},
		"Error Monitor": {
			"name": "Error Monitoring",
			"category": "defense",
			"block_amount": 8,
			"description": "30% chance to block attacks"
		},
		"Load Balancer": {
			"name": "Load Balancer",
			"category": "infrastructure",
			"cpu_bonus": 5,
			"description": "+5 max CPU"
		}
	}

func _generate_uuid() -> String:
	# Simple UUID generation
	var chars = "0123456789abcdef"
	var uuid = ""
	for i in range(8):
		uuid += chars[randi() % chars.length()]
	return uuid
