extends Control

## What every word in this game means, on one page (GDD 3, 4.3, 5.3).
##
## A player is shown "gain 2 spiked", "for each sentinel star item", "3 of 5
## parts" and left to work out what any of it is. The battle screen explains a
## status where it appears -- hover a chip and a card says what a stack does --
## but only during a battle, and only for a status somebody already has. This
## says all of it at once, before the first run.
##
## Built in code, like the Sentaur picker, out of the same pieces: Slab for the
## panel and the lettering, Keycap for the button that closes it.
##
## The words about statuses are the server's, from `/catalogue/statuses`, which
## is where the battle screen gets them too. A copy of them here would go on
## saying 2% the day after it stopped being 2%. The rest -- zones, combining,
## the numbers on a card -- are rules that live in the design document, and
## are written out here because nothing serves them.

const ICON_PATH := "res://assets/icons/statuses/%s.png"

## The two zone colours are the overlay's own, so a zone reads the same here as
## it does drawn on the rack.
const AuraOverlay = preload("res://scripts/aura_overlay.gd")

## How wide the page is, and how much of the screen it may fill before it
## starts scrolling instead of growing. The panel is the heading, this, and a
## key: 640 leaves the whole of it on a 1050-tall screen.
const WIDE := 860.0
const TALLEST := 640.0

var _column: VBoxContainer
var _scroll: ScrollContainer


func _ready() -> void:
	# Offsets as well as anchors. Added to a screen that is not a container,
	# an overlay with anchors alone keeps the zero size it was made with, and
	# everything inside it lays out from the top left corner of the window.
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	z_index = 100

	add_child(Slab.over_everything())

	var middle := CenterContainer.new()
	middle.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(middle)

	var panel := PanelContainer.new()
	panel.name = "Panel"
	panel.custom_minimum_size = Vector2(WIDE, 0)
	panel.add_theme_stylebox_override("panel", Slab.slab())
	middle.add_child(panel)

	var margin := MarginContainer.new()
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 36)
	panel.add_child(margin)

	var page := VBoxContainer.new()
	page.add_theme_constant_override("separation", 16)
	margin.add_child(page)

	page.add_child(Slab.heading("HOW TO PLAY", 36))

	# The page is longer than any screen, so it scrolls rather than growing.
	var scroll := ScrollContainer.new()
	scroll.custom_minimum_size = Vector2(WIDE - 90, TALLEST)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	page.add_child(scroll)

	_scroll = scroll
	_column = VBoxContainer.new()
	_column.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_column.add_theme_constant_override("separation", 10)
	scroll.add_child(_column)

	var done := Button.new()
	done.text = "GOT IT"
	done.custom_minimum_size = Vector2(260, 62)
	done.size = done.custom_minimum_size
	Keycap.dress(done, 26)
	done.pressed.connect(queue_free)
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_child(done)
	page.add_child(row)

	_write_the_rules()
	_ask_what_the_statuses_do()

	# At the top. Filling a scrolling box leaves it wherever the last thing
	# added put it, and a page of instructions that opens halfway down reads
	# as one that has already been half read.
	_to_the_top.call_deferred()


func _to_the_top() -> void:
	if is_instance_valid(_scroll):
		_scroll.scroll_vertical = 0


func _write_the_rules() -> void:
	"""Everything that does not have to be fetched"""
	_part("The run")
	_line("Ten rounds against somebody else's rack. Win a round and you keep "
		+ "your tries; lose and you spend one. Run out and the run is over.")
	_line("Between rounds you buy items and arrange them. A battle is fought "
		+ "by the rack you leave behind, not by you: everything is decided by "
		+ "where things stand when it starts.")

	_part("On a card")
	_pair("Damage", "What a weapon rolls each time it goes off.")
	_pair("Cooldown", "How long it waits between goes.")
	_pair("CPU", "What it costs to go off. Run dry and items wait for the "
		+ "pool to fill.")
	_pair("Quota", "What you have left. It is the health bar.")
	_pair("Traits", "The words under an item -- Sentinel, Feral, Cryo. Auras "
		+ "ask for them by name.")

	_part("Zones")
	_line("An item can project a zone onto the squares around it, drawn on "
		+ "the rack while you hold or hover the item.")
	_zone("star", "A star zone.")
	_zone("diamond", "A diamond zone. An item can have either, both or neither.")
	_line("A zone reaches an item when any square of it lands on any square "
		+ "that item covers -- touching is not the rule, the shape is. It "
		+ "never reaches the item projecting it, and turning an item turns "
		+ "its zone with it.")

	_part("Combining")
	_line("Some items make another when they are put together in your rack. "
		+ "One of the parts has to touch all the others; they do not have to "
		+ "touch each other.")
	_line("It happens as the next shop opens, straight after the battle, and "
		+ "one step at a time -- a result does not combine again until the "
		+ "round after. The new item lands on the squares its parts freed, or "
		+ "goes to the chest if it will not fit.")
	_line("A part with a glow and a count under it is one you are part way to.")

	_part("Buffs and debuffs")
	_line("Both stack, and both are counted per fighter rather than per item. "
		+ "What one stack is worth:")


func _ask_what_the_statuses_do() -> void:
	"""The statuses, in the server's own words.

	Fetched rather than written down: the same call the battle screen makes,
	and the same answer. Until it lands the page is complete without them.
	"""
	var rules = await BattleServerAPI.status_rules()
	if rules == null or not rules.knows_any() or not is_instance_valid(self):
		_line("(The list of buffs could not be fetched just now.)")
		return

	for status in rules.rules:
		var about: Dictionary = rules.about(status)
		_status(status, about)


func _status(status: String, about: Dictionary) -> void:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)

	var icon := TextureRect.new()
	icon.custom_minimum_size = Vector2(30, 30)
	icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	if ResourceLoader.exists(ICON_PATH % status):
		icon.texture = load(ICON_PATH % status)
	row.add_child(icon)

	var name := Label.new()
	name.text = str(about["shown"]).capitalize()
	name.custom_minimum_size = Vector2(150, 0)
	name.add_theme_font_size_override("font_size", 19)
	name.add_theme_color_override("font_color",
		Slab.WON if about["kind"] == "buff" else Slab.LOST)
	row.add_child(name)

	var says := Label.new()
	says.text = str(about["one"])
	if about["detail"] != "":
		says.text += ". " + str(about["detail"])
	says.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	says.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	says.add_theme_font_size_override("font_size", 17)
	says.add_theme_color_override("font_color", Slab.CREAM)
	row.add_child(says)

	_column.add_child(row)


func _part(title: String) -> void:
	"""A heading, with room above it unless it is the first"""
	if _column.get_child_count() > 0:
		var gap := Control.new()
		gap.custom_minimum_size = Vector2(0, 14)
		_column.add_child(gap)

	var heading := Label.new()
	heading.text = title.to_upper()
	heading.add_theme_font_size_override("font_size", 15)
	heading.add_theme_color_override("font_color", Slab.MAGENTA)
	_column.add_child(heading)


func _line(text: String) -> void:
	var label := Label.new()
	label.text = text
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.add_theme_font_size_override("font_size", 17)
	label.add_theme_color_override("font_color", Slab.CREAM)
	_column.add_child(label)


func _pair(word: String, means: String) -> void:
	"""A word and what it means, laid out like a stat on an item's card"""
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)

	var left := Label.new()
	left.text = word
	left.custom_minimum_size = Vector2(150, 0)
	left.add_theme_font_size_override("font_size", 17)
	left.add_theme_color_override("font_color", Slab.MUTED)
	row.add_child(left)

	var right := Label.new()
	right.text = means
	right.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	right.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	right.add_theme_font_size_override("font_size", 17)
	right.add_theme_color_override("font_color", Slab.CREAM)
	row.add_child(right)

	_column.add_child(row)


func _zone(which: String, means: String) -> void:
	"""One of the two zones, in the shape and colour the rack draws it"""
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)

	var mark := Label.new()
	mark.text = "★" if which == "star" else "◆"
	mark.custom_minimum_size = Vector2(150, 0)
	mark.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	mark.add_theme_font_size_override("font_size", 22)
	mark.add_theme_color_override("font_color",
		AuraOverlay.STAR if which == "star" else AuraOverlay.DIAMOND)
	row.add_child(mark)

	var says := Label.new()
	says.text = means
	says.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	says.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	says.add_theme_font_size_override("font_size", 17)
	says.add_theme_color_override("font_color", Slab.CREAM)
	row.add_child(says)

	_column.add_child(row)


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_cancel"):
		queue_free()
		get_viewport().set_input_as_handled()
