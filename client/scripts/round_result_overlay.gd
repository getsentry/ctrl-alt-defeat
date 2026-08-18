extends Control

## The run scoreboard that drops over the battle when a round ends.
##
## It reports the run, not the round: how many wins are banked towards the
## target, and how many tries are left. See section 6.3 of the Game Design
## Document.
##
## The server has already applied the round by the time the battle is replayed,
## so GameStateManager holds the count from *after* it. The screen therefore
## draws the count from before the round and then moves the one icon this round
## changed, which is the whole point of the animation: the player watches the
## trophy light up, or the heart go out.
##
## Nothing here changes game state. Every animation goes through Presentation,
## so a headless run draws none of it and continues on its own instead of
## waiting for a click it can never receive.

const Presentation = preload("res://scripts/presentation.gd")

## Emitted when the player has seen the result and wants to move on.
signal continued

const TROPHY_ICON: Texture2D = preload("res://assets/ui/trophy.svg")
const HEART_ICON: Texture2D = preload("res://assets/ui/heart.svg")
const WON_STING: AudioStream = preload("res://assets/audio/round_won.wav")
const LOST_STING: AudioStream = preload("res://assets/audio/round_lost.wav")

# Neon palette, taken from the battle screen: the player reads cyan, the
# opponent reads red, and the run's own counters get their own two colours so
# they do not read as either side's health.
const DIM_COLOR := Color(0.02, 0.01, 0.07)
const DIM_ALPHA := 0.80
const WON_ACCENT := Color(0.15, 0.85, 1.0)
const LOST_ACCENT := Color(1.0, 0.18, 0.35)
const TROPHY_LIT := Color(1.0, 0.72, 0.18)
const HEART_LIT := Color(1.0, 0.24, 0.45)
const SPENT := Color(0.20, 0.17, 0.33)
# The two mistracked copies behind the banner text.
const GHOST_A := Color(1.0, 0.15, 0.75)
const GHOST_B := Color(0.2, 1.0, 0.95)

# Geometry. Each icon sits in its own slot, and the slot is what keeps the icon
# and its glow inside the plate: an icon left to fill the row stretches with the
# row and spills over the edge.
const CELL_SIZE := Vector2(72, 84)
# A whole multiple of the icons' own 16 pixel grid, so the blocks stay even.
const ICON_SIZE := Vector2(48, 48)
const CELL_GAP := 10
const GLOW_SCALE := 1.55
const POP_SCALE := 1.4
const BAR_HEIGHT := 124.0
const BAR_TITLE_WIDTH := 196.0
const BAR_PAD := 40.0
# Clearance at the pointed end of a bar. It has to beat the slant, or the last
# slot's corner crosses the outline where the plate has already closed in.
const BAR_END_PAD := 46.0
const BANNER_SIZE := Vector2(760, 140)

# Cosmetic timings, in seconds. Presentation.delay() collapses each of them
# when animations are off.
const DIM_FADE := 0.30
const BANNER_DROP := 0.55
const BAR_SLIDE := 0.45
const WINS_SLIDE_AT := 0.30
const TRIES_SLIDE_AT := 0.45
const SWEEP_TIME := 0.40
const GLITCH_STEP := 0.045
const CHANGE_AT := 1.15
const CHANGE_POP := 0.22
const CHANGE_SETTLE := 0.34
const CHANGE_SHAKE := 0.06
const PROMPT_AT := 1.35

# The result being shown. Set by show_result().
var won: bool = false
## Wins banked and tries left after the round, as GameStateManager holds them.
var wins: int = 0
var lives: int = 0

## Whether the animation has finished and the screen is showing its final
## state. A click before that settles it instead of continuing, so an
## impatient player never loses the result.
var settled: bool = false

var _dim: ColorRect
var _sparkles: Control
var _banner: NeonPlate
var _banner_label: Label
var _ghosts: Array[Label] = []
var _wins_bar: NeonPlate
var _tries_bar: NeonPlate
var _prompt: Label
var _sting: AudioStreamPlayer
var _trophies: Array[Control] = []
var _hearts: Array[Control] = []
var _tweens: Array[Tween] = []


func _ready() -> void:
	set_anchors_and_offsets_preset(PRESET_FULL_RECT)
	mouse_filter = MOUSE_FILTER_STOP
	# The battle screen gives its status panels and health bars a z_index, and
	# z_index beats tree order. Without this the result draws under them.
	z_index = 100
	_build()


func _exit_tree() -> void:
	# The tweens outlive this node otherwise, and resuming one against a freed
	# node takes the engine down.
	for tween in _tweens:
		if is_instance_valid(tween):
			tween.kill()
	_tweens.clear()


## Show the result of a round.
##
## `wins_after` and `lives_after` are the run totals the server has already
## applied, so the screen works out the counts to open on from `player_won`.
func show_result(player_won: bool, wins_after: int, lives_after: int) -> void:
	won = player_won
	wins = wins_after
	lives = lives_after

	if not is_node_ready():
		await ready

	_fill_icons()
	_banner_label.text = "ROUND WON" if won else "ROUND LOST"
	for ghost in _ghosts:
		ghost.text = _banner_label.text
	var accent := WON_ACCENT if won else LOST_ACCENT
	_banner_label.add_theme_color_override("font_color", accent)
	_banner.accent = accent
	_sting.stream = WON_STING if won else LOST_STING

	if not Presentation.request("round_result", {"won": won, "wins": wins, "lives": lives}):
		# No display to animate on, so show the settled screen and move on
		# rather than wait for a click that will never come.
		_settle()
		continued.emit()
		return

	_animate()


## The count of banked wins the screen opens on, before this round is applied.
func wins_before() -> int:
	return wins - 1 if won else wins


## The count of tries left the screen opens on, before this round is applied.
func lives_before() -> int:
	return lives if won else lives + 1


## The icon this round moves: the trophy that lights up, or the heart that goes
## out. -1 when the round changed neither, which the run rules do not allow but
## a clamped count could still produce.
func changed_icon_index() -> int:
	var index := wins_before() if won else lives_before() - 1
	var icons := _trophies if won else _hearts
	return index if index >= 0 and index < icons.size() else -1


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_accept") or event.is_action_pressed("ui_cancel"):
		_advance()
		get_viewport().set_input_as_handled()


func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed \
			and event.button_index == MOUSE_BUTTON_LEFT:
		_advance()
		accept_event()


func _advance() -> void:
	# A click during the animation settles it. The player asked to see the
	# result sooner, not to skip past it.
	if settled:
		continued.emit()
	else:
		_settle()


# ============ Building ============

func _build() -> void:
	_dim = ColorRect.new()
	_dim.name = "Dim"
	_dim.color = Color(DIM_COLOR, 0.0)
	_dim.set_anchors_and_offsets_preset(PRESET_FULL_RECT)
	_dim.mouse_filter = MOUSE_FILTER_IGNORE
	add_child(_dim)

	_banner = _build_banner()
	_tries_bar = _build_bar("TRIES", HEART_ICON, HEART_LIT,
		GameStateManager.STARTING_LIVES, _hearts)
	_wins_bar = _build_bar("WINS", TROPHY_ICON, TROPHY_LIT,
		GameStateManager.WINS_TO_VICTORY, _trophies)

	# Each bar is only as wide as it needs to be, so the slots stay evenly
	# spread rather than huddling in one end of an oversized plate.
	add_child(_hold(_wins_bar, _bar_size(GameStateManager.WINS_TO_VICTORY), 356))
	add_child(_hold(_tries_bar, _bar_size(GameStateManager.STARTING_LIVES), 500))
	add_child(_hold(_banner, BANNER_SIZE, 146))

	# Above the plates rather than behind them: the sparks thrown off the icon
	# that just changed have to be seen coming off it.
	_sparkles = Sparkles.new()
	_sparkles.name = "Sparkles"
	_sparkles.set_anchors_and_offsets_preset(PRESET_FULL_RECT)
	_sparkles.mouse_filter = MOUSE_FILTER_IGNORE
	_sparkles.visible = false
	add_child(_sparkles)

	_prompt = Label.new()
	_prompt.name = "ContinuePrompt"
	_prompt.text = "> CLICK TO CONTINUE"
	_prompt.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_prompt.add_theme_font_size_override("font_size", 28)
	_prompt.add_theme_color_override("font_color", Color(0.62, 0.88, 1.0))
	_prompt.modulate.a = 0.0
	_prompt.mouse_filter = MOUSE_FILTER_IGNORE
	add_child(_hold(_prompt, Vector2(600, 44), 664))

	_sting = AudioStreamPlayer.new()
	_sting.name = "Sting"
	_sting.volume_db = -6.0
	add_child(_sting)


## How wide a counter bar has to be to hold its slots.
func _bar_size(count: int) -> Vector2:
	var slots := count * CELL_SIZE.x + (count - 1) * CELL_GAP
	return Vector2(BAR_TITLE_WIDTH + slots + BAR_END_PAD, BAR_HEIGHT)


## Wrap a control in a centred, fixed-size holder.
##
## The holder owns the placement so the control itself is free to be moved by a
## tween. Animating a control whose position the anchors set only fights the
## layout.
func _hold(control: Control, control_size: Vector2, top: float) -> Control:
	var holder := Control.new()
	holder.name = control.name + "Holder"
	holder.mouse_filter = MOUSE_FILTER_IGNORE
	holder.anchor_left = 0.5
	holder.anchor_right = 0.5
	holder.offset_left = -control_size.x / 2.0
	holder.offset_right = control_size.x / 2.0
	holder.offset_top = top
	holder.offset_bottom = top + control_size.y

	control.size = control_size
	control.pivot_offset = control_size / 2.0
	holder.add_child(control)
	return holder


func _build_banner() -> NeonPlate:
	var panel := _neon_panel(LOST_ACCENT)
	panel.name = "ResultBanner"

	# Two mistracked copies behind the text. A screen that cannot quite hold
	# its colours together is the cheapest cyberpunk signal there is, and it
	# gives the glitch on arrival something to pull apart.
	for tint in [GHOST_A, GHOST_B]:
		var ghost := _banner_text(tint)
		ghost.name = "Ghost%d" % _ghosts.size()
		ghost.modulate.a = 0.55
		panel.add_child(ghost)
		_ghosts.append(ghost)

	_banner_label = _banner_text(LOST_ACCENT)
	_banner_label.name = "ResultLabel"
	panel.add_child(_banner_label)
	return panel


func _banner_text(tint: Color) -> Label:
	var label := Label.new()
	label.text = "ROUND LOST"
	label.set_anchors_and_offsets_preset(PRESET_FULL_RECT)
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	label.add_theme_font_size_override("font_size", 66)
	label.add_theme_color_override("font_color", tint)
	label.mouse_filter = MOUSE_FILTER_IGNORE
	return label


func _build_bar(title: String, icon: Texture2D, lit: Color, count: int,
		icons: Array[Control]) -> NeonPlate:
	var panel := _neon_panel(lit)
	panel.name = title.capitalize() + "Bar"

	var label := Label.new()
	label.name = "Title"
	label.text = title
	label.position = Vector2(BAR_PAD, 0)
	label.size = Vector2(BAR_TITLE_WIDTH - BAR_PAD, BAR_HEIGHT)
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	label.add_theme_font_size_override("font_size", 34)
	label.add_theme_color_override("font_color", lit)
	label.mouse_filter = MOUSE_FILTER_IGNORE
	panel.add_child(label)

	var divider := Divider.new()
	divider.name = "Divider"
	divider.accent = lit
	divider.position = Vector2(BAR_TITLE_WIDTH - 22, 0)
	divider.size = Vector2(4, BAR_HEIGHT)
	divider.mouse_filter = MOUSE_FILTER_IGNORE
	panel.add_child(divider)

	var row := HBoxContainer.new()
	row.name = "Icons"
	row.add_theme_constant_override("separation", CELL_GAP)
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.set_anchors_and_offsets_preset(PRESET_FULL_RECT)
	row.offset_left = BAR_TITLE_WIDTH
	row.offset_right = -BAR_END_PAD
	row.mouse_filter = MOUSE_FILTER_IGNORE
	panel.add_child(row)

	for i in count:
		var cell := _build_cell(icon, lit)
		cell.name = "%s%d" % [title.capitalize(), i]
		row.add_child(cell)
		icons.append(cell)
	return panel


## One counter slot: a framed cell holding the icon mask, over a larger washed
## out copy that stands in for a glow. GL compatibility has no bloom to lean on.
##
## The cell shrinks to its own size rather than filling the row, which is what
## keeps the icon and its glow inside the plate.
func _build_cell(icon: Texture2D, lit: Color) -> Control:
	var cell := IconCell.new()
	cell.accent = lit
	cell.custom_minimum_size = CELL_SIZE
	cell.size = CELL_SIZE
	cell.size_flags_vertical = SIZE_SHRINK_CENTER
	cell.pivot_offset = CELL_SIZE / 2.0
	cell.mouse_filter = MOUSE_FILTER_IGNORE
	cell.set_meta("lit", lit)

	var glow_size := ICON_SIZE * GLOW_SCALE
	var glow := TextureRect.new()
	glow.name = "Glow"
	glow.texture = icon
	glow.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	glow.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	glow.size = glow_size
	glow.position = (CELL_SIZE - glow_size) / 2.0
	glow.mouse_filter = MOUSE_FILTER_IGNORE
	glow.modulate = Color(lit, 0.0)
	cell.add_child(glow)

	var mask := TextureRect.new()
	mask.name = "Mask"
	mask.texture = icon
	mask.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	mask.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	mask.size = ICON_SIZE
	mask.position = (CELL_SIZE - ICON_SIZE) / 2.0
	mask.mouse_filter = MOUSE_FILTER_IGNORE
	cell.add_child(mask)
	return cell


func _neon_panel(accent: Color) -> NeonPlate:
	var panel := NeonPlate.new()
	panel.accent = accent
	panel.mouse_filter = MOUSE_FILTER_IGNORE
	return panel


# ============ State ============

## Paint every icon for the counts the screen opens on.
func _fill_icons() -> void:
	for i in _trophies.size():
		_set_icon_lit(_trophies[i], i < wins_before())
	for i in _hearts.size():
		_set_icon_lit(_hearts[i], i < lives_before())


func _set_icon_lit(cell: Control, is_lit: bool) -> void:
	var lit: Color = cell.get_meta("lit")
	cell.get_node("Mask").modulate = lit if is_lit else SPENT
	cell.get_node("Glow").modulate = Color(lit, 0.45 if is_lit else 0.0)
	cell.is_lit = is_lit
	cell.scale = Vector2.ONE


## Jump to the final state: the round applied, everything in place.
func _settle() -> void:
	for tween in _tweens:
		if is_instance_valid(tween):
			tween.kill()
	_tweens.clear()

	_dim.color = Color(DIM_COLOR, DIM_ALPHA)
	for plate in [_banner, _wins_bar, _tries_bar]:
		plate.position = Vector2.ZERO
		plate.modulate.a = 1.0
		plate.sweep = -1.0
	_ghosts[0].position.x = -3.0
	_ghosts[1].position.x = 3.0
	_prompt.modulate.a = 1.0

	for i in _trophies.size():
		_set_icon_lit(_trophies[i], i < wins)
	for i in _hearts.size():
		_set_icon_lit(_hearts[i], i < lives)

	settled = true


# ============ Animation ============

func _animate() -> void:
	_sparkles.visible = true
	_sting.play()

	_dim.color = Color(DIM_COLOR, 0.0)
	_banner.position = Vector2(0, -460)
	_wins_bar.position = Vector2(-1780, 0)
	_tries_bar.position = Vector2(1780, 0)

	var fade := _tween()
	fade.tween_property(_dim, "color:a", DIM_ALPHA, Presentation.delay(DIM_FADE))

	var drop := _tween()
	drop.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	drop.tween_property(_banner, "position", Vector2.ZERO, Presentation.delay(BANNER_DROP))
	drop.tween_callback(_glitch_banner)

	_slide_in(_wins_bar, WINS_SLIDE_AT)
	_slide_in(_tries_bar, TRIES_SLIDE_AT)

	var prompt := _tween()
	prompt.tween_interval(Presentation.delay(PROMPT_AT))
	prompt.tween_property(_prompt, "modulate:a", 1.0, Presentation.delay(0.4))
	# A slow breath, so the prompt reads as waiting rather than as a static
	# caption the player has already dealt with.
	prompt.set_loops()
	prompt.tween_property(_prompt, "modulate:a", 0.4, Presentation.delay(0.9))
	prompt.tween_property(_prompt, "modulate:a", 1.0, Presentation.delay(0.9))

	var change := _tween()
	change.tween_interval(Presentation.delay(CHANGE_AT))
	change.tween_callback(_play_change)


func _slide_in(bar: NeonPlate, at: float) -> void:
	var tween := _tween()
	tween.tween_interval(Presentation.delay(at))
	tween.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	tween.tween_property(bar, "position", Vector2.ZERO, Presentation.delay(BAR_SLIDE))
	# A band of light runs down the plate as it arrives, the way a screen
	# refreshes rather than the way a sign lights up.
	tween.tween_callback(func(): bar.sweep = 0.0)
	tween.tween_property(bar, "sweep", 1.0, Presentation.delay(SWEEP_TIME))
	tween.tween_callback(func(): bar.sweep = -1.0)


## Pull the banner apart for a few frames as it lands: the plate slips
## sideways and the two colour ghosts slip further, then it all snaps back.
func _glitch_banner() -> void:
	var glitch := _tween()
	for offset in [16.0, -12.0, 7.0, -3.0]:
		glitch.set_parallel(true)
		glitch.tween_property(_ghosts[0], "position:x", -offset,
			Presentation.delay(GLITCH_STEP))
		glitch.tween_property(_ghosts[1], "position:x", offset,
			Presentation.delay(GLITCH_STEP))
		glitch.tween_property(_banner, "position:x", offset * 0.35,
			Presentation.delay(GLITCH_STEP))
		glitch.chain()
	# It never fully re-converges. A permanent hair of separation keeps the
	# text reading as a screen rather than as a printed word.
	glitch.set_parallel(true)
	glitch.tween_property(_ghosts[0], "position:x", -3.0, Presentation.delay(0.12))
	glitch.tween_property(_ghosts[1], "position:x", 3.0, Presentation.delay(0.12))
	glitch.tween_property(_banner, "position:x", 0.0, Presentation.delay(0.12))


## Move the one icon this round changed: light the trophy, or put out the heart.
func _play_change() -> void:
	var index := changed_icon_index()
	if index == -1:
		settled = true
		return

	var cell: Control = (_trophies if won else _hearts)[index]
	var lit: Color = cell.get_meta("lit")
	var mask: TextureRect = cell.get_node("Mask")
	var glow: TextureRect = cell.get_node("Glow")

	# Both outcomes flash white first. What differs is where the icon lands.
	var end_mask := lit if won else SPENT
	var end_glow := Color(lit, 0.45 if won else 0.0)
	cell.is_lit = won

	var pop := _tween()
	pop.set_parallel(true)
	pop.tween_property(cell, "scale", Vector2(POP_SCALE, POP_SCALE),
		Presentation.delay(CHANGE_POP)).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	pop.tween_property(mask, "modulate", Color.WHITE, Presentation.delay(CHANGE_POP))
	pop.tween_property(glow, "modulate", Color(lit, 1.0), Presentation.delay(CHANGE_POP))

	var settle := _tween()
	settle.tween_interval(Presentation.delay(CHANGE_POP))
	settle.set_parallel(true)
	settle.tween_property(cell, "scale", Vector2.ONE, Presentation.delay(CHANGE_SETTLE))
	settle.tween_property(mask, "modulate", end_mask, Presentation.delay(CHANGE_SETTLE))
	settle.tween_property(glow, "modulate", end_glow, Presentation.delay(CHANGE_SETTLE))
	settle.chain().tween_callback(func(): settled = true)

	# A win lights its bar up, a loss knocks it. Same beat, opposite reading.
	if won:
		_flash(_wins_bar)
	else:
		_shake(_tries_bar)

	_sparkles.burst(cell.get_global_rect().get_center(), lit)


## Knock a bar sideways and let it settle, for the try just spent.
func _shake(bar: NeonPlate) -> void:
	var shake := _tween()
	for offset in [14.0, -11.0, 8.0, -5.0, 0.0]:
		shake.tween_property(bar, "position:x", offset, Presentation.delay(CHANGE_SHAKE))


## Run the plate's outline up to white and back, for the win just banked.
func _flash(bar: NeonPlate) -> void:
	var accent: Color = bar.accent
	var flash := _tween()
	flash.tween_property(bar, "accent", Color.WHITE, Presentation.delay(CHANGE_POP))
	flash.tween_property(bar, "accent", accent, Presentation.delay(CHANGE_SETTLE * 2))


func _tween() -> Tween:
	var tween := create_tween()
	_tweens = _tweens.filter(func(t): return is_instance_valid(t) and t.is_running())
	_tweens.append(tween)
	return tween


## A hard-edged HUD plate: pointed ends, a notch bitten out of the top edge,
## scanlines across the fill and a double outline.
##
## Drawn rather than styled, because a StyleBoxFlat only does rounded corners
## and GL compatibility has no bloom to make an edge glow, so the glow here is
## a few outlines stepped outwards.
class NeonPlate extends Control:
	const SLANT := 30.0
	const NOTCH_AT := 0.62
	const NOTCH_WIDTH := 54.0
	const NOTCH_DEPTH := 10.0
	const INNER_INSET := 9.0
	const SCANLINE_GAP := 5.0
	const GLOW_STEPS := 5
	const GLOW_REACH := 15.0
	const FILL := Color(0.045, 0.03, 0.13, 0.93)

	var accent: Color = Color.WHITE:
		set(value):
			accent = value
			queue_redraw()

	## Where a band of light sits on the plate, 0 at the top and 1 at the
	## bottom. Negative means no band.
	var sweep: float = -1.0:
		set(value):
			sweep = value
			queue_redraw()

	func _notification(what: int) -> void:
		if what == NOTIFICATION_RESIZED:
			queue_redraw()

	func _draw() -> void:
		for step in range(GLOW_STEPS, 0, -1):
			var reach := GLOW_REACH * step / GLOW_STEPS
			draw_polyline(_shape(-reach), Color(accent, 0.07), 2.0 + reach, true)

		draw_colored_polygon(_shape(0.0), FILL)
		_draw_scanlines()
		_draw_sweep()
		draw_polyline(_shape(INNER_INSET), Color(accent, 0.28), 1.0, true)
		draw_polyline(_shape(0.0), accent, 3.0, true)

	## The plate outline, inset by `inset` on every side. A negative inset grows
	## it, which is how the glow rings are drawn.
	func _shape(inset: float) -> PackedVector2Array:
		var x := inset
		var y := inset
		var w := size.x - inset * 2.0
		var h := size.y - inset * 2.0
		var points := PackedVector2Array()
		points.append(Vector2(x + SLANT, y))

		var notch := x + w * NOTCH_AT
		if notch + NOTCH_WIDTH < x + w - SLANT - 12.0:
			points.append(Vector2(notch, y))
			points.append(Vector2(notch + 10.0, y + NOTCH_DEPTH))
			points.append(Vector2(notch + NOTCH_WIDTH - 10.0, y + NOTCH_DEPTH))
			points.append(Vector2(notch + NOTCH_WIDTH, y))

		points.append(Vector2(x + w - SLANT, y))
		points.append(Vector2(x + w, y + h / 2.0))
		points.append(Vector2(x + w - SLANT, y + h))
		points.append(Vector2(x + SLANT, y + h))
		points.append(Vector2(x, y + h / 2.0))
		points.append(Vector2(x + SLANT, y))
		return points

	## How far in the pointed ends have closed at this height.
	func _span(y: float) -> Vector2:
		var half := size.y / 2.0
		var inset := SLANT * absf(y - half) / half
		return Vector2(inset, size.x - inset)

	func _draw_scanlines() -> void:
		var y := SCANLINE_GAP
		while y < size.y:
			var span := _span(y)
			draw_line(Vector2(span.x, y), Vector2(span.y, y), Color(accent, 0.05), 1.0)
			y += SCANLINE_GAP

	func _draw_sweep() -> void:
		if sweep < 0.0:
			return
		var at := sweep * size.y
		for offset in range(-4, 5):
			var y := at + offset * 2.0
			if y < 0.0 or y > size.y:
				continue
			var span := _span(y)
			draw_line(Vector2(span.x, y), Vector2(span.y, y),
				Color(accent, 0.22 * (1.0 - absf(offset) / 5.0)), 2.0)


## The frame around one counter slot. A lit slot gets a wash of colour behind
## the icon and brighter corners, so a filled counter reads even out of the
## corner of the eye.
class IconCell extends Control:
	const CUT := 11.0
	const TICK := 13.0

	var accent: Color = Color.WHITE:
		set(value):
			accent = value
			queue_redraw()

	var is_lit: bool = false:
		set(value):
			is_lit = value
			queue_redraw()

	func _draw() -> void:
		var w := size.x
		var h := size.y
		# A rectangle with two opposite corners cut off, which reads as a
		# machined part rather than as a box.
		var outline := PackedVector2Array([
			Vector2(CUT, 0), Vector2(w, 0), Vector2(w, h - CUT),
			Vector2(w - CUT, h), Vector2(0, h), Vector2(0, CUT), Vector2(CUT, 0),
		])
		if is_lit:
			draw_colored_polygon(outline, Color(accent, 0.10))
		draw_polyline(outline, Color(accent, 0.42 if is_lit else 0.13), 1.0, true)

		# Corner ticks at the two square corners, brighter than the frame.
		var strength := Color(accent, 0.85 if is_lit else 0.22)
		draw_line(Vector2(w - TICK, 0), Vector2(w, 0), strength, 2.0)
		draw_line(Vector2(w, 0), Vector2(w, TICK), strength, 2.0)
		draw_line(Vector2(0, h - TICK), Vector2(0, h), strength, 2.0)
		draw_line(Vector2(0, h), Vector2(TICK, h), strength, 2.0)


## The rule between a bar's title and its slots.
class Divider extends Control:
	var accent: Color = Color.WHITE

	func _draw() -> void:
		var h := size.y
		draw_line(Vector2(1, 18), Vector2(1, h - 18), Color(accent, 0.30), 2.0)
		draw_line(Vector2(1, h / 2.0 - 6), Vector2(1, h / 2.0 + 6), Color(accent, 0.9), 4.0)


## The drifting four-point stars that keep the screen alive while it waits.
class Sparkles extends Control:
	const COUNT := 34
	const RISE := 26.0

	var _seeds: Array[Dictionary] = []
	var _bursts: Array[Dictionary] = []
	var _clock: float = 0.0

	func _ready() -> void:
		var rng := RandomNumberGenerator.new()
		rng.seed = 20260818
		for i in COUNT:
			_seeds.append({
				"at": Vector2(rng.randf(), rng.randf()),
				"size": rng.randf_range(6.0, 16.0),
				"speed": rng.randf_range(0.5, 1.4),
				"phase": rng.randf() * TAU,
				"tint": Color(0.55, 0.95, 1.0) if i % 3 else Color(1.0, 0.85, 0.5),
			})

	func _process(delta: float) -> void:
		_clock += delta
		for burst in _bursts:
			burst["age"] += delta
		_bursts = _bursts.filter(func(b): return b["age"] < b["life"])
		queue_redraw()

	## Throw sparks off a point, for the icon that just changed. The spread is
	## uneven on purpose: an even ring reads as a clock face, not as a burst.
	func burst(at: Vector2, tint: Color) -> void:
		var rng := RandomNumberGenerator.new()
		rng.seed = 5150
		for i in 14:
			var angle := TAU * i / 14.0 + rng.randf_range(-0.2, 0.2)
			_bursts.append({
				"from": at,
				"heading": Vector2.RIGHT.rotated(angle),
				"reach": rng.randf_range(80.0, 170.0),
				"tint": tint,
				"age": 0.0,
				"life": rng.randf_range(0.55, 0.85),
			})

	func _draw() -> void:
		for seed_data in _seeds:
			var at: Vector2 = seed_data["at"] * size
			# Drift upwards and wrap, so the field never empties.
			at.y = fposmod(at.y - _clock * RISE * seed_data["speed"], size.y)
			var twinkle: float = 0.5 + 0.5 * sin(_clock * 2.6 * seed_data["speed"] + seed_data["phase"])
			_draw_star(at, seed_data["size"] * (0.4 + 0.6 * twinkle),
				Color(seed_data["tint"], 0.25 + 0.55 * twinkle))

		for burst in _bursts:
			var progress: float = burst["age"] / burst["life"]
			var reach: float = 20.0 + burst["reach"] * progress
			_draw_star(burst["from"] + burst["heading"] * reach,
				15.0 * (1.0 - progress), Color(burst["tint"], 1.0 - progress))

	func _draw_star(at: Vector2, radius: float, tint: Color) -> void:
		if radius <= 0.5:
			return
		var waist := radius * 0.24
		draw_colored_polygon(PackedVector2Array([
			at + Vector2(0, -radius),
			at + Vector2(waist, -waist),
			at + Vector2(radius, 0),
			at + Vector2(waist, waist),
			at + Vector2(0, radius),
			at + Vector2(-waist, waist),
			at + Vector2(-radius, 0),
			at + Vector2(-waist, -waist),
		]), tint)
