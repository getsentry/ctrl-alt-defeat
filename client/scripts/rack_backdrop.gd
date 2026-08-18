## The alcove a fighter's rack stands in.
##
## Drawn rather than framed. A neon outline round the rack said "here is a
## boundary" and nothing else; what the space wants to say is where the items
## are, which is a rack in a room full of them. So: two uprights with their
## perforations, a shelf line per rack unit, status lights that will not sit
## still, and cabling along the floor.
##
## Everything is derived from the rack's own cell size, so the shelf lines land
## where the rows of items land rather than near them.

extends Control
class_name RackBackdrop

const RAIL := 20.0
const HOLE_GAP := 22.0
const LED_GAP := 34.0
const CABLES := 5
## How often the status lights are allowed to change. Redrawing two of these
## every frame for the sake of a blinking light is not worth the frames.
const BLINK := 0.22

const BACK := Color(0.028, 0.022, 0.075, 0.94)
const SHADOW := Color(0.0, 0.0, 0.0, 0.45)

var accent: Color = Color.WHITE:
	set(value):
		accent = value
		queue_redraw()

## One rack unit: the height of a row of items, plus the gap under it.
var unit: float = 61.0:
	set(value):
		unit = maxf(value, 8.0)
		queue_redraw()

## Where the rack's own top edge sits inside the alcove, so the shelf lines
## land on the rows of items rather than near them.
var origin: float = 0.0:
	set(value):
		origin = value
		queue_redraw()

var _clock: float = 0.0
var _last_blink: float = 0.0


func _process(delta: float) -> void:
	_clock += delta
	if _clock - _last_blink >= BLINK:
		_last_blink = _clock
		queue_redraw()


func _draw() -> void:
	var w := size.x
	var h := size.y

	draw_rect(Rect2(Vector2.ZERO, size), BACK)
	_draw_depth(w, h)
	_draw_shelves(w, h)
	_draw_uprights(w, h)
	_draw_lights(h)
	_draw_cables(w, h)
	_draw_edge(w, h)


## Light falls from the front, so the back of the alcove is darkest at the top.
func _draw_depth(w: float, h: float) -> void:
	var bands := 9
	for i in bands:
		var top := h * i / float(bands)
		draw_rect(Rect2(Vector2(0, top), Vector2(w, h / float(bands))),
			Color(accent, 0.006 * i))
	draw_rect(Rect2(Vector2.ZERO, Vector2(w, 14)), SHADOW)


## One line per rack unit, level with the rows of items.
func _draw_shelves(w: float, h: float) -> void:
	var y := origin + unit
	while y < h - 6.0:
		draw_line(Vector2(RAIL, y), Vector2(w - RAIL, y), Color(accent, 0.075), 1.0)
		draw_line(Vector2(RAIL, y + 1), Vector2(w - RAIL, y + 1), Color(0, 0, 0, 0.25), 1.0)
		y += unit


## The two nineteen inch uprights, punched all the way down.
func _draw_uprights(w: float, h: float) -> void:
	for x in [0.0, w - RAIL]:
		draw_rect(Rect2(Vector2(x, 0), Vector2(RAIL, h)), Color(accent, 0.11))
		draw_line(Vector2(x + RAIL - 1, 0), Vector2(x + RAIL - 1, h), Color(accent, 0.22), 1.0)
		var hole := 14.0
		while hole < h - 10.0:
			draw_rect(Rect2(Vector2(x + RAIL / 2.0 - 2.0, hole), Vector2(4, 8)),
				Color(0, 0, 0, 0.55))
			hole += HOLE_GAP


## Status lights down the left upright. Most idle, a few working.
func _draw_lights(h: float) -> void:
	var at := 26.0
	var index := 0
	while at < h - 14.0:
		# Deterministic per position, so they blink in no pattern but do not
		# jump about when the rack is redrawn for another reason.
		var phase := sin(_clock * (1.1 + index % 4 * 0.6) + index * 2.3)
		var lit := phase > 0.35
		var tint := Color(0.4, 1.0, 0.6) if index % 5 else Color(1.0, 0.65, 0.2)
		draw_circle(Vector2(RAIL / 2.0, at), 2.5, Color(tint, 0.85 if lit else 0.18))
		if lit:
			draw_circle(Vector2(RAIL / 2.0, at), 5.0, Color(tint, 0.16))
		at += LED_GAP
		index += 1


## Cabling along the floor of the alcove, sagging between the uprights.
func _draw_cables(w: float, h: float) -> void:
	for i in CABLES:
		var sag := 7.0 + i * 3.0
		var base := h - 10.0 - i * 5.0
		var run := PackedVector2Array()
		for step in 13:
			var along := step / 12.0
			run.append(Vector2(RAIL + (w - RAIL * 2.0) * along,
				base + sin(along * PI) * sag))
		draw_polyline(run, Color(accent, 0.09), 2.0)


## A soft edge, stepped outwards. Not an outline: the boundary is not the point.
func _draw_edge(w: float, h: float) -> void:
	for step in range(4, 0, -1):
		var out := step * 3.0
		draw_rect(Rect2(Vector2(-out, -out), Vector2(w + out * 2.0, h + out * 2.0)),
			Color(accent, 0.05), false, 2.0)
	draw_rect(Rect2(Vector2.ZERO, size), Color(accent, 0.30), false, 2.0)
