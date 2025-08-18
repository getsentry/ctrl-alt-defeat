extends Node

# Test script for the game flow
class_name GameFlowTest

static func test_api_connection():
	print("Testing API connection...")
	var http = HTTPRequest.new()
	var tree = Engine.get_main_loop()
	tree.root.add_child(http)

	var response = await _make_request(http, "http://localhost:8000/session/start", HTTPClient.METHOD_POST)

	if response.success:
		print("✓ API connection successful")
		print("  Player ID: ", response.data.get("player_id", ""))
		print("  Gold: ", response.data.get("session", {}).get("gold", 0))
		return true
	else:
		print("✗ API connection failed: ", response.error)
		return false

	http.queue_free()

static func _make_request(http: HTTPRequest, url: String, method: int = HTTPClient.METHOD_GET, body: String = "") -> Dictionary:
	var headers = ["Content-Type: application/json"] if body != "" else []

	http.request(url, headers, method, body)
	var result = await http.request_completed

	if result[1] == 200:
		var json = JSON.new()
		var parse_result = json.parse(result[3].get_string_from_utf8())
		if parse_result == OK:
			return {"success": true, "data": json.data}

	return {"success": false, "error": "Response code: " + str(result[1])}

static func test_game_flow():
	print("\n=== GAME FLOW TEST ===")

	# Test 1: Start new game
	print("\n1. Testing new game start...")
	if not await test_api_connection():
		print("FAILED: Could not connect to API")
		return false

	# Test 2: Shop functionality
	print("\n2. Testing shop refresh...")
	var http = HTTPRequest.new()
	var tree = Engine.get_main_loop()
	tree.root.add_child(http)

	# First start a session
	var session_response = await _make_request(http, "http://localhost:8000/session/start", HTTPClient.METHOD_POST)
	if not session_response.success:
		print("FAILED: Could not start session")
		http.queue_free()
		return false

	var player_id = session_response.data.get("player_id", "")

	# Test shop refresh
	var refresh_body = JSON.stringify({
		"player_id": player_id,
		"round": 1
	})
	var shop_response = await _make_request(http, "http://localhost:8000/shop/refresh", HTTPClient.METHOD_POST, refresh_body)

	if shop_response.success:
		print("✓ Shop refresh successful")
		var shop = shop_response.data.get("shop", [])
		print("  Shop has ", shop.size(), " slots")
		var items_count = 0
		for item in shop:
			if item != null:
				items_count += 1
		print("  Found ", items_count, " items in shop")
	else:
		print("✗ Shop refresh failed")

	# Test 3: Battle simulation
	print("\n3. Testing battle simulation...")
	var battle_body = JSON.stringify({
		"player_id": player_id,
		"inventory": {
			"items": [
				{
					"id": "test-item-1",
					"item_type": "null_pointer",
					"position": [0, 0],
					"tier": 1
				}
			],
			"grid_size": 7
		},
		"round_number": 1
	})

	var battle_response = await _make_request(http, "http://localhost:8000/battle/simulate", HTTPClient.METHOD_POST, battle_body)

	if battle_response.success:
		print("✓ Battle simulation successful")
		var result = battle_response.data.get("battle_result", {})
		var winner = result.get("winner", 0)
		print("  Winner: ", "Player" if winner == 1 else "Opponent")
		print("  New round: ", battle_response.data.get("session_update", {}).get("round", 1))
	else:
		print("✗ Battle simulation failed")

	http.queue_free()

	print("\n=== TEST COMPLETE ===")
	return true

static func run_all_tests():
	await test_game_flow()
