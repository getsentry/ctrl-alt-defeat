## A hard-edged HUD plate: pointed ends, a notch bitten out of the top edge,
## scanlines across the fill and a double outline.
##
## Drawn rather than styled, because a StyleBoxFlat only does rounded corners
## and GL compatibility has no bloom to make an edge glow, so the glow here is
## a few outlines stepped outwards.

extends Control
class_name NeonPlate

const SLANT := 30.0
const NOTCH_AT := 0.62
const NOTCH_WIDTH := 54.0
const NOTCH_DEPTH := 10.0
const INNER_INSET := 9.0
const SCANLINE_GAP := 5.0
const GLOW_STEPS := 5
const GLOW_REACH := 15.0
const FILL := Color(0.045, 0.03, 0.13, 0.93)

var accent: Color = Color.WHITE:
	set(value):
		accent = value
		queue_redraw()

## Where a band of light sits on the plate, 0 at the top and 1 at the
## bottom. Negative means no band.
var sweep: float = -1.0:
	set(value):
		sweep = value
		queue_redraw()

func _notification(what: int) -> void:
	if what == NOTIFICATION_RESIZED:
		queue_redraw()

func _draw() -> void:
	for step in range(GLOW_STEPS, 0, -1):
		var reach := GLOW_REACH * step / GLOW_STEPS
		draw_polyline(_shape(-reach), Color(accent, 0.07), 2.0 + reach, true)

	draw_colored_polygon(_shape(0.0), FILL)
	_draw_scanlines()
	_draw_sweep()
	draw_polyline(_shape(INNER_INSET), Color(accent, 0.28), 1.0, true)
	draw_polyline(_shape(0.0), accent, 3.0, true)

## The plate outline, inset by `inset` on every side. A negative inset grows
## it, which is how the glow rings are drawn.
func _shape(inset: float) -> PackedVector2Array:
	var x := inset
	var y := inset
	var w := size.x - inset * 2.0
	var h := size.y - inset * 2.0
	var points := PackedVector2Array()
	points.append(Vector2(x + SLANT, y))

	var notch := x + w * NOTCH_AT
	if notch + NOTCH_WIDTH < x + w - SLANT - 12.0:
		points.append(Vector2(notch, y))
		points.append(Vector2(notch + 10.0, y + NOTCH_DEPTH))
		points.append(Vector2(notch + NOTCH_WIDTH - 10.0, y + NOTCH_DEPTH))
		points.append(Vector2(notch + NOTCH_WIDTH, y))

	points.append(Vector2(x + w - SLANT, y))
	points.append(Vector2(x + w, y + h / 2.0))
	points.append(Vector2(x + w - SLANT, y + h))
	points.append(Vector2(x + SLANT, y + h))
	points.append(Vector2(x, y + h / 2.0))
	points.append(Vector2(x + SLANT, y))
	return points

## How far in the pointed ends have closed at this height.
func _span(y: float) -> Vector2:
	var half := size.y / 2.0
	var inset := SLANT * absf(y - half) / half
	return Vector2(inset, size.x - inset)

func _draw_scanlines() -> void:
	var y := SCANLINE_GAP
	while y < size.y:
		var span := _span(y)
		draw_line(Vector2(span.x, y), Vector2(span.y, y), Color(accent, 0.05), 1.0)
		y += SCANLINE_GAP

func _draw_sweep() -> void:
	if sweep < 0.0:
		return
	var at := sweep * size.y
	for offset in range(-4, 5):
		var y := at + offset * 2.0
		if y < 0.0 or y > size.y:
			continue
		var span := _span(y)
		draw_line(Vector2(span.x, y), Vector2(span.y, y),
			Color(accent, 0.22 * (1.0 - absf(offset) / 5.0)), 2.0)
