extends SceneTree
# Quick test runner for shop gold tests

func _init():
	print("Running shop gold tests...")

	# Load the test
	var test_script = load("res://tests/test_shop_gold.gd")
	var test_instance = test_script.new()

	# Run the tests
	test_instance.run_tests()

	# Exit
	quit()
