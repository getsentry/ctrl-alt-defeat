# The palette, as name to hex. Sixteen of Kelly's 22 colours of maximum contrast
# (1965), less white, less black, and less the four darkest, which disappear
# against the UI background. Sixteen is near the limit of what a person can tell
# apart by hue alone, so add patterns rather than a seventeenth colour.
#
# The client is sent the value and keeps no palette, so a colour can be retuned
# here without shipping a new client. A pattern is the other way round: it
# arrives as a name, because the client is what draws it.
PALETTE = {
    # In use, one per category.
    "red": "#BE0032",
    "orange": "#F38400",
    "yellow": "#F3C300",
    "lime": "#8DB600",
    "green": "#008856",
    "sky": "#A1CAF1",
    "blue": "#0067A5",
    "violet": "#604E97",
    "pink": "#E68FAC",
    "sand": "#C2B280",
    # Spare, for a category that outgrows the patterns.
    "amber": "#F6A600",
    "ember": "#E25822",
    "citron": "#DCD300",
    "salmon": "#F99379",
    "magenta": "#B3446C",
    "purple": "#875692",
}

# A category larger than the pattern list borrows a second colour, close in
# hue to its first so the category still reads as one thing. Only the two big
# categories need one: 63 weapons and 58 accessories against 36 patterns.
CATEGORY_EXTRA_COLOR = {
    "problem": "ember",  # red-orange, beside red
    "protocol": "citron",  # yellow-green, beside green
}

# Which colour every item of a category wears.
CATEGORY_COLOR = {
    "problem": "red",
    "module": "orange",
    "protocol": "green",
    "consumable": "pink",
    "script": "lime",
    "defense": "blue",
    "infrastructure": "violet",
    "patch": "yellow",
    "monitor": "sky",
    "pet": "sand",
}

# The patterns, most distinct first. A category with four items uses only the
# first four, so the order is what decides how well a small category reads.
PATTERNS = (
    "solid",
    "stripe_d_bold",
    "dot_large_grid",
    "stripe_v_bold",
    "check_large",
    "stripe_h_bold",
    "hatch_diag",
    "dot_small_stagger",
    "chevron_up",
    "stripe_a_bold",
    "rings",
    "stripe_v_fine",
    "dot_large_stagger",
    "check_small",
    "stripe_h_fine",
    "hatch_ortho",
    "chevron_right",
    "stripe_d_fine",
    "dot_small_grid",
    "stripe_a_fine",
    # Added when the catalogue grew past 96 items. Different shapes rather
    # than finer rulings of the ones above, which stop being tellable apart.
    "grid_bold",
    "grid_fine",
    "zigzag_h",
    "zigzag_v",
    "wave_h",
    "wave_v",
    "brick_h",
    "brick_v",
    "scale",
    "triangle_up",
    "triangle_down",
    "diamond_grid",
    "diamond_stagger",
    "cross_grid",
    "plus_grid",
    "speckle",
)


def hex_of(name: str) -> str:
    """The value behind a palette name.

    An item carries the name, because that is what a person edits. What goes
    to the client is the value, so that the client needs no copy of the
    palette and a colour can be retuned without shipping a new client.
    """
    if name not in PALETTE:
        raise KeyError(f"{name} is not a colour in the palette")
    return PALETTE[name]
