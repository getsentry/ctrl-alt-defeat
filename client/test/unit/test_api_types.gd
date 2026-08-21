extends GutTest
# Tests for api_types.gd, the layer that turns a server response into objects.
#
# These check behaviour that must hold whatever the wire shape is: values
# survive parsing, order is kept, nesting resolves, and a round trip through
# to_dict() loses nothing. They deliberately do not enumerate field lists,
# because the field lists are what the API shape work changes.

const APITypes = preload("res://scripts/api_types.gd")

## Where the server's own turn is written, read off disk rather than over
## HTTP: it needs nothing running, and it is the same contract either way.
const GRID_SYSTEM_PATH := "../server/grid_system.py"

## What the server makes of five maps at all four turns, written down by
## `python tools/dump_turned_shapes.py`. See the header of that script.
const TURNED_SHAPES_PATH := "../server/tests/fixtures/turned_shapes.json"


func _item(overrides: Dictionary = {}) -> Dictionary:
	# Fully populated on purpose. A real item carries all of this, and one
	# fixture means a field change lands here rather than in every test that
	# happens to build an item.
	var data = {
		"id": "item_1",
		"slug": "null_blade",
		"item_type": "null_blade",
		"name": "Null Blade",
		"category": "problem",
		"is_container": false,
		"position": [2, 3],
		"rotation": 0,
		"shape": [[0, 0], [1, 0]],
		"kinds": ["melee"],
		"traits": ["Melee"],
		"aura": {},
		"rarity": "rare",
		"cost": 8,
		"price": 8,
		"sell_value": 4,
		"on_sale": false,
		"min_damage": 2,
		"max_damage": 5,
		"min_heal": 0,
		"max_heal": 0,
		"cooldown": 1.5,
		"cpu_cost": 3,
		"block_amount": 0,
		"accuracy": 1.0,
		"damage_per_second": 0.0, "cpu_per_second": 0.0,
		"effects": ["Every 1.5s: deal 2-5 damage.", "On hit: apply 2 Memory Leak."],
		"color": "#BE0032",
		"pattern": "solid"
	}
	data.merge(overrides, true)
	return data


# A container is a placed item that provides squares rather than filling them,
# so it arrives carrying every field an item does.
func _container(overrides: Dictionary = {}) -> Dictionary:
	var data = _item({
		"id": "container_a",
		"item_type": "standard_vm",
		"name": "Standard VM",
		"slug": "standard_vm",
		"category": "container",
		"is_container": true,
		"color": "",
		"pattern": "",
		"shape": [[0, 0], [1, 0], [0, 1], [1, 1]]
	})
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
		"opponent_name": "AI Opponent",
		"opponent_type": "ai",
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
	var item = APITypes.PlacedItem.new(_item())

	assert_eq(item.id, "item_1", "id should survive parsing")
	assert_eq(item.slug, "null_blade", "slug should survive parsing")
	assert_eq(item.item_type, "null_blade", "item_type should survive parsing")
	assert_eq(item.name, "Null Blade", "name should survive parsing")
	assert_eq(item.category, "problem", "category should survive parsing")
	assert_eq(item.position.x, 2, "x should survive parsing")
	assert_eq(item.position.y, 3, "y should survive parsing")
	assert_eq(item.shape, _at([[0, 0], [1, 0]]), "shape should survive parsing")
	assert_eq(item.rarity, "rare", "rarity should survive parsing")
	assert_eq(item.cost, 8, "cost should survive parsing")
	assert_eq(item.min_damage, 2, "min_damage should survive parsing")
	assert_eq(item.max_damage, 5, "max_damage should survive parsing")
	assert_eq(item.cooldown, 1.5, "cooldown should survive parsing")
	assert_eq(item.cpu_cost, 3, "cpu_cost should survive parsing")
	assert_eq(item.effects, ["Every 1.5s: deal 2-5 damage.",
		"On hit: apply 2 Memory Leak."] as Array[String],
		"what the item does should survive parsing")


func test_a_whole_container_survives_parsing():
	var container = APITypes.PlacedItem.new(_container({"id": "container_b", "position": [4, 3]}))

	assert_eq(container.id, "container_b", "id should survive parsing")
	assert_eq(container.slug, "standard_vm", "slug should survive parsing")
	assert_eq(container.item_type, "standard_vm", "item_type should survive parsing")
	assert_true(container.is_container, "a container should say that it is one")
	assert_eq(container.name, "Standard VM", "a container carries the name its tooltip shows")
	assert_eq(container.position.x, 4, "x should survive parsing")
	assert_eq(container.position.y, 3, "y should survive parsing")
	assert_eq(container.shape, _at([[0, 0], [1, 0], [0, 1], [1, 1]]),
		"shape should survive parsing")


# ============ Round trips lose nothing ============

func test_a_round_trip_through_to_dict_loses_nothing():
	# Saved inventory goes out through to_dict() and comes back in on the next
	# screen, so anything to_dict() drops is lost for the rest of the run.
	var item = APITypes.PlacedItem.new(_item({"id": "abc", "position": [6, 4]}))
	var reloaded_item = APITypes.PlacedItem.new(item.to_dict())

	assert_eq(reloaded_item.id, item.id, "item id should survive a round trip")
	assert_eq(reloaded_item.name, item.name, "item name should survive a round trip")
	assert_eq(reloaded_item.slug, item.slug, "item slug should survive a round trip")
	assert_eq(reloaded_item.category, item.category, "item category should survive a round trip")
	assert_eq(reloaded_item.shape, item.shape, "item shape should survive a round trip")
	assert_eq(reloaded_item.position.x, item.position.x, "item x should survive a round trip")
	assert_eq(reloaded_item.position.y, item.position.y, "item y should survive a round trip")

	var container = APITypes.PlacedItem.new(_container({"id": "container_c", "position": [6, 3]}))
	var reloaded_container = APITypes.PlacedItem.new(container.to_dict())

	assert_eq(reloaded_container.id, container.id, "container id should survive a round trip")
	assert_eq(reloaded_container.shape, container.shape, "container shape should survive a round trip")
	assert_eq(reloaded_container.position.x, container.position.x, "container x should survive a round trip")


func test_round_trip_is_stable_over_repeats():
	# Saved state is re-loaded and re-saved every round, so drift would compound.
	var item = APITypes.PlacedItem.new(_item({"position": [7, 4]}))
	for i in range(5):
		item = APITypes.PlacedItem.new(item.to_dict())

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


func test_inventory_state_survives_a_round_trip():
	# An item goes out to the server as plain data and comes back the same.
	var item = APITypes.PlacedItem.new(_item())
	var container = APITypes.PlacedItem.new(_container())

	var state = APITypes.InventoryState.new({
		"items": [item.to_dict()], "servers": [container.to_dict()]
	})

	assert_eq(state.items.size(), 1, "The item should come back")
	assert_eq(state.items[0].id, item.id, "and keep its id")
	assert_eq(state.items[0].shape, item.shape, "and keep its shape")
	assert_eq(state.containers.size(), 1, "The container should come back")


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
		"opponent_name": "AI Opponent",
		"opponent_type": "ai",
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
			"opponent_name": "AI Opponent",
			"opponent_type": "ai",
			"player_inventory": {"items": [_item({"id": "deep"})], "servers": []}
		}),
		"session_update": {
			"round": 3, "gold": 21, "gold_earned": 9, "wins": 2,
			"losses": 0, "lives": 5, "game_over": false, "run_over": false, "victory": false, "shop_refresh_cost": 1,
			"combinations": [], "pending": []
		},
		"new_shop": [],
		"inventory": {"inventory_grid": [], "inventory_storage": [], "server_containers": []},
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
		"losses": 1, "lives": 4, "game_over": false, "run_over": false, "victory": false, "shop_refresh_cost": 1,
		"combinations": [], "pending": []
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
			"shop_refresh_cost": 1,
			"inventory_grid": [], "inventory_storage": [], "pending": [],
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
	var container = APITypes.PlacedItem.new(_container({"position": [4, 3]}))
	var as_dict = container.to_dict()

	assert_typeof(as_dict["position"], TYPE_ARRAY, "A container writes its position as an array")
	assert_eq(as_dict["position"], [4, 3], "The position survives unchanged")


func test_positions_survive_an_item_round_trip():
	var item = APITypes.PlacedItem.new(_item({"position": [6, 4]}))
	var as_dict = item.to_dict()

	assert_typeof(as_dict["position"], TYPE_ARRAY, "An item writes its position as an array")
	assert_eq(as_dict["position"], [6, 4], "The position survives unchanged")


func test_a_shop_sale_survives_parsing():
	# price is what the shop charges today, cost is what the item is worth.
	var item = APITypes.Item.new(_item({"cost": 8, "price": 4, "on_sale": true}))
	assert_eq(item.cost, 8)
	assert_eq(item.price, 4)
	assert_true(item.on_sale)


func test_an_item_not_on_sale_is_charged_its_cost():
	var item = APITypes.Item.new(_item({"cost": 8, "price": 8, "on_sale": false}))
	assert_eq(item.price, item.cost)
	assert_false(item.on_sale)


func test_a_fractional_cpu_cost_is_not_truncated():
	# Stamina comes from Backpack Battles in fractions. Reading it as an int
	# turned a 1.4 into a 1 and made every weapon cheaper to fire.
	var item = APITypes.Item.new(_item({"cpu_cost": 1.4}))
	assert_almost_eq(item.cpu_cost, 1.4, 0.001)


func test_sale_fields_survive_a_round_trip():
	var item = APITypes.Item.new(_item({"cost": 8, "price": 4, "on_sale": true}))
	var reloaded = APITypes.Item.new(item.to_dict())
	assert_eq(reloaded.price, 4)
	assert_true(reloaded.on_sale)




# ============ Turning a shape ============
#
# The server turns shapes the same way. If the two ever disagree, an item draws
# on squares the server has it standing somewhere else, which is the kind of
# thing that only shows up as an item that cannot be placed where it looks like
# it should fit.

func test_the_server_turns_a_square_the_same_way_this_does():
	"""The one thing that cannot be allowed to drift.

	Both sides turn shapes, because the client has to draw a turn before the
	server has heard of it. Turned opposite ways they agree about every
	rectangle and disagree about everything else: an aura reaching out of the
	wrong end of a spear, and an item that cannot be placed where it looks
	like it should fit.
	"""
	var written := _how_the_server_turns()
	assert_eq(written.size(), 3, "setup: three quarter turns in %s" % GRID_SYSTEM_PATH)

	# The turn itself, before the result is settled back against its corner:
	# settling a single square puts it at the origin whichever way it turned,
	# which is exactly the disagreement this is looking for.
	for rotation in written:
		assert_eq(APITypes._spin(_at([[1, 2]]), rotation), _at([written[rotation]]),
			"a turn of %d degrees" % rotation)


## What grid_system._turn() returns for each quarter, worked out for the square
## (1, 2). The source says `return (-y, x)`, which is the only form it takes:
## each half is x or y, with or without a minus.
func _how_the_server_turns() -> Dictionary:
	var path := ProjectSettings.globalize_path("res://").path_join(GRID_SYSTEM_PATH)
	var file := FileAccess.open(path, FileAccess.READ)
	assert_not_null(file, "Should be able to read %s" % path)
	if file == null:
		return {}
	var source := file.get_as_text()
	file.close()

	var start := source.find("def _turn(")
	assert_true(start != -1, "%s should declare _turn()" % GRID_SYSTEM_PATH)
	if start == -1:
		return {}
	var body := source.substr(start, source.find("\n@dataclass", start) - start)

	var turns := {}
	var quarter := RegEx.create_from_string(
		"CLOCKWISE_(90|180|270):\\s*\\n\\s*return \\((-?[xy]), (-?[xy])\\)")
	for found in quarter.search_all(body):
		turns[int(found.get_string(1))] = [
			_value_of(found.get_string(2)), _value_of(found.get_string(3))]
	return turns


## What one half of the server's answer comes to for the square (1, 2).
func _value_of(written: String) -> int:
	var value := 1 if written.ends_with("x") else 2
	return -value if written.begins_with("-") else value


func test_the_client_gives_the_answers_the_server_wrote_down():
	"""The whole turn, not only its direction.

	The turn is two steps -- spin every square, then settle the result back
	against the FOOTPRINT's corner -- and both are written twice, once here
	and once on the server. The direction is what drifted, but a zone settled
	against its own corner instead of the footprint's would slide onto the
	item just as silently.

	The server is held to the same file by test_grid_system.py, so neither
	side can be changed on its own without the other going red.
	"""
	var written := _the_answers_written_down()
	assert_gt(written.size(), 4, "setup: five maps are written down")

	for shape in written:
		# The rotation-0 entry is what the server sends a client: the shape as
		# the catalogue draws it, and the zones in the same frame.
		var upright: Dictionary = shape["turns"]["0"]
		for facing in ["0", "90", "180", "270"]:
			var expected: Dictionary = shape["turns"][facing]
			var placed = APITypes.PlacedItem.new(_item({
				"shape": upright["squares"],
				"star": upright["star"],
				"diamond": upright["diamond"],
				"anchors": shape["anchors"],
				"position": [0, 0],
				"rotation": int(facing),
			}))
			var where := "%s at %s degrees" % [shape["name"], facing]

			assert_eq(_sorted_squares(placed.turned_shape()),
				_sorted_squares(_at(expected["squares"])), where)
			assert_eq(_sorted_squares(placed.turned_star()),
				_sorted_squares(_at(expected["star"])), where)
			assert_eq(_sorted_squares(placed.turned_diamond()),
				_sorted_squares(_at(expected["diamond"])), where)


func _the_answers_written_down() -> Array:
	var path := ProjectSettings.globalize_path("res://").path_join(TURNED_SHAPES_PATH)
	var file := FileAccess.open(path, FileAccess.READ)
	assert_not_null(file, "Should be able to read %s" % path)
	if file == null:
		return []
	var written = JSON.parse_string(file.get_as_text())
	file.close()
	assert_true(written is Array, "%s should hold a list of shapes" % path)
	return written if written is Array else []


func test_a_shape_turned_none_is_unchanged():
	var wide := _at([[0, 0], [1, 0]])
	assert_eq(APITypes.turn(wide, 0), wide, "No turn, no change")


func test_a_quarter_turn_stands_a_wide_shape_on_end():
	# Two across becomes two down.
	assert_eq(_sorted_squares(APITypes.turn(_at([[0, 0], [1, 0]]), 90)), _at([[0, 0], [0, 1]]),
		"A two-wide item turned clockwise is two tall")


func test_a_quarter_turn_lays_a_tall_shape_flat():
	assert_eq(_sorted_squares(APITypes.turn(_at([[0, 0], [0, 1]]), 90)), _at([[0, 0], [1, 0]]),
		"A two-tall item turned clockwise is two wide")


func test_a_half_turn_of_a_wide_shape_is_still_wide():
	var turned = APITypes.turn(_at([[0, 0], [1, 0]]), 180)
	assert_eq(turned.size(), 2, "It still covers two squares")
	var xs = turned.map(func(o): return o.x)
	assert_true(0 in xs and 1 in xs, "and still lies across")


func test_four_quarter_turns_come_back_to_the_start():
	var shape := _at([[0, 0], [1, 0], [0, 1]])
	var once = APITypes.turn(shape, 90)
	var twice = APITypes.turn(once, 90)
	var thrice = APITypes.turn(twice, 90)
	var round_trip = APITypes.turn(thrice, 90)

	assert_eq(_sorted_squares(round_trip), _sorted_squares(shape), "Back where it started")


func test_a_turn_never_moves_the_item_off_its_corner():
	# A turn changes the squares an item covers, not where it stands, so the
	# offsets always start at the origin.
	for rotation in [90, 180, 270]:
		var turned = APITypes.turn(_at([[0, 0], [1, 0], [2, 0]]), rotation)
		var least_x = turned.map(func(o): return o.x).min()
		var least_y = turned.map(func(o): return o.y).min()
		assert_eq([least_x, least_y], [0, 0],
			"Turned by %d it should still sit on its corner" % rotation)


func test_an_L_keeps_its_three_squares_however_it_is_turned():
	for rotation in [0, 90, 180, 270]:
		assert_eq(APITypes.turn(_at([[0, 0], [0, 1], [1, 1]]), rotation).size(), 3,
			"Turning changes the shape, never how much of it there is")


func test_a_turned_item_covers_turned_squares():
	var item = APITypes.PlacedItem.new(
		_item({"shape": [[0, 0], [1, 0]], "position": [4, 3], "rotation": 90}))

	assert_eq(_sorted_squares(item.covered_squares()),
		[Vector2i(4, 3), Vector2i(4, 4)],
		"Standing on end at (4,3), it covers the square below as well")


func test_an_unturned_item_covers_the_squares_it_always_did():
	var item = APITypes.PlacedItem.new(
		_item({"shape": [[0, 0], [1, 0]], "position": [4, 3], "rotation": 0}))

	assert_eq(_sorted_squares(item.covered_squares()),
		[Vector2i(4, 3), Vector2i(5, 3)],
		"Lying flat, it covers the square to its right")


func test_moving_a_turned_item_keeps_it_turned():
	# placed_at used to set the rotation to zero, so every move straightened
	# the item out without asking.
	var item = APITypes.PlacedItem.new(
		_item({"shape": [[0, 0], [1, 0]], "position": [4, 3], "rotation": 90}))

	var moved = item.placed_at(Vector2i(2, 3))

	assert_eq(moved.rotation, 90, "It should still be facing the way it was")
	assert_eq(_sorted_squares(moved.covered_squares()),
		[Vector2i(2, 3), Vector2i(2, 4)],
		"and still cover the squares that go with facing that way")


# The offsets an item covers are a set, so order is never the point.
func _sorted(offsets: Array) -> Array:
	var copy = offsets.duplicate()
	copy.sort_custom(func(a, b): return [a[0], a[1]] < [b[0], b[1]])
	return copy


func _sorted_squares(squares: Array) -> Array:
	var copy = squares.duplicate()
	copy.sort_custom(func(a, b): return [a.x, a.y] < [b.x, b.y])
	return copy


func test_an_item_turns_where_it_stands():
	# Turning is the item's own business, so nothing turning one has to know
	# whether it is on the grid or in a hand. This is the only place a quarter
	# turn is worked out, which is why it was worked out three ways before.
	var item = APITypes.PlacedItem.new(
		_item({"shape": [[0, 0], [1, 0]], "position": [4, 3], "rotation": 0}))

	var turned = item.turned(1)

	assert_eq(turned.facing(), 90, "A quarter clockwise")
	assert_eq(turned.position.to_array(), [4, 3], "and it has not moved")


func test_an_item_that_is_not_on_the_grid_still_turns():
	# One in the hand or carried out of the shop is nowhere in particular.
	var item = APITypes.Item.new(_item({"shape": [[0, 0], [1, 0]]}))

	assert_eq(item.turned(1).facing(), 90, "It turns all the same")


func test_turning_the_other_way():
	var item = APITypes.Item.new(_item({"shape": [[0, 0], [1, 0]]}))
	assert_eq(item.turned(-1).facing(), 270, "Anticlockwise from square on")


func test_turning_adds_up():
	var item = APITypes.Item.new(_item({"shape": [[0, 0], [1, 0]]}))
	assert_eq(item.turned(1).turned(1).facing(), 180, "Two quarters is a half")
	assert_eq(item.turned(1).turned(1).turned(1).turned(1).facing(), 0,
		"and four is back where it started")
# ============ Aura zones ============
#
# The server sends the zones in the item's own frame and the client turns them.
# The two turn the same way or an item draws an aura on squares the server has
# it reaching somewhere else, so these check against the values the server
# produces for the same maps.

# The squares a list of [x, y] pairs means, which is what the client holds them
# as once parsed.
func _at(offsets: Array) -> Array[Vector2i]:
	return APITypes.squares(offsets)


func _potion(overrides: Dictionary = {}) -> Dictionary:
	# Health Potion: the map "*", "^", "#". Its star sits above the anchor and
	# stays there however the item is turned.
	var data = _item({
		"shape": [[0, 0], [0, 1]],
		"star": [[0, -1]],
		"diamond": [],
		"anchors": [[0, 0]],
	})
	data.merge(overrides, true)
	return data


func test_an_item_carries_its_zones():
	var item = APITypes.Item.new(_potion())
	assert_eq(item.star, _at([[0, -1]]), "the star zone comes across")
	assert_eq(item.anchors, _at([[0, 0]]), "and the anchor that decides how it turns")


func test_an_item_without_zones_gets_empty_ones():
	# Not null: nothing asking should have to check first.
	var item = APITypes.Item.new(_item())
	assert_eq(item.star, _at([]), "no star")
	assert_eq(item.diamond, _at([]), "no diamond")


func test_zones_survive_a_round_trip():
	var once = APITypes.Item.new(_potion())
	var twice = APITypes.Item.new(once.to_dict())
	assert_eq(twice.star, once.star)
	assert_eq(twice.anchors, once.anchors)


func test_an_unplaced_item_answers_with_the_zone_as_drawn():
	var item = APITypes.Item.new(_potion())
	assert_eq(item.turned_star(), _at([[0, -1]]), "facing nowhere, so nothing turns")


func test_a_turned_zone_never_lands_on_its_own_item():
	# The whole reason a zone cannot go through turn() alone.
	for rotation in [0, 90, 180, 270]:
		var placed = APITypes.PlacedItem.new(
			_potion({"position": [4, 4], "rotation": rotation}))
		for square in placed.turned_star():
			assert_false(placed.turned_shape().has(square),
				"a zone square landed on the item at %d degrees" % rotation)


func test_an_anchored_zone_stays_above_the_anchor():
	# The same four answers the server gives for this map.
	var expected = {0: [[0, -1]], 90: [[1, -1]], 180: [], 270: [[0, -1]]}
	for rotation in expected:
		var placed = APITypes.PlacedItem.new(
			_potion({"position": [0, 0], "rotation": rotation}))
		assert_eq(placed.turned_star(), _at(expected[rotation]),
			"star at %d degrees" % rotation)


func test_a_zone_with_no_anchor_turns_with_the_item():
	# Rows count downwards, so a quarter clockwise sends the square on the
	# right to the square below.
	var reaching_right = _item({
		"shape": [[0, 0]], "star": [[1, 0]], "diamond": [], "anchors": [], "kinds": [],
		"traits": [], "aura": {},
	})
	reaching_right["position"] = [0, 0]
	reaching_right["rotation"] = 90
	var placed = APITypes.PlacedItem.new(reaching_right)
	assert_eq(placed.turned_star(), _at([[0, 1]]))


func test_a_reach_turns_the_way_the_artwork_does():
	"""The bug this direction was found by.

	Buffer Overflow is a spear: four squares of shaft, five of reach past the
	tip. ItemVisual turns the artwork with Godot's own rotation, which is
	clockwise on a screen whose rows count downwards. Turned the other way the
	squares disagreed with the picture, and a spear drawn pointing right
	threatened the five squares behind it.
	"""
	var spear = _item({
		"shape": [[0, 0], [0, 1], [0, 2], [0, 3]],
		"star": [[0, -5], [0, -4], [0, -3], [0, -2], [0, -1]],
		"diamond": [], "anchors": [], "kinds": [], "aura": {},
	})
	spear["position"] = [0, 0]

	spear["rotation"] = 90
	var pointing_right = APITypes.PlacedItem.new(spear)
	assert_eq(_sorted_squares(pointing_right.turned_shape()),
		_at([[0, 0], [1, 0], [2, 0], [3, 0]]), "the shaft lies across")
	for square in pointing_right.turned_star():
		assert_gt(square.x, 3, "the reach is past the tip, not behind it")

	spear["rotation"] = 270
	var pointing_left = APITypes.PlacedItem.new(spear)
	for square in pointing_left.turned_star():
		assert_lt(square.x, 0, "and the other way round")


func test_a_turn_is_the_one_a_player_asked_for():
	# Every quarter turn, the way a clock hand goes. The artwork is turned by
	# the same number of degrees through Godot, which is clockwise, so this is
	# what keeps the squares and the picture together.
	var reaching_up = _item({
		"shape": [[0, 0]], "star": [[0, -1]],
		"diamond": [], "anchors": [], "kinds": [], "aura": {},
	})
	reaching_up["position"] = [0, 0]
	var expected = {90: [[1, 0]], 180: [[0, 1]], 270: [[-1, 0]]}
	for rotation in expected:
		reaching_up["rotation"] = rotation
		assert_eq(APITypes.PlacedItem.new(reaching_up).turned_star(),
			_at(expected[rotation]), "reaching up, turned %d degrees" % rotation)


# ============ Combining (GDD 5.3) ============

func test_what_the_rack_is_on_the_way_to_survives_parsing():
	var waiting = APITypes.Pending.new({
		"makes": "hero_longsword",
		"have": 2,
		"need": 3,
		"ingredients": ["sword", "stone"],
		"catalysts": [],
		"missing": ["whetstone"],
	})

	assert_eq(waiting.makes, "hero_longsword")
	assert_eq(waiting.have, 2)
	assert_eq(waiting.need, 3)
	assert_eq(waiting.ingredients, ["sword", "stone"] as Array[String])
	assert_eq(waiting.missing, ["whetstone"] as Array[String])
	assert_false(waiting.complete(), "two of three is not finished")


func test_a_finished_recipe_says_so():
	var waiting = APITypes.Pending.new({
		"makes": "serverless_function", "have": 2, "need": 2,
		"ingredients": ["rig"], "catalysts": ["cat"], "missing": [],
	})

	assert_true(waiting.complete())
	assert_eq(waiting.item_ids(), ["rig", "cat"] as Array[String],
		"a catalyst is one of the items this names")
	assert_true(waiting.names("cat"))
	assert_false(waiting.names("somebody_else"))


func test_a_combination_carries_the_items_it_ate():
	var made = APITypes.Combination.new({
		"made": "blue_sage_collar",
		"made_id": "new_1",
		"consumed": [_item({"id": "eaten"})],
		"kept": [_item({"id": "catalyst"})],
		"freed": [[2, 3], [3, 3]],
		"position": [2, 3],
	})

	assert_eq(made.made, "blue_sage_collar")
	assert_eq(made.consumed[0].id, "eaten",
		"whole items, because the client has no catalogue to draw from")
	assert_eq(made.kept[0].id, "catalyst")
	assert_eq(made.freed, _at([[2, 3], [3, 3]]))
	assert_eq(made.position.to_vector2i(), Vector2i(2, 3))


func test_a_result_with_nowhere_to_stand_has_no_position():
	var made = APITypes.Combination.new({
		"made": "stone_golem", "made_id": "new_2",
		"consumed": [], "kept": [], "freed": [], "position": null,
	})

	assert_null(made.position, "no position means the chest, and never nowhere")


func test_the_combining_catalogue_names_both_sides_and_the_items():
	var catalogue = APITypes.CombiningCatalogue.new({
		"partners": {"hero_sword": ["whetstone"], "whetstone": ["hero_sword"]},
		"names": {"hero_longsword": "Long Poll"},
	})

	assert_eq(catalogue.partners_of("hero_sword"), ["whetstone"] as Array[String])
	assert_eq(catalogue.partners_of("bloodthorne"), [] as Array[String],
		"an item in no recipe is absent from the map")
	assert_eq(catalogue.name_of("hero_longsword"), "Long Poll")


func test_the_battle_answer_carries_the_rack_the_combining_left():
	var response = APITypes.BattleResponse.new({
		"battle_result": _battle_result({
			"player_inventory": {"items": [_item({"id": "fought_with"})], "servers": []}
		}),
		"session_update": {
			"round": 3, "gold": 21, "gold_earned": 9, "wins": 2,
			"losses": 0, "lives": 5, "game_over": false, "run_over": false, "victory": false, "shop_refresh_cost": 1,
			"combinations": [{
				"made": "blue_sage_collar", "made_id": "new_1",
				"consumed": [_item({"id": "fought_with"})], "kept": [],
				"freed": [[2, 3]], "position": [2, 3],
			}],
			"pending": [],
		},
		"new_shop": [],
		"inventory": {
			"inventory_grid": [_item({"id": "new_1"})],
			"inventory_storage": [],
			"server_containers": [],
		},
		"battle_id": "battle-9",
	})

	assert_eq(response.battle_result.player_inventory.items[0].id, "fought_with",
		"the rack that fought is the rack before anything combined")
	assert_eq(response.inventory.inventory_grid[0].id, "new_1",
		"and the inventory is the rack the player holds now")
	assert_eq(response.session_update.combinations[0].made, "blue_sage_collar",
		"with what happened in between")
