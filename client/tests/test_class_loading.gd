extends SceneTree
# Test that all custom classes are properly loaded and available

func _init():
	print("\n=== Testing Class Loading ===")

	var errors_found = false

	# Test 1: Check if BattleEventProcessor class can be loaded
	print("Testing BattleEventProcessor class availability...")
	var processor_script = load("res://scripts/BattleEventProcessor.gd")
	if processor_script == null:
		print("❌ FAIL: Could not load BattleEventProcessor.gd")
		errors_found = true
	else:
		print("✓ BattleEventProcessor script loads")

		# Check if it has class_name defined
		var script_source = processor_script.source_code
		if not script_source.begins_with("class_name BattleEventProcessor"):
			print("❌ FAIL: BattleEventProcessor missing class_name declaration")
			errors_found = true
		else:
			print("✓ BattleEventProcessor has class_name")

	# Test 2: Check if BattleScreen can load (which depends on BattleEventProcessor)
	print("\nTesting BattleScreen with BattleEventProcessor dependency...")
	var battle_screen_script = load("res://scripts/BattleScreen.gd")
	if battle_screen_script == null:
		print("❌ FAIL: Could not load BattleScreen.gd - likely due to missing class dependency")
		errors_found = true
	else:
		print("✓ BattleScreen script loads successfully")

		# Try to instantiate it
		var battle_screen = battle_screen_script.new()
		if battle_screen == null:
			print("❌ FAIL: Could not instantiate BattleScreen")
			errors_found = true
		else:
			print("✓ BattleScreen can be instantiated")
			battle_screen.queue_free()

	# Test 3: Check GameStateManager singleton
	print("\nTesting GameStateManager singleton...")
	if not Engine.has_singleton("GameStateManager"):
		print("❌ FAIL: GameStateManager singleton not registered")
		errors_found = true
	else:
		print("✓ GameStateManager singleton is available")

	# Test 4: Check BattleServerAPI singleton
	print("\nTesting BattleServerAPI singleton...")
	if not Engine.has_singleton("BattleServerAPI"):
		print("❌ FAIL: BattleServerAPI singleton not registered")
		errors_found = true
	else:
		print("✓ BattleServerAPI singleton is available")

	if errors_found:
		print("\n❌ TESTS FAILED - Class loading issues detected!")
		print("To fix: Ensure all custom classes have 'class_name' at the top of the file")
		quit(1)
	else:
		print("\n✅ All class loading tests passed!")
		quit(0)
