extends RefCounted
# Test session manager for transaction-based test isolation
# This is 10x faster than resetting the database between tests

static var test_session_id: String = ""
static var session_active: bool = false

static func start_test_session() -> bool:
	"""Start a new test session with transaction isolation"""
	if session_active:
		push_warning("Test session already active")
		return true

	var http = HTTPRequest.new()
	var tree = Engine.get_main_loop() as SceneTree
	if not tree:
		push_error("Cannot get scene tree for test session")
		return false

	tree.root.add_child(http)

	# Get server URL from environment or use default
	var base_url = OS.get_environment("BATTLE_SERVER_URL")
	if base_url == "":
		base_url = "http://localhost:8081"

	var url = base_url + "/test/start-session"
	var headers = ["Content-Type: application/json"]

	# Start test session
	http.request(url, headers, HTTPClient.METHOD_POST, "{}")

	# Wait for response
	var result = await http.request_completed

	if result[1] == 200:
		var json = JSON.new()
		var parse_result = json.parse(result[3].get_string_from_utf8())
		if parse_result == OK:
			var data = json.data
			test_session_id = data.get("session_id", "")
			if test_session_id != "":
				session_active = true
				print("Test session started: %s (transaction-based)" % test_session_id)
				http.queue_free()
				return true

	# Transaction endpoints should always be available now
	var error_msg = "Failed to start test session (code: %d)" % result[1]
	if result[1] == 404:
		error_msg += " - Transaction endpoint not found. Is server running in TEST_MODE?"
	elif result[1] == 403:
		error_msg += " - Server not in TEST_MODE"

	# Parse error response for details
	if result[3].size() > 0:
		var error_json = JSON.new()
		var error_parse = error_json.parse(result[3].get_string_from_utf8())
		if error_parse == OK and error_json.data.has("detail"):
			error_msg += " - " + str(error_json.data["detail"])

	push_error(error_msg)
	http.queue_free()
	return false

static func end_test_session() -> bool:
	"""End the test session and rollback all changes"""
	if not session_active or test_session_id == "":
		push_warning("No active test session to end")
		return false

	# Skip if we never got a real session ID (server issues)
	if test_session_id == "error":
		return false

	var http = HTTPRequest.new()
	var tree = Engine.get_main_loop() as SceneTree
	if not tree:
		push_error("Cannot get scene tree to end test session")
		return false

	tree.root.add_child(http)

	var base_url = OS.get_environment("BATTLE_SERVER_URL")
	if base_url == "":
		base_url = "http://localhost:8081"

	var url = base_url + "/test/end-session/" + test_session_id
	var headers = ["Content-Type: application/json"]

	# End test session
	http.request(url, headers, HTTPClient.METHOD_POST, "{}")

	# Wait for response
	var result = await http.request_completed

	if result[1] == 200:
		print("Test session ended: %s (all changes rolled back)" % test_session_id)
		test_session_id = ""
		session_active = false
		http.queue_free()
		return true

	push_error("Failed to end test session")
	http.queue_free()
	return false

static func ensure_test_mode() -> bool:
	"""Check if server is running in test mode"""
	var http = HTTPRequest.new()
	var tree = Engine.get_main_loop() as SceneTree
	if not tree:
		return false

	tree.root.add_child(http)

	var base_url = OS.get_environment("BATTLE_SERVER_URL")
	if base_url == "":
		base_url = "http://localhost:8081"

	var url = base_url + "/test/status"

	http.request(url, [], HTTPClient.METHOD_GET)

	# Wait for response
	var result = await http.request_completed
	http.queue_free()

	if result[1] == 200:
		var json = JSON.new()
		var parse_result = json.parse(result[3].get_string_from_utf8())
		if parse_result == OK:
			var data = json.data
			if data.get("test_mode", false):
				var db_name = data.get("db_name", "unknown")
				var db_status = "connected" if not data.get("database_fallback", false) else "using fallback"
				print("Server is running in TEST_MODE")
				print("  Database: %s (%s)" % [db_name, db_status])
				print("  Transaction endpoints available: YES")
				return true
			else:
				push_error("Server is not running in TEST_MODE - set TEST_MODE=true when starting server")
				return false
	else:
		push_warning("Could not verify test mode - endpoint may not exist")
		return false

	return false
