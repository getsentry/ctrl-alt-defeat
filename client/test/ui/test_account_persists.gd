extends GutTest
# The account outlives the window being closed.
#
# This needs a real server, because the whole question is whether a token the
# client kept is still worth anything to the one that issued it. Run it through
# run_tests.sh.
#
# What it stands in for: closing the game and opening it again. A launch has no
# token in memory and looks on disk for one, so dropping `_auth_token` while
# leaving `account.cfg` alone is the same starting position.

const APITypes = preload("res://scripts/api_types.gd")


func before_each():
	BattleServerAPI.reset_for_test()


func after_each():
	BattleServerAPI.reset_for_test()


func _relaunch() -> void:
	"""Forget what is in memory, keep what is on disk."""
	BattleServerAPI._auth_token = ""
	BattleServerAPI._user_id = 0
	BattleServerAPI.player_id = ""


func test_the_same_player_comes_back():
	assert_true(await BattleServerAPI._ensure_signed_in(), "A first launch signs in")
	var first = await BattleServerAPI.fetch_account()
	assert_not_null(first, "and has an account")

	_relaunch()
	assert_true(await BattleServerAPI._ensure_signed_in(), "A second launch signs in")
	var second = await BattleServerAPI.fetch_account()

	assert_not_null(second, "and has an account")
	assert_eq(second.user_id, first.user_id, "It should be the same account")
	assert_eq(second.username, first.username, "under the same name")


func test_without_the_file_it_is_somebody_new():
	assert_true(await BattleServerAPI._ensure_signed_in())
	var first = await BattleServerAPI.fetch_account()

	BattleServerAPI.forget_account()
	BattleServerAPI.player_id = ""
	assert_true(await BattleServerAPI._ensure_signed_in())
	var second = await BattleServerAPI.fetch_account()

	assert_ne(second.user_id, first.user_id, "Forgetting should start a new account")


func test_a_token_the_server_refuses_becomes_a_new_guest():
	"""Tokens last 90 days and an account can be removed underneath one.

	A launch that trusted a dead token would fail on its first real call with
	nothing useful to say. It checks first, and starts again if the answer is
	no.
	"""
	BattleServerAPI._save_account("not-a-real-token", 999999)
	_relaunch()

	assert_true(
		await BattleServerAPI._ensure_signed_in(),
		"A refused token should not stop the player playing"
	)

	var account = await BattleServerAPI.fetch_account()
	assert_not_null(account, "It should have signed in as somebody")
	assert_ne(account.user_id, 999999, "and not as whoever the dead token named")


func test_the_account_it_comes_back_as_is_a_guest_with_a_name():
	assert_true(await BattleServerAPI._ensure_signed_in())

	var account = await BattleServerAPI.fetch_account()

	assert_true(account.is_guest(), "A player who never signed up is a guest")
	assert_ne(account.username, "", "The server names the account")
	assert_eq(account.snuba_coin, 0, "A new account has been paid nothing")
	assert_eq(account.total_games, 0, "and has finished no runs")
