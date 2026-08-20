extends GutTest
# The smudge of dark under a standing character.
#
# It measures the character rather than being placed by hand, because the same
# character is drawn at three sizes on three screens, and the artwork has been
# replaced twice. A shadow that has to be moved by hand each time is a shadow
# that ends up under nobody.

const ContactShadow = preload("res://scripts/contact_shadow.gd")
const SMUDGE = preload("res://assets/ui/contact_shadow.png")

## The character's picture: a frame with clear air around what is painted on
## it, which is what a character's artwork always is.
const FRAME := Vector2i(100, 120)
const PAINTED := Rect2i(20, 10, 60, 100)

var room: Control
var who: TextureRect
var shade


func before_each():
	room = Control.new()
	room.size = Vector2(1000, 800)
	add_child(room)

	who = TextureRect.new()
	who.texture = _figure()
	who.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	room.add_child(who)
	who.position = Vector2(300, 200)
	who.size = Vector2(FRAME)

	shade = ContactShadow.new()
	shade.texture = SMUDGE
	shade.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	room.add_child(shade)
	shade.stands_under = shade.get_path_to(who)
	shade.settle()


func after_each():
	room.queue_free()


func _figure() -> ImageTexture:
	"""A character's picture: something painted on a larger clear frame"""
	var img := Image.create(FRAME.x, FRAME.y, false, Image.FORMAT_RGBA8)
	img.fill(Color(0, 0, 0, 0))
	img.fill_rect(PAINTED, Color.WHITE)
	return ImageTexture.create_from_image(img)


func _feet() -> Vector2:
	"""Where the character's feet are, worked out by hand from the fixture"""
	return Vector2(300 + PAINTED.position.x + PAINTED.size.x / 2.0,
		200 + PAINTED.position.y + PAINTED.size.y)


func test_it_lies_across_the_feet():
	assert_almost_eq(shade.get_rect().get_center(), _feet(), Vector2(0.5, 0.5),
		"The middle of the smudge is the point the character stands on")


func test_it_is_a_little_wider_than_the_character():
	# Exactly as wide as the feet reads as a plinth the character is standing
	# on. A little wider reads as ground.
	assert_almost_eq(shade.size.x, PAINTED.size.x * shade.spread, 0.5,
		"It should be half again as wide as the character")


func test_it_keeps_the_shape_of_its_own_picture():
	var art: Vector2 = SMUDGE.get_size()
	assert_almost_eq(shade.size.y / shade.size.x, art.y / art.x, 0.01,
		"A smudge stretched out of shape is a smudge that reads as a puddle")


func test_it_measures_what_is_painted_and_not_the_frame():
	# A character is drawn on a frame with clear air around it. The shop's
	# Sentaur stands a good forty pixels above the bottom of its own frame, and
	# a shadow under the frame is a shadow under nothing.
	assert_lt(shade.size.x, who.size.x * shade.spread,
		"The clear air either side of the character does not count")
	assert_lt(shade.get_rect().get_center().y, who.get_rect().end.y,
		"nor the clear air under it")


func test_it_follows_a_character_that_is_drawn_larger():
	who.scale = Vector2(2.0, 2.0)
	shade.settle()

	assert_almost_eq(shade.size.x, PAINTED.size.x * 2.0 * shade.spread, 0.5,
		"Twice the character is twice the shadow")


func test_it_settles_again_when_the_character_is_given_a_new_rectangle():
	# A character in a container is not the size it will end up being when the
	# screen is first drawn, so the shadow has to be told when that changes.
	var was: Rect2 = shade.get_rect()

	who.size = Vector2(FRAME) * 2.0
	await get_tree().process_frame

	assert_ne(shade.get_rect(), was, "It should have been drawn again")
	assert_almost_eq(shade.size.x, PAINTED.size.x * 2.0 * shade.spread, 0.5,
		"and for the size the character is now")


func test_it_can_be_lifted_off_the_feet():
	# A fighter's feet are cropped by the bottom of the battle screen on
	# purpose, so the floor it stands on is the last of the floor still in view.
	shade.lift = 30.0
	shade.settle()

	assert_almost_eq(shade.get_rect().get_center(), _feet() - Vector2(0, 30.0),
		Vector2(0.5, 0.5), "It should sit that far up from the feet")


func test_it_does_not_answer_the_pointer():
	# It is scenery. A click on it is a click meant for what it lies under.
	assert_eq(shade.mouse_filter, Control.MOUSE_FILTER_IGNORE,
		"The smudge should never take a click")


func test_a_shadow_with_nobody_under_it_stays_where_it_was_put():
	# A screen that hides its character still holds the shadow node. It has
	# nothing to measure, so it must not measure nothing and believe it.
	var lonely = ContactShadow.new()
	lonely.texture = SMUDGE
	lonely.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	room.add_child(lonely)
	lonely.position = Vector2(10, 20)
	lonely.size = Vector2(80, 25)

	lonely.settle()

	assert_eq(lonely.get_rect(), Rect2(10, 20, 80, 25),
		"With nobody to stand under, it stays where the scene put it")
