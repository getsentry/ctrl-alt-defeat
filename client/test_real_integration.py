#!/usr/bin/env python3
"""
Test the actual client-server integration
"""
import requests
import json

BASE_URL = "http://localhost:8000"

print("=== Testing Real Client-Server Integration ===\n")

# 1. Start session (like BattleServerAPI.start_session does)
print("1. Starting session...")
response = requests.post(f"{BASE_URL}/session/start", json={"player_name": "Player"})
if response.status_code != 200:
    print(f"❌ Failed to start session: {response.status_code}")
    exit(1)

data = response.json()
player_id = data["player_id"]
session = data.get("session", {})
print(f"✅ Session started: {player_id[:8]}...")
print(f"   Gold: {session.get('gold')}")
print(f"   Round: {session.get('round')}")
print(f"   Shop items: {len(session.get('current_shop', []))}")

# Get first item from shop
shop = session.get("current_shop", [])
first_item = None
for item in shop:
    if item:
        first_item = item
        break

if not first_item:
    print("❌ No items in shop")
    exit(1)

# 2. Purchase item (like BattleServerAPI.purchase_item does)
print(f"\n2. Purchasing {first_item['name']} for {first_item['cost']}g...")
response = requests.post(f"{BASE_URL}/purchase/item", json={
    "player_id": player_id,
    "item_id": first_item["id"],
    "placement": [2, 3]  # Place on first container
})

if response.status_code != 200:
    print(f"❌ Purchase failed: {response.status_code}")
    print(f"   Error: {response.text}")
    exit(1)

result = response.json()
print(f"✅ Purchase successful!")
print(f"   Remaining gold: {result.get('gold')}")

# 3. Simulate battle (like BattleServerAPI.submit_battle does)
print(f"\n3. Simulating battle...")
response = requests.post(f"{BASE_URL}/battle/simulate", json={
    "player_id": player_id,
    "round_number": 1
})

if response.status_code != 200:
    print(f"❌ Battle failed: {response.status_code}")
    print(f"   Error: {response.text}")
    exit(1)

result = response.json()
battle_result = result.get("battle_result", {})
winner = "Player" if battle_result.get("winner") == 1 else "AI"
print(f"✅ Battle complete! Winner: {winner}")

session_update = result.get("session_update", {})
print(f"   New round: {session_update.get('round')}")
print(f"   Gold earned: {session_update.get('gold_earned')}")

# 4. Refresh shop (like BattleServerAPI.refresh_shop does)
print(f"\n4. Refreshing shop...")
response = requests.post(f"{BASE_URL}/shop/refresh", json={
    "player_id": player_id,
    "round": 2
})

if response.status_code != 200:
    print(f"❌ Shop refresh failed: {response.status_code}")
    print(f"   Error: {response.text}")
    exit(1)

data = response.json()
new_shop = data.get("shop", [])
print(f"✅ Shop refreshed!")
print(f"   New shop has {len([i for i in new_shop if i])} items")
print(f"   Current gold: {data.get('gold')}")

print("\n✅ All integration tests passed!")
