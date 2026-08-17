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
	var defaults = {"item_type": "core_dumper", "slug": "core_dumper",
		"name": "Core Dumper"}
	defaults.merge(overrides, true)
	return TestHelpers.item(defaults)


# ============ Shape ============

func test_reads_the_shape_from_the_item():
	_make(_item({"shape": [[0, 0], [1, 0]]}))
	assert_eq(visual.item_shape, [[0, 0], [1, 0]], "Should take the shape from the item")


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


# ============ Artwork ============

func test_uses_the_artwork_matching_the_slug():
	# core_dumper.png is in assets/items
	_make(_item({"slug": "core_dumper"}))
	assert_eq(visual._get_texture_path(), "res://assets/items/core_dumper.png",
		"Should find the artwork named after the slug")


func test_falls_back_when_there_is_no_artwork():
	_make(_item({"slug": "no_such_item_anywhere"}))
	assert_eq(visual._get_texture_path(), "",
		"An item with no artwork should report no path, not a broken one")


func test_draws_something_even_without_artwork():
	_make(_item({"slug": "no_such_item_anywhere"}))
	assert_gt(visual.get_child_count(), 0,
		"An item with no artwork should still draw coloured cells")


func test_draws_one_cell_per_shape_square_without_artwork():
	_make(_item({"slug": "no_such_item_anywhere", "shape": [[0, 0], [1, 0], [0, 1]]}))
	assert_eq(visual.get_child_count(), 3, "Should draw one panel per square of the shape")


# ============ Typed items ============

func test_accepts_a_typed_inventory_item():
	visual = ItemVisual.new()
	add_child(visual)
	var item = TestHelpers.placed_item({"slug": "core_dumper",
		"item_type": "core_dumper", "name": "Core Dumper"})

	visual.setup(item, 45.0, 1.0)

	assert_eq(visual._get_texture_path(), "res://assets/items/core_dumper.png",
		"Should read the slug off a typed item")


# ============ Containers ============

func test_container_is_drawn_in_its_own_colour():
	_make(TestHelpers.container({"slug": "no_such_item_anywhere"}))
	var container_cell = visual.get_child(0)
	var container_style = container_cell.get_theme_stylebox("panel")

	_make(_item({"slug": "no_such_item_anywhere", "is_container": false}))
	var item_cell = visual.get_child(0)
	var item_style = item_cell.get_theme_stylebox("panel")

	assert_ne(container_style.bg_color, item_style.bg_color,
		"A container should not look the same as an item")


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
	visual.tooltip_panel = Panel.new()
	get_tree().root.add_child(visual.tooltip_panel)
	var panel = visual.tooltip_panel

	visual.get_parent().remove_child(visual)
	await get_tree().process_frame

	assert_null(visual.tooltip_panel, "The item should drop its tooltip when it leaves the tree")
	assert_false(is_instance_valid(panel), "The tooltip panel should be freed")
