extends SceneTree

# A scratch tool: draws the shop screen with arcs, a glow and a progress label,
# saves a picture of it and quits. Not a test -- it is how a person checks that
# the effect looks like an effect.

const APITypes = preload("res://scripts/api_types.gd")

var ui: Control
var state: Node  # the GameStateManager autoload, by name: a script run
# with --script cannot see the autoloads by their global identifier.
var frames := 0
var pointer := Vector2.ZERO
var shot_to := "user://combining.png"
# SHOW=merge plays the merge instead, and takes the picture partway through it.
var showing := OS.get_environment("SHOW")
var shoot_at := 60


func _initialize() -> void:
	var where := OS.get_environment("SHOT_TO")
	if where != "":
		shot_to = where

	state = root.get_node("GameStateManager")
	state.start_new_game()
	state.gold = 40
	state.save_inventory_state([], [
		_container("container_a", [2, 3]),
		_container("container_b", [4, 3]),
		_container("container_c", [6, 3]),
	])

	ui = load("res://scenes/UnifiedGridUI.tscn").instantiate()
	root.add_child(ui)


func _process(_delta: float) -> bool:
	frames += 1
	if frames == 5:
		if showing == "merge":
			_set_a_merge_going()
		else:
			_set_the_scene()
	if frames > 5 and showing != "merge":
		ui.refresh_combining(pointer)
	if frames == 30:
		print("overlay: ", ui.combining_overlay)
		print("source: ", ui.combining_source(pointer))
		print("arcs: ", ui.combining_overlay.arcs())
		print("glowing: ", ui.combining_overlay.glowing())
		print("label: ", ui.combining_overlay.label_text())
		print("on screen: ", ui.items_on_screen().size())
		print("overlay rect: ", ui.combining_overlay.get_global_rect(),
			" index ", ui.combining_overlay.get_index(),
			" of ", ui.get_child_count())
	if frames == shoot_at:
		var image := root.get_viewport().get_texture().get_image()
		image.save_png(shot_to)
		print("saved ", ProjectSettings.globalize_path(shot_to))
		return true
	return false


func _set_a_merge_going() -> void:
	"""The rack as it fought, and the merge that happened when it stopped."""
	# AT says which frame of the merge to catch. At sixty frames a second:
	# 0-33 the items rattle, 34-58 they fly in, 60 the flash, then the result
	# stands up with rings struck round it.
	var frame := OS.get_environment("AT")
	shoot_at = 5 + (int(frame) if frame != "" else 60)
	state.combining.catalogue = APITypes.CombiningCatalogue.new({
		"partners": {},
		"names": {
			"blue_sage_collar": "Amethyst Collar",
			"serverless_function": "Serverless Function",
		},
	})
	ui.set_process(false)

	var fought_with := {
		"items": [
			_item("collar", "neural_link_collar", "neural_link_collar", [2, 3]),
			_item("booster", "cpu_booster", "cpu_booster", [3, 3]),
			_item("cat", "maneki_neko", "maneki_neko", [4, 3]),
			_item("rig", "crypto_mining_rig", "crypto_mining_rig", [5, 3]),
		],
		"servers": [
			_container("container_a", [2, 3]),
			_container("container_b", [4, 3]),
			_container("container_c", [6, 3]),
		],
	}
	state.rack_that_fought = APITypes.InventoryState.new(fought_with)
	state.save_inventory_state(
		[_item("made", "blue_sage_collar", "blue_sage_collar", [2, 3]),
		 _item("cat", "maneki_neko", "maneki_neko", [4, 3]),
		 _item("done", "serverless_function", "serverless_function", [5, 3])],
		fought_with["servers"])

	var combinations: Array[APITypes.Combination] = []
	combinations.append(APITypes.Combination.new({
		"made": "blue_sage_collar", "made_id": "made",
		"consumed": [
			_item("collar", "neural_link_collar", "neural_link_collar", [2, 3]),
			_item("booster", "cpu_booster", "cpu_booster", [3, 3])],
		"kept": [], "freed": [[2, 3], [3, 3]], "position": [2, 3]}))
	combinations.append(APITypes.Combination.new({
		"made": "serverless_function", "made_id": "done",
		"consumed": [
			_item("rig", "crypto_mining_rig", "crypto_mining_rig", [5, 3])],
		"kept": [_item("cat", "maneki_neko", "maneki_neko", [4, 3])],
		"freed": [[5, 3]], "position": [5, 3]}))
	state.combinations_to_play = combinations

	ui.call_deferred("play_combining")


func _set_the_scene() -> void:
	state.combining.catalogue = APITypes.CombiningCatalogue.new({
		"partners": {
			"hero_sword": ["whetstone"],
			"whetstone": ["hero_sword", "whetstone"],
			"neural_link_collar": ["cpu_booster"],
			"cpu_booster": ["neural_link_collar"],
		},
		"names": {
			"hero_longsword": "Long Poll",
			"blue_sage_collar": "Amethyst Collar",
			"serverless_function": "Serverless Function",
		},
	})

	ui.inventory_grid.load_inventory_state(APITypes.InventoryState.new({
		"items": [
			_item("sword", "hero_sword", "null_blade", [2, 3]),
			_item("stone", "whetstone", "whetstone", [3, 4]),
			_item("collar", "neural_link_collar", "neural_link_collar", [4, 3]),
			_item("booster", "cpu_booster", "cpu_booster", [5, 3]),
		],
		"servers": [
			_container("container_a", [2, 3]),
			_container("container_b", [4, 3]),
			_container("container_c", [6, 3]),
		],
	}))

	var shop: Array[APITypes.Item] = [
		APITypes.Item.new(_item("shelf_stone", "whetstone", "whetstone", [0, 0])),
	]
	ui._display_shop_items(shop)

	var chest: Array[APITypes.Item] = []
	chest.append(APITypes.Item.new(
		_item("chest_stone", "whetstone", "whetstone", [0, 0])))
	state.inventory_storage = chest
	ui.load_storage()

	# Two of the four are about to combine, and the sword is on its way to a
	# Long Poll.
	state.note_pending([
		APITypes.Pending.new({
			"makes": "blue_sage_collar", "have": 2, "need": 2,
			"ingredients": ["collar", "booster"], "catalysts": [], "missing": []}),
		APITypes.Pending.new({
			"makes": "hero_longsword", "have": 2, "need": 3,
			"ingredients": ["sword", "stone"], "catalysts": [],
			"missing": ["whetstone"]}),
	])

	# The pointer rests on the sword, so the arcs come from it.
	pointer = ui.inventory_grid.item_visual("sword").get_global_rect().get_center()
	ui.set_process(false)


func _item(id: String, item_type: String, slug: String, at: Array) -> Dictionary:
	return {
		"id": id, "item_type": item_type, "name": item_type.capitalize(),
		"slug": slug, "category": "problem", "rarity": "common",
		"cost": 4, "price": 4, "sell_value": 2, "on_sale": false,
		"is_container": false, "shape": [[0, 0]], "star": [], "diamond": [],
		"anchors": [], "effects": [], "color": "#BE0032", "pattern": "solid",
		"min_damage": 0, "max_damage": 0, "min_heal": 0, "max_heal": 0,
		"block_amount": 0, "cooldown": 0.0, "cpu_cost": 0.0,
		"position": at, "rotation": 0,
	}


func _container(id: String, at: Array) -> Dictionary:
	var data := _item(id, "standard_vm", "standard_vm", at)
	data["is_container"] = true
	data["category"] = "container"
	data["shape"] = [[0, 0], [1, 0], [0, 1], [1, 1]]
	return data
