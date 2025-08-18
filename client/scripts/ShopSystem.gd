extends HBoxContainer
class_name ShopSystem

signal item_purchased(item: Dictionary)
signal shop_refreshed()

const SHOP_SLOTS = 5
const SLOT_SIZE = Vector2(180, 200)

var shop_items: Array = []
var shop_slots: Array[Control] = []
var current_gold: int = 0

func _ready():
	theme_override_constants/separation = 15
	_setup_shop_slots()

func _setup_shop_slots():
	for i in range(SHOP_SLOTS):
		var slot = _create_shop_slot(i)
		shop_slots.append(slot)
		add_child(slot)

func _create_shop_slot(index: int) -> Control:
	var slot_container = Panel.new()
	slot_container.custom_minimum_size = SLOT_SIZE
	slot_container.set_meta("slot_index", index)

	var style = StyleBoxFlat.new()
	style.bg_color = Color(0.15, 0.15, 0.2, 0.95)
	style.border_color = Color(0.5, 0.5, 0.6, 1.0)
	style.set_border_width_all(2)
	style.corner_radius_top_left = 8
	style.corner_radius_top_right = 8
	style.corner_radius_bottom_left = 8
	style.corner_radius_bottom_right = 8
	slot_container.add_theme_stylebox_override("panel", style)

	var content = VBoxContainer.new()
	content.add_theme_constant_override("separation", 5)
	content.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	content.set_offsets_preset(Control.PRESET_FULL_RECT)
	content.set_margins_preset(Control.PRESET_FULL_RECT)
	content.add_theme_constant_override("margin_left", 10)
	content.add_theme_constant_override("margin_top", 10)
	content.add_theme_constant_override("margin_right", 10)
	content.add_theme_constant_override("margin_bottom", 10)
	slot_container.add_child(content)

	return slot_container

func display_shop(items: Array, gold: int):
	shop_items = items
	current_gold = gold

	for i in range(SHOP_SLOTS):
		_update_shop_slot(i)

func _update_shop_slot(index: int):
	if index >= shop_slots.size():
		return

	var slot = shop_slots[index]
	var content = slot.get_child(0) as VBoxContainer

	# Clear existing content
	for child in content.get_children():
		child.queue_free()

	if index < shop_items.size() and shop_items[index] != null:
		var item = shop_items[index]
		_populate_shop_slot(content, item, index)
	else:
		_show_empty_slot(content)

func _populate_shop_slot(content: VBoxContainer, item: Dictionary, index: int):
	# Item name
	var name_label = Label.new()
	name_label.text = item.get("name", "Unknown Item")
	name_label.add_theme_font_size_override("font_size", 14)
	name_label.add_theme_color_override("font_color", _get_rarity_color(item.get("rarity", "common")))
	name_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	content.add_child(name_label)

	# Category and tier
	var category_label = Label.new()
	var category = item.get("category", "")
	var tier = item.get("tier", 1)
	category_label.text = "%s (T%d)" % [category.capitalize(), tier]
	category_label.add_theme_font_size_override("font_size", 11)
	category_label.modulate = Color(0.8, 0.8, 0.8)
	content.add_child(category_label)

	# Spacer
	var spacer = Control.new()
	spacer.custom_minimum_size.y = 5
	content.add_child(spacer)

	# Stats
	if item.get("min_damage", 0) > 0:
		var damage_label = Label.new()
		damage_label.text = "Damage: %d-%d" % [item.get("min_damage"), item.get("max_damage")]
		damage_label.add_theme_font_size_override("font_size", 12)
		damage_label.modulate = Color(1.0, 0.6, 0.6)
		content.add_child(damage_label)

	if item.get("cooldown", 0) > 0:
		var cooldown_label = Label.new()
		cooldown_label.text = "Cooldown: %.1fs" % item.get("cooldown")
		cooldown_label.add_theme_font_size_override("font_size", 11)
		cooldown_label.modulate = Color(0.8, 0.8, 1.0)
		content.add_child(cooldown_label)

	if item.get("cpu_cost", 0) > 0:
		var cpu_label = Label.new()
		cpu_label.text = "CPU: %d" % item.get("cpu_cost")
		cpu_label.add_theme_font_size_override("font_size", 11)
		cpu_label.modulate = Color(0.8, 1.0, 0.8)
		content.add_child(cpu_label)

	if item.get("special_effect", "") != "":
		var special_label = Label.new()
		special_label.text = item.get("special_effect")
		special_label.add_theme_font_size_override("font_size", 10)
		special_label.modulate = Color(1.0, 1.0, 0.6)
		special_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		content.add_child(special_label)

	# Add flexible spacer to push button to bottom
	var flex_spacer = Control.new()
	flex_spacer.size_flags_vertical = Control.SIZE_EXPAND_FILL
	content.add_child(flex_spacer)

	# Cost and buy button container
	var button_container = VBoxContainer.new()
	button_container.add_theme_constant_override("separation", 5)
	content.add_child(button_container)

	# Cost
	var cost = item.get("cost", 0)
	var cost_label = Label.new()
	cost_label.text = "Cost: %d Gold" % cost
	cost_label.add_theme_font_size_override("font_size", 13)
	if cost > current_gold:
		cost_label.modulate = Color(1.0, 0.4, 0.4)
	else:
		cost_label.modulate = Color(1.0, 1.0, 0.5)
	cost_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	button_container.add_child(cost_label)

	# Buy button
	var buy_button = Button.new()
	buy_button.text = "Buy"
	buy_button.custom_minimum_size.y = 30
	buy_button.disabled = cost > current_gold
	buy_button.pressed.connect(_on_buy_pressed.bind(item, index))
	button_container.add_child(buy_button)

	# Update slot style based on rarity
	var slot = shop_slots[index]
	var style = slot.get_theme_stylebox("panel") as StyleBoxFlat
	if style:
		var new_style = style.duplicate() as StyleBoxFlat
		new_style.border_color = _get_rarity_color(item.get("rarity", "common"))
		new_style.border_color.a = 0.8
		slot.add_theme_stylebox_override("panel", new_style)

func _show_empty_slot(content: VBoxContainer):
	var empty_label = Label.new()
	empty_label.text = "Empty Slot"
	empty_label.add_theme_font_size_override("font_size", 14)
	empty_label.modulate = Color(0.5, 0.5, 0.5)
	empty_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	empty_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	empty_label.size_flags_vertical = Control.SIZE_EXPAND_FILL
	content.add_child(empty_label)

func _get_rarity_color(rarity: String) -> Color:
	match rarity:
		"common":
			return Color(0.8, 0.8, 0.8)
		"uncommon":
			return Color(0.4, 0.9, 0.4)
		"rare":
			return Color(0.4, 0.6, 1.0)
		"epic":
			return Color(0.8, 0.4, 1.0)
		"legendary":
			return Color(1.0, 0.7, 0.3)
		"godly":
			return Color(1.0, 0.3, 0.3)
		_:
			return Color.WHITE

func _on_buy_pressed(item: Dictionary, slot_index: int):
	if item.get("cost", 0) <= current_gold:
		# Clear the slot
		shop_items[slot_index] = null
		_update_shop_slot(slot_index)

		# Emit purchase signal
		item_purchased.emit(item)

func refresh_shop(new_items: Array, gold: int):
	display_shop(new_items, gold)
	shop_refreshed.emit()

func update_gold(gold: int):
	current_gold = gold
	# Update button states
	for i in range(shop_items.size()):
		if shop_items[i] != null:
			_update_shop_slot(i)
