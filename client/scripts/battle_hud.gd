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
## Numbers thrown off a hit drift up as they fade, so where they start has to
## leave room for that drift. At 0.62 a number rose out of the fighter and
## across the bottom edge of the rack above, so it was read half over the
## battle and half over the furniture.
const PLAYER_AT := Vector2(0.085, 0.70)
const ENEMY_AT := Vector2(0.915, 0.70)

# Proportions taken from the game this is modelled on: about a quarter of the
# width to each rack, about half of it to the stats in the middle, and the
# fighters shrunk into the bottom corners. The racks and the numbers are what a
# player reads; the characters are scenery.
## When night falls, in seconds. A battle has no length to run out of, so the
## bar under the clock counts towards this instead: the moment fatigue starts
## and the battle begins to end itself. It stays full from then on, which is
## the same thing the darkened city says. Section 7.1 of the design document
## holds the number, and the server's own NIGHTFALL must agree with it.
const NIGHTFALL := 17.0

## How big a status is drawn beside a fighter, and where its picture lives.
## Small: a status is something to notice out of the corner of the eye, and the
## card under the pointer is where the reading happens.
const ICON := 30.0
const ICON_PATH := "res://assets/icons/statuses/%s.png"

## The clock carries the time and nothing else. Its buttons used to sit inside
## it, which made the plate wide enough to hold three things in a row -- and
## the racks either side could only be as wide as what that plate left them.
## Out from under it, the plate is no wider than the number it shows.
const CLOCK_SIZE := Vector2(240, 52)
## The row of buttons under the clock: pause, speed, and the log. All the same
## size, so a row of them reads as a row rather than as three separate things.
const CONTROL_SIZE := Vector2(84, 32)
const CONTROL_GAP := 8.0
const CONTROLS_TOP := 78.0
const LOG_SIZE := Vector2(700, 344)
## How far down the racks start. Below the clock, not beside it: the racks
## are as wide as the room allows now, so their backdrops reach in under the
## clock plate and a rack's title was being read as "R RACK". With the clock
## narrowed to the width of the time and its buttons moved into a row beneath
## it, nothing reaches over the racks any more and they start at the top of
## the window instead of below the middle of it.
const RACK_TOP := 30.0
## How far a rack keeps from the edge of the window. Small, because every
## pixel here is a pixel wider the rack can be drawn, and there is nothing at
## the edge of the window for it to run into.
const RACK_MARGIN := 16.0
const RACK_PAD := Vector2(20, 20)
const STATS_SIZE := Vector2(780, 372)
## Low, next to the fighters. Both sit in the bottom two fifths of the screen
## in the game this is modelled on, with the racks above them.
const STATS_TOP := 634.0
# Width only. The art is 1024 by 1536, and a box of any other shape letterboxes
# it: ask for 236 by 430 and you get 236 by 352 with the rest left empty, which
# is why the fighters came out smaller than the numbers said.
const FIGHTER_WIDTH := 350.0
## The proportions of a fighter's artwork, for a fighter that has none to read.
const FIGHTER_ART := Vector2(800, 1141)
## How far past the bottom edge their feet go. Cut off slightly by the frame
## they stand in, they read as standing in the room rather than pasted on top
## of it - the same trick the game this is modelled on uses.
const FEET_BELOW := 26.0
## How far the bottom of the ground shadow stays above the bottom edge. Above
## the crop, or the one thing saying they are standing on something is off the
## screen along with their feet.
const SHADOW_ABOVE := 42.0
## The smudge under a fighter, the same one the shop and the menu use.
const GROUND = preload("res://assets/ui/contact_shadow.png")
const ContactShadow = preload("res://scripts/contact_shadow.gd")
## The card that says what a buff or a debuff on a fighter is doing.
const STATUS_CARD = preload("res://scenes/StatusTooltip.tscn")
const COLUMN_INSET := 26.0
## How far a name keeps away from each end of its column. The blades sit in the
## middle, and a name that runs into them reads as one long word.
const NAME_INSET := 38.0
const ROW_LABEL := 118.0
const BAR_WIDTH := 244.0

## Health below this fraction turns the bar amber, so a fighter about to go
## down reads as such without anyone having to do the arithmetic.
const LOW_HEALTH := 0.3

## The blue Block is written in. Not the health's colour: Block is spent before
## health is touched, and a player deciding whether they will survive the next
## blow is adding the two rather than reading one.
const BLOCK_TINT := Color(0.5, 0.85, 1.0)

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
## The Block figure for each side, by "player" and "enemy". See _build_block().
var _block: Dictionary = {}
## The card explaining whichever chip the pointer is on, or null.
var _explaining: Control = null
## The picture for each status, looked up once. A null in here means there is
## no picture for that status, which is worth remembering too.
var _pictures: Dictionary = {}
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
	# In a row under the clock, once both of them have made their buttons. The
	# log used to sit in the top corner, over a rack that now runs to the top.
	_lay_out_controls([pause_button, speed_button, log_button])
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
	timeline.position = Vector2(16, 9)
	timeline.size = Vector2(CLOCK_SIZE.x - 32, 8)
	timeline.mouse_filter = Control.MOUSE_FILTER_IGNORE
	clock_plate.add_child(timeline)

	_reparent(time_label, clock_plate)
	time_label.scale = Vector2.ONE
	time_label.position = Vector2(0, 20)
	time_label.size = Vector2(CLOCK_SIZE.x, 26)
	time_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	time_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	# The plate is drawn with a chevron at either end, so the time has the
	# middle of it and not the whole of it to sit in.
	time_label.add_theme_font_size_override("font_size", 20)
	time_label.add_theme_color_override("font_color", Color(1.0, 0.93, 0.8))

	pause_button = Button.new()
	pause_button.name = "PauseButton"
	pause_button.text = PAUSE_GLYPH

	_reparent(speed_button, screen)
	screen.add_child(pause_button)


## Say whether the battle is running or held.
func show_paused(held: bool) -> void:
	if is_instance_valid(pause_button):
		pause_button.text = PLAY_GLYPH if held else PAUSE_GLYPH


## Move the clock hand on.
func tick(elapsed: float) -> void:
	if is_instance_valid(timeline):
		timeline.progress = clampf(elapsed / NIGHTFALL, 0.0, 1.0)


# ============ The log ============

## The log, out of the way until it is asked for.
##
## It used to sit open in the middle of the screen, over the ground the two
## fighters stand on and over the numbers flying off them. Now it is a drawer
## on the right, shut until the button is pressed.
func _lay_out_controls(buttons: Array) -> void:
	"""Lay the buttons out in one row, centred under the clock.

	All one size and evenly spaced, so the row reads as a set of controls
	rather than three things that happened to land near each other. Under the
	clock rather than in it or in a corner: the plate stays as narrow as the
	number it holds, and the racks get the rest of the window.
	"""
	var count := buttons.size()
	if count < 1:
		return
	var wide: float = CONTROL_SIZE.x * count + CONTROL_GAP * (count - 1)
	var left: float = (_window().x - wide) / 2.0
	for i in count:
		var button: Button = buttons[i]
		if button == null:
			continue
		# Before it is put anywhere: the speed button comes out of the scene
		# asking for 150 by 40, and a Control cannot be made smaller than the
		# minimum it is carrying, so sizing it first has no effect at all.
		button.custom_minimum_size = CONTROL_SIZE
		_put(button, Vector2(left + i * (CONTROL_SIZE.x + CONTROL_GAP), CONTROLS_TOP),
			CONTROL_SIZE)
		_style_button(button, CLOCK_ACCENT)
		button.z_index = 80


func _build_log_drawer(log_panel: Control) -> void:
	log_button = Button.new()
	log_button.name = "LogButton"
	log_button.text = "LOG"
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
	_block[side] = _build_block(side, left, 160)

	# The rows below the Block moved down to make room for it. Drawn where they
	# were, "BLOCK 12" sat against the word BUFFS with no gap at all and read
	# as the first line of them.
	_effects[side + "_buff"] = _build_effects(side, "BUFFS", Color(0.4, 1.0, 0.6), left, 196)
	_effects[side + "_debuff"] = _build_effects(side, "DEBUFFS", Color(1.0, 0.45, 0.5), left, 280)


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


## The Block a fighter is standing behind.
##
## No bar: Block has no maximum to fill, and a bar without one is a bar that
## means nothing. It reads as a shield with a number on it, and it is only
## there while there is any -- most fighters never hold a point of it, and a
## permanent "BLOCK 0" is a line to read that says nothing.
func _build_block(side: String, left: float, top: float) -> Label:
	var held := Label.new()
	held.name = side.capitalize() + "Block"
	held.position = Vector2(left + 4, top)
	held.size = Vector2(ROW_LABEL + BAR_WIDTH, 24)
	held.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	held.add_theme_font_size_override("font_size", 18)
	held.add_theme_color_override("font_color", BLOCK_TINT)
	held.mouse_filter = Control.MOUSE_FILTER_IGNORE
	held.visible = false
	stats_plate.add_child(held)
	return held


## Say how much Block this fighter is standing behind, or take it away.
func set_block(player: int, amount: int) -> void:
	var held: Label = _block.get("player" if player == 1 else "enemy")
	if not is_instance_valid(held):
		return
	held.visible = amount > 0
	held.text = "BLOCK  %d" % amount


func _build_effects(side: String, title: String, tint: Color, left: float,
		top: float) -> HFlowContainer:
	var caption := Label.new()
	caption.text = title
	caption.position = Vector2(left + 4, top)
	caption.size = Vector2(ROW_LABEL, 26)
	caption.add_theme_font_size_override("font_size", 18)
	caption.add_theme_color_override("font_color", Color(tint, 0.7))
	caption.mouse_filter = Control.MOUSE_FILTER_IGNORE
	stats_plate.add_child(caption)

	# It wraps. An HBoxContainer neither wraps nor clips: a fighter with more
	# statuses than the plate is wide ran its chips straight across into the
	# other fighter's column. There is room under this row for a second line --
	# the rows are 84 apart and a line is 34 -- and no build can reach a third,
	# there being ten statuses in the game and two rows to put them in.
	var row := HFlowContainer.new()
	row.name = side.capitalize() + title.capitalize()
	row.position = Vector2(left + 4, top + 28)
	row.size = Vector2(ROW_LABEL + BAR_WIDTH, 44)
	row.add_theme_constant_override("h_separation", 6)
	row.add_theme_constant_override("v_separation", 4)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	stats_plate.add_child(row)
	return row


## Note that a fighter has picked something up, or had something done to them.
##
## `status` is what the engine calls it, which is what a rule about it is
## looked up by; `effect_name` is the word a player reads on the chip.
func add_effect(player: int, effect_name: String, good: bool,
		status: String = "", stacks: int = 1) -> void:
	var key := ("player" if player == 1 else "enemy") + ("_buff" if good else "_debuff")
	var row: HFlowContainer = _effects.get(key)
	if row == null:
		return

	# One chip per kind, counted, rather than a row that grows without end.
	# Counted in stacks rather than in actions: API Token grants 2 Regenerating
	# in one action, and a chip counting the action said one.
	for chip in row.get_children():
		if chip.get_meta("effect") == effect_name:
			chip.set_meta("count", chip.get_meta("count") + stacks)
			_write_on(chip, effect_name, chip.get_meta("count"))
			# A stack landing while the card for it is up: the card is about
			# how many there are, so it is drawn again saying the new number.
			if is_instance_valid(_explaining):
				_explain(chip)
			return

	var tint := Color(0.4, 1.0, 0.6) if good else Color(1.0, 0.45, 0.5)
	var chip := Button.new()
	chip.flat = true
	chip.focus_mode = Control.FOCUS_NONE
	chip.set_meta("effect", effect_name)
	chip.set_meta("status", status)
	chip.set_meta("count", stacks)
	chip.add_theme_font_size_override("font_size", 17)
	chip.add_theme_color_override("font_color", tint)
	chip.add_theme_color_override("font_hover_color", tint)
	chip.add_theme_color_override("font_pressed_color", tint)
	chip.icon = _picture_of(status)
	if chip.icon != null:
		# icon_max_width scales the picture down to this and leaves the chip to
		# size itself around it and the number. A minimum size on the chip does
		# not work: the number shares it, and the picture came out half the
		# size asked for. expand_icon does not work either -- it fills the room
		# left over, which is none, and the picture disappeared altogether.
		chip.add_theme_constant_override("icon_max_width", int(ICON))
		chip.add_theme_constant_override("h_separation", 2)
	_write_on(chip, effect_name, stacks)
	# It answers the pointer, because it has something to say when asked.
	chip.mouse_filter = Control.MOUSE_FILTER_STOP
	chip.mouse_entered.connect(_explain.bind(chip))
	chip.mouse_exited.connect(_stop_explaining)
	row.add_child(chip)


## What goes on a chip: how many, where there is a picture saying which; the
## word and how many, where there is not.
##
## The word is worth the room only while it is the only thing identifying the
## status. Beside a picture it is a caption nobody reads twice, and ten of them
## are what filled the middle of the screen. The card under the pointer is
## where the word went.
func _write_on(chip: Button, effect_name: String, count: int) -> void:
	if chip.icon != null:
		chip.text = "" if count <= 1 else str(count)
		chip.tooltip_text = ""
		return
	chip.text = effect_name if count <= 1 else "%s x%d" % [effect_name, count]


## The picture for a status, or nothing where none has been drawn.
##
## Nothing is the honest answer rather than a stand-in: a status with no
## picture keeps the word it always had, so one added to the engine tomorrow
## shows up on the plate instead of showing up as a blank square.
func _picture_of(status: String) -> Texture2D:
	if status == "":
		return null
	if _pictures.has(status):
		return _pictures[status]
	var path := ICON_PATH % status
	var found: Texture2D = load(path) if ResourceLoader.exists(path) else null
	_pictures[status] = found
	return found


## Take stacks of a status away from a fighter, however they lost them.
##
## Found by what the engine calls the status rather than by the word on the
## chip: a `spend` or a `cleanse` names it the engine's way, and the two lists
## are not the same one. Both rows are searched because a cleanse takes
## debuffs off as readily as buffs, and what it took is all it says.
##
## A chip with nothing left on it goes, rather than standing there saying x0.
func drop_effect(player: int, status: String, stacks: int) -> void:
	if status == "" or stacks <= 0:
		return
	var side := "player" if player == 1 else "enemy"
	for kind in ["_buff", "_debuff"]:
		var row: HFlowContainer = _effects.get(side + kind)
		if row == null:
			continue
		for chip in row.get_children():
			if chip.get_meta("status", "") != status:
				continue
			var left: int = chip.get_meta("count") - stacks
			if left <= 0:
				# The card is about a chip that is going, so it goes too --
				# and it is freed here rather than left to tree_exiting,
				# which fires a frame later with the pointer still on it.
				if is_instance_valid(_explaining):
					_stop_explaining()
				row.remove_child(chip)
				chip.queue_free()
				return
			chip.set_meta("count", left)
			_write_on(chip, str(chip.get_meta("effect")), left)
			# The card says how many there are, so it says the new number.
			if is_instance_valid(_explaining):
				_explain(chip)
			return


## Put up the card for this chip, at once.
##
## Godot's own tooltip was tried first and is wrong for this three ways over:
## it waits half a second, it is one run of plain text, and it is drawn in a
## style that belongs to nothing else here. This is the card the shop draws for
## an item, and it arrives with the pointer.
func _explain(chip: Control) -> void:
	_stop_explaining()
	var rule: Dictionary = GameStateManager.about_a_status(
		chip.get_meta("status", ""))
	if rule.is_empty():
		return

	_explaining = STATUS_CARD.instantiate()
	_explaining.z_index = 100
	screen.get_tree().root.add_child(_explaining)
	if not _explaining.say(rule, chip.get_meta("count", 1)):
		_stop_explaining()
		return

	# The card takes its own size once it has been laid out, and where it
	# stands depends on how tall it came out, so it is placed again when that
	# settles rather than guessed at now.
	_explaining.resized.connect(_explaining.stand_beside.bind(chip))
	_explaining.stand_beside(chip)

	# The board is drawn again on every action of the battle, so the chip can
	# be freed while the pointer is still on it. The card goes with it: left
	# standing, the next layout pass would hand a freed chip to stand_beside(),
	# which is a hard error rather than something a guard inside it can catch.
	chip.tree_exiting.connect(_stop_explaining)


func _stop_explaining() -> void:
	if is_instance_valid(_explaining):
		_explaining.queue_free()
	_explaining = null


# ============ The fighters ============

## Stand the fighters in the bottom corners, out of the way.
##
## The scene drew them six times their own size in the middle of the screen,
## where they took up more room than the racks and the numbers together. They
## are scenery: the racks are what the battle is decided by.
## How big a fighter is drawn, keeping the art's own proportions.
##
## Read off the artwork itself where there is any, because the artwork has been
## replaced twice now and a fighter drawn to the last one's proportions is a
## fighter squashed.
func _fighter_size(fighter: Control = null) -> Vector2:
	var art := FIGHTER_ART
	if fighter is TextureRect and fighter.texture:
		art = fighter.texture.get_size()
	return Vector2(FIGHTER_WIDTH, FIGHTER_WIDTH * art.y / art.x)


func _place_fighters(art: Dictionary) -> void:
	# The panel art behind the old bottom corner readouts belongs to a layout
	# that no longer exists, and it has Health and Stamina painted into it.
	for key in ["player_art", "enemy_art"]:
		if art.get(key) != null:
			art[key].visible = false

	var window := _window()
	var player: Control = art.get("player")
	var enemy: Control = art.get("enemy")
	_stand(player, Vector2(2, window.y + FEET_BELOW - _fighter_size(player).y))
	var theirs := _fighter_size(enemy)
	_stand(enemy, Vector2(window.x - theirs.x - 2, window.y + FEET_BELOW - theirs.y))


func _stand(fighter: Control, at: Vector2) -> void:
	if fighter == null:
		return
	var holder := fighter.get_parent() as Control
	if holder != null:
		holder.scale = Vector2.ONE
		_place(holder, Vector2.ZERO)
	fighter.scale = Vector2.ONE
	_put(fighter, at, _fighter_size(fighter))

	# Under their feet, and behind them: without it they are a picture over a
	# background rather than someone standing in it. Their feet are cropped by
	# the bottom of the screen on purpose, so the ground they stand on is the
	# last of the floor still in view rather than the line their hooves are on.
	var shadow := ContactShadow.new()
	shadow.name = holder.name + "Shadow" if holder != null else "Shadow"
	shadow.texture = GROUND
	shadow.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	shadow.lift = FEET_BELOW + SHADOW_ABOVE
	if holder != null:
		holder.add_child(shadow)
		holder.move_child(shadow, 0)
		shadow.stands_under = shadow.get_path_to(fighter)
		# Twice: the first settling is what says how big the smudge is, and how
		# big it is decides how far up from the feet it has to sit to stay on
		# the screen.
		shadow.settle()
		shadow.lift = FEET_BELOW + SHADOW_ABOVE + shadow.size.y / 2.0
		shadow.settle()


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
	"""Name a rack, and leave it to stand in the room on its own.

	There used to be an alcove drawn behind each rack -- uprights, shelf lines,
	status lights, cabling. It was a rack drawn behind the racks, and its shelf
	lines were spaced off the board rather than off the racks standing on it,
	so the eye had two pieces of hardware to read and no way to tell which one
	the player owned.
	"""
	if grid == null:
		return

	# The grid draws its own caption in grey at its top left corner, which
	# reads as a debug label. One chip over the board instead.
	grid.title = ""
	var chip := Label.new()
	chip.name = grid.name + "Title"
	chip.text = title
	chip.add_theme_font_size_override("font_size", 18)
	chip.add_theme_color_override("font_color", Color(accent, 0.75))
	chip.mouse_filter = Control.MOUSE_FILTER_IGNORE
	screen.add_child(chip)
	chip.position = grid.global_position + Vector2(4, -26)


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


## The bar that fills as nightfall comes on.
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
