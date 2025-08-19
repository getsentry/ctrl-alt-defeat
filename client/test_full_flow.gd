extends SceneTree

func _init():
	print("=== Full Flow Integration Test ===")

	# Test sequence:
	# 1. Start from MainMenu
	# 2. Click Start Game → goes to UnifiedGridUI
	# 3. UnifiedGridUI connects to real server
	# 4. Purchase item
	# 5. Start battle

	print("\n1. Loading MainMenu scene...")
	var main_menu = load("res://scenes/MainMenu.tscn").instantiate()
	root.add_child(main_menu)

	# Wait for scene to load
	await create_timer(0.5).timeout

	print("2. Simulating Start Game button click...")
	main_menu._on_start_game()

	# Wait for scene transition
	await create_timer(1.0).timeout

	# Check if UnifiedGridUI loaded
	var unified_grid = root.get_node_or_null("UnifiedGridUI")
	if unified_grid:
		print("✅ UnifiedGridUI loaded successfully")

		# Check if connected to server
		if unified_grid.player_id != "":
			print("✅ Connected to server with player_id: ", unified_grid.player_id)
			print("   Gold: ", unified_grid.current_gold)
			print("   Round: ", unified_grid.current_round)
			print("   Shop items: ", unified_grid.shop_items.size())
		else:
			print("❌ Failed to connect to server")
	else:
		print("❌ UnifiedGridUI not found after scene transition")

	await create_timer(1.0).timeout
	print("\n=== Test Complete ===")
	quit()
