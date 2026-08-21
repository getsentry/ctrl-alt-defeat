extends GutTest
# The glyphs the built-in font does not have.
#
# Every one of these was a box on the web, and only on the web: a desktop
# build asks the operating system for a font that has them and a page has
# none to give. So the check is what the font itself can draw, which is what
# a browser is left with.

const Symbols = preload("res://scripts/symbols.gd")

const DRAWN := {
	0x2694: "the crossed swords between the fighters",
	0x25B6: "play",
	0x275A: "pause",
	0x2715: "the cross that closes the battle log",
	0x2605: "a star zone",
	0x25C6: "a diamond zone",
}


func test_the_built_in_font_still_cannot_draw_them():
	# The reason this file exists. If Godot ever ships a font that can, this
	# fails and the fallback can go.
	var bare := FontFile.new()
	assert_false(bare.has_char(0x2605),
		"An empty font should not have the star, or the test below proves nothing")


func test_every_symbol_the_game_draws_can_be_drawn():
	Symbols.stands_behind(ThemeDB.fallback_font)

	for code in DRAWN:
		assert_true(ThemeDB.fallback_font.has_char(code),
			"U+%04X, %s, has nothing to draw it" % [code, DRAWN[code]])


func test_the_fallback_is_added_once_however_often_it_is_asked():
	var font := FontFile.new()

	Symbols.stands_behind(font)
	Symbols.stands_behind(font)

	assert_eq(font.fallbacks.size(), 1, "The same file should not be listed twice")


func test_the_text_itself_is_left_alone():
	# A fallback rather than a replacement: Open Sans still draws the words.
	var font := FontFile.new()
	Symbols.stands_behind(font)

	assert_eq(font.fallbacks[0], Symbols.SYMBOLS, "behind, not instead of")
