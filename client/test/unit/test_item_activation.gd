extends GutTest
# What happens on screen when an item goes off.
#
# The signal that says so was declared and connected since the class was
# written and never once emitted, so none of this could have worked. These
# cover the whole path: the timeline says an item acted, the rack finds it, and
# it swells and starts cooling.

const APITypes = preload("res://scripts/api_types.gd")
const BattleEventProcessor = preload("res://scripts/battle_event_processor.gd")
const Presentation = preload("res://scripts/presentation.gd")
const ItemVisual = preload("res://scripts/item_visual.gd")

var processor
var grid


func before_each():
	Presentation.clear_requests()
	Presentation.set_recording(true)
	processor = BattleEventProcessor.new()
	add_child(processor)

	grid = InventoryGrid.new()
	grid.read_only = true
	grid.show_base_grid = false
	grid.configure(9, 7, 60, 1)
	add_child(grid)
	await get_tree().process_frame


func after_each():
	for child in get_children():
		if is_instance_valid(child):
			remove_child(child)
			child.queue_free()
	processor = null
	grid = null
	await get_tree().process_frame
	Presentation.clear_requests()


func _battle(actions: Array) -> APITypes.BattleResult:
	return APITypes.BattleResult.new({
		"winner": 1, "duration": 1.0, "player1_quota": 25, "player2_quota": 0,
		"seed": 1, "actions": actions, "opponent_name": "AI", "opponent_type": "ai",
		"player_inventory": {"items": [], "servers": []},
		"enemy_inventory": {"items": [], "servers": []},
	})


func _action(overrides: Dictionary) -> Dictionary:
	var data = {
		"timestamp": 0, "source": "system", "action": "damage", "player": 2,
		"target": null, "damage": 3,
		# The engine stamps both fighters' quotas on every action it records.
		"details": {"hp": [25, 22], "max_hp": [25, 25]},
	}
	data.merge(overrides, true)
	return data


func _load(items: Array) -> void:
	grid.load_inventory_state(APITypes.InventoryState.new({
		"items": items,
		"servers": [TestHelpers.container_data({"id": "srv", "position": [0, 0]})],
	}))
	await get_tree().process_frame


# ============ Finding the item that acted ============

func test_the_rack_finds_an_item_by_the_id_the_server_uses():
	await _load([TestHelpers.placed_item_data({"id": "abc-123", "position": [0, 0]})])

	var found = grid.item_visual("abc-123")

	assert_not_null(found, "The rack should find the item the timeline named")
	assert_eq(found.item_data.id, "abc-123", "and find the right one")


func test_an_id_the_rack_does_not_hold_finds_nothing():
	await _load([TestHelpers.placed_item_data({"id": "abc-123", "position": [0, 0]})])

	assert_null(grid.item_visual("not-here"),
		"An item in the other player's rack is not in this one")


func test_the_right_item_is_found_when_the_rack_holds_several():
	await _load([
		TestHelpers.placed_item_data({"id": "first", "position": [0, 0]}),
		TestHelpers.placed_item_data({"id": "second", "position": [1, 0]}),
		TestHelpers.placed_item_data({"id": "third", "position": [0, 1]}),
	])

	assert_eq(grid.item_visual("second").item_data.id, "second",
		"Should find the one asked for, not the first one it sees")


# ============ Saying which item acted ============

func test_an_action_says_which_item_did_it():
	var seen = []
	processor.item_activated.connect(
		func(item_id, player, action): seen.append([item_id, player, action]))

	processor.load_battle_events(_battle([
		_action({"source": "blade-1", "action": "damage", "player": 2})]))
	processor.skip_to_end()

	assert_eq(seen.size(), 1, "One action, one item firing")
	assert_eq(seen[0][0], "blade-1", "Should name the item that did it")
	assert_eq(seen[0][2], "damage", "and say what it did")


func test_an_action_with_no_item_behind_it_says_nothing():
	# battle_start and the stacking damage the engine attributes to nobody come
	# through as "system". There is no item on screen to point at.
	var seen = []
	processor.item_activated.connect(func(_i, _p, _a): seen.append(true))

	processor.load_battle_events(_battle([
		_action({"source": "system", "action": "battle_start", "player": 0})]))
	processor.skip_to_end()

	assert_eq(seen.size(), 0, "Nothing on screen fired")


func test_every_kind_of_action_names_its_item():
	# A buff is an item doing its job as much as a hit is, and it should swell
	# the same way even though it does not sound the same.
	var seen = []
	processor.item_activated.connect(func(item_id, _p, action): seen.append(action))

	processor.load_battle_events(_battle([
		_action({"source": "a", "action": "damage"}),
		_action({"timestamp": 10, "source": "b", "action": "heal", "player": 1}),
		_action({"timestamp": 20, "source": "c", "action": "buff", "player": 1,
			"details": {"buff_name": "speed", "actual_value": 1}}),
	]))
	processor.skip_to_end()

	assert_eq(seen, ["damage", "heal", "buff"], "Every one of them acted")


# ============ What it looks like ============

func test_an_item_that_fires_swells():
	await _load([TestHelpers.placed_item_data({"id": "one", "position": [0, 0]})])
	var visual = grid.item_visual("one")

	visual.fire(0.0)
	assert_eq(visual.pivot_offset, visual.size / 2.0,
		"It should grow from the middle, or it slides sideways as it grows")

	# Watched over time rather than over frames: a tween has not moved anything
	# until the frame after it starts, and headless runs frames as fast as it
	# can, so a fixed number of them is no particular length of animation.
	var biggest := 0.0
	var until := Time.get_ticks_msec() + 500
	while Time.get_ticks_msec() < until:
		await get_tree().process_frame
		biggest = maxf(biggest, visual.scale.x)

	assert_gt(biggest, 1.0, "It should swell")
	assert_almost_eq(visual.scale.x, 1.0, 0.02, "and settle back to its own size")


func test_an_item_with_a_cooldown_goes_dark_and_fills():
	await _load([TestHelpers.placed_item_data({"id": "one", "position": [0, 0]})])
	var visual = grid.item_visual("one")

	visual.fire(2.0)

	assert_true(visual.is_cooling(), "It should not be ready again yet")


func test_the_charge_fills_the_picture_and_not_the_square():
	# It used to draw a rectangle of dark over the whole cell. Most items do
	# not fill their cell, so what the player watched fill was the gap around
	# the item rather than the item.
	await _load([TestHelpers.placed_item_data({"id": "one", "position": [0, 0]})])
	var visual = grid.item_visual("one")

	visual.fire(2.0)

	var charging = visual._cooldown
	assert_true(charging.get_child_count() > 0,
		"There should be a lit copy of the picture to fill with")
	assert_lt(visual._artwork.modulate.v, 1.0,
		"and the picture underneath it should be dark while it charges")


func test_the_lit_part_grows_from_the_bottom():
	await _load([TestHelpers.placed_item_data({"id": "one", "position": [0, 0]})])
	var visual = grid.item_visual("one")

	visual.fire(0.4)
	var charging = visual._cooldown
	var at_first: float = charging.filled()
	await get_tree().create_timer(0.15).timeout

	assert_gt(charging.filled(), at_first, "More of it should be lit as it charges")
	assert_almost_eq(charging.position.y + charging.size.y, visual.size.y, 1.0,
		"and the lit part should reach the bottom of the item, not the top")


func test_a_charged_item_is_bright_again():
	await _load([TestHelpers.placed_item_data({"id": "one", "position": [0, 0]})])
	var visual = grid.item_visual("one")

	visual.fire(0.05)
	await get_tree().create_timer(0.2).timeout

	assert_eq(visual._artwork.modulate, Color.WHITE,
		"A charged item is drawn as it was drawn before it fired")
	assert_eq(visual._cooldown.get_child_count(), 0,
		"and the lit copy has nothing left to do")


func test_an_item_hands_out_a_copy_of_its_picture():
	# For a blow to throw at somebody. The picture rather than the cell: a cell
	# is a square of nothing with a picture somewhere in it.
	await _load([TestHelpers.placed_item_data({"id": "one", "position": [0, 0]})])
	var visual = grid.item_visual("one")

	var copy = visual.artwork_copy()

	assert_not_null(copy, "It should hand out a copy")
	assert_eq(copy.size, visual._artwork.size, "the same size as its own picture")
	assert_null(copy.get_parent(), "and not one already hanging in the scene")


func test_an_item_with_no_cooldown_never_goes_dark():
	await _load([TestHelpers.placed_item_data(
		{"id": "one", "position": [0, 0], "cooldown": 0.0})])
	var visual = grid.item_visual("one")

	visual.fire(0.0)

	assert_false(visual.is_cooling(),
		"Nothing to wait for, so nothing to cover it with")


func test_the_cover_clears_when_the_cooldown_runs_out():
	await _load([TestHelpers.placed_item_data({"id": "one", "position": [0, 0]})])
	var visual = grid.item_visual("one")

	visual.fire(0.05)
	assert_true(visual.is_cooling(), "Set up: cooling")
	await get_tree().create_timer(0.2).timeout

	assert_false(visual.is_cooling(), "It should be ready again")
