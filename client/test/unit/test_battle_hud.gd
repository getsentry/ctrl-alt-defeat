extends GutTest
# The battle screen's furniture: the clock, the bars, the log drawer and the
# numbers that fly off a hit.
#
# Most of these hold a piece of the screen that was wrong rather than merely
# plain: a control off the edge of the window, a bar that never filled, numbers
# thrown where a panel covered them.

const APITypes = preload("res://scripts/api_types.gd")
const BattleHud = preload("res://scripts/battle_hud.gd")

var battle_scene = preload("res://scenes/BattleScreen.tscn")
var battle_screen
var hud


func before_each():
	var battle_data = {
		"winner": 1,
		"duration": 10.0,
		"player1_quota": 25,
		"player2_quota": 0,
		"seed": 1,
		"actions": [
			# Both fighters' quotas, as the engine stamps them on every action.
			{"timestamp": 0, "source": "system", "action": "battle_start", "player": 0,
				"target": null, "damage": null,
				"details": {"hp": [25, 25], "max_hp": [25, 25]}}
		],
		"opponent_name": "AI Opponent",
		"opponent_type": "ai",
		"player_inventory": {"items": [], "servers": [
			TestHelpers.container_data({"id": "srv1", "position": [1, 2]})]},
		"enemy_inventory": {"items": [], "servers": [
			TestHelpers.container_data({"id": "srv2", "position": [1, 2]})]}
	}
	GameStateManager.last_battle_result = APITypes.BattleResult.new(battle_data)
	GameStateManager.last_battle_events = GameStateManager.last_battle_result.actions

	battle_screen = battle_scene.instantiate()
	add_child(battle_screen)
	await get_tree().process_frame
	hud = battle_screen.hud


func after_each():
	if is_instance_valid(battle_screen):
		battle_screen.battle_active = false
		if is_instance_valid(battle_screen.event_processor):
			battle_screen.event_processor.stop_playback()
			battle_screen.event_processor.set_process(false)
	hud = null
	battle_screen = null
	for child in get_children():
		if is_instance_valid(child):
			remove_child(child)
			child.queue_free()
	await get_tree().process_frame
	await get_tree().process_frame

	GameStateManager.last_battle_result = null
	GameStateManager.last_battle_events = []


func window() -> Rect2:
	# Not get_viewport_rect(): headless that is a 64 by 64 dummy window.
	return Rect2(Vector2.ZERO, Vector2(
		ProjectSettings.get_setting("display/window/size/viewport_width"),
		ProjectSettings.get_setting("display/window/size/viewport_height")))


# ============ Everything on screen ============

func test_the_speed_control_is_on_screen():
	# The scene parked it 1133 pixels above the bottom of a 1050 pixel window,
	# which is off the top of it. No player could ever press it.
	var button = battle_screen.find_child("SpeedButton", true, false)

	assert_true(window().encloses(button.get_global_rect()),
		"The speed control should be inside the window, not off the top of it")


func test_the_clock_is_on_screen():
	assert_true(window().encloses(hud.clock_plate.get_global_rect()),
		"The clock should be inside the window")


func test_the_speed_control_says_the_speed_the_battle_starts_at():
	var button = battle_screen.find_child("SpeedButton", true, false)

	assert_eq(button.text, "%.0fx" % battle_screen.battle_speed_multiplier,
		"The scene's hardcoded label had nothing to do with the real speed")


# ============ The bars ============

func test_every_bar_has_a_fill():
	# They were stock ProgressBars, which draw a flat block whatever the value
	# is: the number said 20/25 while the bar said nothing at all.
	for bar in [battle_screen.player_health_bar, battle_screen.enemy_health_bar,
			battle_screen.player_stamina_bar, battle_screen.enemy_stamina_bar]:
		assert_true(bar.has_theme_stylebox_override("fill"),
			"%s should have a fill to draw" % bar.name)


func test_a_health_bar_turns_amber_near_the_end():
	var bar = battle_screen.player_health_bar
	bar.max_value = 100
	bar.value = 90
	hud.health_changed(bar)
	assert_eq(bar.get_meta("fill_color"), BattleHud.HEALTH_FILL,
		"Set up: a healthy bar reads as healthy")

	bar.value = 10
	hud.health_changed(bar)

	assert_eq(bar.get_meta("fill_color"), BattleHud.HEALTH_LOW,
		"A fighter about to go down should read as such")


func test_a_health_bar_goes_back_when_healed_past_the_line():
	var bar = battle_screen.enemy_health_bar
	bar.max_value = 100
	bar.value = 10
	hud.health_changed(bar)

	bar.value = 80
	hud.health_changed(bar)

	assert_eq(bar.get_meta("fill_color"), BattleHud.HEALTH_FILL,
		"Healing back up should take the warning off")


# ============ The log ============

func test_the_log_starts_shut():
	# It used to sit open across the middle of the screen, over the ground the
	# fighters stand on and over the numbers thrown off them.
	assert_false(hud.is_log_open(), "The log should start shut")
	assert_false(hud.log_drawer.visible, "Nothing should be drawn for a shut log")


func test_the_log_opens_and_shuts_again():
	hud.toggle_log()
	assert_true(hud.is_log_open(), "Should open")
	assert_true(hud.log_drawer.visible, "Should be drawn when open")

	hud.toggle_log()

	assert_false(hud.is_log_open(), "Should shut again")
	assert_false(hud.log_drawer.visible, "Should stop being drawn")


func test_the_log_button_says_which_way_it_goes():
	var shut = hud.log_button.text
	hud.toggle_log()

	assert_ne(hud.log_button.text, shut, "The button should say what pressing it does")


func test_the_log_still_reaches_the_text_it_writes_to():
	# The drawer reparents the panel the log lives in, and the screen keeps
	# writing to the label inside it.
	assert_not_null(battle_screen.battle_log_container, "The log text should still exist")
	assert_true(battle_screen.battle_log_container.is_inside_tree(),
		"The log text should still be in the tree after being moved")


# ============ Numbers off a hit ============

func test_the_two_fighters_stand_on_opposite_sides():
	var player = hud.fighter_at(1)
	var enemy = hud.fighter_at(2)

	assert_lt(player.x, window().size.x / 2.0, "The player stands left of centre")
	assert_gt(enemy.x, window().size.x / 2.0, "The opponent stands right of centre")


func test_a_number_lands_on_the_fighter_it_happened_to():
	# They used to be thrown at two fixed points near the middle, where the log
	# panel covered them.
	var label = hud.combat_number(1, "-7", Color.WHITE, 40)
	await get_tree().process_frame

	var thrown_at = label.get_global_rect().get_center()
	assert_almost_eq(thrown_at.x, hud.fighter_at(1).x, 120.0,
		"A number should land near the fighter it happened to")
	assert_eq(label.text, "-7", "It should say what happened")


func test_numbers_landing_together_do_not_print_on_top_of_each_other():
	var first = hud.combat_number(2, "-3", Color.WHITE, 40)
	var second = hud.combat_number(2, "-4", Color.WHITE, 40)

	assert_ne(first.position, second.position,
		"Two hits at once should be readable as two")


# ============ What an item sounds like ============

func test_the_hit_is_ready_to_play():
	# Both halves of this have been silently missing at some point: the sound
	# that says an item landed was declared and never wired, and before that
	# the signal behind it was declared and never emitted.
	assert_not_null(hud._hit, "The hit sound should be loaded")
	assert_gt(hud._voices.size(), 0, "and have somewhere to play")


func test_hits_landing_together_do_not_all_sound():
	# Six items landing at once should read as one blow. Without the gate it is
	# six copies of the same tick over each other.
	hud.item_fired()
	var after_one = hud._next_voice
	for i in 5:
		hud.item_fired()

	# _next_voice only moves on when a hit actually plays, which makes it the
	# honest count of how many were let through. The clock is not: six calls in
	# the same millisecond all read the same tick.
	assert_eq(hud._next_voice, after_one,
		"A hit in the same instant as the last should be swallowed")


func test_a_hit_can_sound_again_once_the_gate_has_passed():
	hud.item_fired()
	var after_one = hud._next_voice
	# Reach past the gate rather than waiting on the clock.
	hud._last_hit -= BattleHud.HIT_GAP_MS * 2

	hud.item_fired()

	assert_ne(hud._next_voice, after_one, "The next blow should sound")


# ============ The stats, in the middle ============

func test_both_fighters_stats_are_side_by_side_in_the_middle():
	# They used to be two panels in the bottom corners, as far apart as a
	# screen allows, so comparing the two meant looking corner to corner.
	var plate = hud.stats_plate.get_global_rect()

	assert_almost_eq(plate.get_center().x, window().size.x / 2.0, 2.0,
		"The stats should sit across the middle of the screen")
	assert_gt(plate.get_center().y, window().size.y / 2.0,
		"and below the racks, not over them")
	for bar in [battle_screen.player_health_bar, battle_screen.enemy_health_bar,
			battle_screen.player_stamina_bar, battle_screen.enemy_stamina_bar]:
		assert_true(plate.encloses(bar.get_global_rect()),
			"%s should be on the stats panel" % bar.name)


func test_a_long_name_stays_in_its_own_half():
	# A ghost opponent is named by whoever played them, so nothing promises the
	# length. The server made this worse for a while by appending the round
	# number to its own AI's name.
	battle_screen.opponent_name_label.text = "A Very Long Handle Indeed (Round 12)"
	await get_tree().process_frame

	var name_at = battle_screen.opponent_name_label.get_global_rect()
	var middle = hud.stats_plate.get_global_rect().get_center().x

	assert_gt(name_at.position.x, middle,
		"The opponent's name should stay on the opponent's side")
	assert_true(hud.stats_plate.get_global_rect().encloses(name_at),
		"and inside the panel")
	assert_true(battle_screen.opponent_name_label.clip_text,
		"and be cut off rather than allowed to run over the blades")


func test_the_two_fighters_read_left_and_right_of_the_split():
	var middle = hud.stats_plate.get_global_rect().get_center().x

	assert_lt(battle_screen.player_health_bar.get_global_rect().get_center().x, middle,
		"The player reads on the left")
	assert_gt(battle_screen.enemy_health_bar.get_global_rect().get_center().x, middle,
		"The opponent reads on the right")


func test_a_buff_shows_up_against_the_fighter_that_got_it():
	hud.add_effect(1, "overclock", true)

	var row = hud._effects["player_buff"]
	assert_eq(row.get_child_count(), 1, "The buff should be listed")
	assert_eq(row.get_child(0).text, "overclock", "It should say which buff")
	assert_eq(hud._effects["enemy_buff"].get_child_count(), 0,
		"The opponent did not get it")


func test_the_same_buff_twice_is_counted_not_repeated():
	hud.add_effect(2, "shielded", true)
	hud.add_effect(2, "shielded", true)

	var row = hud._effects["enemy_buff"]
	assert_eq(row.get_child_count(), 1, "One chip, not a row that grows forever")
	assert_eq(row.get_child(0).text, "shielded x2", "It should say how many")


func test_a_debuff_is_kept_apart_from_a_buff():
	hud.add_effect(1, "memory_leaked", false)

	assert_eq(hud._effects["player_debuff"].get_child_count(), 1,
		"A debuff belongs under debuffs")
	assert_eq(hud._effects["player_buff"].get_child_count(), 0,
		"and not under buffs")


# ============ The fighters ============

func test_the_fighters_stand_in_the_bottom_corners():
	# The scene drew them at six times their own size across the middle of the
	# screen, taking up more room than the racks and the numbers together.
	var player = battle_screen.get_node("Player1Container/CharacterDisplay")
	var enemy = battle_screen.get_node("Player2Container/CharacterDisplay")

	for fighter in [player, enemy]:
		var stood = fighter.get_global_rect()
		assert_gt(stood.position.x, -1.0, "A fighter should not run off the side")
		assert_lt(stood.end.x, window().size.x + 1.0, "or off the other side")
		assert_gt(stood.get_center().y, window().size.y / 2.0,
			"A fighter should stand in the bottom half")
	assert_lt(player.get_global_rect().get_center().x, window().size.x / 2.0,
		"The player stands on the left")
	assert_gt(enemy.get_global_rect().get_center().x, window().size.x / 2.0,
		"The opponent stands on the right")


func test_the_fighters_feet_run_past_the_bottom_edge():
	# Cut off by the frame they stand in, they read as standing in the room.
	# Ending neatly above the edge, they read as pasted on top of it.
	for side in ["Player1Container/CharacterDisplay", "Player2Container/CharacterDisplay"]:
		var stood = battle_screen.get_node(side).get_global_rect()
		assert_gt(stood.end.y, window().size.y,
			"%s should be cropped by the bottom edge" % side)
		assert_lt(stood.position.y, window().size.y,
			"but their head should still be on screen")


func test_each_fighter_stands_on_a_shadow():
	for side in ["Player1Container", "Player2Container"]:
		var shadow = battle_screen.get_node(side).find_child(side + "Shadow", true, false)
		assert_not_null(shadow, "%s should have a shadow under them" % side)
		# Above the crop, or the one thing saying they are standing on
		# something is off screen along with their feet.
		assert_lt(shadow.get_global_rect().end.y, window().size.y,
			"The shadow should be on screen")


func test_a_fighter_stands_on_the_same_smudge_as_everyone_else():
	# One picture of a shadow, under every standing character in the game. This
	# screen used to draw its own out of a stack of ellipses.
	var shadow = battle_screen.get_node("Player1Container").find_child(
		"Player1ContainerShadow", true, false)

	assert_not_null(shadow.texture, "The shadow should be drawn from artwork")
	assert_true("contact_shadow" in shadow.texture.resource_path,
		"and from the artwork the other screens use, got: %s"
		% shadow.texture.resource_path)


func test_a_fighter_is_drawn_to_the_shape_of_its_own_artwork():
	# The proportions used to be written down here. The artwork has been
	# replaced twice since, and a fighter drawn to the last one's shape is a
	# fighter stretched.
	var player = battle_screen.get_node("Player1Container/CharacterDisplay")
	var art: Vector2 = player.texture.get_size()

	assert_almost_eq(player.size.y / player.size.x, art.y / art.x, 0.01,
		"A fighter should keep the shape of the picture it is drawn from")


func test_the_fighters_do_not_cover_the_stats():
	var plate = hud.stats_plate.get_global_rect()

	for side in ["Player1Container/CharacterDisplay", "Player2Container/CharacterDisplay"]:
		var fighter = battle_screen.get_node(side).get_global_rect()
		assert_false(plate.intersects(fighter),
			"%s should stand clear of the numbers" % side)


# ============ The racks ============

func test_both_racks_are_on_screen():
	for grid in [battle_screen.player_inventory, battle_screen.enemy_inventory]:
		# The drawn size, not size: both panels are scaled down in the scene.
		var drawn = Rect2(grid.global_position,
			grid.size * grid.get_global_transform().get_scale())
		assert_true(window().encloses(drawn),
			"%s should be inside the window" % grid.title)


func test_the_racks_stand_level_with_each_other():
	var player = battle_screen.player_inventory
	var enemy = battle_screen.enemy_inventory

	assert_almost_eq(player.global_position.y, enemy.global_position.y, 1.0,
		"The two racks should stand at the same height")


func test_the_racks_leave_the_same_margin_at_each_edge():
	var player = battle_screen.player_inventory
	var enemy = battle_screen.enemy_inventory
	var left = player.global_position.x
	var right = window().size.x - (enemy.global_position.x
		+ enemy.size.x * enemy.get_global_transform().get_scale().x)

	assert_almost_eq(left, right, 2.0, "The racks should be inset equally")


func test_a_battle_rack_draws_no_empty_squares():
	# Empty squares say where a thing could go. Nothing can be placed during a
	# battle, so they say nothing, and drawing them turns a build into a sheet
	# of graph paper.
	assert_false(battle_screen.player_inventory.show_base_grid,
		"A battle rack should not draw the grid behind it")
	assert_false(battle_screen.enemy_inventory.show_base_grid,
		"An opponent's rack should not draw it either")
