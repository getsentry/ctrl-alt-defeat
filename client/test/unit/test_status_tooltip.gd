extends GutTest
# The card that says what a buff or a debuff on a fighter is doing.
#
# What is checked here is the two things that were wrong when it was first
# written, and neither was anything to do with the words on it: how big it came
# out, and where it stood. The words are covered in test_battle_hud.gd, where
# the chips that put it up are.

const CARD = preload("res://scenes/StatusTooltip.tscn")

var card: Control


func before_each():
	card = CARD.instantiate()
	add_child_autofree(card)


func _a_rule(overrides: Dictionary = {}) -> Dictionary:
	var rule := {
		"shown": "regenerating", "kind": "buff", "each": 1,
		"one": "Heals 1 health every 2s",
		"many": "Heals {total} health every 2s",
		"detail": "",
	}
	rule.merge(overrides, true)
	return rule


func _settled(rule: Dictionary, stacks: int) -> Control:
	card.say(rule, stacks)
	# The size settles over a layout pass or two. _process asks every frame.
	for pass_ in range(4):
		await get_tree().process_frame
	return card


# ============ How big it comes out ============

func test_the_card_is_only_as_tall_as_its_text():
	"""A wrapping label works out its height from its width, and only learns
	its width once a layout pass reaches it. Measured before that, every word
	counted as a line: this card came out 300 wide and 4186 tall, hanging off
	the top of the screen with nothing readable on it."""
	await _settled(_a_rule(), 6)

	assert_almost_eq(card.size.y, card.get_combined_minimum_size().y, 1.0,
		"The card should stand at the height its own text asks for")


func test_the_card_is_a_card_rather_than_a_column():
	"""The number that matters, said plainly: whatever the text, it fits on
	the screen it is drawn on."""
	await _settled(_a_rule({
		"detail": "Speed-ups and slow-downs add. 1000% either way at most.",
	}), 6)

	assert_lt(card.size.y, 400.0,
		"A card taller than this is not a card, it is a wall")


func test_a_card_with_less_to_say_is_smaller():
	await _settled(_a_rule({"detail": "Only when their blow lands."}), 6)
	var with_detail := card.size.y

	await _settled(_a_rule(), 1)

	assert_lt(card.size.y, with_detail,
		"No detail and no total is a shorter card")


# ============ Where it stands ============

func _chip_at(where: Vector2) -> Control:
	var chip := Label.new()
	chip.text = "regenerating x6"
	chip.position = where
	chip.size = Vector2(140, 24)
	add_child_autofree(chip)
	return chip


func test_the_card_stands_beside_the_chip_rather_than_over_it():
	"""Above it, the card covered exactly the health and CPU figures a player
	is reading it against."""
	var chip := _chip_at(Vector2(600, 800))
	await _settled(_a_rule(), 6)

	card.stand_beside(chip)

	assert_false(card.get_global_rect().intersects(chip.get_global_rect()),
		"The card should not be drawn over the chip it is about")


func test_a_card_beside_a_chip_on_the_left_edge_stays_on_the_screen():
	var chip := _chip_at(Vector2(4, 800))
	await _settled(_a_rule(), 6)

	card.stand_beside(chip)

	assert_true(card.get_viewport_rect().encloses(card.get_global_rect()),
		"There is no room to its left, so it goes to its right")


func test_a_card_beside_a_chip_at_the_bottom_stays_on_the_screen():
	var room: Vector2 = card.get_viewport_rect().size
	var chip := _chip_at(Vector2(600, room.y - 30))
	await _settled(_a_rule(), 6)

	card.stand_beside(chip)

	assert_true(card.get_viewport_rect().encloses(card.get_global_rect()),
		"It should come up to meet the bottom edge rather than run off it")


func test_a_card_beside_a_chip_at_the_top_stays_on_the_screen():
	var chip := _chip_at(Vector2(600, 2))
	await _settled(_a_rule(), 6)

	card.stand_beside(chip)

	assert_true(card.get_viewport_rect().encloses(card.get_global_rect()))


func test_a_card_is_placed_again_when_its_size_settles():
	"""Where it stands depends on how tall it came out, and how tall it came
	out is not known for a pass or two."""
	var chip := _chip_at(Vector2(600, 800))
	card.say(_a_rule(), 6)
	card.stand_beside(chip)
	var before := card.position

	for pass_ in range(4):
		await get_tree().process_frame
	card.stand_beside(chip)

	assert_ne(before, card.position, "It moved once it knew its own size")
	assert_true(card.get_viewport_rect().encloses(card.get_global_rect()))
