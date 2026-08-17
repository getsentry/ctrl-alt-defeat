extends Node
# Server API - connects to real Python backend

const APITypes = preload("res://scripts/api_types.gd")

signal session_started(response: APITypes.SessionStartResponse)
signal battle_completed(result: APITypes.BattleResult)
signal shop_refreshed(response: APITypes.ShopRefreshResponse)
signal purchase_completed(response: APITypes.PurchaseResponse)
signal sell_completed(response: APITypes.SellResponse)
signal error_occurred(message: String)

var BASE_URL = "http://localhost:8000"

var http_request: HTTPRequest
var player_id: String = ""
var last_response_code: int = 0
var last_response_body: PackedByteArray

# Auth state managed internally - not exposed globally
var _auth_token: String = ""
var _user_id: int = 0

# Testing support - using real server for tests

func _ready():
	# Check for environment variable to override server URL (for testing)
	var env_url = OS.get_environment("BATTLE_SERVER_URL")
	if env_url != "":
		BASE_URL = env_url
		print("Using server URL from environment: ", BASE_URL)
	else:
		print("Using default server URL: ", BASE_URL)

	http_request = HTTPRequest.new()
	add_child(http_request)

func reset_for_test():
	# Reset everything to force a completely new session
	player_id = ""
	_auth_token = ""  # Force re-authentication
	_user_id = 0

func start_session(player_name: String = "", game_seed: int = -1) -> APITypes.SessionStartResponse:
	# BATTLE_TEST_SEED fixes the game seed, which makes the shop deterministic.
	# The server only accepts a seed in TEST_MODE.
	if game_seed < 0:
		var seed_override := OS.get_environment("BATTLE_TEST_SEED")
		if seed_override != "" and seed_override.is_valid_int():
			game_seed = int(seed_override)

	# First authenticate as guest if we don't have a token
	if _auth_token == "":
		var auth_success = await _authenticate_guest()
		if not auth_success:
			push_error("Failed to authenticate with server")
			return null

	# Use provided name or get from GameStateManager or default
	if player_name == "":
		player_name = GameStateManager.player_name if GameStateManager.player_name != "" else "Player"

	# Start a new game session
	var url = BASE_URL + "/session/start"
	var headers = [
		"Content-Type: application/json",
		"Authorization: Bearer " + _auth_token
	]

	var body_dict = {
		"player_name": player_name
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
	print("response code", last_response_code)

	if last_response_code == 200:
		var json = JSON.new()
		var parse_result = json.parse(last_response_body.get_string_from_utf8())
		if parse_result == OK:
			var data = json.data
			print("data", data)

			# Create typed response - let it fail if fields are missing
			var response = APITypes.SessionStartResponse.new(data)

			# Store player_id
			player_id = response.player_id

			session_started.emit(response)
			return response

	# Server connection failed
	var error_msg = "Failed to start session - code: " + str(last_response_code)
	push_error(error_msg)
	error_occurred.emit(error_msg)
	# For debug builds, assert to make the failure obvious
	assert(false, "Server connection failed: " + error_msg)
	return null

func _authenticate_guest() -> bool:
	# Authenticate as guest to get a token
	var url = BASE_URL + "/auth/guest"
	var headers = ["Content-Type: application/json"]

	http_request.request(url, headers, HTTPClient.METHOD_POST, "")
	var result = await http_request.request_completed

	if result[1] == 200:
		var json = JSON.new()
		var parse_result = json.parse(result[3].get_string_from_utf8())
		if parse_result == OK:
			var data = json.data
			_auth_token = data.get("access_token", "")
			_user_id = data.get("user_id", 0)
			print("Authenticated as guest user: ", data.get("username", ""))
			return true

	push_error("Failed to authenticate as guest")
	return false

func submit_battle(inventory_state: Dictionary) -> APITypes.BattleResponse:
	# Submit battle to real server
	print("Submitting battle to server")

	if player_id == "":
		push_error("Cannot submit battle - no session started")
		return null

	var url = BASE_URL + "/battle/simulate"
	var headers = [
		"Content-Type: application/json",
		"Authorization: Bearer " + _auth_token
	]

	var body_dict = {}

	print("Sending battle request for round %d" % GameStateManager.current_round)

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

			# Create typed BattleResponse per server schema
			var battle_response = APITypes.BattleResponse.new(data)

			# Emit battle_result signal but return full response
			battle_completed.emit(battle_response.battle_result)
			return battle_response

	# Parse error response for better debugging
	var error_msg = "Battle request failed with code: " + str(last_response_code)
	if last_response_body.size() > 0:
		var error_json = JSON.new()
		var error_parse = error_json.parse(last_response_body.get_string_from_utf8())
		if error_parse == OK:
			var error_data = error_json.data
			if error_data.has("detail"):
				error_msg += " - " + str(error_data["detail"])
		else:
			error_msg += " - " + last_response_body.get_string_from_utf8()

	push_error(error_msg)
	error_occurred.emit(error_msg)
	return null

func refresh_shop(round: int) -> APITypes.ShopRefreshResponse:
	# Refresh shop from real server
	if player_id == "":
		push_error("Cannot refresh shop - no session started")
		return null

	var url = BASE_URL + "/shop/refresh"
	var headers = [
		"Content-Type: application/json",
		"Authorization: Bearer " + _auth_token
	]
	var body = JSON.stringify({
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
			var response = APITypes.ShopRefreshResponse.new(data)
			shop_refreshed.emit(response)
			return response

	push_error("Shop refresh failed with code: " + str(last_response_code))
	return null

func purchase_item(item_id: String, placement) -> APITypes.PurchaseResponse:
	# Purchase item on real server
	if player_id == "":
		push_error("Cannot purchase item - no session started")
		return null

	var url = BASE_URL + "/purchase/item"
	var headers = [
		"Content-Type: application/json",
		"Authorization: Bearer " + _auth_token
	]

	var body_dict = {
		"item_id": item_id
	}

	# Server expects target_position field for grid placement
	if placement is Array and placement.size() == 2:
		body_dict["target_position"] = placement

	var body = JSON.stringify(body_dict)
	print("DEBUG: Purchasing item %s at position %s" % [item_id, placement])
	http_request.request(url, headers, HTTPClient.METHOD_POST, body)
	var result = await http_request.request_completed

	last_response_code = result[1]
	last_response_body = result[3]

	var response: APITypes.PurchaseResponse

	if last_response_code == 200:
		var json = JSON.new()
		var parse_result = json.parse(last_response_body.get_string_from_utf8())
		if parse_result == OK:
			var data = json.data
			response = APITypes.PurchaseResponse.new(data)
			# HTTP 200 means success
			print("DEBUG: Purchase successful, gold now: %d" % response.gold)
			purchase_completed.emit(response)
			return response

	var error_msg = "Purchase failed with code: " + str(last_response_code)
	print("DEBUG: " + error_msg)
	error_occurred.emit(error_msg)
	return null

func sell_item(item_id: String) -> APITypes.SellResponse:
	# Sell item on real server
	if player_id == "":
		push_error("Cannot sell item - no session started")
		return null

	var url = BASE_URL + "/sell/item"
	var headers = [
		"Content-Type: application/json",
		"Authorization: Bearer " + _auth_token
	]

	var body_dict = {
		"item_id": item_id
	}

	var body = JSON.stringify(body_dict)
	http_request.request(url, headers, HTTPClient.METHOD_POST, body)
	var result = await http_request.request_completed

	last_response_code = result[1]
	last_response_body = result[3]

	var response: APITypes.SellResponse

	if last_response_code == 200:
		var json = JSON.new()
		var parse_result = json.parse(last_response_body.get_string_from_utf8())
		if parse_result == OK:
			var data = json.data
			response = APITypes.SellResponse.new(data)
			sell_completed.emit(response)
			return response

	var error_msg = "Sell failed with code: " + str(last_response_code)
	error_occurred.emit(error_msg)
	return null

func move_item(item_id: String, to_location) -> APITypes.MoveItemResponse:
	# Move item to new position on real server
	if player_id == "":
		push_error("Cannot move item - no session started")
		return null

	var url = BASE_URL + "/move/item"
	var headers = [
		"Content-Type: application/json",
		"Authorization: Bearer " + _auth_token
	]

	var body_dict = {
		"item_id": item_id,
		"to_location": to_location  # Either "storage" or [x, y]
	}

	var body = JSON.stringify(body_dict)
	print("DEBUG: Moving item %s to position %s" % [item_id, to_location])
	http_request.request(url, headers, HTTPClient.METHOD_POST, body)
	var result = await http_request.request_completed

	last_response_code = result[1]
	last_response_body = result[3]

	if last_response_code == 200:
		var json = JSON.new()
		var parse_result = json.parse(last_response_body.get_string_from_utf8())
		if parse_result == OK:
			var data = json.data
			var response = APITypes.MoveItemResponse.new(data)
			print("DEBUG: Move successful")
			return response

	var error_msg = "Move failed with code: " + str(last_response_code)
	print("DEBUG: " + error_msg)
	error_occurred.emit(error_msg)
	return null
