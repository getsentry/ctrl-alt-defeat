extends GutTest
# Tests for ItemVisual, the control that draws one item or container.
#
# It is used by the shop, both inventory grids and both battle inventories, so a
# regression here is visible everywhere at once.

const ItemVisual = preload("res://scripts/item_visual.gd")
const APITypes = preload("res://scripts/api_types.gd")

var visual


func after_each():
	if is_instance_valid(visual):
		if visual.get_parent():
			visual.get_parent().remove_child(visual)
		visual.queue_free()
	visual = null
	await get_tree().process_frame


func _make(data, size: float = 45.0, spacing: float = 1.0) -> Control:
	visual = ItemVisual.new()
	add_child(visual)
	visual.setup(data, size, spacing)
	return visual


func _item(overrides: Dictionary = {}) -> Resource:
	return TestHelpers.item(overrides)


# ============ Shape ============

func test_reads_the_shape_from_the_item():
	# A shape is written out as pairs and arrives as squares: APITypes turns
	# what the server sends into Vector2i on the way in.
	_make(_item({"shape": [[0, 0], [1, 0]]}))
	assert_eq(visual.item_shape, [Vector2i(0, 0), Vector2i(1, 0)],
		"Should take the shape from the item")


func test_size_follows_a_single_cell_shape():
	_make(_item({"shape": [[0, 0]]}), 45.0, 1.0)
	assert_eq(visual.size, Vector2(45, 45), "A one-cell item should be one cell wide and tall")


func test_size_follows_a_wide_shape():
	_make(_item({"shape": [[0, 0], [1, 0]]}), 45.0, 1.0)
	# two cells plus the spacing between them
	assert_eq(visual.size, Vector2(91, 45), "A two-wide item should span two cells and the gap")


func test_size_follows_a_tall_shape():
	_make(_item({"shape": [[0, 0], [0, 1]]}), 45.0, 1.0)
	assert_eq(visual.size, Vector2(45, 91), "A two-tall item should span two cells and the gap")


func test_size_follows_a_square_shape():
	_make(_item({"shape": [[0, 0], [1, 0], [0, 1], [1, 1]]}), 45.0, 1.0)
	assert_eq(visual.size, Vector2(91, 91), "A 2x2 item should be square")


func test_cell_size_is_honoured():
	_make(_item({"shape": [[0, 0]]}), 60.0, 2.0)
	assert_eq(visual.size, Vector2(60, 60), "Should draw at the size it was given")


# ============ Charging back up ============
#
# A cooldown is a battle second like the rest of the battle, and the battle is
# a replay the player can run at 2x or 3x. One filling at wall speed while the
# battle runs at 3x is still filling after the item has fired twice more.

func test_a_charge_fills_at_the_pace_it_is_given():
	var visual := _make(_item({"slug": "null_blade"}), 45.0, 1.0)
	visual.set_charge_pace(3.0)
	visual.fire(3.0)

	# One second of real time at three battle seconds a second finishes it.
	visual._cooldown._process(1.01)

	assert_false(visual.is_cooling(), "Three seconds of battle have gone by")


func test_a_charge_at_ordinary_speed_takes_its_own_time():
	var visual := _make(_item({"slug": "null_blade"}), 45.0, 1.0)
	visual.set_charge_pace(1.0)
	visual.fire(3.0)

	visual._cooldown._process(1.01)

	assert_true(visual.is_cooling(), "and is still filling a second in")


func test_a_charge_already_running_follows_a_change_of_speed():
	"""The speed control is pressed in the middle of a battle as often as
	before it."""
	var visual := _make(_item({"slug": "null_blade"}), 45.0, 1.0)
	visual.fire(3.0)

	visual.set_charge_pace(3.0)
	visual._cooldown._process(1.01)

	assert_false(visual.is_cooling(), "The one already filling sped up too")


# ============ Where a click lands ============
#
# A Control answers for its whole rectangle, and an item's rectangle is the box
# around its shape. So the empty corner of an L picked the item up -- and those
# are the squares an aura is drawn in, so a player aiming at what an aura
# reached was picking up the item projecting it.
#
# The rectangle still takes the press. What is done about it is the grid's, in
# test_inventory_grid.gd: refusing the press outright hands it to the container
# underneath, which then comes up instead of the item.

func _an_L() -> Control:
	# Covers three squares of a two-by-two box: the fourth is empty.
	return _make(_item({"shape": [[0, 0], [1, 0], [0, 1]]}), 45.0, 1.0)


func test_a_click_on_a_square_the_item_covers_is_on_the_item():
	var visual := _an_L()

	for offset in [Vector2(0, 0), Vector2(1, 0), Vector2(0, 1)]:
		var middle: Vector2 = offset * 46.0 + Vector2(22, 22)
		assert_true(visual.covers_point(middle),
			"the square at %s is the item's own" % offset)


func test_a_click_on_the_empty_corner_is_not_on_the_item():
	var visual := _an_L()

	assert_false(visual.covers_point(Vector2(46, 46) + Vector2(22, 22)),
		"The fourth square of the box is not covered, so it is not the item")



func test_the_hairline_between_two_of_its_squares_is_still_the_item():
	"""The gap ruled between two squares is inside the item's own drawing. A
	point in it that answered "not the item" would be a one pixel line through
	the middle of an item where clicking does nothing."""
	var visual := _an_L()

	# Dead on the ruled line between the item's two top squares.
	assert_true(visual.covers_point(Vector2(45.5, 22)))


func test_a_click_outside_the_box_is_not_on_the_item():
	var visual := _an_L()

	assert_false(visual.covers_point(Vector2(-5, 10)), "left of it")
	assert_false(visual.covers_point(Vector2(10, 400)), "below it")


func test_a_rectangle_answers_for_all_of_itself():
	# The common case, and the one that must not change.
	var visual := _make(_item({"shape": [[0, 0], [1, 0], [0, 1], [1, 1]]}), 45.0, 1.0)

	for offset in [Vector2(0, 0), Vector2(1, 0), Vector2(0, 1), Vector2(1, 1)]:
		assert_true(visual.covers_point(offset * 46.0 + Vector2(22, 22)),
			"every square of a 2x2 is the item")


# ============ Artwork ============

func test_uses_the_artwork_matching_the_slug():
	# null_blade.png is in assets/items
	_make(_item({"slug": "null_blade"}))
	assert_eq(visual._get_texture_path(), "res://assets/items/null_blade.png",
		"Should find the artwork named after the slug")


func test_the_squares_turn_the_way_the_artwork_does():
	"""The two halves of a turn, tied together.

	An item's picture is turned by handing `facing` straight to Godot as
	degrees, and the squares it covers are turned by APITypes. Nothing makes
	the two agree except that they are the same turn, so this asks Godot
	itself which way a point goes and holds the squares to that answer. Turned
	opposite ways, a spear was drawn pointing right with its reach behind it.
	"""
	for facing in [90, 180, 270]:
		# Where the artwork sends a point one square to its right.
		var drawn := Vector2(1, 0).rotated(deg_to_rad(facing))
		var square := APITypes._spin([Vector2i(1, 0)] as Array[Vector2i], facing)[0]

		assert_eq(Vector2i(roundi(drawn.x), roundi(drawn.y)), square,
			"the squares and the picture disagree at %d degrees" % facing)
	# And that `facing` really is what the picture is turned by: see
	# test_the_artwork_turns_with_the_item below.


func test_falls_back_when_there_is_no_artwork():
	_make(_item({"slug": "no_such_item_anywhere"}))
	assert_eq(visual._get_texture_path(), "",
		"An item with no artwork should report no path, not a broken one")


func test_draws_something_even_without_artwork():
	_make(_item({"slug": "no_such_item_anywhere"}))
	assert_gt(visual.get_child_count(), 0,
		"An item with no artwork should still draw coloured cells")


func test_hands_the_whole_shape_to_one_placeholder():
	# One drawing for the whole item, not one per cell. That is what lets the
	# outline go around the outside of the shape instead of around each square.
	var shape = [[0, 0], [1, 0], [0, 1]]
	_make(_item({"slug": "no_such_item_anywhere", "shape": shape}))

	assert_eq(visual.get_child_count(), 1, "One placeholder should draw the whole item")
	assert_eq(visual.get_child(0).shape,
		[Vector2i(0, 0), Vector2i(1, 0), Vector2i(0, 1)],
		"It should be given every square")


func test_the_placeholder_covers_the_whole_item():
	_make(_item({"slug": "no_such_item_anywhere", "shape": [[0, 0], [1, 0]]}), 45.0, 1.0)
	assert_eq(visual.get_child(0).size, visual.size,
		"The placeholder should be as big as the item it draws")


func test_uses_the_colour_the_server_sent():
	_make(_item({"slug": "no_such_item_anywhere", "color": "#8DB600"}))
	assert_eq(visual.get_child(0).fill_color, Color("#8DB600"),
		"Should draw the item in the colour it arrived with")


# ============ Typed items ============

func test_accepts_a_typed_inventory_item():
	visual = ItemVisual.new()
	add_child(visual)
	var item = TestHelpers.placed_item({"slug": "null_blade",
		"item_type": "null_blade", "name": "Null blade"})

	visual.setup(item, 45.0, 1.0)

	assert_eq(visual._get_texture_path(), "res://assets/items/null_blade.png",
		"Should read the slug off a typed item")


# ============ Containers ============

func test_container_is_drawn_in_its_own_colour():
	# A container is the ground the items sit on. If it took a palette colour
	# the grid would be too busy to read.
	_make(TestHelpers.container({"slug": "no_such_item_anywhere"}))
	var container_fill = visual.get_child(0).fill_color

	_make(_item({"slug": "no_such_item_anywhere", "is_container": false}))
	var item_fill = visual.get_child(0).fill_color

	assert_ne(container_fill, item_fill,
		"A container should not look the same as an item")
	assert_lt(container_fill.a, 1.0, "A container should stay see-through")


func test_a_container_in_the_shop_is_drawn_as_a_container():
	# In the shop a container is an ordinary Item with the flag set, because
	# that is what the player buys. It carries no colour of its own, so it has
	# to be drawn as a container wherever it is.
	#
	# A slug with no artwork, because the colour is what is being asked about
	# and artwork is drawn instead of it. This named standard_vm, which has a
	# picture, so it read fill_color off a TextureRect: an error every run, and
	# a test that asserted nothing at all.
	_make(_item({"slug": "no_such_item_anywhere", "is_container": true,
		"color": "", "pattern": ""}))
	assert_lt(visual.get_child(0).fill_color.a, 1.0,
		"A container for sale is still a container")


# ============ Tooltip ============

func test_tooltip_is_off_by_default():
	_make(_item())
	assert_false(visual.enable_tooltip, "Tooltips should be opt-in")
	assert_null(visual.tooltip_panel, "No tooltip should exist before hovering")


func test_hide_tooltip_is_safe_when_nothing_is_showing():
	_make(_item())
	visual._hide_tooltip()
	assert_null(visual.tooltip_panel, "Hiding a tooltip that is not showing should do nothing")


func test_leaving_the_tree_takes_the_tooltip_with_it():
	# The tooltip is parented to the tree root, not to the item, so it has to be
	# taken down explicitly or it outlives the thing it describes.
	_make(_item())
	visual.tooltip_panel = load("res://scenes/ItemTooltip.tscn").instantiate()
	get_tree().root.add_child(visual.tooltip_panel)
	var panel = visual.tooltip_panel

	visual.get_parent().remove_child(visual)
	await get_tree().process_frame

	assert_null(visual.tooltip_panel, "The item should drop its tooltip when it leaves the tree")
	assert_false(is_instance_valid(panel), "The tooltip panel should be freed")


func _hovered(at: Vector2, data = null) -> Control:
	# An item on screen with the pointer on it, and the card it puts up.
	var item = ItemVisual.new()
	item.enable_tooltip = true
	add_child(item)
	item.setup(data if data else _item(), 45.0, 1.0)
	item.position = at
	await item._show_tooltip()
	await get_tree().process_frame
	return item


func test_every_card_stands_in_the_same_place():
	# A card beside the item covers the next thing the player wants to look at
	# -- the shelf they are comparing against, the square they are about to
	# drop into -- and has to be found again each time before it can be read.
	var near = await _hovered(Vector2(40, 60))
	var here = near.tooltip_panel.position
	near._hide_tooltip()

	var far = await _hovered(Vector2(1400, 900))
	var there = far.tooltip_panel.position

	assert_eq(here, there, "The card should stand where the last one stood")

	far._hide_tooltip()
	near.queue_free()
	far.queue_free()


func test_the_card_fills_the_column_it_stands_in():
	# The empty column of the shop screen: between the rack and the shelves,
	# and below the START BATTLE key.
	var item = await _hovered(Vector2(40, 60))
	var card = item.tooltip_panel

	assert_eq(card.position, ItemVisual.TOOLTIP_SPOT,
		"The card should stand where every card stands")
	assert_eq(card.size.x, ItemVisual.TOOLTIP_WIDTH,
		"and be as wide as the column it fills")

	item._hide_tooltip()
	item.queue_free()


func test_a_tall_card_comes_up_to_meet_the_bottom_edge():
	# Rather than running off the bottom of the screen, which is where the
	# lines nobody has read yet would be. The card is given its height here
	# rather than filled with text, so the test says what it means whatever
	# the font measures.
	var item = await _hovered(Vector2(40, 60))
	var room = item.get_viewport_rect().size
	item.tooltip_panel.size.y = room.y - ItemVisual.TOOLTIP_SPOT.y
	item._place_tooltip()

	assert_almost_eq(item.tooltip_panel.position.y + item.tooltip_panel.size.y,
		room.y - ItemVisual.TOOLTIP_EDGE, 1.0,
		"Its last line should sit just inside the bottom edge")

	item._hide_tooltip()
	item.queue_free()


func test_a_card_taller_than_the_screen_starts_at_the_top():
	# There is nowhere for all of it to go, so what it can show is the top.
	var item = await _hovered(Vector2(40, 60))
	var room = item.get_viewport_rect().size
	item.tooltip_panel.size.y = room.y * 2
	item._place_tooltip()

	assert_eq(item.tooltip_panel.position.y, ItemVisual.TOOLTIP_EDGE,
		"The card should start at the top edge")

	item._hide_tooltip()
	item.queue_free()


func test_drawing_an_item_again_does_not_connect_its_tooltip_twice():
	# An item is drawn again whenever it changes, and turning one is a redraw.
	# Connecting on each of those raises an error every time.
	visual = ItemVisual.new()
	visual.enable_tooltip = true
	add_child(visual)

	visual.setup(_item(), 45.0, 1.0)
	visual.setup(_item(), 45.0, 1.0)

	assert_eq(visual.mouse_entered.get_connections().size(), 1,
		"Drawn twice, connected once")
	assert_eq(visual.mouse_exited.get_connections().size(), 1,
		"and the same going out")


# ============ Turning ============
#
# The squares an item covers are turned without the picture of it, and for as
# long as items were drawn as coloured shapes that was the whole of turning.
# With artwork it was not: a sword on its side was fitted to the squares it
# now covered and left standing upright, so it was drawn upright and shrunk
# until its own length fitted across their width. It did not turn, it dwindled.

func _artwork_of(visual_node: Control) -> TextureRect:
	for child in visual_node.get_children():
		if child is TextureRect:
			return child
	return null


func _sword(facing: int) -> Resource:
	return TestHelpers.placed_item({
		"slug": "darksaber", "shape": [[0, 0], [0, 1], [0, 2], [0, 3]],
		"rotation": facing})


func test_the_artwork_turns_with_the_item():
	_make(_sword(90))
	var art := _artwork_of(visual)
	assert_not_null(art, "A slug with artwork should be drawn as artwork")
	assert_eq(art.rotation_degrees, 90.0,
		"An item on its side should have its picture on its side")


func test_the_artwork_stays_upright_when_the_item_does():
	_make(_sword(0))
	assert_eq(_artwork_of(visual).rotation_degrees, 0.0,
		"An item facing its own way should not have its picture turned")


func test_turning_does_not_shrink_the_artwork():
	# The bug this is here for: turned, the sword was drawn at a quarter of
	# the size it stands at, because it was fitted upright into its own width.
	_make(_sword(0))
	var standing: Vector2 = _artwork_of(visual).scale
	_make(_sword(90))
	var lying: Vector2 = _artwork_of(visual).scale
	assert_almost_eq(lying.x, standing.x, 0.001,
		"An item should be drawn the same size whichever way it faces")


func test_turned_artwork_still_fits_the_squares_it_covers():
	_make(_sword(90))
	var art := _artwork_of(visual)
	# Turned a quarter, what the picture covers is its own size the other way.
	var covers := Vector2(art.size.y * art.scale.y, art.size.x * art.scale.x)
	assert_lte(covers.x, visual.size.x + 1.0, "It should not run past its squares")
	assert_lte(covers.y, visual.size.y + 1.0, "nor past them downwards")


# ============ What a visual holds ============

func _a_visual(data) -> ItemVisual:
	var visual := ItemVisual.new()
	add_child_autofree(visual)
	visual.setup(data, 45.0, 1.0)
	return visual


func test_a_visual_that_is_handed_a_different_item_draws_the_different_item():
	"""now_holds() skips the redraw when the picture would be the same. Judged
	on the facing alone, an item replaced by another facing the same way -- two
	items combining into a third -- kept the picture of the one that is gone."""
	var visual := _a_visual(TestHelpers.placed_item({"id": "before", "slug": "api_token"}))
	var was: Array = visual.get_children().map(func(n): return n.get_instance_id())

	visual.now_holds(TestHelpers.placed_item({"id": "after", "slug": "null_blade"}))

	assert_eq(visual.item_data.id, "after", "It holds the new item")
	assert_ne(visual.get_children().map(func(n): return n.get_instance_id()), was,
		"and it is drawn again, because it is not the same picture")


func test_a_visual_that_only_moves_is_not_drawn_again():
	var visual := _a_visual(TestHelpers.placed_item({"id": "same", "position": [0, 0]}))
	var was: Array = visual.get_children().map(func(n): return n.get_instance_id())

	visual.now_holds(visual.item_data.placed_at(Vector2i(4, 3)))

	assert_eq(visual.where(), Vector2i(4, 3), "It knows where it moved to")
	assert_eq(visual.get_children().map(func(n): return n.get_instance_id()), was,
		"and nothing was drawn again for it")


func test_a_visual_that_turns_is_drawn_again():
	var visual := _a_visual(TestHelpers.placed_item(
		{"id": "same", "shape": [[0, 0], [1, 0]]}))
	var was: Array = visual.get_children().map(func(n): return n.get_instance_id())

	visual.now_holds(visual.item_data.turned(1))

	assert_ne(visual.get_children().map(func(n): return n.get_instance_id()), was)
	assert_eq(visual.item_shape, visual.item_data.turned_shape(),
		"and it covers the squares it faces now")
