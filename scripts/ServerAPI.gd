extends Node
class_name ServerAPI

const BASE_URL = "http://localhost:8000"

var http_request: HTTPRequest
var player_id: String = ""

signal game_started(player_id: String, game_state: Dictionary)
signal shop_received(shop_data: Dictionary)
signal battle_complete(result: Dictionary)
signal error_occurred(message: String)

func _ready():
	http_request = HTTPRequest.new()
	add_child(http_request)

func start_new_game():
	var url = BASE_URL + "/game/start"
	http_request.request_completed.connect(_on_game_start_complete, CONNECT_ONE_SHOT)
	http_request.request(url, [], HTTPClient.METHOD_POST)

func _on_game_start_complete(result: int, response_code: int, headers: PackedStringArray, body: PackedByteArray):
	if response_code == 200:
		var json = JSON.new()
		var parse_result = json.parse(body.get_string_from_utf8())
		if parse_result == OK:
			var data = json.data
			player_id = data["player_id"]
			game_started.emit(player_id, data["game_state"])
			shop_received.emit(data["shop"])
	else:
		error_occurred.emit("Failed to start game")

func get_game_state():
	if player_id == "":
		error_occurred.emit("No player ID")
		return
	
	var url = BASE_URL + "/game/state/" + player_id
	http_request.request_completed.connect(_on_state_received, CONNECT_ONE_SHOT)
	http_request.request(url)

func _on_state_received(result: int, response_code: int, headers: PackedStringArray, body: PackedByteArray):
	if response_code == 200:
		var json = JSON.new()
		var parse_result = json.parse(body.get_string_from_utf8())
		if parse_result == OK:
			pass
	else:
		error_occurred.emit("Failed to get game state")

func purchase_item(shop_index: int):
	if player_id == "":
		error_occurred.emit("No player ID")
		return
	
	var url = BASE_URL + "/shop/purchase"
	var headers = ["Content-Type: application/json"]
	var body = JSON.stringify({
		"player_id": player_id,
		"shop_index": shop_index
	})
	
	http_request.request_completed.connect(_on_purchase_complete, CONNECT_ONE_SHOT)
	http_request.request(url, headers, HTTPClient.METHOD_POST, body)

func _on_purchase_complete(result: int, response_code: int, headers: PackedStringArray, body: PackedByteArray):
	if response_code == 200:
		var json = JSON.new()
		var parse_result = json.parse(body.get_string_from_utf8())
		if parse_result == OK:
			pass
	else:
		error_occurred.emit("Failed to purchase item")

func place_item(item_id: String, position: Vector2i):
	if player_id == "":
		error_occurred.emit("No player ID")
		return
	
	var url = BASE_URL + "/inventory/place"
	var headers = ["Content-Type: application/json"]
	var body = JSON.stringify({
		"player_id": player_id,
		"item_id": item_id,
		"position": [position.x, position.y]
	})
	
	http_request.request_completed.connect(_on_place_complete, CONNECT_ONE_SHOT)
	http_request.request(url, headers, HTTPClient.METHOD_POST, body)

func _on_place_complete(result: int, response_code: int, headers: PackedStringArray, body: PackedByteArray):
	if response_code == 200:
		var json = JSON.new()
		var parse_result = json.parse(body.get_string_from_utf8())
		if parse_result == OK:
			pass
	else:
		error_occurred.emit("Failed to place item")

func reroll_shop():
	if player_id == "":
		error_occurred.emit("No player ID")
		return
	
	var url = BASE_URL + "/shop/reroll/" + player_id
	http_request.request_completed.connect(_on_reroll_complete, CONNECT_ONE_SHOT)
	http_request.request(url, [], HTTPClient.METHOD_POST)

func _on_reroll_complete(result: int, response_code: int, headers: PackedStringArray, body: PackedByteArray):
	if response_code == 200:
		var json = JSON.new()
		var parse_result = json.parse(body.get_string_from_utf8())
		if parse_result == OK:
			shop_received.emit(json.data["shop"])
	else:
		error_occurred.emit("Failed to reroll shop")

func start_battle(opponent_id: String = ""):
	if player_id == "":
		error_occurred.emit("No player ID")
		return
	
	var url = BASE_URL + "/battle/start"
	var headers = ["Content-Type: application/json"]
	var body_dict = {"player_id": player_id}
	
	if opponent_id != "":
		body_dict["opponent_id"] = opponent_id
	
	var body = JSON.stringify(body_dict)
	
	http_request.request_completed.connect(_on_battle_complete, CONNECT_ONE_SHOT)
	http_request.request(url, headers, HTTPClient.METHOD_POST, body)

func _on_battle_complete(result: int, response_code: int, headers: PackedStringArray, body: PackedByteArray):
	if response_code == 200:
		var json = JSON.new()
		var parse_result = json.parse(body.get_string_from_utf8())
		if parse_result == OK:
			battle_complete.emit(json.data)
	else:
		error_occurred.emit("Failed to start battle")

func get_leaderboard():
	var url = BASE_URL + "/leaderboard"
	http_request.request_completed.connect(_on_leaderboard_received, CONNECT_ONE_SHOT)
	http_request.request(url)

func _on_leaderboard_received(result: int, response_code: int, headers: PackedStringArray, body: PackedByteArray):
	if response_code == 200:
		var json = JSON.new()
		var parse_result = json.parse(body.get_string_from_utf8())
		if parse_result == OK:
			pass
	else:
		error_occurred.emit("Failed to get leaderboard")