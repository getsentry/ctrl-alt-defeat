extends SceneTree
# Test runner script for all UI tests

func _init():
	print("=== Running Autobattler Client Tests ===")
	print("")

	# Run tests and exit
	await run_tests()
	quit()

func run_tests():
	var gut = preload("res://addons/gut/gut.gd").new()
	root.add_child(gut)

	# Configure GUT
	gut.set_parameter("exit_on_finish", true)
	gut.set_parameter("should_print_to_console", true)
	gut.set_parameter("log_level", 1)  # Show errors and failures
	gut.set_parameter("show_help", false)

	# Add test directories
	gut.add_directory("res://test/unit")

	# Run the tests
	print("Starting test execution...")
	gut.test_scripts()

	await gut.end_run

	# Print summary
	print("\n=== Test Results ===")
	print("Tests Run: ", gut.get_test_count())
	print("Assertions: ", gut.get_assert_count())
	print("Failures: ", gut.get_fail_count())
	print("Errors: ", gut.get_error_count())

	# Return exit code based on results
	if gut.get_fail_count() > 0 or gut.get_error_count() > 0:
		print("\n[FAILED] Some tests failed!")
		OS.set_exit_code(1)
	else:
		print("\n[SUCCESS] All tests passed!")
		OS.set_exit_code(0)
