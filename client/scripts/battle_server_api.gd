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

## Where the account is kept between launches.
##
## Its own file, not `player_settings.cfg`. A ConfigFile is written whole, so
## anything that saves a setting without loading first would take the token
## with it -- and `main_menu.gd` does exactly that.
##
## Godot maps `user://` to localStorage in a web build, so one path covers both.
const ACCOUNT_PATH := "user://account.cfg"

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
	# The saved account too, or a test would sign back in as whoever the last
	# run left behind.
	forget_account()


## Sign in, reusing the account from last time if there is one.
##
## A launch used to call /auth/guest every time, so every launch was a different
## person and nothing an account holds -- its name, its SnubaCoin, how many runs
## it has finished -- could outlive the window being closed.
##
## The saved token is checked before it is trusted. It can be refused: the
## account may have been deleted, or the token may have expired (they last 90
## days). Either way the answer is a new guest, and the old one is forgotten
## rather than left to fail on the next call.
func _ensure_signed_in() -> bool:
	if _auth_token != "":
		return true

	if _load_account():
		if await fetch_account() != null:
			return true
		print("The saved account was refused. Starting a new one.")
		forget_account()

	return await _authenticate_guest()


## The account behind the current token, or null if there is no usable one.
func fetch_account() -> APITypes.Account:
	if _auth_token == "":
		return null

	http_request.request(
		BASE_URL + "/auth/me",
		["Authorization: Bearer " + _auth_token],
		HTTPClient.METHOD_GET
	)
	var result = await http_request.request_completed

	last_response_code = result[1]
	last_response_body = result[3]
	if last_response_code != 200:
		return null

	var json = JSON.new()
	if json.parse(last_response_body.get_string_from_utf8()) != OK:
		push_error("Could not read the account")
		return null
	return APITypes.Account.new(json.data)


func _load_account() -> bool:
	var config = ConfigFile.new()
	if config.load(ACCOUNT_PATH) != OK:
		return false
	var token = config.get_value("account", "token", "")
	if token == "":
		return false
	_auth_token = token
	_user_id = int(config.get_value("account", "user_id", 0))
	return true


func _save_account(token: String, user_id: int) -> void:
	var config = ConfigFile.new()
	config.set_value("account", "token", token)
	config.set_value("account", "user_id", user_id)
	if config.save(ACCOUNT_PATH) != OK:
		push_error("Could not keep the account. The next launch will start a new one.")


## Drop the saved account. The next sign-in makes a new guest.
func forget_account() -> void:
	_auth_token = ""
	_user_id = 0
	DirAccess.remove_absolute(ProjectSettings.globalize_path(ACCOUNT_PATH))

## Start a run.
##
## The player's name is not sent. It belongs to the account, and the server
## reads it from the token. `StartSessionRequest` forbids extra fields, so a
## name in the body is a 422 rather than a field quietly ignored.
func start_session(game_seed: int = -1) -> APITypes.SessionStartResponse:
	# BATTLE_TEST_SEED fixes the game seed, which makes the shop deterministic.
	# The server only accepts a seed in TEST_MODE.
	if game_seed < 0:
		var seed_override := OS.get_environment("BATTLE_TEST_SEED")
		if seed_override != "" and seed_override.is_valid_int():
			game_seed = int(seed_override)

	if not await _ensure_signed_in():
		push_error("Failed to authenticate with server")
		return null

	# Start a new game session
	var url = BASE_URL + "/session/start"
	var headers = [
		"Content-Type: application/json",
		"Authorization: Bearer " + _auth_token
	]

	var body_dict = {}

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

	# Whether the request went out at all. One HTTPRequest serves the whole
	# API, so a call made while another is still in flight is refused here and
	# never sent -- and the await below would then take the other call's
	# answer for this one's.
	var sent := http_request.request(url, headers, HTTPClient.METHOD_POST, "")
	if sent != OK:
		push_error("Could not ask for a guest account: error %d" % sent)
		return false

	var result = await http_request.request_completed

	if result[1] == 200:
		var json = JSON.new()
		var parse_result = json.parse(result[3].get_string_from_utf8())
		if parse_result == OK:
			var data = json.data
			_auth_token = data["access_token"]
			_user_id = int(data["user_id"])
			_save_account(_auth_token, _user_id)
			print("Authenticated as guest user: ", data["username"])
			return true

	# Saying which code and what came back, because this one is rare and the
	# message it used to carry -- the bare fact of it -- named nothing that
	# would help find it again.
	push_error("Failed to authenticate as guest: code %d, said %s" % [
		result[1], result[3].get_string_from_utf8().substr(0, 200)])
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

func combining_catalogue() -> APITypes.CombiningCatalogue:
	"""Which item types go together in a recipe, and what to call each one.

	Neither a session nor a token: it is the same for every player and it never
	changes, so the client asks once -- before there is a rack to ask about --
	and answers from it after that. A line is wanted on hover and while
	dragging, and a line every frame cannot be a request every frame.
	"""
	# Its own request rather than the shared one. It is asked for as the shop
	# screen opens, which is exactly when the screen is also loading a session,
	# and two requests down one HTTPRequest is one refused request and one
	# await that never returns.
	var asking := HTTPRequest.new()
	add_child(asking)

	var sent := asking.request(BASE_URL + "/catalogue/combining",
		["Content-Type: application/json"])
	if sent != OK:
		# request_completed never fires for a request that never went, so
		# waiting on it would hang here, holding the node for the whole run.
		asking.queue_free()
		push_error("Could not ask for the combining catalogue: error %d" % sent)
		return null

	var result = await asking.request_completed
	asking.queue_free()

	if result[1] == 200:
		var json = JSON.new()
		if json.parse(result[3].get_string_from_utf8()) == OK:
			return APITypes.CombiningCatalogue.new(json.data)

	push_error("Could not fetch the combining catalogue: code %d" % result[1])
	return null


func status_rules() -> APITypes.StatusRules:
	"""What every buff and debuff does, per stack.

	Neither a session nor a token, like the combining catalogue beside it: the
	same for every player, never changes, asked for once.
	"""
	var asking := HTTPRequest.new()
	add_child(asking)

	var sent := asking.request(BASE_URL + "/catalogue/statuses",
		["Content-Type: application/json"])
	if sent != OK:
		asking.queue_free()
		push_error("Could not ask what the statuses do: error %d" % sent)
		return null

	var result = await asking.request_completed
	asking.queue_free()

	if result[1] == 200:
		var json = JSON.new()
		if json.parse(result[3].get_string_from_utf8()) == OK:
			return APITypes.StatusRules.new(json.data)

	push_error("Could not fetch what the statuses do: code %d" % result[1])
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

static func purchase_body(
	item_id: String, placement: Variant, facing: int = 0
) -> Dictionary:
	"""What a purchase asks the server for.

	A square is named as a position and the chest is named as itself, which is
	the same pair of choices a move offers. Its own function so that what is
	asked for can be read without a session to ask it of.
	"""
	var body := {
		"item_id": item_id,
		# An item can be turned while it is carried out of the shop, and the
		# purchase is when that is settled. Sent every time, so what the server
		# stores is what the player saw themselves put down.
		"rotation": facing
	}
	if placement is Array and placement.size() == 2:
		body["target_position"] = placement
	elif placement == "storage":
		body["to_storage"] = true
	return body


func purchase_item(
	item_id: String, placement: Variant, facing: int = 0
) -> APITypes.PurchaseResponse:
	# Purchase item on real server
	if player_id == "":
		push_error("Cannot purchase item - no session started")
		return null

	var url = BASE_URL + "/purchase/item"
	var headers = [
		"Content-Type: application/json",
		"Authorization: Bearer " + _auth_token
	]

	var body = JSON.stringify(purchase_body(item_id, placement, facing))
	print("DEBUG: Purchasing item %s at %s facing %d" % [item_id, placement, facing])
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
			GameStateManager.note_pending(response.pending)
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
			GameStateManager.note_pending(response.pending)
			sell_completed.emit(response)
			return response

	var error_msg = "Sell failed with code: " + str(last_response_code)
	error_occurred.emit(error_msg)
	return null

# to_location is a square as [x, y], or the word "storage". GDScript cannot
# say "one of these two", so it is Variant. Splitting it into two calls would
# type it properly; see docs/BACKLOG.md.
func move_item(
	item_id: String, to_location: Variant, facing: int = 0
) -> APITypes.MoveItemResponse:
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
		"to_location": to_location,  # Either "storage" or [x, y]
		# An item can be turned while it is held, and the move is when that is
		# settled. Sent every time, so a move never straightens an item out.
		"rotation": facing
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
			GameStateManager.note_pending(response.pending)
			print("DEBUG: Move successful")
			return response

	var error_msg = "Move failed with code: " + str(last_response_code)
	print("DEBUG: " + error_msg)
	error_occurred.emit(error_msg)
	return null
