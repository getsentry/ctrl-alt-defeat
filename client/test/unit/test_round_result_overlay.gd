extends GutTest
# The run scoreboard that drops over the battle when a round ends.
#
# It is given the totals from *after* the round, because that is what the
# server has already applied, and works out what to draw and what to animate
# from the outcome. Section 6.3 of the Game Design Document.

const Presentation = preload("res://scripts/presentation.gd")

var overlay_scene = preload("res://scenes/RoundResultOverlay.tscn")
var overlay


func before_each():
	Presentation.clear_requests()
	Presentation.set_recording(true)
	overlay = overlay_scene.instantiate()
	add_child(overlay)
	await get_tree().process_frame


func after_each():
	if is_instance_valid(overlay):
		remove_child(overlay)
		overlay.queue_free()
	overlay = null
	await get_tree().process_frame
	Presentation.clear_requests()


func lit_trophies() -> int:
	return _lit(overlay._trophies)


func lit_hearts() -> int:
	return _lit(overlay._hearts)


func _lit(icons: Array) -> int:
	var count := 0
	for holder in icons:
		if holder.get_node("Mask").modulate != overlay.SPENT:
			count += 1
	return count


# ============ The counters ============

func test_there_is_one_trophy_per_win_the_run_needs():
	overlay.show_result(false, 0, 5)

	assert_eq(overlay._trophies.size(), GameStateManager.WINS_TO_VICTORY,
		"A trophy for every win the run is played for")


func test_there_is_one_heart_per_try_the_run_starts_with():
	overlay.show_result(false, 0, 5)

	assert_eq(overlay._hearts.size(), GameStateManager.STARTING_LIVES,
		"A heart for every try the run starts with")


# ============ Opening on the count from before the round ============

func test_a_win_opens_one_trophy_short():
	# Four wins banked, the fourth of them won just now.
	overlay.show_result(true, 4, 3)

	assert_eq(overlay.wins_before(), 3, "Should open on the three wins banked before")
	assert_eq(overlay.lives_before(), 3, "A win costs no tries")


func test_a_loss_opens_one_heart_up():
	# Two tries left, the third spent just now.
	overlay.show_result(false, 3, 2)

	assert_eq(overlay.lives_before(), 3, "Should open on the three tries left before")
	assert_eq(overlay.wins_before(), 3, "A loss banks no wins")


func test_the_win_moves_the_next_unlit_trophy():
	overlay.show_result(true, 4, 3)

	assert_eq(overlay.changed_icon_index(), 3, "The fourth trophy is the one that lights up")


func test_the_loss_moves_the_last_lit_heart():
	overlay.show_result(false, 3, 2)

	assert_eq(overlay.changed_icon_index(), 2, "The third heart is the one that goes out")


# ============ Where it ends up ============

func test_a_win_ends_showing_the_wins_banked():
	overlay.show_result(true, 4, 3)

	assert_eq(lit_trophies(), 4, "Should end on every win banked, this one included")
	assert_eq(lit_hearts(), 3, "Should end on the tries left")


func test_a_loss_ends_showing_the_tries_left():
	overlay.show_result(false, 3, 2)

	assert_eq(lit_hearts(), 2, "Should end on the tries left, this one spent")
	assert_eq(lit_trophies(), 3, "Should end on the wins banked")


func test_a_run_with_nothing_banked_lights_nothing():
	overlay.show_result(false, 0, 4)

	assert_eq(lit_trophies(), 0, "No wins yet, so no trophy is lit")
	assert_eq(lit_hearts(), 4, "Every try left is lit")


func test_the_last_try_leaves_no_heart_lit():
	overlay.show_result(false, 2, 0)

	assert_eq(lit_hearts(), 0, "The run is out of tries")
	assert_eq(overlay.changed_icon_index(), 0, "The first heart is the one that goes out")


func test_the_winning_round_lights_every_trophy():
	overlay.show_result(true, GameStateManager.WINS_TO_VICTORY, 2)

	assert_eq(lit_trophies(), GameStateManager.WINS_TO_VICTORY, "The run is won")


# ============ Staying inside the plate ============

func test_every_slot_stays_inside_its_bar():
	# An icon left to fill the row stretches with the row, and its glow then
	# hangs over the edge of the plate. The slots are what stop that.
	overlay.show_result(false, 3, 2)
	await get_tree().process_frame

	for bar in [{"plate": overlay._wins_bar, "cells": overlay._trophies},
			{"plate": overlay._tries_bar, "cells": overlay._hearts}]:
		var plate: Rect2 = bar["plate"].get_global_rect()
		for cell in bar["cells"]:
			assert_true(plate.encloses(cell.get_global_rect()),
				"Slot %s should sit inside its bar" % cell.name)
			assert_true(plate.encloses(cell.get_node("Glow").get_global_rect()),
				"The glow on %s should sit inside its bar" % cell.name)


# ============ What it says ============

func test_a_loss_says_so():
	overlay.show_result(false, 3, 2)

	assert_eq(overlay._banner_label.text, "ROUND LOST", "Should name the result")


func test_a_win_says_so():
	overlay.show_result(true, 4, 3)

	assert_eq(overlay._banner_label.text, "ROUND WON", "Should name the result")


# ============ What it sounds like ============

func test_a_loss_cues_the_loss_sting():
	overlay.show_result(false, 3, 2)

	assert_eq(overlay._sting.stream, overlay.LOST_STING, "Should cue the loss sting")


func test_a_win_cues_the_win_sting():
	overlay.show_result(true, 4, 3)

	assert_eq(overlay._sting.stream, overlay.WON_STING, "Should cue the win sting")


func test_nothing_is_played_when_nothing_is_drawn():
	# Headless. The sting belongs to the animation, so it goes with it.
	overlay.show_result(false, 3, 2)

	assert_false(overlay._sting.playing, "A silent run should stay silent")


# ============ Moving on ============

func test_it_asks_to_draw_the_result():
	overlay.show_result(false, 3, 2)

	assert_eq(Presentation.request_count("round_result"), 1,
		"Should ask to draw the result even when nothing draws it")
	assert_false(Presentation.requests("round_result")[0]["data"]["won"],
		"Should record which result it was asked to draw")


func test_it_continues_on_its_own_when_nothing_is_drawn():
	# Headless, so there is no click coming. Waiting for one would strand the
	# run on a screen nobody can see.
	watch_signals(overlay)

	overlay.show_result(false, 3, 2)

	assert_signal_emitted(overlay, "continued", "Should move on by itself")
	assert_true(overlay.settled, "Should be showing the settled result")


func test_a_click_during_the_animation_settles_it():
	overlay.show_result(false, 3, 2)
	watch_signals(overlay)
	overlay.settled = false

	overlay._advance()

	assert_true(overlay.settled, "The result should be shown in full")
	assert_signal_not_emitted(overlay, "continued",
		"A click made the result appear, so it has not been read yet")


func test_a_click_once_it_has_settled_moves_on():
	overlay.show_result(false, 3, 2)
	watch_signals(overlay)

	overlay._advance()

	assert_signal_emitted(overlay, "continued", "Should move on")


# ============ Settling from a part-played animation ============

func test_settling_finishes_the_counters():
	overlay.show_result(true, 4, 3)
	# Put it back the way it looked before the round was applied.
	overlay.settled = false
	overlay._fill_icons()
	assert_eq(lit_trophies(), 3, "Set up: showing the count from before the round")

	overlay._settle()

	assert_eq(lit_trophies(), 4, "Settling should apply the round")
	assert_true(overlay.settled, "Settling should say so")
