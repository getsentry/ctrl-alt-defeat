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
var session_data: Dictionary = {}
var last_response_code: int = 0
var last_response_body: PackedByteArray

# Auth state managed internally - not exposed globally
var _auth_token: String = ""
var _user_id: int = 0

# Testing support - using real server for tests

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
	session_data = {}
	_auth_token = ""  # Force re-authentication
	_user_id = 0

func start_session(game_seed: int = -1) -> APITypes.SessionStartResponse:
	# First authenticate as guest if we don't have a token
	if _auth_token == "":
		var auth_success = await _authenticate_guest()
		if not auth_success:
			push_error("Failed to authenticate with server")
			return null

	# Start a new game session with the real server
	var url = BASE_URL + "/session/start"
	var headers = [
		"Content-Type: application/json",
		"Authorization: Bearer " + _auth_token
	]

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

			# Get starting containers from session data
			if data.has("session") and data["session"].has("server_containers"):
				data["starting_containers"] = data["session"]["server_containers"]

			# Create typed response
			var response = APITypes.SessionStartResponse.new(data)

			# Store session data for internal use
			session_data = {
				"player_id": response.player_id,
				"round": response.round,
				"gold": response.gold,
				"current_shop": response.current_shop
			}

			session_started.emit(response)
			return response

	# Server connection failed
	push_error("Failed to start session - code: " + str(last_response_code))
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

func submit_battle(inventory_state: Dictionary) -> APITypes.BattleResult:
	# Submit battle to real server
	print("Submitting battle to server")

	if player_id == "":
		push_error("Cannot submit battle - no player ID")
		return null

	var url = BASE_URL + "/battle/simulate"
	var headers = [
		"Content-Type: application/json",
		"Authorization: Bearer " + _auth_token
	]

	var body_dict = {"player_id": player_id}

	print("Sending battle request for round %d" % session_data.get("round", 1))

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

			# Create typed battle result - combine the nested battle_result with other top-level fields
			var battle_data = data.get("battle_result", {})
			# Add session_update from top level
			battle_data["session_update"] = data.get("session_update", {})
			var battle_result = APITypes.BattleResult.new(battle_data)

			# Update session data from top-level session_update
			var session_update = data.get("session_update", {})
			if session_update.size() > 0:
				session_data["round"] = session_update.get("round", session_data.get("round", 1))
				session_data["gold"] = session_update.get("gold", session_data.get("gold", 0))

			battle_completed.emit(battle_result)
			return battle_result

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
		push_error("Cannot refresh shop - no player ID")
		return null

	var url = BASE_URL + "/shop/refresh"
	var headers = [
		"Content-Type: application/json",
		"Authorization: Bearer " + _auth_token
	]
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
			var response = APITypes.ShopRefreshResponse.new(data)
			session_data["current_shop"] = response.shop
			session_data["gold"] = response.gold
			shop_refreshed.emit(response)
			return response

	push_error("Shop refresh failed with code: " + str(last_response_code))
	return null

func purchase_item(item_id: String, placement) -> APITypes.PurchaseResponse:
	# Purchase item on real server
	if player_id == "":
		push_error("Cannot purchase item - no player ID")
		return null

	var url = BASE_URL + "/purchase/item"
	var headers = [
		"Content-Type: application/json",
		"Authorization: Bearer " + _auth_token
	]

	var body_dict = {
		"player_id": player_id,
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
			if response.success:
				session_data["gold"] = response.gold
				print("DEBUG: Purchase successful, gold now: %d" % response.gold)
			purchase_completed.emit(response)
			return response

	var error_msg = "Purchase failed with code: " + str(last_response_code)
	print("DEBUG: " + error_msg)
	response = APITypes.PurchaseResponse.new({"error": error_msg})
	purchase_completed.emit(response)
	error_occurred.emit(error_msg)
	return response

func sell_item(item_id: String, from_storage: bool = false) -> APITypes.SellResponse:
	# Sell item on real server
	if player_id == "":
		push_error("Cannot sell item - no player ID")
		return null

	var url = BASE_URL + "/sell/item"
	var headers = [
		"Content-Type: application/json",
		"Authorization: Bearer " + _auth_token
	]

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

	var response: APITypes.SellResponse

	if last_response_code == 200:
		var json = JSON.new()
		var parse_result = json.parse(last_response_body.get_string_from_utf8())
		if parse_result == OK:
			var data = json.data
			response = APITypes.SellResponse.new(data)
			if response.success:
				session_data["gold"] = response.gold
			sell_completed.emit(response)
			return response

	var error_msg = "Sell failed with code: " + str(last_response_code)
	response = APITypes.SellResponse.new({"error": error_msg})
	sell_completed.emit(response)
	error_occurred.emit(error_msg)
	return response
