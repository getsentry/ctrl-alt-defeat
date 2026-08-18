extends Control
class_name ItemPlaceholder

## What an item looks like for as long as it has no artwork.
##
## The colour says which category the item belongs to. A pattern and a category
## icon go on top of it later, and neither changes the geometry here. See
## docs/item_placeholder_visuals.md.
##
## The cells of one item are drawn as a single mass with one outline around the
## whole of it, so that a 2x3 item reads as one thing rather than as six
## squares. Everything below works from the list of covered squares alone, so an
## L, a T, or a shape with a hole in it needs no special case.

## How wide the outline is, and how much darker than the fill.
const OUTLINE_WIDTH := 3.0
const OUTLINE_DARKENING := 0.45

var shape: Array = [[0, 0]]  # Array[Array[int]]: the [x, y] offsets it covers
var fill_color := Color(0.2, 0.5, 1.0)
var cell_size := 45.0
var cell_spacing := 1.0


func setup(item_shape: Array, color: Color, size: float, spacing: float) -> void:
	shape = item_shape
	fill_color = color
	cell_size = size
	cell_spacing = spacing
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	queue_redraw()


func outline_color() -> Color:
	"""The outline is the fill, darkened. It says "these cells are one item"
	and nothing else, so it must not bring a second colour onto the grid."""
	return fill_color.darkened(OUTLINE_DARKENING)


static func squares_of(item_shape: Array) -> Dictionary:
	"""The covered squares, as a set that can be asked about a neighbour."""
	var squares := {}
	for offset in item_shape:
		if offset is Array and offset.size() >= 2:
			squares[Vector2i(int(offset[0]), int(offset[1]))] = true
	return squares


static func filled_rects(
	item_shape: Array, size: float, spacing: float
) -> Array[Rect2]:
	"""The area the item covers, as one rectangle per square.

	The grid leaves a gap between its squares. Inside an item that gap is
	filled, or the outline would have holes in it where two cells meet. Only
	the gaps between cells of the same item are closed, so the item still lines
	up with the grid squares underneath it.
	"""
	var squares := squares_of(item_shape)
	var step := size + spacing
	var rects: Array[Rect2] = []
	for square in squares:
		var rect := Rect2(square.x * step, square.y * step, size, size)
		if squares.has(square + Vector2i(1, 0)):
			rect.size.x += spacing
		if squares.has(square + Vector2i(0, 1)):
			rect.size.y += spacing
		rects.append(rect)
	return rects


static func inner_rects(
	item_shape: Array, size: float, spacing: float, width: float
) -> Array[Rect2]:
	"""The same area, pulled in from every side that is on the item's edge.

	A side is on the edge when the square beyond it is not part of the item.
	That is the whole rule, and it is what makes an L or a hole come out right.

	Painting the outline colour over the filled area and these rectangles on
	top of it leaves a band exactly on the edge, and only on the edge. It is
	easier to get right than tracing the edge as lines, because the corners
	take care of themselves.
	"""
	var squares := squares_of(item_shape)
	var step := size + spacing
	var rects: Array[Rect2] = []
	for square in squares:
		var rect := Rect2(square.x * step, square.y * step, size, size)

		# A side with a neighbour beyond it is inside the item, so it keeps its
		# full extent and reaches across the grid's gap.
		if not squares.has(square + Vector2i(-1, 0)):
			rect.position.x += width
			rect.size.x -= width
		if squares.has(square + Vector2i(1, 0)):
			rect.size.x += spacing
		else:
			rect.size.x -= width

		if not squares.has(square + Vector2i(0, -1)):
			rect.position.y += width
			rect.size.y -= width
		if squares.has(square + Vector2i(0, 1)):
			rect.size.y += spacing
		else:
			rect.size.y -= width

		# A cell smaller than two outlines would otherwise turn inside out.
		rect.size.x = maxf(rect.size.x, 0.0)
		rect.size.y = maxf(rect.size.y, 0.0)
		rects.append(rect)
	return rects


func _draw() -> void:
	for rect in filled_rects(shape, cell_size, cell_spacing):
		draw_rect(rect, outline_color())
	for rect in inner_rects(shape, cell_size, cell_spacing, OUTLINE_WIDTH):
		draw_rect(rect, fill_color)
