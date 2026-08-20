extends TextureRect
class_name ContactShadow

## The smudge of dark under a standing character.
##
## Without one a character is a cut-out laid over the picture: nothing says
## which floor it is standing on, or whether it is standing at all. A soft
## ellipse under the feet is the whole trick.
##
## It measures the character rather than being placed by hand, so that it stays
## under the feet when the artwork changes, when a screen is laid out again, or
## when the same character is drawn at two sizes on two screens. Every one of
## those has happened here already.

## The character this lies under. It can be anywhere in the scene: what is
## needed is where its artwork is drawn, not where it sits in the tree.
@export_node_path("CanvasItem") var stands_under: NodePath

## How much wider than the character the smudge is. A shadow exactly as wide as
## the feet reads as a plinth the character is standing on; a little wider
## reads as ground.
@export var spread := 1.15

## How far above the feet the ground is. Nothing for a character standing in
## full view; a few dozen pixels for one whose feet are deliberately cropped by
## the bottom of the screen, where the floor it stands on is the last of the
## floor that can be seen.
@export var lift := 0.0

## How dark it is drawn. The artwork carries its own softness and its own
## alpha, so full strength is the artwork as it was drawn; this is here for a
## screen lit brightly enough to want less of it.
@export var depth := 1.0


func _ready() -> void:
	# It is scenery. Nothing about it answers the pointer, and it must not take
	# a click meant for whatever it is lying under.
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	modulate.a = depth
	settle()
	# And again once the screen has finished laying itself out. A character in
	# a container is not the size it will end up being at the moment this runs,
	# and a shadow drawn for the size it was is a shadow that misses.
	settle.call_deferred()


func settle() -> void:
	"""Put the shadow under the feet of the character it belongs to.

	Public so that a screen which moves its character can say so, and so that a
	test can ask for it without waiting a frame.
	"""
	var who := get_node_or_null(stands_under) as CanvasItem
	if not who or not texture:
		return

	# Whenever the character is given a new rectangle, this is worth doing
	# again. Asked for here rather than when this node is readied, because the
	# character it belongs to is often named after that.
	if who is Control and not who.item_rect_changed.is_connected(settle):
		who.item_rect_changed.connect(settle)

	var stood := stands_on(who)
	if stood.size.x <= 0.0:
		return

	var wide := stood.size.x * spread
	var tall := wide * texture.get_height() / float(texture.get_width())
	size = Vector2(wide, tall)
	# Across the middle of the feet, and centred on them rather than sitting
	# below them: the ground the character stands on is under the feet, so half
	# the smudge belongs behind them.
	position = Vector2(
		stood.get_center().x - wide / 2.0, stood.end.y - lift - tall / 2.0)


func stands_on(who: CanvasItem) -> Rect2:
	"""Where the character's artwork is drawn, in this shadow's own space.

	The node's own rectangle is not the answer: a character drawn to fit a box
	leaves empty air either side of it, and a shadow as wide as the box is a
	shadow wider than the character.
	"""
	var here: Transform2D = get_parent().get_global_transform().affine_inverse() \
		* who.get_global_transform()
	var art := _artwork(who)

	var corners: Array[Vector2] = [
		here * art.position,
		here * Vector2(art.end.x, art.position.y),
		here * Vector2(art.position.x, art.end.y),
		here * art.end,
	]
	var from := corners[0]
	var to := corners[0]
	for corner in corners:
		from = from.min(corner)
		to = to.max(corner)
	return Rect2(from, to - from)


func _artwork(who: CanvasItem) -> Rect2:
	"""The picture the character draws, in the character's own coordinates"""
	if who is AnimatedSprite2D:
		return _frame_rect(who)
	if who is Sprite2D:
		if not who.texture:
			return Rect2(Vector2.ZERO, Vector2.ZERO)
		return _painted(who.texture,
			_drawn_at(who.texture.get_size(), who.centered, who.offset))
	if who is TextureRect:
		return _painted(who.texture, _fitted(who))
	return Rect2(Vector2.ZERO, Vector2.ZERO)


func _frame_rect(sprite: AnimatedSprite2D) -> Rect2:
	var frames := sprite.sprite_frames
	if not frames or not frames.has_animation(sprite.animation):
		return Rect2(Vector2.ZERO, Vector2.ZERO)
	var frame := frames.get_frame_texture(sprite.animation, sprite.frame)
	if not frame:
		return Rect2(Vector2.ZERO, Vector2.ZERO)
	return _painted(frame,
		_drawn_at(frame.get_size(), sprite.centered, sprite.offset))


func _painted(art: Texture2D, whole: Rect2) -> Rect2:
	"""The part of the picture that is actually painted on.

	A character is rarely drawn to the edges of its own frame -- the shop's
	Sentaur stands a good forty pixels above the bottom of its animation frame
	-- and a shadow under the frame is a shadow under nothing. So the picture
	is read and the clear border around it taken off.

	The whole frame is the answer if the picture cannot be read. An atlas hands
	back the sheet it was cut from rather than its own square, and a sheet's
	painted part says nothing about one frame of it.
	"""
	if not art:
		return whole
	var img := art.get_image()
	if not img or img.get_size() != Vector2i(art.get_size()):
		return whole

	var used := img.get_used_rect()
	if used.size.x <= 0 or used.size.y <= 0:
		return whole

	var of := Vector2(art.get_size())
	return Rect2(
		whole.position + whole.size * (Vector2(used.position) / of),
		whole.size * (Vector2(used.size) / of))


func _drawn_at(art: Vector2, centered: bool, offset: Vector2) -> Rect2:
	var corner := offset - art / 2.0 if centered else offset
	return Rect2(corner, art)


func _fitted(rect: TextureRect) -> Rect2:
	"""What a TextureRect actually covers, once its picture has been fitted.

	Only the modes this game uses are worked out. Anything else fills the whole
	rectangle, which is what a TextureRect does by default.
	"""
	var box := Rect2(Vector2.ZERO, rect.size)
	if not rect.texture:
		return box

	var keeps_shape := rect.stretch_mode in [
		TextureRect.STRETCH_KEEP_ASPECT,
		TextureRect.STRETCH_KEEP_ASPECT_CENTERED,
		TextureRect.STRETCH_KEEP_ASPECT_COVERED,
	]
	if not keeps_shape:
		return box

	var art: Vector2 = rect.texture.get_size()
	if art.x <= 0.0 or art.y <= 0.0:
		return box

	var fit := minf(box.size.x / art.x, box.size.y / art.y)
	if rect.stretch_mode == TextureRect.STRETCH_KEEP_ASPECT_COVERED:
		fit = maxf(box.size.x / art.x, box.size.y / art.y)

	var drawn: Vector2 = art * fit
	if rect.stretch_mode == TextureRect.STRETCH_KEEP_ASPECT:
		return Rect2(Vector2.ZERO, drawn)
	return Rect2((box.size - drawn) / 2.0, drawn)
