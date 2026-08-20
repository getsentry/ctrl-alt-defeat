extends RefCounted

## The shape of an arc of electricity between two points.
##
## Geometry only: no colour, no width, no node. What makes it read as
## electricity rather than a wire is that it is redrawn as a different jag
## several times a second, and a shape that is worked out rather than
## remembered is what allows that.
##
## Each jag is settled by a seed, so the same seed always draws the same shape.
## The overlay animates by changing the seed, and a test can pin one.


## A jagged line from one point to the other.
##
## Both ends are exact: the arc has to start on the item it comes from and
## finish on the one it points at, or it reads as two separate strokes. Only
## the points in between wander, and by less as they near either end, which is
## what gives the taper of a real arc rather than a saw blade.
static func bolt(
	from: Vector2,
	to: Vector2,
	jag: int,
	spread: float = 10.0,
	steps: int = 12,
) -> PackedVector2Array:
	var points := PackedVector2Array()
	if steps < 2:
		steps = 2

	var along := to - from
	var sideways := Vector2(-along.y, along.x).normalized()
	var rng := RandomNumberGenerator.new()
	rng.seed = jag

	points.append(from)
	for step in range(1, steps):
		# Not on the beat. Turns spaced evenly down the line read as a saw
		# blade, so each one slides a little way along it as well as across.
		var fraction := clampf(
			(float(step) + rng.randf_range(-0.35, 0.35)) / steps, 0.0, 1.0)
		var straight := from.lerp(to, fraction)
		# Nothing at either end, most in the middle.
		var room := spread * sin(fraction * PI)
		points.append(straight + sideways * rng.randf_range(-room, room))
	points.append(to)

	return points


## A point some fraction of the way along a line, for the spark that runs down
## it. By length rather than by point, so the spark does not speed up over the
## long segments and crawl over the short ones.
static func along(points: PackedVector2Array, fraction: float) -> Vector2:
	if points.is_empty():
		return Vector2.ZERO
	# Both ends exactly, rather than as near as the arithmetic gets: a spark
	# that stops a hair short of the item it is running into is visible.
	if points.size() == 1 or fraction <= 0.0:
		return points[0]
	if fraction >= 1.0:
		return points[points.size() - 1]

	var lengths := PackedFloat32Array()
	var total := 0.0
	for step in range(points.size() - 1):
		total += points[step].distance_to(points[step + 1])
		lengths.append(total)
	if total <= 0.0:
		return points[0]

	var walked := clampf(fraction, 0.0, 1.0) * total
	for step in range(lengths.size()):
		if walked > lengths[step]:
			continue
		var before := 0.0 if step == 0 else lengths[step - 1]
		var segment := lengths[step] - before
		var into := 0.0 if segment <= 0.0 else (walked - before) / segment
		return points[step].lerp(points[step + 1], into)

	return points[points.size() - 1]


## An arc between two items, jagged by as much as its own length allows.
##
## A fixed wander is wrong at both ends of the scale: ten pixels of it is a
## crackle across a rack and nothing at all across the room. So the wander and
## the number of turns both come from how far the arc has to go, and a short
## hop between two items on the same shelf reads the same as a long reach to
## the chest.
static func arc(from: Vector2, to: Vector2, jag: int) -> PackedVector2Array:
	var reach := from.distance_to(to)
	return bolt(
		from, to, jag,
		clampf(reach * 0.07, 4.0, 34.0),
		clampi(int(reach / 24.0), 3, 26))


## Short branches off an arc, which is most of what makes one read as
## electricity rather than as a drawn line. Each starts somewhere along the arc
## and dies out well before it arrives anywhere: a fork that reached the other
## item would be a second arc, and the player would count two partners.
static func forks(points: PackedVector2Array, jag: int) -> Array:
	if points.size() < 4:
		return []

	var rng := RandomNumberGenerator.new()
	rng.seed = jag * 17 + 3
	var grown := []
	for fork in range(rng.randi_range(1, 3)):
		var leaves := rng.randi_range(1, points.size() - 2)
		var from := points[leaves]
		# Off at an angle to where the arc was going, and a short way only.
		var heading := (points[leaves + 1] - points[leaves - 1]).normalized()
		var reach := from.distance_to(points[points.size() - 1]) * \
			rng.randf_range(0.08, 0.22)
		var turned := heading.rotated(
			rng.randf_range(0.5, 1.2) * (1 if fork % 2 == 0 else -1))
		grown.append(bolt(from, from + turned * reach, jag + fork * 5,
			reach * 0.22, 3))
	return grown


## How bright an arc is at this moment. Never steady: a line held at one
## brightness is a wire, and it is the unevenness that reads as current.
static func flicker(jag: int) -> float:
	var rng := RandomNumberGenerator.new()
	rng.seed = jag * 7919
	return rng.randf_range(0.45, 1.0)


## Which jag to draw at this moment. Fourteen a second: fast enough to crackle,
## slow enough that the eye can still follow which items are joined.
const JAGS_A_SECOND := 14.0


static func jag_at(seconds: float, line: int = 0) -> int:
	# The line number is mixed in so that two arcs drawn at the same moment do
	# not jag in step, which reads as one shape rather than several.
	return int(seconds * JAGS_A_SECOND) * 31 + line * 7


## Where a line from the middle of a rectangle towards a point leaves it.
##
## An arc drawn between two middles runs under both pictures, and the end a
## player is looking at is the end they cannot see. This gives the arc the edge
## of the item to start from instead.
static func edge(rect: Rect2, towards: Vector2) -> Vector2:
	var middle := rect.get_center()
	var along := towards - middle
	if along == Vector2.ZERO or rect.size == Vector2.ZERO:
		return middle

	# How far along that direction the first wall is.
	var reach := INF
	if absf(along.x) > 0.0:
		reach = minf(reach, (rect.size.x / 2.0) / absf(along.x))
	if absf(along.y) > 0.0:
		reach = minf(reach, (rect.size.y / 2.0) / absf(along.y))
	if reach == INF or reach > 1.0:
		# The point is inside the rectangle, so the line never leaves it.
		return towards
	return middle + along * reach
