extends GutTest
# Tests for battle_event_processor.gd, which replays a finished battle.
#
# The server decides the whole battle up front and sends a timeline. This class
# walks that timeline and announces what happened. These tests cover the walk
# and the announcements, not the wire format of an action.

const BattleEventProcessorScript = preload("res://scripts/battle_event_processor.gd")
const APITypes = preload("res://scripts/api_types.gd")

var processor


func before_each():
	GameStateManager.start_new_game()
	processor = BattleEventProcessorScript.new()
	add_child(processor)
	await get_tree().process_frame


func after_each():
	if is_instance_valid(processor):
		processor.stop_playback()
		processor.set_process(false)
		remove_child(processor)
		processor.queue_free()
	processor = null
	await get_tree().process_frame


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


func _item(id: String, item_name: String) -> Dictionary:
	return TestHelpers.placed_item_data({"id": id, "name": item_name})


func _battle(actions: Array, player_items: Array = [], enemy_items: Array = []) -> APITypes.BattleResult:
	return APITypes.BattleResult.new({
		"winner": 1,
		"duration": 10.0,
		"player1_quota": 25,
		"player2_quota": 0,
		"seed": 1,
		"actions": actions,
		"opponent_name": "AI Opponent",
		"opponent_type": "ai",
		"player_inventory": {"items": player_items, "servers": []},
		"enemy_inventory": {"items": enemy_items, "servers": []}
	})


# ============ Loading ============

func test_loading_a_battle_makes_it_ready_to_play():
	GameStateManager.current_round = 1
	processor.load_battle_events(_battle([
		_action({"timestamp": 0}),
		_action({"timestamp": 500, "action": "damage", "damage": 3, "player": 2})
	]))

	var quota = GameStateManager.get_round_quota()
	assert_eq(processor.events.size(), 2, "Every event should be loaded")
	assert_eq(processor.current_event_index, 0, "Playback should start from the first event")
	assert_false(processor.is_playing, "Loading a battle should not start it")
	assert_eq(processor.battle_duration, 10.0, "The duration should come from the battle")
	assert_eq(processor.player1_hp, quota, "Player 1 should start on the round quota")
	assert_eq(processor.player2_hp, quota, "Player 2 should start on the round quota")


func test_loading_a_second_battle_replaces_the_first():
	processor.load_battle_events(_battle([_action(), _action(), _action()]))
	processor.load_battle_events(_battle([_action()]))

	assert_eq(processor.events.size(), 1, "A new battle should replace the previous one")


# ============ Naming items in the log ============

func test_items_from_both_sides_can_be_named():
	processor.load_battle_events(_battle(
		[_action()],
		[_item("mine", "My Blade")],
		[_item("theirs", "Their Firewall")]
	))

	assert_eq(processor.item_lookup["mine"], "My Blade", "Player items should be nameable")
	assert_eq(processor.item_lookup["theirs"], "Their Firewall", "Enemy items should be nameable")


func test_the_lookup_is_rebuilt_for_each_battle():
	processor.load_battle_events(_battle([_action()], [_item("old", "Old Item")]))
	processor.load_battle_events(_battle([_action()], [_item("new", "New Item")]))

	assert_false(processor.item_lookup.has("old"), "Last battle's items should not linger")
	assert_true(processor.item_lookup.has("new"), "This battle's items should be there")


# ============ Playback ============

func test_playback_starts_stops_and_keeps_its_speed():
	processor.load_battle_events(_battle([_action()]))
	assert_eq(processor.get_progress(), 0.0, "Nothing has played yet")

	processor.start_playback(4.0)
	assert_true(processor.is_playing, "Starting playback should mark it playing")
	assert_eq(processor.playback_speed, 4.0, "The speed it was started with should be kept")

	processor.stop_playback()
	assert_false(processor.is_playing, "Stopping should mark it stopped")


func test_starting_playback_with_no_events_does_nothing():
	processor.load_battle_events(_battle([]))
	processor.start_playback(1.0)

	assert_false(processor.is_playing, "There is nothing to play")


# ============ Skipping to the end ============

func test_skipping_processes_every_event():
	processor.load_battle_events(_battle([
		_action({"timestamp": 0}),
		_action({"timestamp": 1000, "action": "damage", "damage": 3, "player": 2}),
		_action({"timestamp": 2000, "action": "damage", "damage": 4, "player": 2})
	]))

	processor.skip_to_end()

	assert_eq(processor.current_event_index, 3, "Skipping should consume the whole timeline")


func test_skipping_applies_the_damage_along_the_way():
	# Skipping must land on the same state as watching it play.
	GameStateManager.current_round = 1
	var quota = GameStateManager.get_round_quota()
	processor.load_battle_events(_battle([
		_action({"timestamp": 100, "action": "damage", "damage": 5, "player": 2}),
		_action({"timestamp": 200, "action": "damage", "damage": 3, "player": 2})
	]))

	processor.skip_to_end()

	assert_eq(processor.player2_hp, quota - 8, "Both hits should have landed")


func test_skipping_an_empty_battle_is_safe():
	processor.load_battle_events(_battle([]))
	processor.skip_to_end()
	assert_eq(processor.current_event_index, 0, "There was nothing to skip")


# ============ What it announces ============

func test_damage_is_announced():
	watch_signals(processor)
	processor.load_battle_events(_battle([
		_action({"timestamp": 0, "action": "damage", "damage": 6, "player": 2, "source": "blade"})
	]))

	processor.skip_to_end()

	assert_signal_emitted(processor, "damage_dealt", "Damage should be announced")
	var args = get_signal_parameters(processor, "damage_dealt", 0)
	assert_eq(args[0], 2, "Should say who took the damage")
	assert_eq(args[1], 6, "Should say how much")


func test_a_defeat_is_announced():
	watch_signals(processor)
	processor.load_battle_events(_battle([
		_action({"timestamp": 0, "action": "player_defeated", "player": 2})
	]))

	processor.skip_to_end()

	assert_signal_emitted(processor, "player_died", "A defeat should be announced")


func test_the_start_of_the_battle_is_announced():
	watch_signals(processor)
	processor.load_battle_events(_battle([
		_action({"timestamp": 0, "action": "battle_start"})
	]))

	processor.skip_to_end()

	assert_signal_emitted(processor, "battle_started", "The start should be announced")


func test_every_event_is_logged():
	watch_signals(processor)
	processor.load_battle_events(_battle([
		_action({"timestamp": 0, "action": "battle_start"}),
		_action({"timestamp": 100, "action": "damage", "damage": 2, "player": 2}),
		_action({"timestamp": 200, "action": "miss", "player": 2})
	]))

	processor.skip_to_end()

	assert_signal_emit_count(processor, "log_message", 3,
		"Every event should produce a line in the battle log")


func test_an_unknown_action_still_reaches_the_log():
	# The server can add an action kind before the client knows about it. It
	# should still show, not vanish.
	watch_signals(processor)
	processor.load_battle_events(_battle([
		_action({"timestamp": 0, "action": "some_new_action", "player": 1})
	]))

	processor.skip_to_end()

	assert_signal_emitted(processor, "log_message", "An unknown action should still be logged")


# ============ Damage arithmetic ============

func test_damage_reduces_the_right_player():
	GameStateManager.current_round = 1
	var quota = GameStateManager.get_round_quota()
	processor.load_battle_events(_battle([
		_action({"timestamp": 0, "action": "damage", "damage": 4, "player": 1})
	]))

	processor.skip_to_end()

	assert_eq(processor.player1_hp, quota - 4, "Player 1 took the hit")
	assert_eq(processor.player2_hp, quota, "Player 2 was not touched")


func test_a_defeat_puts_health_at_zero():
	processor.load_battle_events(_battle([
		_action({"timestamp": 0, "action": "player_defeated", "player": 2})
	]))

	processor.skip_to_end()

	assert_eq(processor.player2_hp, 0, "A defeated player should be on zero")


func test_healing_reaches_the_health_bar():
	GameStateManager.current_round = 1
	var quota = GameStateManager.get_round_quota()
	processor.load_battle_events(_battle([
		_action({"timestamp": 0, "action": "damage", "damage": 6, "player": 1}),
		_action({"timestamp": 100, "action": "heal", "damage": 4, "player": 1})
	]))
	watch_signals(processor)

	processor.skip_to_end()

	assert_eq(processor.player1_hp, quota - 2, "A heal should put health back")
	assert_signal_emitted(processor, "healing_done", "A heal should be announced")


func test_a_heal_cannot_take_health_past_full():
	GameStateManager.current_round = 1
	var quota = GameStateManager.get_round_quota()
	processor.load_battle_events(_battle([
		_action({"timestamp": 0, "action": "heal", "damage": 99, "player": 1})
	]))

	processor.skip_to_end()

	assert_eq(processor.player1_hp, quota, "Health should stop at full")


func test_a_buff_is_announced_by_name():
	processor.load_battle_events(_battle([
		_action({"timestamp": 0, "action": "buff", "player": 1,
			"details": {"buff_name": "speed", "actual_value": 0.2}})
	]))
	watch_signals(processor)

	processor.skip_to_end()

	# The name travels in the server's details, under buff_name.
	assert_signal_emitted_with_parameters(processor, "buff_applied", [1, "speed"])


func test_a_debuff_is_announced_by_name():
	processor.load_battle_events(_battle([
		_action({"timestamp": 0, "action": "debuff", "player": 2,
			"details": {"debuff_name": "memory_leaked", "actual_value": 1}})
	]))
	watch_signals(processor)

	processor.skip_to_end()

	assert_signal_emitted_with_parameters(
		processor, "debuff_applied", [2, "memory_leaked"])


func test_damage_over_time_wears_health_down():
	GameStateManager.current_round = 1
	var quota = GameStateManager.get_round_quota()
	processor.load_battle_events(_battle([
		_action({"timestamp": 0, "action": "dot", "damage": 3, "player": 2,
			"details": {"debuff_name": "memory_leaked"}})
	]))

	processor.skip_to_end()

	assert_eq(processor.player2_hp, quota - 3, "Damage over time should still hurt")


# ============ The client knows every action the server can send ============

func test_the_client_handles_every_action_the_server_declares():
	# The server publishes its action names as an enum in its OpenAPI schema.
	# Anything in there that the client does not recognise falls through to the
	# generic log line, which is exactly how heals, buffs and debuffs were lost.
	var http = HTTPRequest.new()
	add_child(http)
	http.request(OS.get_environment("BATTLE_SERVER_URL") + "/openapi.json")
	var result = await http.request_completed
	assert_eq(result[1], 200, "Should be able to read the server's schema")
	http.queue_free()

	var schema = JSON.parse_string(result[3].get_string_from_utf8())
	var declared = schema["components"]["schemas"]["BattleActionName"]["enum"]
	assert_gt(declared.size(), 0, "The server should declare its action names")

	# What a well-formed action of each kind carries. Anything not listed here
	# needs no details.
	var details_for = {
		"buff": {"buff_name": "speed", "actual_value": 0.2},
		"debuff": {"debuff_name": "memory_leaked", "actual_value": 1},
		"dot": {"debuff_name": "memory_leaked"},
		"cpu_fail": {"reason": "Insufficient CPU"}
	}

	for action_name in declared:
		var messages: Array = []
		var record = func(message: String, _colour: Color): messages.append(message)
		processor.log_message.connect(record)

		processor.load_battle_events(_battle([_action({
			"action": action_name, "player": 1, "damage": 1,
			"details": details_for.get(action_name, null)
		})]))
		processor.skip_to_end()
		processor.log_message.disconnect(record)

		assert_eq(messages.size(), 1, "One action should log one line")
		assert_false("Action=" in messages[0],
			"The client should recognise '%s', not fall through to the generic line"
				% action_name)
