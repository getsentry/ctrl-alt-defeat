extends Control

## The zone an item reaches into, drawn over the squares it covers (GDD 4.3).
##
## It stands beside the grid rather than inside it. Every square it draws is a
## grid square, so inside would be the natural place -- but `_setup_visual()`
## frees every child the grid has whenever the board is redrawn, and the board
## is redrawn on every move, purchase and merge. So it holds the grid and asks
## it where a square is.
##
## Each square of the zone carries a marker -- a star or a diamond, so the two
## zones are told apart by shape and not only by colour. An outline means the
## aura covers that square and is doing nothing with it. A filled one means the
## aura is acting on the item standing there. An item is filled once however
## many squares of the zone land on it (GDD 4.4), so counting the filled
## markers counts the items the placement is worth.
##
## Everything is drawn through: the player is choosing where to put a thing,
## and a marker that hid what it was choosing between would be no help.

const Aura = preload("res://scripts/aura.gd")

## Violet for the star, spring green for the diamond. Neither is used anywhere
## else on this screen -- the arcs are cyan, the combining glow is orange, the
## rack is lit yellow-green -- so a zone is never mistaken for one of those.
const STAR := Color(0.85, 0.45, 1.0)
const DIAMOND := Color(0.35, 1.0, 0.62)

## Above the items and the placement mark, below the arcs and any tooltip.
const LAYER := 25

## How much of a square a marker takes, and how solid it is drawn.
##
## The filled one has to read as filled at a glance -- that is the whole
## difference between a square doing something and a square doing nothing --
## and still be seen through, because the item underneath is what the player is
## choosing between. So it is better than half solid and no more.
const MARKER := 0.30
const OUTLINE_ALPHA := 0.50
const FILLED_ALPHA := 0.62
const FILLED_EDGE_ALPHA := 1.0

## How a marker answers when an item is put down or clicked on. Only the ones
## doing something answer: a square doing nothing has nothing to say.
##
## It grows -- quickly, but visibly, so the eye follows it out rather than
## finding it already there -- and then the big one fades off while the
## ordinary marker underneath stays. Nothing ever shrinks: a marker easing back
## down reads as something deflating, where a big one fading off a small one
## reads as the marker having answered.
const SWELL := 2.1
const GROW := 0.13
const FADE := 0.22

## How soon the same answer can be asked for again. A click asks for it, and a
## button held down would otherwise ask on every frame.
const AGAIN_AFTER := 0.25

## The grid whose squares are being drawn on.
var grid: Control = null

var _placed_at := -1.0
var _time := 0.0

# Each entry is {square: Vector2i, doing: bool}, one per square of the zone.
var _star: Array = []
var _diamond: Array = []


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	z_index = LAYER


func _process(delta: float) -> void:
	_time += delta
	if _placed_at >= 0.0:
		if _time - _placed_at >= GROW + FADE:
			_placed_at = -1.0
		queue_redraw()


## Draw these zones. Told nothing, it draws nothing.
func show_zones(star: Array, diamond: Array) -> void:
	_star = star
	_diamond = diamond
	queue_redraw()


func no_zones() -> void:
	show_zones([], [])


func swell() -> void:
	"""Swell what the aura caught: an item has been put down, or clicked on.

	On a click and not on a hover, because this is the answer to a question
	the player asked by pressing something, and an answer that came every time
	the pointer crossed an item would be noise. Asking again inside
	AGAIN_AFTER is ignored, so a held button does not ask on every frame and a
	placement -- which is also a click -- swells once rather than twice.
	"""
	if _placed_at >= 0.0 and _time - _placed_at < AGAIN_AFTER:
		return
	_placed_at = _time
	queue_redraw()


func swelling() -> float:
	"""How big the answering copy of a marker is, right now.

	It grows to SWELL and stays there while it fades, so what leaves the screen
	is a big marker going out rather than a small one arriving.
	"""
	if _placed_at < 0.0:
		return 1.0
	var age := _time - _placed_at
	if age >= GROW:
		return SWELL
	# Fast out, and faster at the start of it: it has to look struck.
	var grown := clampf(age / GROW, 0.0, 1.0)
	return 1.0 + (SWELL - 1.0) * (1.0 - (1.0 - grown) * (1.0 - grown))


func ghosting() -> float:
	"""How solid that copy is. Nothing at all when there is no answer to give."""
	if _placed_at < 0.0:
		return 0.0
	var age := _time - _placed_at
	if age < GROW:
		return 1.0
	return clampf(1.0 - (age - GROW) / FADE, 0.0, 1.0)


## What is being drawn, and what it is worth, for a test to read.
func showing() -> Array:
	return _star + _diamond


func worth() -> int:
	return Aura.worth(_star) + Aura.worth(_diamond)


func _draw() -> void:
	if not is_instance_valid(grid):
		return
	for marked in _star:
		_draw_marker(marked, STAR, true)
	for marked in _diamond:
		_draw_marker(marked, DIAMOND, false)


func _draw_marker(marked: Dictionary, colour: Color, is_star: bool) -> void:
	var middle := _middle_of(marked["square"])
	var reach: float = grid.cell_size * MARKER

	if not marked["doing"]:
		_draw_shape(middle, reach, colour, is_star, false, 1.0)
		return

	# The ordinary marker is always there. The answering copy grows out of it
	# and fades off it, so the square never goes back to being empty-looking
	# even for a frame.
	_draw_shape(middle, reach, colour, is_star, true, 1.0)
	var fading := ghosting()
	if fading > 0.0:
		_draw_shape(middle, reach * swelling(), colour, is_star, true, fading)


func _draw_shape(middle: Vector2, reach: float, colour: Color, is_star: bool,
		filled: bool, solidity: float) -> void:
	var points := Aura.star_points(middle, reach) if is_star \
		else Aura.diamond_points(middle, reach)
	if filled:
		draw_colored_polygon(points, Color(colour, FILLED_ALPHA * solidity))
		_draw_edge(points, Color(colour, FILLED_EDGE_ALPHA * solidity), 2.0)
	else:
		_draw_edge(points, Color(colour, OUTLINE_ALPHA * solidity), 1.5)


func _middle_of(square: Vector2i) -> Vector2:
	"""The middle of a grid square, in this node's own space."""
	var cell: float = grid.cell_size
	var on_the_grid: Vector2 = grid.grid_to_pixel(square) + Vector2(cell, cell) / 2.0
	return get_global_transform().affine_inverse() \
		* (grid.get_global_transform() * on_the_grid)


func _draw_edge(points: PackedVector2Array, colour: Color, width: float) -> void:
	# Closed, because draw_polyline leaves the last side off a shape.
	var closed := points.duplicate()
	closed.append(points[0])
	draw_polyline(closed, colour, width, true)
