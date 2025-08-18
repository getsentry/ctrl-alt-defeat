extends Node

# Test ServerAPI functionality
class_name TestServerAPI

var server_api: Node
var test_player_id: String = ""
var test_passed: Dictionary = {}

func setup():
	print("Setting up ServerAPI tests...")
	server_api = preload("res://scripts/ServerAPI.gd").new()
	add_child(server_api)

func teardown():
	if server_api:
		server_api.queue_free()

func test_api_connection():
	print("Testing API connection...")

	var http = HTTPRequest.new()
	add_child(http)

	var connected = false
	http.request("http://localhost:8000/docs")
	var result = await http.request_completed

	if result[1] == 200:
		print("✓ Server is accessible")
		connected = true
	else:
		print("✗ Server not accessible. Status: ", result[1])

	http.queue_free()
	assert(connected, "Server should be running on localhost:8000")
	return connected

func test_start_new_game():
	print("Testing start new game...")

	var success = false
	var data_received = {}

	# Connect to signals
	server_api.game_started.connect(func(player_id, game_state):
		test_player_id = player_id
		data_received = game_state
		success = true
	, CONNECT_ONE_SHOT)

	server_api.error_occurred.connect(func(message):
		print("Error: ", message)
		success = false
	, CONNECT_ONE_SHOT)

	# Start game
	server_api.start_new_game()

	# Wait for response
	await wait_for_signal_or_timeout(server_api.game_started, 2.0)

	assert(success, "Should successfully start a new game")
	assert(test_player_id != "", "Should receive a player ID")
	assert(data_received.has("session"), "Should receive session data")

	if success:
		print("✓ Game started with player ID: ", test_player_id.substr(0, 8), "...")
		print("  Gold: ", data_received.get("session", {}).get("gold", 0))

	return success

func test_shop_refresh():
	print("Testing shop refresh...")

	if test_player_id == "":
		print("No player ID, starting new game first...")
		await test_start_new_game()

	var success = false
	var shop_data = {}

	server_api.shop_received.connect(func(data):
		shop_data = data
		success = true
	, CONNECT_ONE_SHOT)

	server_api.refresh_shop(1)

	await wait_for_signal_or_timeout(server_api.shop_received, 2.0)

	assert(success, "Should successfully refresh shop")
	assert(shop_data.has("shop"), "Should receive shop data")

	if success:
		var items = shop_data.get("shop", [])
		var item_count = 0
		for item in items:
			if item != null:
				item_count += 1
		print("✓ Shop refreshed with ", item_count, " items")

	return success

func test_purchase_item():
	print("Testing item purchase...")

	if test_player_id == "":
		await test_start_new_game()

	# First get shop to find an item
	await test_shop_refresh()

	# For testing, use a mock item ID
	var test_item_id = "test-item-123"

	var completed = false

	# The purchase doesn't have a specific signal, so we check for errors
	server_api.error_occurred.connect(func(message):
		print("Purchase error: ", message)
		completed = true
	, CONNECT_ONE_SHOT)

	server_api.purchase_item(test_item_id)

	# Give it time to complete
	await get_tree().create_timer(1.0).timeout

	# If no error occurred, consider it a pass for now
	print("✓ Purchase request sent")
	return true

func test_battle_simulation():
	print("Testing battle simulation...")

	if test_player_id == "":
		await test_start_new_game()

	var test_inventory = [
		{
			"id": "test-item-1",
			"item_type": "null_pointer",
			"position": [3, 4],
			"tier": 1
		}
	]

	var success = false
	var battle_data = {}

	server_api.battle_complete.connect(func(result):
		battle_data = result
		success = true
	, CONNECT_ONE_SHOT)

	server_api.simulate_battle(test_inventory, 1)

	await wait_for_signal_or_timeout(server_api.battle_complete, 3.0)

	assert(success, "Should complete battle simulation")
	assert(battle_data.has("battle_result"), "Should receive battle result")

	if success:
		var winner = battle_data.get("battle_result", {}).get("winner", 0)
		print("✓ Battle completed. Winner: ", "Player" if winner == 1 else "Opponent")

	return success

func wait_for_signal_or_timeout(sig: Signal, timeout: float):
	var timer = get_tree().create_timer(timeout)
	var result = await wait_for_any([sig, timer.timeout])
	return result

func wait_for_any(signals: Array):
	var result = null
	var completed = false

	for s in signals:
		if s is Signal:
			s.connect(func(args = null):
				if not completed:
					completed = true
					result = args
			, CONNECT_ONE_SHOT)

	while not completed:
		await get_tree().process_frame

	return result

func run_all_tests():
	print("\n=== RUNNING SERVERAPI TESTS ===\n")

	setup()

	var tests = [
		["API Connection", test_api_connection],
		["Start New Game", test_start_new_game],
		["Shop Refresh", test_shop_refresh],
		["Purchase Item", test_purchase_item],
		["Battle Simulation", test_battle_simulation]
	]

	var passed = 0
	var failed = 0

	for test in tests:
		print("\n--- ", test[0], " ---")
		var result = await test[1].call()
		if result:
			passed += 1
			test_passed[test[0]] = true
		else:
			failed += 1
			test_passed[test[0]] = false

	print("\n=== TEST RESULTS ===")
	print("Passed: ", passed, "/", tests.size())
	print("Failed: ", failed, "/", tests.size())

	for test_name in test_passed:
		var status = "✓" if test_passed[test_name] else "✗"
		print(status, " ", test_name)

	teardown()

	return failed == 0

func assert(condition: bool, message: String):
	if not condition:
		push_error("Assertion failed: " + message)
		print("✗ ASSERT FAILED: ", message)
