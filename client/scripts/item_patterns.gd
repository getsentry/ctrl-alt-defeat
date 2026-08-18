extends RefCounted
class_name ItemPatterns

## The patterns drawn over an item that has no artwork.
##
## The colour of an item says which category it belongs to; the pattern says
## which item it is. There are more items in a category than there are colours,
## so the pattern is what separates them. See docs/item_placeholder_visuals.md.
##
## A pattern is a predicate over a point rather than drawing code: is there ink
## at this place in the tile? That way all of them can be checked without
## rendering anything, and drawing is one routine that asks the predicate.
##
## Every measurement comes from the cell size, so a 45 px grid square and a
## 30 px chest square carry the same pattern at the same relative scale.

const INK := Color(0, 0, 0, 0.30)

## Every pattern there is, in the order a category draws from: most distinct
## first, because a category with four items uses only the first four. The
## server holds the same list and refuses an item wearing anything else.
const NAMES: Array[String] = [
	"solid",
	"stripe_d_bold", "dot_large_grid", "stripe_v_bold", "check_large",
	"stripe_h_bold", "hatch_diag", "dot_small_stagger", "chevron_up",
	"stripe_a_bold", "rings", "stripe_v_fine", "dot_large_stagger",
	"check_small", "stripe_h_fine", "hatch_ortho", "chevron_right",
	"stripe_d_fine", "dot_small_grid", "stripe_a_fine",
	"grid_bold", "grid_fine", "zigzag_h", "zigzag_v", "wave_h", "wave_v",
	"brick_h", "brick_v", "scale", "triangle_up", "triangle_down",
	"diamond_grid", "diamond_stagger", "cross_grid", "plus_grid", "speckle",
]

# How many times a motif repeats across one cell. A bold motif repeats three
# times, a fine one nine, which is what makes the two tell apart at a glance.
const BOLD := 3.0
const FINE := 9.0
const MEDIUM := 4.0


static func period(name: String, cell_size: float) -> int:
	"""How many pixels one repeat of this pattern takes.

	Never smaller than three, or a fine pattern on a small square turns into a
	grey wash with no shape to it.
	"""
	var repeats := BOLD
	if name.ends_with("_fine") or name == "speckle":
		repeats = FINE
	elif name in ["dot_small_grid", "dot_small_stagger", "check_small",
			"hatch_ortho", "hatch_diag", "scale"]:
		repeats = MEDIUM
	return maxi(3, int(round(cell_size / repeats)))


static func is_ink(name: String, x: int, y: int, p: int) -> bool:
	"""Whether there is ink at this point of the tile.

	The point is in tile space, so 0 to p on both sides, and the tile repeats.
	Everything below works in that space alone, which is what lets a pattern be
	checked without drawing it.
	"""
	var half := p / 2.0
	var third := p / 3.0
	var thick := maxi(1, p / 3)
	var thin := maxi(1, p / 5)

	match name:
		"solid":
			return false

		# Stripes. Bold and fine differ by their period, not by their rule.
		"stripe_h_bold", "stripe_h_fine":
			return y < thick
		"stripe_v_bold", "stripe_v_fine":
			return x < thick
		"stripe_d_bold", "stripe_d_fine":
			return (x + y) % p < thick
		"stripe_a_bold", "stripe_a_fine":
			return (x - y + p) % p < thick

		# Cross-hatch is stripes both ways at once.
		"hatch_ortho":
			return x < thin or y < thin
		"hatch_diag":
			return (x + y) % p < thin or (x - y + p) % p < thin

		# Dots, square and staggered. A staggered row is shifted by half.
		"dot_large_grid", "dot_small_grid":
			return _round_dot(x, y, half, half, p * 0.30)
		"dot_large_stagger", "dot_small_stagger":
			# Two dots per tile, set corner to corner, so the rows sit between
			# each other rather than lining up as the square layout does.
			return _round_dot(x, y, p * 0.25, p * 0.25, p * 0.22) \
				or _round_dot(x, y, p * 0.75, p * 0.75, p * 0.22)

		"check_large", "check_small":
			return (x < half) == (y < half)

		"rings":
			var to_middle := Vector2(x - half, y - half).length()
			return int(to_middle) % maxi(2, int(third)) < thin

		"chevron_up":
			return absi(x - int(half)) == y
		"chevron_right":
			return absi(y - int(half)) == x

		# A grid is the lines between the squares, where a check is the squares.
		"grid_bold", "grid_fine":
			return x < thin or y < thin

		"zigzag_h":
			return absi(y - int(half)) == absi(x - int(half))
		"zigzag_v":
			return absi(x - int(half)) == absi(y - int(half)) and x != y

		# A band following a sine, thick enough to read as a line rather than
		# as scattered points where the curve is steep.
		"wave_h":
			return absf(y - (half + half * 0.6 * sin(TAU * x / p))) < thin
		"wave_v":
			return absf(x - (half + half * 0.6 * sin(TAU * y / p))) < thin

		# Brick: a course of blocks, every other row offset by half.
		"brick_h":
			var course := int(y / half)
			var offset := 0 if course % 2 == 0 else int(half)
			return y % maxi(1, int(half)) < thin or (x + offset) % p < thin
		"brick_v":
			var column := int(x / half)
			var down := 0 if column % 2 == 0 else int(half)
			return x % maxi(1, int(half)) < thin or (y + down) % p < thin

		"scale":
			var from_top := Vector2(x - half, y).length()
			var from_bottom := Vector2(x - half, y - p).length()
			return absi(int(from_top - half)) < thin \
				or absi(int(from_bottom - half)) < thin

		"triangle_up":
			return absi(x - int(half)) > y / 2
		"triangle_down":
			return absi(x - int(half)) > (p - y) / 2

		"diamond_grid":
			return absi(x - int(half)) + absi(y - int(half)) < int(third)
		"diamond_stagger":
			var row := int(y / half)
			var shifted := (x + (int(half) if row % 2 else 0)) % p
			return absi(shifted - int(half)) \
				+ absi(y % maxi(1, int(half)) - int(half / 2.0)) < int(third)

		# A cross leans, a plus stands upright. Same idea, told apart by angle.
		"cross_grid":
			var across := absi(x - int(half))
			var down := absi(y - int(half))
			return absi(across - down) < thin and across + down < half
		"plus_grid":
			return (absi(x - int(half)) < thin and absi(y - int(half)) < thick) \
				or (absi(y - int(half)) < thin and absi(x - int(half)) < thick)

		"speckle":
			# Scattered rather than ruled, and fixed, so an item looks the same
			# every time it draws. A plain sum of x and y bands into stripes.
			return absi(hash(Vector2i(x, y))) % 100 < 22

	push_warning("No pattern called %s, so nothing is drawn over the colour" % name)
	return false


static func _round_dot(x: int, y: int, at_x: float, at_y: float, r: float) -> bool:
	return Vector2(x - at_x, y - at_y).length() <= r


## Tiles already built, so a pattern is drawn from pixels rather than from the
## predicate every frame. Keyed by name and size, because the chest draws the
## same pattern smaller than the grid does.
static var _tiles: Dictionary[String, ImageTexture] = {}


static func tile(name: String, cell_size: float) -> ImageTexture:
	"""One repeat of this pattern, as a texture that can be tiled"""
	var p := period(name, cell_size)
	var key := "%s@%d" % [name, p]
	if _tiles.has(key):
		return _tiles[key]

	var image := Image.create(p, p, false, Image.FORMAT_RGBA8)
	image.fill(Color(0, 0, 0, 0))
	for y in p:
		for x in p:
			if is_ink(name, x, y, p):
				image.set_pixel(x, y, INK)

	var texture := ImageTexture.create_from_image(image)
	_tiles[key] = texture
	return texture


static func draws_nothing(name: String) -> bool:
	"""Whether this pattern puts no ink down at all, so drawing it is wasted"""
	return name == "" or name == "solid"
