extends GutTest
# The chest, as a box things are thrown into rather than a tray of squares.
#
# An item in the chest is off the grid: the server keeps no place and no facing
# for one, so where it lies is the client's business alone. It lies where it
# lands, it is left there, and nothing that is thrown may end up anywhere the
# player cannot reach it.

const APITypes = preload("res://scripts/api_types.gd")
const StorageBin = preload("res://scripts/storage_bin.gd")
const InventoryGrid = preload("res://scripts/inventory_grid.gd")

## The opening of the tray, and the panel it sits in, as the game sets them up.
const TRAY := Rect2(40, 21, 240, 214)
const PANEL := Vector2(320, 276)
## How many physics frames a test waits before asking where something settled.
## A second and a half at the usual rate, which is longer than a fall through a
## tray this deep takes.
const SETTLING := 90

var bin: StorageBin
var sell_zone: Control
var grid_zone: InventoryGrid


func before_each():
	sell_zone = Control.new()
	sell_zone.position = Vector2(800, 400)
	sell_zone.size = Vector2(120, 100)
	add_child(sell_zone)

	grid_zone = InventoryGrid.new()
	grid_zone.position = Vector2(0, 0)
	add_child(grid_zone)
	grid_zone.configure(9, 7, 40.0, 1.0)

	bin = StorageBin.new()
	bin.position = Vector2(500, 500)
	bin.size = PANEL
	bin.sell_zone = sell_zone
	bin.grid_zone = grid_zone
	add_child(bin)
	bin.configure(TRAY, 30.0, 1.0)


func after_each():
	bin.queue_free()
	sell_zone.queue_free()
	grid_zone.queue_free()


func _chest(ids: Array) -> Array:
	var items := []
	for id in ids:
		items.append(TestHelpers.item({"id": id}))
	return items


func _settle() -> void:
	for i in range(SETTLING):
		await get_tree().physics_frame


func _in_the_tray(item_id: String) -> Vector2:
	"""Where an item lies, in the tray's own coordinates"""
	return bin.where_is(item_id)


func _press(at: Vector2, down: bool) -> InputEventMouseButton:
	"""The left button going down or coming up, at a place on the screen"""
	var event := InputEventMouseButton.new()
	event.button_index = MOUSE_BUTTON_LEFT
	event.pressed = down
	event.global_position = at
	event.position = at
	return event


func _body(item_id: String) -> RigidBody2D:
	"""The body carrying an item about. Only a test looks at one directly."""
	return bin._lying[item_id].body


# ============ What is in it ============

func test_it_holds_what_the_server_says_is_in_it():
	bin.show_items(_chest(["first", "second"]))

	assert_eq(bin.count(), 2, "Both should be in the tray")
	assert_true("first" in bin.ids() and "second" in bin.ids(), "and both by id")


func test_it_lets_go_of_what_has_left_the_chest():
	bin.show_items(_chest(["staying", "leaving"]))

	bin.show_items(_chest(["staying"]))

	assert_eq(bin.ids(), ["staying"], "What the server no longer has is not drawn")


func test_it_leaves_what_is_already_lying_in_it_alone():
	# The server answers every move with the whole chest, so this runs
	# constantly. Laying the tray out again each time would tidy away every
	# throw the player made.
	bin.show_items(_chest(["settled"]))
	var was := _in_the_tray("settled")

	bin.show_items(_chest(["settled", "arriving"]))

	assert_eq(_in_the_tray("settled"), was, "It should be where it already was")
	assert_eq(bin.count(), 2, "and the new one is in as well")


func test_what_is_in_hand_is_not_also_in_the_tray():
	# The hand is a shortcut and not a place, so the item is in the chest the
	# whole time it is held. Drawing it in both would look like two of it.
	bin.show_items(_chest(["in_hand", "left_behind"]), "in_hand")

	assert_eq(bin.ids(), ["left_behind"], "Only what is not in hand is drawn")


func test_it_has_no_squares_to_run_out_of():
	# It used to be twenty-four squares, and the server holds no such limit, so
	# a full chest lost items out of sight.
	bin.show_items(_chest(range(40).map(func(i): return "item_%d" % i)))

	assert_eq(bin.count(), 40, "Everything the server holds should be in the tray")


# ============ Falling in ============

func test_an_item_nobody_threw_falls_in_over_the_opening():
	bin.show_items(_chest(["falling"]))

	var at := _in_the_tray("falling")
	assert_between(at.x, TRAY.position.x, TRAY.end.x,
		"It should fall between the walls rather than onto one of them")
	assert_lt(at.y, TRAY.end.y, "and from above the bottom of the tray")


func test_an_item_dropped_in_falls_from_where_it_was_let_go_of():
	var at := bin.global_position + Vector2(120, 60)

	bin.catch(TestHelpers.item({"id": "dropped"}), at)

	assert_almost_eq(_in_the_tray("dropped"), Vector2(120, 60), Vector2(0.5, 0.5),
		"It should start where the pointer let go of it, not above the tray")


func test_what_falls_in_comes_to_rest_in_the_tray():
	bin.show_items(_chest(["falling"]))

	await _settle()

	var at := _in_the_tray("falling")
	assert_lt(at.y, TRAY.end.y, "It should come to rest on the floor of the tray")
	assert_gt(at.y, TRAY.position.y, "rather than fall through it")
	assert_between(at.x, TRAY.position.x, TRAY.end.x, "and stay between the walls")


func test_things_in_the_tray_push_each_other_apart():
	# There are no squares, so nothing keeps two items apart but the physics.
	var here := bin.global_position + Vector2(TRAY.get_center().x, TRAY.position.y)
	bin.catch(TestHelpers.item({"id": "one"}), here)
	bin.catch(TestHelpers.item({"id": "two"}), here)

	await _settle()

	assert_gt(_in_the_tray("one").distance_to(_in_the_tray("two")), 10.0,
		"Two items dropped on the same spot should not end up inside each other")


func test_an_item_dropped_in_off_the_grid_loses_the_turn():
	# It was turned to fit a square, and the server keeps no facing for what is
	# in the chest, so the tray must not go on showing one.
	var turned = TestHelpers.placed_item({"id": "sideways"}).turned(1)

	bin.catch(turned, bin.global_position + Vector2(100, 60))

	assert_eq(bin.drawn("sideways").item_data.facing(), 0,
		"What is in the chest faces the way the catalogue draws it")


# ============ Throwing ============

func test_a_hard_throw_is_slowed_down():
	# A flick is easy to do by accident. An item that leaves at the speed of
	# the pointer is out of the room before the player has seen where it went.
	bin.show_items(_chest(["thrown"]))
	var item = bin.item_at(bin.global_position + _in_the_tray("thrown"))
	bin.pick_up(item, bin.global_position + Vector2(100, 100))

	bin.release_at(bin.global_position + Vector2(100, 100), Vector2(9000, 0))

	assert_lte(_body("thrown").linear_velocity.length(), StorageBin.THROW_MAX,
		"A throw should be held to the speed the chest allows")


func test_throwing_upwards_is_held_back_hardest():
	# Up is the one direction where the item is gone for a while and there is
	# nothing to watch until it comes back down.
	bin.show_items(_chest(["thrown"]))
	var item = bin.item_at(bin.global_position + _in_the_tray("thrown"))
	bin.pick_up(item, bin.global_position + Vector2(100, 100))

	bin.release_at(bin.global_position + Vector2(100, 100), Vector2(0, -9000))

	assert_gte(_body("thrown").linear_velocity.y, -StorageBin.THROW_UP_MAX,
		"Thrown up, it should leave the hand gently")
	assert_lt(_body("thrown").linear_velocity.y, 0.0, "but it should still go up")


func test_anything_that_gets_out_of_the_room_is_fetched_back():
	# A throw can put an item over a wall, and there is no floor out there for
	# it to land on. Rather than let it fall for ever, it is put back.
	bin.show_items(_chest(["escaped"]))
	_body("escaped").position = Vector2(-5000, 9000)

	bin.keep_in_bounds()

	var at := _in_the_tray("escaped")
	assert_between(at.x, TRAY.position.x, TRAY.end.x, "It should be back over the tray")
	assert_lt(at.y, TRAY.end.y, "and above the bottom of it")


func test_what_is_still_in_the_room_is_left_where_it_is():
	# Being out of the tray is not being lost: an item thrown up is out of it
	# for a second and comes back down by itself.
	bin.show_items(_chest(["flying"]))
	var over_the_tray := Vector2(TRAY.get_center().x, TRAY.position.y - 300)
	_body("flying").position = over_the_tray

	bin.keep_in_bounds()

	assert_eq(_in_the_tray("flying"), over_the_tray, "It is still on its way down")


func test_the_walls_reach_above_the_tray():
	# The picture shows walls as high as the tray. These go on up out of the
	# top of the screen, so a thing thrown in the chest stays over the chest.
	var high_up := bin.global_position \
		+ Vector2(TRAY.get_center().x, TRAY.position.y - 400)
	bin.catch(TestHelpers.item({"id": "hurled"}), high_up, Vector2(4000, 0))

	await _settle()

	var at := _in_the_tray("hurled")
	assert_between(at.x, TRAY.position.x, TRAY.end.x,
		"However hard it is thrown, it comes down in the tray")


func test_nothing_travels_faster_than_the_chest_allows():
	# The throw is held back where it leaves the hand, but two items landing
	# inside each other are shoved apart by however far in they got, and that
	# shove has no limit of its own.
	bin.show_items(_chest(["shoved"]))
	_body("shoved").linear_velocity = Vector2(9000, -9000)
	_body("shoved").angular_velocity = 200.0

	bin.hold_the_speed_down()

	assert_lte(_body("shoved").linear_velocity.length(), StorageBin.MAX_SPEED,
		"It should be brought back to a speed the eye can follow")
	assert_lte(abs(_body("shoved").angular_velocity), StorageBin.MAX_SPIN,
		"and to a spin the eye can follow")


func test_a_roof_keeps_what_is_thrown_up_in_sight():
	# An item that leaves the screen is gone as far as the player is concerned,
	# however faithfully it is still being simulated up there.
	bin.show_items(_chest(["hurled"]))
	bin.pick_up(bin.item_at(bin.global_position + _in_the_tray("hurled")),
		bin.global_position + Vector2(100, 100))
	bin.release_at(bin.global_position + Vector2(100, 100), Vector2(0, -90000))

	await _settle()

	assert_gt(_in_the_tray("hurled").y, bin._roof_height(),
		"It should come back down off the roof rather than through it")


func test_something_fetched_down_from_the_ceiling_comes_all_the_way_down():
	# What is being put back does not count as something to drop in above. It
	# used to, so an item fetched from the ceiling was put back just above the
	# ceiling, which is where it already was, and it never came home.
	bin.show_items(_chest(["stuck"]))
	_body("stuck").position = Vector2(TRAY.get_center().x, bin._roof_height() - 900)

	bin.keep_in_bounds()

	assert_lt(_in_the_tray("stuck").y, TRAY.end.y, "It is over the tray")
	assert_gt(_in_the_tray("stuck").y, bin._roof_height(),
		"and back inside the room, not still up in the roof")


func test_what_is_dragged_stays_on_the_screen():
	# The pointer can leave the window while the button is held. An item that
	# goes with it is being carried somewhere the player cannot see, and it
	# used to be possible to let go of one up there.
	bin.show_items(_chest(["carried"]))
	bin.pick_up(bin.item_at(bin.global_position + _in_the_tray("carried")),
		bin.global_position + Vector2(50, 50))
	var drawn := bin.dragged_visual()

	bin._follow(Vector2(-4000, -4000))

	var view := bin.get_viewport_rect()
	assert_true(view.encloses(Rect2(drawn.global_position, drawn.size)),
		"What is in hand should stop at the edge of the screen")


func test_something_let_go_of_over_the_roof_lands_under_it():
	# Whatever the pointer says, an item put down over the roof would land on
	# top of the roof and stay there.
	bin.show_items(_chest(["dropped"]))
	bin.pick_up(bin.item_at(bin.global_position + _in_the_tray("dropped")),
		bin.global_position + Vector2(50, 50))

	bin.release_at(bin.global_position + Vector2(TRAY.get_center().x, -9000))

	assert_gt(_in_the_tray("dropped").y, bin._roof_height(),
		"It lands under the roof, not above it")
	assert_between(_in_the_tray("dropped").x, TRAY.position.x, TRAY.end.x,
		"and between the walls")


func test_it_catches_anything_let_go_of_above_it():
	# Aiming at the opening itself is a small target, and the walls reach the
	# top of the screen, so anything let go of up there falls in anyway.
	var over_the_tray := bin.global_position + Vector2(TRAY.get_center().x, 0)
	assert_true(bin.catches(over_the_tray + Vector2(0, TRAY.get_center().y)),
		"The tray itself catches things")
	assert_true(bin.catches(over_the_tray - Vector2(0, 500)),
		"and so does the room above it")
	assert_false(bin.catches(over_the_tray + Vector2(400, -500)),
		"but not the room beside it")


# ============ Picking things back up ============

func test_carrying_something_over_the_grid_marks_where_it_would_land():
	# An item is picked out of the chest to be put on the grid as often as not.
	# Without the mark the player is aiming it at a square they cannot see.
	bin.show_items(_chest(["carried"]))
	bin.pick_up(bin.item_at(bin.global_position + _in_the_tray("carried")),
		bin.global_position + Vector2(50, 50))

	bin._follow(grid_zone.global_position + Vector2(60, 60))

	assert_true(grid_zone.hover_preview.visible,
		"The grid should mark the square it would land on")


func test_carrying_it_away_from_the_grid_clears_the_mark():
	bin.show_items(_chest(["carried"]))
	bin.pick_up(bin.item_at(bin.global_position + _in_the_tray("carried")),
		bin.global_position + Vector2(50, 50))
	bin._follow(grid_zone.global_position + Vector2(60, 60))

	bin._follow(bin.global_position + Vector2(50, 50))

	assert_false(grid_zone.hover_preview.visible,
		"Nothing would land on the grid from over here")


func test_letting_go_clears_the_mark():
	bin.show_items(_chest(["carried"]))
	bin.pick_up(bin.item_at(bin.global_position + _in_the_tray("carried")),
		bin.global_position + Vector2(50, 50))
	bin._follow(grid_zone.global_position + Vector2(60, 60))

	bin.release_at(grid_zone.global_position + Vector2(60, 60))

	assert_false(grid_zone.hover_preview.visible,
		"The mark should not outlive the item it was drawn for")



func test_it_says_what_lies_under_a_point():
	bin.show_items(_chest(["lying"]))
	var at := bin.global_position + _in_the_tray("lying")

	assert_eq(bin.item_at(at).id, "lying", "The item under the pointer")
	assert_null(bin.item_at(bin.global_position + Vector2(-400, -400)),
		"and nothing where there is nothing")


func test_picking_something_up_takes_it_out_of_the_tray():
	bin.show_items(_chest(["picked"]))
	var item = bin.item_at(bin.global_position + _in_the_tray("picked"))

	bin.pick_up(item, bin.global_position + Vector2(50, 50))

	assert_eq(bin.count(), 0, "It is in hand, so it is not lying in the tray")
	assert_eq(bin.dragged().id, "picked", "and it is what is in hand")


func test_letting_go_over_nothing_puts_it_back_in_the_chest():
	# It never left the chest as far as the server is concerned, so there is
	# nowhere else for it to go.
	bin.show_items(_chest(["picked"]))
	bin.pick_up(bin.item_at(bin.global_position + _in_the_tray("picked")),
		bin.global_position + Vector2(50, 50))

	bin.release_at(bin.global_position + Vector2(60, 60))

	assert_eq(bin.ids(), ["picked"], "It goes back in the chest")
	assert_null(bin.dragged(), "and nothing is in hand")


func test_letting_go_over_the_sell_chest_sells_it():
	bin.show_items(_chest(["for_sale"]))
	bin.pick_up(bin.item_at(bin.global_position + _in_the_tray("for_sale")),
		bin.global_position + Vector2(50, 50))
	watch_signals(bin)

	bin.release_at(sell_zone.global_position + sell_zone.size / 2)

	assert_signal_emitted(bin, "item_sold", "The sell chest takes it")
	assert_eq(bin.count(), 0, "so it is not put back in the tray")


func test_letting_go_over_the_grid_takes_it_out_of_the_chest():
	bin.show_items(_chest(["placing"]))
	bin.pick_up(bin.item_at(bin.global_position + _in_the_tray("placing")),
		bin.global_position + Vector2(50, 50))
	watch_signals(bin)

	var going = bin.dragged()
	var pointer := grid_zone.global_position + Vector2(30, 30)
	bin.release_at(pointer)

	assert_signal_emitted_with_parameters(bin, "item_unstored", [going, pointer], 0)
	assert_eq(bin.count(), 0, "The grid has it now, so the tray does not")


func test_turning_what_was_picked_out_of_the_chest():
	# An item is often picked out of the chest to be put on the grid, and
	# turning it on the way is quicker than putting it down and turning it.
	bin.show_items(_chest(["turning"]))
	bin.pick_up(bin.item_at(bin.global_position + _in_the_tray("turning")),
		bin.global_position + Vector2(50, 50))

	assert_true(bin.turn_dragged(1), "It says it turned something")
	assert_eq(bin.dragged().facing(), 90, "and it is facing a quarter turn round")


func test_pressing_on_something_in_the_tray_picks_it_up():
	# The tray answers the pointer for everything in it, so a press has to find
	# what is under it rather than wait for the artwork to say.
	bin.show_items(_chest(["pressed"]))
	var at := bin.global_position + _in_the_tray("pressed")

	bin._input(_press(at, true))

	assert_eq(bin.dragged().id, "pressed", "The press picks it up")
	assert_eq(bin.count(), 0, "so it stops lying in the tray")


func test_something_falling_can_be_caught_on_its_way_down():
	# A thing thrown up is in the air for a second or two, and the chest hears
	# about the pointer wherever it is, so it can be caught up there.
	bin.show_items(_chest(["falling"]))
	var in_the_air := Vector2(TRAY.get_center().x, TRAY.position.y - 500)
	_body("falling").position = in_the_air

	bin._input(_press(bin.global_position + in_the_air, true))

	assert_eq(bin.dragged().id, "falling", "It is caught in mid-air")
	assert_eq(bin.count(), 0, "and no longer falling")


func test_nothing_is_picked_up_while_something_is_already_in_hand():
	# One hand. A press while an item is in it is what puts that item down,
	# and picking up a second would leave the first with nobody holding it.
	bin.show_items(_chest(["lying", "in_hand"]), "in_hand")
	var at := bin.global_position + _in_the_tray("lying")

	bin._input(_press(at, true))

	assert_null(bin.dragged(), "The press is not the chest's to take")
	assert_eq(bin.count(), 1, "and nothing has left the tray")


func test_pressing_on_the_empty_tray_picks_nothing_up():
	bin.show_items(_chest(["elsewhere"]))

	bin._input(_press(bin.global_position + Vector2(10, 10), true))

	assert_null(bin.dragged(), "There is nothing under the pointer to pick up")


func test_letting_the_button_go_puts_it_down():
	bin.show_items(_chest(["pressed"]))
	var at := bin.global_position + _in_the_tray("pressed")
	bin._input(_press(at, true))

	bin._input(_press(at + Vector2(20, -10), false))

	assert_null(bin.dragged(), "Nothing is in hand once the button comes up")
	assert_eq(bin.ids(), ["pressed"], "and it is back in the chest")


func test_turning_with_nothing_in_hand_does_nothing():
	assert_false(bin.turn_dragged(1), "Nothing was turned, so the input is not used")


func test_an_item_put_back_in_the_chest_loses_the_turn():
	# The server keeps no facing for a stored item, so one drawn turned in the
	# tray would be picked up facing a way the server has never heard of.
	bin.show_items(_chest(["turned"]))
	bin.pick_up(bin.item_at(bin.global_position + _in_the_tray("turned")),
		bin.global_position + Vector2(50, 50))
	bin.turn_dragged(1)

	bin.release_at(bin.global_position + Vector2(60, 60))

	assert_eq(bin.drawn("turned").item_data.facing(), 0,
		"What is in the chest faces the way the catalogue draws it")


func test_nothing_is_picked_up_out_of_a_chest_being_watched():
	# A battle is somebody else's board. Nothing on it can be moved.
	bin.read_only = true
	bin.show_items(_chest(["watched"]))

	bin.pick_up(bin.item_at(bin.global_position + _in_the_tray("watched")),
		bin.global_position + Vector2(50, 50))

	assert_null(bin.dragged(), "Nothing can be picked up")
	assert_eq(bin.count(), 1, "and it is still lying in the tray")
