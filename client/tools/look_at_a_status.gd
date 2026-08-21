extends SceneTree

# A scratch tool: draws the battle screen with buffs and debuffs on both
# fighters, puts the card up for one of them, saves a picture and quits. Not a
# test -- it is how a person checks that a card looks like a card.
#
#   godot --headless --path . -s tools/look_at_a_status.gd
#   STACKS=6 STATUS=optimized SHOT_TO=/tmp/card.png godot ... (as above)

const APITypes = preload("res://scripts/api_types.gd")

var screen: Control
var state: Node  # the GameStateManager autoload, by name
var frames := 0
var shot_to := "user://status_card.png"
var status := OS.get_environment("STATUS")
var stacks := int(OS.get_environment("STACKS"))


func _initialize() -> void:
	var where := OS.get_environment("SHOT_TO")
	if where != "":
		shot_to = where
	if status == "":
		status = "regenerating"
	if stacks <= 0:
		stacks = 6

	state = root.get_node("GameStateManager")
	state.start_new_game()
	state.status_rules = APITypes.StatusRules.new(_the_catalogue())

	state.last_battle_result = APITypes.BattleResult.new({
		"winner": 1, "duration": 10.0, "player1_quota": 80, "player2_quota": 80,
		"seed": 1,
		"actions": [{"timestamp": 0, "source": "system", "action": "battle_start",
			"player": 0, "target": null, "damage": null,
			"details": {"hp": [80, 80], "max_hp": [80, 80],
				"cpu": [2.0, 2.0], "max_cpu": [3.0, 3.0], "block": [12, 0]}}],
		"opponent_name": "AI Opponent", "opponent_type": "ai",
		"player_inventory": {"items": [], "servers": []},
		"enemy_inventory": {"items": [], "servers": []},
	})
	state.last_battle_events = state.last_battle_result.actions

	screen = load("res://scenes/BattleScreen.tscn").instantiate()
	root.add_child(screen)


## ALL=<file> draws a card for every status in that catalogue at once, laid out
## in a grid, so all ten can be read side by side. The file is what
## /catalogue/statuses answers with:
##
##   curl -s localhost:8082/catalogue/statuses > /tmp/statuses.json
##   ALL=/tmp/statuses.json SHOT_TO=/tmp/all.png godot --path . -s tools/look_at_a_status.gd
var every := OS.get_environment("ALL")


func _lay_them_all_out() -> void:
	var file := FileAccess.open(every, FileAccess.READ)
	if file == null:
		print("could not read ", every)
		return
	var catalogue = JSON.parse_string(file.get_as_text())
	file.close()

	var card_scene := load("res://scenes/StatusTooltip.tscn")
	var across := 0
	var down := 0
	for rule in catalogue["statuses"]:
		var card = card_scene.instantiate()
		root.add_child(card)
		# Six stacks, so every card shows its total line as well as its rule.
		card.say({
			"shown": rule["shown"], "kind": rule["kind"], "each": rule["each"],
			"one": rule["one"], "many": rule["many"],
			"detail": rule.get("detail", ""),
		}, 6)
		card.set_process(false)
		card.size = Vector2(300, card.get_combined_minimum_size().y)
		card.position = Vector2(24 + across * 324, 24 + down * 400)
		across += 1
		if across == 5:
			across = 0
			down += 1


## The rules the cards are filled from: whatever RULES or ALL points at, so a
## picture is of what the server really says, and a small fixture only when
## neither is given.
func _the_catalogue() -> Dictionary:
	var from := OS.get_environment("RULES")
	if from == "":
		from = OS.get_environment("ALL")
	if from != "":
		var file := FileAccess.open(from, FileAccess.READ)
		if file != null:
			var read = JSON.parse_string(file.get_as_text())
			file.close()
			if read is Dictionary:
				return read
		print("could not read ", from, ", using the fixture")
	return {"statuses": [

		{"status": "regenerating", "shown": "regenerating", "kind": "buff",
			"each": 1, "one": "Heals 1 every 2 seconds",
			"many": "Heals {total} every 2 seconds",
			"detail": "On its own clock, every two seconds, whatever your "
				+ "items are doing."},
		{"status": "optimized", "shown": "optimised", "kind": "buff",
			"each": 2, "one": "Items trigger 2% faster",
			"many": "Items trigger {total}% faster",
			"detail": "Everything you own comes round sooner. Speed-ups and "
				+ "slow-downs are added together rather than applied one "
				+ "after another, and the most either way is ten times."},
		{"status": "memory_leaked", "shown": "memory leak", "kind": "debuff",
			"each": 1, "one": "Takes 1 damage every 2 seconds",
			"many": "Takes {total} damage every 2 seconds",
			"detail": "On its own clock, every two seconds, whatever your "
				+ "items are doing. Nothing else in the battle has to happen "
				+ "for it to hurt."},
	]}


func _process(_delta: float) -> bool:
	frames += 1
	if every != "":
		if frames == 5:
			_lay_them_all_out()
		if frames == 20:
			var image := root.get_viewport().get_texture().get_image()
			image.save_png(shot_to)
			print("saved ", ProjectSettings.globalize_path(shot_to))
			return true
		return false
	if frames == 10:
		_put_some_statuses_on()
	if frames == 20:
		var chip = screen.hud._effects["player_buff"].get_child(0)
		screen.hud._explain(chip)
		var card = screen.hud._explaining
		print("card: ", card)
		if card != null:
			print("  name  : ", card.name_label.text)
			print("  count : ", card.count_label.text, " shown ", card.count_label.visible)
			print("  kind  : ", card.kind_label.text)
			print("  each  : ", card.each_label.text)
			print("  detail: ", card.detail_label.text)
			print("  total : ", card.total_label.text, " shown ", card.total_label.visible)
			print("  size  : ", card.size, " at ", card.position)
	if frames == 24:
		# After the timeline has had its say, so the picture shows the row
		# rather than whatever the fixture's first action set.
		screen.hud.set_block(1, 12)
	if frames == 25:
		var held = screen.hud._block.get("player")
		print("block label: ", held)
		if held != null:
			print("  text ", held.text, " visible ", held.visible,
				" at ", held.global_position, " size ", held.size,
				" parent ", held.get_parent())
	if frames == 29 and screen.hud._explaining != null:
		var card = screen.hud._explaining
		print("settled size: ", card.size, " at ", card.position)
	if frames == 30:
		var image := root.get_viewport().get_texture().get_image()
		image.save_png(shot_to)
		print("saved ", ProjectSettings.globalize_path(shot_to))
		return true
	return false


func _put_some_statuses_on() -> void:
	var shown := {"regenerating": "regenerating", "optimized": "optimised",
		"memory_leaked": "memory leak"}
	for stack in range(stacks):
		screen.hud.add_effect(1, shown[status], true, status)
	# Something beside it, so the card is seen against a row rather than alone.
	screen.hud.add_effect(1, "optimised", true, "optimized")
	screen.hud.add_effect(1, "memory leak", false, "memory_leaked")
