extends GutTest
# Tests for item_patterns.gd, the marks drawn over an item that has no artwork.
#
# A pattern is a predicate over a point, so these ask it directly rather than
# rendering anything and looking at pixels. The properties that matter are the
# ones a player would notice: that every pattern exists, that each puts some
# ink down but not all of it, and that no two look the same.

const ItemPatterns = preload("res://scripts/item_patterns.gd")

const CELL := 45.0


func _ink_map(name: String) -> Array[bool]:
	"""Every point of one tile, as a flat list of whether there is ink."""
	var p := ItemPatterns.period(name, CELL)
	var map: Array[bool] = []
	for y in p:
		for x in p:
			map.append(ItemPatterns.is_ink(name, x, y, p))
	return map


func _ink_share(name: String) -> float:
	var map := _ink_map(name)
	var inked := 0
	for is_ink in map:
		if is_ink:
			inked += 1
	return float(inked) / map.size()


# ============ Every pattern the catalogue can ask for ============

func test_there_are_thirty_six_patterns():
	# The server holds the same list and refuses an item wearing anything else,
	# so the two have to agree.
	assert_eq(ItemPatterns.NAMES.size(), 36, "All 36 should be here")


func test_no_pattern_is_named_twice():
	var seen := {}
	for name in ItemPatterns.NAMES:
		assert_false(seen.has(name), "%s is in the list twice" % name)
		seen[name] = true


func test_solid_is_the_only_one_that_draws_nothing():
	for name in ItemPatterns.NAMES:
		var draws_nothing = ItemPatterns.draws_nothing(name)
		assert_eq(draws_nothing, name == "solid",
			"%s should%s draw nothing" % [name, "" if name == "solid" else " not"])


# ============ Each one is visible, and is not a solid block ============

func test_every_pattern_puts_some_ink_down():
	# One that inks nothing is invisible, and its item would be
	# indistinguishable from the plain colour.
	for name in ItemPatterns.NAMES:
		if name == "solid":
			continue
		assert_gt(_ink_share(name), 0.0, "%s draws nothing at all" % name)


func test_no_pattern_covers_everything():
	# One that inks every point is a flat block, and hides the colour under it.
	for name in ItemPatterns.NAMES:
		assert_lt(_ink_share(name), 0.95, "%s covers the whole square" % name)


func test_no_pattern_is_so_faint_it_cannot_be_seen():
	for name in ItemPatterns.NAMES:
		if name == "solid":
			continue
		assert_gt(_ink_share(name), 0.02,
			"%s inks so few points it would read as plain colour" % name)


# ============ No two items can look the same ============

func test_every_pattern_looks_different_from_every_other():
	# Colour says the category and pattern says the item, so two patterns that
	# draw the same thing make two items indistinguishable.
	var seen := {}
	var clashes: Array[String] = []
	for name in ItemPatterns.NAMES:
		var fingerprint := str(_ink_map(name))
		if seen.has(fingerprint):
			clashes.append("%s draws the same as %s" % [name, seen[fingerprint]])
		seen[fingerprint] = name

	assert_eq(clashes, [] as Array[String],
		"Two patterns that draw the same thing make two items indistinguishable")
	assert_eq(seen.size(), ItemPatterns.NAMES.size(), "so every one should be its own")


# ============ Scale ============

func test_a_fine_pattern_repeats_more_often_than_a_bold_one():
	assert_lt(ItemPatterns.period("stripe_h_fine", CELL),
		ItemPatterns.period("stripe_h_bold", CELL),
		"Fine should repeat in a smaller space, which is what tells them apart")


func test_a_pattern_never_gets_too_small_to_read():
	# The chest draws at 30 px and could go smaller. A one pixel period is a
	# grey wash with no shape to it.
	for name in ItemPatterns.NAMES:
		assert_gte(ItemPatterns.period(name, 8.0), 3,
			"%s would have no shape left at a tiny cell size" % name)


func test_an_unknown_pattern_draws_nothing_and_says_so():
	# An item wearing a pattern this client has never heard of should leave the
	# colour showing rather than take the grid down.
	assert_false(ItemPatterns.is_ink("no_such_pattern", 1, 1, 9),
		"An unknown pattern should put no ink down")
