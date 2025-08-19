extends SceneTree

# Script to run integration tests from command line
# Usage: godot --headless --script run_integration_tests.gd

func _init():
	print("\n========================================")
	print("GODOT CLIENT INTEGRATION TESTS")
	print("========================================\n")

	# Create test runner
	var test_runner = preload("res://tests/test_server_integration.gd").new()
	root.add_child(test_runner)

	# Run all tests
	var success = await test_runner.run_all_tests()

	# Exit with appropriate code
	if success:
		print("\n✅ All client tests passed!")
		quit(0)
	else:
		print("\n❌ Some client tests failed")
		quit(1)
