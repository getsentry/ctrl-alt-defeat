#!/usr/bin/env python3
"""
Comprehensive integration test that verifies the full game flow
with the new server-authoritative architecture.
"""

import os
import sys
import time
import json
import subprocess
import requests
from typing import Dict, List, Optional
import signal

BASE_URL = "http://localhost:8000"

class FullIntegrationTest:
    """Complete integration test suite"""

    def __init__(self):
        self.server_process = None
        self.results = {"passed": 0, "failed": 0, "skipped": 0}
        os.environ["TEST_MODE"] = "true"

    def start_server(self) -> bool:
        """Start the server if not already running"""
        # Check if server is already running
        try:
            response = requests.get(f"{BASE_URL}/docs", timeout=1)
            if response.status_code == 200:
                print("✓ Using existing server")
                return True
        except:
            pass

        print("Starting server...")
        try:
            self.server_process = subprocess.Popen(
                ["python", "main.py"],
                cwd="server",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, "TEST_MODE": "true"}
            )

            # Wait for server to start
            for i in range(10):
                time.sleep(1)
                try:
                    response = requests.get(f"{BASE_URL}/docs", timeout=1)
                    if response.status_code == 200:
                        print("✓ Server started")
                        return True
                except:
                    continue

            print("✗ Server failed to start")
            return False

        except Exception as e:
            print(f"✗ Error starting server: {e}")
            return False

    def stop_server(self):
        """Stop the server if we started it"""
        if self.server_process:
            print("Stopping server...")
            self.server_process.terminate()
            self.server_process.wait(timeout=5)
            self.server_process = None

    def test_complete_game_flow(self):
        """Test a complete game from start to victory/defeat"""
        print("\n=== COMPLETE GAME FLOW TEST ===\n")

        # 1. Start new game
        print("1. Starting new game session...")
        response = requests.post(f"{BASE_URL}/session/start?game_seed=42")
        assert response.status_code == 200, f"Failed to start session: {response.status_code}"

        data = response.json()
        player_id = data["player_id"]
        session = data["session"]

        print(f"   ✓ Session started (Player: {player_id[:8]}...)")
        print(f"   - Gold: {session['gold']}")
        print(f"   - Lives: {session['lives']}")

        # 2. Test multiple rounds
        for round_num in range(1, 6):
            print(f"\n2.{round_num}. Playing Round {round_num}...")

            # Get current session
            response = requests.get(f"{BASE_URL}/session/{player_id}")
            assert response.status_code == 200
            session = response.json()

            # Purchase items
            shop = session["current_shop"]
            positions = [[2, 3], [3, 3], [4, 3], [5, 3], [2, 4], [3, 4]]
            purchases = 0

            for i, item in enumerate(shop):
                if item and purchases < min(3 + round_num // 2, 6):
                    response = requests.post(
                        f"{BASE_URL}/purchase/item",
                        json={
                            "player_id": player_id,
                            "item_id": item["id"],
                            "placement": positions[purchases]
                        }
                    )
                    if response.status_code == 200:
                        purchases += 1

            print(f"   - Purchased {purchases} items")

            # Battle
            response = requests.post(
                f"{BASE_URL}/battle/simulate",
                json={
                    "player_id": player_id,
                    "round_number": round_num,
                    "seed": 42 + round_num,
                    "test_ai_difficulty": "easy" if round_num <= 3 else None
                }
            )
            assert response.status_code == 200, f"Battle failed: {response.status_code}"

            result = response.json()
            battle = result["battle_result"]
            update = result["session_update"]

            winner = "Player" if battle["winner"] == 1 else "AI"
            print(f"   - Battle: {winner} won")
            print(f"   - Lives: {update['lives']}, Gold: {update['gold']}")

            if update.get("game_over"):
                print(f"\n   ✗ Game Over at round {round_num}")
                break

            if update.get("victory"):
                print(f"\n   ✓ Victory achieved at round {round_num}!")
                break

        self.results["passed"] += 1
        print("\n✓ Complete game flow test passed")

    def test_inventory_management(self):
        """Test all inventory operations"""
        print("\n=== INVENTORY MANAGEMENT TEST ===\n")

        # Start session
        response = requests.post(f"{BASE_URL}/session/start?game_seed=100")
        data = response.json()
        player_id = data["player_id"]
        shop = data["session"]["current_shop"]

        # 1. Test purchase to grid
        print("1. Testing purchase to grid...")
        item = next((i for i in shop if i), None)
        if item:
            response = requests.post(
                f"{BASE_URL}/purchase/item",
                json={
                    "player_id": player_id,
                    "item_id": item["id"],
                    "placement": [2, 3]
                }
            )
            assert response.status_code == 200
            print("   ✓ Item placed on grid")

        # 2. Test purchase to storage
        print("2. Testing purchase to storage...")
        response = requests.get(f"{BASE_URL}/session/{player_id}")
        shop = response.json()["current_shop"]
        item = next((i for i in shop if i), None)
        if item:
            response = requests.post(
                f"{BASE_URL}/purchase/item",
                json={
                    "player_id": player_id,
                    "item_id": item["id"],
                    "placement": "storage"
                }
            )
            assert response.status_code == 200
            print("   ✓ Item placed in storage")

        # 3. Test invalid placement
        print("3. Testing invalid placement rejection...")
        response = requests.get(f"{BASE_URL}/session/{player_id}")
        shop = response.json()["current_shop"]
        item = next((i for i in shop if i), None)
        if item:
            response = requests.post(
                f"{BASE_URL}/purchase/item",
                json={
                    "player_id": player_id,
                    "item_id": item["id"],
                    "placement": [0, 0]  # Invalid
                }
            )
            assert response.status_code == 400
            print("   ✓ Invalid placement correctly rejected")

        # 4. Test selling
        print("4. Testing item selling...")
        response = requests.get(f"{BASE_URL}/session/{player_id}")
        grid_items = response.json()["inventory_grid"]
        if grid_items:
            response = requests.post(
                f"{BASE_URL}/sell/item",
                json={
                    "player_id": player_id,
                    "item_id": grid_items[0]["id"],
                    "from_storage": False
                }
            )
            assert response.status_code == 200
            print("   ✓ Item sold successfully")

        self.results["passed"] += 1
        print("\n✓ Inventory management test passed")

    def test_battle_validation(self):
        """Test battle validation rules"""
        print("\n=== BATTLE VALIDATION TEST ===\n")

        # Start session
        response = requests.post(f"{BASE_URL}/session/start?game_seed=200")
        data = response.json()
        player_id = data["player_id"]

        # 1. Test empty inventory rejection
        print("1. Testing empty inventory rejection...")
        response = requests.post(
            f"{BASE_URL}/battle/simulate",
            json={
                "player_id": player_id,
                "round_number": 1
            }
        )
        assert response.status_code == 400
        assert "empty inventory" in response.json()["detail"].lower()
        print("   ✓ Empty inventory correctly rejected")

        # 2. Purchase item and battle
        print("2. Testing battle with items...")
        response = requests.get(f"{BASE_URL}/session/{player_id}")
        shop = response.json()["current_shop"]

        # Purchase multiple items
        positions = [[2, 3], [3, 3], [4, 3]]
        purchases = 0
        for i, item in enumerate(shop):
            if item and purchases < 3:
                response = requests.post(
                    f"{BASE_URL}/purchase/item",
                    json={
                        "player_id": player_id,
                        "item_id": item["id"],
                        "placement": positions[purchases]
                    }
                )
                if response.status_code == 200:
                    purchases += 1

        # Battle with items
        response = requests.post(
            f"{BASE_URL}/battle/simulate",
            json={
                "player_id": player_id,
                "round_number": 1,
                "seed": 42,
                "test_ai_difficulty": "easy"
            }
        )
        assert response.status_code == 200
        result = response.json()
        print(f"   ✓ Battle completed (Winner: {'Player' if result['battle_result']['winner'] == 1 else 'AI'})")

        self.results["passed"] += 1
        print("\n✓ Battle validation test passed")

    def test_session_persistence(self):
        """Test that session state persists correctly"""
        print("\n=== SESSION PERSISTENCE TEST ===\n")

        # Start session
        response = requests.post(f"{BASE_URL}/session/start?game_seed=300")
        data = response.json()
        player_id = data["player_id"]
        initial_gold = data["session"]["gold"]

        # Make some changes
        shop = data["session"]["current_shop"]
        item = next((i for i in shop if i), None)

        if item:
            # Purchase item
            response = requests.post(
                f"{BASE_URL}/purchase/item",
                json={
                    "player_id": player_id,
                    "item_id": item["id"],
                    "placement": [2, 3]
                }
            )
            assert response.status_code == 200
            gold_after_purchase = response.json()["gold"]

            # Get session and verify changes persist
            response = requests.get(f"{BASE_URL}/session/{player_id}")
            assert response.status_code == 200
            session = response.json()

            assert session["gold"] == gold_after_purchase
            assert session["gold"] < initial_gold
            assert len(session["inventory_grid"]) == 1

            print("   ✓ Gold updated correctly")
            print("   ✓ Inventory persisted")

        self.results["passed"] += 1
        print("\n✓ Session persistence test passed")

    def test_shop_mechanics(self):
        """Test shop refresh and rarity mechanics"""
        print("\n=== SHOP MECHANICS TEST ===\n")

        # Start session
        response = requests.post(f"{BASE_URL}/session/start?game_seed=400")
        data = response.json()
        player_id = data["player_id"]
        initial_shop = data["session"]["current_shop"]
        initial_gold = data["session"]["gold"]

        # 1. Test shop refresh
        print("1. Testing shop refresh...")
        response = requests.post(
            f"{BASE_URL}/shop/refresh",
            json={
                "player_id": player_id,
                "round": 1
            }
        )
        assert response.status_code == 200
        new_shop = response.json()["shop"]
        new_gold = response.json()["gold"]

        # Should cost 1 gold
        assert new_gold == initial_gold - 1
        print("   ✓ Shop refresh cost 1 gold")

        # Should have different items (with high probability)
        initial_ids = [i["id"] if i else None for i in initial_shop]
        new_ids = [i["id"] if i else None for i in new_shop]
        assert initial_ids != new_ids  # Very unlikely to be same with random generation
        print("   ✓ Shop items changed")

        self.results["passed"] += 1
        print("\n✓ Shop mechanics test passed")

    def run_all_tests(self):
        """Run all integration tests"""
        print("\n" + "="*50)
        print("FULL INTEGRATION TEST SUITE")
        print("="*50)

        if not self.start_server():
            print("✗ Could not start server")
            return False

        tests = [
            self.test_complete_game_flow,
            self.test_inventory_management,
            self.test_battle_validation,
            self.test_session_persistence,
            self.test_shop_mechanics,
        ]

        for test_func in tests:
            try:
                test_func()
            except AssertionError as e:
                print(f"\n✗ Test failed: {e}")
                self.results["failed"] += 1
            except Exception as e:
                print(f"\n✗ Test crashed: {e}")
                self.results["failed"] += 1

        # Print summary
        print("\n" + "="*50)
        print("TEST SUMMARY")
        print("="*50)
        print(f"✓ Passed: {self.results['passed']}")
        print(f"✗ Failed: {self.results['failed']}")
        print(f"⊘ Skipped: {self.results['skipped']}")

        success = self.results["failed"] == 0
        if success:
            print("\n✅ ALL INTEGRATION TESTS PASSED!")
        else:
            print("\n❌ SOME TESTS FAILED")

        return success

    def cleanup(self):
        """Clean up resources"""
        self.stop_server()


def main():
    tester = FullIntegrationTest()
    try:
        success = tester.run_all_tests()
        return 0 if success else 1
    finally:
        tester.cleanup()


if __name__ == "__main__":
    sys.exit(main())
