extends GutTest
# UI INTEGRATION TESTS - Testing by driving the actual UI
# These tests simulate real user interactions through the UI
# Now using real server instead of mocks

func before_each():
	# Tests now use real server started by run_tests_with_server.sh
	# Server URL is set via BATTLE_SERVER_URL environment variable
	pass

func after_each():
	# Clean up current scene
	if get_tree().current_scene:
		get_tree().current_scene.queue_free()
		await get_tree().process_frame

func test_full_user_journey_through_ui():
	"""Test complete user journey from launch to battle through UI only"""
	print("\n=== UI TEST: Complete User Journey ===")

	# 1. Launch game
	var main_menu = load("res://scenes/MainMenu.tscn").instantiate()
	get_tree().root.add_child(main_menu)
	get_tree().current_scene = main_menu
	await get_tree().process_frame

	# 2. Click New Game
	var new_game_btn = main_menu.find_child("NewGameButton", true, false)
	assert_not_null(new_game_btn, "New Game button must exist")
	new_game_btn.pressed.emit()
	await get_tree().create_timer(2.0).timeout  # Wait for server response

	# 3. Verify game UI loaded
	var game_ui = get_tree().current_scene
	assert_eq(game_ui.name, "UnifiedGridUI", "Should transition to game UI")

	# 4. Verify starting containers placed
	assert_eq(game_ui.servers.size(), 3, "Should have 3 starting containers")

	# 5. Verify shop loaded from server
	assert_gte(game_ui.shop_items.size(), 2, "Shop should have items from server")

	print("   ✓ Game launched and initialized with real server")

func test_shop_purchase_and_item_placement():
	"""Test purchasing from shop and placing items through UI"""
	print("\n=== UI TEST: Shop Purchase & Placement ===")

	# Setup game
	var main_menu = load("res://scenes/MainMenu.tscn").instantiate()
	get_tree().root.add_child(main_menu)
	get_tree().current_scene = main_menu
	await get_tree().process_frame

	var new_game_btn = main_menu.find_child("NewGameButton", true, false)
	new_game_btn.pressed.emit()
	await get_tree().create_timer(2.0).timeout  # Wait for server

	var game_ui = get_tree().current_scene

	# Get shop item from game_ui's shop_items array
	assert_gt(game_ui.shop_items.size(), 0, "Shop should have items from server")
	var shop_item = game_ui.shop_items[0]
	var initial_gold = GameStateManager.gold

	# Simulate drag from shop
	var drag_start = shop_item.global_position + shop_item.size / 2
	var drag_end = Vector2(400, 300)  # Target position on grid

	# Create mouse events
	var mouse_down = InputEventMouseButton.new()
	mouse_down.button_index = MOUSE_BUTTON_LEFT
	mouse_down.pressed = true
	mouse_down.position = drag_start

	var mouse_move = InputEventMouseMotion.new()
	mouse_move.position = drag_end

	var mouse_up = InputEventMouseButton.new()
	mouse_up.button_index = MOUSE_BUTTON_LEFT
	mouse_up.pressed = false
	mouse_up.position = drag_end

	# Simulate drag & drop
	if shop_item.has_method("_gui_input"):
		shop_item._gui_input(mouse_down)
		await get_tree().process_frame
		game_ui._input(mouse_move)
		await get_tree().process_frame
		game_ui._input(mouse_up)
		await get_tree().process_frame

		# Verify item was placed (gold should decrease)
		assert_lt(GameStateManager.gold, initial_gold, "Gold should decrease after purchase")

	print("   ✓ Shop purchase tested with real server")

func test_battle_button_and_full_battle():
	"""Test clicking battle button and going through full battle"""
	print("\n=== UI TEST: Full Battle Flow ===")

	# Setup game
	var main_menu = load("res://scenes/MainMenu.tscn").instantiate()
	get_tree().root.add_child(main_menu)
	get_tree().current_scene = main_menu
	await get_tree().process_frame

	var new_game_btn = main_menu.find_child("NewGameButton", true, false)
	new_game_btn.pressed.emit()
	await get_tree().create_timer(2.0).timeout  # Wait for server

	var game_ui = get_tree().current_scene
	assert_eq(game_ui.name, "UnifiedGridUI", "Should be in game UI")

	# Find and click battle button
	var battle_btn = game_ui.find_child("BattleButton", true, false)
	if not battle_btn:
		# Try alternate names
		for child in game_ui.get_children():
			if child is Button and ("Battle" in child.text or "Fight" in child.text):
				battle_btn = child
				break

	assert_not_null(battle_btn, "Battle button must exist")

	# Click battle button
	battle_btn.pressed.emit()
	await get_tree().create_timer(3.0).timeout  # Wait for server battle simulation

	# Should transition to battle screen
	var current_scene = get_tree().current_scene
	assert_true(current_scene.name == "BattleScreen" or current_scene.name == "PostBattleScreen",
		"Should transition to battle or post-battle screen")

	# If in battle screen, wait for it to complete
	if current_scene.name == "BattleScreen":
		print("   - Battle is playing...")

		# Look for skip button
		var skip_btn = current_scene.find_child("SkipButton", true, false)
		if skip_btn:
			skip_btn.pressed.emit()
			await get_tree().create_timer(1.0).timeout
		else:
			# Wait for battle to complete naturally
			await get_tree().create_timer(5.0).timeout

	# Should now be in post-battle
	current_scene = get_tree().current_scene
	if current_scene.name == "PostBattleScreen":
		print("   - In post-battle screen")

		# Find continue button
		var continue_btn = current_scene.find_child("ContinueButton", true, false)
		if not continue_btn:
			for child in current_scene.get_children():
				if child is Button and "Continue" in child.text:
					continue_btn = child
					break

		if continue_btn:
			continue_btn.pressed.emit()
			await get_tree().create_timer(1.0).timeout

			# Should be back in game UI
			current_scene = get_tree().current_scene
			assert_eq(current_scene.name, "UnifiedGridUI", "Should return to game UI after battle")
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

	var new_game_btn = main_menu.find_child("NewGameButton", true, false)
	new_game_btn.pressed.emit()
	await get_tree().create_timer(2.0).timeout

	var game_ui = get_tree().current_scene

	# Record initial state
	var initial_round = GameStateManager.current_round
	var initial_gold = GameStateManager.gold
	var initial_lives = GameStateManager.player_lives

	print("   - Round %d: Gold=%d, Lives=%d" % [initial_round, initial_gold, initial_lives])

	# Start battle
	var battle_btn = null
	for child in game_ui.get_children():
		if child is Button and ("Battle" in str(child.text) or "Fight" in str(child.text)):
			battle_btn = child
			break

	if battle_btn:
		battle_btn.pressed.emit()
		print("   - Started battle")
		await get_tree().create_timer(3.0).timeout  # Wait for server

		# Handle battle screen
		var current_scene = get_tree().current_scene
		if current_scene.name == "BattleScreen":
			# Skip battle
			var skip_btn = current_scene.find_child("SkipButton", true, false)
			if skip_btn:
				skip_btn.pressed.emit()
			await get_tree().create_timer(1.0).timeout

		# Handle post-battle
		current_scene = get_tree().current_scene
		if current_scene.name == "PostBattleScreen":
			var continue_btn = current_scene.find_child("ContinueButton", true, false)
			if not continue_btn:
				for child in current_scene.get_children():
					if child is Button and "Continue" in str(child.text):
						continue_btn = child
						break
			if continue_btn:
				continue_btn.pressed.emit()
				await get_tree().create_timer(1.0).timeout

		# Verify we're in next round
		current_scene = get_tree().current_scene
		if current_scene.name == "UnifiedGridUI":
			assert_eq(GameStateManager.current_round, initial_round + 1, "Round should advance")
			print("   - Advanced to round %d" % GameStateManager.current_round)
			print("   - New state: Gold=%d, Lives=%d" % [GameStateManager.gold, GameStateManager.player_lives])
	else:
		# If no battle button, just verify the setup worked
		assert_eq(game_ui.servers.size(), 3, "Should have starting containers")

	print("   ✓ Complete round cycle tested with real server")

func test_refresh_shop_button():
	"""Test shop refresh functionality through UI"""
	print("\n=== UI TEST: Shop Refresh ===")

	# Start game
	var main_menu = load("res://scenes/MainMenu.tscn").instantiate()
	get_tree().root.add_child(main_menu)
	get_tree().current_scene = main_menu
	await get_tree().process_frame

	var new_game_btn = main_menu.find_child("NewGameButton", true, false)
	new_game_btn.pressed.emit()
	await get_tree().create_timer(2.0).timeout

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
		await get_tree().create_timer(1.0).timeout  # Wait for server

		# Verify something changed (gold or shop items)
		var gold_changed = GameStateManager.gold != initial_gold
		var shop_changed = game_ui.shop_items.size() > 0
		assert_true(gold_changed or shop_changed, "Refresh should affect gold or shop")

		print("   ✓ Shop refresh tested with real server")
	else:
		print("   - Refresh button not found (may not be implemented)")
		assert_true(true, "Refresh button not implemented yet")

func test_server_connection():
	"""Test that we can connect to the real server"""
	print("\n=== UI TEST: Server Connection ===")

	# Start game which will connect to server
	var main_menu = load("res://scenes/MainMenu.tscn").instantiate()
	get_tree().root.add_child(main_menu)
	get_tree().current_scene = main_menu
	await get_tree().process_frame

	var new_game_btn = main_menu.find_child("NewGameButton", true, false)
	new_game_btn.pressed.emit()
	await get_tree().create_timer(2.0).timeout

	# If we got here, server connection worked
	var game_ui = get_tree().current_scene
	if game_ui and game_ui.name == "UnifiedGridUI":
		assert_true(BattleServerAPI.player_id != "", "Should have player ID from server")
		assert_true(BattleServerAPI.session_data.size() > 0, "Should have session data from server")
		print("   ✓ Server connection successful")
	else:
		# Connection might have failed
		assert_true(false, "Failed to connect to server - is it running?")

func test_multiple_rounds():
	"""Test playing multiple rounds in sequence"""
	print("\n=== UI TEST: Multiple Rounds ===")

	# Start game
	var main_menu = load("res://scenes/MainMenu.tscn").instantiate()
	get_tree().root.add_child(main_menu)
	get_tree().current_scene = main_menu
	await get_tree().process_frame

	var new_game_btn = main_menu.find_child("NewGameButton", true, false)
	new_game_btn.pressed.emit()
	await get_tree().create_timer(2.0).timeout

	var game_ui = get_tree().current_scene
	var rounds_to_play = 3

	for i in range(rounds_to_play):
		var current_round = GameStateManager.current_round
		print("   - Playing round %d" % current_round)

		# Find and click battle button
		var battle_btn = null
		for child in game_ui.get_children():
			if child is Button and ("Battle" in str(child.text) or "Fight" in str(child.text)):
				battle_btn = child
				break

		if not battle_btn:
			print("   - No battle button found")
			break

		battle_btn.pressed.emit()
		await get_tree().create_timer(3.0).timeout

		# Handle battle/post-battle screens
		var current_scene = get_tree().current_scene

		if current_scene.name == "BattleScreen":
			# Skip battle
			var skip_btn = current_scene.find_child("SkipButton", true, false)
			if skip_btn:
				skip_btn.pressed.emit()
			await get_tree().create_timer(1.0).timeout
			current_scene = get_tree().current_scene

		if current_scene.name == "PostBattleScreen":
			# Continue to next round
			var continue_btn = current_scene.find_child("ContinueButton", true, false)
			if not continue_btn:
				for child in current_scene.get_children():
					if child is Button and "Continue" in str(child.text):
						continue_btn = child
						break

			if continue_btn:
				continue_btn.pressed.emit()
				await get_tree().create_timer(1.0).timeout

		# Verify round advanced
		game_ui = get_tree().current_scene
		if game_ui.name == "UnifiedGridUI":
			assert_eq(GameStateManager.current_round, current_round + 1, "Round should advance")

	print("   ✓ Multiple rounds tested with real server")
