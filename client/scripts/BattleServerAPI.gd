extends Node
# Server API - connects to real Python backend

signal session_started(data: Dictionary)
signal battle_completed(result: Dictionary)
signal shop_refreshed(items: Array)
signal purchase_completed(success: bool, data: Dictionary)
signal sell_completed(success: bool, data: Dictionary)
signal error_occurred(message: String)

const BASE_URL = "http://localhost:8000"

var http_request: HTTPRequest
var player_id: String = ""
var session_data: Dictionary = {}
var last_response_code: int = 0
var last_response_body: PackedByteArray

# Testing support
var use_mock_mode: bool = false
var mock_session_data: Dictionary = {}
var mock_battle_result: Dictionary = {}

# Action codes from server (matching Python ACTION_CODES)
const ACTION_CODES = {
	"START": "s",
	"ACTIVATE": "a",
	"DAMAGE": "d",
	"MISS": "m",
	"CRIT": "c",
	"HEAL": "h",
	"BLOCK": "b",
	"CPU_FAIL": "cf",
	"BUFF": "bf",
	"DEBUFF": "df",
	"DOT": "dt",
	"REFLECT": "r",
	"DEATH": "x"
}

func _ready():
	http_request = HTTPRequest.new()
	add_child(http_request)

func start_session(game_seed: int = -1) -> Dictionary:
	# Check if we're in mock mode for testing
	if use_mock_mode:
		await get_tree().create_timer(0.1).timeout  # Simulate network delay
		session_data = mock_session_data
		player_id = mock_session_data.get("player_id", "test-player")
		session_started.emit(session_data)
		return session_data

	# Start a new game session with the real server
	var url = BASE_URL + "/session/start"
	var headers = ["Content-Type: application/json"]

	var body_dict = {
		"player_name": "Player"
	}

	# Use seed if provided (for testing)
	if game_seed >= 0:
		body_dict["seed"] = game_seed

	var body = JSON.stringify(body_dict)

	# Make request and wait for response
	http_request.request(url, headers, HTTPClient.METHOD_POST, body)
	var result = await http_request.request_completed

	# Parse the actual server response
	last_response_code = result[1]
	last_response_body = result[3]

	if last_response_code == 200:
		var json = JSON.new()
		var parse_result = json.parse(last_response_body.get_string_from_utf8())
		if parse_result == OK:
			var data = json.data
			player_id = data.get("player_id", "")

			# Get the session data from server
			var session = data.get("session", {})

			# Format response to match what game expects
			var response = {
				"player_id": player_id,
				"round": session.get("round", 1),
				"gold": session.get("gold", 12),
				"current_shop": session.get("current_shop", []),
				"starting_containers": [
					{"type": "standard_vm", "position": {"x": 2, "y": 3}},
					{"type": "standard_vm", "position": {"x": 4, "y": 3}},
					{"type": "standard_vm", "position": {"x": 6, "y": 3}}
				],
				"item_catalog": {}  # Item catalog comes from server
			}

			session_data = response
			session_started.emit(response)
			return response

	# Server connection failed
	push_error("Failed to connect to server at " + BASE_URL)
	return {}

func submit_battle(inventory_state: Dictionary) -> Dictionary:
	# Check if we're in mock mode for testing
	if use_mock_mode:
		await get_tree().create_timer(0.1).timeout  # Simulate network delay
		if mock_battle_result.is_empty():
			# Provide default mock result
			mock_battle_result = {
				"battle_result": {
					"winner": 1,
					"duration": 10.0,
					"player1_quota": 100,
					"player2_quota": 0,
					"actions": []
				},
				"session_update": {
					"round": 2,
					"gold": 15,
					"lives": 5
				}
			}
		battle_completed.emit(mock_battle_result)
		return mock_battle_result

	# Submit battle to real server
	print("Submitting battle to server")

	if player_id == "":
		push_error("Cannot submit battle - no player ID")
		return {}

	var url = BASE_URL + "/battle/simulate"
	var headers = ["Content-Type: application/json"]

	var body_dict = {
		"player_id": player_id,
		"round_number": session_data.get("round", 1)
	}

	var body = JSON.stringify(body_dict)

	http_request.request(url, headers, HTTPClient.METHOD_POST, body)
	var result = await http_request.request_completed

	last_response_code = result[1]
	last_response_body = result[3]

	if last_response_code == 200:
		var json = JSON.new()
		var parse_result = json.parse(last_response_body.get_string_from_utf8())
		if parse_result == OK:
			var data = json.data

			# Update session data
			if data.has("session_update"):
				var update = data["session_update"]
				session_data["round"] = update.get("round", session_data.get("round", 1))
				session_data["gold"] = update.get("gold", session_data.get("gold", 0))

			battle_completed.emit(data)
			return data

	push_error("Battle request failed with code: " + str(last_response_code))
	return {}

func refresh_shop(round: int) -> Array:
	# Refresh shop from real server
	if player_id == "":
		push_error("Cannot refresh shop - no player ID")
		return []

	var url = BASE_URL + "/shop/refresh"
	var headers = ["Content-Type: application/json"]
	var body = JSON.stringify({
		"player_id": player_id,
		"round": round
	})

	http_request.request(url, headers, HTTPClient.METHOD_POST, body)
	var result = await http_request.request_completed

	last_response_code = result[1]
	last_response_body = result[3]

	if last_response_code == 200:
		var json = JSON.new()
		var parse_result = json.parse(last_response_body.get_string_from_utf8())
		if parse_result == OK:
			var data = json.data
			var new_shop = data.get("shop", [])
			session_data["current_shop"] = new_shop
			session_data["gold"] = data.get("gold", session_data.get("gold", 0))
			shop_refreshed.emit(new_shop)
			return new_shop

	push_error("Shop refresh failed with code: " + str(last_response_code))
	return []

func purchase_item(item_id: String, placement):
	# Purchase item on real server
	if player_id == "":
		push_error("Cannot purchase item - no player ID")
		return

	var url = BASE_URL + "/purchase/item"
	var headers = ["Content-Type: application/json"]

	var body_dict = {
		"player_id": player_id,
		"item_id": item_id,
		"placement": placement  # Can be [x,y] or "storage"
	}

	var body = JSON.stringify(body_dict)
	http_request.request(url, headers, HTTPClient.METHOD_POST, body)
	var result = await http_request.request_completed

	last_response_code = result[1]
	last_response_body = result[3]

	if last_response_code == 200:
		var json = JSON.new()
		var parse_result = json.parse(last_response_body.get_string_from_utf8())
		if parse_result == OK:
			var data = json.data
			purchase_completed.emit(true, data)
			return data

	var error_msg = "Purchase failed with code: " + str(last_response_code)
	purchase_completed.emit(false, {"error": error_msg})
	error_occurred.emit(error_msg)
	return {}

func sell_item(item_id: String, from_storage: bool = false):
	# Sell item on real server
	if player_id == "":
		push_error("Cannot sell item - no player ID")
		return

	var url = BASE_URL + "/sell/item"
	var headers = ["Content-Type: application/json"]

	var body_dict = {
		"player_id": player_id,
		"item_id": item_id,
		"from_storage": from_storage
	}

	var body = JSON.stringify(body_dict)
	http_request.request(url, headers, HTTPClient.METHOD_POST, body)
	var result = await http_request.request_completed

	last_response_code = result[1]
	last_response_body = result[3]

	if last_response_code == 200:
		var json = JSON.new()
		var parse_result = json.parse(last_response_body.get_string_from_utf8())
		if parse_result == OK:
			var data = json.data
			sell_completed.emit(true, data)
			return data

	var error_msg = "Sell failed with code: " + str(last_response_code)
	sell_completed.emit(false, {"error": error_msg})
	error_occurred.emit(error_msg)
	return {}
