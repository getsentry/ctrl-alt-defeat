extends GutTest
# Tests for lightning.gd, the shape of the arc drawn between two items that go
# together (GDD 5.3).

const Lightning = preload("res://scripts/lightning.gd")


func test_it_starts_and_finishes_exactly_where_it_is_told():
	"""An arc that misses either end reads as a stroke of its own rather than
	as a line joining two items."""
	var from := Vector2(10, 20)
	var to := Vector2(200, 90)

	var points := Lightning.bolt(from, to, 1)

	assert_eq(points[0], from, "it starts on the item it comes from")
	assert_eq(points[points.size() - 1], to, "and finishes on the other one")


func test_the_same_jag_is_always_the_same_shape():
	"""A redraw is not a reshuffle: the arc only changes when the jag does."""
	assert_eq(
		Lightning.bolt(Vector2.ZERO, Vector2(100, 0), 7),
		Lightning.bolt(Vector2.ZERO, Vector2(100, 0), 7))


func test_a_different_jag_is_a_different_shape():
	assert_ne(
		Lightning.bolt(Vector2.ZERO, Vector2(100, 0), 7),
		Lightning.bolt(Vector2.ZERO, Vector2(100, 0), 8))


func test_it_wanders_but_not_far():
	"""Far enough to crackle, near enough that it still points at the item."""
	var spread := 12.0
	var points := Lightning.bolt(Vector2.ZERO, Vector2(300, 0), 3, spread)

	var wandered := 0.0
	for point in points:
		wandered = maxf(wandered, absf(point.y))
	assert_lt(wandered, spread + 0.001, "no point strays past the spread")
	assert_gt(wandered, 0.0, "and it is not a straight line")


func test_it_wanders_least_at_the_ends():
	"""The taper of an arc, rather than the teeth of a saw."""
	var points := Lightning.bolt(Vector2.ZERO, Vector2(300, 0), 5, 12.0, 12)

	var middle := absf(points[points.size() / 2].y)
	assert_lte(absf(points[1].y), middle, "the second point is nearer the line")
	assert_lte(absf(points[points.size() - 2].y), middle,
		"and so is the one before the end")


func test_two_points_are_enough_to_draw():
	var points := Lightning.bolt(Vector2.ZERO, Vector2(10, 0), 1, 4.0, 1)

	assert_gte(points.size(), 2, "a line needs at least its two ends")


func test_the_spark_runs_from_one_end_to_the_other():
	var from := Vector2(0, 0)
	var to := Vector2(100, 0)
	var points := Lightning.bolt(from, to, 2)

	assert_eq(Lightning.along(points, 0.0), from, "it starts at the start")
	assert_eq(Lightning.along(points, 1.0), to, "and finishes at the finish")
	assert_gt(Lightning.along(points, 0.5).x, 0.0, "and is somewhere in between")
	assert_lt(Lightning.along(points, 0.5).x, 100.0)


func test_the_spark_moves_at_one_speed():
	"""By length rather than by point, so it does not crawl over the short
	segments and race over the long ones."""
	var points := PackedVector2Array(
		[Vector2(0, 0), Vector2(10, 0), Vector2(110, 0)])

	assert_almost_eq(Lightning.along(points, 0.5).x, 55.0, 0.01,
		"halfway along is halfway by distance, not the middle point")


func test_the_spark_stays_on_the_line_when_asked_for_nonsense():
	var points := Lightning.bolt(Vector2.ZERO, Vector2(50, 0), 1)

	assert_eq(Lightning.along(points, -3.0), Vector2.ZERO)
	assert_eq(Lightning.along(points, 9.0), Vector2(50, 0))


func test_a_line_of_no_length_is_still_a_point():
	var points := PackedVector2Array([Vector2(5, 5), Vector2(5, 5)])

	assert_eq(Lightning.along(points, 0.5), Vector2(5, 5),
		"two items on top of each other must not divide by nothing")


func test_the_jag_changes_several_times_a_second():
	assert_eq(Lightning.jag_at(0.0), Lightning.jag_at(0.05),
		"it holds still long enough to be seen")
	assert_ne(Lightning.jag_at(0.0), Lightning.jag_at(1.0),
		"and has changed a second later")


func test_two_arcs_drawn_at_once_do_not_jag_in_step():
	"""Lines that share a shape read as one line rather than several."""
	assert_ne(Lightning.jag_at(0.5, 0), Lightning.jag_at(0.5, 1))


# ============ Where an arc meets the item it joins ============

func test_an_arc_leaves_the_item_by_its_edge():
	"""Drawn between two middles it would run under both pictures, and the end
	the player is looking at is the end they cannot see."""
	var item := Rect2(0, 0, 40, 20)

	assert_eq(Lightning.edge(item, Vector2(100, 10)), Vector2(40, 10),
		"straight out of the right wall")
	assert_eq(Lightning.edge(item, Vector2(20, -80)), Vector2(20, 0),
		"and out of the top when the other item is above")


func test_an_arc_to_something_on_top_of_it_stays_where_it_is():
	var item := Rect2(0, 0, 40, 20)

	assert_eq(Lightning.edge(item, item.get_center()), item.get_center(),
		"two items in the same place must not divide by nothing")
	assert_eq(Lightning.edge(Rect2(5, 5, 0, 0), Vector2(9, 9)), Vector2(5, 5),
		"an item with no size is a point")


# ============ An arc jags by as much as its length allows ============

func test_a_long_arc_wanders_more_than_a_short_one():
	"""Ten pixels of wander is a crackle across a rack and nothing at all
	across the room."""
	var short_hop := Lightning.arc(Vector2.ZERO, Vector2(60, 0), 3)
	var long_reach := Lightning.arc(Vector2.ZERO, Vector2(1200, 0), 3)

	assert_lt(_widest(short_hop), _widest(long_reach))


func test_a_long_arc_turns_more_often():
	assert_gt(Lightning.arc(Vector2.ZERO, Vector2(1200, 0), 3).size(),
		Lightning.arc(Vector2.ZERO, Vector2(60, 0), 3).size())


func test_even_the_shortest_arc_is_a_line():
	var points := Lightning.arc(Vector2(10, 10), Vector2(11, 11), 3)

	assert_gte(points.size(), 2)
	assert_eq(points[0], Vector2(10, 10))
	assert_eq(points[points.size() - 1], Vector2(11, 11))


func _widest(points: PackedVector2Array) -> float:
	var wandered := 0.0
	for point in points:
		wandered = maxf(wandered, absf(point.y))
	return wandered


# ============ What makes it crackle ============

func test_an_arc_grows_a_few_short_forks():
	var points := Lightning.arc(Vector2.ZERO, Vector2(600, 0), 5)

	var forks := Lightning.forks(points, 5)

	assert_gt(forks.size(), 0, "an arc without branches reads as a wire")
	assert_lte(forks.size(), 3, "and one made of branches reads as a mess")


func test_a_fork_starts_on_the_arc_and_dies_out():
	"""One that arrived anywhere would be a second arc, and the player would
	count a partner that is not there."""
	var points := Lightning.arc(Vector2.ZERO, Vector2(600, 0), 5)
	var whole := points[0].distance_to(points[points.size() - 1])

	for fork in Lightning.forks(points, 5):
		var strand: PackedVector2Array = fork
		var starts: Vector2 = strand[0]
		var on_the_arc := false
		for point in points:
			on_the_arc = on_the_arc or point.distance_to(starts) < 0.001
		assert_true(on_the_arc, "a fork leaves the arc it belongs to")
		assert_lt(starts.distance_to(strand[strand.size() - 1]), whole * 0.5,
			"and gets nowhere near the other end")


func test_the_same_jag_forks_the_same_way():
	var points := Lightning.arc(Vector2.ZERO, Vector2(600, 0), 5)

	assert_eq(Lightning.forks(points, 5), Lightning.forks(points, 5))


func test_a_line_too_short_to_fork_does_not():
	assert_eq(Lightning.forks(PackedVector2Array([Vector2.ZERO, Vector2(4, 0)]), 1),
		[])


func test_the_brightness_is_never_steady():
	"""A line held at one brightness is a wire."""
	var first := Lightning.flicker(1)

	assert_ne(first, Lightning.flicker(2))
	assert_eq(first, Lightning.flicker(1), "but it does not change on a redraw")
	assert_gt(first, 0.0, "and it never goes out altogether")
	assert_lte(first, 1.0)
