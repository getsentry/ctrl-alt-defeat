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

## The icon's share of a square, and the dark line drawn round its edge.
const ICON_SHARE := 0.62
const ICON_EDGE := Color(0, 0, 0, 0.55)
const ICON_DIRECTIONS := [
	Vector2(-1, 0), Vector2(1, 0), Vector2(0, -1), Vector2(0, 1)
]

## Icons already loaded, so a grid full of items reads each file once.
static var _icons: Dictionary[String, Texture2D] = {}

var shape: Array = [[0, 0]]  # Array[Array[int]]: the [x, y] offsets it covers
var fill_color := Color(0.2, 0.5, 1.0)
var pattern := ""
var category := ""
var cell_size := 45.0
var cell_spacing := 1.0


func setup(
	item_shape: Array, color: Color, size: float, spacing: float,
	pattern_name: String = "", item_category: String = ""
) -> void:
	shape = item_shape
	fill_color = color
	pattern = pattern_name
	category = item_category
	cell_size = size
	cell_spacing = spacing
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	queue_redraw()


func outline_color() -> Color:
	"""The outline is the fill, darkened. It says "these cells are one item"
	and nothing else, so it must not bring a second colour onto the grid."""
	return fill_color.darkened(OUTLINE_DARKENING)


static func square_of(offset) -> Array:
	"""One offset as a square, whatever form it arrives in.

	Shapes off the server come through APITypes as Vector2i. Shapes written
	out by hand -- tests, and the odd caller -- are still pairs. Anything that
	is neither is not an offset at all, and drawing has to carry on without
	it rather than take the rest of the shape down with it.

	Returns the square in a one-item array, or an empty one for something that
	is not an offset, because there is no Vector2i that means "no square".
	"""
	if offset is Vector2i:
		return [offset]
	if offset is Vector2:
		return [Vector2i(offset)]
	if offset is Array and offset.size() >= 2:
		return [Vector2i(int(offset[0]), int(offset[1]))]
	return []


static func squares_in(item_shape: Array) -> Array[Vector2i]:
	"""The squares a shape covers, in the order the shape gives them."""
	var squares: Array[Vector2i] = []
	for offset in item_shape:
		squares.append_array(square_of(offset))
	return squares


static func squares_of(item_shape: Array) -> Dictionary[Vector2i, bool]:
	"""The covered squares, as a set that can be asked about a neighbour."""
	var squares: Dictionary[Vector2i, bool] = {}
	for square in squares_in(item_shape):
		squares[square] = true
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

	var inner := inner_rects(shape, cell_size, cell_spacing, OUTLINE_WIDTH)
	for rect in inner:
		draw_rect(rect, fill_color)

	# The pattern runs across the whole item rather than restarting in each
	# square: the piece of the tile drawn in each rectangle is taken from where
	# that rectangle sits, so the motif carries on across the seams. It goes
	# inside the outline, which is why it follows the inner rectangles.
	#
	# Not every item has one -- solid is a pattern too -- and the icon is drawn
	# either way, because what it says about the item does not depend on that.
	if not ItemPatterns.draws_nothing(pattern):
		texture_repeat = CanvasItem.TEXTURE_REPEAT_ENABLED
		var texture := ItemPatterns.tile(pattern, cell_size)
		for rect in inner:
			draw_texture_rect_region(texture, rect, Rect2(rect.position, rect.size))

	_draw_icons()


static func icon_for(item_category: String) -> Texture2D:
	"""The silhouette for a category, or nothing if it has no icon yet.

	A category with no icon draws none rather than stopping the grid, because
	the server can name a category this client has never heard of.
	"""
	if item_category == "":
		return null
	if _icons.has(item_category):
		return _icons[item_category]

	var path := "res://assets/icons/categories/%s.svg" % item_category
	if not ResourceLoader.exists(path):
		push_warning("No icon for the %s category, so none is drawn" % item_category)
		_icons[item_category] = null
		return null

	_icons[item_category] = load(path)
	return _icons[item_category]


func icon_rects() -> Array[Rect2]:
	"""Where the icon goes: the middle of every square the item covers.

	On every square rather than once in the middle, because an item with an
	irregular shape has no reliable middle, and a repeated icon still reads
	when a neighbour covers part of the item.
	"""
	var size := cell_size * ICON_SHARE
	var inset := (cell_size - size) / 2.0
	var step := cell_size + cell_spacing
	var rects: Array[Rect2] = []
	for square in squares_of(shape):
		rects.append(Rect2(
			square.x * step + inset, square.y * step + inset, size, size))
	return rects


func _draw_icons() -> void:
	"""Knock the category icon out of the pattern.

	The silhouette is drawn in the dark ink at four offsets of a pixel, which
	shows as an edge, and then in the plain fill colour on top. So the icon
	reads as a clean shape cut out of the pattern rather than as a mark laid
	over it, and both the pattern and the icon keep their full strength.
	"""
	var icon := icon_for(category)
	if icon == null:
		return

	for rect in icon_rects():
		for direction in ICON_DIRECTIONS:
			draw_texture_rect(icon, Rect2(rect.position + direction, rect.size),
				false, ICON_EDGE)
		draw_texture_rect(icon, rect, false, fill_color)
