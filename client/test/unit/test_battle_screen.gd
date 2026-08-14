extends GutTest
# Comprehensive tests for BattleScreen

const APITypes = preload("res://scripts/api_types.gd")

var battle_scene = preload("res://scenes/BattleScreen.tscn")
var battle_screen

func before_each():
	# Set up test battle data - create proper APITypes.BattleResult
	var battle_data = {
		"winner": 1,
		"duration": 10.0,
		"player1_quota": 80,
		"player2_quota": 0,
		"seed": 12345,
		"actions": [
			{"timestamp": 0, "source": "system", "action": "battle_start", "player": 0, "target": null, "damage": null, "details": null},
			{"timestamp": 1000, "source": "test_item", "action": "activate", "player": 1, "target": null, "damage": null, "details": null},
			{"timestamp": 1500, "source": "enemy", "action": "damage", "player": 2, "target": "player", "damage": 20, "details": {"hp": 80}},
			{"timestamp": 5000, "source": "player", "action": "death", "player": 2, "target": null, "damage": null, "details": null}
		],
		"player_inventory": {
			"items": [],
			"servers": [
				{"id": "srv1", "slug": "standard_vm", "type": "standard_vm", "position": [2, 3], "width": 2, "height": 2}
			]
		},
		"enemy_inventory": {
			"items": [],
			"servers": [
				{"id": "srv2", "slug": "standard_vm", "type": "standard_vm", "position": [2, 3], "width": 2, "height": 2}
			]
		}
	}

	var APITypes = preload("res://scripts/api_types.gd")
	GameStateManager.last_battle_result = APITypes.BattleResult.new(battle_data)
	# BattleScreen._ready() asserts when last_battle_events is empty.
	GameStateManager.last_battle_events = GameStateManager.last_battle_result.actions

	battle_screen = battle_scene.instantiate()
	add_child(battle_screen)
	await get_tree().process_frame

func after_each():
	# _ready() starts playback on a timer. Stop it before freeing the screen, or
	# the tweens and timers it started fire on freed nodes and crash the engine.
	if is_instance_valid(battle_screen):
		battle_screen.battle_active = false
		if is_instance_valid(battle_screen.event_processor):
			battle_screen.event_processor.stop_playback()
			battle_screen.event_processor.set_process(false)

	battle_screen = null
	for child in get_children():
		if is_instance_valid(child):
			# remove_child() first so is_inside_tree() is false straight away.
			# queue_free() alone defers, and _ready()'s pending timer can still
			# resume on a node that is about to die.
			remove_child(child)
			child.queue_free()
	await get_tree().process_frame
	await get_tree().process_frame

	GameStateManager.last_battle_result = null
	GameStateManager.last_battle_events = []

func test_battle_screen_loads():
	assert_not_null(battle_screen, "BattleScreen should load")
	assert_true(battle_screen.visible, "BattleScreen should be visible")

func test_ui_elements_exist():
	# The essential elements: the clock, both player name labels, the battle log.
	assert_not_null(battle_screen.time_label, "Time label should exist")
	assert_not_null(battle_screen.battle_log_container, "Battle log should exist")
	assert_not_null(
		battle_screen.find_child("Player1NameLabel", true, false),
		"Player 1 name label should exist"
	)
	assert_not_null(
		battle_screen.find_child("Player2NameLabel", true, false),
		"Player 2 name label should exist"
	)

func test_round_label_exists():
	pending("BattleScreen shows no round number.")

func test_health_bars_initialized():
	# Both bars are named HealthBar, so find_child cannot tell them apart.
	# Use the script's references.
	var p1_health = battle_screen.player_health_bar
	var p2_health = battle_screen.enemy_health_bar

	assert_not_null(p1_health, "Player 1 health bar should exist")
	assert_not_null(p2_health, "Player 2 health bar should exist")
	assert_true(p1_health is ProgressBar, "Player 1 health bar should be a ProgressBar")
	assert_true(p2_health is ProgressBar, "Player 2 health bar should be a ProgressBar")
	assert_gt(p1_health.max_value, 0.0, "Player 1 health bar should be initialised")
	assert_gt(p2_health.max_value, 0.0, "Player 2 health bar should be initialised")

func test_control_buttons():
	# Playback control is a single speed toggle.
	var controls = battle_screen.find_child("ControlButtons", true, false)
	assert_not_null(controls, "Should have a playback control bar")

	var speed_btn = battle_screen.find_child("SpeedButton", true, false)
	assert_not_null(speed_btn, "Should have playback controls")
	assert_true(
		speed_btn.pressed.is_connected(battle_screen._on_toggle_speed),
		"Speed button should be connected to _on_toggle_speed"
	)

func test_play_pause_and_skip_buttons():
	pending("BattleScreen has no play, pause or skip button, only a speed toggle.")

func test_battle_event_processor():
	# The processor is made in _ready() and added as a child.
	var processor = battle_screen.event_processor

	assert_not_null(processor, "Battle screen should create an event processor")
	assert_true(processor is BattleEventProcessor,
		"Event processor should be a BattleEventProcessor")
	assert_eq(processor.get_parent(), battle_screen,
		"Event processor should be a child of the battle screen")

	# It must be wired to the battle screen, or nothing is drawn during playback
	assert_true(processor.battle_ended.is_connected(battle_screen._on_battle_ended),
		"Event processor should tell the battle screen when the battle ends")
	assert_true(processor.damage_dealt.is_connected(battle_screen._on_damage_dealt),
		"Event processor should tell the battle screen about damage")

	# And it must have been given the battle to play
	assert_gt(processor.events.size(), 0, "Event processor should have loaded the events")

func test_grid_display():
	# The grids sit under Player1Inventory and Player2Inventory, not at the top.
	var grids = _find_all_grid_containers(battle_screen)

	assert_gte(grids.size(), 1, "Should have at least one grid display")
	assert_eq(grids.size(), 2, "Should have one grid for each player")

func _find_all_grid_containers(node: Node) -> Array:
	var found = []
	for child in node.get_children():
		if child is GridContainer:
			found.append(child)
		found.append_array(_find_all_grid_containers(child))
	return found

func test_battle_loads_from_game_state():
	await get_tree().create_timer(0.1).timeout

	assert_not_null(GameStateManager.last_battle_result,
		"Should have battle data from GameStateManager")
	assert_gt(GameStateManager.last_battle_result.actions.size(), 0,
		"Battle data should contain actions")
	assert_eq(GameStateManager.last_battle_result.winner, 1,
		"Battle data should keep the winner from the fixture")

func test_timer_display():
	var timer_label = battle_screen.time_label
	assert_not_null(timer_label, "Timer should be displayed")
	assert_true(timer_label is Label, "Timer should be a Label")

func test_animation_speed_control():
	# Speed control is $ControlButtons/SpeedButton.
	var speed_control = battle_screen.find_child("SpeedButton", true, false)
	assert_not_null(speed_control, "Speed control exists")

	# Pressing it should change the playback multiplier
	var before = battle_screen.battle_speed_multiplier
	battle_screen._on_toggle_speed()
	await get_tree().process_frame
	assert_ne(battle_screen.battle_speed_multiplier, before,
		"Speed control should change the playback speed")

func test_skip_to_end_functionality():
	pending("BattleScreen has no skip button.")

func test_battle_result_display():
	# BattleScreen shows no result itself. _on_battle_ended() waits 2 seconds and
	# then changes to PostBattleScreen, which draws the result. Calling it here
	# would swap the scene tree out from under the run, so check the routing.
	# The result text is covered by test_post_battle_screen.gd.
	assert_true(battle_screen.has_method("_on_battle_ended"),
		"Battle end should be handled")
	assert_true(battle_screen.has_method("_go_to_post_battle"),
		"Battle end should lead to the post-battle screen")
	assert_true(ResourceLoader.exists("res://scenes/PostBattleScreen.tscn"),
		"The post-battle screen it routes to should exist")

func test_battle_ended_stops_playback():
	# _on_battle_ended() sets battle_active = false, then waits 2 seconds and
	# calls change_scene_to_file(). A test cannot call it: the scene swap fires
	# later, during another test or teardown, and takes the engine down.
	# Testing this needs the scene change split out of _on_battle_ended().
	pending("_on_battle_ended() changes scene on a timer. Not safe to call in a test.")

func test_continue_button_after_battle():
	# There is no Continue button on BattleScreen. Moving on is automatic, via
	# the scene change in _go_to_post_battle().
	pending("BattleScreen has no Continue button. It changes scene automatically.")

func test_inventory_display():
	var p1_inventory = battle_screen.find_child("Player1Inventory", true, false)
	var p2_inventory = battle_screen.find_child("Player2Inventory", true, false)

	assert_not_null(p1_inventory, "Player 1 inventory should be displayed")
	assert_not_null(p2_inventory, "Player 2 inventory should be displayed")

func test_event_log_display():
	var event_log = battle_screen.battle_log_container
	assert_not_null(event_log, "Event log exists for debugging")
	assert_true(event_log is RichTextLabel, "Event log should be a RichTextLabel")

func test_responsive_layout():
	# Test that battle screen adapts to window size
	var original_size = DisplayServer.window_get_size()

	# Test smaller window
	DisplayServer.window_set_size(Vector2i(1024, 768))
	await get_tree().process_frame

	# Main elements should still be visible
	var visible_elements = 0
	for child in battle_screen.get_children():
		if child is Control and child.visible:
			visible_elements += 1

	assert_gt(visible_elements, 0, "Elements should be visible at smaller size")

	# Restore
	DisplayServer.window_set_size(original_size)
