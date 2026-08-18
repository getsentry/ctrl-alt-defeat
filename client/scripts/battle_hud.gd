extends RefCounted

## The battle screen's furniture: the clock, the bars, the log drawer and the
## numbers that fly off a hit.
##
## It is all presentation. The battle screen owns the battle; this owns how it
## looks, so that neither file has to be read to change the other.
##
## The scene is left holding the nodes it always held, under the names the
## screen and its tests already use. What happens here is that they are moved,
## restyled and given somewhere to live, because the scene put the clock in the
## middle of the floor and the speed button off the top of the window.

const NeonPlateScript = preload("res://scripts/neon_plate.gd")
const RackBackdropScript = preload("res://scripts/rack_backdrop.gd")

# Taken from the battle screen's own art: the player reads cyan, the opponent
# reads red, and what happens between them reads amber.
const PLAYER_ACCENT := Color(0.15, 0.75, 1.0)
const ENEMY_ACCENT := Color(1.0, 0.25, 0.35)
const CLOCK_ACCENT := Color(1.0, 0.72, 0.18)
const HEALTH_FILL := Color(1.0, 0.22, 0.34)
const HEALTH_LOW := Color(1.0, 0.55, 0.1)
const STAMINA_FILL := Color(1.0, 0.75, 0.2)
const TRACK := Color(0.09, 0.07, 0.18, 0.9)

# Where the two fighters stand, as a fraction of the window. The numbers that
# fly off a hit start here, so they have to follow the characters rather than
# sit at the fixed screen positions the old code used - which put them behind
# the log panel, where nobody ever saw them.
const PLAYER_AT := Vector2(0.085, 0.62)
const ENEMY_AT := Vector2(0.915, 0.62)

# Proportions taken from the game this is modelled on: about a quarter of the
# width to each rack, about half of it to the stats in the middle, and the
# fighters shrunk into the bottom corners. The racks and the numbers are what a
# player reads; the characters are scenery.
const CLOCK_SIZE := Vector2(452, 68)
const LOG_SIZE := Vector2(700, 344)
const LOG_BUTTON_SIZE := Vector2(126, 46)
const RACK_TOP := 78.0
const RACK_MARGIN := 36.0
const RACK_PAD := Vector2(20, 20)
const STATS_SIZE := Vector2(780, 372)
## Low, next to the fighters. Both sit in the bottom two fifths of the screen
## in the game this is modelled on, with the racks above them.
const STATS_TOP := 634.0
# Width only. The art is 1024 by 1536, and a box of any other shape letterboxes
# it: ask for 236 by 430 and you get 236 by 352 with the rest left empty, which
# is why the fighters came out smaller than the numbers said.
const FIGHTER_WIDTH := 380.0
const FIGHTER_ART := Vector2(1024, 1536)
## How far past the bottom edge their feet go. Cut off slightly by the frame
## they stand in, they read as standing in the room rather than pasted on top
## of it - the same trick the game this is modelled on uses.
const FEET_BELOW := 26.0
## Where the ground shadow sits, up from the bottom edge. Above the crop, or
## the one thing saying they are standing on something is off screen too.
const SHADOW_ABOVE := 42.0
const SHADOW_SIZE := Vector2(340, 66)
const COLUMN_INSET := 26.0
## How far a name keeps away from each end of its column. The blades sit in the
## middle, and a name that runs into them reads as one long word.
const NAME_INSET := 38.0
const ROW_LABEL := 118.0
const BAR_WIDTH := 244.0

## Health below this fraction turns the bar amber, so a fighter about to go
## down reads as such without anyone having to do the arithmetic.
const LOW_HEALTH := 0.3

var screen: Control
var clock_plate: NeonPlate
var pause_button: Button
var timeline: Timeline
var log_drawer: Control
var log_button: Button
var stats_plate: NeonPlate
var _hit: AudioStream = null
var _voices: Array[AudioStreamPlayer] = []
var _next_voice: int = 0
var _last_hit: int = -HIT_GAP_MS
var _effects: Dictionary = {}
var _log_open: bool = false


func _init(battle_screen: Control) -> void:
	screen = battle_screen


## The size the game is drawn at.
##
## Not the live viewport: headless that is a 64 by 64 dummy, so anything laid
## out against it lands off the screen and no test of where things sit means
## anything. The window is pinned to this size and cannot be resized, so the
## setting is the truth.
func _window() -> Vector2:
	return Vector2(
		ProjectSettings.get_setting("display/window/size/viewport_width", 1680),
		ProjectSettings.get_setting("display/window/size/viewport_height", 1050))


## Rearrange and restyle everything the scene handed over.
func build(time_label: Label, speed_button: Button, log_panel: Control,
		stats: Dictionary, grids: Dictionary, art: Dictionary) -> void:
	_build_clock(time_label, speed_button)
	_build_log_drawer(log_panel)
	_place_racks(grids)
	_frame(grids["player"], PLAYER_ACCENT, "YOUR RACK")
	_frame(grids["enemy"], ENEMY_ACCENT, "THEIR RACK")
	_place_fighters(art)
	_build_stats(stats)
	_build_hits()


# ============ The clock ============

## The clock, the elapsed time and the speed control, together at the top.
##
## The scene had the time label floating over the floor at nearly three times
## its font size and the speed button parked off the top of the window, where
## no player could reach it.
func _build_clock(time_label: Label, speed_button: Button) -> void:
	# The scene wraps the time label in a Panel sitting dead centre of the
	# screen. Once the label moves out, all that is left of it is a small black
	# bar over the middle of the battle.
	var holder := time_label.get_parent()
	if holder is Panel:
		holder.visible = false

	clock_plate = _plate(CLOCK_ACCENT)
	clock_plate.name = "ClockPlate"
	_put(clock_plate, Vector2((_window().x - CLOCK_SIZE.x) / 2.0, 18), CLOCK_SIZE)
	screen.add_child(clock_plate)

	timeline = Timeline.new()
	timeline.name = "Timeline"
	timeline.accent = CLOCK_ACCENT
	timeline.position = Vector2(26, 13)
	timeline.size = Vector2(CLOCK_SIZE.x - 52, 9)
	timeline.mouse_filter = Control.MOUSE_FILTER_IGNORE
	clock_plate.add_child(timeline)

	_reparent(time_label, clock_plate)
	time_label.scale = Vector2.ONE
	time_label.position = Vector2(26, 28)
	time_label.size = Vector2(120, 32)
	time_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT
	time_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	time_label.add_theme_font_size_override("font_size", 24)
	time_label.add_theme_color_override("font_color", Color(1.0, 0.93, 0.8))

	_reparent(speed_button, clock_plate)
	speed_button.position = Vector2(CLOCK_SIZE.x - 140, 29)
	speed_button.size = Vector2(94, 30)
	speed_button.custom_minimum_size = Vector2(94, 30)
	_style_button(speed_button, CLOCK_ACCENT)

	pause_button = Button.new()
	pause_button.name = "PauseButton"
	pause_button.text = PAUSE_GLYPH
	_put(pause_button, Vector2(CLOCK_SIZE.x - 240, 29), Vector2(84, 30))
	pause_button.custom_minimum_size = Vector2(84, 30)
	_style_button(pause_button, CLOCK_ACCENT)
	clock_plate.add_child(pause_button)


## Say whether the battle is running or held.
func show_paused(held: bool) -> void:
	if is_instance_valid(pause_button):
		pause_button.text = PLAY_GLYPH if held else PAUSE_GLYPH


## Move the clock hand and the elapsed time on.
func tick(elapsed: float, total: float) -> void:
	if is_instance_valid(timeline):
		timeline.progress = clampf(elapsed / maxf(total, 0.001), 0.0, 1.0)


# ============ The log ============

## The log, out of the way until it is asked for.
##
## It used to sit open in the middle of the screen, over the ground the two
## fighters stand on and over the numbers flying off them. Now it is a drawer
## on the right, shut until the button is pressed.
func _build_log_drawer(log_panel: Control) -> void:
	log_button = Button.new()
	log_button.name = "LogButton"
	log_button.text = "LOG"
	_put(log_button, Vector2(_window().x - LOG_BUTTON_SIZE.x - 26, 24), LOG_BUTTON_SIZE)
	_style_button(log_button, PLAYER_ACCENT)
	log_button.pressed.connect(toggle_log)
	screen.add_child(log_button)

	# Down the middle, over the empty ground between the two fighters. On the
	# right it covered the opponent's rack, which is the thing you most want to
	# look at while reading what their build just did to you.
	log_drawer = _plate(PLAYER_ACCENT)
	log_drawer.name = "LogDrawer"
	# Above the stats, not over them. Reading what happened while the numbers
	# it happened to are hidden behind the reading is no use.
	_put(log_drawer, Vector2((_window().x - LOG_SIZE.x) / 2.0,
		STATS_TOP - LOG_SIZE.y - 16), LOG_SIZE)
	log_drawer.visible = false
	# Above the racks, the fighters and the stats, all of which are added after
	# it and would otherwise cover it. The whole point of opening it is to read
	# it.
	log_drawer.z_index = 80
	log_button.z_index = 80
	screen.add_child(log_drawer)

	_reparent(log_panel, log_drawer)
	log_panel.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	log_panel.offset_left = 26
	log_panel.offset_right = -26
	log_panel.offset_top = 18
	log_panel.offset_bottom = -18
	if log_panel is Panel:
		var clear := StyleBoxEmpty.new()
		log_panel.add_theme_stylebox_override("panel", clear)

	# Big enough to read at a glance. It was inheriting the default, which on a
	# 1680 wide window is a whisper.
	var text := log_panel.find_child("LogText", true, false)
	if text != null:
		text.add_theme_font_size_override("normal_font_size", 24)
		text.add_theme_font_size_override("bold_font_size", 24)
		text.add_theme_constant_override("line_separation", 6)


func toggle_log() -> void:
	_log_open = not _log_open
	log_drawer.visible = _log_open
	log_button.text = "LOG ✕" if _log_open else "LOG"


func is_log_open() -> bool:
	return _log_open


# ============ What an item sounds like ============

## How loud a single item landing is. Under the stings, but audibly so: at
## -17 dB on top of a quiet file it came to 19 dB below them, almost all of it
## at 140 Hz, and nobody could hear it at all.
const HIT_VOLUME := -9.0
## How many can sound at once. Past this the oldest is cut off, which is
## preferable to twenty overlapping copies of the same tick.
const VOICES := 6
## How soon it may sound again. Six items landing together should read as one
## blow, not as six.
const HIT_GAP_MS := 55
const HIT_PATH := "res://assets/audio/hit.wav"
const PAUSE_GLYPH := "❚❚"
const PLAY_GLYPH := "▶"


func _build_hits() -> void:
	if not ResourceLoader.exists(HIT_PATH):
		return
	_hit = load(HIT_PATH)
	for i in VOICES:
		var voice := AudioStreamPlayer.new()
		voice.name = "Hit%d" % i
		voice.volume_db = HIT_VOLUME
		screen.add_child(voice)
		_voices.append(voice)


## Sound an item landing a hit.
func item_fired() -> void:
	if _hit == null or _voices.is_empty():
		return

	# Several items landing together should read as one blow, not as a burst of
	# identical ticks over each other.
	var now := Time.get_ticks_msec()
	if now - _last_hit < HIT_GAP_MS:
		return
	_last_hit = now

	var voice := _voices[_next_voice]
	_next_voice = (_next_voice + 1) % _voices.size()
	voice.stream = _hit
	voice.play()


# ============ The stats, in the middle ============

## Both fighters' numbers, side by side in the centre of the screen.
##
## They were two panels in the bottom corners, as far apart as a screen allows,
## so comparing the two meant looking from one corner to the other. Side by
## side is the whole point: a battle is one build against another.
##
## Buffs and debuffs get a row each. They are not filled by anything yet, but
## the space is theirs and is laid out for them, because leaving it out is what
## made the old panels a pair of two-line readouts.
func _build_stats(stats: Dictionary) -> void:
	stats_plate = _plate(Color(0.55, 0.5, 0.85))
	stats_plate.name = "StatsPlate"
	_put(stats_plate, Vector2((_window().x - STATS_SIZE.x) / 2.0, STATS_TOP), STATS_SIZE)
	screen.add_child(stats_plate)

	var column := (STATS_SIZE.x - COLUMN_INSET * 2.0) / 2.0
	_build_column(stats, "player", PLAYER_ACCENT, COLUMN_INSET)
	_build_column(stats, "enemy", ENEMY_ACCENT, COLUMN_INSET + column)

	# The line down the middle, and the crossed blades on it.
	var split := ColorRect.new()
	split.name = "Split"
	split.color = Color(0.6, 0.55, 0.9, 0.25)
	split.position = Vector2(STATS_SIZE.x / 2.0 - 1, 62)
	split.size = Vector2(2, STATS_SIZE.y - 86)
	split.mouse_filter = Control.MOUSE_FILTER_IGNORE
	stats_plate.add_child(split)

	var versus := Label.new()
	versus.name = "Versus"
	versus.text = "⚔"
	versus.position = Vector2(STATS_SIZE.x / 2.0 - 30, 8)
	versus.size = Vector2(60, 46)
	versus.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	versus.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	versus.add_theme_font_size_override("font_size", 34)
	versus.add_theme_color_override("font_color", Color(0.8, 0.78, 1.0))
	versus.mouse_filter = Control.MOUSE_FILTER_IGNORE
	stats_plate.add_child(versus)


func _build_column(stats: Dictionary, side: String, accent: Color, left: float) -> void:
	var column := (STATS_SIZE.x - COLUMN_INSET * 2.0) / 2.0

	var name_label: Label = stats[side + "_name"]
	_reparent(name_label, stats_plate)
	# Kept clear of the middle, where the blades are, and cut off rather than
	# allowed to run over them. A ghost opponent is named by whoever played
	# them, so the length of it is nobody's to promise.
	name_label.position = Vector2(left + NAME_INSET, 8)
	name_label.size = Vector2(column - NAME_INSET * 2.0, 44)
	name_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	name_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	name_label.add_theme_font_size_override("font_size", 28)
	name_label.add_theme_color_override("font_color", accent)
	name_label.clip_text = true
	name_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS

	_build_row(stats, side, "health", accent, left, 72, HEALTH_FILL)
	_build_row(stats, side, "stamina", accent, left, 122, STAMINA_FILL)

	_effects[side + "_buff"] = _build_effects(side, "BUFFS", Color(0.4, 1.0, 0.6), left, 184)
	_effects[side + "_debuff"] = _build_effects(side, "DEBUFFS", Color(1.0, 0.45, 0.5), left, 268)


func _build_row(stats: Dictionary, side: String, what: String, accent: Color,
		left: float, top: float, fill: Color) -> void:
	var caption := Label.new()
	caption.name = side.capitalize() + what.capitalize() + "Caption"
	caption.text = what.to_upper()
	caption.position = Vector2(left + 4, top)
	caption.size = Vector2(ROW_LABEL, 30)
	caption.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	caption.add_theme_font_size_override("font_size", 20)
	caption.add_theme_color_override("font_color", Color(accent, 0.8))
	caption.mouse_filter = Control.MOUSE_FILTER_IGNORE
	stats_plate.add_child(caption)

	var bar: ProgressBar = stats[side + "_" + what]
	_reparent(bar, stats_plate)
	bar.scale = Vector2.ONE
	bar.position = Vector2(left + ROW_LABEL, top)
	bar.size = Vector2(BAR_WIDTH, 30)
	_style_bar(bar, fill)

	var value: Label = stats[side + "_" + what + "_value"]
	_reparent(value, stats_plate)
	value.scale = Vector2.ONE
	value.position = Vector2(left + ROW_LABEL, top)
	value.size = Vector2(BAR_WIDTH, 30)
	value.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	value.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	value.add_theme_font_size_override("font_size", 20)
	value.add_theme_color_override("font_color", Color(1, 1, 1))
	value.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.75))
	value.add_theme_constant_override("outline_size", 5)
	value.mouse_filter = Control.MOUSE_FILTER_IGNORE


func _build_effects(side: String, title: String, tint: Color, left: float,
		top: float) -> HBoxContainer:
	var caption := Label.new()
	caption.text = title
	caption.position = Vector2(left + 4, top)
	caption.size = Vector2(ROW_LABEL, 26)
	caption.add_theme_font_size_override("font_size", 18)
	caption.add_theme_color_override("font_color", Color(tint, 0.7))
	caption.mouse_filter = Control.MOUSE_FILTER_IGNORE
	stats_plate.add_child(caption)

	var row := HBoxContainer.new()
	row.name = side.capitalize() + title.capitalize()
	row.position = Vector2(left + 4, top + 28)
	row.size = Vector2(ROW_LABEL + BAR_WIDTH, 44)
	row.add_theme_constant_override("separation", 8)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	stats_plate.add_child(row)
	return row


## Note that a fighter has picked something up, or had something done to them.
func add_effect(player: int, effect_name: String, good: bool) -> void:
	var key := ("player" if player == 1 else "enemy") + ("_buff" if good else "_debuff")
	var row: HBoxContainer = _effects.get(key)
	if row == null:
		return

	# One chip per kind, counted, rather than a row that grows without end.
	for chip in row.get_children():
		if chip.get_meta("effect") == effect_name:
			chip.set_meta("count", chip.get_meta("count") + 1)
			chip.text = "%s x%d" % [effect_name, chip.get_meta("count")]
			return

	var tint := Color(0.4, 1.0, 0.6) if good else Color(1.0, 0.45, 0.5)
	var chip := Label.new()
	chip.text = effect_name
	chip.set_meta("effect", effect_name)
	chip.set_meta("count", 1)
	chip.add_theme_font_size_override("font_size", 17)
	chip.add_theme_color_override("font_color", tint)
	chip.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(chip)


# ============ The fighters ============

## Stand the fighters in the bottom corners, out of the way.
##
## The scene drew them six times their own size in the middle of the screen,
## where they took up more room than the racks and the numbers together. They
## are scenery: the racks are what the battle is decided by.
## How big a fighter is drawn, keeping the art's own proportions.
func _fighter_size() -> Vector2:
	return Vector2(FIGHTER_WIDTH, FIGHTER_WIDTH * FIGHTER_ART.y / FIGHTER_ART.x)


func _place_fighters(art: Dictionary) -> void:
	# The panel art behind the old bottom corner readouts belongs to a layout
	# that no longer exists, and it has Health and Stamina painted into it.
	for key in ["player_art", "enemy_art"]:
		if art.get(key) != null:
			art[key].visible = false

	var window := _window()
	var drawn := _fighter_size()
	var top := window.y + FEET_BELOW - drawn.y
	_stand(art.get("player"), Vector2(2, top), PLAYER_ACCENT)
	_stand(art.get("enemy"), Vector2(window.x - drawn.x - 2, top), ENEMY_ACCENT)


func _stand(fighter: Control, at: Vector2, accent: Color) -> void:
	if fighter == null:
		return
	var holder := fighter.get_parent() as Control
	if holder != null:
		holder.scale = Vector2.ONE
		_place(holder, Vector2.ZERO)
	var drawn := _fighter_size()
	fighter.scale = Vector2.ONE
	_put(fighter, at, drawn)

	# Under their feet, and behind them: without it they are a picture over a
	# background rather than someone standing in it.
	var shadow := Shadow.new()
	shadow.tint = accent
	shadow.name = holder.name + "Shadow" if holder != null else "Shadow"
	shadow.mouse_filter = Control.MOUSE_FILTER_IGNORE
	shadow.position = Vector2(at.x + drawn.x / 2.0 - SHADOW_SIZE.x / 2.0,
		_window().y - SHADOW_ABOVE - SHADOW_SIZE.y / 2.0)
	shadow.size = SHADOW_SIZE
	if holder != null:
		holder.add_child(shadow)
		holder.move_child(shadow, 0)


# ============ The bars ============

func _style_bar(bar: ProgressBar, fill: Color) -> void:
	var track := StyleBoxFlat.new()
	track.bg_color = TRACK
	track.set_corner_radius_all(3)
	track.border_color = Color(fill, 0.35)
	track.set_border_width_all(1)
	bar.add_theme_stylebox_override("background", track)

	var filled := StyleBoxFlat.new()
	filled.bg_color = fill
	filled.set_corner_radius_all(3)
	bar.add_theme_stylebox_override("fill", filled)
	bar.show_percentage = false
	bar.set_meta("fill_color", fill)


## Repaint a health bar for how much is left. Amber near the end.
func health_changed(bar: ProgressBar) -> void:
	if bar.max_value <= 0:
		return
	var left := bar.value / bar.max_value
	var wanted := HEALTH_LOW if left <= LOW_HEALTH else HEALTH_FILL
	if bar.get_meta("fill_color", HEALTH_FILL) == wanted:
		return
	_style_bar(bar, wanted)


# ============ The inventories ============

## Stand the two racks level with each other, an equal margin from each edge.
##
## The scene anchors one from the left and the other from the right, at
## different scales and different offsets, so they sat at different heights,
## different widths, and left a gap that was not in the middle. The clock,
## which is in the middle, landed on top of the right one.
func _place_racks(grids: Dictionary) -> void:
	var window := _window()
	for side in ["player", "enemy"]:
		var grid: Control = grids[side]
		var panel := grid.get_parent() as Control
		if panel == null:
			continue
		# The scene scales these panels down. The rack is meant to be read, so
		# it is drawn at its own size.
		panel.scale = Vector2.ONE
		var wide: float = grid.size.x
		var at := RACK_MARGIN if side == "player" else window.x - RACK_MARGIN - wide
		_place(panel, Vector2(at, RACK_TOP + RACK_PAD.y))


func _place(panel: Control, at: Vector2) -> void:
	# The scene made these Panels, so they draw the theme's default slab behind
	# the rack. With the empty grid gone that slab is the only thing left
	# marking out a nine by seven area nobody can see or use.
	if panel is Panel:
		panel.add_theme_stylebox_override("panel", StyleBoxEmpty.new())
	panel.anchor_left = 0.0
	panel.anchor_right = 0.0
	panel.anchor_top = 0.0
	panel.anchor_bottom = 0.0
	panel.position = at


## Stand a rack in its alcove.
##
## The whole rack, and the same size every round. Fitted to what the build
## happens to hold, it starts the run as a thumbnail and moves and resizes
## every time a container is bought, so the screen never settles.
##
## Sized off the grid, not off the panel holding it. The panels in the scene are
## half as wide again as the grids they contain, so a frame built from the
## panel runs off both edges of the window with nothing in the overhang.
func _frame(grid: Control, accent: Color, title: String) -> void:
	if grid == null:
		return
	var drawn := grid.size * grid.get_global_transform().get_scale()
	var back: RackBackdrop = RackBackdropScript.new()
	back.name = grid.name + "Backdrop"
	back.accent = accent
	back.unit = grid.cell_size + grid.cell_spacing
	back.origin = RACK_PAD.y + 14
	back.position = grid.global_position - Vector2(RACK_PAD.x, RACK_PAD.y + 14)
	back.size = drawn + Vector2(RACK_PAD.x * 2, RACK_PAD.y * 2 + 14)
	back.mouse_filter = Control.MOUSE_FILTER_IGNORE
	# Behind the rack it holds, and behind everything drawn over it.
	screen.add_child(back)
	screen.move_child(back, 1)

	# The grid draws its own caption in grey at its top left corner, which
	# reads as a debug label. One chip on the alcove instead.
	grid.title = ""
	var chip := Label.new()
	chip.name = "Title"
	chip.text = title
	chip.position = Vector2(30, 4)
	chip.add_theme_font_size_override("font_size", 18)
	chip.add_theme_color_override("font_color", Color(accent, 0.75))
	chip.mouse_filter = Control.MOUSE_FILTER_IGNORE
	back.add_child(chip)


# ============ Numbers off a hit ============

## Where a fighter stands, in screen coordinates.
func fighter_at(player: int) -> Vector2:
	var window := _window()
	var at := PLAYER_AT if player == 1 else ENEMY_AT
	return Vector2(window.x * at.x, window.y * at.y)


## Throw a number off a fighter: damage, healing, a block, a miss.
##
## They used to appear at two fixed points near the middle of the screen, which
## the log panel covered, so the one piece of feedback that says what just
## happened was invisible.
func combat_number(player: int, text: String, tint: Color, size: int) -> Label:
	var label := Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", size)
	label.add_theme_color_override("font_color", tint)
	label.add_theme_color_override("font_outline_color", Color(0.02, 0.01, 0.06, 0.9))
	label.add_theme_constant_override("outline_size", 8)
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.size = Vector2(220, 60)
	label.pivot_offset = Vector2(110, 30)
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	label.z_index = 60

	# Scattered a little, so two hits landing together do not print on top of
	# one another.
	var jitter := Vector2(randf_range(-46.0, 46.0), randf_range(-30.0, 30.0))
	label.position = fighter_at(player) - Vector2(110, 30) + jitter
	screen.add_child(label)
	return label


# ============ Shared ============

func _plate(accent: Color) -> NeonPlate:
	var plate: NeonPlate = NeonPlateScript.new()
	plate.accent = accent
	plate.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return plate


func _style_button(button: Button, accent: Color) -> void:
	for state in ["normal", "hover", "pressed", "focus"]:
		var style := StyleBoxFlat.new()
		style.bg_color = Color(0.06, 0.04, 0.16, 0.95)
		style.border_color = accent if state != "hover" else Color.WHITE
		style.set_border_width_all(2)
		style.set_corner_radius_all(4)
		if state == "pressed":
			style.bg_color = Color(accent, 0.28)
		button.add_theme_stylebox_override(state, style)
	button.add_theme_color_override("font_color", accent)
	button.add_theme_color_override("font_hover_color", Color.WHITE)
	button.add_theme_font_size_override("font_size", 22)


## Put a control at a spot, clear of the anchors it was born with.
##
## Anchors resolve against the parent, and the parent follows the live
## viewport, which headless is 64 by 64. Everything laid out by anchor lands
## somewhere else in a test run than it does in a real one.
func _put(control: Control, at: Vector2, control_size: Vector2) -> void:
	control.anchor_left = 0.0
	control.anchor_top = 0.0
	control.anchor_right = 0.0
	control.anchor_bottom = 0.0
	control.position = at
	control.size = control_size


func _reparent(node: Node, to: Node) -> void:
	if node.get_parent() != null:
		node.get_parent().remove_child(node)
	to.add_child(node)


## The pool of light a fighter stands in.
##
## A shadow, on this floor, is invisible: the ground is already almost black,
## so darkening it says nothing. What does read is the floor lit around their
## feet, which grounds them the same way and belongs to a neon-lit room.
##
## Godot's 2D drawing has no gradient fill, so it is a stack of ellipses, each
## one smaller than the last, piling up alpha towards the middle.
class Shadow extends Control:
	const RINGS := 10

	var tint: Color = Color.WHITE

	func _draw() -> void:
		var middle := size / 2.0
		for ring in range(RINGS, 0, -1):
			var scaling := float(ring) / RINGS
			var points := PackedVector2Array()
			for step in 32:
				var angle := TAU * step / 32.0
				points.append(middle + Vector2(cos(angle) * middle.x * scaling,
					sin(angle) * middle.y * scaling))
			draw_colored_polygon(points, Color(tint, 0.035))
		# A darker core right under them, so it is contact and not just a glow.
		var core := PackedVector2Array()
		for step in 32:
			var angle := TAU * step / 32.0
			core.append(middle + Vector2(cos(angle) * middle.x * 0.42,
				sin(angle) * middle.y * 0.5))
		draw_colored_polygon(core, Color(0.02, 0.0, 0.06, 0.35))


## The bar that fills as the battle runs out.
class Timeline extends Control:
	var accent: Color = Color.WHITE
	var progress: float = 0.0:
		set(value):
			progress = value
			queue_redraw()

	func _draw() -> void:
		var whole := Rect2(Vector2.ZERO, size)
		draw_rect(whole, Color(0.09, 0.07, 0.18, 0.9))
		if progress > 0.0:
			draw_rect(Rect2(Vector2.ZERO, Vector2(size.x * progress, size.y)),
				Color(accent, 0.85))
			# A brighter head, so the eye can find where it has got to.
			draw_rect(Rect2(Vector2(size.x * progress - 3.0, -2.0),
				Vector2(3.0, size.y + 4.0)), Color.WHITE)
		draw_rect(whole, Color(accent, 0.7), false, 1.0)
