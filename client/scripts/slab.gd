class_name Slab
extends RefCounted

## The panel this game puts words on, and the colours it writes them in.
##
## A screen built in code is a screen with its palette written into it, and the
## second one written a shade off is the one that looks wrong without anybody
## being able to say why. So the picker's look lives here, where the game-over
## screen can have the same one -- the same near-black behind, the same dark
## slab with a violet edge, the same cream lettering.
##
## The button that goes under all this is Keycap, for the same reason.

## Over whatever is behind, so the words are read against one colour rather
## than against a room. Not opaque: the run the player just finished is still
## faintly there.
const DIM := Color(0.055, 0.039, 0.078, 0.88)

## What a slab is made of, and the edge around it.
const FILL := Color(0.110, 0.078, 0.157)
const EDGE := Color(0.275, 0.220, 0.361)

## Lettering: cream for what is said, magenta for what matters in it, muted
## for the words that only label a number.
const CREAM := Color(0.949, 0.890, 0.769)
const MAGENTA := Color(1.0, 0.239, 0.745)
const MUTED := Color(0.541, 0.471, 0.620)

## And the two answers a run can end with.
const WON := Color(0.376, 0.965, 0.639)
const LOST := Color(1.0, 0.412, 0.435)


static func over_everything() -> ColorRect:
	"""The dim that separates a panel from whatever it stands in front of"""
	var dim := ColorRect.new()
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	dim.color = DIM
	return dim


static func slab(fill: Color = FILL, edge: Color = EDGE, width: int = 2) -> StyleBoxFlat:
	"""One panel: dark, edged, and rounded the way the cards are"""
	var box := StyleBoxFlat.new()
	box.bg_color = fill
	box.border_color = edge
	box.set_border_width_all(width)
	box.set_corner_radius_all(12)
	box.set_content_margin_all(8)
	return box


static func heading(text: String, size: int, colour: Color = CREAM) -> Label:
	"""A line of words, centred, in the size and colour it is meant in"""
	var label := Label.new()
	label.text = text
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.add_theme_font_size_override("font_size", size)
	label.add_theme_color_override("font_color", colour)
	return label


static func row(caption: String, size: int = 26) -> HBoxContainer:
	"""A number with a word for what it is: the label left, the value right.

	The same shape an item's card uses for its stats, which is where a player
	has already learned to read one.
	"""
	var line := HBoxContainer.new()
	line.add_theme_constant_override("separation", 40)

	var left := Label.new()
	left.text = caption
	left.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left.add_theme_font_size_override("font_size", size)
	left.add_theme_color_override("font_color", MUTED)
	line.add_child(left)

	var right := Label.new()
	right.name = "Value"
	right.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	right.add_theme_font_size_override("font_size", size)
	right.add_theme_color_override("font_color", CREAM)
	line.add_child(right)

	return line
