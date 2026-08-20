extends GutTest
# Tests for aura.gd: which squares an item's zone covers and which of them are
# doing anything (GDD 4.3, 4.4).
#
# The point of the display is that a player can count the marked squares and
# know how many items their aura is worth. So the rules that matter here are
# what an aura acts on, and that it is worth one however many squares it lands
# on the same item with.

const APITypes = preload("res://scripts/api_types.gd")
const Aura = preload("res://scripts/aura.gd")


func _item(overrides: Dictionary = {}) -> APITypes.Item:
	return APITypes.Item.new(TestHelpers.item_data(overrides))


func _rack(items: Dictionary) -> Callable:
	"""What stands where, as the grid would answer it."""
	return func(square: Vector2i): return items.get(square)


func _at(squares: Array) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	for square in squares:
		out.append(Vector2i(square[0], square[1]))
	return out


# ============ What an aura acts on ============

func test_a_zone_that_wants_nothing_acts_on_everything():
	"""\"Triggers 10% faster for each Star item\" reaches whatever stands
	there."""
	var anything := [{"any_of": [], "all_of": []}]

	assert_true(Aura.acts_on(anything, _item({"category": "problem"})))
	assert_true(Aura.acts_on(anything, _item({"category": "pet"})))


func test_a_zone_nothing_acts_through_acts_on_nothing():
	"""68 of the 117 items that draw a zone have no clause built yet. Their
	zone is real, does nothing, and must never light up."""
	assert_false(Aura.acts_on([], _item()))


func test_a_narrowed_zone_acts_only_on_what_it_wants():
	# "Star Pets and Star Scripts trigger faster".
	var pets_and_scripts := [{"any_of": ["pet", "script"], "all_of": []}]

	assert_true(Aura.acts_on(pets_and_scripts, _item({"category": "pet"})))
	assert_true(Aura.acts_on(pets_and_scripts, _item({"category": "script"})))
	assert_false(Aura.acts_on(pets_and_scripts, _item({"category": "problem"})))


func test_a_zone_wanting_weapons_acts_on_a_weapon():
	"""Edge Cache: "Star Weapons gain 1 damage".

	A weapon is not a category -- it is any of the three kinds an item can
	attack with -- so the server sends the three and the item is matched on
	the kind it carries. This is the shape of clause the server sends for 21
	items, and every one of them used to send nothing at all, so no weapon
	ever lit up under one.
	"""
	var weapons := [{"any_of": ["melee", "ranged", "magic"], "all_of": []}]

	assert_true(Aura.acts_on(weapons, _item({"kinds": ["melee"]})), "a blade")
	assert_true(Aura.acts_on(weapons, _item({"kinds": ["magic"]})), "a spell")
	assert_false(Aura.acts_on(weapons, _item({"kinds": ["food"]})), "not a snack")


func test_a_kind_narrows_it_as_well_as_a_category():
	"""A tag is either, so "Star Pets" and "Star nature-items" read the same."""
	var nature := [{"any_of": ["nature"], "all_of": []}]

	assert_true(Aura.acts_on(nature, _item({"kinds": ["nature"]})))
	assert_false(Aura.acts_on(nature, _item({"kinds": ["fire"]})))


func test_wanting_all_of_them_wants_all_of_them():
	var both := [{"any_of": [], "all_of": ["fire", "melee"]}]

	assert_true(Aura.acts_on(both, _item({"kinds": ["fire", "melee"]})))
	assert_false(Aura.acts_on(both, _item({"kinds": ["fire"]})))


func test_two_clauses_on_one_zone_both_count():
	"""An item may act through the same zone twice over."""
	var either := [
		{"any_of": ["pet"], "all_of": []},
		{"any_of": ["script"], "all_of": []},
	]

	assert_true(Aura.acts_on(either, _item({"category": "script"})))


func test_casing_in_the_catalogue_does_not_matter():
	var pets := [{"any_of": ["pet"], "all_of": []}]

	assert_true(Aura.acts_on(pets, _item({"category": "Pet"})))


# ============ Which squares are doing anything ============

func test_an_empty_square_is_marked_and_does_nothing():
	var marked = Aura.markers(_at([[1, 1]]), _rack({}), [{"any_of": [], "all_of": []}])

	assert_eq(marked.size(), 1, "the square is still drawn")
	assert_false(marked[0]["doing"], "and it is doing nothing")


func test_a_square_with_something_the_aura_acts_on_is_doing_something():
	var pet := _item({"id": "cat", "category": "pet"})
	var marked = Aura.markers(
		_at([[1, 1]]), _rack({Vector2i(1, 1): pet}),
		[{"any_of": ["pet"], "all_of": []}])

	assert_true(marked[0]["doing"])
	assert_eq(Aura.worth(marked), 1, "the aura is worth one item here")


func test_a_square_with_something_it_does_not_act_on_is_not():
	"""A zone narrowed to pets lands on a weapon and does nothing, and saying
	otherwise would make the display a decoration."""
	var weapon := _item({"id": "sword", "category": "problem"})
	var marked = Aura.markers(
		_at([[1, 1]]), _rack({Vector2i(1, 1): weapon}),
		[{"any_of": ["pet"], "all_of": []}])

	assert_false(marked[0]["doing"])
	assert_eq(Aura.worth(marked), 0)


func test_an_item_under_several_squares_counts_once():
	"""The rule that makes this a measure: an aura reaches an item once,
	however many of its squares land on it. A player counting the marked
	squares is counting the items their aura is worth."""
	var wide := _item({"id": "wide", "category": "pet"})
	var zone := _at([[1, 1], [2, 1], [3, 1]])
	var marked = Aura.markers(zone, _rack({
		Vector2i(1, 1): wide, Vector2i(2, 1): wide, Vector2i(3, 1): wide,
	}), [{"any_of": ["pet"], "all_of": []}])

	assert_eq(Aura.worth(marked), 1, "one item, so one square is doing anything")
	assert_true(marked[0]["doing"], "and it is the first of them, in reading order")
	assert_false(marked[1]["doing"])
	assert_false(marked[2]["doing"])


func test_two_items_in_the_zone_are_worth_two():
	var one := _item({"id": "a", "category": "pet"})
	var other := _item({"id": "b", "category": "pet"})
	var marked = Aura.markers(_at([[1, 1], [2, 1]]), _rack({
		Vector2i(1, 1): one, Vector2i(2, 1): other,
	}), [{"any_of": ["pet"], "all_of": []}])

	assert_eq(Aura.worth(marked), 2)


func test_the_squares_are_walked_in_reading_order():
	"""So the marked square is always the top-left-most one an item covers,
	and the same rack always draws the same way."""
	var pet := _item({"id": "cat", "category": "pet"})
	var marked = Aura.markers(_at([[5, 5], [1, 1], [3, 1]]), _rack({
		Vector2i(5, 5): pet, Vector2i(3, 1): pet,
	}), [{"any_of": ["pet"], "all_of": []}])

	assert_eq(marked[0]["square"], Vector2i(1, 1))
	assert_eq(marked[1]["square"], Vector2i(3, 1))
	assert_true(marked[1]["doing"], "the earlier square is the one that counts")
	assert_false(marked[2]["doing"])


func test_an_aura_that_does_nothing_marks_no_square():
	var pet := _item({"id": "cat", "category": "pet"})
	var marked = Aura.markers(_at([[1, 1]]), _rack({Vector2i(1, 1): pet}), [])

	assert_eq(marked.size(), 1, "the zone is still drawn")
	assert_eq(Aura.worth(marked), 0, "and none of it is worth anything")


# ============ The two markers ============

func test_a_star_has_five_points():
	var points = Aura.star_points(Vector2(50, 50), 10.0)

	assert_eq(points.size(), 10, "five out and five in")
	var reaches := 0
	for point in points:
		if absf(point.distance_to(Vector2(50, 50)) - 10.0) < 0.01:
			reaches += 1
	assert_eq(reaches, 5, "five of them reach the full radius")


func test_a_diamond_is_a_square_on_its_corner():
	var points = Aura.diamond_points(Vector2(50, 50), 10.0)

	assert_eq(points.size(), 4)
	assert_eq(points[0], Vector2(50, 40), "a point straight up")
	assert_eq(points[2], Vector2(50, 60), "and one straight down")


func test_both_markers_stay_inside_the_square_they_are_drawn_in():
	"""They are laid over an item's artwork, so one spilling into the next
	square would read as covering an item it does not."""
	for points in [Aura.star_points(Vector2.ZERO, 10.0),
			Aura.diamond_points(Vector2.ZERO, 10.0)]:
		for point in points:
			assert_lte(point.length(), 10.001)


func test_a_star_and_a_diamond_are_not_the_same_shape():
	"""Two zones the player has to tell apart at a glance."""
	assert_ne(Aura.star_points(Vector2.ZERO, 10.0).size(),
		Aura.diamond_points(Vector2.ZERO, 10.0).size())


func test_a_marker_says_which_item_it_is_lighting():
	"""The marker says which square. The screen also has to light the item,
	and it is the same answer, so it comes from the same place."""
	var pet := _item({"id": "cat", "category": "pet"})
	var marked = Aura.markers(_at([[1, 1], [2, 1]]), _rack({
		Vector2i(1, 1): pet, Vector2i(2, 1): pet,
	}), [{"any_of": ["pet"], "all_of": []}])

	assert_eq(Aura.lit_by(marked), ["cat"] as Array[String],
		"named once, however many squares land on it")


func test_nothing_is_lit_where_the_aura_does_nothing():
	var weapon := _item({"id": "sword", "category": "problem"})
	var marked = Aura.markers(_at([[1, 1]]), _rack({Vector2i(1, 1): weapon}),
		[{"any_of": ["pet"], "all_of": []}])

	assert_eq(Aura.lit_by(marked), [] as Array[String])
