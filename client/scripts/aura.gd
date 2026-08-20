extends RefCounted

## Which squares an item's aura covers, and which of them are doing anything
## (GDD 4.3, 4.4).
##
## An aura is a set of squares an item projects around itself. It reaches an
## item when any square of the zone lands on any square that item covers --
## touching is not required and distance is not a rule, the map says exactly
## which squares. It never reaches the item projecting it.
##
## What makes this worth drawing is the second half: a zone can be narrowed to
## a tag, so "Star Pets trigger faster" lands on a weapon and does nothing. The
## server sends what each zone wants and what tags each item carries, and the
## matching is done here, because this is asked on every frame of a drag.
##
## The rule that makes the display a measure rather than a decoration: **an
## aura reaches an item once, however many of its squares land on it.** So one
## square per item is marked as doing something, and a player counting the
## marked squares is counting the items their aura is worth.

const APITypes = preload("res://scripts/api_types.gd")


## What an item can be narrowed by: the kinds it carries and the category it
## belongs to, so "Star Pets" and "Star nature-items" both match from here.
static func tags_of(item: APITypes.Item) -> Array[String]:
	var tags: Array[String] = []
	for kind in item.kinds:
		tags.append(kind.to_lower())
	tags.append(item.category.to_lower())
	return tags


## Whether an aura on this zone acts on this item.
##
## `wants` is what the server said the zone acts on: one entry per clause, each
## naming the tags it wants. An item matches a clause by carrying one of
## `any_of`, or all of `all_of`; a clause wanting nothing wants everything. No
## clauses at all means nothing acts through the zone, which is true of 68 of
## the 117 items that draw one, and they must not light up.
static func acts_on(wants: Array, item: APITypes.Item) -> bool:
	var tags := tags_of(item)
	for clause in wants:
		var any_of: Array = clause.get("any_of", [])
		var all_of: Array = clause.get("all_of", [])
		if any_of.is_empty() and all_of.is_empty():
			return true
		for tag in any_of:
			if tags.has(tag):
				return true
		if not all_of.is_empty():
			var carries_all := true
			for tag in all_of:
				carries_all = carries_all and tags.has(tag)
			if carries_all:
				return true
	return false


## Every square of the zone, and whether it is the one square counted for an
## item the aura acts on.
##
## `standing` answers what covers a square, as a Callable taking a Vector2i and
## returning an APITypes.Item or null. Squares are walked in reading order, so
## the square marked for an item is always its top-left-most, and the same rack
## always draws the same way.
static func markers(
	zone: Array[Vector2i], standing: Callable, wants: Array
) -> Array:
	var counted := {}
	var marked := []
	var squares := zone.duplicate()
	squares.sort_custom(func(a, b): return [a.y, a.x] < [b.y, b.x])

	for square in squares:
		var item = standing.call(square)
		var lighting := ""
		if item != null and not counted.has(item.id) and acts_on(wants, item):
			counted[item.id] = true
			lighting = item.id
		marked.append({
			"square": square, "doing": lighting != "", "item": lighting})
	return marked


## The items an aura is acting on, by id. What to light up as well as mark:
## the marker says which square, and the item itself says which item.
static func lit_by(marked: Array) -> Array[String]:
	var ids: Array[String] = []
	for one in marked:
		if one["doing"]:
			ids.append(one["item"])
	return ids


## How many items an aura is worth where it stands. What the marked squares
## come to, and the number the player is really choosing between placements on.
static func worth(marked: Array) -> int:
	var count := 0
	for one in marked:
		if one["doing"]:
			count += 1
	return count


## The two markers, as polygons. Geometry rather than drawing, so the shapes
## can be checked without a screen.
##
## A star and a diamond, because that is what the catalogue calls the two zones
## and a player should not have to learn which colour means which. Simple
## outlines: they are laid over artwork the player still has to be able to see.


## A five-pointed star around a point.
static func star_points(middle: Vector2, reach: float) -> PackedVector2Array:
	var points := PackedVector2Array()
	for step in range(10):
		# Alternating out and in is what makes the points; a fixed ratio keeps
		# the star the same shape at any size.
		var out := reach if step % 2 == 0 else reach * 0.42
		var turn := -PI / 2.0 + step * PI / 5.0
		points.append(middle + Vector2(cos(turn), sin(turn)) * out)
	return points


## A diamond around a point: a square stood on its corner.
static func diamond_points(middle: Vector2, reach: float) -> PackedVector2Array:
	return PackedVector2Array([
		middle + Vector2(0, -reach),
		middle + Vector2(reach * 0.78, 0),
		middle + Vector2(0, reach),
		middle + Vector2(-reach * 0.78, 0),
	])
