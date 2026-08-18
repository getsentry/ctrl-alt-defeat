extends GutTest
# Tests for ItemPlaceholder, which draws an item that has no artwork yet.
#
# The geometry is what matters here and it is worked out without drawing, so
# these tests ask for the rectangles rather than looking at pixels.
#
# The rule under all of it: a side is on the item's edge when the square beyond
# it is not part of the item. Everything else follows, which is why an L and a
# shape with a hole need no code of their own.

const ItemPlaceholder = preload("res://scripts/item_placeholder.gd")

const CELL := 45.0
const GAP := 1.0
const WIDTH := 3.0

# One cell, its right-hand neighbour, the cell below it, and the cell below
# that neighbour missing: an L, with one concave corner.
const L_SHAPE := [[0, 0], [1, 0], [0, 1]]

# A ring of eight around a missing middle.
const RING := [[0, 0], [1, 0], [2, 0], [0, 1], [2, 1], [0, 2], [1, 2], [2, 2]]


func _filled(shape: Array) -> Array[Rect2]:
	return ItemPlaceholder.filled_rects(shape, CELL, GAP)


func _inner(shape: Array) -> Array[Rect2]:
	return ItemPlaceholder.inner_rects(shape, CELL, GAP, WIDTH)


func _rect_in(rects: Array[Rect2], square: Vector2i) -> Rect2:
	"""The rectangle drawn for one square.

	Found by which cell it starts in rather than by where it starts, because an
	outlined side moves the corner inwards.
	"""
	var step := CELL + GAP
	var cell := Rect2(square.x * step, square.y * step, CELL, CELL)
	for rect in rects:
		if cell.has_point(rect.position + Vector2(0.5, 0.5)):
			return rect
	fail_test("No rectangle is drawn in square %s" % square)
	return Rect2()


# ============ The covered squares ============

func test_reads_every_square_of_the_shape():
	var squares = ItemPlaceholder.squares_of(L_SHAPE)
	assert_eq(squares.size(), 3, "An L covers three squares")
	assert_true(squares.has(Vector2i(0, 1)), "Should hold the square below the anchor")


func test_ignores_an_offset_that_is_not_a_pair():
	var squares = ItemPlaceholder.squares_of([[0, 0], "nonsense", [7]])
	assert_eq(squares.size(), 1, "Only the one real offset should count")


# ============ The area the item covers ============

func test_one_rectangle_per_square():
	assert_eq(_filled(L_SHAPE).size(), 3, "An L should be three rectangles")


func test_a_single_cell_fills_its_square_exactly():
	var rects = _filled([[0, 0]])
	assert_eq(rects[0], Rect2(0, 0, CELL, CELL),
		"A one-cell item should cover its square and no more")


func test_a_cell_reaches_across_the_gap_to_its_neighbour():
	# Without this the outline would have a hole in it where two cells meet.
	var left = _rect_in(_filled([[0, 0], [1, 0]]), Vector2i(0, 0))
	assert_eq(left.size.x, CELL + GAP, "The left cell should close the gap on its right")
	assert_eq(left.size.y, CELL, "It has no neighbour below, so its height is unchanged")


func test_the_two_cells_of_a_wide_item_meet_with_nothing_between_them():
	var rects = _filled([[0, 0], [1, 0]])
	var left = _rect_in(rects, Vector2i(0, 0))
	var right = _rect_in(rects, Vector2i(1, 0))
	assert_eq(left.end.x, right.position.x, "The two cells should touch")


func test_the_item_still_lines_up_with_the_grid_underneath_it():
	# Only the gaps inside the item are closed. The gap the grid leaves around
	# the outside is left alone, or the item would sit off its squares.
	var rects = _filled([[0, 0], [1, 0]])
	var right = _rect_in(rects, Vector2i(1, 0))
	assert_eq(right.end.x, 2 * CELL + GAP,
		"A two-wide item should end where the second grid square ends")


# ============ The outline ============

func test_a_single_cell_is_pulled_in_on_all_four_sides():
	var rects = _inner([[0, 0]])
	assert_eq(rects[0], Rect2(WIDTH, WIDTH, CELL - 2 * WIDTH, CELL - 2 * WIDTH),
		"A lone cell is edge on every side, so it takes an outline all round")


func test_a_side_with_a_neighbour_takes_no_outline():
	# This is what makes it one outline around the item instead of a box
	# around each cell.
	var left = _rect_in(_inner([[0, 0], [1, 0]]), Vector2i(0, 0))
	assert_eq(left.position.x, WIDTH, "Its left side is on the edge")
	assert_eq(left.end.x, CELL + GAP,
		"Its right side has a neighbour, so it keeps its full extent")


func test_the_inside_of_a_wide_item_has_no_seam():
	var rects = _inner([[0, 0], [1, 0]])
	var left = _rect_in(rects, Vector2i(0, 0))
	var right = _rect_in(rects, Vector2i(1, 0))
	assert_eq(left.end.x, right.position.x,
		"The fill should run straight through where the two cells meet")


func test_a_concave_corner_is_outlined():
	# The cell to the right of the anchor of an L has nothing below it, so its
	# bottom is on the edge even though the anchor's bottom is not.
	var rects = _inner(L_SHAPE)
	var corner = _rect_in(rects, Vector2i(1, 0))
	assert_eq(corner.end.y, CELL - WIDTH, "The overhanging cell is outlined below")
	var anchor = _rect_in(rects, Vector2i(0, 0))
	assert_eq(anchor.end.y, CELL + GAP, "The anchor has a neighbour below, so it is not")


func test_a_hole_in_the_middle_is_outlined_too():
	# The square above the hole has the hole below it, so that side is an edge
	# just as much as the outside of the item is.
	var above_hole = _rect_in(_inner(RING), Vector2i(1, 0))
	assert_eq(above_hole.end.y, CELL - WIDTH,
		"A cell facing the hole should be outlined on that side")


func test_every_rectangle_stays_the_right_way_out():
	# An outline wider than the cell would otherwise give a negative size, and
	# draw_rect would fill the whole item.
	for rect in ItemPlaceholder.inner_rects([[0, 0]], 4.0, GAP, WIDTH):
		assert_gte(rect.size.x, 0.0, "Width should never go below zero")
		assert_gte(rect.size.y, 0.0, "Height should never go below zero")


# ============ Colour ============

func test_the_outline_is_the_fill_darkened():
	var placeholder = ItemPlaceholder.new()
	autofree(placeholder)
	placeholder.setup([[0, 0]], Color("#BE0032"), CELL, GAP)

	var outline = placeholder.outline_color()
	assert_lt(outline.v, placeholder.fill_color.v, "The outline should be darker")
	assert_almost_eq(outline.h, placeholder.fill_color.h, 0.01,
		"It should be the same colour, not a second one")
