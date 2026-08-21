extends GutTest

## Skins are a picture and nothing else (GDD 11).

const SETTINGS := "user://player_settings.cfg"

var _kept := ""
var _existed := false


func before_each() -> void:
	# These tests write the real settings file, because that is the thing under
	# test. The whole file is copied out verbatim and put back afterwards.
	#
	# Verbatim, and not key by key: this file is shared with the player name and
	# the signed-in account, and rebuilding it from the keys this test happens to
	# know about would quietly drop the rest. An empty rebuild once wiped the
	# guest token and failed test_account_persists.gd instead of this file.
	_existed = FileAccess.file_exists(SETTINGS)
	if _existed:
		_kept = FileAccess.get_file_as_string(SETTINGS)


func after_each() -> void:
	if _existed:
		var file := FileAccess.open(SETTINGS, FileAccess.WRITE)
		file.store_string(_kept)
		file.close()
	elif FileAccess.file_exists(SETTINGS):
		# There was no file before these tests, so there is none after them.
		DirAccess.remove_absolute(ProjectSettings.globalize_path(SETTINGS))
	_kept = ""


func test_every_skin_has_both_poses() -> void:
	for skin in Skins.ALL:
		assert_true(ResourceLoader.exists(skin["shop"]),
			"%s has no shop pose at %s" % [skin["id"], skin["shop"]])
		assert_true(ResourceLoader.exists(skin["battle"]),
			"%s has no battle pose at %s" % [skin["id"], skin["battle"]])


func test_both_poses_actually_load() -> void:
	for skin in Skins.ALL:
		assert_not_null(load(skin["shop"]), "%s shop pose did not load" % skin["id"])
		assert_not_null(load(skin["battle"]), "%s battle pose did not load" % skin["id"])


func test_ids_are_unique() -> void:
	var seen := {}
	for id in Skins.ids():
		assert_false(seen.has(id), "two skins share the id %s" % id)
		seen[id] = true


func test_default_is_one_of_ours() -> void:
	assert_has(Skins.ids(), Skins.DEFAULT)


func test_an_unknown_id_falls_back_rather_than_failing() -> void:
	# An id we do not know can only come from a settings file written by some
	# other build. Drawing the default beats drawing nothing.
	assert_eq(Skins.by_id("no_such_skin")["id"], Skins.DEFAULT)


func test_choosing_one_is_remembered() -> void:
	Skins.choose("neko")
	assert_eq(Skins.chosen(), "neko")


func test_choosing_does_not_lose_the_player_name() -> void:
	var config := ConfigFile.new()
	config.load(SETTINGS)
	config.set_value("player", "name", "Sentaur McTestface")
	config.save(SETTINGS)

	Skins.choose("dotmatrix")

	var after := ConfigFile.new()
	after.load(SETTINGS)
	assert_eq(after.get_value("player", "name", ""), "Sentaur McTestface")


func test_no_skin_carries_anything_but_pictures() -> void:
	# The moment a skin grows a stat, it stops being a skin.
	for skin in Skins.ALL:
		assert_eq(skin.keys().size(), 4,
			"%s has extra keys: %s" % [skin["id"], skin.keys()])
		for key in ["id", "label", "shop", "battle"]:
			assert_has(skin, key)
