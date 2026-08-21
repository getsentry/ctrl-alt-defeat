class_name Keycap
extends RefCounted

## The one button in this game.
##
## Every button the player presses is the same worn key from the logo, lit
## magenta under the pointer, so the whole game reads as one keyboard rather
## than as a screen of controls. It lived in main_menu.gd until the shop needed
## one too; a second copy of these numbers would have drifted from the first
## within a week.

const ART := preload("res://assets/ui/menu_button.png")
const LIT := preload("res://assets/ui/menu_button_magenta.png")

## How much of each end of the keycap is drawn at its own size rather than
## stretched with the rest of it.
##
## None of it, which wants saying. Slicing the ends off is what lets one
## picture of a key serve buttons of different widths, and these buttons are
## all one width -- so the only thing it does here is draw the ends at three
## times the detail of the stretched middle, which reads as two chunky blocks
## bolted to a thin key. The whole picture is squashed instead, near enough
## evenly: a button is about a third of the artwork either way.
##
## Give it 60 or so if a screen ever holds buttons of different widths.
const END := 0.0

## How much of the bottom of a button is the lit lip, as a share of its height.
## Nothing is sliced off the top or the bottom: a button is drawn about a third
## of the height of the artwork, and slices of the size the lip is drawn at
## would not fit inside it. So the key is squashed whole, and this only says how
## far up the lettering has to sit to stay on the face of it.
const LIP := 0.3

## The lettering. The same dark the logo's keycaps are lettered in.
const INK := Color("#2d2034")
const DIM := Color(0.35, 0.3, 0.38, 0.7)


static func style(art: Texture2D, tall: float, tint := Color.WHITE) -> StyleBoxTexture:
	"""One key, cut from the artwork and stretched to the width of the button."""
	var cap := StyleBoxTexture.new()
	cap.texture = art
	cap.texture_margin_left = END
	cap.texture_margin_right = END
	cap.modulate_color = tint
	cap.content_margin_left = 24.0
	cap.content_margin_right = 24.0
	cap.content_margin_top = 0.0
	cap.content_margin_bottom = tall * LIP
	return cap


static func dress(button: Button, font_size: int = 30) -> void:
	"""Turn a plain Button into one of ours, in every state it can be in."""
	var tall: float = max(button.custom_minimum_size.y, button.size.y)
	button.add_theme_stylebox_override("normal", style(ART, tall))
	button.add_theme_stylebox_override("hover", style(LIT, tall))
	button.add_theme_stylebox_override(
		"pressed", style(LIT, tall, Color(0.82, 0.82, 0.82)))
	button.add_theme_stylebox_override("focus", style(LIT, tall))
	button.add_theme_stylebox_override(
		"disabled", style(ART, tall, Color(0.62, 0.6, 0.66)))

	button.add_theme_font_size_override("font_size", font_size)
	for state in ["font_color", "font_hover_color", "font_pressed_color",
			"font_focus_color"]:
		button.add_theme_color_override(state, INK)
	button.add_theme_color_override("font_disabled_color", DIM)
