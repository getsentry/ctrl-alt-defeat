## The plate a shop price is written on.
##
## Drawn rather than styled. A StyleBoxFlat gives a flat rectangle with a
## border, which is a text box; a price wants a face — a lit top edge, a coin
## stamped on it — so that it reads as money at a glance and not as a caption
## that happens to hold a number.
##
## It draws the plate only. The number itself is the Label this sits behind, so
## that the price stays a piece of text something can read.

extends Control
class_name PriceTag

const CORNER := 7.0
const COIN_RADIUS := 8.0
const COIN_CENTRE := 16.0
## How much of the plate the lit edge covers.
const SHEEN := 0.38
## Where the word sits when the plate is a sale plate, and how big it is.
const FLAG_CENTRE := 28.0
const FLAG_FONT_SIZE := 14

## The colour of the metal. Gold ordinarily, green for a sale, red for a price
## there is not enough gold to meet.
var ink: Color = Color(1.0, 0.82, 0.25):
	set(value):
		ink = value
		queue_redraw()

## Whether the plate says SALE where the coin would otherwise be.
var sale: bool = false:
	set(value):
		sale = value
		queue_redraw()


func _notification(what: int) -> void:
	if what == NOTIFICATION_RESIZED:
		queue_redraw()


## How far in from the left edge the number has to start to clear the coin or
## the word. The plate knows this; the label asks it rather than guessing.
func text_inset() -> float:
	return (FLAG_CENTRE * 2.0 + 6.0) if sale else (COIN_CENTRE + COIN_RADIUS + 4.0)


func _draw() -> void:
	var plate := StyleBoxFlat.new()
	plate.bg_color = ink.darkened(0.18)
	plate.border_color = ink.lightened(0.4)
	plate.set_border_width_all(2)
	plate.set_corner_radius_all(int(CORNER))
	draw_style_box(plate, Rect2(Vector2.ZERO, size))

	_draw_sheen()

	if sale:
		_draw_sale_word()
	else:
		_draw_coin(Vector2(COIN_CENTRE, size.y / 2.0))


func _draw_sheen() -> void:
	"""The lit top of the plate, fading downwards.

	Without it the plate is one flat colour and has no face to catch the
	light. Drawn as a handful of bands rather than one, because a single band
	leaves a hard line across the middle of the tag where it stops.
	"""
	var bands := 16
	var top := 3.0
	var reach := size.y * SHEEN
	for band in bands:
		var lit := Color(ink.lightened(0.55), 0.5 * pow(1.0 - float(band) / bands, 1.6))
		var strip := StyleBoxFlat.new()
		strip.bg_color = lit
		if band == 0:
			strip.corner_radius_top_left = int(CORNER) - 2
			strip.corner_radius_top_right = int(CORNER) - 2
		draw_style_box(strip, Rect2(
			Vector2(3.0, top + reach * band / bands),
			Vector2(maxf(size.x - 6.0, 0.0), reach / bands + 1.0)))


func _draw_coin(at: Vector2) -> void:
	"""A coin stamped into the plate, so the number is money and not a count"""
	draw_circle(at, COIN_RADIUS, ink.lightened(0.3))
	draw_arc(at, COIN_RADIUS, 0.0, TAU, 24, ink.darkened(0.55), 1.5)
	draw_arc(at, COIN_RADIUS * 0.5, 0.0, TAU, 20, ink.darkened(0.5), 1.5)


func _draw_sale_word() -> void:
	"""SALE, where the coin goes on an ordinary plate.

	It takes the coin's place rather than standing beside the tag, so that a
	sale is one thing to look at and not two.
	"""
	var font := ThemeDB.fallback_font
	var text := "SALE"
	var font_size := FLAG_FONT_SIZE
	var width := font.get_string_size(
		text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size).x
	draw_string(
		font,
		Vector2(FLAG_CENTRE - width / 2.0, size.y / 2.0 + font_size / 2.5),
		text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size,
		ink.darkened(0.72)
	)
