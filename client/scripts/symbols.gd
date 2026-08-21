extends Node

## The glyphs the built-in font does not have.
##
## Godot ships Open Sans and no fallbacks, and Open Sans has none of the
## symbols this game draws: not the play triangle, not the pause bars, not the
## close cross, not the crossed swords between the fighters, and not the star
## and diamond an aura is named by. On a desktop they appear anyway, because
## Godot asks the operating system for a font that has them. A page has no
## such font to offer, so the web build drew a box for every one of them.
##
## So a font carrying exactly those six is put behind the built-in one. Behind:
## the text stays Open Sans, and only a character it cannot draw is fetched
## from here. See assets/fonts/README.md for what is in it and how it was cut.

const SYMBOLS := preload("res://assets/fonts/noto_symbols_subset.ttf")


func _ready() -> void:
	stands_behind(ThemeDB.fallback_font)


static func stands_behind(font: Font) -> void:
	"""Put the symbol font behind this one, and only once.

	Godot's own font is a resource shared by everything that draws text, so
	adding to its fallbacks reaches every label, button and rich text in the
	game -- and adding twice would leave the same file in the list twice.
	"""
	if font == null or font.fallbacks.has(SYMBOLS):
		return
	font.fallbacks = font.fallbacks + [SYMBOLS]
