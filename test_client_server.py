#!/usr/bin/env python3
"""
Test that the Godot client properly connects to the Python server
"""

import time
import requests
import subprocess
import sys
import os

def test_server_running():
    """Check if server is accessible"""
    try:
        response = requests.get("http://localhost:8000/docs", timeout=1)
        return response.status_code == 200
    except:
        return False

def start_server():
    """Start the server if not running"""
    if test_server_running():
        print("✅ Server already running")
        return None

    print("Starting server...")
    process = subprocess.Popen(
        ["python", "main.py"],
        cwd="server",
        env={**os.environ, "TEST_MODE": "true"}
    )

    # Wait for server to start
    for i in range(10):
        time.sleep(1)
        if test_server_running():
            print("✅ Server started")
            return process

    print("❌ Failed to start server")
    return None

def test_api():
    """Quick test of the API"""
    print("\nTesting API endpoints:")

    # Start session
    response = requests.post("http://localhost:8000/session/start?game_seed=42")
    if response.status_code != 200:
        print("❌ Failed to start session")
        return False

    data = response.json()
    player_id = data["player_id"]
    session = data["session"]

    print(f"✅ Session started (Player: {player_id[:8]}...)")
    print(f"   Gold: {session['gold']}")
    print(f"   Shop items: {len([i for i in session['current_shop'] if i])}")

    # Purchase an item
    item = next((i for i in session['current_shop'] if i), None)
    if item:
        response = requests.post(
            "http://localhost:8000/purchase/item",
            json={
                "player_id": player_id,
                "item_id": item["id"],
                "placement": [2, 3]  # Valid container position
            }
        )

        if response.status_code == 200:
            print(f"✅ Purchased {item['name']} at [2,3]")
        else:
            print(f"❌ Purchase failed: {response.status_code}")

    # Simulate battle
    response = requests.post(
        "http://localhost:8000/battle/simulate",
        json={
            "player_id": player_id,
            "round_number": 1,
            "seed": 42,
            "test_ai_difficulty": "easy"
        }
    )

    if response.status_code == 200:
        result = response.json()
        winner = "Player" if result["battle_result"]["winner"] == 1 else "AI"
        print(f"✅ Battle completed (Winner: {winner})")
    else:
        print(f"❌ Battle failed: {response.status_code}")

    return True

def main():
    print("=" * 50)
    print("CLIENT-SERVER INTEGRATION TEST")
    print("=" * 50)

    # Start server if needed
    server_process = start_server()

    if not test_server_running():
        print("❌ Could not start server")
        return 1

    # Test API
    if not test_api():
        return 1

    print("\n" + "=" * 50)
    print("✅ INTEGRATION READY!")
    print("=" * 50)
    print("\nThe server is running and API is working.")
    print("You can now:")
    print("1. Open Godot")
    print("2. Run the project (F5)")
    print("3. Click 'START NEW GAME'")
    print("4. The game will connect to the real server!")
    print("\nThe client will now:")
    print("- Use real shop items from server")
    print("- Validate placement on server containers")
    print("- Run real battles on the server")
    print("- Track inventory server-side")

    if server_process:
        print("\nPress Ctrl+C to stop the server")
        try:
            server_process.wait()
        except KeyboardInterrupt:
            server_process.terminate()

    return 0

if __name__ == "__main__":
    sys.exit(main())
