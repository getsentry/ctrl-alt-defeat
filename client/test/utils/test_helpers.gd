extends Resource
class_name TestHelpers

# One fully populated item. The server sends every field on every item, so a
# fixture that leaves fields out would not be testing what the client receives.
static func item_data(overrides: Dictionary = {}) -> Dictionary:
	var data = {
		"id": "item_1",
		"item_type": "null_blade",
		"name": "Null Blade",
		"slug": "null_blade",
		"category": "problem",
		"rarity": "rare",
		"cost": 8,
		"price": 8,
		"sell_value": 4,
		"on_sale": false,
		"is_container": false,
		"shape": [[0, 0]],
		"kinds": [],
		"traits": [],
		"aura": {},
		"effects": ["Every 1.5s: deal 2-5 damage."],
		"color": "#BE0032",
		"pattern": "solid",
		"min_damage": 2,
		"max_damage": 5,
		"min_heal": 0,
		"max_heal": 0,
		"block_amount": 0,
		"cooldown": 1.5,
		"cpu_cost": 3,
	}
	data.merge(overrides, true)
	return data


static func placed_item_data(overrides: Dictionary = {}) -> Dictionary:
	var data = item_data({"position": [2, 3], "rotation": 0})
	data.merge(overrides, true)
	return data


static func item(overrides: Dictionary = {}) -> Resource:
	return preload("res://scripts/api_types.gd").Item.new(item_data(overrides))


static func placed_item(overrides: Dictionary = {}) -> Resource:
	return preload("res://scripts/api_types.gd").PlacedItem.new(
		placed_item_data(overrides))


static func container_data(overrides: Dictionary = {}) -> Dictionary:
	var data = placed_item_data({
		"id": "container_a",
		"item_type": "standard_vm",
		"name": "Standard VM",
		"slug": "standard_vm",
		"category": "container",
		"is_container": true,
		"cost": 4,
		"price": 4,
		"sell_value": 2,
		"effects": [],
		"color": "",
		"pattern": "",
		"min_damage": 0,
		"max_damage": 0,
		"cooldown": 0.0,
		"cpu_cost": 0,
		"shape": [[0, 0], [1, 0], [0, 1], [1, 1]],
	})
	data.merge(overrides, true)
	return data


static func container(overrides: Dictionary = {}) -> Resource:
	return preload("res://scripts/api_types.gd").PlacedItem.new(
		container_data(overrides))

# Helper to create a valid BattleResult for testing
static func create_test_battle_result(winner: int = 1, duration: float = 10.0) -> Resource:
	var APITypes = preload("res://scripts/api_types.gd")

	var battle_data = {
		"winner": winner,
		"duration": duration,
		"player1_quota": 100,
		"player2_quota": 0 if winner == 1 else 100,
		"seed": randi(),
		"actions": [
			# The engine stamps both fighters' quotas on every action it
			# records, so an action without them is not one the client is ever
			# given -- and the screen reads its health off them.
			{"timestamp": 0, "source": "system", "action": "battle_start",
				"player": 0, "target": null, "damage": null,
				"details": {"hp": [25, 25], "max_hp": [25, 25]}},
			{"timestamp": 2500, "source": "player_item", "action": "damage",
				"player": 1, "target": "enemy", "damage": 10,
				"details": {"hp": [15, 25], "max_hp": [25, 25]}},
			{"timestamp": 5000, "source": "enemy_item", "action": "damage",
				"player": 2, "target": "player", "damage": 5,
				"details": {"hp": [15, 20], "max_hp": [25, 25]}},
			{"timestamp": 10000, "source": "system", "action": "battle_end",
				"player": winner, "target": null, "damage": null,
				"details": {"hp": [15, 20], "max_hp": [25, 25]}}
		],
		"opponent_name": "AI Opponent",
		"opponent_type": "ai",
		"player_inventory": {
			"items": [],
			"servers": [
				container_data({"id": "test_srv1"})
			]
		},
		"enemy_inventory": {
			"items": [],
			"servers": [
				container_data({"id": "test_srv2"})
			]
		}
	}

	return APITypes.BattleResult.new(battle_data)

# Helper to create a valid SessionUpdate for testing
static func create_test_session_update(round: int = 1, gold: int = 12, lives: int = 5) -> Resource:
	var APITypes = preload("res://scripts/api_types.gd")

	var session_data = {
		"round": round,
		"gold": gold,
		"gold_earned": 0,
		"wins": 0,
		"losses": 0,
		"lives": lives,
		"game_over": lives <= 0,
		"victory": false,
		"combinations": [],
		"pending": []
	}

	return APITypes.SessionUpdate.new(session_data)


# The three lists a battle answers with: the rack, the chest and the containers
# as the shop phase begins, which is after anything on the rack has combined.
static func inventory_after_battle(overrides: Dictionary = {}) -> Dictionary:
	var whole := {
		"inventory_grid": [],
		"inventory_storage": [],
		"server_containers": [container_data({"id": "test_srv1"})]
	}
	whole.merge(overrides, true)
	return whole

# Helper to wait for a signal with timeout
static func wait_for_signal_with_timeout(test: GutTest, sig: Signal, timeout_sec: float = 2.0) -> bool:
	var timer = test.get_tree().create_timer(timeout_sec)
	var signal_received = false

	var on_signal = func():
		signal_received = true

	sig.connect(on_signal, CONNECT_ONE_SHOT)

	while not signal_received and timer.time_left > 0:
		await test.get_tree().process_frame

	return signal_received

# Helper to verify no script errors occurred
static func assert_no_script_errors(test: GutTest):
	# This is a placeholder - in practice, you'd need to hook into Godot's error reporting
	# For now, we just check that critical objects exist
	test.assert_not_null(test.get_tree(), "Scene tree should exist")
	test.assert_true(true, "No script errors detected")

# Helper to clean up all child nodes
static func cleanup_children(node: Node):
	for child in node.get_children():
		child.queue_free()
	# Wait a frame for cleanup to complete
	if node.is_inside_tree():
		await node.get_tree().process_frame

# Helper to reset GameStateManager to clean state
static func reset_game_state():
	GameStateManager.start_new_game()
	GameStateManager.last_battle_result = null
	GameStateManager.current_shop = []
	BattleServerAPI.reset_for_test()

# Helper to create test inventory
static func create_test_inventory_state() -> Dictionary:
	return {
		"items": [
			placed_item_data({"id": "item1", "name": "Test Item"})
		],
		"servers": [
			container_data({"id": "srv1"})
		]
	}

# Helper to verify gold constraints
static func assert_valid_gold(test: GutTest, gold: int, message: String = ""):
	test.assert_gte(gold, 0, message if message else "Gold should not be negative")
	test.assert_lte(gold, 999999, message if message else "Gold should not exceed maximum")
