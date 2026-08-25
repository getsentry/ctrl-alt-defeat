extends Control
class_name StorageBin

## The chest, as a box things are thrown into rather than a tray of squares.
##
## An item in the chest is off the grid. The server keeps no place and no
## facing for one -- PlacedItem.stored() throws both away -- so where it lies
## is the client's business alone, and it lies where it lands.
##
## Godot's own 2D physics does the falling, the bouncing and the pushing apart.
## What is here is a body for each item, three walls, the rules for how hard a
## thing may be thrown, and a net under the whole lot: anything that gets out
## of the room is put back in the tray.

const APITypes = preload("res://scripts/api_types.gd")
const ItemVisual = preload("res://scripts/item_visual.gd")
const InventoryGrid = preload("res://scripts/inventory_grid.gd")

# ============ How it throws ============

## How much of the pointer's speed an item keeps when it is let go of.
const THROW_KEEP := 0.45
## The fastest an item may be thrown. A flick across the screen is easy to do
## by accident, and an item that leaves at the speed of the pointer is out of
## the room before the player has seen where it went.
const THROW_MAX := 520.0
## The fastest an item may be thrown upwards, which is less. Throwing up is
## the one direction where the item leaves the tray for a long time, and there
## is nothing to see while it is gone.
const THROW_UP_MAX := 200.0
## How much spin a throw puts on an item, in radians per second per pixel of
## sideways speed. Enough to tumble, not enough to spin like a top.
const THROW_SPIN := 0.012
## How much an item turns as it falls, however it got there. Things dropped in
## a tray land any way up, and a row of them all square to the tray reads as a
## shelf rather than as a heap.
const TUMBLE := 3.0

# ============ How it falls ============

## Gravity, as a share of the project's own. The tray is a couple of hundred
## pixels deep, so full gravity drops an item through it in a blink.
const FALL := 0.7
const AIR_DRAG := 0.4
const SPIN_DRAG := 2.0
const BOUNCE := 0.12
const GRIP := 0.9
## How thick the walls of the tray are. They are only there to be hit, so this
## is simply enough that nothing tunnels through at throwing speed.
const WALL := 24.0
## How far the walls reach above the tray when there is no screen to measure
## against. The picture shows walls the height of the tray; these go on up to
## the top of the screen, where the roof is, so a thing thrown in the chest
## stays over the chest and in sight however hard it is thrown.
const WALL_UP := 1400.0
## The fastest anything in the chest may travel, whatever put it in motion.
## A throw is already held back, but the physics can shove two items apart
## hard when one lands on top of another, and one shove used to be enough to
## send an item off round the room.
const MAX_SPEED := 700.0
const MAX_SPIN := 12.0

## How far out of the chest a thing may get before it is fetched back, to
## either side of the tray and below the floor. Above is the roof itself:
## nothing has any business being over it, so anything that is has gone wrong.
## The walls and the roof already hold everything in, so this is a net under
## the physics rather than a rule of the game.
const ROOM_LEFT := 260.0
const ROOM_RIGHT := 260.0
const ROOM_DOWN := 90.0

# ============ What it holds ============

## The opening of the tray, in this control's own coordinates. The walls stand
## on it, and it is where anything fetched back is dropped in.
var tray := Rect2()
## How big items are drawn. The tray sets this from its opening, so what is in
## the chest is drawn smaller than what is on the grid.
var cell_size := 30.0
var cell_spacing := 1.0
var read_only := false

## Where an item taken out of the chest can be dropped. The owner hands both
## over, the same as it does for the grid: the chest only needs somewhere to
## test the pointer against.
var sell_zone: Control = null
var grid_zone: InventoryGrid = null

## An item in the chest, and the body carrying it about.
class Lying extends RefCounted:
	var item: APITypes.Item
	var body: RigidBody2D
	var visual: ItemVisual

	func _init(what: APITypes.Item, carried_by: RigidBody2D, drawn: ItemVisual):
		item = what
		body = carried_by
		visual = drawn


# What lies in the chest, keyed by item id.
var _lying: Dictionary[String, Lying] = {}
var _walls: StaticBody2D = null
# Everything between the walls, from the floor of the tray to well above the
# screen. Whatever is let go of in there falls into the chest.
var _catch_zone: Control = null

# What has been picked out of the chest and is following the pointer. It is
# still in the chest as far as the server is concerned -- nothing has been
# asked of it yet -- so it comes back here unless it is dropped somewhere that
# takes it.
var _dragged: APITypes.Item = null
var _dragged_visual: ItemVisual = null
## What the pointer was last seen doing, so a release can throw. Only motion
## the chest is sent counts, which is the motion of its own drag.
var _pointer_speed := Vector2.ZERO
## Which item the pointer is resting on. The artwork does not answer the
## pointer itself here, so the tray tells it when it is being looked at.
var _hovered := ""
## What the owner is holding in hand, if anything. The hand is a shortcut and
## not a place, so the item is in the chest as well: it is not drawn here, and
## nothing else may be picked up while it is out.
var _in_hand := ""

signal item_sold(item_data)
## Dragged out of the chest and dropped on the main grid. Carries where it was
## dropped, because the chest cannot work out a square on someone else's grid.
signal item_unstored(item_data, global_pos)
signal drag_started(item_data)
signal drag_ended()


func _ready() -> void:
	# The pointer is answered in _input rather than here, because what is in
	# the chest can be anywhere between the walls -- falling down the screen,
	# well above this box -- and a control only hears about its own square.
	mouse_filter = Control.MOUSE_FILTER_IGNORE


func configure(opening: Rect2, drawn_at: float, spacing: float = 1.0) -> void:
	"""Set the chest up around the opening of its tray"""
	tray = opening
	cell_size = drawn_at
	cell_spacing = spacing
	_build_walls()


func _build_walls() -> void:
	"""A floor and two sides, so what is thrown in stays in.

	The top is open. An item can be thrown out of it, and gravity brings it
	back; that is the whole trick.
	"""
	if is_instance_valid(_walls):
		_walls.queue_free()

	_walls = StaticBody2D.new()
	_walls.name = "Walls"
	var stone := PhysicsMaterial.new()
	stone.bounce = BOUNCE
	stone.friction = GRIP
	_walls.physics_material_override = stone

	_walls.add_child(_wall(
		Vector2(tray.get_center().x, tray.end.y + WALL / 2.0),
		Vector2(tray.size.x + 2 * WALL, WALL)))
	# The sides run from the floor of the tray to the top of the screen, and
	# the roof closes it there. Nothing thrown in the chest can land anywhere
	# but in it, and nothing can be thrown out of sight.
	var roof := _roof_height()
	var side := Vector2(WALL, tray.end.y - roof)
	var middle := tray.end.y - side.y / 2.0
	_walls.add_child(_wall(Vector2(tray.position.x - WALL / 2.0, middle), side))
	_walls.add_child(_wall(Vector2(tray.end.x + WALL / 2.0, middle), side))
	_walls.add_child(_wall(
		Vector2(tray.get_center().x, roof - WALL / 2.0),
		Vector2(tray.size.x + 2 * WALL, WALL)))
	add_child(_walls)

	_catch_zone = Control.new()
	_catch_zone.name = "CatchZone"
	_catch_zone.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_catch_zone.position = Vector2(tray.position.x, roof)
	_catch_zone.size = Vector2(tray.size.x, side.y)
	add_child(_catch_zone)


func _roof_height() -> float:
	"""Where the roof goes, measured in the chest's own coordinates.

	The top of the screen. An item that leaves the screen is gone as far as the
	player is concerned, however faithfully it is still being simulated up
	there, so the room it is thrown about in is the room that can be seen.
	"""
	if not is_inside_tree():
		return tray.end.y - WALL_UP
	return (get_global_transform().affine_inverse() * Vector2.ZERO).y


func _wall(at: Vector2, size: Vector2) -> CollisionShape2D:
	var shape := CollisionShape2D.new()
	var box := RectangleShape2D.new()
	box.size = size
	shape.shape = box
	shape.position = at
	return shape


# ============ What is in it ============

func show_items(in_chest: Array, held_id: String = "") -> void:
	"""Draw what the server says is in the chest.

	Nothing that is already lying here is moved. An item is put down where it
	fell and stays there, so a redraw -- and the server answers every move with
	one -- must not tidy the tray up behind the player.
	"""
	_in_hand = held_id

	var still_here: Dictionary[String, bool] = {}
	for item in in_chest:
		if item.id == held_id or item.id == _dragged_id():
			continue
		still_here[item.id] = true
		if not _lying.has(item.id):
			_drop_in(item)

	for id in _lying.keys():
		if not still_here.has(id):
			_take_out(id)


func ids() -> Array:
	"""The ids of what is lying in the chest, in no particular order"""
	return _lying.keys()


func count() -> int:
	return _lying.size()


func drawn(item_id: String) -> ItemVisual:
	"""The artwork for an item lying in the chest, or nothing"""
	return _lying[item_id].visual if _lying.has(item_id) else null


func dragged_visual() -> ItemVisual:
	"""The artwork for what has been picked out of the chest, or nothing"""
	return _dragged_visual


func where_is(item_id: String) -> Vector2:
	"""Where an item lies, in this control's own coordinates"""
	if not _lying.has(item_id):
		return Vector2.INF
	return _lying[item_id].body.position


func _drop_in(item: APITypes.Item, at := Vector2.INF, thrown := Vector2.ZERO) -> void:
	"""Put an item in the chest, falling from wherever it came in.

	Told nowhere in particular, it falls in from above the tray. That is what
	happens to an item the player did not put there: one the server set down
	because a container move left it with nowhere to stand, or one that was
	already in the chest when the game was loaded.
	"""
	# An item in the chest faces the way the catalogue draws it. The server
	# keeps no facing for a stored item, so one drawn turned here would be
	# picked up again facing a way the server has never heard of.
	var lying := _unturned(item)

	var visual := ItemVisual.new()
	visual.enable_tooltip = true
	visual.setup(lying, cell_size, cell_spacing)
	# After setup, which sets this itself. The pointer is answered by the tray
	# and not by the artwork: what is drawn hangs off a body that turns, and a
	# turned Control takes the pointer in its own square rather than where it
	# looks. The tray hovers and picks up by asking which body a point is in.
	visual.mouse_filter = Control.MOUSE_FILTER_IGNORE
	visual.position = -visual.size / 2.0

	var body := RigidBody2D.new()
	# Nothing in the chest is ever allowed to fall asleep. A body that sleeps
	# stops being pulled down, and two of them that arrived inside each other
	# can settle each other still while they are both in mid-air -- which looks
	# exactly like an item hanging in space, because that is what it is.
	body.can_sleep = false
	body.gravity_scale = FALL
	body.linear_damp = AIR_DRAG
	body.angular_damp = SPIN_DRAG
	var stuff := PhysicsMaterial.new()
	stuff.bounce = BOUNCE
	stuff.friction = GRIP
	body.physics_material_override = stuff

	var shape := CollisionShape2D.new()
	var box := RectangleShape2D.new()
	box.size = visual.size
	shape.shape = box
	body.add_child(shape)
	body.add_child(visual)

	body.position = _inside(
		at if at != Vector2.INF else _falls_from(visual.size), visual.size)
	body.linear_velocity = thrown
	# A little spin whatever happens, so that a trayful does not come to rest
	# standing to attention in a row.
	body.angular_velocity = thrown.x * THROW_SPIN + randf_range(-TUMBLE, TUMBLE)
	add_child(body)

	_lying[item.id] = Lying.new(lying, body, visual)


func _unturned(item: APITypes.Item) -> APITypes.Item:
	"""The same item, facing the way the catalogue draws it"""
	return item if item.facing() == 0 else item.placed_at(Vector2i.ZERO, 0)


func _inside(at: Vector2, item_size: Vector2) -> Vector2:
	"""The nearest place to this that an item of this size fits in the chest.

	Where a thing lands is not always somewhere it can be: an item can be let
	go of over the roof, and one dropped in there would land on top of the
	roof and stay there. So the chest takes it at the nearest place inside
	itself instead.
	"""
	var half := item_size / 2.0
	if item_size.x >= tray.size.x:
		return Vector2(tray.get_center().x, at.y)
	return Vector2(
		clampf(at.x, tray.position.x + half.x, tray.end.x - half.x),
		clampf(at.y, _roof_height() + half.y, tray.end.y - half.y))


func _falls_from(item_size: Vector2, ignoring := "") -> Vector2:
	"""Somewhere above whatever is in the tray, for an item nobody threw.

	Between the walls, so that nothing starts inside one: an item as wide as
	the tray has nowhere to vary, so it falls down the middle. Above the
	highest thing already in the chest, so that nothing starts inside anything
	else either -- a chestful arriving at once would otherwise appear as one
	heap of items in the same place, which the physics has to shove apart
	before it can do anything else.
	"""
	var margin := item_size.x / 2.0 + WALL / 2.0
	var across := tray.get_center().x
	if margin * 2 < tray.size.x:
		across = randf_range(tray.position.x + margin, tray.end.x - margin)

	# Whatever is being put back does not count as something to clear: an item
	# fetched down from the ceiling would otherwise be dropped in from just
	# above the ceiling, which is where it already was.
	var clear := tray.position.y
	for id in _lying:
		if id == ignoring:
			continue
		clear = min(clear, _lying[id].body.position.y - _lying[id].visual.size.y / 2.0)
	return Vector2(across, clear - item_size.y)


func _take_out(item_id: String) -> void:
	"""Take an item out of the chest and stop drawing it"""
	if not _lying.has(item_id):
		return
	# Its tooltip is parented to the root rather than to the artwork, so it
	# outlives what it describes unless it is put away first.
	_lying[item_id].visual.hover_ended()
	if _hovered == item_id:
		_hovered = ""
	_lying[item_id].body.queue_free()
	_lying.erase(item_id)


func _dragged_id() -> String:
	return _dragged.id if _dragged else ""


# ============ Catching what is dropped in ============

func catch(item: APITypes.Item, from: Vector2, thrown := Vector2.ZERO) -> void:
	"""An item has been let go of over the chest, at this place on the screen.

	Used for an item dropped in off the grid, which is let go of over the tray
	and falls from there rather than from above it.
	"""
	if _lying.has(item.id):
		return
	_drop_in(item, get_global_transform().affine_inverse() * from, _throwable(thrown))


func _throwable(speed: Vector2) -> Vector2:
	"""How fast an item may leave the hand, given how fast the pointer left it.

	A flick is easy to do by accident, and a hard throw takes the item out of
	sight. Up is held back hardest, because up is the direction where there is
	nothing to watch until it comes down again.
	"""
	var thrown := (speed * THROW_KEEP).limit_length(THROW_MAX)
	thrown.y = max(thrown.y, -THROW_UP_MAX)
	return thrown


# ============ Picking things back up ============

func item_at(global_point: Vector2) -> APITypes.Item:
	"""What lies under this point on the screen, or nothing.

	The topmost first, so a click picks up what the player can see rather than
	what is buried under it.
	"""
	var ordered := _lying.values()
	ordered.reverse()
	for lying in ordered:
		var local: Vector2 = lying.body.get_global_transform().affine_inverse() * global_point
		if Rect2(-lying.visual.size / 2.0, lying.visual.size).has_point(local):
			return lying.item
	return null


func pick_up(item: APITypes.Item, at: Vector2) -> void:
	"""Take an item out of the chest and let it follow the pointer.

	It stays the server's business only when it lands somewhere: until then it
	is still in the chest, and letting go of it anywhere else drops it back in.
	"""
	if read_only or _dragged:
		return

	_take_out(item.id)
	_dragged = item
	_dragged_visual = ItemVisual.new()
	_dragged_visual.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_dragged_visual.setup(item, cell_size, cell_spacing)
	_dragged_visual.z_index = 10
	add_child(_dragged_visual)
	_follow(at)
	_pointer_speed = Vector2.ZERO
	drag_started.emit(item)


func dragged() -> APITypes.Item:
	"""What has been picked out of the chest, if anything"""
	return _dragged


func turn_dragged(quarters: int, pointer: Vector2) -> bool:
	"""Turn what was picked out of the chest, and say whether there was one.

	The pointer is told, not read, the same as for one on the grid.

	Worth turning even though the chest keeps no facing: an item is often
	picked out of the chest to be put on the grid, and turning it on the way is
	quicker than putting it down and turning it there.
	"""
	if not _dragged:
		return false
	_dragged = _dragged.turned(quarters)
	var at := pointer
	if is_instance_valid(_dragged_visual):
		_dragged_visual.redraw_as(_dragged)
		# Turned, it hangs from a different square of itself, so it is hung
		# again -- and hanging it draws the mark for the squares it covers now.
		_follow(at)
	else:
		# It covers different squares now, so the mark is drawn again for them.
		mark_where_it_would_land(at)
	return true


func release_at(pointer: Vector2, thrown := Vector2.ZERO) -> void:
	"""Let go of what was picked out of the chest, wherever the pointer is.

	Takes where and how fast rather than reading the pointer, so a throw can be
	asked about without a mouse.
	"""
	if not _dragged:
		return

	var item := _dragged
	_dragged = null
	if is_instance_valid(_dragged_visual):
		_dragged_visual.queue_free()
	_dragged_visual = null
	if is_instance_valid(grid_zone):
		grid_zone.hide_hover_preview()
	drag_ended.emit()

	if sell_zone and sell_zone.get_global_rect().has_point(pointer):
		item_sold.emit(item)
		return

	if grid_zone and grid_zone.get_global_rect().has_point(pointer):
		item_unstored.emit(item, pointer)
		return

	# Nowhere that takes it, so it goes back in the chest -- thrown, if the
	# pointer was moving.
	_drop_in(
		item,
		get_global_transform().affine_inverse() * pointer,
		_throwable(thrown))


# ============ The net under it all ============

func catch_zone() -> Control:
	"""The whole column over the chest, for a drop to be tested against.

	Handed out rather than described, because the grid holds a zone and tests
	the pointer against it itself.
	"""
	return _catch_zone


func catches(global_point: Vector2) -> bool:
	"""Whether something let go of here falls into the chest.

	Anywhere between the walls counts, however high up: the walls reach past
	the top of the screen, so a thing let go of over the chest has nowhere to
	fall but into it. Aiming at the opening itself is a small target, and this
	is the same rule the physics already follows.
	"""
	return is_instance_valid(_catch_zone) \
		and _catch_zone.get_global_rect().has_point(global_point)


func hold_the_speed_down() -> void:
	"""Keep everything in the chest to a speed the eye can follow.

	The throw is held back where it leaves the hand, but that is not the only
	thing that puts an item in motion: two items landing inside each other are
	shoved apart by however far in they got, and that shove has no limit of its
	own. One of those used to be enough to send an item off round the room.
	"""
	for lying in _lying.values():
		var body: RigidBody2D = lying.body
		if body.linear_velocity.length() > MAX_SPEED:
			body.linear_velocity = body.linear_velocity.limit_length(MAX_SPEED)
		body.angular_velocity = clampf(body.angular_velocity, -MAX_SPIN, MAX_SPIN)


func keep_in_bounds() -> void:
	"""Fetch back anything that has got out of the room.

	A throw can put an item over a wall, and there is no floor outside the
	tray for it to land on. Rather than let it fall for ever, it is dropped
	back in. Public so that it can be asked for rather than waited for.
	"""
	var room := _room()
	for id in _lying:
		var lying: Lying = _lying[id]
		var at: Vector2 = lying.body.position
		if room.has_point(at) and is_finite(at.x) and is_finite(at.y):
			continue
		lying.body.linear_velocity = Vector2.ZERO
		lying.body.angular_velocity = 0.0
		lying.body.rotation = 0.0
		lying.body.position = _falls_from(lying.visual.size, id)


func _room() -> Rect2:
	"""Where a thing in the chest may be. Outside it, something has gone wrong.

	It reaches up to the roof and no further. Resting against the roof is a
	perfectly good place to be, and a body doing it has its middle a good way
	below the roof line, so nothing in the chest is ever above this.
	"""
	var top := _roof_height()
	return Rect2(
		tray.position.x - ROOM_LEFT, top,
		tray.size.x + ROOM_LEFT + ROOM_RIGHT, tray.end.y + ROOM_DOWN - top)


func _physics_process(_delta: float) -> void:
	hold_the_speed_down()
	keep_in_bounds()


func _process(_delta: float) -> void:
	if _dragged and is_instance_valid(_dragged_visual):
		_follow(get_global_mouse_position())


func _follow(pointer: Vector2) -> void:
	"""Put what is being dragged under the pointer, but keep it on the screen.

	The pointer can leave the window while the button is held, and an item
	that goes with it is being carried somewhere the player cannot see. It
	stops at the edge instead, which also means it can never be let go of
	anywhere but on the screen.
	"""
	if not is_instance_valid(_dragged_visual):
		return
	# Under the middle of its own artwork, which is where a hand holds a thing
	# nobody picked a square on.
	var corner := pointer - _dragged_visual.size / 2.0
	_dragged_visual.position = get_global_transform().affine_inverse() \
		* on_the_screen(corner, _dragged_visual.size)
	mark_where_it_would_land(pointer)


func mark_where_it_would_land(pointer: Vector2) -> void:
	"""Show the square an item out of the chest would land on, and whether it can.

	An item is picked out of the chest to be put on the grid as often as not,
	and without the mark the player is aiming an item at a square they cannot
	see. The grid draws it, because the square is one of the grid's own.
	"""
	if not is_instance_valid(grid_zone):
		return
	if not _dragged or not grid_zone.get_global_rect().has_point(pointer):
		grid_zone.hide_hover_preview()
		return

	# Where the artwork is, rather than where the pointer is: those are the
	# same square only for an item one square across.
	var local: Vector2 = \
		grid_zone.get_global_transform().affine_inverse() * pointer
	grid_zone.show_hover_preview_for_shop(_dragged, grid_zone.square_for_corner(
		grid_zone.carried_corner(local, _dragged.turned_shape())))


func on_the_screen(corner: Vector2, item_size: Vector2) -> Vector2:
	"""The nearest place to this corner where an item of this size is in view.

	The corner rather than the middle, because an item is carried by whichever
	of its own squares was picked up, and the middle of its artwork is not
	where the pointer is.
	"""
	var view := get_viewport_rect()
	return corner.clamp(
		view.position, (view.end - item_size).max(view.position))


func _input(event: InputEvent) -> void:
	"""Pick something out of the chest, carry it, and let go of it again.

	Anywhere on the screen, not only over the tray: a thing thrown up is in the
	air for a second or two and can be caught while it is up there. Nothing is
	taken from the pointer unless there is something under it to take, so the
	shop and the buttons keep their clicks.
	"""
	if event is InputEventMouseMotion:
		if _dragged:
			_pointer_speed = event.velocity
		else:
			_hover(event.global_position)
		return

	if read_only or not event is InputEventMouseButton:
		return
	if event.button_index != MOUSE_BUTTON_LEFT:
		return

	if event.pressed:
		# One hand. Something is already out of the chest and following the
		# pointer, so this press is what puts that down rather than what picks
		# up another -- and the owner has a hand of its own, for an item a
		# container move left with nowhere to stand.
		if _dragged or _in_hand != "":
			return
		var under := item_at(event.global_position)
		if under:
			pick_up(under, event.global_position)
			get_viewport().set_input_as_handled()
		return

	if _dragged:
		release_at(event.global_position, _pointer_speed)
		get_viewport().set_input_as_handled()


func _hover(pointer: Vector2) -> void:
	"""Say which item the pointer is resting on, so it can describe itself.

	The tooltip belongs to the artwork, and the artwork is not what the pointer
	meets: the chest answers for the lot of it. So the chest has to say when
	the pointer arrives and when it leaves, and it hears about every movement
	of the pointer for exactly that reason.
	"""
	var under := item_at(pointer)
	var id: String = under.id if under else ""
	if id == _hovered:
		return
	if _lying.has(_hovered):
		_lying[_hovered].visual.hover_ended()
	_hovered = id
	if _lying.has(id):
		_lying[id].visual.hover_started()



