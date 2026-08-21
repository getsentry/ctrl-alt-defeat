extends Control

## How to turn the item in your hand, said while there is one in it.
##
## Turning is the only thing a player has to be told: everything else on this
## screen is drag, drop or click, and none of that needs saying. A turn is two
## keys and the wheel, none of which are written anywhere, so a player who does
## not already know finds every long item unplaceable and no reason why.
##
## It is up only while something is being carried. A permanent notice reads as
## an instruction to be obeyed rather than an answer to a question just asked,
## and the question -- "how do I get this to fit?" -- is only ever asked with
## an item in hand.

## Amber, the colour the shop writes prices and plate edges in, so this reads
## as part of the same furniture rather than as a warning.
const ACCENT := Color(1, 0.85, 0.3)
const PLATE := Color(0.05, 0.05, 0.07, 0.9)

## What it says, before the keys. "Turn" was shorter and read as a noun on a
## plate of its own; this reads as the thing it is.
const SAYS := "Rotate item"

const SIZE := Vector2(330, 62)
## How far it keeps from the top right corner of the window.
const MARGIN := Vector2(22, 20)

## The key caps, in reading order, and what each one does.
const KEYS := ["R", "E"]
const KEY_SIZE := Vector2(30, 30)
const KEY_GAP := 6.0

## The mouse, drawn rather than lettered: "the wheel" is three words and a
## picture of a wheel is not.
const MOUSE_SIZE := Vector2(20, 30)

## How quickly it arrives and leaves. Quick enough not to be waited for, slow
## enough that it does not read as a flicker.
const FADE := 0.14

var _showing := false
var _fade: Tween = null


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	size = SIZE
	modulate.a = 0.0
	visible = false
	_settle()
	get_viewport().size_changed.connect(_settle)


## Put it in the top right corner of the window, where nothing else stands.
func _settle() -> void:
	var window := get_viewport_rect().size
	position = Vector2(window.x - SIZE.x - MARGIN.x, MARGIN.y)


## Say whether something is being carried. Called every frame, so it does
## nothing at all when the answer has not changed.
func carrying(something: bool) -> void:
	if something == _showing:
		return
	_showing = something

	if _fade != null and _fade.is_valid():
		_fade.kill()
	if something:
		visible = true
	_fade = create_tween()
	_fade.tween_property(self, "modulate:a", 1.0 if something else 0.0, FADE)
	if not something:
		_fade.tween_callback(func(): visible = false)


func showing() -> bool:
	return _showing


func _draw() -> void:
	_draw_plate()

	var font := get_theme_default_font()
	var at := Vector2(14, (SIZE.y - KEY_SIZE.y) / 2.0)

	draw_string(font, at + Vector2(0, KEY_SIZE.y * 0.72), SAYS,
		HORIZONTAL_ALIGNMENT_LEFT, -1, 16, Color(ACCENT, 0.85))
	at.x += font.get_string_size(
		SAYS, HORIZONTAL_ALIGNMENT_LEFT, -1, 16).x + 12.0

	for cap in KEYS:
		_draw_key(at, cap, font)
		at.x += KEY_SIZE.x + KEY_GAP

	at.x += 4
	_draw_mouse(Vector2(at.x, (SIZE.y - MOUSE_SIZE.y) / 2.0))
	at.x += MOUSE_SIZE.x + 10

	draw_string(font, Vector2(at.x, SIZE.y / 2.0 + 6), "wheel",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 15, Color(1, 1, 1, 0.7))


func _draw_plate() -> void:
	var whole := Rect2(Vector2.ZERO, SIZE)
	draw_rect(whole, PLATE)
	draw_rect(whole, Color(ACCENT, 0.35), false, 2.0)


## One key cap, with the letter on it.
func _draw_key(at: Vector2, cap: String, font: Font) -> void:
	var box := Rect2(at, KEY_SIZE)
	draw_rect(box, Color(ACCENT, 0.12))
	draw_rect(box, Color(ACCENT, 0.6), false, 1.5)
	var letter := font.get_string_size(cap, HORIZONTAL_ALIGNMENT_LEFT, -1, 17)
	draw_string(font, at + Vector2((KEY_SIZE.x - letter.x) / 2.0, 21), cap,
		HORIZONTAL_ALIGNMENT_LEFT, -1, 17, Color(1, 1, 1, 0.92))


## A mouse seen from above, with the wheel between its buttons.
func _draw_mouse(at: Vector2) -> void:
	var body := Rect2(at, MOUSE_SIZE)
	draw_rect(body, Color(ACCENT, 0.1))
	draw_rect(body, Color(ACCENT, 0.6), false, 1.5)
	# The line dividing the two buttons, down to the waist of the mouse.
	draw_line(Vector2(body.get_center().x, at.y),
		Vector2(body.get_center().x, at.y + MOUSE_SIZE.y * 0.42),
		Color(ACCENT, 0.45), 1.0)
	# The wheel itself, lit, because it is the part being talked about.
	var wheel := Rect2(
		body.get_center().x - 2.0, at.y + MOUSE_SIZE.y * 0.14, 4.0,
		MOUSE_SIZE.y * 0.26)
	draw_rect(wheel, Color(1, 1, 1, 0.9))
