extends Node

# Main test runner for all game tests
class_name TestRunner

var test_suites: Array[Dictionary] = []
var current_suite_index: int = 0
var all_passed: bool = true

func _ready():
	print("\n" + "=" * 60)
	print(" SENTRY AUTOBATTLER TEST SUITE")
	print("=" * 60)

	# Register all test suites
	register_test_suites()

	# Run tests
	run_all_test_suites()

func register_test_suites():
	test_suites = [
		{
			"name": "Server API Tests",
			"script": preload("res://tests/test_server_api.gd"),
			"instance": null
		},
		{
			"name": "Inventory System Tests",
			"script": preload("res://tests/test_inventory_system.gd"),
			"instance": null
		},
		{
			"name": "Shop System Tests",
			"script": preload("res://tests/test_shop_system.gd"),
			"instance": null
		},
		{
			"name": "Game Flow Tests",
			"script": preload("res://tests/test_game_flow.gd"),
			"instance": null
		}
	]

func run_all_test_suites():
	if current_suite_index >= test_suites.size():
		print_final_results()
		return

	var suite = test_suites[current_suite_index]
	print("\n" + "=" * 60)
	print(" Running: " + suite["name"])
	print("=" * 60)

	# Create instance of test suite
	suite["instance"] = suite["script"].new()
	add_child(suite["instance"])

	# Run the test suite
	if suite["instance"].has_method("run_all_tests"):
		var result = await suite["instance"].run_all_tests()
		if not result:
			all_passed = false

		# Clean up
		suite["instance"].queue_free()

		# Move to next suite
		current_suite_index += 1

		# Add small delay between suites
		await get_tree().create_timer(0.5).timeout

		# Run next suite
		run_all_test_suites()
	else:
		print("✗ Test suite missing run_all_tests() method")
		all_passed = false
		current_suite_index += 1
		run_all_test_suites()

func print_final_results():
	print("\n" + "=" * 60)
	print(" FINAL TEST RESULTS")
	print("=" * 60)

	if all_passed:
		print("\n✅ ALL TEST SUITES PASSED!")
	else:
		print("\n❌ SOME TEST SUITES FAILED")

	print("\nTest run complete.")

	# Exit with appropriate code
	if OS.has_feature("editor"):
		print("\n(Running in editor - not exiting)")
	else:
		get_tree().quit(0 if all_passed else 1)
