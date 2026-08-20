extends GutTest
# Tests for combining_overlay.gd, the arcs, the glow and the progress label
# drawn over the shop screen (GDD 5.3).
#
# What is drawn cannot be read back out of a headless run, so these check what
# it was told to draw and where that lands: an arc between the right two items,
# an item lit or not, a label saying the right thing in the right place.

const Overlay = preload("res://scripts/combining_overlay.gd")

var overlay: Control


func before_each():
	overlay = Overlay.new()
	overlay.size = Vector2(1000, 800)
	add_child_autofree(overlay)


func _item(at: Vector2, size := Vector2(40, 40)) -> Control:
	var item := Control.new()
	item.position = at
	item.size = size
	overlay.add_child(item)
	return item


# ============ The arcs ============

func test_it_draws_nothing_until_it_is_told_to():
	assert_eq(overlay.arcs(), [], "no arcs")
	assert_eq(overlay.glowing(), [], "nothing lit")
	assert_eq(overlay.label_text(), "", "and nothing said")


func test_an_arc_reaches_from_the_held_item_to_each_partner():
	var held := _item(Vector2(100, 100))
	var one := _item(Vector2(400, 100))
	var other := _item(Vector2(100, 400))

	overlay.lines_from(held, [one, other])

	assert_eq(overlay.arcs().size(), 2, "one arc per partner")


func test_an_arc_starts_and_finishes_on_the_edge_of_an_item():
	"""Between two middles it would run under both pictures."""
	var held := _item(Vector2(0, 0))          # middle at (20, 20)
	var partner := _item(Vector2(300, 0))     # middle at (320, 20)

	overlay.lines_from(held, [partner])
	var ends = overlay.arcs()[0]

	assert_eq(ends[0], Vector2(40, 20), "out of the right wall of the first")
	assert_eq(ends[1], Vector2(300, 20), "into the left wall of the second")


func test_the_arcs_follow_an_item_that_moves():
	"""The item an arc comes from is usually the one being dragged."""
	var held := _item(Vector2(0, 0))
	var partner := _item(Vector2(300, 0))
	overlay.lines_from(held, [partner])
	var before = overlay.arcs()[0][0]

	held.position = Vector2(0, 200)

	assert_ne(overlay.arcs()[0][0], before, "the arc moved with the item")


func test_arcs_are_taken_away_when_the_item_is_let_go_of():
	var held := _item(Vector2(0, 0))
	overlay.lines_from(held, [_item(Vector2(300, 0))])

	overlay.no_lines()

	assert_eq(overlay.arcs(), [])


func test_an_item_that_has_gone_is_not_drawn_to():
	"""The shop redraws itself under the pointer: an item bought out of it is
	freed while the arc pointing at it is still up."""
	var held := _item(Vector2(0, 0))
	var bought := _item(Vector2(300, 0))
	overlay.lines_from(held, [bought])

	bought.free()

	assert_eq(overlay.arcs(), [], "and it does not take the screen down with it")


# ============ The glow ============

func test_the_items_of_a_combination_are_lit():
	var one := _item(Vector2(10, 10))
	var other := _item(Vector2(60, 10))

	overlay.glow_around([[one, other]])

	assert_eq(overlay.glowing().size(), 2, "both items are lit")
	assert_true(overlay.glowing().has(Rect2(10, 10, 40, 40)))


func test_two_combinations_at_once_are_both_lit():
	var group = [_item(Vector2(0, 0)), _item(Vector2(50, 0))]
	var another = [_item(Vector2(0, 100)), _item(Vector2(50, 100))]

	overlay.glow_around([group, another])

	assert_eq(overlay.glowing().size(), 4)


func test_the_glow_goes_out_when_nothing_is_about_to_combine():
	overlay.glow_around([[_item(Vector2(0, 0)), _item(Vector2(50, 0))]])

	overlay.glow_around([])

	assert_eq(overlay.glowing(), [])


func test_the_glow_does_not_depend_on_the_arcs():
	"""It is not an answer to a question the player asked. It is a warning
	about what happens if they do nothing."""
	var lit := _item(Vector2(0, 0))
	overlay.glow_around([[lit, _item(Vector2(50, 0))]])

	overlay.lines_from(_item(Vector2(300, 300)), [])
	overlay.no_lines()

	assert_eq(overlay.glowing().size(), 2, "still lit")


# ============ The progress label ============

func test_it_says_what_an_item_is_on_the_way_to():
	var part := _item(Vector2(100, 200))

	overlay.progress("Long Poll 2/3", part)

	assert_eq(overlay.label_text(), "Long Poll 2/3")


func test_the_label_stands_above_the_item_it_is_about():
	var part := _item(Vector2(100, 200))

	overlay.progress("Long Poll 2/3", part)
	var label: Label = overlay.get_node("Progress")

	assert_lt(label.position.y, 200.0, "above the item, not over it")
	assert_almost_eq(label.position.x + label.size.x / 2.0, 120.0, 1.0,
		"and in the middle of it")


func test_saying_nothing_takes_the_label_away():
	var part := _item(Vector2(100, 200))
	overlay.progress("Long Poll 2/3", part)

	overlay.progress("", part)

	assert_eq(overlay.label_text(), "")


func test_a_label_asked_for_over_nothing_is_not_shown():
	overlay.progress("Long Poll 2/3", null)

	assert_eq(overlay.label_text(), "")


# ============ The bloom where two items became one ============

func test_a_merge_leaves_a_bloom_behind():
	overlay.flash_at(Vector2(120, 90))

	assert_eq(overlay.flashes(), 1)


func test_a_bloom_goes_out_by_itself():
	overlay.flash_at(Vector2(120, 90), 0.2)

	# Two frames of a tenth of a second each, which is longer than it lives.
	overlay._process(0.1)
	overlay._process(0.15)

	assert_eq(overlay.flashes(), 0, "and nothing is left to take away by hand")


func test_two_merges_in_one_round_are_two_blooms():
	overlay.flash_at(Vector2(120, 90))
	overlay.flash_at(Vector2(300, 90))

	assert_eq(overlay.flashes(), 2)
