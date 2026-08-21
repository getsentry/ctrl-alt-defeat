extends SceneTree

# A scratch tool: puts a great many buffs and debuffs on both fighters and
# saves a picture of the battle screen. Not a test -- it is how a person sees
# what a busy build looks like before deciding what to do about it.
#
#   godot --headless --path . -s tools/look_at_a_crowd.gd
#   HOW_MANY=3 SHOT_TO=/tmp/crowd.png godot ... (as above)

const APITypes = preload("res://scripts/api_types.gd")

## Every status the engine has, as the server names them and shows them.
const ALL := [
	["optimized", "optimised", true], ["calibrated", "compute", true],
	["regenerating", "regenerating", true], ["spiked", "spiked", true],
	["credits", "credits", true],
	["throttled", "throttled", false], ["monitored", "monitored", false],
	["rate_limited", "rate limited", false],
	["memory_leaked", "memory leak", false], ["draining", "draining", false],
]

var screen: Control
var frames := 0
var shot_to := "user://crowd.png"
var how_many := int(OS.get_environment("HOW_MANY"))


func _initialize() -> void:
	var where := OS.get_environment("SHOT_TO")
	if where != "":
		shot_to = where
	if how_many <= 0:
		how_many = ALL.size()

	var state := root.get_node("GameStateManager")
	state.start_new_game()
	state.last_battle_result = APITypes.BattleResult.new({
		"winner": 1, "duration": 10.0, "player1_quota": 80, "player2_quota": 80,
		"seed": 1,
		"actions": [{"timestamp": 0, "source": "system", "action": "battle_start",
			"player": 0, "target": null, "damage": null,
			"details": {"hp": [80, 80], "max_hp": [80, 80],
				"cpu": [2.0, 2.0], "max_cpu": [3.0, 3.0], "block": [12, 4]}}],
		"opponent_name": "AI Opponent", "opponent_type": "ai",
		"player_inventory": {"items": [], "servers": []},
		"enemy_inventory": {"items": [], "servers": []},
	})
	state.last_battle_events = state.last_battle_result.actions

	screen = load("res://scenes/BattleScreen.tscn").instantiate()
	root.add_child(screen)


func _process(_delta: float) -> bool:
	frames += 1
	if frames == 10:
		for entry in ALL.slice(0, how_many):
			for side in [1, 2]:
				screen.hud.add_effect(side, entry[1], entry[2], entry[0], 3)
	if frames == 20:
		var image := root.get_viewport().get_texture().get_image()
		image.save_png(shot_to)
		print("saved ", ProjectSettings.globalize_path(shot_to))
		return true
	return false
