extends GutTest
# Tests for combining.gd, which answers what the rack is on the way to and
# which items go together (GDD 5.3).
#
# Everything here is a question the screen asks while the player is moving the
# pointer around, so none of it may need the server.

const APITypes = preload("res://scripts/api_types.gd")
const Combining = preload("res://scripts/combining.gd")


func _pending(overrides: Dictionary = {}) -> APITypes.Pending:
	var data := {
		"makes": "hero_longsword",
		"have": 2,
		"need": 3,
		"ingredients": ["sword", "stone"],
		"catalysts": [],
		"missing": ["whetstone"],
	}
	data.merge(overrides, true)
	return APITypes.Pending.new(data)


func _catalogue(partners: Dictionary, names: Dictionary) -> APITypes.CombiningCatalogue:
	return APITypes.CombiningCatalogue.new({"partners": partners, "names": names})


func _knowing(waiting: Array, partners := {}, names := {}) -> Combining:
	var combining := Combining.new()
	var typed: Array[APITypes.Pending] = []
	typed.assign(waiting)
	combining.pending = typed
	if not partners.is_empty() or not names.is_empty():
		combining.catalogue = _catalogue(partners, names)
	return combining


# ============ Before the catalogue has arrived ============

func test_it_draws_no_lines_until_it_knows_the_catalogue():
	var combining := Combining.new()

	assert_false(combining.knows_the_catalogue(), "nothing has been fetched")
	assert_eq(combining.partners_of("whetstone"), [] as Array[String],
		"a screen asking early gets no partners rather than an error")


func test_an_item_it_cannot_name_is_called_by_its_type():
	var combining := _knowing([], {}, {"whetstone": "Edge Cache"})

	assert_eq(combining.name_of("whetstone"), "Edge Cache")
	assert_eq(combining.name_of("class:fire"), "class:fire",
		"a wildcard is not an item, so the catalogue has no name for it")


# ============ Which items go together ============

func test_it_answers_which_items_go_together():
	var combining := _knowing([], {
		"hero_sword": ["whetstone"],
		"whetstone": ["hero_sword", "whetstone"],
	})

	assert_true(combining.goes_with("hero_sword", "whetstone"))
	assert_true(combining.goes_with("whetstone", "whetstone"),
		"a Long Poll eats two whetstones, so one points at another")
	assert_false(combining.goes_with("hero_sword", "bloodthorne"))


func test_an_item_in_no_recipe_goes_with_nothing():
	var combining := _knowing([], {"hero_sword": ["whetstone"]})

	assert_eq(combining.partners_of("bloodthorne"), [] as Array[String])


# ============ What is about to combine ============

func test_a_finished_recipe_is_about_to_combine():
	var combining := _knowing([
		_pending({"have": 2, "need": 2, "ingredients": ["a", "b"], "missing": []}),
	])

	assert_eq(combining.about_to_combine().size(), 1)
	assert_eq(combining.groups_about_to_combine(), [["a", "b"]],
		"and both of its items are named, for the glow to join up")


func test_an_unfinished_recipe_is_not():
	var combining := _knowing([_pending({"have": 2, "need": 3})])

	assert_eq(combining.about_to_combine(), [] as Array[APITypes.Pending])
	assert_eq(combining.groups_about_to_combine(), [],
		"nothing is promised while a part is still missing")


func test_a_catalyst_is_about_to_combine_as_much_as_an_ingredient():
	"""It has to be there and touching, so the glow has to reach it."""
	var combining := _knowing([_pending({
		"makes": "serverless_function",
		"have": 2, "need": 2,
		"ingredients": ["rig"], "catalysts": ["cat"], "missing": [],
	})])

	assert_eq(combining.groups_about_to_combine(), [["rig", "cat"]],
		"the kept item is lit with the one that is eaten")


func test_the_glow_is_told_which_items_to_join_up():
	var combining := _knowing([
		_pending({"have": 2, "need": 2, "ingredients": ["a", "b"], "missing": []}),
		_pending({"makes": "blue_sage_collar", "have": 2, "need": 2,
			"ingredients": ["c"], "catalysts": ["d"], "missing": []}),
		_pending({"have": 1, "need": 3, "ingredients": ["e"]}),
	])

	assert_eq(combining.groups_about_to_combine(), [["a", "b"], ["c", "d"]],
		"one list per combination, and the unfinished one is not among them")


# ============ The progress label ============

func test_an_item_being_collected_is_labelled_with_what_it_is_becoming():
	var combining := _knowing(
		[_pending()], {}, {"hero_longsword": "Long Poll"})

	assert_eq(combining.progress_label("sword"), "Long Poll 2/3")
	assert_eq(combining.progress_label("stone"), "Long Poll 2/3",
		"every part of it says the same thing")


func test_an_item_on_the_way_to_nothing_is_labelled_with_nothing():
	var combining := _knowing([_pending()], {}, {"hero_longsword": "Long Poll"})

	assert_eq(combining.progress_label("somebody_else"), "")


func test_an_item_that_is_about_to_combine_is_not_labelled_with_progress():
	"""It is going to combine. Naming something else it could have been
	instead would only be confusing."""
	var combining := _knowing([
		_pending({"have": 2, "need": 2, "ingredients": ["a", "b"], "missing": []}),
	], {}, {"hero_longsword": "Long Poll"})

	assert_eq(combining.progress_label("a"), "")


func test_an_item_in_two_recipes_is_labelled_with_the_nearest_one():
	"""The player is most likely collecting the one nearest done."""
	var combining := _knowing([
		_pending({"makes": "crossblades", "have": 1, "need": 2,
			"ingredients": ["sword"], "missing": ["falcon_blade"]}),
		_pending({"have": 2, "need": 3, "ingredients": ["sword", "stone"]}),
	], {}, {"hero_longsword": "Long Poll", "crossblades": "Cross-Site Blades"})

	assert_eq(combining.progress_label("sword"), "Long Poll 2/3")


func test_a_rack_is_forgotten_but_the_catalogue_is_not():
	"""A new run is a new rack, and the same game."""
	var combining := _knowing([_pending()], {"hero_sword": ["whetstone"]})

	combining.forget_the_rack()

	assert_eq(combining.pending, [] as Array[APITypes.Pending])
	assert_true(combining.knows_the_catalogue())
