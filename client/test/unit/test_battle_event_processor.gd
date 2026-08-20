extends GutTest
# Tests for battle_event_processor.gd, which replays a finished battle.
#
# The server decides the whole battle up front and sends a timeline. This class
# walks that timeline and announces what happened. These tests cover the walk
# and the announcements, not the wire format of an action.

const BattleEventProcessorScript = preload("res://scripts/battle_event_processor.gd")
const APITypes = preload("res://scripts/api_types.gd")

## The server's schema, relative to the client project, and the enum in it that
## names every action a battle can contain.
const SCHEMAS_PATH := "../server/schemas.py"
const ACTION_ENUM := "BattleActionName"

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


## What the fixtures here are fought for. The engine stamps both fighters'
## quotas on every action it records, so an action without them is not one the
## client will ever be given.
const QUOTA := 25


func _standing(hp: Array, extra: Dictionary = {}) -> Dictionary:
	"""An action's details: where both fighters stand once it has landed"""
	var details := {"hp": hp, "max_hp": [QUOTA, QUOTA]}
	details.merge(extra, true)
	return details


func _action(overrides: Dictionary = {}) -> Dictionary:
	var data = {
		"timestamp": 0,
		"source": "system",
		"action": "battle_start",
		"target": null,
		"damage": null,
		"player": 0,
		"details": _standing([QUOTA, QUOTA])
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


# ============ When it is over ============

func test_health_is_read_off_the_battle_rather_than_worked_out():
	# The engine stamps both fighters' quotas on every action it records. The
	# client used to start them on a quota from a table of its own and subtract
	# its way down, and that table disagreed with the engine's from round two
	# on -- so a battle ran for seconds after the screen had counted somebody
	# to nothing.
	watch_signals(processor)
	processor.load_battle_events(_battle([
		_action({"timestamp": 10, "source": "a", "action": "damage",
			"player": 2, "damage": 3,
			"details": {"hp": [70, 41], "max_hp": [70, 70]}}),
	]))
	processor.skip_to_end()

	assert_eq(processor.player2_max_hp, 70, "The battle says what it was fought for")
	var hurt = get_signal_parameters(processor, "damage_dealt", 0)
	assert_eq(hurt[2], 41,
		"and what is left, which is not the same as the last figure less the blow")


# ============ Loading ============

func test_loading_a_battle_makes_it_ready_to_play():
	GameStateManager.current_round = 1
	processor.load_battle_events(_battle([
		_action({"timestamp": 0}),
		_action({"timestamp": 500, "action": "damage", "damage": 3, "player": 2})
	]))

	assert_eq(processor.events.size(), 2, "Every event should be loaded")
	assert_eq(processor.current_event_index, 0, "Playback should start from the first event")
	assert_false(processor.is_playing, "Loading a battle should not start it")
	assert_eq(processor.battle_duration, 10.0, "The duration should come from the battle")
	assert_eq(processor.player1_hp, QUOTA, "Player 1 starts on what the battle says")
	assert_eq(processor.player2_hp, QUOTA, "and so does Player 2")


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
	processor.load_battle_events(_battle([
		_action({"timestamp": 100, "action": "damage", "damage": 5, "player": 2,
			"details": _standing([QUOTA, 20])}),
		_action({"timestamp": 200, "action": "damage", "damage": 3, "player": 2,
			"details": _standing([QUOTA, 17])})
	]))

	processor.skip_to_end()

	assert_eq(processor.player2_hp, 17, "It should end where the last action left it")


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
	processor.load_battle_events(_battle([
		_action({"timestamp": 0, "action": "damage", "damage": 4, "player": 1,
			"details": _standing([21, QUOTA])})
	]))

	processor.skip_to_end()

	assert_eq(processor.player1_hp, 21, "Player 1 took the hit")
	assert_eq(processor.player2_hp, QUOTA, "Player 2 was not touched")


func test_a_defeat_puts_health_at_zero():
	processor.load_battle_events(_battle([
		_action({"timestamp": 0, "action": "player_defeated", "player": 2,
			"details": _standing([QUOTA, 0])})
	]))

	processor.skip_to_end()

	assert_eq(processor.player2_hp, 0, "A defeated player should be on zero")


func test_healing_reaches_the_health_bar():
	processor.load_battle_events(_battle([
		_action({"timestamp": 0, "action": "damage", "damage": 6, "player": 1,
			"details": _standing([19, QUOTA])}),
		_action({"timestamp": 100, "action": "heal", "damage": 4, "player": 1,
			"details": _standing([23, QUOTA])})
	]))
	watch_signals(processor)

	processor.skip_to_end()

	assert_eq(processor.player1_hp, 23, "A heal should put health back")
	assert_signal_emitted(processor, "healing_done", "A heal should be announced")


func test_a_heal_cannot_take_health_past_full():
	# The engine caps it and says so. The screen shows what it is told, which
	# is the whole of the client's job here.
	processor.load_battle_events(_battle([
		_action({"timestamp": 0, "action": "heal", "damage": 99, "player": 1,
			"details": _standing([QUOTA, QUOTA])})
	]))

	processor.skip_to_end()

	assert_eq(processor.player1_hp, QUOTA, "Health should stop at full")


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
	processor.load_battle_events(_battle([
		_action({"timestamp": 0, "action": "dot", "damage": 3, "player": 2,
			"details": _standing([QUOTA, 22], {"debuff_name": "memory_leaked"})})
	]))

	processor.skip_to_end()

	assert_eq(processor.player2_hp, 22, "Damage over time should still hurt")


# ============ Where the CPU stands ============

func test_an_action_says_where_both_fighters_cpu_stood():
	# The client used to invent a full pool of ten and never move it: three
	# times the real pool, and static for the whole battle. Nothing in the
	# timeline said otherwise, because nothing in the timeline said anything.
	var seen = {}
	processor.cpu_changed.connect(
		func(player, cpu, max_cpu): seen[player] = [cpu, max_cpu])

	processor.load_battle_events(_battle([_action({
		"details": {"cpu": [1.5, 2.75], "max_cpu": [3, 4]}})]))
	processor.skip_to_end()

	assert_eq(seen[1], [1.5, 3.0], "The player's pool, as the battle had it")
	assert_eq(seen[2], [2.75, 4.0], "and the opponent's, which is not the same")


func test_an_action_without_a_cpu_level_says_nothing_about_it():
	# Not every action carries one: an engine method called on its own outside
	# a battle has no players to ask.
	var seen = []
	processor.cpu_changed.connect(func(_p, _c, _m): seen.append(true))

	processor.load_battle_events(_battle([_action({"details": null})]))
	processor.skip_to_end()

	assert_eq(seen.size(), 0, "Better silent than made up")


func test_the_pool_can_grow_during_a_battle():
	# Infrastructure raises max_cpu, so the pool is not fixed for the battle
	# and cannot be read once at the start.
	var pools = []
	processor.cpu_changed.connect(
		func(player, _cpu, max_cpu): if player == 1: pools.append(max_cpu))

	processor.load_battle_events(_battle([
		_action({"details": {"cpu": [3.0, 3.0], "max_cpu": [3, 3]}}),
		_action({"timestamp": 100, "details": {"cpu": [4.0, 3.0], "max_cpu": [5, 3]}}),
	]))
	processor.skip_to_end()

	assert_eq(pools, [3.0, 5.0], "The pool should follow what the battle says")


# ============ Changing pace without moving the playhead ============

func _play_for(seconds: float) -> void:
	await get_tree().create_timer(seconds).timeout


func test_the_playhead_does_not_jump_when_the_speed_changes():
	# It used to be the wall clock since the start times the speed, so changing
	# the speed rescaled every second already played: eight seconds in, going
	# from 1x to 2x moved the playhead to sixteen and fired everything in
	# between at once.
	processor.load_battle_events(_battle([_action({"timestamp": 60000})]))
	processor.start_playback(1.0)
	await _play_for(0.2)

	var before = processor.get_current_time()
	processor.set_playback_speed(4.0)
	var after = processor.get_current_time()

	assert_almost_eq(after, before, 0.02,
		"Changing the speed should not move where the battle has got to")
	processor.stop_playback()


func test_a_faster_speed_covers_more_battle_in_the_same_time():
	processor.load_battle_events(_battle([_action({"timestamp": 60000})]))
	processor.start_playback(1.0)
	await _play_for(0.15)
	var slow = processor.get_current_time()

	processor.set_playback_speed(8.0)
	var from = processor.get_current_time()
	await _play_for(0.15)
	var fast = processor.get_current_time() - from

	assert_gt(fast, slow, "Eight times the speed should cover more ground")
	processor.stop_playback()


func test_a_held_battle_stays_where_it_is():
	processor.load_battle_events(_battle([_action({"timestamp": 60000})]))
	processor.start_playback(1.0)
	await _play_for(0.15)

	processor.set_paused(true)
	var held = processor.get_current_time()
	await _play_for(0.2)

	assert_almost_eq(processor.get_current_time(), held, 0.01,
		"A held battle should not run on")
	processor.stop_playback()


func test_letting_go_carries_on_from_where_it_was_held():
	processor.load_battle_events(_battle([_action({"timestamp": 60000})]))
	processor.start_playback(1.0)
	await _play_for(0.15)
	processor.set_paused(true)
	var held = processor.get_current_time()
	await _play_for(0.2)

	processor.set_paused(false)

	assert_almost_eq(processor.get_current_time(), held, 0.02,
		"It should carry on from where it stopped, not skip the pause")
	processor.stop_playback()


func test_holding_it_twice_changes_nothing():
	processor.load_battle_events(_battle([_action({"timestamp": 60000})]))
	processor.start_playback(1.0)
	await _play_for(0.1)
	processor.set_paused(true)
	var held = processor.get_current_time()

	processor.set_paused(true)

	assert_almost_eq(processor.get_current_time(), held, 0.01,
		"Asking again for what is already true should do nothing")
	processor.stop_playback()


# ============ The client knows every action the server can send ============

func test_the_client_handles_every_action_the_server_declares():
	# The server declares its action names as an enum, and says in as many
	# words that the set is the contract between the two sides. Anything in
	# there that the client does not recognise falls through to the generic log
	# line, which is exactly how heals, buffs and debuffs were lost.
	var declared := _action_names_the_server_declares()
	assert_gt(declared.size(), 0, "The server should declare its action names")

	# What a well-formed action of each kind carries. Anything not listed here
	# needs no details.
	var details_for = {
		"buff": {"buff_name": "speed", "actual_value": 0.2},
		"debuff": {"debuff_name": "memory_leaked", "actual_value": 1},
		"dot": {"debuff_name": "memory_leaked"},
		"cpu_fail": {"reason": "Insufficient CPU"},
		"cpu_drain": {"amount": 1},
		"cleanse": {"removed": {"memory_leaked": 2}}
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

		assert_eq(messages.size(), 1,
			"'%s' should log one line" % action_name)
		assert_false("Action=" in messages[0],
			"The client should recognise '%s', not fall through to the generic line"
				% action_name)


## The action names the server declares, read straight out of its schema.
##
## Off disk rather than over HTTP. The old version of this asked a running
## server for /openapi.json, which meant the check only ran when someone
## remembered to start one - and an HTTPRequest never completes under the GUT
## command line runner anyway, so in practice it never ran at all. The file is
## the same contract, it needs nothing running, and it works in the plain unit
## suite.
func _action_names_the_server_declares() -> Array:
	var path := ProjectSettings.globalize_path("res://").path_join(SCHEMAS_PATH)
	var file := FileAccess.open(path, FileAccess.READ)
	assert_not_null(file, "Should be able to read %s" % path)
	if file == null:
		return []
	var source := file.get_as_text()
	file.close()

	var start := source.find("class %s" % ACTION_ENUM)
	assert_true(start != -1, "%s should declare %s" % [SCHEMAS_PATH, ACTION_ENUM])
	if start == -1:
		return []
	var end := source.find("\nclass ", start + 1)
	if end == -1:
		end = source.length()

	var names := []
	var member := RegEx.create_from_string('=\\s*"([a-z_]+)"')
	for found in member.search_all(source.substr(start, end - start)):
		names.append(found.get_string(1))
	return names
