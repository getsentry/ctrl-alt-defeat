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


static func animations_enabled() -> bool:
	var override := OS.get_environment("BATTLE_ANIMATIONS")
	if override != "":
		return override != "0" and override.to_lower() != "false"
	return DisplayServer.get_name() != "headless"


static func delay(seconds: float) -> float:
	"""Length of a cosmetic pause. Zero when animations are off."""
	return seconds if animations_enabled() else 0.0
