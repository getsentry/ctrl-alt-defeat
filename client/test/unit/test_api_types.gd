extends GutTest
# Tests for api_types.gd, the layer that turns a server response into objects.
#
# These check behaviour that must hold whatever the wire shape is: values
# survive parsing, order is kept, nesting resolves, and a round trip through
# to_dict() loses nothing. They deliberately do not enumerate field lists,
# because the field lists are what the API shape work changes.

const APITypes = preload("res://scripts/api_types.gd")


func _item(overrides: Dictionary = {}) -> Dictionary:
	# Fully populated on purpose. A real item carries all of this, and keeping
	# one fixture means the API shape work updates it here rather than in every
	# test that happens to build an item.
	var data = {
		"id": "item_1",
		"slug": "null_blade",
		"item_type": "null_blade",
		"name": "Null Blade",
		"category": "problem",
		"position": [2, 3],
		"shape": [[0, 0], [1, 0]],
		"rarity": "rare",
		"cost": 8,
		"min_damage": 2,
		"max_damage": 5,
		"min_heal": 0,
		"max_heal": 0,
		"cooldown": 1.5,
		"cpu_cost": 3,
		"special_effect": "Memory leak",
		"block_amount": 0,
		"description": "Deals 2-5 damage"
	}
	data.merge(overrides, true)
	return data


func _container(overrides: Dictionary = {}) -> Dictionary:
	var data = {
		"id": "container_a",
		"slug": "standard_vm",
		"type": "standard_vm",
		"position": [2, 3],
		"width": 2,
		"height": 2
	}
	data.merge(overrides, true)
	return data


func _battle_result(overrides: Dictionary = {}) -> Dictionary:
	var data = {
		"winner": 1,
		"duration": 12.5,
		"player1_quota": 80,
		"player2_quota": 0,
		"seed": 12345,
		"actions": [],
		"player_inventory": {"items": [], "servers": []},
		"enemy_inventory": {"items": [], "servers": []}
	}
	data.merge(overrides, true)
	return data


func _action(overrides: Dictionary = {}) -> Dictionary:
	var data = {
		"timestamp": 0,
		"source": "system",
		"action": "battle_start",
		"target": null,
		"damage": null,
		"player": 0,
		"details": null
	}
	data.merge(overrides, true)
	return data


# ============ Parsing keeps everything ============

func test_a_whole_item_survives_parsing():
	var item = APITypes.InventoryItem.new(_item())

	assert_eq(item.id, "item_1", "id should survive parsing")
	assert_eq(item.slug, "null_blade", "slug should survive parsing")
	assert_eq(item.item_type, "null_blade", "item_type should survive parsing")
	assert_eq(item.name, "Null Blade", "name should survive parsing")
	assert_eq(item.category, "problem", "category should survive parsing")
	assert_eq(item.position.x, 2, "x should survive parsing")
	assert_eq(item.position.y, 3, "y should survive parsing")
	assert_eq(item.shape, [[0, 0], [1, 0]], "shape should survive parsing")
	assert_eq(item.rarity, "rare", "rarity should survive parsing")
	assert_eq(item.cost, 8, "cost should survive parsing")
	assert_eq(item.min_damage, 2, "min_damage should survive parsing")
	assert_eq(item.max_damage, 5, "max_damage should survive parsing")
	assert_eq(item.cooldown, 1.5, "cooldown should survive parsing")
	assert_eq(item.cpu_cost, 3, "cpu_cost should survive parsing")
	assert_eq(item.special_effect, "Memory leak", "special_effect should survive parsing")
	assert_eq(item.description, "Deals 2-5 damage", "description should survive parsing")


func test_a_whole_container_survives_parsing():
	var container = APITypes.ServerContainer.new(_container({"id": "container_b", "position": [4, 3]}))

	assert_eq(container.id, "container_b", "id should survive parsing")
	assert_eq(container.slug, "standard_vm", "slug should survive parsing")
	assert_eq(container.type, "standard_vm", "type should survive parsing")
	assert_eq(container.position.x, 4, "x should survive parsing")
	assert_eq(container.position.y, 3, "y should survive parsing")
	assert_eq(container.width, 2, "width should survive parsing")
	assert_eq(container.height, 2, "height should survive parsing")


# ============ Round trips lose nothing ============

func test_a_round_trip_through_to_dict_loses_nothing():
	# Saved inventory goes out through to_dict() and comes back in on the next
	# screen, so anything to_dict() drops is lost for the rest of the run.
	var item = APITypes.InventoryItem.new(_item({"id": "abc", "position": [6, 4]}))
	var reloaded_item = APITypes.InventoryItem.new(item.to_dict())

	assert_eq(reloaded_item.id, item.id, "item id should survive a round trip")
	assert_eq(reloaded_item.name, item.name, "item name should survive a round trip")
	assert_eq(reloaded_item.slug, item.slug, "item slug should survive a round trip")
	assert_eq(reloaded_item.category, item.category, "item category should survive a round trip")
	assert_eq(reloaded_item.shape, item.shape, "item shape should survive a round trip")
	assert_eq(reloaded_item.position.x, item.position.x, "item x should survive a round trip")
	assert_eq(reloaded_item.position.y, item.position.y, "item y should survive a round trip")

	var container = APITypes.ServerContainer.new(_container({"id": "container_c", "position": [6, 3]}))
	var reloaded_container = APITypes.ServerContainer.new(container.to_dict())

	assert_eq(reloaded_container.id, container.id, "container id should survive a round trip")
	assert_eq(reloaded_container.width, container.width, "container width should survive a round trip")
	assert_eq(reloaded_container.position.x, container.position.x, "container x should survive a round trip")


func test_round_trip_is_stable_over_repeats():
	# Saved state is re-loaded and re-saved every round, so drift would compound.
	var item = APITypes.InventoryItem.new(_item({"position": [7, 4]}))
	for i in range(5):
		item = APITypes.InventoryItem.new(item.to_dict())

	assert_eq(item.position.x, 7, "x should not drift over repeated round trips")
	assert_eq(item.position.y, 4, "y should not drift over repeated round trips")


# ============ Collections keep their contents ============

func test_inventory_state_loads_items_and_containers():
	var state = APITypes.InventoryState.new({
		"items": [_item({"id": "a"}), _item({"id": "b"})],
		"servers": [_container({"id": "c1"}), _container({"id": "c2"}), _container({"id": "c3"})]
	})

	assert_eq(state.items.size(), 2, "Should load every item")
	assert_eq(state.containers.size(), 3, "Should load every container")


func test_inventory_state_keeps_item_order():
	var state = APITypes.InventoryState.new({
		"items": [_item({"id": "first"}), _item({"id": "second"}), _item({"id": "third"})],
		"servers": []
	})

	var ids = state.items.map(func(i): return i.id)
	assert_eq(ids, ["first", "second", "third"], "Items should keep their order")


func test_inventory_state_handles_an_empty_inventory():
	var state = APITypes.InventoryState.new({"items": [], "servers": []})

	assert_eq(state.items.size(), 0, "An empty inventory should load as empty")
	assert_eq(state.containers.size(), 0, "An empty inventory should have no containers")


func test_inventory_state_accepts_already_parsed_objects():
	# get_inventory_state() hands back objects, and they get reloaded as-is.
	var item = APITypes.InventoryItem.new(_item())
	var container = APITypes.ServerContainer.new(_container())

	var state = APITypes.InventoryState.new({"items": [item], "servers": [container]})

	assert_eq(state.items.size(), 1, "An already parsed item should be accepted")
	assert_eq(state.containers.size(), 1, "An already parsed container should be accepted")


# ============ Battle results ============

func test_battle_result_keeps_the_outcome():
	var result = APITypes.BattleResult.new(_battle_result({"winner": 2, "duration": 12.5, "seed": 999}))

	assert_eq(result.winner, 2, "The winner should survive parsing")
	assert_eq(result.duration, 12.5, "The duration should survive parsing")
	assert_eq(result.seed, 999, "The seed should survive parsing, so a battle can be replayed")


func test_battle_result_keeps_actions_in_order():
	var result = APITypes.BattleResult.new(_battle_result({"actions": [
		_action({"timestamp": 0, "action": "battle_start"}),
		_action({"timestamp": 1500, "action": "damage", "damage": 7, "player": 2}),
		_action({"timestamp": 5000, "action": "player_defeated", "player": 2})
	]}))

	assert_eq(result.actions.size(), 3, "Every action should be parsed")
	assert_eq(result.actions[0].timestamp, 0, "Actions should keep their order")
	assert_eq(result.actions[1].timestamp, 1500, "Actions should keep their order")
	assert_eq(result.actions[2].timestamp, 5000, "Actions should keep their order")


func test_battle_action_keeps_its_payload():
	var action = APITypes.BattleAction.new(
		_action({"timestamp": 1500, "source": "null_blade", "action": "damage", "damage": 7, "player": 2})
	)

	assert_eq(action.timestamp, 1500, "The timestamp drives playback")
	assert_eq(action.source, "null_blade", "The source names the item that acted")
	assert_eq(action.action, "damage", "The action kind should survive parsing")
	assert_eq(action.damage, 7, "The amount should survive parsing")
	assert_eq(action.player, 2, "The player should survive parsing")


func test_battle_result_carries_both_inventories():
	var result = APITypes.BattleResult.new(_battle_result({
		"player_inventory": {"items": [_item({"id": "mine"})], "servers": [_container()]},
		"enemy_inventory": {"items": [_item({"id": "theirs"}), _item({"id": "theirs2"})], "servers": []}
	}))

	assert_eq(result.player_inventory.items.size(), 1, "The player inventory should be parsed")
	assert_eq(result.enemy_inventory.items.size(), 2, "The enemy inventory should be parsed")
	assert_eq(result.player_inventory.items[0].id, "mine", "The two inventories should not be mixed up")
	assert_eq(result.enemy_inventory.items[0].id, "theirs", "The two inventories should not be mixed up")


# ============ Nesting resolves all the way down ============

func test_battle_response_resolves_to_leaf_values():
	var response = APITypes.BattleResponse.new({
		"battle_result": _battle_result({
			"winner": 1,
			"actions": [_action({"timestamp": 250, "action": "damage", "damage": 4, "player": 2})],
			"player_inventory": {"items": [_item({"id": "deep"})], "servers": []}
		}),
		"session_update": {
			"round": 3, "gold": 21, "gold_earned": 9, "wins": 2,
			"losses": 0, "lives": 5, "game_over": false, "victory": false
		},
		"new_shop": [],
		"battle_id": "battle-123"
	})

	assert_eq(response.battle_id, "battle-123", "The battle id should survive parsing")
	assert_eq(response.battle_result.winner, 1, "The nested result should be parsed")
	assert_eq(response.battle_result.actions[0].damage, 4, "Actions nested two deep should be parsed")
	assert_eq(response.battle_result.player_inventory.items[0].id, "deep",
		"An item nested three deep should be parsed")
	assert_eq(response.session_update.gold, 21, "The session update should be parsed")


func test_session_update_carries_the_whole_session():
	var update = APITypes.SessionUpdate.new({
		"round": 4, "gold": 30, "gold_earned": 12, "wins": 3,
		"losses": 1, "lives": 4, "game_over": false, "victory": false
	})

	assert_eq(update.round, 4, "round should survive parsing")
	assert_eq(update.gold, 30, "gold should survive parsing")
	assert_eq(update.gold_earned, 12, "gold_earned should survive parsing")
	assert_eq(update.wins, 3, "wins should survive parsing")
	assert_eq(update.losses, 1, "losses should survive parsing")
	assert_eq(update.lives, 4, "lives should survive parsing")
	assert_false(update.game_over, "game_over should survive parsing")
	assert_false(update.victory, "victory should survive parsing")


func test_session_start_response_resolves_the_session():
	var response = APITypes.SessionStartResponse.new({
		"player_id": "42",
		"player_name": "Tester",
		"session": {
			"player_id": "42", "player_name": "Tester", "round": 1, "gold": 12,
			"lives": 5, "wins": 0, "losses": 0, "last_battle_result": null,
			"current_shop": [], "game_seed": 777, "shop_refresh_count": 0,
			"inventory_grid": [], "inventory_storage": [],
			"server_containers": [_container(), _container({"id": "container_b", "position": [4, 3]})]
		}
	})

	assert_eq(response.player_id, "42", "The player id should survive parsing")
	assert_eq(response.session.game_seed, 777, "The seed should survive parsing")
	assert_eq(response.session.server_containers.size(), 2, "Starting containers should be parsed")
	assert_eq(response.session.server_containers[1].position.x, 4,
		"Container positions should survive parsing")

# ============ Positions ============

func test_position_reads_and_writes_an_array():
	var pos = APITypes.Position.new([2, 3])

	assert_eq(pos.x, 2, "x comes from index 0")
	assert_eq(pos.y, 3, "y comes from index 1")
	assert_eq(pos.to_array(), [2, 3], "to_array() gives back [x, y]")
	assert_eq(pos.to_vector2(), Vector2(2, 3), "to_vector2() converts for drawing")


func test_position_takes_nothing_but_an_array():
	# GUT catches the push_error, so the test carries on past it.
	var from_mapping = APITypes.Position.new({"x": 2, "y": 3})
	assert_eq(from_mapping.x, 0, "A mapping does not set x")
	assert_eq(from_mapping.y, 0, "A mapping does not set y")

	var wrong_length = APITypes.Position.new([2, 3, 4])
	assert_eq(wrong_length.x, 0, "A three-item array does not set x")
	assert_eq(wrong_length.y, 0, "A three-item array does not set y")


func test_a_position_serialises_only_as_an_array():
	var pos = APITypes.Position.new([2, 3])
	assert_false(pos.has_method("to_dict"),
		"A position serialises with to_array(), not to_dict()")


func test_positions_survive_a_container_round_trip():
	var container = APITypes.ServerContainer.new(_container({"position": [4, 3]}))
	var as_dict = container.to_dict()

	assert_typeof(as_dict["position"], TYPE_ARRAY, "A container writes its position as an array")
	assert_eq(as_dict["position"], [4, 3], "The position survives unchanged")


func test_positions_survive_an_item_round_trip():
	var item = APITypes.InventoryItem.new(_item({"position": [6, 4]}))
	var as_dict = item.to_dict()

	assert_typeof(as_dict["position"], TYPE_ARRAY, "An item writes its position as an array")
	assert_eq(as_dict["position"], [6, 4], "The position survives unchanged")
