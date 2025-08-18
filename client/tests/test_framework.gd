extends Node
class_name TestFramework

# Simple test framework similar to pytest
# Automatically discovers and runs all test_*.gd files

var tests_run := 0
var tests_passed := 0
var tests_failed := 0
var current_test_file := ""

func run_all_tests() -> bool:
	print("\n" + "="*60)
	print("GODOT TEST RUNNER")
	print("="*60)

	# Find all test files
	var test_files = _find_test_files("res://tests/")
	print("Found %d test files" % test_files.size())
	print("")

	# Run each test file
	for test_file in test_files:
		if test_file.ends_with("test_framework.gd") or test_file.ends_with("run_tests.gd"):
			continue  # Skip framework files
		_run_test_file(test_file)

	# Print summary
	print("\n" + "="*60)
	if tests_failed == 0:
		print("✅ %d/%d tests passed" % [tests_passed, tests_run])
	else:
		print("❌ %d/%d tests passed, %d failed" % [tests_passed, tests_run, tests_failed])
	print("="*60)

	return tests_failed == 0

func _find_test_files(path: String) -> Array:
	var files = []
	var dir = DirAccess.open(path)
	if dir:
		dir.list_dir_begin()
		var file_name = dir.get_next()
		while file_name != "":
			var full_path = path + "/" + file_name
			if file_name.begins_with("test_") and file_name.ends_with(".gd"):
				files.append(full_path)
			file_name = dir.get_next()
	return files

func _run_test_file(file_path: String):
	current_test_file = file_path.get_file()
	print("\nRunning %s..." % current_test_file)
	print("-" * 40)

	# Load and instantiate the test script
	var script = load(file_path)
	if not script:
		print("  ❌ Failed to load test file")
		tests_failed += 1
		return

	var test_instance = script.new()
	if not test_instance:
		print("  ❌ Failed to instantiate test")
		tests_failed += 1
		return

	# Find and run all test methods (methods starting with test_)
	var methods = []
	for method in test_instance.get_method_list():
		if method.name.begins_with("test_"):
			methods.append(method.name)

	if methods.is_empty():
		print("  ⚠ No test methods found")
		return

	# Run each test method
	for method_name in methods:
		_run_test_method(test_instance, method_name)

	# Clean up
	if test_instance.has_method("_cleanup"):
		test_instance._cleanup()

func _run_test_method(test_instance, method_name: String):
	tests_run += 1

	# Setup before test if available
	if test_instance.has_method("_setup"):
		test_instance._setup()

	# Run the test
	var success = true
	var error_msg = ""

	# Capture test result
	if test_instance.has_method(method_name):
		try:
			var result = test_instance.call(method_name)
			# If test returns false, it failed
			if result is bool and not result:
				success = false
				error_msg = "Test returned false"
		except:
			success = false
			error_msg = "Test threw exception"
	else:
		success = false
		error_msg = "Method not found"

	# Print result
	if success:
		tests_passed += 1
		print("  ✓ %s" % method_name)
	else:
		tests_failed += 1
		print("  ✗ %s - %s" % [method_name, error_msg])

	# Teardown after test if available
	if test_instance.has_method("_teardown"):
		test_instance._teardown()

# Helper assertion functions for tests
static func assert_equal(actual, expected, message: String = "") -> bool:
	if actual != expected:
		print("    Assertion failed: %s" % message)
		print("    Expected: %s" % str(expected))
		print("    Got: %s" % str(actual))
		return false
	return true

static func assert_true(condition: bool, message: String = "") -> bool:
	if not condition:
		print("    Assertion failed: %s" % message)
		return false
	return true

static func assert_false(condition: bool, message: String = "") -> bool:
	if condition:
		print("    Assertion failed: %s" % message)
		return false
	return true

static func assert_not_null(value, message: String = "") -> bool:
	if value == null:
		print("    Assertion failed (null): %s" % message)
		return false
	return true

# Exception helper for Godot 4
static func try(callable: Callable):
	return callable.call()

static func except():
	pass
