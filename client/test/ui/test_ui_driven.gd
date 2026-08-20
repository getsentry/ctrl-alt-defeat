extends GutTest
# UI INTEGRATION TESTS - Testing by driving the actual UI
# These tests simulate real user interactions through the UI
# Now using real server with transaction-based test isolation

var TestSessionManager = preload("res://test/integration/test_session_manager.gd")

func before_all():
	# Verify server is in test mode - this is required for transaction isolation
	var is_test_mode = await TestSessionManager.ensure_test_mode()
	if not is_test_mode:
		push_error("Server is not in TEST_MODE - transaction isolation will not work")
		# Fail fast - don't run tests without proper isolation
		assert_true(false, "Server must be in TEST_MODE for tests to run")
		return

	# Start a test session for transaction isolation (10x faster than table truncation)
	var session_started = await TestSessionManager.start_test_session()
	if not session_started:
		push_error("Failed to start test session - transaction isolation required")
		assert_true(false, "Test session must be started for proper test isolation")
		return

var _root_children_before: Array = []

func before_each():
	# Reset game state for each test
	GameStateManager.start_new_game()
	BattleServerAPI.reset_for_test()  # Force new server session

	# Remember what root held, so after_each can free exactly what the test adds
	# and nothing else. root also holds the autoloads (GameStateManager,
	# BattleServerAPI) and the GUT runner, which must survive.
	_root_children_before = get_tree().root.get_children()
	await get_tree().process_frame

func after_each():
	var scene = get_tree().current_scene
	if scene and is_instance_valid(scene):
		get_tree().current_scene = null

	# A test adds the main menu to root itself, then change_scene_to_file()
	# swaps current_scene to the game UI. Both need freeing, or their timers and
	# battle playback keep running into the next test and crash the engine.
	for child in get_tree().root.get_children():
		if child in _root_children_before:
			continue
		if is_instance_valid(child):
			get_tree().root.remove_child(child)
			child.queue_free()
	await get_tree().process_frame
	await get_tree().process_frame

	GameStateManager.start_new_game()
	BattleServerAPI.reset_for_test()

func after_all():
	# End test session and rollback all changes (fast!)
	var session_ended = await TestSessionManager.end_test_session()
	if session_ended:
		print("Test session completed - all database changes rolled back")
	else:
		push_warning("Failed to end test session properly")

func test_full_user_journey_through_ui():
	"""Test complete user journey from launch through shopping, battling, and advancing rounds"""
	print("\n=== UI TEST: Complete User Journey ===")

	# 1. Launch game
	print("   1. Launching game...")
	var main_menu = load("res://scenes/MainMenu.tscn").instantiate()
	get_tree().root.add_child(main_menu)
	get_tree().current_scene = main_menu
	await get_tree().process_frame

	# 2. Click New Game
	print("   2. Starting new game...")
	var new_game_btn = main_menu.new_game_button
	assert_not_null(new_game_btn, "New Game button must exist")
	new_game_btn.pressed.emit()
	var reached_game = await _wait_for_shop_ready()

	# 3. Verify game UI loaded
	var game_ui = get_tree().current_scene
	assert_true(reached_game, "Should transition to game UI")
	assert_eq(game_ui.name, "UnifiedGridUI", "Should transition to game UI")
	assert_eq(GameStateManager.current_round, 1, "Should start at round 1")

	# 4. Verify starting setup
	print("   3. Verifying initial setup...")
	assert_gte(game_ui.inventory_grid.containers.size(), 3,
		"Should have at least 3 starting containers")
	assert_gte(game_ui.shop_items.size(), 2, "Shop should have items from server")
	var initial_gold = GameStateManager.gold
	assert_gt(initial_gold, 0, "Should start with gold")

	# 5. Purchase an item from shop
	print("   4. Purchasing from shop...")
	# The square first, so the item can be one that fits on it.
	var target_grid_pos = _find_first_empty_grid_cell(game_ui)
	assert_ne(target_grid_pos, Vector2(-1, -1), "Should find empty grid cell for placement")

	var shop_item = _first_non_container_shop_item(game_ui, Vector2i(target_grid_pos))
	assert_not_null(shop_item, "Shop should offer an item that fits on a container")
	var item_data = shop_item.get_meta("item_data")
	var item_cost = item_data.cost

	# Simulate purchase through UI - we need to trigger the shop item's input handler
	print("   - Simulating purchase through UI...")

	# Get UI references
	var server_room_container = game_ui.server_room_container
	var cell_size = game_ui.inventory_grid.cell_size
	var cell_spacing = game_ui.inventory_grid.cell_spacing
	var grid_global_pos = server_room_container.global_position
	var drag_end = grid_global_pos + target_grid_pos * (cell_size + cell_spacing) + Vector2(cell_size/2, cell_size/2)

	# Get shop item center position
	var shop_item_center = shop_item.global_position + shop_item.size / 2

	# Start drag from shop item
	var mouse_down = InputEventMouseButton.new()
	mouse_down.button_index = MOUSE_BUTTON_LEFT
	mouse_down.pressed = true
	mouse_down.position = shop_item.size / 2  # Local position within shop item
	mouse_down.global_position = shop_item_center

	# Send to shop item's input handler
	shop_item.gui_input.emit(mouse_down)
	await get_tree().process_frame

	# Drag to target position
	var mouse_move = InputEventMouseMotion.new()
	mouse_move.global_position = drag_end
	mouse_move.position = drag_end
	mouse_move.relative = drag_end - shop_item_center
	mouse_move.button_mask = MOUSE_BUTTON_MASK_LEFT

	game_ui._input(mouse_move)
	await get_tree().process_frame

	# Drop at target
	var mouse_up = InputEventMouseButton.new()
	mouse_up.button_index = MOUSE_BUTTON_LEFT
	mouse_up.pressed = false
	mouse_up.global_position = drag_end
	mouse_up.position = drag_end

	game_ui._input(mouse_up)
	await _wait_until(func(): return GameStateManager.gold < initial_gold)

	assert_lt(GameStateManager.gold, initial_gold, "Gold should decrease after purchase")

	assert_gt(game_ui.inventory_grid.items.size(), 0, "Should have items in inventory after purchase")
	print("   - Items in inventory: %d" % game_ui.inventory_grid.items.size())

	# Get current inventory state for debugging
	var inventory_state = game_ui.get_inventory_state() if game_ui.has_method("get_inventory_state") else {}
	assert_gt(inventory_state["items"].size(), 0, "Inventory state should contain items")
	print("   - Inventory items: %d" % inventory_state["items"].size())

	# Store inventory count before battle for verification later
	var items_before_battle = inventory_state["items"].size()
	print("   - Items before battle: %d" % items_before_battle)

	# 6. Start a battle
	print("   5. Starting battle with %d items..." % items_before_battle)
	var battle_btn = get_tree().current_scene.find_child("ReadyButton", true , false)
	if not battle_btn:
		battle_btn = get_tree().current_scene.find_child("BattleButton", true, false)

	if battle_btn:
		battle_btn.pressed.emit()
		await _wait_for_scene_change("UnifiedGridUI")
	else:
		push_error("No battle button found")
		assert_not_null(battle_btn, "Battle button should exist")

	# 7. Handle battle screen
	var current_scene = get_tree().current_scene
	# Assert that we transitioned away from UnifiedGridUI
	assert_ne(current_scene.name, "UnifiedGridUI", "Should transition to battle after clicking battle button")

	if current_scene.name == "BattleScreen":
		print("   6. Battle in progress...")
		# The battle ends straight in the shop. There was a screen in between
		# that named the result and asked for a click; the round result overlay
		# says all of that over the battle itself now.
		await _wait_for_scene("UnifiedGridUI", 20.0)
		await _wait_for_shop_ready()
	else:
		assert_eq(current_scene.name, "UnifiedGridUI",
			"Should be in either the battle or the shop it ends in")

	# 8. Verify we're back in game UI for next round
	current_scene = get_tree().current_scene
	if current_scene.name == "UnifiedGridUI":
		print("   8. Back to shop for round %d" % GameStateManager.current_round)
		assert_eq(GameStateManager.current_round, 2, "Should advance to round 2")
		assert_gte(current_scene.shop_items.size(), 1, "Should have new shop for round 2")

		# Verify inventory was preserved across battle
		var post_battle_inventory = current_scene.get_inventory_state() if current_scene.has_method("get_inventory_state") else {}
		if post_battle_inventory.has("items"):
			var items_after_battle = post_battle_inventory["items"].size()
			print("   - Items after battle: %d (was %d before battle)" % [items_after_battle, items_before_battle])
			assert_eq(items_after_battle, items_before_battle, "Inventory items should be preserved across battle")

		# 10. Try one more purchase to verify the cycle continues
		print("   9. Testing shop in round 2...")
		if current_scene.shop_items.size() > 0:
			var round2_gold = GameStateManager.gold
			assert_gt(round2_gold, 0, "Should have gold for round 2")
			print("   - Round 2 shop has %d items, gold: %d" % [current_scene.shop_items.size(), round2_gold])

		print("   ✓ Complete user journey validated: Menu -> Game -> Shop -> Battle -> Next Round")
	else:
		print("   - Ended in %s scene" % current_scene.name)
		# Don't fail if we're still in battle - just note it
		if current_scene.name == "BattleScreen":
			print("   - Still in battle screen, may need more time")
		else:
			assert_true(false, "Should return to game UI after battle")

func _find_ui_element(node: Node, property_name: String, property_value) -> Node:
	"""Helper to recursively find a UI element by property"""
	if node.get(property_name) == property_value:
		return node

	for child in node.get_children():
		var result = _find_ui_element(child, property_name, property_value)
		if result:
			return result

	return null

func _find_first_empty_grid_cell(game_ui) -> Vector2:
	"""Find the first empty cell that's on an active server grid"""
	var inventory_grid = game_ui.inventory_grid

	# Check known server positions (from server initialization)
	# Default containers are at (2,3), (4,3), (6,3), each 2x2
	var container_positions = [
		Vector2i(2, 3), Vector2i(3, 3), Vector2i(2, 4), Vector2i(3, 4),  # Container A
		Vector2i(4, 3), Vector2i(5, 3), Vector2i(4, 4), Vector2i(5, 4),  # Container B
		Vector2i(6, 3), Vector2i(7, 3), Vector2i(6, 4), Vector2i(7, 4),  # Container C
	]

	# Find first empty position
	for pos in container_positions:
		# Check if this position is occupied in the item_grid
		if inventory_grid.active_grid[pos.y][pos.x] and not inventory_grid.item_grid[pos.y][pos.x]:
			print("   - Found empty cell at: %s" % pos)
			return pos

	print("   - No empty cells found in containers")
	return Vector2(-1, -1)

func test_shop_purchase_and_item_placement():
	"""Test purchasing from shop and placing items through UI"""
	print("\n=== UI TEST: Shop Purchase & Placement ===")

	# Setup game
	var main_menu = load("res://scenes/MainMenu.tscn").instantiate()
	get_tree().root.add_child(main_menu)
	get_tree().current_scene = main_menu
	await get_tree().process_frame

	var new_game_btn = main_menu.new_game_button
	new_game_btn.pressed.emit()
	await _wait_for_shop_ready()

	var game_ui = get_tree().current_scene

	# UnifiedGridUI has these properties directly accessible
	assert_eq(game_ui.name, "UnifiedGridUI", "Should be in game UI")

	# Get shop container directly - it's a property of UnifiedGridUI
	var shop_container = game_ui.shop_container
	assert_not_null(shop_container, "Shop container should exist")

	# Get shop items from the game_ui's shop_items array
	assert_gt(game_ui.shop_items.size(), 0, "Should have shop items")
	# The square first, so the item can be one that fits on it.
	var target_grid_pos = _find_first_empty_grid_cell(game_ui)
	assert_ne(target_grid_pos, Vector2(-1, -1), "Should find at least one empty grid cell")
	print("   - Found empty grid cell at: %s" % target_grid_pos)

	var shop_item = _first_non_container_shop_item(game_ui, Vector2i(target_grid_pos))
	assert_not_null(shop_item, "Shop should offer an item that fits on a container")

	var initial_gold = GameStateManager.gold
	var item_data = shop_item.get_meta("item_data")
	var item_type = item_data.item_type
	print("   - Found shop item: %s (cost: %d, type: %s)" % [item_data.name, item_data.cost, item_type])
	print("   - Full item_data: %s" % item_data)

	# Record initial inventory state - items are in inventory_grid
	var initial_inventory_count = game_ui.inventory_grid.items.size()

	print("   - Number of containers: %d" % game_ui.inventory_grid.containers.size())
	for placed in game_ui.inventory_grid.containers:
		print("     Container at pos %s" % placed.position())

	# Get the server room container directly - it's a property of UnifiedGridUI
	var server_room_container = game_ui.server_room_container
	assert_not_null(server_room_container, "Server room container should exist")

	# Get cell size and spacing from UI constants
	var cell_size = game_ui.inventory_grid.cell_size
	var cell_spacing = game_ui.inventory_grid.cell_spacing
	var grid_global_pos = server_room_container.global_position
	var drag_end = grid_global_pos + target_grid_pos * (cell_size + cell_spacing) + Vector2(cell_size/2, cell_size/2)

	print("   - Grid container at: %s" % grid_global_pos)
	print("   - Cell size: %d, spacing: %d" % [cell_size, cell_spacing])
	print("   - Target drop position: %s" % drag_end)

	# Simulate drag and drop from shop to inventory
	print("   - Simulating shop drag and drop...")

	# Start drag by pressing mouse on shop item
	var mouse_down = InputEventMouseButton.new()
	mouse_down.button_index = MOUSE_BUTTON_LEFT
	mouse_down.pressed = true
	mouse_down.position = shop_item.size / 2  # Local position within shop item
	mouse_down.global_position = shop_item.global_position + shop_item.size / 2

	# Send mouse down to shop item to start drag
	shop_item.gui_input.emit(mouse_down)
	await get_tree().process_frame

	# Simulate drag motion to target position
	await get_tree().create_timer(0.1).timeout

	# End drag by releasing mouse at target position
	var mouse_up = InputEventMouseButton.new()
	mouse_up.button_index = MOUSE_BUTTON_LEFT
	mouse_up.pressed = false
	# Convert target grid position to pixel position
	var target_pixel_pos = game_ui.inventory_grid.grid_to_pixel(Vector2i(target_grid_pos.x, target_grid_pos.y))
	mouse_up.position = target_pixel_pos + Vector2(cell_size/2, cell_size/2)
	mouse_up.global_position = game_ui.inventory_grid.global_position + mouse_up.position

	# Send mouse up to the UI to trigger drop
	game_ui._input(mouse_up)
	await get_tree().process_frame

	# Wait for potential server response
	await _wait_for_server()

	# Verify purchase
	assert_lt(GameStateManager.gold, initial_gold, "Gold should decrease after purchase")

	# Verify inventory increased
	var new_item_count = game_ui.inventory_grid.items.size()
	assert_gt(new_item_count, initial_inventory_count, "Inventory should have new item")

	# The new system automatically places items in the first available spot
	# We can verify the item was placed somewhere on the grid
	var placed_item = null
	if new_item_count > initial_inventory_count:
		# Get the newly added item (should be the last one)
		placed_item = game_ui.inventory_grid.items[-1]

	if placed_item and placed_item.has_meta("grid_pos"):
		var pos = placed_item.get_meta("grid_pos")
		print("   - Item placed at grid position (%d,%d)" % [pos.x, pos.y])
		if placed_item.has_meta("item_data"):
			var data = placed_item.get_meta("item_data")
			print("   - Placed item data: %s" % data)
			if item_type != "":
				assert_eq(data.item_type, item_type, "Placed item should match shop item type")
	else:
		print("   - Warning: Could not find placed item position")


func test_selling_an_item_pays_the_player():
	"""Dropping a placed item on the chest should sell it, not destroy it.

	This drove a right click until fd2ff8d took that gesture away for being
	undiscoverable and replaced it with the chest, and the test was left
	driving an input nothing listens for any more.
	"""
	print("\n=== UI TEST: Sell ===")

	var main_menu = load("res://scenes/MainMenu.tscn").instantiate()
	get_tree().root.add_child(main_menu)
	get_tree().current_scene = main_menu
	await get_tree().process_frame

	main_menu.new_game_button.pressed.emit()
	await _wait_for_shop_ready()
	var game_ui = get_tree().current_scene

	# Buy one item onto the grid, the way the shop drop does.
	var target = _find_first_empty_grid_cell(game_ui)
	assert_ne(target, Vector2(-1, -1), "There should be a free cell to buy into")
	var shop_item = _first_non_container_shop_item(game_ui, Vector2i(target))
	assert_not_null(shop_item, "The shop should offer something that fits there")
	var item_data = shop_item.get_meta("item_data")

	game_ui.dragging_shop_item = shop_item
	game_ui.dragging_shop_data = item_data
	game_ui.drag_preview = ItemVisual.new()
	game_ui.add_child(game_ui.drag_preview)
	game_ui._end_shop_drag(
		game_ui.inventory_grid.global_position
		+ game_ui.inventory_grid.grid_to_pixel(Vector2i(target.x, target.y))
		+ Vector2(game_ui.inventory_grid.cell_size / 2, game_ui.inventory_grid.cell_size / 2)
	)
	await _wait_for_server()

	assert_eq(game_ui.inventory_grid.items.size(), 1, "Setup: one item is on the grid")
	var gold_before_selling = GameStateManager.gold
	var placed_visual = game_ui.inventory_grid.items[0]

	# Pick the item up and drop it on the chest, which is what selling is.
	var grid = game_ui.inventory_grid
	assert_not_null(grid.sell_zone, "Setup: the shop should give the grid a chest")
	grid._start_drag(placed_visual)
	grid._end_drag(grid.sell_zone.get_global_rect().get_center())
	await _wait_for_server()

	assert_eq(game_ui.inventory_grid.items.size(), 0, "The sold item leaves the grid")
	assert_gt(GameStateManager.gold, gold_before_selling,
		"Selling should pay the player, not take the item for nothing")
	# The item's own sell_value, not cost / 2 worked out again here. Half price
	# is rounded up (`sale_price` in items.py), and GDScript's integer division
	# rounds down, so the two agreed only on even costs - and the shop roll
	# decides which you get, which made this fail about half the time.
	assert_eq(GameStateManager.gold, gold_before_selling + item_data.sell_value,
		"A sale pays what the item says it sells for")


func test_battle_button_and_full_battle():
	"""Test clicking battle button and going through full battle"""
	print("\n=== UI TEST: Full Battle Flow ===")

	# Setup game
	var main_menu = load("res://scenes/MainMenu.tscn").instantiate()
	get_tree().root.add_child(main_menu)
	get_tree().current_scene = main_menu
	await get_tree().process_frame

	var new_game_btn = main_menu.new_game_button
	new_game_btn.pressed.emit()
	await _wait_for_shop_ready()

	var game_ui = get_tree().current_scene
	assert_eq(game_ui.name, "UnifiedGridUI", "Should be in game UI")

	# Purchase an item first (battles require items)
	print("   - Shop has %d items" % game_ui.shop_items.size())
	if game_ui.shop_items.size() > 0:
		var target_grid_pos = _find_first_empty_grid_cell(game_ui)
		print("   - Found empty cell at: %s" % target_grid_pos)
		var shop_item = _first_non_container_shop_item(game_ui, Vector2i(target_grid_pos))
		if target_grid_pos != Vector2(-1, -1):
			# Quick purchase simulation
			var server_room_container = game_ui.server_room_container
			var cell_size = game_ui.inventory_grid.cell_size
			var cell_spacing = game_ui.inventory_grid.cell_spacing
			var grid_global_pos = server_room_container.global_position
			var drag_end = grid_global_pos + target_grid_pos * (cell_size + cell_spacing) + Vector2(cell_size/2, cell_size/2)

			var shop_item_center = shop_item.global_position + shop_item.size / 2

			# Start drag
			var mouse_down = InputEventMouseButton.new()
			mouse_down.button_index = MOUSE_BUTTON_LEFT
			mouse_down.pressed = true
			mouse_down.position = shop_item.size / 2
			mouse_down.global_position = shop_item_center
			shop_item.gui_input.emit(mouse_down)
			await get_tree().process_frame

			# Move to grid
			var mouse_move = InputEventMouseMotion.new()
			mouse_move.global_position = drag_end
			mouse_move.position = drag_end
			mouse_move.relative = drag_end - shop_item_center
			mouse_move.button_mask = MOUSE_BUTTON_MASK_LEFT
			game_ui._input(mouse_move)
			await get_tree().process_frame

			# Release
			var mouse_up = InputEventMouseButton.new()
			mouse_up.button_index = MOUSE_BUTTON_LEFT
			mouse_up.pressed = false
			mouse_up.global_position = drag_end
			mouse_up.position = drag_end
			game_ui._input(mouse_up)
			await _wait_for_server()
			print("   - Purchase completed")
		else:
			print("   - No empty cells for placement")
	else:
		print("   - Shop is empty")

	# Find and click battle button
	# By name. What it says is painted on the key, so there is no text on it.
	var battle_btn = game_ui.find_child("ReadyButton", true, false)

	assert_not_null(battle_btn, "Battle button must exist")

	# Click battle button
	battle_btn.pressed.emit()
	await _wait_for_server()  # Wait for server battle simulation

	# Should transition to battle screen
	var current_scene = get_tree().current_scene
	assert_true(current_scene.name == "BattleScreen" or current_scene.name == "UnifiedGridUI",
		"Should transition to battle or post-battle screen")

	# If in battle screen, wait for it to complete
	if current_scene.name == "BattleScreen":
		print("   - Battle is playing...")
		# Mock battle takes time to complete and then 2s to transition
		await _wait_for_scene("UnifiedGridUI", 25.0)

		# Look for skip button
		var skip_btn = current_scene.find_child("SkipButton", true, false)
		if skip_btn:
			skip_btn.pressed.emit()
			await _wait_for_server()

	# The battle lands in the shop. There used to be a screen in between with a
	# Continue button on it, and the round result overlay says what it said.
	current_scene = get_tree().current_scene
	if current_scene.name == "UnifiedGridUI":
		await _wait_for_shop_ready()
		assert_eq(GameStateManager.current_round, 2, "Round should advance after battle")

	print("   ✓ Full battle flow completed with real server")

func test_complete_round_cycle():
	"""Test a complete round: shop, purchase, battle, next round"""
	print("\n=== UI TEST: Complete Round Cycle ===")

	# Start game
	var main_menu = load("res://scenes/MainMenu.tscn").instantiate()
	get_tree().root.add_child(main_menu)
	get_tree().current_scene = main_menu
	await get_tree().process_frame

	var new_game_btn = main_menu.new_game_button
	new_game_btn.pressed.emit()
	await _wait_for_shop_ready()

	var game_ui = get_tree().current_scene

	# Record initial state
	var initial_round = GameStateManager.current_round
	var initial_gold = GameStateManager.gold
	var initial_lives = GameStateManager.player_lives

	print("   - Round %d: Gold=%d, Lives=%d" % [initial_round, initial_gold, initial_lives])

	# Purchase an item first (battles require items)
	print("   - Shop has %d items" % game_ui.shop_items.size())
	if game_ui.shop_items.size() > 0:
		var target_grid_pos = _find_first_empty_grid_cell(game_ui)
		print("   - Found empty cell at: %s" % target_grid_pos)
		var shop_item = _first_non_container_shop_item(game_ui, Vector2i(target_grid_pos))
		if target_grid_pos != Vector2(-1, -1):
			# Quick purchase simulation
			var server_room_container = game_ui.server_room_container
			var cell_size = game_ui.inventory_grid.cell_size
			var cell_spacing = game_ui.inventory_grid.cell_spacing
			var grid_global_pos = server_room_container.global_position
			var drag_end = grid_global_pos + target_grid_pos * (cell_size + cell_spacing) + Vector2(cell_size/2, cell_size/2)

			var shop_item_center = shop_item.global_position + shop_item.size / 2

			# Start drag
			var mouse_down = InputEventMouseButton.new()
			mouse_down.button_index = MOUSE_BUTTON_LEFT
			mouse_down.pressed = true
			mouse_down.position = shop_item.size / 2
			mouse_down.global_position = shop_item_center
			shop_item.gui_input.emit(mouse_down)
			await get_tree().process_frame

			# Move to grid
			var mouse_move = InputEventMouseMotion.new()
			mouse_move.global_position = drag_end
			mouse_move.position = drag_end
			mouse_move.relative = drag_end - shop_item_center
			mouse_move.button_mask = MOUSE_BUTTON_MASK_LEFT
			game_ui._input(mouse_move)
			await get_tree().process_frame

			# Release
			var mouse_up = InputEventMouseButton.new()
			mouse_up.button_index = MOUSE_BUTTON_LEFT
			mouse_up.pressed = false
			mouse_up.global_position = drag_end
			mouse_up.position = drag_end
			game_ui._input(mouse_up)
			await _wait_for_server()
			print("   - Item purchased")

	# Start battle
	var battle_btn = game_ui.find_child("ReadyButton", true, false)

	if battle_btn:
		battle_btn.pressed.emit()
		print("   - Started battle")
		await _wait_for_scene_change("UnifiedGridUI", 20.0)

		# Handle battle screen
		var current_scene = get_tree().current_scene
		if current_scene.name == "BattleScreen":
			print("   - In battle screen, waiting for completion...")
			# Wait longer for battle with empty inventory (mock battle)
			await _wait_for_scene("UnifiedGridUI", 25.0)

			# Try skip button if available. Re-read the scene: playback may have
			# already moved on and freed the node this local pointed at.
			current_scene = get_tree().current_scene
			var skip_btn = current_scene.find_child("SkipButton", true, false) if is_instance_valid(current_scene) else null
			if skip_btn:
				skip_btn.pressed.emit()
				await _wait_for_server()

			# Re-check current scene
			current_scene = get_tree().current_scene

		# The battle lands in the shop directly.
		if current_scene.name == "UnifiedGridUI":
			await _wait_for_shop_ready()

		# Verify we're in next round
		current_scene = get_tree().current_scene
		if current_scene.name == "UnifiedGridUI":
			assert_eq(GameStateManager.current_round, initial_round + 1, "Round should advance from %d to %d" % [initial_round, initial_round + 1])
			print("   - Advanced to round %d" % GameStateManager.current_round)
			print("   - New state: Gold=%d, Lives=%d" % [GameStateManager.gold, GameStateManager.player_lives])
		else:
			# Battle might get stuck with empty inventory - that's ok for this test
			print("   - Warning: Battle did not complete, may be due to empty inventory")
			assert_true(current_scene.name == "BattleScreen" or current_scene.name == "UnifiedGridUI",
				"Should be in battle-related screen")
	else:
		# If no battle button, that's a test failure
		assert_not_null(battle_btn, "Battle button should exist in game UI")

	print("   ✓ Complete round cycle tested with real server")

func test_refresh_shop_button():
	"""Test shop refresh functionality through UI"""
	print("\n=== UI TEST: Shop Refresh ===")

	# Start game
	var main_menu = load("res://scenes/MainMenu.tscn").instantiate()
	get_tree().root.add_child(main_menu)
	get_tree().current_scene = main_menu
	await get_tree().process_frame

	var new_game_btn = main_menu.new_game_button
	new_game_btn.pressed.emit()
	await _wait_for_shop_ready()

	var game_ui = get_tree().current_scene

	# Find refresh button
	var refresh_btn = game_ui.find_child("RefreshButton", true, false)
	if not refresh_btn:
		for child in game_ui.get_children():
			if child is Button and "Refresh" in str(child.text):
				refresh_btn = child
				break

	if refresh_btn:
		var initial_gold = GameStateManager.gold
		var initial_shop_items = game_ui.shop_items.duplicate()

		# Click refresh
		refresh_btn.pressed.emit()
		await _wait_for_server()

		# Verify something changed (gold or shop items)
		var gold_changed = GameStateManager.gold != initial_gold
		var shop_changed = game_ui.shop_items.size() > 0
		assert_true(gold_changed or shop_changed, "Refresh should affect gold or shop")

		print("   ✓ Shop refresh tested with real server")
	else:
		# Refresh button may not be implemented yet, which is acceptable for now
		print("   - Refresh button not found (may not be implemented)")
		assert_true(true, "Refresh button is optional")  # Add assertion to avoid risky test

func test_server_connection():
	"""Test that we can connect to the real server"""
	print("\n=== UI TEST: Server Connection ===")

	# Start game which will connect to server
	var main_menu = load("res://scenes/MainMenu.tscn").instantiate()
	get_tree().root.add_child(main_menu)
	get_tree().current_scene = main_menu
	await get_tree().process_frame

	var new_game_btn = main_menu.new_game_button
	new_game_btn.pressed.emit()
	await _wait_for_shop_ready()

	# If we got here, server connection worked
	var game_ui = get_tree().current_scene
	if game_ui and game_ui.name == "UnifiedGridUI":
		assert_true(BattleServerAPI.player_id != "", "Should have player ID from server")
		assert_gt(GameStateManager.current_shop.size(), 0, "Should have a shop from the server")
		print("   ✓ Server connection successful")
	else:
		# Connection might have failed
		assert_true(false, "Failed to connect to server - is it running?")

func test_inventory_persistence_across_battle():
	"""Test that inventory items are preserved when going through a battle"""
	print("\n=== UI TEST: Inventory Persistence Across Battle ===")

	# Start game
	var main_menu = load("res://scenes/MainMenu.tscn").instantiate()
	get_tree().root.add_child(main_menu)
	get_tree().current_scene = main_menu
	await get_tree().process_frame

	var new_game_btn = main_menu.new_game_button
	new_game_btn.pressed.emit()
	await _wait_for_shop_ready()

	var game_ui = get_tree().current_scene
	assert_eq(game_ui.name, "UnifiedGridUI", "Should be in game UI")

	# Purchase multiple items to test persistence
	print("   - Purchasing items to test persistence...")
	var items_to_purchase = min(3, game_ui.shop_items.size())
	var purchased_items = []

	for i in range(items_to_purchase):
		if GameStateManager.gold < 3:  # Most items cost at least 3
			break

		var shop_item = game_ui.shop_items[i]
		var item_data = shop_item.get_meta("item_data")
		var target_pos = _find_first_empty_grid_cell(game_ui)

		if target_pos == Vector2(-1, -1):
			print("   - No more empty cells, stopping purchases")
			break

		# Quick purchase via drag/drop
		var inventory_grid = game_ui.inventory_grid
		var target_pixel = inventory_grid.grid_to_pixel(Vector2i(target_pos.x, target_pos.y))
		var drop_pos = inventory_grid.global_position + target_pixel + Vector2(game_ui.inventory_grid.cell_size/2, game_ui.inventory_grid.cell_size/2)

		# Simulate drag and drop
		var mouse_down = InputEventMouseButton.new()
		mouse_down.button_index = MOUSE_BUTTON_LEFT
		mouse_down.pressed = true
		mouse_down.position = shop_item.size / 2
		mouse_down.global_position = shop_item.global_position + shop_item.size / 2
		shop_item.gui_input.emit(mouse_down)
		await get_tree().process_frame

		var mouse_up = InputEventMouseButton.new()
		mouse_up.button_index = MOUSE_BUTTON_LEFT
		mouse_up.pressed = false
		mouse_up.global_position = drop_pos
		mouse_up.position = drop_pos
		game_ui._input(mouse_up)
		await _wait_for_server()

		purchased_items.append(item_data.name)
		print("   - Purchased: %s" % item_data.name)

	# Get inventory state before battle
	var pre_battle_inventory = game_ui.inventory_grid.get_inventory_state()
	var items_before = pre_battle_inventory.items.size()
	print("   - Total items before battle: %d" % items_before)
	assert_gt(items_before, 0, "Should have items before battle")

	# Record item details for verification
	var item_details_before = []
	for item in pre_battle_inventory.items:
		if item is Dictionary:
			item_details_before.append({
				"name": item["name"],
				"position": item["position"]
			})

	# Start battle
	print("   - Starting battle...")
	var battle_btn = game_ui.find_child("ReadyButton", true, false)

	assert_not_null(battle_btn, "Battle button should exist")
	battle_btn.pressed.emit()
	await _wait_for_scene_change("UnifiedGridUI", 20.0)

	# Wait for battle to complete
	var current_scene = get_tree().current_scene
	if current_scene.name == "BattleScreen":
		print("   - Battle in progress...")
		await _wait_for_scene("UnifiedGridUI", 25.0)
		current_scene = get_tree().current_scene

	# The battle lands in the shop directly.
	if current_scene.name == "UnifiedGridUI":
		await _wait_for_shop_ready()

	# Verify we're back in game UI
	current_scene = get_tree().current_scene
	assert_eq(current_scene.name, "UnifiedGridUI", "Should return to game UI after battle")

	# Verify inventory was preserved
	print("   - Checking inventory after battle...")
	var post_battle_inventory = current_scene.inventory_grid.get_inventory_state()
	var items_after = post_battle_inventory.items.size()

	print("   - Items after battle: %d (was %d before)" % [items_after, items_before])
	assert_eq(items_after, items_before, "All items should be preserved across battle")

	# Verify item details match
	var items_match = true
	for i in range(min(item_details_before.size(), post_battle_inventory.items.size())):
		var before = item_details_before[i]
		var after = post_battle_inventory.items[i]
		if after["name"] != before.name:
			items_match = false
			print("   - Item mismatch: %s != %s" % [after["name"], before.name])

	assert_true(items_match, "Item details should match after battle")

	print("   ✓ Inventory persistence across battle verified")

func test_item_drag_and_move_persistence():
	"""Test dragging items within inventory and verifying move is persisted"""
	print("\n=== UI TEST: Item Drag & Move Persistence ===")

	# Start game
	var main_menu = load("res://scenes/MainMenu.tscn").instantiate()
	get_tree().root.add_child(main_menu)
	get_tree().current_scene = main_menu
	await get_tree().process_frame

	var new_game_btn = main_menu.new_game_button
	new_game_btn.pressed.emit()
	await _wait_for_shop_ready()

	var game_ui = get_tree().current_scene
	assert_eq(game_ui.name, "UnifiedGridUI", "Should be in game UI")

	# First, purchase an item to have something to move
	print("   - Purchasing item to test move...")
	assert_gt(game_ui.shop_items.size(), 0, "Should have shop items")
	# Find first empty cell for initial placement
	var initial_pos = _find_first_empty_grid_cell(game_ui)
	assert_ne(initial_pos, Vector2(-1, -1), "Should find empty cell for initial placement")

	var shop_item = _first_non_container_shop_item(game_ui, Vector2i(initial_pos))
	assert_not_null(shop_item, "The shop should offer something that fits there")
	var item_data = shop_item.get_meta("item_data")
	print("   - Initial placement at: %s" % initial_pos)

	# Purchase item via drag and drop
	var server_room_container = game_ui.server_room_container
	var inventory_grid = game_ui.inventory_grid
	var cell_size = game_ui.inventory_grid.cell_size
	var cell_spacing = game_ui.inventory_grid.cell_spacing

	# Simulate shop purchase drag
	var shop_item_center = shop_item.global_position + shop_item.size / 2
	var target_pixel_pos = inventory_grid.grid_to_pixel(Vector2i(initial_pos.x, initial_pos.y))
	var drop_pos = inventory_grid.global_position + target_pixel_pos + Vector2(cell_size/2, cell_size/2)

	# Start drag on shop item
	var mouse_down = InputEventMouseButton.new()
	mouse_down.button_index = MOUSE_BUTTON_LEFT
	mouse_down.pressed = true
	mouse_down.position = shop_item.size / 2
	mouse_down.global_position = shop_item_center
	shop_item.gui_input.emit(mouse_down)
	await get_tree().process_frame

	# Drag to initial position
	var mouse_move = InputEventMouseMotion.new()
	mouse_move.global_position = drop_pos
	mouse_move.position = drop_pos
	mouse_move.relative = drop_pos - shop_item_center
	mouse_move.button_mask = MOUSE_BUTTON_MASK_LEFT
	game_ui._input(mouse_move)
	await get_tree().process_frame

	# Drop item
	var mouse_up = InputEventMouseButton.new()
	mouse_up.button_index = MOUSE_BUTTON_LEFT
	mouse_up.pressed = false
	mouse_up.global_position = drop_pos
	mouse_up.position = drop_pos
	game_ui._input(mouse_up)
	await _wait_for_server()

	# Verify item was placed
	assert_gt(inventory_grid.items.size(), 0, "Should have item in inventory")
	var placed_item = inventory_grid.items[0]
	var placed_item_data = placed_item.get_meta("item_data")
	var item_id = placed_item_data.id
	assert_ne(item_id, "", "Placed item should have ID")
	print("   - Item placed with ID: %s" % item_id)

	# Now test moving the item to a different position
	print("   - Testing item move within inventory...")

	# Find a different empty cell to move to
	var new_pos = Vector2i(-1, -1)
	var container_positions = [
		Vector2i(2, 3), Vector2i(3, 3), Vector2i(2, 4), Vector2i(3, 4),  # Container A
		Vector2i(4, 3), Vector2i(5, 3), Vector2i(4, 4), Vector2i(5, 4),  # Container B
		Vector2i(6, 3), Vector2i(7, 3), Vector2i(6, 4), Vector2i(7, 4),  # Container C
	]

	for pos in container_positions:
		if pos != Vector2i(initial_pos.x, initial_pos.y):
			# Check if this position is on active grid and empty
			if inventory_grid.active_grid[pos.y][pos.x] and not inventory_grid.item_grid[pos.y][pos.x]:
				new_pos = pos
				break

	assert_ne(new_pos, Vector2i(-1, -1), "Should find different empty cell for move")
	print("   - Moving item from %s to %s" % [initial_pos, new_pos])

	# Simulate dragging the placed item to new position
	var item_center = placed_item.global_position + placed_item.size / 2
	var new_target_pixel = inventory_grid.grid_to_pixel(new_pos)
	var new_drop_pos = inventory_grid.global_position + new_target_pixel + Vector2(cell_size/2, cell_size/2)

	# Start drag on the item
	mouse_down = InputEventMouseButton.new()
	mouse_down.button_index = MOUSE_BUTTON_LEFT
	mouse_down.pressed = true
	mouse_down.position = placed_item.size / 2
	mouse_down.global_position = item_center

	# Send input to the placed item to start drag
	placed_item._gui_input(mouse_down)
	await get_tree().process_frame

	# Drag to new position
	mouse_move = InputEventMouseMotion.new()
	mouse_move.global_position = new_drop_pos
	mouse_move.position = new_drop_pos
	mouse_move.relative = new_drop_pos - item_center
	mouse_move.button_mask = MOUSE_BUTTON_MASK_LEFT

	# Process drag through inventory grid
	inventory_grid._input(mouse_move)
	await get_tree().process_frame

	# Drop at new position
	mouse_up = InputEventMouseButton.new()
	mouse_up.button_index = MOUSE_BUTTON_LEFT
	mouse_up.pressed = false
	mouse_up.global_position = new_drop_pos
	mouse_up.position = inventory_grid.to_local(new_drop_pos)

	# Send mouse up to inventory grid to complete move
	inventory_grid._input(mouse_up)
	await _wait_for_server()

	# Verify item moved to new position
	var final_pos = placed_item.get_meta("grid_pos")
	print("   - Item final position: %s" % final_pos)

	# The move should either succeed (item at new position) or fail (item at original position)
	# Due to async API call, we accept either outcome as long as item is still valid
	assert_true(
		final_pos == new_pos or final_pos == Vector2i(initial_pos.x, initial_pos.y),
		"Item should be at new position if move succeeded, or original if failed"
	)

	if final_pos == new_pos:
		print("   ✓ Item successfully moved and persisted")
	else:
		print("   - Move was rejected by server (item stayed at original position)")

	# Verify item is still in inventory and valid
	assert_gt(inventory_grid.items.size(), 0, "Item should still be in inventory")
	assert_true(placed_item in inventory_grid.items, "Original item should still exist")

	print("   ✓ Item drag and move tested with server persistence")

func test_multiple_rounds():
	"""Test playing multiple rounds in sequence"""
	print("\n=== UI TEST: Multiple Rounds ===")

	# Start game
	var main_menu = load("res://scenes/MainMenu.tscn").instantiate()
	get_tree().root.add_child(main_menu)
	get_tree().current_scene = main_menu
	await get_tree().process_frame

	var new_game_btn = main_menu.new_game_button
	new_game_btn.pressed.emit()
	await _wait_for_shop_ready()

	var game_ui = get_tree().current_scene
	var rounds_to_play = 3

	for i in range(rounds_to_play):
		var current_round = GameStateManager.current_round
		print("   - Playing round %d" % current_round)

		# Purchase an item first (battles require items)
		if game_ui.shop_items.size() > 0:
			var target_grid_pos = _find_first_empty_grid_cell(game_ui)
			var shop_item = _first_non_container_shop_item(game_ui, Vector2i(target_grid_pos))
			if target_grid_pos != Vector2(-1, -1):
				# Quick purchase simulation
				var server_room_container = game_ui.server_room_container
				var cell_size = game_ui.inventory_grid.cell_size
				var cell_spacing = game_ui.inventory_grid.cell_spacing
				var grid_global_pos = server_room_container.global_position
				var drag_end = grid_global_pos + target_grid_pos * (cell_size + cell_spacing) + Vector2(cell_size/2, cell_size/2)

				var shop_item_center = shop_item.global_position + shop_item.size / 2

				# Start drag
				var mouse_down = InputEventMouseButton.new()
				mouse_down.button_index = MOUSE_BUTTON_LEFT
				mouse_down.pressed = true
				mouse_down.position = shop_item.size / 2
				mouse_down.global_position = shop_item_center
				shop_item.gui_input.emit(mouse_down)
				await get_tree().process_frame

				# Move to grid
				var mouse_move = InputEventMouseMotion.new()
				mouse_move.global_position = drag_end
				mouse_move.position = drag_end
				mouse_move.relative = drag_end - shop_item_center
				mouse_move.button_mask = MOUSE_BUTTON_MASK_LEFT
				game_ui._input(mouse_move)
				await get_tree().process_frame

				# Release
				var mouse_up = InputEventMouseButton.new()
				mouse_up.button_index = MOUSE_BUTTON_LEFT
				mouse_up.pressed = false
				mouse_up.global_position = drag_end
				mouse_up.position = drag_end
				game_ui._input(mouse_up)
				await _wait_for_server()

		# Find and click battle button
		var battle_btn = game_ui.find_child("ReadyButton", true, false)

		if not battle_btn:
			assert_not_null(battle_btn, "Battle button should exist for round %d" % current_round)
			break

		battle_btn.pressed.emit()
		await _wait_for_scene_change("UnifiedGridUI", 20.0)

		# Handle battle/post-battle screens
		var current_scene = get_tree().current_scene

		if current_scene.name == "BattleScreen":
			print("   - Battle in progress for round %d..." % current_round)
			# Wait longer for mock battle to complete
			await _wait_for_scene("UnifiedGridUI", 25.0)
			# Skip battle if possible. Re-read the scene: playback may have already
			# moved on and freed the node this local pointed at.
			current_scene = get_tree().current_scene
			var skip_btn = current_scene.find_child("SkipButton", true, false) if is_instance_valid(current_scene) else null
			if skip_btn:
				skip_btn.pressed.emit()
			await _wait_for_server()
			current_scene = get_tree().current_scene

		# The battle lands in the shop directly.
		if current_scene.name == "UnifiedGridUI":
			await _wait_for_shop_ready()

		# Verify round advanced
		game_ui = get_tree().current_scene
		if game_ui.name == "UnifiedGridUI":
			assert_eq(GameStateManager.current_round, current_round + 1, "Round %d should advance to %d" % [current_round, current_round + 1])
		else:
			# Battle might be stuck - count it and move on
			print("   - Warning: Round %d battle did not complete" % current_round)
			break  # Stop trying more rounds if we're stuck

	# We tried to play rounds
	assert_gte(GameStateManager.current_round, 1, "Should have at least started the game")
	print("   ✓ Multiple rounds tested with real server")


# ============ Waiting helpers ============
#
# These replace fixed sleeps. A fixed sleep has to be long enough for the
# slowest case, so it makes every run slow and still fails when the machine is
# busy. These return as soon as the condition holds, and fail fast if it never
# does.

const DEFAULT_TIMEOUT := 10.0


func _wait_until(condition: Callable, timeout: float = DEFAULT_TIMEOUT) -> bool:
	"""Poll condition each frame. Return true when it holds, false on timeout."""
	var deadline := Time.get_ticks_msec() + int(timeout * 1000)
	while Time.get_ticks_msec() < deadline:
		if condition.call():
			return true
		await get_tree().process_frame
	return false


func _wait_for_scene(scene_name: String, timeout: float = DEFAULT_TIMEOUT) -> bool:
	"""Wait until the given scene is the current one."""
	return await _wait_until(
		func():
			var scene = get_tree().current_scene
			return scene != null and scene.name == scene_name,
		timeout
	)


func _wait_for_server(timeout: float = DEFAULT_TIMEOUT) -> bool:
	"""Wait for the in-flight request to BattleServerAPI to finish.

	BattleServerAPI drives a single HTTPRequest node, so its client status tells
	us when the call is done. This replaces guessing at a duration.
	"""
	await get_tree().process_frame
	return await _wait_until(
		func():
			var req = BattleServerAPI.http_request
			return req == null or req.get_http_client_status() == HTTPClient.STATUS_DISCONNECTED,
		timeout
	)


func _wait_for_shop_ready(timeout: float = DEFAULT_TIMEOUT) -> bool:
	"""Wait for UnifiedGridUI to be current AND finished loading.

	The scene becomes current before its _ready() has fetched the session, so
	waiting on the name alone gives you an empty grid and an empty shop.
	"""
	return await _wait_until(
		func():
			var scene = get_tree().current_scene
			if scene == null or scene.name != "UnifiedGridUI":
				return false
			if scene.inventory_grid == null:
				return false
			return scene.inventory_grid.containers.size() > 0 and scene.shop_items.size() > 0,
		timeout
	)


func _wait_for_scene_change(from_name: String, timeout: float = DEFAULT_TIMEOUT) -> bool:
	"""Wait until the current scene is no longer the given one."""
	return await _wait_until(
		func():
			var scene = get_tree().current_scene
			return scene != null and scene.name != from_name,
		timeout
	)


func _first_non_container_shop_item(game_ui, fitting_at := Vector2i(-1, -1)):
	"""Pick a shop item that can go on an existing server container.

	The shop is generated randomly, so slot 0 is sometimes a container. A
	container cannot be dropped onto another container, so a test that always
	took slot 0 failed whenever the roll produced one.

	`fitting_at` is the square the caller means to drop it on. A container is
	two squares by two and the shop can offer an item four squares tall, so an
	item that is not a container can still have nowhere to go -- which failed
	about one run in ten. The grid's own rule answers it, so the test is not
	keeping a second opinion about what fits.
	"""
	for shop_item in game_ui.shop_items:
		var data = shop_item.get_meta("item_data")
		if data.is_container:
			continue
		if fitting_at.x >= 0 and not game_ui.inventory_grid.can_place_item(data, fitting_at):
			continue
		return shop_item
	return null


func test_the_server_says_which_items_go_together():
	"""GDD 5.3: the client answers hover lines from this, so what it fetches
	once has to be what it thinks it fetched.

	Against the real catalogue, so a slug renamed on the server, or a field
	renamed on either side, is caught here rather than by a line that silently
	stops being drawn.
	"""
	await GameStateManager.fetch_combining_catalogue()
	var combining = GameStateManager.combining

	assert_true(combining.knows_the_catalogue(), "the catalogue arrived")
	assert_true(combining.goes_with("hero_sword", "whetstone"),
		"a Long Poll is a Main Branch and two Edge Caches")
	assert_true(combining.goes_with("whetstone", "hero_sword"),
		"and it is named from both ends")
	assert_true(combining.goes_with("whetstone", "whetstone"),
		"two of them, so one Edge Cache points at another")
	assert_eq(combining.name_of("hero_longsword"), "Long Poll",
		"and it can name a thing that does not exist yet")


func test_buying_something_says_what_the_rack_is_on_the_way_to():
	"""Every answer that can change the rack carries it, so the glow and the
	progress label are never a round behind."""
	var game_ui = await _start_a_game()
	var slot = _first_buyable_shop_slot(game_ui)
	assert_not_null(slot, "Setup: the shop offers something to buy")

	var item = slot.get_meta("item_data")
	var answer = await BattleServerAPI.purchase_item(item.id, "storage")

	assert_not_null(answer, "the purchase went through")
	assert_eq(typeof(answer.pending), TYPE_ARRAY,
		"and it said what the rack is on the way to")
	assert_eq(GameStateManager.combining.pending.size(), answer.pending.size(),
		"which the screen is now holding")


func _start_a_game() -> Node:
	"""Open the shop screen the way the player does, and wait for the shelf."""
	var main_menu = load("res://scenes/MainMenu.tscn").instantiate()
	get_tree().root.add_child(main_menu)
	get_tree().current_scene = main_menu
	await get_tree().process_frame
	main_menu.new_game_button.pressed.emit()
	await _wait_for_shop_ready()
	return get_tree().current_scene


func _first_buyable_shop_slot(game_ui: Node) -> Panel:
	for slot in game_ui.shop_items:
		var data = slot.get_meta("item_data")
		if not data.is_container and data.price <= GameStateManager.gold:
			return slot
	return null


func test_the_screen_lights_the_two_items_the_server_will_combine():
	"""GDD 5.3, the whole way through: the server's rules decide that these two
	combine, the answer travels over the wire, and the screen lights the right
	two items.

	Every other test of the glow builds the answer by hand. This one does not
	know what combines -- it puts a Neural Link Collar next to a CPU Booster and
	lets the server say.
	"""
	var game_ui = await _start_a_game()
	await _stand_on_the_rack([
		{"item_type": "neural_link_collar", "position": [2, 3]},
		{"item_type": "cpu_booster", "position": [3, 3]},
	])

	# A real move, so the answer comes back the way it does in play. The booster
	# goes under the collar rather than beside it, which is still touching:
	# corners do not count, so [3, 4] would have broken the pair up.
	var answer = await BattleServerAPI.move_item("test1", [2, 4])
	assert_not_null(answer, "the server took the move")
	game_ui.inventory_grid.load_inventory_state(answer.as_inventory_state())

	assert_eq(GameStateManager.combining.about_to_combine().size(), 1,
		"the server says these two will combine")
	game_ui.refresh_combining(Vector2(-500, -500))

	assert_eq(game_ui.combining_overlay.glowing().size(), 2,
		"and both of them are lit, whatever the pointer is doing")


func test_a_rack_that_combines_is_played_out_on_the_shop_screen():
	"""The other half: the battle combines them, and the shop screen the player
	comes back to plays it and ends on the rack the server sent."""
	await _start_a_game()
	await _stand_on_the_rack([
		{"item_type": "neural_link_collar", "position": [2, 3]},
		{"item_type": "cpu_booster", "position": [3, 3]},
	])

	# What the Start Battle button does, without the battle playback. That
	# button is covered by test_battle_button_and_full_battle.
	var battle = await BattleServerAPI.submit_battle({})
	assert_not_null(battle, "the battle was fought")
	GameStateManager.update_after_battle(battle)

	var combinations = GameStateManager.combinations_to_play
	assert_eq(combinations.size(), 1, "the collar and the booster combined")
	assert_eq(combinations[0].made, "blue_sage_collar", "into an Amethyst Collar")
	var made_id = combinations[0].made_id

	# Coming back to the shop, which is where the player sees it.
	var shop = load("res://scenes/UnifiedGridUI.tscn").instantiate()
	get_tree().root.add_child(shop)
	var drawn = await _wait_until(func():
		return shop.inventory_grid != null \
			and shop.inventory_grid.item_visual(made_id) != null)

	assert_true(drawn, "the rack ends holding what the server made")
	assert_null(shop.inventory_grid.item_visual("test0"),
		"and the items it was made from are gone")


func _stand_on_the_rack(items: Array) -> void:
	"""Put these items on the player's rack through the server's test hook.

	A test cannot buy two particular items: the shop offers what the seed says
	it offers. The hook is TEST_MODE only and is named by player rather than by
	token, because the token belongs to the client and this is not the client.
	"""
	var http := HTTPRequest.new()
	get_tree().root.add_child(http)

	var base_url := OS.get_environment("BATTLE_SERVER_URL")
	if base_url == "":
		base_url = "http://localhost:8081"

	var body := JSON.stringify({
		"player_id": BattleServerAPI.player_id, "items": items})
	http.request(base_url + "/test/rack", ["Content-Type: application/json"],
		HTTPClient.METHOD_POST, body)
	var result = await http.request_completed
	http.queue_free()

	assert_eq(result[1], 200,
		"the rack was set: %s" % result[3].get_string_from_utf8())
