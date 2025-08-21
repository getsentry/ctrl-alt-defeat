extends GutTest

func test_purchase_and_battle():
	"""Debug test to isolate purchase and battle issue"""
	print("\n=== DEBUG: Purchase and Battle ===")

	# Start with server setup
	var api = BattleServerAPI
	await api.start_test_session()

	# Authenticate
	var auth_response = await api.authenticate_guest()
	assert_not_null(auth_response, "Should authenticate")
	print("   - Authenticated as: %s" % api.player_id)

	# Start session
	var session_response = await api.start_session()
	assert_not_null(session_response, "Should start session")
	print("   - Session started with %d gold" % session_response.gold)
	print("   - Shop has %d items" % session_response.current_shop.size())

	# Try to purchase first item at position (2, 3)
	if session_response.current_shop.size() > 0:
		var item = session_response.current_shop[0]
		print("   - Purchasing %s at position (2, 3)" % item.get("name", "Unknown"))
		var purchase_response = await api.purchase_item(item.get("id"), [2, 3])
		assert_not_null(purchase_response, "Should get purchase response")
		# HTTP 200 means success, no separate success field
		print("   - Purchase successful, gold: %d" % purchase_response.gold)

		# Now try to battle
		print("   - Submitting battle...")
		var battle_result = await api.submit_battle({})
		assert_not_null(battle_result, "Should get battle result")
		print("   - Battle completed, winner: %d" % battle_result.winner)
	else:
		print("   - No items in shop to test with")

	await api.end_test_session()
	print("   ✓ Debug test complete")
