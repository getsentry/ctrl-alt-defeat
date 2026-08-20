extends Node

## How big the window was left, remembered between runs.
##
## Desktop only. A page decides how big a web build is, and there is nothing
## there to remember: asking for a size would be the game resizing somebody's
## browser tab.
##
## Only the size is kept, and the window is put back in the middle of whatever
## screen it opens on. A remembered corner lands off the edge as soon as the
## screen it was on is unplugged, and a game that opens where it cannot be seen
## is worse than one that opens in the middle.

## Kept beside the player's name, which is already remembered this way.
const SETTINGS := "user://window.cfg"
const SECTION := "window"

## The smallest window worth putting back. Anything under this is a window
## dragged shut rather than a size somebody chose, and the game is unusable at
## it -- the whole screen is laid out in one 1680 by 1050 space.
const SMALLEST := Vector2i(720, 450)

## How long after the last change the size is written down. Dragging an edge
## sends a stream of these, and a file written on every one of them is a file
## written two hundred times to record one decision.
const SETTLE := 0.4

var _settle: Timer = null


func _ready() -> void:
	if not remembers(OS.has_feature("web")):
		return

	_restore()

	_settle = Timer.new()
	_settle.one_shot = true
	_settle.wait_time = SETTLE
	_settle.timeout.connect(write_down)
	add_child(_settle)
	get_tree().root.size_changed.connect(_changed)


func _notification(what: int) -> void:
	# The last change may not have settled yet, and closing the window is the
	# one moment there is certainly no more coming.
	if what == NOTIFICATION_WM_CLOSE_REQUEST:
		write_down()


static func remembers(on_the_web: bool) -> bool:
	"""Whether this build has a window of its own to remember"""
	return not on_the_web


static func fits(wanted: Vector2i, screen: Vector2i) -> Vector2i:
	"""The size to actually ask for, given the screen it has to fit on.

	Nothing at all for a size not worth restoring, so that a first run, a
	corrupt file and a window dragged shut all end up at the size the project
	settings ask for rather than at something unusable.
	"""
	if wanted.x < SMALLEST.x or wanted.y < SMALLEST.y:
		return Vector2i.ZERO
	return Vector2i(mini(wanted.x, screen.x), mini(wanted.y, screen.y))


static func remembered(config: ConfigFile) -> Vector2i:
	"""The size written down last time, or nothing if there is none"""
	var size = config.get_value(SECTION, "size", Vector2i.ZERO)
	return size if size is Vector2i else Vector2i.ZERO


static func remember(config: ConfigFile, size: Vector2i, maximised: bool) -> void:
	"""Write down a size, unless the window is not the size of itself.

	A maximised window measures as big as the screen. Writing that down and
	putting it back next time gives a window that fills the screen without
	being maximised, which cannot be put back to the size it was before.
	"""
	config.set_value(SECTION, "maximised", maximised)
	if not maximised:
		config.set_value(SECTION, "size", size)


func write_down() -> void:
	"""Save how big the window is now"""
	if not remembers(OS.has_feature("web")):
		return

	var config := ConfigFile.new()
	# Loaded first so that nothing else written in here is thrown away.
	config.load(SETTINGS)
	var mode := DisplayServer.window_get_mode()
	remember(config, DisplayServer.window_get_size(),
		mode == DisplayServer.WINDOW_MODE_MAXIMIZED)
	config.save(SETTINGS)


func _changed() -> void:
	if is_instance_valid(_settle):
		_settle.start()


func _restore() -> void:
	var config := ConfigFile.new()
	if config.load(SETTINGS) != OK:
		return

	var screen := DisplayServer.screen_get_usable_rect(
		DisplayServer.window_get_current_screen())
	var size := fits(remembered(config), screen.size)
	if size != Vector2i.ZERO:
		DisplayServer.window_set_size(size)
		DisplayServer.window_set_position(
			screen.position + (screen.size - size) / 2)

	if config.get_value(SECTION, "maximised", false):
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_MAXIMIZED)
