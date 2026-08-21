class_name Skins
extends RefCounted

## Which Sentaur the player looks like (GDD 11).
##
## A skin is a picture and nothing else. Nothing in here is sent to the server,
## nothing in here is read by the battle engine, and a skin that changed a
## number would be a bug.
##
## Each one needs BOTH poses. The Sentaur stands calm in the menu and the shop
## and squares up in a battle, so a skin with only one of those would drop the
## player back to somebody else's character halfway through their own game.

## The same file main_menu.gd keeps the player's name in. Anything written here
## must load it first, or the name goes with it.
const SETTINGS := "user://player_settings.cfg"

const DEFAULT := "classic"

const ALL := [
	{
		"id": "classic", "label": "CLASSIC",
		"shop": "res://assets/characters/sentaur_shop.png",
		"battle": "res://assets/characters/sentaur_battle.png",
	},
	{
		"id": "og", "label": "OG",
		"shop": "res://assets/characters/skins/sentaur_black_shop.png",
		"battle": "res://assets/characters/skins/sentaur_black_battle.png",
	},
	{
		"id": "neko", "label": "NEKO",
		"shop": "res://assets/characters/skins/ref_catface.png",
		"battle": "res://assets/characters/skins/ref_catface_battle.png",
	},
	{
		"id": "dotmatrix", "label": "DOT MATRIX",
		"shop": "res://assets/characters/skins/ref_dotmatrix.png",
		"battle": "res://assets/characters/skins/ref_dotmatrix_battle.png",
	},
	{
		"id": "nightshift", "label": "NIGHT SHIFT",
		"shop": "res://assets/characters/skins/ref_visor_anime.png",
		"battle": "res://assets/characters/skins/ref_visor_anime_battle.png",
	},
]


static func ids() -> Array:
	var out := []
	for skin in ALL:
		out.append(skin["id"])
	return out


static func by_id(id: String) -> Dictionary:
	"""The skin with this id, or the default one. An id that is not ours can
	only come from a settings file written by an older or newer build, and
	falling back beats refusing to draw a character."""
	for skin in ALL:
		if skin["id"] == id:
			return skin
	return ALL[0]


static func chosen() -> String:
	var config := ConfigFile.new()
	if config.load(SETTINGS) != OK:
		return DEFAULT
	var id: String = config.get_value("player", "skin", DEFAULT)
	return by_id(id)["id"]


static func choose(id: String) -> void:
	# Load first: this file is shared with the player's name, and saving a
	# fresh ConfigFile would drop whatever else is in it.
	var config := ConfigFile.new()
	config.load(SETTINGS)
	config.set_value("player", "skin", by_id(id)["id"])
	config.save(SETTINGS)


static func shop_texture(id: String = "") -> Texture2D:
	return load(by_id(id if id else chosen())["shop"])


static func battle_texture(id: String = "") -> Texture2D:
	return load(by_id(id if id else chosen())["battle"])


static func wear(node: TextureRect, pose: String) -> void:
	"""Put the chosen skin on one TextureRect. Told a node that is not there,
	it does nothing -- a scene that has lost its character node is a problem
	worth seeing on screen, not one worth crashing over."""
	if not is_instance_valid(node):
		return
	node.texture = battle_texture() if pose == "battle" else shop_texture()
