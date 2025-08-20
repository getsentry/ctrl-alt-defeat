extends RefCounted
# Helper class to reset the test database before API tests

static func reset_database() -> bool:
	"""Reset the test database to a clean state"""
	var http = HTTPRequest.new()
	# Need to add to scene tree temporarily
	var tree = Engine.get_main_loop() as SceneTree
	if not tree:
		push_error("Cannot get scene tree for database reset")
		return false

	tree.root.add_child(http)

	# Get server URL from environment or use default
	var base_url = OS.get_environment("BATTLE_SERVER_URL")
	if base_url == "":
		base_url = "http://localhost:8081"

	var url = base_url + "/test/reset-database"
	var headers = ["Content-Type: application/json"]

	# Make synchronous request to reset database
	http.request(url, headers, HTTPClient.METHOD_POST, "{}")

	# Wait for response with timeout
	var timeout = 5.0
	var time_passed = 0.0
	var start_time = Time.get_ticks_msec() / 1000.0
	while http.get_http_client_status() != HTTPClient.STATUS_DISCONNECTED:
		await tree.process_frame
		time_passed = (Time.get_ticks_msec() / 1000.0) - start_time
		if time_passed > timeout:
			push_error("Database reset timed out")
			http.queue_free()
			return false

	# Clean up
	http.queue_free()

	print("Database reset successfully")
	return true

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
				print("Server is running in TEST_MODE with database: %s" % data.get("db_name", "unknown"))
				return true
			else:
				push_error("Server is not running in TEST_MODE")
				return false
	else:
		push_warning("Could not verify test mode - endpoint may not exist")
		return false

	return false
