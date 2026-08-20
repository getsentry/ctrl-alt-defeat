extends GutTest
# Tests for aura_overlay.gd, which draws the zone an item reaches into.
#
# What it draws cannot be read back out of a headless run, so these check what
# it was told to draw and how big it is drawing it.

const Overlay = preload("res://scripts/aura_overlay.gd")

var overlay: Control


func before_each():
	overlay = Overlay.new()
	add_child_autofree(overlay)


# ============ Swelling when an item is put down ============

func test_markers_are_their_own_size_until_something_is_placed():
	assert_eq(overlay.swelling(), 1.0)


func test_putting_an_item_down_swells_what_its_aura_caught():
	overlay.swell()

	overlay._process(overlay.GROW)

	assert_eq(overlay.swelling(), overlay.SWELL, "out to full size")


func test_the_swell_is_over_by_itself():
	overlay.swell()

	overlay._process(overlay.GROW + overlay.FADE + 0.01)

	assert_eq(overlay.swelling(), 1.0, "and back to its own size")


func test_the_big_one_fades_off_rather_than_shrinking():
	"""A marker easing back down reads as something deflating. This one stays
	big and goes out, leaving the ordinary marker underneath it."""
	overlay.swell()
	overlay._process(overlay.GROW + 0.001)
	var out: float = overlay.swelling()
	var solid: float = overlay.ghosting()

	overlay._process(overlay.FADE / 2.0)

	assert_eq(out, overlay.SWELL, "full size once it is out")
	assert_eq(overlay.swelling(), overlay.SWELL, "and it stays that size")
	assert_lt(overlay.ghosting(), solid, "while going out")


func test_it_is_solid_while_it_grows_and_gone_by_the_end():
	overlay.swell()
	assert_eq(overlay.ghosting(), 1.0, "solid on the way out")

	overlay._process(overlay.GROW + overlay.FADE + 0.01)

	assert_eq(overlay.ghosting(), 0.0, "and gone afterwards")


func test_the_growing_is_watchable_rather_than_instant():
	"""The eye should follow it out rather than find it already there."""
	overlay.swell()

	overlay._process(overlay.GROW * 0.25)

	assert_gt(overlay.swelling(), 1.0, "it has started")
	assert_lt(overlay.swelling(), overlay.SWELL, "and has not finished")


func test_it_is_out_quickly():
	overlay.swell()

	overlay._process(overlay.GROW / 2.0)

	assert_gt(overlay.swelling(), 1.0 + (overlay.SWELL - 1.0) * 0.5,
		"more than half way out at half way through the growing")


func test_asking_again_too_soon_is_ignored():
	"""A held button would otherwise ask on every frame, and a placement --
	which is also a click -- would swell twice."""
	overlay.swell()
	overlay._process(overlay.GROW + overlay.FADE + 0.01)
	assert_eq(overlay.swelling(), 1.0, "Setup: the first one is over")

	overlay.swell()

	assert_eq(overlay.swelling(), 1.0, "too soon, so nothing happened")


func test_asking_again_later_swells_again():
	overlay.swell()
	overlay._process(overlay.AGAIN_AFTER + 0.01)

	overlay.swell()
	overlay._process(overlay.GROW + 0.001)

	assert_eq(overlay.swelling(), overlay.SWELL)
