extends Node

## The chest asking for the item in your hand.
##
## The chest is the one thing on this screen a player can do something with
## that never moves and never lights up, so it read as scenery. With something
## in hand it is the second place that item can go, and it says so: it rocks
## awake, keeps a slow sway for as long as the item is up, and lights up and
## swells when the pointer comes over it.
##
## It **rocks rather than slides**. A sideways shudder was tried first and read
## as the picture being mirrored back and forth rather than moved: the chest is
## lit from one side, and sliding an asymmetric picture left and right a dozen
## times a second makes the lit side look as though it is swapping ends.
## Turning it about its own middle cannot be read that way, because the
## silhouette leans instead of jumping.
##
## None of the movement is load-bearing. The price is written on the prompt
## either way and the lighting says where a drop would land, so a run with
## animations off loses only the rocking.

const Presentation = preload("res://scripts/presentation.gd")

## The rock when an item is first picked up: how far it leans, how many times,
## and how long it takes to die away. Small and few -- it is a chest noticing,
## not a chest complaining -- and slow enough to be read as one movement rather
## than as a blur.
const WAKE_LEAN := deg_to_rad(2.6)
const WAKE_BEATS := 2.5
const WAKE_TIME := 0.45

## The sway it settles into while the item is still in hand. Slow and barely
## there: a shudder that never stops is a fault, not an invitation.
const SWAY_LEAN := deg_to_rad(0.5)
const SWAY_PERIOD := 2.2

## How much brighter it is with something in hand, and again when the pointer
## is over it. The second is the one that matters -- it is the answer to "will
## this drop land?" -- so it is the bigger step of the two, and unlike the
## movement it happens whether or not anything is animated.
const AWAKE := Color(1.15, 1.15, 1.15)
const OVER := Color(1.45, 1.3, 1.05)
const ASLEEP := Color.WHITE

## How much bigger it swells while the pointer is over it, about the pivot in
## its middle, so it grows towards the pointer as much as away from it.
const LEAN := 1.06
const LEAN_TIME := 0.12

var chest: Control = null
var prompt: Label = null

var _carrying := false
var _over := false
var _woke_at := -1.0
var _time := 0.0
var _lean: Tween = null


func watch(over_chest: Control) -> void:
	"""Take the chest, and turn it about its own middle rather than its corner.

	Both the rock and the swell are about that pivot: from the corner, a lean
	would throw the chest across the screen and a swell would grow it out of
	one side.
	"""
	chest = over_chest
	prompt = chest.get_node("Prompt") as Label
	chest.pivot_offset = chest.size / 2.0


## An item has been picked up, and this is what it is worth. Says the price
## whether or not anything is animated: it is the part a player needs.
func offer(sell_value: int) -> void:
	if not is_instance_valid(chest):
		return
	prompt.text = "Drop here to sell for %d" % sell_value
	prompt.visible = true
	_carrying = true
	chest.modulate = AWAKE

	# The brightness above says where the item can go and is wanted either
	# way. Only the movement is decoration.
	if not Presentation.request("sell_chest_wakes", {"worth": sell_value}):
		return
	_woke_at = _time


## The item has been put down, sold or taken away. Everything goes back.
func rest() -> void:
	if not is_instance_valid(chest):
		return
	prompt.text = "Drop here to sell"
	prompt.visible = false
	_carrying = false
	_over = false
	_woke_at = -1.0
	chest.modulate = ASLEEP
	chest.rotation = 0.0
	_stop_leaning()
	chest.scale = Vector2.ONE


## Whether the pointer is over the chest, which is the question a player is
## asking while they hold something above it.
func pointing_at_it(pointer: Vector2) -> void:
	if not is_instance_valid(chest) or not _carrying:
		return
	var over := chest.get_global_rect().has_point(pointer)
	if over == _over:
		return
	_over = over

	chest.modulate = OVER if over else AWAKE
	if not Presentation.request("sell_chest_leans", {"over": over}):
		return
	_stop_leaning()
	_lean = chest.create_tween()
	_lean.set_ease(Tween.EASE_OUT)
	# Scale rather than size: the chest is a Panel with the artwork parented to
	# it, and only scale takes the picture with it.
	_lean.tween_property(chest, "scale",
		Vector2.ONE * (LEAN if over else 1.0), Presentation.delay(LEAN_TIME))


func _stop_leaning() -> void:
	if _lean != null and _lean.is_valid():
		_lean.kill()
	_lean = null


func _process(delta: float) -> void:
	_time += delta
	if not is_instance_valid(chest) or not _carrying or _woke_at < 0.0:
		return
	chest.rotation = tilt_for(_time - _woke_at, _time)


## How far the chest is leaning, in radians, `since` seconds after being
## offered something, at `now` on the clock.
##
## Worked out rather than tweened, because it is two movements at once: the
## rock dying away, and the sway that carries on under it. A tween would have
## to be rebuilt every time one of them changed. Takes both times rather than
## reading the clock, so what it draws can be asked about in a headless run,
## where nothing is drawn at all.
func tilt_for(since: float, now: float) -> float:
	var sway := SWAY_LEAN * sin(now * TAU / SWAY_PERIOD)
	if since >= WAKE_TIME:
		return sway
	# Dying away over its own time, so it lands exactly on the sway.
	var left := 1.0 - since / WAKE_TIME
	return sway + WAKE_LEAN * left * sin(since * TAU * WAKE_BEATS)


## How far it is leaning now, for a test: headless draws nothing, so what is
## checked is what would have been drawn.
func tilt_now() -> float:
	if not is_instance_valid(chest):
		return 0.0
	return chest.rotation
