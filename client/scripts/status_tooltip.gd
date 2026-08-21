extends PanelContainer

## What a buff or a debuff on a fighter is doing, and what all of it is doing.
##
## The chips beside each fighter read "regenerating x6" and left the player to
## guess what six of them were worth. Godot's own tooltip was tried first: it
## waits half a second before it appears, it is one run of plain text, and it
## is drawn in a style that belongs to no other part of this game. A card, the
## same card the shop draws for an item, arrives the moment the pointer does.
##
## It reads in the order the question is asked: which status this is, what one
## stack of it does, what is worth knowing beyond the number, and only then
## what the whole stack comes to. The last line is the one a player looked up
## the chip for; it is last because it means nothing until the ones above it
## have been read.
##
## Every word of it is the server's, out of `/catalogue/statuses`. The rules
## are the server's -- what a stack is worth, and what a stack is worth six
## times -- and a copy of them here would go on saying 2% the day after it
## stopped being 2%.

## Green for something a fighter wants, red for something done to them. The
## same two the chips themselves are drawn in, so a card is plainly about the
## chip under the pointer.
const BUFF := Color(0.4, 1.0, 0.6)
const DEBUFF := Color(1.0, 0.45, 0.5)

## How far the card keeps from the edge of the window, and from the chip it
## belongs to.
const EDGE := 12.0
const CLEARANCE := 10.0

@onready var name_label: Label = $MarginContainer/VBoxContainer/NameRow/NameLabel
@onready var count_label: Label = $MarginContainer/VBoxContainer/NameRow/CountLabel
@onready var kind_label: Label = $MarginContainer/VBoxContainer/KindLabel
@onready var each_label: Label = $MarginContainer/VBoxContainer/EachLabel
@onready var detail_label: Label = $MarginContainer/VBoxContainer/DetailLabel
@onready var total_label: Label = $MarginContainer/VBoxContainer/TotalLabel
@onready var foot_rule: HSeparator = $MarginContainer/VBoxContainer/FootRule


func _process(_delta: float) -> void:
	"""Stand at the size of what the card holds, and nothing more.

	A wrapping label works out how tall it is from how wide it is, and it only
	learns its width when a layout pass reaches it -- a pass or two after the
	card was put on screen. Measured before that reached it, the text counts as
	one word a line: this card came out three hundred wide and four thousand
	tall, hanging off the top of the screen with nothing readable on it.

	So it asks every frame instead of counting them, the same as the item card
	does. The answer settles within a frame or two and then stops changing, and
	whatever placed the card follows it there through `resized`.
	"""
	var wanted := get_combined_minimum_size()
	if not size.is_equal_approx(wanted):
		size = wanted


## Fill the card in for this many stacks of this status.
##
## `rule` is one entry of the status catalogue, as the server sends it. Says
## whether there was anything to draw: a status nothing is known about has no
## card, rather than a card with nothing on it.
func say(rule: Dictionary, stacks: int) -> bool:
	if rule.is_empty() or str(rule.get("one", "")) == "":
		return false

	var tint: Color = DEBUFF if str(rule.get("kind", "")) == "debuff" else BUFF
	name_label.text = str(rule["shown"]).capitalize()
	name_label.add_theme_color_override("font_color", tint)

	count_label.text = "x%d" % stacks if stacks > 1 else ""
	count_label.visible = stacks > 1

	kind_label.text = "Debuff" if str(rule.get("kind", "")) == "debuff" else "Buff"

	each_label.text = str(rule["one"])
	detail_label.text = str(rule.get("detail", ""))
	detail_label.visible = detail_label.text != ""

	# What the whole stack comes to. Only where there is more than one of them
	# and the status is worth a number -- "all 1 of them" is the line above
	# said twice, and credits do not add up to anything.
	var each := int(rule.get("each", 0))
	var many := str(rule.get("many", ""))
	var totals := stacks > 1 and each > 0 and many != ""
	if totals:
		# The only arithmetic on this side. What one stack is worth came from
		# the server, and so did the sentence it goes in.
		total_label.text = "All %d: %s" % [
			stacks, many.replace("{total}", str(each * stacks))]
		total_label.add_theme_color_override("font_color", tint)
	total_label.visible = totals
	foot_rule.visible = totals

	return true


## Stand beside the chip this is about, and stay on the screen.
##
## To the side of it, not above: the chips sit at the bottom of the plate that
## holds both fighters' health and CPU, and a card above one covers exactly the
## numbers a player is reading it against. To the left where there is room,
## since the player's own chips are on the left half of that plate and the room
## beside them is empty.
func stand_beside(chip: Control) -> void:
	if not is_inside_tree() or not is_instance_valid(chip):
		return
	var room := get_viewport_rect().size
	var against := chip.get_global_rect()

	var left := against.position.x - size.x - CLEARANCE
	if left < EDGE:
		left = against.end.x + CLEARANCE
	# Level with the chip rather than centred on it, so a tall card grows
	# downwards into the empty space under the plate instead of upwards over
	# the fighters' numbers.
	position = Vector2(
		clampf(left, EDGE, room.x - size.x - EDGE),
		clampf(against.get_center().y - size.y / 2.0, EDGE,
			room.y - size.y - EDGE))
