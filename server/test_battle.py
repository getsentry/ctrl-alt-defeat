import requests
import json

# Start a session
response = requests.post("http://localhost:8000/session/start")
data = response.json()
player_id = data["player_id"]

print(f"Started session with player_id: {player_id}")
print(f"Initial gold: {data['session']['gold']}")
print(f"Shop has {len(data['session']['current_shop'])} items")

# Simulate a battle with some items
inventory = {
    "items": [
        {"id": "1", "item_type": "null_pointer", "position": [0, 0], "tier": 1},
        {"id": "2", "item_type": "error_monitoring", "position": [1, 0], "tier": 1},
        {"id": "3", "item_type": "redis_cache", "position": [0, 1], "tier": 1}
    ],
    "grid_size": 6
}

battle_request = {
    "player_id": player_id,
    "inventory": inventory,
    "opponent_id": None  # Fight AI
}

print("\nSimulating battle...")
response = requests.post("http://localhost:8000/battle/simulate", json=battle_request)
result = response.json()

print(f"Battle Result: {result['battle_result']['winner']}")
print(f"Duration: {result['battle_result']['duration']:.1f}s")
print(f"Player health remaining: {result['battle_result']['player1_health_remaining']}")
print(f"Enemy health remaining: {result['battle_result']['player2_health_remaining']}")
print(f"New round: {result['session_update']['round']}")
print(f"New gold: {result['session_update']['gold']}")
print(f"Events recorded: {len(result['battle_result']['events'])}")

# Print first few events
print("\nFirst 5 battle events:")
for event in result['battle_result']['events'][:5]:
    print(f"  {event['timestamp']:.1f}s: {event['description']}")
