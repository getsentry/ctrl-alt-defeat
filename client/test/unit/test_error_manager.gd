extends GutTest
# Tests for ErrorManager, the toast that tells the player something went wrong.
#
# It is the only feedback a player gets when the server is unreachable, so the
# message has to be understandable and the toast has to clear itself.

const ErrorManagerScript = preload("res://scripts/ErrorManager.gd")
const Presentation = preload("res://scripts/Presentation.gd")

var manager
var host_scene


func before_each():
	# _display_error_ui() draws into get_tree().current_scene, so there has to
	# be one.
	host_scene = Control.new()
	host_scene.name = "ErrorHostScene"
	get_tree().root.add_child(host_scene)
	get_tree().current_scene = host_scene

	manager = ErrorManagerScript.new()
	add_child(manager)
	Presentation.clear_requests()
	await get_tree().process_frame


func after_each():
	if is_instance_valid(manager):
		manager.clear_all_errors()
		remove_child(manager)
		manager.queue_free()
	manager = null

	if is_instance_valid(host_scene):
		get_tree().current_scene = null
		get_tree().root.remove_child(host_scene)
		host_scene.queue_free()
	host_scene = null
	await get_tree().process_frame


func _toast() -> Node:
	return host_scene.find_child("ErrorPanel", true, false)


# ============ Showing ============

func test_shows_the_message():
	manager.show_error("Something broke")

	var toast = _toast()
	assert_not_null(toast, "An error should put a toast on screen")
	var label = toast.find_child("*", true, false)
	assert_eq(label.text, "Something broke", "The toast should carry the message")


func test_emits_error_displayed():
	watch_signals(manager)
	manager.show_error("Something broke")
	assert_signal_emitted(manager, "error_displayed", "Should announce the error")


func test_asks_to_animate_the_toast_in():
	# Headless plays no fade, so check that it still asked.
	manager.show_error("Something broke")
	assert_eq(Presentation.request_count("error_toast_in"), 1,
		"Showing an error should ask to fade the toast in")


func test_a_second_error_waits_its_turn():
	manager.show_error("First")
	manager.show_error("Second")

	assert_eq(manager.error_queue.size(), 1, "The second error should queue")
	var label = _toast().find_child("*", true, false)
	assert_eq(label.text, "First", "The first error should be the one on screen")


# ============ Clearing ============

func test_clear_all_errors_takes_the_toast_down():
	manager.show_error("Something broke")
	assert_not_null(_toast(), "Setup: the toast should be showing")

	manager.clear_all_errors()
	await get_tree().process_frame

	assert_null(manager.current_error_ui, "Clearing should drop the toast")


func test_clear_all_errors_empties_the_queue():
	manager.show_error("First")
	manager.show_error("Second")
	manager.show_error("Third")

	manager.clear_all_errors()

	assert_eq(manager.error_queue.size(), 0, "Clearing should empty the queue")


func test_clear_all_errors_emits_error_cleared():
	manager.show_error("Something broke")
	watch_signals(manager)

	manager.clear_all_errors()

	assert_signal_emitted(manager, "error_cleared", "Should announce that the error is gone")


func test_clear_all_errors_is_safe_when_nothing_is_showing():
	manager.clear_all_errors()
	assert_null(manager.current_error_ui, "Clearing nothing should do nothing")


# ============ Network errors get a readable message ============

func test_404_is_explained():
	manager._on_network_error("Request failed with 404")
	var label = _toast().find_child("*", true, false)
	assert_eq(label.text, "Server not found. Is the server running?",
		"A 404 should be explained in plain words")


func test_timeout_is_explained():
	manager._on_network_error("Connection Timeout after 30s")
	var label = _toast().find_child("*", true, false)
	assert_eq(label.text, "Connection timed out. Check your internet connection.",
		"A timeout should be explained in plain words")


func test_500_is_explained():
	manager._on_network_error("Got 500 from server")
	var label = _toast().find_child("*", true, false)
	assert_eq(label.text, "Server error. Please try again later.",
		"A 500 should be explained in plain words")


func test_an_unrecognised_error_is_passed_through():
	manager._on_network_error("Something odd")
	var label = _toast().find_child("*", true, false)
	assert_eq(label.text, "Network error: Something odd",
		"An unknown error should still reach the player")


# ============ Warnings and info ============

func test_warnings_and_info_also_reach_the_player():
	manager.show_warning("Careful")
	assert_not_null(_toast(), "A warning should be shown")

	manager.clear_all_errors()
	await get_tree().process_frame

	manager.show_info("Just so you know")
	assert_not_null(_toast(), "Info should be shown")
