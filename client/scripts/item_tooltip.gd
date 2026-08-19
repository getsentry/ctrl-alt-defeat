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
@onready var size_label = $MarginContainer/VBoxContainer/Stats/SizeRow/SizeLabel
@onready var price_label = $MarginContainer/VBoxContainer/Stats/PriceRow/PriceLabel
@onready var special_label = $MarginContainer/VBoxContainer/SpecialLabel
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
	_set_row(size_label, _squares(item_data), item_data.shape.size() > 1)
	_set_row(price_label, _asking_price(item_data), show_price)

	special_label.text = item_data.special_effect
	special_label.visible = item_data.special_effect != ""

	# The description is the server's own sentence about the item, and for most
	# items it just reads back the rows above it. It earns its place only when
	# there are no rows to read.
	description_label.text = item_data.description
	description_label.visible = item_data.description != "" \
		and not (acts or special_label.visible)

	info_label.text = _identity(item_data)
	info_label.visible = info_label.text != ""

	# The rules divide the card into parts, so one with nothing on either side
	# of it is a line across an empty box.
	top_rule.visible = _has_body()
	foot_rule.visible = _has_body() and info_label.visible


func _has_body() -> bool:
	"""Whether anything sits between the name and the footer"""
	for row in stats.get_children():
		if row.visible:
			return true
	return special_label.visible or description_label.visible


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


func _squares(item_data: APITypes.Item) -> String:
	"""How much room the item takes up, in squares"""
	var count: int = item_data.shape.size()
	return "%d squares" % count if count != 1 else "1 square"


func _identity(item_data: APITypes.Item) -> String:
	"""What the item is: its rarity and its kind, as the footer reads it.

	Common is what most things are, so naming it says nothing. Anything rarer
	is worth the words.
	"""
	var parts: Array[String] = []
	if item_data.category:
		parts.append(item_data.category.capitalize())
	if item_data.rarity and item_data.rarity != "common":
		parts.append(item_data.rarity.capitalize())
	return " • ".join(parts)


func _wear_rarity(accent: Color) -> void:
	"""Edge the card in the colour of what it holds"""
	var style: StyleBoxFlat = get_theme_stylebox("panel").duplicate()
	style.border_color = Color(accent, 0.85)
	add_theme_stylebox_override("panel", style)
