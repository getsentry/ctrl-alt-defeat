extends Resource
class_name Item

enum ItemCategory {
	PROBLEM,
	DEFENSE,
	INFRASTRUCTURE
}

enum ItemType {
	NULL_POINTER,
	MEMORY_LEAK,
	RACE_CONDITION,
	INFINITE_LOOP,
	SQL_INJECTION,
	ERROR_MONITORING,
	SESSION_REPLAY,
	PERFORMANCE_MONITORING,
	PROFILING,
	ALERTING,
	DISTRIBUTED_TRACING,
	LOAD_BALANCER,
	REDIS_CACHE,
	KUBERNETES_CLUSTER,
	CDN,
	DATABASE
}

enum Rarity {
	COMMON,
	UNCOMMON,
	RARE,
	EPIC,
	LEGENDARY
}

@export var item_name: String = "Basic Item"
@export var item_category: ItemCategory = ItemCategory.PROBLEM
@export var item_type: ItemType = ItemType.NULL_POINTER
@export var rarity: Rarity = Rarity.COMMON
@export var tier: int = 1
@export var icon_path: String = ""

@export var base_damage: int = 0
@export var base_health: int = 0
@export var base_speed: float = 1.0
@export var base_armor: int = 0

@export var ability_description: String = ""
@export var adjacency_bonus: String = ""
@export var flavor_text: String = ""

var grid_position: Vector2i = Vector2i(-1, -1)
var is_active: bool = false

func get_total_damage() -> int:
	return base_damage * tier

func get_total_health() -> int:
	return base_health * tier

func can_merge_with(other_item: Item) -> bool:
	return item_type == other_item.item_type and tier == other_item.tier and tier < 3

func merge() -> Item:
	var upgraded = duplicate()
	upgraded.tier += 1
	return upgraded

func get_adjacent_positions() -> Array[Vector2i]:
	var positions: Array[Vector2i] = []
	if grid_position.x >= 0 and grid_position.y >= 0:
		positions.append(grid_position + Vector2i.UP)
		positions.append(grid_position + Vector2i.DOWN)
		positions.append(grid_position + Vector2i.LEFT)
		positions.append(grid_position + Vector2i.RIGHT)
	return positions