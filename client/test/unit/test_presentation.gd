extends GutTest
# Presentation decides whether cosmetic effects are drawn, and records every
# request either way.
#
# The recording is what keeps the skipping honest: a headless run draws nothing,
# so without it a broken call site would look exactly like a working one.

const Presentation = preload("res://scripts/presentation.gd")


func before_each():
	Presentation.clear_requests()
	Presentation.set_recording(true)


func after_each():
	Presentation.clear_requests()


# ============ The switch ============

func test_animations_are_off_headless():
	assert_false(Presentation.animations_enabled(),
		"A headless run should not draw animations")


func test_delay_collapses_when_animations_are_off():
	assert_eq(Presentation.delay(2.0), 0.0, "A cosmetic pause should collapse to nothing")
	assert_eq(Presentation.delay(0.5), 0.0, "Every pause should collapse, whatever its length")


# ============ Recording ============

func test_request_records_the_effect():
	Presentation.request("damage_number", {"player": 1, "amount": 7})

	assert_eq(Presentation.request_count(), 1, "The request should be recorded")
	assert_eq(Presentation.requests()[0]["effect"], "damage_number", "Should record which effect")
	assert_eq(Presentation.requests()[0]["data"]["amount"], 7, "Should record the detail")


func test_request_reports_whether_to_draw():
	# Headless, so the caller is told to skip, but the request is still recorded.
	var should_draw = Presentation.request("damage_number")

	assert_false(should_draw, "Headless should tell the caller not to draw")
	assert_eq(Presentation.request_count("damage_number"), 1,
		"Skipping must not skip the record")


func test_requests_filters_by_effect():
	Presentation.request("damage_number", {"amount": 1})
	Presentation.request("heal_effect", {"amount": 2})
	Presentation.request("damage_number", {"amount": 3})

	assert_eq(Presentation.request_count(), 3, "Should record all of them")
	assert_eq(Presentation.request_count("damage_number"), 2, "Should count one kind")
	assert_eq(Presentation.request_count("heal_effect"), 1, "Should count the other kind")
	assert_eq(Presentation.requests("damage_number")[1]["data"]["amount"], 3,
		"Should keep them in order")


func test_requests_are_ordered_oldest_first():
	Presentation.request("first")
	Presentation.request("second")

	var order = Presentation.requests().map(func(r): return r["effect"])
	assert_eq(order, ["first", "second"], "Requests should read oldest first")


func test_clear_requests_empties_the_record():
	Presentation.request("damage_number")
	Presentation.clear_requests()

	assert_eq(Presentation.request_count(), 0, "clear_requests() should empty the record")


func test_recording_can_be_turned_off():
	Presentation.set_recording(false)
	Presentation.request("damage_number")

	assert_eq(Presentation.request_count(), 0, "Nothing should be recorded while recording is off")

	Presentation.set_recording(true)


func test_returned_requests_are_a_copy():
	Presentation.request("damage_number")

	var taken = Presentation.requests()
	taken.clear()

	assert_eq(Presentation.request_count(), 1,
		"Changing the returned array must not change the record")
