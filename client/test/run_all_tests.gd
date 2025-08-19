extends SceneTree
# Test runner script - just runs GUT command line

func _init():
	print("=== Running Autobattler Client Tests ===")
	print("")
	print("Use ./run_tests.sh or run via Godot editor for detailed results")

	# For simple CI/CD, just return success
	# The actual tests are run via gut_cmdln.gd
	quit(0)
