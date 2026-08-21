extends PanelContainer
class_name ItemTooltip

## The card shown when the pointer rests on an item.
##
## It is the only place the player reads an item's numbers, so every stat it
## has gets a row of its own -- caption on the left, value on the right -- and
## every stat it does not have leaves no gap behind. What the item *is* goes in
## the footer, so the top of the card is always the name and the numbers.

@onready var name_label = $MarginContainer/VBoxContainer/NameLabel
@onready var info_label = $MarginContainer/VBoxContainer/InfoLabel
@onready var stats = $MarginContainer/VBoxContainer/Stats
@onready var damage_label = $MarginContainer/VBoxContainer/Stats/DamageRow/DamageLabel
@onready var heal_label = $MarginContainer/VBoxContainer/Stats/HealRow/HealLabel
@onready var block_label = $MarginContainer/VBoxContainer/Stats/BlockRow/BlockLabel
@onready var cooldown_label = $MarginContainer/VBoxContainer/Stats/CooldownRow/CooldownLabel
@onready var cpu_label = $MarginContainer/VBoxContainer/Stats/CpuRow/CpuLabel
@onready var price_label = $MarginContainer/VBoxContainer/Stats/PriceRow/PriceLabel
@onready var description_label = $MarginContainer/VBoxContainer/DescriptionLabel
@onready var top_rule = $MarginContainer/VBoxContainer/TopRule
@onready var foot_rule = $MarginContainer/VBoxContainer/FootRule

var pending_item_data: APITypes.Item = null

## Whether to say what the shop would charge. Only a shelf sets this: an item
## already owned has no price, and showing one would read as a second cost.
var show_price: bool = false

func _ready():
	# If we have pending data, set it up now
	if pending_item_data:
		_setup_tooltip_internal(pending_item_data)
		pending_item_data = null

# Rarity colors
const RARITY_COLORS = {
	"common": Color(0.88, 0.9, 1.0),
	"uncommon": Color(0.3, 1.0, 0.3),
	"rare": Color(0.3, 0.6, 1.0),
	"epic": Color(0.7, 0.3, 1.0),
	"legendary": Color(1.0, 0.5, 0.0),
	"godly": Color(1.0, 0.2, 0.2)
}

func setup_tooltip(item_data: APITypes.Item):
	"""Configure the tooltip with item data"""
	# If nodes aren't ready yet, store the data for later
	if not is_node_ready():
		pending_item_data = item_data
		return

	_setup_tooltip_internal(item_data)


func _set_row(value_label: Label, text: String, shown: bool) -> void:
	"""Show a stat row and what it says, or take the whole row away.

	The caption and the value are one thing, so the row is hidden with the
	label rather than left behind as an empty line.
	"""
	value_label.visible = shown
	value_label.get_parent().visible = shown
	if shown:
		value_label.text = text


func _setup_tooltip_internal(item_data: APITypes.Item):
	"""Internal function to actually set up the tooltip"""
	var rarity = item_data.rarity
	var accent: Color = RARITY_COLORS.get(rarity, Color.WHITE)

	name_label.text = item_data.name
	name_label.add_theme_color_override("font_color", accent)
	_wear_rarity(accent)

	_set_row(damage_label, _range(item_data.min_damage, item_data.max_damage),
		item_data.min_damage > 0 or item_data.max_damage > 0)
	_set_row(heal_label, _range(item_data.min_heal, item_data.max_heal) + " HP",
		item_data.min_heal > 0 or item_data.max_heal > 0)
	_set_row(block_label, "%d damage" % item_data.block_amount,
		item_data.block_amount > 0)
	# A cooldown on an item that does nothing is not a stat the player can use,
	# so it only shows next to the thing it paces.
	var acts: bool = damage_label.visible or heal_label.visible or block_label.visible
	_set_row(cooldown_label, "%.1fs" % item_data.cooldown, acts and item_data.cooldown > 0)
	_set_row(cpu_label, _tidy(item_data.cpu_cost), item_data.cpu_cost > 0)
	_set_row(price_label, _asking_price(item_data), show_price)

	# Everything the item does, a line at a time, as the server worked it out
	# from the item's own effects. The rows above are the headline numbers; a
	# build is decided on the rest, and there used to be nowhere to read it.
	description_label.text = _coloured(item_data.effects)
	description_label.visible = not item_data.effects.is_empty()

	info_label.text = _identity(item_data)
	info_label.visible = info_label.text != ""

	# The rules divide the card into parts, so one with nothing on either side
	# of it is a line across an empty box.
	top_rule.visible = _has_body()
	foot_rule.visible = _has_body() and info_label.visible


func _process(_delta: float) -> void:
	"""Stand at the size of what the card holds, and nothing more.

	A wrapping label works out how tall it is from how wide it is, and it only
	learns its width when a layout pass reaches it -- a pass or two after the
	card was put on screen. Measured before that reached it, the text counted
	as one word a line and the card came out several times taller than what it
	holds, with the empty space hanging below the footer.

	So the card asks every frame instead of counting them. The answer settles
	within a frame or two of appearing and then stops changing, and whatever
	placed the card follows it there through `resized`.
	"""
	var wanted := get_combined_minimum_size()
	if not size.is_equal_approx(wanted):
		size = wanted


## What marks a status out in a line: a colour, rather than capitals. The
## server says which of the ten a name is, since it is the one that knows
## which are worth having; which colour that becomes is the card's business.
const BUFF_COLOUR := "8fe0a0"
const DEBUFF_COLOUR := "ff9a9a"

## And the two zones, which are drawn on the board as well as named in the
## words. The colours are the overlay's own, so a line saying "for each star
## item" is the colour of the squares the player is looking at, and the shape
## in front of it is the shape drawn in them.
const AuraOverlay = preload("res://scripts/aura_overlay.gd")
const STAR_MARK := "★"
const DIAMOND_MARK := "◆"


func _coloured(said: Array) -> String:
	"""Everything the item does, with what it names picked out.

	A status by the kind of status it is, and a zone by the shape and colour
	the board draws it in. The marks come from the server, which knows what a
	name is; what they are drawn as is the card's business.
	"""
	var text: String = "\n".join(said)
	var marks := {
		"buff": "[color=#%s]" % BUFF_COLOUR,
		"debuff": "[color=#%s]" % DEBUFF_COLOUR,
		"star": "[color=#%s]%s " % [AuraOverlay.STAR.to_html(false), STAR_MARK],
		"diamond": "[color=#%s]%s " % [
			AuraOverlay.DIAMOND.to_html(false), DIAMOND_MARK],
	}
	for mark in marks:
		text = text.replace("[%s]" % mark, marks[mark])
		text = text.replace("[/%s]" % mark, "[/color]")
	return text


func _has_body() -> bool:
	"""Whether anything sits between the name and the footer"""
	for row in stats.get_children():
		if row.visible:
			return true
	return description_label.visible


func _asking_price(item_data: APITypes.Item) -> String:
	"""What the shop wants for it, and what it wanted before any sale.

	The shelf shows the one number being charged. How big a cut that is only
	matters while the player is deciding, which is when the card is out.
	"""
	if item_data.on_sale and item_data.cost > item_data.price:
		return "%d gold (was %d)" % [item_data.price, item_data.cost]
	return "%d gold" % item_data.price


func _range(low: float, high: float) -> String:
	"""A span of numbers, or the single number when there is no span.

	An item that always deals three damage is not rolling anything, and "3-3"
	invites the player to look for the difference between the two threes.
	"""
	if is_equal_approx(low, high):
		return _tidy(low)
	return "%s-%s" % [_tidy(low), _tidy(high)]


func _tidy(number: float) -> String:
	"""A number as a player would write it, with no tail of zeroes.

	Every number the server sends is a float, so a CPU cost of two arrives as
	2.0 and would read as though halves were possible.
	"""
	if is_equal_approx(number, roundf(number)):
		return str(int(roundf(number)))
	return str(snappedf(number, 0.1))


func _identity(item_data: APITypes.Item) -> String:
	"""What the item is: its rarity, its kind, and the traits it carries.

	Common is what most things are, so naming it says nothing. Anything rarer
	is worth the words.

	The traits are here because half the catalogue asks for them -- "gain 3
	regenerating for each holy star item" is a line the player cannot act on
	without knowing which of their items are holy. The category is one of the
	things an aura can ask for as well, so the footer is the whole list of
	what this item answers to.
	"""
	var parts: Array[String] = []
	if item_data.category:
		parts.append(item_data.category.capitalize())
	if item_data.rarity and item_data.rarity != "common":
		parts.append(item_data.rarity.capitalize())
	for trait_name in item_data.traits:
		parts.append(trait_name)
	return " • ".join(parts)


func _wear_rarity(accent: Color) -> void:
	"""Edge the card in the colour of what it holds"""
	var style: StyleBoxFlat = get_theme_stylebox("panel").duplicate()
	style.border_color = Color(accent, 0.85)
	add_theme_stylebox_override("panel", style)
