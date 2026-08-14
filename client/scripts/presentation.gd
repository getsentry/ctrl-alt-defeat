extends RefCounted

## Cosmetic timing: animations, fades and the pauses between them.
##
## None of it changes game state. In a test it only adds wall-clock time and
## leaves tweens and timers running against nodes the test is about to free,
## which crashes the engine.
##
## Headless means a test run, so animations are off there and every cosmetic
## pause collapses to a single frame. BATTLE_ANIMATIONS overrides the choice
## either way: set it to 1 to watch a headless run animate, or to 0 to strip
## animations from a normal run.
##
## Skipping an animation must not hide a bug in the code that asks for it, so
## every request is recorded first. A test can then check that the game tried
## to play the right effect at the right moment, without waiting for it.


## Effects requested since the last clear_requests(), oldest first.
## Each entry is {"effect": String, "data": Dictionary}.
static var _requests: Array[Dictionary] = []

## Whether to keep that record. On by default in a test, off in a real run so
## that nothing accumulates during play.
static var _recording: int = -1  # -1 = not yet decided


static func animations_enabled() -> bool:
	var override := OS.get_environment("BATTLE_ANIMATIONS")
	if override != "":
		return override != "0" and override.to_lower() != "false"
	return DisplayServer.get_name() != "headless"


static func delay(seconds: float) -> float:
	"""Length of a cosmetic pause. Zero when animations are off."""
	return seconds if animations_enabled() else 0.0


static func is_recording() -> bool:
	if _recording == -1:
		_recording = 1 if DisplayServer.get_name() == "headless" else 0
	return _recording == 1


static func set_recording(enabled: bool) -> void:
	_recording = 1 if enabled else 0


static func request(effect: String, data: Dictionary = {}) -> bool:
	"""Ask to play a cosmetic effect.

	Records the request, then reports whether the caller should actually draw
	it. Call it as the guard at the top of every effect:

		if not Presentation.request("damage_number", {"amount": amount}):
			return
	"""
	if is_recording():
		_requests.append({"effect": effect, "data": data})
	return animations_enabled()


static func requests(effect: String = "") -> Array[Dictionary]:
	"""Recorded requests, all of them or just one kind."""
	if effect == "":
		return _requests.duplicate()
	var matching: Array[Dictionary] = []
	for entry in _requests:
		if entry["effect"] == effect:
			matching.append(entry)
	return matching


static func request_count(effect: String = "") -> int:
	return requests(effect).size()


static func clear_requests() -> void:
	_requests.clear()
