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
		"block_amount": 0, "special_effect": "", "description": ""
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


func test_shows_special_effect():
	tooltip.setup_tooltip(_item({"special_effect": "Memory leak"}))
	assert_true(tooltip.special_label.visible, "Special effect should be shown")
	assert_true("Memory leak" in tooltip.special_label.text, "Should show the effect")


func test_hides_every_effect_row_for_a_plain_item():
	tooltip.setup_tooltip(_plain_item())
	assert_false(tooltip.damage_label.visible, "No damage row for a plain item")
	assert_false(tooltip.heal_label.visible, "No heal row for a plain item")
	assert_false(tooltip.block_label.visible, "No block row for a plain item")
	assert_false(tooltip.special_label.visible, "No special row for a plain item")


# ============ How much room it takes ============

func test_a_single_square_item_does_not_say_so():
	tooltip.setup_tooltip(_item({"shape": [[0, 0]]}))
	assert_false(tooltip.size_label.visible, "One square is the ordinary case")


func test_a_bigger_item_says_how_many_squares():
	tooltip.setup_tooltip(_item({"shape": [[0, 0], [0, 1]]}))
	assert_true(tooltip.size_label.visible, "Room taken up is worth knowing")
	assert_eq(tooltip.size_label.text, "2 squares")


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

func test_description_shown_when_there_are_no_effects():
	tooltip.setup_tooltip(_plain_item({"description": "Does nothing at all"}))
	assert_true(tooltip.description_label.visible, "Description should fill the gap")
	assert_eq(tooltip.description_label.text, "Does nothing at all", "Should show the description")


func test_description_hidden_when_effects_say_it_better():
	tooltip.setup_tooltip(_item({"description": "Does nothing at all", "min_damage": 2, "max_damage": 5}))
	assert_false(tooltip.description_label.visible,
		"The effect rows replace the description")


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
