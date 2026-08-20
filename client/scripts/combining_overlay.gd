extends Control

## What the player is shown about combining, drawn over the whole shop screen
## (GDD 5.3). Three things, all of them on one node because all three are lines
## and glows between items that stand in three different places -- the shelf,
## the rack and the chest -- and only something drawn over the lot of them can
## join one to another.
##
## - An **arc** from the item under the pointer, or in hand, to every item it
##   could combine with. Which items those are is a fact about the catalogue,
##   so it is answered on this side; see combining.gd.
## - An **orange glow** joining the items that will combine when the battle
##   starts, so the player can see it coming and break it up first.
## - A **progress label** beside a part just put down: "Long Poll 2/3".
##
## It is told which items to join, never which items exist. Where a thing is on
## screen is the screen's business, so this takes the nodes and asks them.

const Lightning = preload("res://scripts/lightning.gd")

## Cold blue-white, so an arc reads as current rather than as one more thing
## the room is lit by.
const HALO := Color(0.35, 0.85, 1.0)
const CORE := Color(0.93, 0.99, 1.0)
## Orange, which is what GDD 5.3 asks for and what nothing else on the screen
## uses. It has to be seen against the rack's yellow-green and the shop's blue.
const READY := Color(1.0, 0.55, 0.12)

## Above the items and below a tooltip, which sits at 100. An arc that covered
## the card explaining the item it points at would be worse than no arc.
const LAYER := 50

## How near two items have to be before the arc between them is drawn middle to
## middle rather than edge to edge. Two squares, about.
const TOUCHING := 26.0

# Where the arcs come from, and what they point at. Nodes rather than places,
# so a line follows an item being dragged without being told it moved.
var _from: Control = null
var _to: Array[Control] = []
# Each entry is the items of one combination that is about to happen.
var _groups: Array = []

# Blooms where ingredients met, each with the moment it was struck.
var _flashes: Array = []

var _label: Label = null
var _label_over: Control = null

var _time := 0.0


func _ready() -> void:
	# It draws over everything and answers nothing: a click has to reach the
	# item under it.
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	z_index = LAYER
	set_anchors_preset(Control.PRESET_FULL_RECT)
	_build_label()


func _process(delta: float) -> void:
	# Only while there is something moving to draw. An arc is a jag redrawn
	# several times a second, a glow breathes, a bloom fades; nothing else
	# here moves.
	_time += delta
	var alive := []
	for flash in _flashes:
		if _time - flash["struck"] < flash["life"]:
			alive.append(flash)
	_flashes = alive
	if _from != null or not _groups.is_empty() or not _flashes.is_empty():
		queue_redraw()


# ============= What to draw =============


func lines_from(source: Control, targets: Array) -> void:
	"""Draw an arc from this item to each of those.

	Called on hover and on picking something up, and again whenever what is
	on screen changes. The nodes are kept rather than their places, because
	the source of these arcs is usually being dragged.
	"""
	_from = source
	_to = []
	for target in targets:
		if target is Control:
			_to.append(target)
	queue_redraw()


func no_lines() -> void:
	_from = null
	_to = []
	queue_redraw()


func glow_around(groups: Array) -> void:
	"""Join up the items of each combination that is about to happen.

	One list of items per combination. They stay lit whatever the pointer is
	doing: this is not an answer to a question the player asked, it is a
	warning about something that will happen if they do nothing.
	"""
	_groups = []
	for group in groups:
		var lit: Array[Control] = []
		for item in group:
			if item is Control:
				lit.append(item)
		if not lit.is_empty():
			_groups.append(lit)
	queue_redraw()


func flash_at(spot_on_screen: Vector2, life: float = 0.5) -> void:
	"""A bloom of light where ingredients met and became one thing.

	Round and soft-edged, because it is light. A square of colour over the
	squares would read as a card laid on the rack.
	"""
	_flashes.append({
		"at": get_global_transform().affine_inverse() * spot_on_screen,
		"struck": _time,
		"life": life,
	})
	queue_redraw()


func flashes() -> int:
	return _flashes.size()


func progress(text: String, over: Control) -> void:
	"""Put a label above an item: "Long Poll 2/3".

	It belongs to the item the arcs come from, so it comes and goes with them:
	the player asked about that item by reaching for it, and the answer stays
	up for as long as they are still reaching.
	"""
	if text == "" or over == null:
		no_progress()
		return
	_label.text = text
	_label_over = over
	_label.visible = true
	_place_label()


func no_progress() -> void:
	_label_over = null
	if _label != null:
		_label.visible = false


# ============= What is being drawn =============
#
# Where each thing lands, worked out from the nodes it was given. _draw() uses
# these, and so does a test: a headless run draws nothing, so what is checked
# is what would have been drawn.


func arcs() -> Array:
	"""Every arc as its two ends, in this node's own space."""
	var drawn := []
	if not is_instance_valid(_from):
		return drawn
	var source := _rect_of(_from)
	for target in _to:
		if not is_instance_valid(target):
			continue
		var reaches := _rect_of(target)
		var leaves := Lightning.edge(source, reaches.get_center())
		var lands := Lightning.edge(reaches, source.get_center())
		# Two items side by side share an edge, and an arc drawn between the
		# two touching corners is a pixel long and reads as nothing at all.
		# Near neighbours are joined middle to middle instead, over the top of
		# both, where there is room for the arc to be seen.
		if leaves.distance_to(lands) < TOUCHING:
			drawn.append([source.get_center(), reaches.get_center()])
		else:
			drawn.append([leaves, lands])
	return drawn


func glowing() -> Array:
	"""Every item lit as about to combine, in this node's own space."""
	var lit := []
	for group in _groups:
		for item in group:
			if is_instance_valid(item):
				lit.append(_rect_of(item))
	return lit


func label_text() -> String:
	if _label == null or not _label.visible:
		return ""
	return _label.text


# ============= The drawing itself =============


func _draw() -> void:
	for group in _groups:
		_draw_glow(group)
	for flash in _flashes:
		_draw_flash(flash)
	var line := 0
	for ends in arcs():
		_draw_arc_between(ends[0], ends[1], line)
		line += 1


func _draw_arc_between(from: Vector2, to: Vector2, line: int) -> void:
	var jag := Lightning.jag_at(_time, line)
	var lit := Lightning.flicker(jag)

	# Three strands rather than one line. They are struck from the same two
	# points by different jags, so they cross and part along the way, which is
	# what an arc does and what a stroke of any width cannot.
	var strands := [
		Lightning.arc(from, to, jag),
		Lightning.arc(from, to, jag + 101),
		Lightning.arc(from, to, jag + 211),
	]
	# Faint on purpose. The player is looking at the items, and an arc that
	# competes with them is in the way; it only has to be enough to follow.
	for strand in strands:
		draw_polyline(strand, Color(HALO, 0.10 * lit), 9.0, true)
	draw_polyline(strands[0], Color(HALO, 0.22 * lit), 4.0, true)
	draw_polyline(strands[0], Color(CORE, 0.55 * lit), 1.4, true)
	draw_polyline(strands[1], Color(CORE, 0.30 * lit), 1.0, true)
	draw_polyline(strands[2], Color(HALO, 0.22 * lit), 1.0, true)

	for fork in Lightning.forks(strands[0], jag):
		draw_polyline(fork, Color(HALO, 0.18 * lit), 3.0, true)
		draw_polyline(fork, Color(CORE, 0.35 * lit), 1.0, true)

	# A spark running the length of it, so the eye is led from the item in hand
	# to the item it could go with.
	var spark := Lightning.along(strands[0],
		fposmod(_time * 1.6 + line * 0.3, 1.0))
	draw_circle(spark, 5.0, Color(HALO, 0.22))
	draw_circle(spark, 1.8, Color(CORE, 0.75))


func _draw_flash(flash: Dictionary) -> void:
	var age: float = (_time - flash["struck"]) / flash["life"]
	var fading := 1.0 - clampf(age, 0.0, 1.0)
	# Growing as it goes out, which is what a flash of light does and what
	# tells the player it has happened rather than that it is happening.
	var reach := 16.0 + 44.0 * age
	var at: Vector2 = flash["at"]
	draw_circle(at, reach, Color(READY, 0.28 * fading))
	draw_circle(at, reach * 0.6, Color(1.0, 0.92, 0.7, 0.45 * fading))
	draw_circle(at, reach * 0.28, Color(1.0, 1.0, 0.96, 0.8 * fading))


func _draw_glow(group: Array) -> void:
	# Breathing, because a still glow reads as part of the artwork. It has to
	# carry across a wall of pipes and warning stripes, so it is never faint.
	var lit := 0.75 + 0.25 * sin(_time * 3.0)

	var middles := PackedVector2Array()
	for item in group:
		if not is_instance_valid(item):
			continue
		var rect := _rect_of(item)
		middles.append(rect.get_center())

		# A wash under the item and rings around it. The wash is what the eye
		# catches across the room; the rings are what says which squares.
		draw_rect(rect.grow(7.0), Color(READY, lit * 0.22))
		for ring in range(3):
			draw_rect(rect.grow(1.0 + ring * 4.0),
				Color(READY, lit * (0.9 - ring * 0.25)), false, 3.0 - ring)

	# One item touches all the others, so the joins are drawn from the first of
	# them: that is the shape the recipe actually has (GDD 5.3).
	if middles.size() < 2:
		return
	for other in range(1, middles.size()):
		draw_line(middles[0], middles[other], Color(READY, lit * 0.35), 9.0, true)
		draw_line(middles[0], middles[other], Color(1, 0.85, 0.6, lit), 2.0, true)


# ============= Where things are =============


func _rect_of(node: Control) -> Rect2:
	"""Where an item is, in this node's own space.

	An item in the chest hangs off a physics body and one on the shelf off a
	shelf, so what they share is where they are on the screen, and that is what
	is asked for here.
	"""
	var rect := node.get_global_rect()
	var here := get_global_transform().affine_inverse()
	return Rect2(here * rect.position, here.basis_xform(rect.size))


func _build_label() -> void:
	_label = Label.new()
	_label.name = "Progress"
	_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_label.visible = false
	_label.add_theme_color_override("font_color", Color(1.0, 0.93, 0.75))
	_label.add_theme_color_override("font_outline_color", Color(0.05, 0.03, 0.0))
	_label.add_theme_constant_override("outline_size", 6)
	add_child(_label)


func _place_label() -> void:
	if _label == null or not is_instance_valid(_label_over):
		return
	var over := _rect_of(_label_over)
	_label.size = _label.get_minimum_size()
	# Above the item and in the middle of it, which is where a hand reaching
	# for the item is not.
	_label.position = Vector2(
		over.get_center().x - _label.size.x / 2.0,
		over.position.y - _label.size.y - 4.0)
