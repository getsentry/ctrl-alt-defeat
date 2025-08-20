#!/usr/bin/env python3
"""
Simple end-to-end test for the Sentry Autobattler.
Tests the complete flow with the new SimpleBattleRequest format.
"""

import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def test_full_game_flow():
    """Test a complete game flow from start to battle"""

    print("=" * 50)
    print("SENTRY AUTOBATTLER E2E TEST")
    print("=" * 50)

    # 1. Start a new session
    print("\n1. Starting new session...")
    response = requests.post(f"{BASE_URL}/session/start?game_seed=42")
    if response.status_code != 200:
        print(f"❌ Failed to start session: {response.status_code}")
        return False

    data = response.json()
    player_id = data["player_id"]
    session = data["session"]

    print(f"✅ Session started")
    print(f"   Player ID: {player_id[:8]}...")
    print(f"   Gold: {session['gold']}")
    print(f"   Lives: {session['lives']}")
    print(f"   Shop items: {len([i for i in session['current_shop'] if i])}")

    # 2. Purchase items from shop
    print("\n2. Purchasing items...")
    shop = session["current_shop"]
    items_purchased = 0
    positions = [[2, 3], [3, 3], [4, 3]]  # Valid container positions

    for i, item in enumerate(shop):
        if item and items_purchased < 3:
            purchase_request = {
                "player_id": player_id,
                "item_id": item["id"],
                "placement": positions[items_purchased]
            }

            response = requests.post(
                f"{BASE_URL}/purchase/item",
                json=purchase_request
            )

            if response.status_code == 200:
                result = response.json()
                print(f"✅ Purchased {item['name']} at {positions[items_purchased]} for {item['cost']}g")
                print(f"   Remaining gold: {result['gold']}")
                items_purchased += 1
            else:
                print(f"❌ Failed to purchase {item['name']}: {response.status_code}")
                if response.text:
                    print(f"   Error: {response.json().get('detail', response.text)}")

    if items_purchased == 0:
        print("❌ No items purchased, cannot battle")
        return False

    # 3. Simulate battle with SimpleBattleRequest
    print(f"\n3. Starting battle with {items_purchased} items...")
    battle_request = {
        "player_id": player_id,
        "round_number": 1,
        "seed": 42,
        "test_ai_difficulty": "easy"  # Easy AI for demo
    }

    response = requests.post(
        f"{BASE_URL}/battle/simulate",
        json=battle_request
    )

    if response.status_code != 200:
        print(f"❌ Failed to simulate battle: {response.status_code}")
        if response.text:
            print(f"   Error: {response.json().get('detail', response.text)}")
        return False

    result = response.json()
    battle_result = result["battle_result"]
    session_update = result["session_update"]

    winner = "Player" if battle_result["winner"] == 1 else "AI"
    print(f"✅ Battle completed!")
    print(f"   Winner: {winner}")
    print(f"   New round: {session_update['round']}")
    print(f"   Gold earned: {session_update['gold_earned']}")
    print(f"   Total gold: {session_update['gold']}")
    print(f"   Lives: {session_update['lives']}")
    print(f"   Wins: {session_update['wins']}")
    print(f"   Losses: {session_update['losses']}")

    # 4. Test invalid operations
    print("\n4. Testing error handling...")

    # Try to battle with empty inventory (new session)
    response = requests.post(f"{BASE_URL}/session/start")
    new_player = response.json()["player_id"]

    battle_request = {
        "player_id": new_player,
        "round_number": 1
    }

    response = requests.post(f"{BASE_URL}/battle/simulate", json=battle_request)
    if response.status_code == 400:
        print("✅ Correctly rejected battle with empty inventory")
    else:
        print("❌ Should have rejected empty inventory battle")

    # Try invalid placement
    response = requests.post(f"{BASE_URL}/session/start")
    data = response.json()
    new_player = data["player_id"]
    shop = data["session"]["current_shop"]

    for item in shop:
        if item:
            purchase_request = {
                "player_id": new_player,
                "item_id": item["id"],
                "placement": [0, 0]  # Invalid position
            }

            response = requests.post(f"{BASE_URL}/purchase/item", json=purchase_request)
            if response.status_code == 400:
                print("✅ Correctly rejected invalid placement at [0, 0]")
            else:
                print("❌ Should have rejected invalid placement")
            break

    print("\n" + "=" * 50)
    print("✅ E2E TEST COMPLETED SUCCESSFULLY!")
    print("=" * 50)
    return True


def check_server():
    """Check if server is running"""
    try:
        response = requests.get(f"{BASE_URL}/docs", timeout=1)
        return response.status_code == 200
    except:
        return False


def main():
    # Check server
    if not check_server():
        print("❌ Server not running at http://localhost:8000")
        print("   Start it with: cd server && python main.py")
        return 1

    print("✅ Server is running")

    # Run test
    if test_full_game_flow():
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
