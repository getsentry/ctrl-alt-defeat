#!/usr/bin/env python3
"""
Test script to verify server-client integration
"""
import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_integration():
    print("Testing server-client integration...")

    # 1. Start a new game
    print("\n1. Starting new game...")
    response = requests.post(f"{BASE_URL}/session/start", json={"player_name": "TestPlayer", "seed": 42})
    if response.status_code != 200:
        print(f"Failed to start game: {response.text}")
        return False

    game_data = response.json()
    player_id = game_data["player_id"]
    print(f"Game started! Player ID: {player_id}")
    print(f"Initial gold: {game_data['session']['gold']}")
    print(f"Shop items: {len(game_data['session']['current_shop'])} slots")

    # 2. Get session info
    print("\n2. Getting session info...")
    response = requests.get(f"{BASE_URL}/session/{player_id}")
    if response.status_code != 200:
        print(f"Failed to get session: {response.text}")
        return False

    session = response.json()
    print(f"Round: {session['round']}, Gold: {session['gold']}, Lives: {session['lives']}")

    # 3. Purchase an item
    print("\n3. Attempting to purchase first shop item...")
    shop = session["current_shop"]
    first_item = None
    for item in shop:
        if item is not None:
            first_item = item
            break

    if first_item:
        print(f"Purchasing {first_item['name']} for {first_item['cost']}g")
        response = requests.post(f"{BASE_URL}/purchase/item", json={
            "player_id": player_id,
            "item_id": first_item["id"],
            "placement": [2, 3]  # Place on first container
        })

        if response.status_code == 200:
            result = response.json()
            print(f"Purchase successful! Remaining gold: {result['gold']}")
        else:
            print(f"Purchase failed: {response.text}")

    # 4. Get updated session
    print("\n4. Getting updated inventory...")
    response = requests.get(f"{BASE_URL}/session/{player_id}")
    session = response.json()
    print(f"Items in grid: {len(session['inventory_grid'])}")
    print(f"Items in storage: {len(session['inventory_storage'])}")

    # 5. Simulate a battle
    print("\n5. Simulating battle...")
    response = requests.post(f"{BASE_URL}/battle/simulate", json={
        "player_id": player_id,
        "round_number": 1
    })

    if response.status_code == 200:
        result = response.json()
        battle_result = result["battle_result"]
        winner = "Player" if battle_result["winner"] == 1 else "AI"
        print(f"Battle complete! Winner: {winner}")
        print(f"New round: {result['session_update']['round']}")
        print(f"Gold earned: {result['session_update'].get('gold_earned', 0)}")
    else:
        print(f"Battle failed: {response.text}")

    print("\n✅ Integration test complete!")
    return True

if __name__ == "__main__":
    try:
        test_integration()
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Make sure it's running on port 8000.")
    except Exception as e:
        print(f"❌ Test failed: {e}")
