#!/usr/bin/env python3
"""
Integration tests for the Sentry Autobattler game.
Tests the complete flow from session start to battle completion.
"""

import requests
import json
import time
from typing import Dict, List, Optional

BASE_URL = "http://localhost:8000"

class GameIntegrationTest:
    def __init__(self):
        self.player_id = None
        self.session = None
        self.shop = []

    def test_server_running(self) -> bool:
        """Test if server is accessible"""
        try:
            response = requests.get(f"{BASE_URL}/docs")
            print("✓ Server is running")
            return response.status_code == 200
        except:
            print("✗ Server is not running. Start with: cd server && python main.py")
            return False

    def test_start_session(self) -> bool:
        """Test starting a new game session"""
        try:
            response = requests.post(f"{BASE_URL}/session/start")
            if response.status_code == 200:
                data = response.json()
                self.player_id = data.get("player_id")
                self.session = data.get("session", {})
                print(f"✓ Session started: Player ID = {self.player_id[:8]}...")
                print(f"  Initial gold: {self.session.get('gold', 0)}")
                print(f"  Shop items: {len(self.session.get('current_shop', []))}")
                return True
            else:
                print(f"✗ Failed to start session: {response.status_code}")
                return False
        except Exception as e:
            print(f"✗ Error starting session: {e}")
            return False

    def test_shop_refresh(self) -> bool:
        """Test refreshing the shop"""
        if not self.player_id:
            print("✗ No player ID - start session first")
            return False

        try:
            payload = {
                "player_id": self.player_id,
                "round": 1
            }
            response = requests.post(f"{BASE_URL}/shop/refresh", json=payload)
            if response.status_code == 200:
                data = response.json()
                self.shop = data.get("shop", [])
                items_count = sum(1 for item in self.shop if item is not None)
                print(f"✓ Shop refreshed: {items_count} items available")

                # Display shop items
                for i, item in enumerate(self.shop):
                    if item:
                        print(f"  Slot {i+1}: {item.get('name')} - {item.get('cost')}g")
                return True
            else:
                print(f"✗ Failed to refresh shop: {response.status_code}")
                return False
        except Exception as e:
            print(f"✗ Error refreshing shop: {e}")
            return False

    def test_purchase_item(self) -> bool:
        """Test purchasing an item from the shop"""
        if not self.player_id:
            print("✗ No player ID - start session first")
            return False

        # Find first available item
        item_to_buy = None
        for item in self.shop:
            if item and item.get("cost", 999) <= self.session.get("gold", 0):
                item_to_buy = item
                break

        if not item_to_buy:
            print("✗ No affordable items in shop")
            return False

        try:
            url = f"{BASE_URL}/purchase/item?player_id={self.player_id}&item_id={item_to_buy['id']}"
            response = requests.post(url)
            if response.status_code == 200:
                data = response.json()
                print(f"✓ Purchased: {item_to_buy.get('name')} for {item_to_buy.get('cost')}g")
                print(f"  Remaining gold: {data.get('gold', 0)}")
                return True
            else:
                print(f"✗ Failed to purchase item: {response.status_code}")
                return False
        except Exception as e:
            print(f"✗ Error purchasing item: {e}")
            return False

    def test_battle_simulation(self) -> bool:
        """Test running a battle simulation"""
        if not self.player_id:
            print("✗ No player ID - start session first")
            return False

        # Create a simple inventory with one item
        inventory = {
            "items": [
                {
                    "id": "test-item-1",
                    "item_type": "null_pointer",
                    "position": [3, 4],
                    "tier": 1
                }
            ],
            "grid_size": 7
        }

        payload = {
            "player_id": self.player_id,
            "inventory": inventory,
            "round_number": 1
        }

        try:
            response = requests.post(f"{BASE_URL}/battle/simulate", json=payload)
            if response.status_code == 200:
                data = response.json()
                result = data.get("battle_result", {})
                winner = result.get("winner", 0)

                print(f"✓ Battle completed:")
                print(f"  Winner: {'Player' if winner == 1 else 'Opponent'}")
                print(f"  New round: {data.get('session_update', {}).get('round', 1)}")
                print(f"  Gold earned: {data.get('session_update', {}).get('gold_earned', 0)}")
                print(f"  Total gold: {data.get('session_update', {}).get('gold', 0)}")
                return True
            else:
                print(f"✗ Failed to simulate battle: {response.status_code}")
                print(f"  Response: {response.text}")
                return False
        except Exception as e:
            print(f"✗ Error simulating battle: {e}")
            return False

    def test_full_game_flow(self) -> bool:
        """Test a complete game flow"""
        print("\n=== FULL GAME FLOW TEST ===")

        tests = [
            ("Server Running", self.test_server_running),
            ("Start Session", self.test_start_session),
            ("Shop Refresh", self.test_shop_refresh),
            ("Purchase Item", self.test_purchase_item),
            ("Battle Simulation", self.test_battle_simulation)
        ]

        passed = 0
        failed = 0

        for name, test_func in tests:
            print(f"\nTesting: {name}")
            if test_func():
                passed += 1
            else:
                failed += 1
                print(f"  Stopping tests due to failure")
                break

        print(f"\n=== TEST RESULTS ===")
        print(f"Passed: {passed}/{len(tests)}")
        print(f"Failed: {failed}/{len(tests)}")

        return failed == 0


def main():
    """Run all integration tests"""
    print("Starting Sentry Autobattler Integration Tests")
    print("=" * 50)

    tester = GameIntegrationTest()

    # Check if server is running first
    if not tester.test_server_running():
        print("\nPlease start the server first:")
        print("  cd server")
        print("  python main.py")
        return 1

    # Run full test suite
    if tester.test_full_game_flow():
        print("\n✅ All tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed")
        return 1


if __name__ == "__main__":
    exit(main())
