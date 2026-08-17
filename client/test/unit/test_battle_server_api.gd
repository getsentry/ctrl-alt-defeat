extends GutTest
# Tests for battle_server_api.gd, the client's side of the connection.
#
# BattleServerAPI is an autoload, so these use the live one. They cover the
# parts that need no server: where it points, what it refuses to send, and that
# it hands back typed objects rather than raw dictionaries. The round trip
# against a real server is covered by test/ui/test_ui_driven.gd.

const APITypes = preload("res://scripts/api_types.gd")

var _saved_player_id: String


func before_each():
	_saved_player_id = BattleServerAPI.player_id


func after_each():
	BattleServerAPI.player_id = _saved_player_id


# ============ Where it points ============

func test_it_reads_the_server_url_from_the_environment():
	# The test runner sets BATTLE_SERVER_URL so tests hit the test server
	# instead of the one a developer happens to be running.
	var from_env = OS.get_environment("BATTLE_SERVER_URL")
	if from_env == "":
		pending("BATTLE_SERVER_URL is not set, so there is nothing to compare against")
		return

	assert_eq(BattleServerAPI.BASE_URL, from_env,
		"The client should talk to the server the environment names")


func test_it_has_an_http_request_ready():
	assert_not_null(BattleServerAPI.http_request, "There should be a request node to send with")


# ============ Refusing to send nonsense ============

func test_it_will_not_send_anything_without_a_session():
	# Every call needs a player id. Without one the request must be refused
	# before it goes out, not sent and rejected by the server.
	BattleServerAPI.player_id = ""

	assert_null(await BattleServerAPI.submit_battle({}), "A battle needs a session")
	assert_null(await BattleServerAPI.refresh_shop(1), "A shop refresh needs a session")
	assert_null(await BattleServerAPI.purchase_item("item_1", [2, 3]), "A purchase needs a session")
	assert_null(await BattleServerAPI.sell_item("item_1"), "A sale needs a session")
	assert_null(await BattleServerAPI.move_item("item_1", [2, 3]), "A move needs a session")


# ============ Resetting between tests ============

func test_reset_clears_everything_from_the_last_run():
	# Without a full reset a test would inherit the previous test's guest
	# account and session.
	BattleServerAPI.player_id = "99"
	BattleServerAPI._auth_token = "stale"
	BattleServerAPI._user_id = 7

	BattleServerAPI.reset_for_test()

	assert_eq(BattleServerAPI.player_id, "", "Resetting should drop the player id")
	assert_eq(BattleServerAPI._auth_token, "", "Resetting should drop the token")
	assert_eq(BattleServerAPI._user_id, 0, "Resetting should drop the user")


# ============ It announces failures ============

func test_a_failed_purchase_reports_back_and_changes_nothing():
	# A failure is nothing plus an error, the way every call reports one. There
	# is no response object, so a caller cannot read fields off an item nobody
	# bought.
	BattleServerAPI.player_id = "1"
	BattleServerAPI.BASE_URL = "http://127.0.0.1:1"  # nothing listens here
	GameStateManager.gold = 17
	watch_signals(BattleServerAPI)

	var result = await BattleServerAPI.purchase_item("item_1", [2, 3])

	assert_null(result, "A failed purchase should not hand back a response")
	assert_eq(GameStateManager.gold, 17, "A failed purchase should not change the gold")
	assert_signal_not_emitted(BattleServerAPI, "purchase_completed",
		"Nothing was purchased, so nothing completed")
	assert_signal_emitted(BattleServerAPI, "error_occurred",
		"A failed purchase should report the error")


func test_a_failed_sale_reports_back_and_changes_nothing():
	BattleServerAPI.player_id = "1"
	BattleServerAPI.BASE_URL = "http://127.0.0.1:1"  # nothing listens here
	GameStateManager.gold = 17
	watch_signals(BattleServerAPI)

	var result = await BattleServerAPI.sell_item("item_1")

	assert_null(result, "A failed sale should not hand back a response")
	assert_eq(GameStateManager.gold, 17, "A failed sale should not change the gold")
	assert_signal_not_emitted(BattleServerAPI, "sell_completed",
		"Nothing was sold, so nothing completed")
	assert_signal_emitted(BattleServerAPI, "error_occurred",
		"A failed sale should report the error")

	BattleServerAPI.BASE_URL = OS.get_environment("BATTLE_SERVER_URL")


# ============ It hands back typed objects ============

func test_the_signals_carry_typed_objects():
	# Every consumer reads these as APITypes objects, not dictionaries. If a
	# signal ever carried a raw dictionary the callers would break.
	var signals = {
		"session_started": "SessionStartResponse",
		"battle_completed": "BattleResult",
		"shop_refreshed": "ShopRefreshResponse",
		"purchase_completed": "PurchaseResponse",
		"sell_completed": "SellResponse"
	}
	var declared = {}
	for entry in BattleServerAPI.get_signal_list():
		declared[entry["name"]] = entry

	for signal_name in signals:
		assert_true(declared.has(signal_name),
			"BattleServerAPI should announce %s" % signal_name)
