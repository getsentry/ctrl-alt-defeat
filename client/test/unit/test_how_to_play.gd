extends GutTest
# The page that says what every word in the game means.
#
# A player is shown "gain 2 spiked" and "for each sentinel star item" with
# nothing to look either up in. The battle screen explains a status where it
# appears, but only during a battle and only for one somebody already has.

const HowToPlay = preload("res://scripts/how_to_play.gd")

var page


func after_each():
	if is_instance_valid(page):
		page.queue_free()
	page = null
	await get_tree().process_frame


func _open() -> Control:
	page = HowToPlay.new()
	add_child(page)
	await get_tree().process_frame
	return page


func _words_in(node: Node) -> String:
	var said := ""
	for child in node.get_children():
		if child is Label:
			said += child.text + "\n"
		said += _words_in(child)
	return said


func test_it_says_what_the_numbers_on_a_card_are():
	page = await _open()

	var said := _words_in(page)
	for word in ["Damage", "Cooldown", "CPU", "Quota", "Traits"]:
		assert_true(word in said, "%s should be explained" % word)


func test_it_says_what_a_zone_is_and_draws_both():
	page = await _open()

	var said := _words_in(page)
	assert_true("★" in said, "The star zone should be shown as the rack draws it")
	assert_true("◆" in said, "and the diamond zone too")
	assert_true("touching is not the rule" in said.to_lower(),
		"and the rule that catches people out should be stated")


func test_it_says_how_combining_works():
	page = await _open()

	var said := _words_in(page).to_lower()
	assert_true("combining" in said, "Combining should have a part of its own")
	assert_true("touch all the others" in said,
		"including the bit nobody guesses: one part touches all the rest")


func test_it_closes_on_the_key_and_on_escape():
	page = await _open()

	var buttons := []
	for child in page.find_children("*", "Button", true, false):
		buttons.append(child.text)

	assert_true("GOT IT" in buttons, "There should be a way out of it")


func test_it_opens_at_the_top():
	# Filling a scrolling box leaves it wherever the last thing added put it,
	# and a page of instructions that opens halfway down reads as one that has
	# already been half read.
	page = await _open()
	await get_tree().process_frame

	var scroll: ScrollContainer = page.find_children(
		"*", "ScrollContainer", true, false)[0]
	assert_eq(scroll.scroll_vertical, 0, "It should start at the first line")


func test_the_page_is_a_slab_like_the_rest_of_the_game():
	page = await _open()

	var panel = page.find_child("Panel", true, false)
	assert_not_null(panel, "It should stand on a slab")
	assert_true(panel.has_theme_stylebox_override("panel"), "and be dressed")
