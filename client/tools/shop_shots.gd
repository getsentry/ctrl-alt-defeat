extends SceneTree
## Take a picture of the shop screen in each of the states worth looking at.
##
## A screen is the one thing the tests cannot check: they can say a label holds
## the right words and still miss the label sitting on top of another one. This
## walks the real game to the shop and saves a PNG of each state, so a change
## to how the screen looks can be looked at.
##
##     cd client
##     BATTLE_SERVER_URL=http://localhost:8082 \
##       godot --path . -s tools/shop_shots.gd -- /tmp/shop
##
## It needs a server, because the shop is the server's: the items on the
## shelves, their prices and what is on sale all come from a new game.
##
## Close any other copy of the game first. A window with another one in front
## of it stops being drawn, and a picture is taken after the drawing, so the
## run hangs at the first shot rather than failing.
##
## The directory is the last argument, and defaults to user://shop_shots.
## Godot's own arguments come first, so `--` separates them from this one.

var out_dir := ""


func _initialize() -> void:
	out_dir = _where_to_write()
	run.call_deferred()


func _where_to_write() -> String:
	var args := OS.get_cmdline_user_args()
	if args.size() > 0:
		return args[0]
	return ProjectSettings.globalize_path("user://shop_shots")


func frames(count: int) -> void:
	for i in count:
		await process_frame


func shot(shot_name: String) -> void:
	# The picture is of what was drawn, so it has to be taken after the drawing.
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("%s/%s.png" % [out_dir, shot_name])
	print("shot: %s/%s.png" % [out_dir, shot_name])


func run() -> void:
	DirAccess.make_dir_recursive_absolute(out_dir)
	var state = root.get_node("GameStateManager")

	var shop = await _new_game_through_to_the_shop()
	if shop == null:
		push_error("Never reached the shop. Is a server running?")
		quit(1)
		return
	await shot("01_shop")

	if shop.shop_items.is_empty():
		push_error("The shop is empty, so there is nothing to photograph.")
		quit(1)
		return

	await _with_a_sale(shop, state)

	var slot = shop.shop_items[mini(1, shop.shop_items.size() - 1)]

	# A shelf under the pointer: lit, lifted, and read out on a card.
	shop._on_shelf_entered(slot)
	await frames(20)
	await shot("02_hovered")
	shop._on_shelf_left(slot)
	await frames(10)

	# Nothing the player can afford.
	var had: int = state.gold
	state.gold = 0
	shop._update_stats()
	await frames(20)
	await shot("03_out_of_gold")
	state.gold = had
	shop._update_stats()
	await frames(20)

	# Bought and gone off the shelf.
	shop._mark_shop_item_sold(shop.shop_items[0])
	await frames(10)
	await shot("04_sold")

	# On its way to the grid, over a square it can have and one it cannot.
	var grid = shop.inventory_grid
	shop._start_shop_drag(slot, slot.get_meta("item_data"))
	await frames(2)
	shop._input(_pointer_over(grid, Vector2i(2, 3)))
	await frames(10)
	await shot("05_drop_allowed")

	shop._input(_pointer_over(grid, Vector2i(0, 0)))
	await frames(10)
	await shot("06_drop_refused")

	quit()


func _with_a_sale(shop, state) -> void:
	"""Put one item on sale, so the sale plate is always photographed.

	Whether the shop rolls a sale is the server's business and a run that
	happens not to get one leaves the state nobody looked at.
	"""
	var shelf: Array = state.current_shop
	for item in shelf:
		if item != null and item.on_sale:
			return

	for item in shelf:
		if item == null:
			continue
		item.on_sale = true
		item.cost = item.price + 2
		break

	shop._display_shop_items(shelf)
	await frames(5)
	await shot("01_shop")


func _new_game_through_to_the_shop():
	"""Start a game the way a player does, and wait for the shop to open"""
	var menu = load("res://scenes/MainMenu.tscn").instantiate()
	root.add_child(menu)
	current_scene = menu
	await frames(5)

	menu.new_game_button.pressed.emit()

	for waited in 300:
		await frames(1)
		if current_scene and current_scene.name == "UnifiedGridUI":
			await frames(30)
			return current_scene
	return null


func _pointer_over(grid, square: Vector2i) -> InputEventMouseMotion:
	"""A pointer sitting inside one square of the grid"""
	var motion := InputEventMouseMotion.new()
	motion.global_position = grid.get_global_transform() \
		* (grid.grid_to_pixel(square) + Vector2(4, 4))
	return motion
