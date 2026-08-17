extends Panel
class_name ItemTooltip

@onready var name_label = $MarginContainer/VBoxContainer/NameLabel
@onready var info_label = $MarginContainer/VBoxContainer/InfoLabel
@onready var cost_label = $MarginContainer/VBoxContainer/CostLabel
@onready var damage_label = $MarginContainer/VBoxContainer/DamageLabel
@onready var heal_label = $MarginContainer/VBoxContainer/HealLabel
@onready var block_label = $MarginContainer/VBoxContainer/BlockLabel
@onready var special_label = $MarginContainer/VBoxContainer/SpecialLabel
@onready var description_label = $MarginContainer/VBoxContainer/DescriptionLabel

var pending_item_data: APITypes.Item = null

func _ready():
	# If we have pending data, set it up now
	if pending_item_data:
		_setup_tooltip_internal(pending_item_data)
		pending_item_data = null

# Rarity colors
const RARITY_COLORS = {
	"common": Color(1.0, 1.0, 1.0),
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

func _setup_tooltip_internal(item_data: APITypes.Item):
	"""Internal function to actually set up the tooltip"""
	# Get item properties
	var item_name = ""
	var category = ""
	var rarity = "common"
	var cost = 0
	var min_damage = 0
	var max_damage = 0
	var min_heal = 0
	var max_heal = 0
	var cooldown = 0.0
	var cpu_cost = 0
	var block_amount = 0
	var special_effect = ""
	var description = ""

	item_name = item_data.name
	category = item_data.category
	rarity = item_data.rarity
	cost = item_data.cost
	min_damage = item_data.min_damage
	max_damage = item_data.max_damage
	min_heal = item_data.min_heal
	max_heal = item_data.max_heal
	cooldown = item_data.cooldown
	cpu_cost = item_data.cpu_cost
	block_amount = item_data.block_amount
	special_effect = item_data.special_effect
	description = item_data.description

	# Set name with rarity color
	name_label.text = item_name
	name_label.add_theme_color_override("font_color", RARITY_COLORS.get(rarity, Color.WHITE))

	# Set category and rarity info
	var info_text = ""
	if category:
		info_text = category.capitalize()
	if rarity and rarity != "common":
		if info_text:
			info_text += " • "
		info_text += rarity.capitalize()

	if info_text:
		info_label.text = info_text
		info_label.visible = true
	else:
		info_label.visible = false

	# Set cost
	if cost > 0:
		cost_label.text = "Value: " + str(cost) + " gold"
		cost_label.visible = true
	else:
		cost_label.visible = false

	var has_effects = false

	# Set damage
	if min_damage > 0 or max_damage > 0:
		var damage_text = "⚔️ Damage: " + str(min_damage) + "-" + str(max_damage)
		if cooldown > 0:
			damage_text += " every " + str(cooldown) + "s"
		if cpu_cost > 0:
			damage_text += " (CPU: " + str(cpu_cost) + ")"
		damage_label.text = damage_text
		damage_label.visible = true
		has_effects = true
	else:
		damage_label.visible = false

	# Set heal
	if min_heal > 0 or max_heal > 0:
		var heal_text = "❤️ Heals: " + str(min_heal) + "-" + str(max_heal) + " HP"
		if cooldown > 0:
			heal_text += " every " + str(cooldown) + "s"
		heal_label.text = heal_text
		heal_label.visible = true
		has_effects = true
	else:
		heal_label.visible = false

	# Set block
	if block_amount > 0:
		block_label.text = "🛡️ Blocks: " + str(block_amount) + " damage"
		block_label.visible = true
		has_effects = true
	else:
		block_label.visible = false

	# Set special effect
	if special_effect:
		special_label.text = "✨ Special: " + special_effect
		special_label.visible = true
		has_effects = true
	else:
		special_label.visible = false

	# Set description (only if no effects)
	if description and not has_effects:
		description_label.text = description
		description_label.visible = true
	else:
		description_label.visible = false
