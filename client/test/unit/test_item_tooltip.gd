extends GutTest
# Tests for ItemTooltip, the panel shown when hovering an item.
#
# It is the only place the player reads an item's numbers, so each row has to
# appear when the item has that stat and stay hidden when it does not.

const APITypes = preload("res://scripts/api_types.gd")

var tooltip_scene = preload("res://scenes/ItemTooltip.tscn")
var tooltip


func before_each():
	tooltip = tooltip_scene.instantiate()
	add_child(tooltip)
	await get_tree().process_frame


func after_each():
	if is_instance_valid(tooltip):
		remove_child(tooltip)
		tooltip.queue_free()
	tooltip = null
	await get_tree().process_frame


func _item(overrides: Dictionary = {}) -> Resource:
	# A real item, not a dictionary, because that is what the tooltip is handed.
	return TestHelpers.item(overrides)


func _plain_item(overrides: Dictionary = {}) -> Resource:
	# An item that does nothing, so the effect rows have nothing to show.
	var data = {
		"min_damage": 0, "max_damage": 0, "min_heal": 0, "max_heal": 0,
		"block_amount": 0, "effects": []
	}
	data.merge(overrides, true)
	return _item(data)


# ============ Name and identity ============

func test_shows_the_item_name():
	tooltip.setup_tooltip(_item({"name": "Null Blade"}))
	assert_eq(tooltip.name_label.text, "Null Blade", "Should show the item name")


func test_rarity_colours_the_name():
	tooltip.setup_tooltip(_item({"rarity": "legendary"}))
	var legendary = tooltip.name_label.get_theme_color("font_color")

	tooltip.setup_tooltip(_item({"rarity": "common"}))
	var common = tooltip.name_label.get_theme_color("font_color")

	assert_ne(legendary, common, "Rarity should change the name colour")


# ============ Category and rarity row ============

func test_shows_category_and_rarity():
	tooltip.setup_tooltip(_item({"category": "problem", "rarity": "legendary"}))
	assert_true(tooltip.info_label.visible, "Info row should be shown")
	assert_eq(tooltip.info_label.text, "Problem • Legendary", "Should show category and rarity")


func test_common_rarity_is_not_named():
	tooltip.setup_tooltip(_item({"category": "problem", "rarity": "common"}))
	assert_eq(tooltip.info_label.text, "Problem", "Common is the default, so it is not spelled out")


func test_info_row_hidden_without_category_or_rarity():
	tooltip.setup_tooltip(_item({"category": "", "rarity": ""}))
	assert_false(tooltip.info_label.visible, "Info row should be hidden when there is nothing to say")


# ============ Effects ============

func test_shows_damage_range():
	tooltip.setup_tooltip(_item({"min_damage": 2, "max_damage": 5}))
	assert_true(tooltip.damage_label.visible, "Damage should be shown")
	assert_true("2-5" in tooltip.damage_label.text, "Should show the damage range")


func test_cooldown_and_cpu_get_rows_of_their_own():
	tooltip.setup_tooltip(_item({
		"min_damage": 2, "max_damage": 5, "cooldown": 1.5, "cpu_cost": 3
	}))
	assert_true(tooltip.cooldown_label.visible, "Cooldown should be shown")
	assert_true("1.5" in tooltip.cooldown_label.text, "Should show the cooldown")
	assert_true(tooltip.cpu_label.visible, "CPU cost should be shown")
	assert_eq(tooltip.cpu_label.text, "3", "Should show the CPU cost")


func test_a_cooldown_on_an_item_that_does_nothing_is_not_shown():
	# Nothing paces, so the number is not a stat the player can use.
	tooltip.setup_tooltip(_plain_item({"cooldown": 4.0}))
	assert_false(tooltip.cooldown_label.visible, "A cooldown alone says nothing")


func test_shows_healing():
	tooltip.setup_tooltip(_item({"min_heal": 3, "max_heal": 6}))
	assert_true(tooltip.heal_label.visible, "Healing should be shown")
	assert_true("3-6" in tooltip.heal_label.text, "Should show the heal range")


func test_shows_block():
	tooltip.setup_tooltip(_item({"block_amount": 4}))
	assert_true(tooltip.block_label.visible, "Block should be shown")
	assert_true("4" in tooltip.block_label.text, "Should show how much is blocked")


func test_shows_everything_the_item_does():
	# The rows are the headline numbers. A build is decided on the rest, and
	# an item with three triggers used to show one sentence about one of them.
	tooltip.setup_tooltip(_item({"effects": [
		"Every 1.9s: deal 5-7 damage", "On hit: apply 2 [debuff]memory leak[/debuff]"]}))

	assert_true(tooltip.description_label.visible, "What it does should be shown")
	assert_true("memory leak" in tooltip.description_label.get_parsed_text(),
		"including the parts no row has a number for")
	assert_true("\n" in tooltip.description_label.get_parsed_text(),
		"a line for each, rather than one run-on sentence")


func test_a_status_is_picked_out_in_colour():
	# The server marks which of the ten a name is, because it is the one that
	# knows which are worth having. The colour is the card's to choose.
	tooltip.setup_tooltip(_item({"effects": [
		"On hit: gain 1 [buff]spiked[/buff] and apply 2 [debuff]memory leak[/debuff] to your opponent"]}))

	var text: String = tooltip.description_label.text
	assert_false("[buff]" in text, "The mark itself should never reach the player")
	assert_false("[debuff]" in text, "nor the one for a debuff")
	assert_true(ItemTooltip.BUFF_COLOUR in text, "A buff should be given its colour")
	assert_true(ItemTooltip.DEBUFF_COLOUR in text, "and a debuff its own")
	assert_true("gain 1 spiked" in tooltip.description_label.get_parsed_text(),
		"and the words themselves should read as they were written")


func test_hides_every_effect_row_for_a_plain_item():
	tooltip.setup_tooltip(_plain_item())
	assert_false(tooltip.damage_label.visible, "No damage row for a plain item")
	assert_false(tooltip.heal_label.visible, "No heal row for a plain item")
	assert_false(tooltip.block_label.visible, "No block row for a plain item")


# ============ How much room it takes ============

const LONG_EFFECTS = [
	"When attacked (Melee, 30%):",
	"\u2022 Prevent 7 damage",
	"\u2022 Drain 0.3 CPU from your opponent",
	"\u2022 Gain 1 [buff]spiked[/buff] (up to 5 times)",
]


func _shown(item) -> Control:
	# A card put on screen the way the hover path puts one there, and left for
	# a couple of frames: what the player is looking at a moment after the
	# pointer arrives.
	var card = tooltip_scene.instantiate()
	get_tree().root.add_child(card)
	card.setup_tooltip(item)
	await get_tree().process_frame
	await get_tree().process_frame
	return card


func test_the_card_is_only_as_tall_as_its_text():
	# A wrapping label works out its height from its width, and it only learns
	# its width once a layout pass reaches it. Measured before that, the text
	# counted as one word a line and the card came out several times taller
	# than what it holds, with the empty space hanging below the footer.
	var card = await _shown(_item({"effects": LONG_EFFECTS}))

	assert_almost_eq(card.size.y, card.get_combined_minimum_size().y, 1.0,
		"The card should stand at the height its own text asks for")

	card.queue_free()


func test_the_card_says_when_it_has_taken_its_size():
	# Whatever placed the card is standing it beside an item and level with
	# the middle of it, and cannot do that until it knows how tall the card
	# is. So the card has to say when that changes.
	var card = tooltip_scene.instantiate()
	get_tree().root.add_child(card)
	card.setup_tooltip(_item({"effects": LONG_EFFECTS}))
	watch_signals(card)
	await get_tree().process_frame
	await get_tree().process_frame

	assert_signal_emitted(card, "resized", "The card should say it has resized")

	card.queue_free()


func test_a_card_saying_more_is_taller_than_one_saying_less():
	# The other way the measurement goes wrong is a card that never grows,
	# with its text running off the bottom.
	var few = await _shown(_item({"effects": ["Every 2s: deal 1-2 damage"]}))
	var many = await _shown(_item({"effects": LONG_EFFECTS}))

	assert_gt(many.size.y, few.size.y, "More lines should take more room")
	assert_lt(many.size.y, few.size.y * 3.0,
		"but four lines should not take the room of a dozen")

	few.queue_free()
	many.queue_free()


# ============ Price ============

func test_the_price_is_only_named_on_the_shelf():
	tooltip.setup_tooltip(_item({"price": 4}))
	assert_false(tooltip.price_label.visible, "An item already owned has no price")


func test_a_shop_item_names_its_price():
	tooltip.show_price = true
	tooltip.setup_tooltip(_item({"price": 4}))
	assert_true(tooltip.price_label.visible, "The shelf should say what it charges")
	assert_true("4" in tooltip.price_label.text, "Should show the price")


# ============ Rules ============

func test_an_item_with_nothing_to_say_draws_no_rules():
	# Otherwise the card is a name with two lines under it and nothing between.
	tooltip.setup_tooltip(_plain_item({"cpu_cost": 0, "shape": [[0, 0]]}))
	assert_false(tooltip.top_rule.visible, "Nothing to divide from the name")
	assert_false(tooltip.foot_rule.visible, "Nothing to divide from the footer")


func test_an_item_with_stats_draws_its_rules():
	tooltip.setup_tooltip(_item({"min_damage": 2, "max_damage": 5}))
	assert_true(tooltip.top_rule.visible, "The stats are divided from the name")
	assert_true(tooltip.foot_rule.visible, "and from the footer")


# ============ Description ============

func test_nothing_is_said_about_an_item_that_does_nothing():
	# A container, or an item the catalogue carries without any behaviour yet.
	tooltip.setup_tooltip(_plain_item({"effects": []}))

	assert_false(tooltip.description_label.visible,
		"An empty line is a gap in the card")


func test_the_squares_it_covers_are_not_a_stat():
	# The item is drawn on the grid in the shape it takes up, so a row saying
	# "2 squares" is the card telling the player what they can see.
	tooltip.setup_tooltip(_item({"shape": [[0, 0], [1, 0]]}))

	for row in tooltip.stats.get_children():
		assert_false("Size" in row.name, "There should be no size row left")


# ============ Typed items ============

func test_accepts_a_typed_inventory_item():
	# Battle inventories hand over an APITypes.PlacedItem, not a Dictionary.
	var item = TestHelpers.placed_item({"cost": 4})

	tooltip.setup_tooltip(item)

	assert_eq(tooltip.name_label.text, "Null Blade", "Should read the name off a typed item")
	assert_true(tooltip.damage_label.visible, "Should read the damage off a typed item")
	assert_true("2-5" in tooltip.damage_label.text, "Should show the typed item's damage")


# ============ Setup before the nodes are ready ============

func test_data_given_before_ready_is_applied():
	# _show_tooltip() calls setup_tooltip() right after instantiate(), before the
	# @onready labels exist, so the data has to be held and applied later.
	var early = tooltip_scene.instantiate()
	early.setup_tooltip(_item({"name": "Early Bird"}))

	add_child(early)
	await get_tree().process_frame

	assert_eq(early.name_label.text, "Early Bird", "Data given before ready should still be applied")

	remove_child(early)
	early.queue_free()
