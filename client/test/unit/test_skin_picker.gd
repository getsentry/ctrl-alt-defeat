extends GutTest

## The picker itself (GDD 11).
##
## test_skins.gd covers the registry, which is why a parse error in this file
## once shipped a CHANGE SKIN button that did nothing: nothing loaded the
## script. These tests load it and press it.

const PICKER := "res://scripts/skin_picker.gd"
const SETTINGS := "user://player_settings.cfg"

var _kept := ""
var _existed := false


func before_each() -> void:
	# The whole settings file, verbatim, because it is shared with the player
	# name and the signed-in account.
	_existed = FileAccess.file_exists(SETTINGS)
	if _existed:
		_kept = FileAccess.get_file_as_string(SETTINGS)


func after_each() -> void:
	if _existed:
		var file := FileAccess.open(SETTINGS, FileAccess.WRITE)
		file.store_string(_kept)
		file.close()
	elif FileAccess.file_exists(SETTINGS):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(SETTINGS))
	_kept = ""


func _opened() -> Control:
	var picker: Control = (load(PICKER) as GDScript).new()
	add_child_autofree(picker)
	await get_tree().process_frame
	return picker


func _cards_of(picker: Control) -> Array:
	"""Every card button in the picker, in the order they are shown."""
	var found := []
	var waiting: Array[Node] = [picker]
	while not waiting.is_empty():
		var node: Node = waiting.pop_front()
		if node is Button and node.tooltip_text != "":
			found.append(node)
		for child in node.get_children():
			waiting.append(child)
	return found


func test_the_script_loads() -> void:
	# On its own this would have caught the button doing nothing.
	assert_not_null(load(PICKER), "skin_picker.gd did not load")


func test_it_opens_with_a_card_for_every_skin() -> void:
	var picker := await _opened()
	assert_eq(_cards_of(picker).size(), Skins.ALL.size())


func test_pressing_a_card_changes_the_skin() -> void:
	Skins.choose("classic")
	var picker := await _opened()
	for card in _cards_of(picker):
		if card.tooltip_text == "NEKO":
			card.pressed.emit()
			break
	assert_eq(Skins.chosen(), "neko", "pressing NEKO should choose it")


func test_pressing_a_card_says_so() -> void:
	Skins.choose("classic")
	var picker := await _opened()
	watch_signals(picker)
	for card in _cards_of(picker):
		if card.tooltip_text == "DOT MATRIX":
			card.pressed.emit()
			break
	assert_signal_emitted_with_parameters(picker, "picked", ["dotmatrix"])


func test_pressing_the_one_already_chosen_says_nothing() -> void:
	# Nothing changed, so nothing behind the picker needs redrawing.
	Skins.choose("og")
	var picker := await _opened()
	watch_signals(picker)
	for card in _cards_of(picker):
		if card.tooltip_text == "OG":
			card.pressed.emit()
			break
	assert_signal_not_emitted(picker, "picked")


func test_it_opens_showing_what_is_already_chosen() -> void:
	Skins.choose("nightshift")
	var picker := await _opened()
	var labels := []
	var waiting: Array[Node] = [picker]
	while not waiting.is_empty():
		var node: Node = waiting.pop_front()
		if node is Label:
			labels.append(node.text)
		for child in node.get_children():
			waiting.append(child)
	assert_has(labels, "NIGHT SHIFT", "the chosen skin should be named")
