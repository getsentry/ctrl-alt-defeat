extends Control

## The screen where the player picks which Sentaur they look like (GDD 11).
##
## Built in code rather than as a scene, because it is one panel and a row of
## buttons and a .tscn for that is more to keep in step than it is worth.
##
## It is an overlay, not a screen of its own: it opens over the shop, the shop
## is still behind it, and picking is instant. There is no confirm step because
## there is nothing to confirm -- the choice costs nothing and shows itself
## immediately.

signal picked(id: String)

const CARD := Vector2(196, 236)
const CREAM := Color(0.949, 0.890, 0.769)
const MAGENTA := Color(1.0, 0.239, 0.745)
const MUTED := Color(0.541, 0.471, 0.620)

var _chosen := ""
var _cards: Array[Button] = []
var _preview: TextureRect
var _name: Label


func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	z_index = 100
	_chosen = Skins.chosen()

	var dim := ColorRect.new()
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	dim.color = Color(0.055, 0.039, 0.078, 0.88)
	add_child(dim)

	var panel := PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_CENTER)
	panel.add_theme_stylebox_override("panel", _slab(Color(0.110, 0.078, 0.157)))
	add_child(panel)

	var margin := MarginContainer.new()
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 40)
	panel.add_child(margin)

	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 18)
	margin.add_child(column)

	column.add_child(_heading("SENTAUR SELECT", 40, CREAM))

	_preview = TextureRect.new()
	_preview.custom_minimum_size = Vector2(340, 400)
	_preview.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_preview.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	column.add_child(_preview)

	_name = _heading("", 30, MAGENTA)
	column.add_child(_name)

	var rack := HBoxContainer.new()
	rack.add_theme_constant_override("separation", 12)
	rack.alignment = BoxContainer.ALIGNMENT_CENTER
	column.add_child(rack)

	for skin in Skins.ALL:
		var card := _card(skin)
		rack.add_child(card)
		_cards.append(card)

	var close := Button.new()
	close.text = "DONE"
	close.custom_minimum_size = Vector2(0, 62)
	close.size = Vector2(0, 62)
	Keycap.dress(close, 26)
	close.pressed.connect(queue_free)
	column.add_child(close)

	_show_chosen()


func _card(skin: Dictionary) -> Button:
	var button := Button.new()
	button.custom_minimum_size = CARD
	button.tooltip_text = skin["label"]
	button.pressed.connect(_pick.bind(skin["id"]))

	var inside := VBoxContainer.new()
	inside.set_anchors_preset(Control.PRESET_FULL_RECT)
	inside.mouse_filter = Control.MOUSE_FILTER_IGNORE
	inside.add_theme_constant_override("separation", 4)
	button.add_child(inside)

	var art := TextureRect.new()
	art.texture = load(skin["shop"])
	art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	art.size_flags_vertical = Control.SIZE_EXPAND_FILL
	art.mouse_filter = Control.MOUSE_FILTER_IGNORE
	inside.add_child(art)

	var label := Label.new()
	label.text = skin["label"]
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.add_theme_font_size_override("font_size", 17)
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	inside.add_child(label)

	return button


func _pick(id: String) -> void:
	if id == _chosen:
		return
	_chosen = id
	Skins.choose(id)
	_show_chosen()
	picked.emit(id)


func _show_chosen() -> void:
	var skin := Skins.by_id(_chosen)
	_preview.texture = load(skin["shop"])
	_name.text = skin["label"]
	for i in _cards.size():
		var lit: bool = Skins.ALL[i]["id"] == _chosen
		_cards[i].add_theme_stylebox_override(
			"normal", _slab(Color(0.153, 0.110, 0.220), MAGENTA if lit else Color(0.275, 0.220, 0.361), 3 if lit else 1))
		_cards[i].modulate = Color.WHITE if lit else Color(0.78, 0.74, 0.82)


func _heading(text: String, size: int, colour: Color) -> Label:
	var label := Label.new()
	label.text = text
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.add_theme_font_size_override("font_size", size)
	label.add_theme_color_override("font_color", colour)
	return label


func _slab(fill: Color, edge: Color = Color(0.275, 0.220, 0.361), width: int = 2) -> StyleBoxFlat:
	var box := StyleBoxFlat.new()
	box.bg_color = fill
	box.border_color = edge
	box.set_border_width_all(width)
	box.set_corner_radius_all(12)
	box.set_content_margin_all(8)
	return box


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_cancel"):
		queue_free()
		get_viewport().set_input_as_handled()
