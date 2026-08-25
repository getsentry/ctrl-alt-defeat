extends GutTest
# Comprehensive tests for BattleScreen

const APITypes = preload("res://scripts/api_types.gd")
const Presentation = preload("res://scripts/presentation.gd")

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
		# Every action the engine records is stamped with where both fighters
		# stand, so a fixture without that is not a battle the client is ever
		# given -- and the screen reads its bars off it.
		"actions": [
			{"timestamp": 0, "source": "system", "action": "battle_start",
				"player": 0, "target": null, "damage": null,
				"details": {"hp": [80, 80], "max_hp": [80, 80]}},
			{"timestamp": 1000, "source": "test_item", "action": "activate",
				"player": 1, "target": null, "damage": null,
				"details": {"hp": [80, 80], "max_hp": [80, 80]}},
			{"timestamp": 1500, "source": "enemy", "action": "damage",
				"player": 2, "target": "player", "damage": 20,
				"details": {"hp": [80, 60], "max_hp": [80, 80]}},
			{"timestamp": 5000, "source": "player", "action": "death",
				"player": 2, "target": null, "damage": null,
				"details": {"hp": [80, 60], "max_hp": [80, 80]}}
		],
		"opponent_name": "AI Opponent",
		"opponent_type": "ai",
		"player_inventory": {
			"inventory_grid": [],
			"server_containers": [
				TestHelpers.container_data({"id": "srv1", "position": [2, 3]})
			]
		},
		"enemy_inventory": {
			"inventory_grid": [],
			"server_containers": [
				TestHelpers.container_data({"id": "srv2", "position": [2, 3]})
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

func test_the_clock_counts_up_and_against_nothing():
	"""A battle has no length to run out of, so the clock only counts up.

	Section 7.1: nightfall is what ends a battle, not a time limit. A clock
	reading "4.2 / 20s" told a player the battle stops at twenty seconds,
	which is not true of any battle the engine plays.
	"""
	var timer_label = battle_screen.time_label
	assert_not_null(timer_label, "Timer should be displayed")
	assert_true(timer_label is Label, "Timer should be a Label")

	# Hold the playhead still at a known moment and let the screen read it.
	battle_screen.battle_active = true
	battle_screen.event_processor.is_playing = true
	battle_screen.event_processor.paused = true
	battle_screen.event_processor.played = 4.2
	battle_screen._process(0.0)

	assert_eq(timer_label.text, "4.2s",
		"The clock should say how far into the battle we are, and nothing else")

func test_a_speed_change_reaches_the_charges_already_filling():
	"""A cooldown is a battle second like the rest of the battle. One left
	filling at the old pace finishes after the item has fired again."""
	battle_screen.battle_speed_multiplier = 1.0
	var rack = battle_screen.player_inventory
	assert_not_null(rack, "setup: the screen draws the player's rack")
	# The fixture's rack is empty, and this is about what happens to the items
	# standing on it. The container it holds stands at (2, 3).
	rack.place_shop_item(TestHelpers.item({"id": "charging"}), Vector2i(2, 3))
	assert_false(rack.items.is_empty(), "setup: an item is on the rack")
	var visual = rack.items[0]

	battle_screen._on_toggle_speed()

	assert_eq(visual.charge_pace, battle_screen.battle_speed_multiplier,
		"Every item on the rack charges at the speed the battle is replayed at")


# ============ What a buff chip says when it is hovered ============

func test_a_buff_from_the_timeline_carries_what_it_does():
	"""The whole path: an action in the timeline, through the processor, onto
	a chip beside the fighter. Testing the hud on its own missed that the
	identifier has to survive the journey."""
	GameStateManager.status_rules = APITypes.StatusRules.new({"statuses": [{
		"status": "regenerating", "shown": "regenerating", "kind": "buff",
		"each": 1, "one": "Heals 1 every 2 seconds",
		"many": "Heals {total} every 2 seconds",
	}]})

	battle_screen.event_processor._process_event(_buff_action("regenerating"))
	await get_tree().process_frame

	var row = battle_screen.hud._effects["player_buff"]
	assert_eq(row.get_child_count(), 1, "a chip for it")

	battle_screen.hud._explain(row.get_child(0))

	assert_true(is_instance_valid(battle_screen.hud._explaining),
		"and hovering it puts up a card")
	assert_eq(battle_screen.hud._explaining.each_label.text,
		"Heals 1 every 2 seconds")
	autofree(battle_screen.hud._explaining)


func _buff_action(status: String) -> APITypes.BattleAction:
	return APITypes.BattleAction.new({
		"timestamp": 1000, "source": "an_item", "action": "buff",
		"player": 1, "target": null, "damage": null,
		"details": {
			"buff_name": status, "shown": status, "actual_value": 1,
			"hp": [80, 80], "max_hp": [80, 80],
		},
	})


# ============ The CPU bar between the moments ============

func test_the_bar_and_the_number_read_the_same_line():
	battle_screen.current_time = 0.5
	battle_screen._read_the_cpu_bars()

	battle_screen._update_stats_display()

	assert_almost_eq(battle_screen.player_stamina_bar.value,
		battle_screen._cpu_shown[1], 0.001)
	assert_true(battle_screen.player_stamina_label.text.begins_with(
		"%.1f" % battle_screen._cpu_shown[1]),
		"reads %s" % battle_screen.player_stamina_label.text)


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
	# The result is drawn by the round result overlay, which _on_battle_ended()
	# drops over the finished battle. Calling that here would swap the scene
	# tree out from under the run, because with nothing to animate the overlay
	# continues straight on. So check the routing.
	# What the overlay draws is covered by test_round_result_overlay.gd.
	assert_true(battle_screen.has_method("_on_battle_ended"),
		"Battle end should be handled")
	assert_true(battle_screen.has_method("_show_round_result"),
		"Battle end should show the run scoreboard")
	assert_true(ResourceLoader.exists("res://scenes/RoundResultOverlay.tscn"),
		"The overlay it shows should exist")
	assert_true(battle_screen.has_method("_go_to_round_over"),
		"Reading the result should lead out of the battle")
	assert_true(ResourceLoader.exists("res://scenes/UnifiedGridUI.tscn"),
		"and back to the shop, which is where the next round is played from")
	assert_true(ResourceLoader.exists("res://scenes/GameOverScreen.tscn"),
		"unless the run is over")

func test_battle_ended_stops_playback():
	# _on_battle_ended() sets battle_active = false, then waits and shows the
	# overlay, which changes scene. A test cannot call it: the scene swap fires
	# later, during another test or teardown, and takes the engine down.
	# Testing this needs the scene change split out of _on_battle_ended().
	pending("_on_battle_ended() changes scene on a timer. Not safe to call in a test.")

func test_continue_button_after_battle():
	# There is no Continue button on BattleScreen. The round result overlay
	# waits for a click instead, and moves on by itself when there is no
	# display to click on. Covered by test_round_result_overlay.gd.
	pending("BattleScreen has no Continue button. The round result overlay waits for the click.")

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


func _wait_for_playback_start() -> bool:
	"""_ready() starts playback a frame later, which is what fills player_data."""
	for i in range(120):
		if battle_screen.player_data.has("max_health"):
			return true
		await get_tree().process_frame
	return false

# ============ Cosmetic effects ============
#
# Headless draws no animations, so these check that the screen still asks for
# the right effect. Without them a broken effect call site would be invisible.

func test_damage_asks_for_a_damage_number():
	assert_true(await _wait_for_playback_start(), "Playback should start")
	Presentation.clear_requests()

	battle_screen._on_damage_dealt(1, 7, 18, "test_item")

	assert_eq(Presentation.request_count("damage_number"), 1,
		"Taking damage should ask for a damage number")
	var data = Presentation.requests("damage_number")[0]["data"]
	assert_eq(data["player"], 1, "Should be for the player who took the damage")
	assert_eq(data["amount"], 7, "Should carry the amount of damage")


func test_the_bars_are_up_before_the_battle_starts():
	# Playback waits half a second, and the scene's bars are Godot's own, which
	# read a hundred out of a hundred until something says otherwise. That was
	# long enough to see a full hundred flash up on a battle fought for eighty.
	assert_eq(battle_screen.player_health_bar.max_value, 80.0,
		"The bar should be scaled before anything is played")
	assert_eq(battle_screen.player_health_bar.value, 80.0,
		"and full, because nothing has happened yet")
	assert_eq(battle_screen.player_health_label.text, "80/80",
		"and the number should say the same")


func test_poison_says_it_is_poison():
	# It arrives on its own clock, off an item that struck some time ago, so a
	# player watching their health fall with nobody hitting them has to be able
	# to see why.
	assert_true(await _wait_for_playback_start(), "Playback should start")
	Presentation.clear_requests()

	battle_screen._on_damage_dealt(1, 4, 16, "venom", "dot")

	var data = Presentation.requests("damage_number")[0]["data"]
	assert_eq(data["kind"], "dot", "The number should know what hurt them")


func test_poison_is_written_in_another_colour_than_a_blow():
	# The numbers themselves are only drawn where animations run, so what the
	# colours mean is asked for rather than looked at.
	assert_ne(battle_screen.hurt_colour("dot"), battle_screen.hurt_colour("damage"),
		"Poison and a blow should not be written in the same colour")
	assert_eq(battle_screen.hurt_colour("critical_hit"), battle_screen.hurt_colour("damage"),
		"and anything else that hurts is a blow until it says otherwise")


func test_fatigue_is_written_in_another_colour_again():
	# It comes from no item and lands on both fighters at once, so reading it
	# as a blow sends the player looking for a blow that is not there.
	var tired = battle_screen.hurt_colour("fatigue")
	assert_ne(tired, battle_screen.hurt_colour("damage"),
		"Fatigue and a blow should not be written in the same colour")
	assert_ne(tired, battle_screen.hurt_colour("dot"),
		"nor fatigue and poison, which arrive for different reasons")


func test_health_spent_on_block_is_not_written_as_a_wound():
	# "Convert 50 health into 100 Block" takes health and nothing hit them.
	# Written in the colour Block is written in, because that is where it went.
	var spent = battle_screen.hurt_colour("convert_health")
	assert_ne(spent, battle_screen.hurt_colour("damage"),
		"A price and a blow should not be written in the same colour")
	assert_eq(spent, battle_screen.SHIELDED,
		"and it should be written in the one the Block it bought is")


func _with_an_item_to_throw() -> void:
	"""The fixture's racks are empty, and a blow throws the item that made it"""
	battle_screen.player_inventory.load_inventory_state(APITypes.InventoryState.new({
		"server_containers": [TestHelpers.container_data({"id": "srv1", "position": [2, 3]})],
		"inventory_grid": [TestHelpers.placed_item_data({"id": "blade", "position": [2, 3]})],
	}))


func test_a_blow_throws_the_item_that_made_it():
	assert_true(await _wait_for_playback_start(), "Playback should start")
	_with_an_item_to_throw()
	Presentation.clear_requests()

	battle_screen._show_item_activation("blade", 2, "damage")

	assert_eq(Presentation.request_count("item_strike"), 1,
		"A blow should throw a copy of the item that made it")
	assert_eq(Presentation.requests("item_strike")[0]["data"]["player"], 2,
		"through whoever it landed on")


func test_a_miss_is_thrown_at_the_other_fighter_all_the_same():
	# A hit says who was hurt; a miss says who swung. Read the same way round,
	# every miss was thrown at the fighter who threw it.
	assert_true(await _wait_for_playback_start(), "Playback should start")
	_with_an_item_to_throw()
	Presentation.clear_requests()

	battle_screen._show_item_activation("blade", 1, "miss")

	assert_eq(Presentation.requests("item_strike")[0]["data"]["player"], 2,
		"The rack it stands in says who swung it, whatever the action says")


func test_mending_somebody_throws_nothing_at_them():
	assert_true(await _wait_for_playback_start(), "Playback should start")
	_with_an_item_to_throw()
	Presentation.clear_requests()

	battle_screen._show_item_activation("blade", 1, "heal")

	assert_eq(Presentation.request_count("item_strike"), 0,
		"A red item falling through somebody says they were hit")


func test_healing_asks_for_a_heal_effect():
	assert_true(await _wait_for_playback_start(), "Playback should start")
	Presentation.clear_requests()

	battle_screen._on_healing_done(1, 5, 30)

	assert_eq(Presentation.request_count("heal_effect"), 1,
		"Healing should ask for a heal effect")
	assert_eq(Presentation.requests("heal_effect")[0]["data"]["amount"], 5,
		"Should carry the amount healed")


func test_nightfall_asks_to_darken_the_city():
	assert_true(await _wait_for_playback_start(), "Playback should start")
	Presentation.clear_requests()

	battle_screen._on_nightfall()

	assert_eq(Presentation.request_count("nightfall"), 1,
		"Night falling should ask for the screen to say so")


func test_block_asks_for_a_block_effect():
	assert_true(await _wait_for_playback_start(), "Playback should start")
	Presentation.clear_requests()

	battle_screen._on_block_activated(2, 4)

	assert_eq(Presentation.request_count("block_effect"), 1,
		"Blocking should ask for a block effect")
	assert_eq(Presentation.requests("block_effect")[0]["data"]["player"], 2,
		"Should be for the player who blocked")


func test_effects_draw_nothing_headless():
	assert_true(await _wait_for_playback_start(), "Playback should start")
	# The point of skipping: no stray nodes are left behind for the teardown to
	# trip over.
	var children_before = battle_screen.get_child_count()

	battle_screen._on_damage_dealt(1, 7, 18, "test_item")
	battle_screen._on_healing_done(1, 5, 30)
	battle_screen._on_block_activated(2, 4)
	await get_tree().process_frame

	assert_eq(battle_screen.get_child_count(), children_before,
		"A skipped effect should add no nodes")


func test_damage_updates_health_even_though_it_does_not_animate():
	assert_true(await _wait_for_playback_start(), "Playback should start")
	# Skipping the animation must not skip the state change it accompanies.
	battle_screen.player_data["health"] = 25

	battle_screen._on_damage_dealt(1, 7, 18, "test_item")

	assert_eq(battle_screen.player_data["health"], 18,
		"Health should follow the event, with or without animation")


# ============ Stat readouts ============

func test_both_players_have_a_full_stat_readout():
	# Each side shows a health bar, a health number, a stamina bar and a
	# stamina number. Both sets sit together on the stats panel in the middle
	# now, rather than one in each bottom corner, so this checks the screen's
	# own references rather than where in the tree they hang.
	var readouts = {
		"player health bar": battle_screen.player_health_bar,
		"player health number": battle_screen.player_health_label,
		"player stamina bar": battle_screen.player_stamina_bar,
		"player stamina number": battle_screen.player_stamina_label,
		"opponent health bar": battle_screen.enemy_health_bar,
		"opponent health number": battle_screen.enemy_health_label,
		"opponent stamina bar": battle_screen.enemy_stamina_bar,
		"opponent stamina number": battle_screen.enemy_stamina_label,
	}
	for what in readouts:
		assert_not_null(readouts[what], "The %s should exist" % what)
		assert_true(readouts[what].is_inside_tree(), "The %s should be drawn" % what)


func test_stat_readouts_show_numbers_once_the_battle_starts():
	assert_true(await _wait_for_playback_start(), "Playback should start")

	assert_ne(battle_screen.player_health_label.text, "",
		"Player health should read as a number, not blank")
	assert_true("/" in battle_screen.player_health_label.text,
		"Health should read as current out of max")
	assert_ne(battle_screen.player_stamina_label.text, "",
		"Player stamina should read as a number, not blank")


func test_health_bar_tracks_the_health_number():
	assert_true(await _wait_for_playback_start(), "Playback should start")

	# What the battle was fought for, off the battle itself.
	var quota = battle_screen.event_processor.player1_max_hp
	assert_eq(battle_screen.player_health_bar.max_value, float(quota),
		"The bar should be scaled to the quota the battle was fought for")
	assert_eq(battle_screen.player_health_bar.value, float(battle_screen.player_data["health"]),
		"The bar should agree with the underlying health")


func test_player_names_are_filled_in():
	GameStateManager.player_name = "Tester"
	var label = battle_screen.find_child("Player1NameLabel", true, false)
	assert_ne(label.text, "", "Player 1 should be named")


# ============ Battle log ============

func test_battle_log_fills_up_during_playback():
	assert_true(await _wait_for_playback_start(), "Playback should start")

	# Let a few events play at the headless speed
	for i in range(30):
		if battle_screen.battle_log_container.get_parsed_text().strip_edges() != "":
			break
		await get_tree().process_frame

	assert_ne(battle_screen.battle_log_container.get_parsed_text().strip_edges(), "",
		"The battle log should show what happened")


func test_log_message_appends_to_the_log():
	battle_screen.battle_log_container.clear()

	battle_screen._on_log_message("A thing happened", Color.WHITE)

	assert_true("A thing happened" in battle_screen.battle_log_container.get_parsed_text(),
		"A logged message should appear in the log")


# ============ The music gets out of the way ============
#
# The round result arrives with a win or a loss sting. A sting over a battle
# track still in full flow is two things saying different at once, so the
# music goes down as soon as the fighting stops.

func test_the_battle_has_music():
	var music = battle_screen.get_node_or_null("BattleMusic")
	assert_not_null(music, "The battle screen should carry a music player")
	assert_not_null(music.stream, "and that player should have something to play")
	assert_true(music.stream.loop,
		"which loops, because a battle can run longer than the track")


func test_the_music_stops_when_the_battle_ends():
	var music = battle_screen.get_node_or_null("BattleMusic")
	if music == null:
		return
	music.play()
	assert_true(music.playing, "the music should be going before the battle ends")

	battle_screen._fade_out_music()
	await get_tree().process_frame

	assert_false(music.playing,
		"and stopped once it has, so the round result sting is heard alone")


func test_fading_music_that_is_not_playing_is_harmless():
	# The battle can end with the music already stopped -- a second call, or a
	# run where it never started -- and that must not error.
	var music = battle_screen.get_node_or_null("BattleMusic")
	if music == null:
		return
	music.stop()
	battle_screen._fade_out_music()
	await get_tree().process_frame
	assert_false(music.playing, "nothing to fade, and nothing broken by asking")


# ------------------------------------------------------------------ skins
#
# The player's Sentaur wears their chosen skin here, and only theirs (GDD 11).
# These pin the choice down rather than trusting whatever this machine happens
# to have saved: the ordering bug below shipped once and was only caught
# because the settings file on hand held a skin of a different shape.

const SETTINGS := "user://player_settings.cfg"

var _kept := ""
var _existed := false


func _keep_settings() -> void:
	_existed = FileAccess.file_exists(SETTINGS)
	if _existed:
		_kept = FileAccess.get_file_as_string(SETTINGS)


func _put_settings_back() -> void:
	if _existed:
		var file := FileAccess.open(SETTINGS, FileAccess.WRITE)
		file.store_string(_kept)
		file.close()
	elif FileAccess.file_exists(SETTINGS):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(SETTINGS))
	_kept = ""


func _screen_wearing(id: String) -> Node:
	"""A fresh battle screen, built with `id` already chosen."""
	Skins.choose(id)
	var screen = battle_scene.instantiate()
	add_child_autofree(screen)
	await get_tree().process_frame
	return screen


func test_the_player_wears_the_chosen_skin() -> void:
	_keep_settings()
	var screen = await _screen_wearing("neko")
	var player: TextureRect = screen.get_node("Player1Container/CharacterDisplay")
	assert_eq(player.texture.resource_path, Skins.by_id("neko")["battle"])
	_put_settings_back()


func test_the_opponent_does_not() -> void:
	# An opponent in our own skin reads as a mirror match that is not happening.
	_keep_settings()
	var screen = await _screen_wearing("neko")
	var enemy: TextureRect = screen.get_node("Player2Container/CharacterDisplay")
	assert_eq(enemy.texture.resource_path, Skins.by_id("classic")["battle"])
	_put_settings_back()


func test_a_skinned_fighter_keeps_its_own_shape() -> void:
	# The skin has to be on before anything lays the screen out. A fighter is
	# drawn to the shape of its picture, read at the moment it is placed, so a
	# skin put on afterwards leaves it stretched to the shape of the one it
	# replaced. That is exactly what happened.
	_keep_settings()
	var screen = await _screen_wearing("nightshift")
	var player: TextureRect = screen.get_node("Player1Container/CharacterDisplay")
	var art: Vector2 = player.texture.get_size()
	assert_almost_eq(player.size.y / player.size.x, art.y / art.x, 0.01,
		"a skinned fighter should keep the shape of its own artwork")
	_put_settings_back()
