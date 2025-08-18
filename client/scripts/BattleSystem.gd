extends Node
class_name BattleSystem

var player_units: Array = []
var enemy_units: Array = []
var battle_timer: float = 0.0
var battle_duration: float = 60.0
var is_battling: bool = false

signal battle_started()
signal battle_ended(player_won: bool)
signal unit_damaged(unit: Node, damage: int)
signal unit_died(unit: Node)

func _ready():
	set_process(false)

func _process(delta):
	if is_battling:
		battle_timer += delta
		update_battle(delta)

		if battle_timer >= battle_duration:
			end_battle()

func start_battle(player_inventory: Inventory, enemy_build: Array):
	is_battling = true
	battle_timer = 0.0
	set_process(true)

	spawn_player_units(player_inventory)
	spawn_enemy_units(enemy_build)

	battle_started.emit()

func spawn_player_units(inventory: Inventory):
	player_units.clear()
	var items = inventory.get_all_items()

	for item in items:
		var unit = create_battle_unit(item, true)
		player_units.append(unit)

func spawn_enemy_units(enemy_items: Array):
	enemy_units.clear()

	for item_data in enemy_items:
		var unit = create_battle_unit_from_data(item_data, false)
		enemy_units.append(unit)

func create_battle_unit(item: Item, is_player: bool) -> Dictionary:
	return {
		"item": item,
		"current_hp": item.get_total_health(),
		"max_hp": item.get_total_health(),
		"damage": item.get_total_damage(),
		"speed": item.base_speed,
		"attack_cooldown": 0.0,
		"is_player": is_player,
		"position": Vector2.ZERO,
		"target": null,
		"effects": [],
		"stacked_damage": 0
	}

func create_battle_unit_from_data(item_data: Dictionary, is_player: bool) -> Dictionary:
	return {
		"item": null,
		"current_hp": item_data.get("health", 10),
		"max_hp": item_data.get("health", 10),
		"damage": item_data.get("damage", 5),
		"speed": item_data.get("speed", 1.0),
		"attack_cooldown": 0.0,
		"is_player": is_player,
		"position": Vector2.ZERO,
		"target": null,
		"effects": [],
		"stacked_damage": 0
	}

func update_battle(delta: float):
	for unit in player_units:
		if unit.current_hp > 0:
			update_unit(unit, enemy_units, delta)

	for unit in enemy_units:
		if unit.current_hp > 0:
			update_unit(unit, player_units, delta)

	remove_dead_units()

func update_unit(unit: Dictionary, targets: Array, delta: float):
	unit.attack_cooldown -= delta * unit.speed

	if unit.attack_cooldown <= 0:
		var target = find_target(unit, targets)
		if target:
			attack(unit, target)
			unit.attack_cooldown = 2.0

	process_unit_abilities(unit, delta)

func find_target(unit: Dictionary, targets: Array) -> Dictionary:
	var valid_targets = targets.filter(func(t): return t.current_hp > 0)
	if valid_targets.size() > 0:
		return valid_targets[0]
	return {}

func attack(attacker: Dictionary, target: Dictionary):
	var damage = attacker.damage + attacker.stacked_damage

	if attacker.item and attacker.item.item_type == Item.ItemType.PROFILING:
		if randf() < 0.3:
			damage *= 2

	apply_damage(target, damage)

	if attacker.item and attacker.item.item_type == Item.ItemType.SESSION_REPLAY:
		var reflect_damage = damage * 0.5
		apply_damage(attacker, reflect_damage)

	unit_damaged.emit(target, damage)

func apply_damage(unit: Dictionary, damage: int):
	unit.current_hp -= damage
	if unit.current_hp <= 0:
		unit.current_hp = 0
		unit_died.emit(unit)

func process_unit_abilities(unit: Dictionary, delta: float):
	if not unit.item:
		return

	match unit.item.item_type:
		Item.ItemType.CRON_MONITORING:
			if not unit.has("cron_timer"):
				unit["cron_timer"] = 0.0
			unit.cron_timer += delta
			if unit.cron_timer >= 3.0:
				var targets = enemy_units if unit.is_player else player_units
				for target in targets:
					if target.current_hp > 0:
						apply_damage(target, 3)
				unit.cron_timer = 0.0

		Item.ItemType.PERFORMANCE:
			pass

		Item.ItemType.ISSUE_TRACKER:
			pass

func remove_dead_units():
	player_units = player_units.filter(func(u): return u.current_hp > 0)
	enemy_units = enemy_units.filter(func(u): return u.current_hp > 0)

func end_battle():
	is_battling = false
	set_process(false)

	var player_total_hp = 0
	for unit in player_units:
		player_total_hp += unit.current_hp

	var enemy_total_hp = 0
	for unit in enemy_units:
		enemy_total_hp += unit.current_hp

	var player_won = player_total_hp > enemy_total_hp
	battle_ended.emit(player_won)

func get_battle_state() -> Dictionary:
	return {
		"timer": battle_timer,
		"duration": battle_duration,
		"player_units": player_units.size(),
		"enemy_units": enemy_units.size(),
		"is_battling": is_battling
	}
