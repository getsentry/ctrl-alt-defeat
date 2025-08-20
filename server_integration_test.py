#!/usr/bin/env python3
"""
Full integration tests for the Sentry Autobattler.
Tests both server API and client-server integration.
"""

import os
import sys
import time
import json
import subprocess
import requests
from typing import Dict, List, Optional, Tuple
import signal

# Add server directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

BASE_URL = "http://localhost:8000"

class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

class ServerIntegrationTest:
    """Complete integration tests for server and client"""

    def __init__(self):
        self.server_process = None
        self.player_id = None
        self.session = None
        self.shop = []
        self.inventory_grid = []
        self.inventory_storage = []

        # Enable test mode
        os.environ["TEST_MODE"] = "true"

    def start_server(self) -> bool:
        """Start the server process"""
        print(f"{Colors.BLUE}Starting server...{Colors.ENDC}")
        try:
            # Start server in background
            self.server_process = subprocess.Popen(
                ["python", "main.py"],
                cwd="server",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid if sys.platform != "win32" else None
            )

            # Wait for server to start
            time.sleep(2)

            # Check if server is running
            try:
                response = requests.get(f"{BASE_URL}/docs", timeout=2)
                if response.status_code == 200:
                    print(f"{Colors.GREEN}✓ Server started successfully{Colors.ENDC}")
                    return True
            except:
                pass

            print(f"{Colors.RED}✗ Server failed to start{Colors.ENDC}")
            self.stop_server()
            return False

        except Exception as e:
            print(f"{Colors.RED}✗ Error starting server: {e}{Colors.ENDC}")
            return False

    def stop_server(self):
        """Stop the server process"""
        if self.server_process:
            print(f"{Colors.BLUE}Stopping server...{Colors.ENDC}")
            if sys.platform == "win32":
                self.server_process.terminate()
            else:
                os.killpg(os.getpgid(self.server_process.pid), signal.SIGTERM)
            self.server_process.wait(timeout=5)
            self.server_process = None
            print(f"{Colors.GREEN}✓ Server stopped{Colors.ENDC}")

    def test_start_session(self, seed: int = 42) -> bool:
        """Test starting a new game session with seed"""
        print(f"\n{Colors.BOLD}Testing: Start Session{Colors.ENDC}")
        try:
            response = requests.post(f"{BASE_URL}/session/start?game_seed={seed}")
            if response.status_code == 200:
                data = response.json()
                self.player_id = data.get("player_id")
                self.session = data.get("session", {})

                print(f"{Colors.GREEN}✓ Session started{Colors.ENDC}")
                print(f"  Player ID: {self.player_id[:8]}...")
                print(f"  Gold: {self.session.get('gold', 0)}")
                print(f"  Lives: {self.session.get('lives', 0)}")
                print(f"  Round: {self.session.get('round', 0)}")

                # Store shop and inventory
                self.shop = self.session.get('current_shop', [])
                self.inventory_grid = self.session.get('inventory_grid', [])
                self.inventory_storage = self.session.get('inventory_storage', [])

                return True
            else:
                print(f"{Colors.RED}✗ Failed to start session: {response.status_code}{Colors.ENDC}")
                return False
        except Exception as e:
            print(f"{Colors.RED}✗ Error: {e}{Colors.ENDC}")
            return False

    def test_get_session(self) -> bool:
        """Test getting current session state"""
        print(f"\n{Colors.BOLD}Testing: Get Session{Colors.ENDC}")
        if not self.player_id:
            print(f"{Colors.YELLOW}⚠ No player ID, skipping{Colors.ENDC}")
            return False

        try:
            response = requests.get(f"{BASE_URL}/session/{self.player_id}")
            if response.status_code == 200:
                self.session = response.json()

                print(f"{Colors.GREEN}✓ Got session state{Colors.ENDC}")
                print(f"  Round: {self.session.get('round', 0)}")
                print(f"  Gold: {self.session.get('gold', 0)}")
                print(f"  Lives: {self.session.get('lives', 0)}")
                print(f"  Grid items: {len(self.session.get('inventory_grid', []))}")
                print(f"  Storage items: {len(self.session.get('inventory_storage', []))}")

                return True
            else:
                print(f"{Colors.RED}✗ Failed: {response.status_code}{Colors.ENDC}")
                return False
        except Exception as e:
            print(f"{Colors.RED}✗ Error: {e}{Colors.ENDC}")
            return False

    def test_purchase_to_grid(self) -> bool:
        """Test purchasing an item to the grid"""
        print(f"\n{Colors.BOLD}Testing: Purchase to Grid{Colors.ENDC}")

        # Find first available item
        item_to_buy = None
        for item in self.shop:
            if item and item.get("cost", 999) <= self.session.get("gold", 0):
                item_to_buy = item
                break

        if not item_to_buy:
            print(f"{Colors.YELLOW}⚠ No affordable items{Colors.ENDC}")
            return False

        try:
            payload = {
                "player_id": self.player_id,
                "item_id": item_to_buy["id"],
                "placement": [2, 3]  # First container position
            }

            response = requests.post(f"{BASE_URL}/purchase/item", json=payload)
            if response.status_code == 200:
                data = response.json()
                print(f"{Colors.GREEN}✓ Purchased to grid{Colors.ENDC}")
                print(f"  Item: {item_to_buy.get('name')}")
                print(f"  Position: [2, 3]")
                print(f"  Cost: {item_to_buy.get('cost')}g")
                print(f"  Remaining gold: {data.get('gold', 0)}")
                return True
            else:
                print(f"{Colors.RED}✗ Failed: {response.status_code}{Colors.ENDC}")
                if response.text:
                    print(f"  Error: {response.json().get('detail', response.text)}")
                return False
        except Exception as e:
            print(f"{Colors.RED}✗ Error: {e}{Colors.ENDC}")
            return False

    def test_purchase_to_storage(self) -> bool:
        """Test purchasing an item to storage"""
        print(f"\n{Colors.BOLD}Testing: Purchase to Storage{Colors.ENDC}")

        # Refresh session to get current shop
        self.test_get_session()
        self.shop = self.session.get('current_shop', [])

        # Find an available item
        item_to_buy = None
        for item in self.shop:
            if item and item.get("cost", 999) <= self.session.get("gold", 0):
                item_to_buy = item
                break

        if not item_to_buy:
            print(f"{Colors.YELLOW}⚠ No affordable items{Colors.ENDC}")
            return False

        try:
            payload = {
                "player_id": self.player_id,
                "item_id": item_to_buy["id"],
                "placement": "storage"
            }

            response = requests.post(f"{BASE_URL}/purchase/item", json=payload)
            if response.status_code == 200:
                data = response.json()
                print(f"{Colors.GREEN}✓ Purchased to storage{Colors.ENDC}")
                print(f"  Item: {item_to_buy.get('name')}")
                print(f"  Cost: {item_to_buy.get('cost')}g")
                return True
            else:
                print(f"{Colors.RED}✗ Failed: {response.status_code}{Colors.ENDC}")
                return False
        except Exception as e:
            print(f"{Colors.RED}✗ Error: {e}{Colors.ENDC}")
            return False

    def test_invalid_placement(self) -> bool:
        """Test that invalid placement is rejected"""
        print(f"\n{Colors.BOLD}Testing: Invalid Placement{Colors.ENDC}")

        # Get fresh shop
        self.test_shop_refresh()

        item_to_buy = None
        for item in self.shop:
            if item:
                item_to_buy = item
                break

        if not item_to_buy:
            print(f"{Colors.YELLOW}⚠ No items in shop{Colors.ENDC}")
            return False

        try:
            payload = {
                "player_id": self.player_id,
                "item_id": item_to_buy["id"],
                "placement": [0, 0]  # Invalid position (not on container)
            }

            response = requests.post(f"{BASE_URL}/purchase/item", json=payload)
            if response.status_code == 400:
                print(f"{Colors.GREEN}✓ Correctly rejected invalid placement{Colors.ENDC}")
                error = response.json().get('detail', '')
                print(f"  Error: {error}")
                return True
            else:
                print(f"{Colors.RED}✗ Should have rejected placement{Colors.ENDC}")
                return False
        except Exception as e:
            print(f"{Colors.RED}✗ Error: {e}{Colors.ENDC}")
            return False

    def test_shop_refresh(self) -> bool:
        """Test refreshing the shop"""
        print(f"\n{Colors.BOLD}Testing: Shop Refresh{Colors.ENDC}")

        try:
            payload = {
                "player_id": self.player_id,
                "round": self.session.get("round", 1)
            }

            response = requests.post(f"{BASE_URL}/shop/refresh", json=payload)
            if response.status_code == 200:
                data = response.json()
                self.shop = data.get("shop", [])

                items_count = sum(1 for item in self.shop if item is not None)
                print(f"{Colors.GREEN}✓ Shop refreshed{Colors.ENDC}")
                print(f"  Items available: {items_count}")
                print(f"  Gold remaining: {data.get('gold', 0)}")

                # Display first 3 items
                displayed = 0
                for item in self.shop:
                    if item and displayed < 3:
                        print(f"  - {item.get('name')} ({item.get('cost')}g)")
                        displayed += 1

                return True
            else:
                print(f"{Colors.RED}✗ Failed: {response.status_code}{Colors.ENDC}")
                return False
        except Exception as e:
            print(f"{Colors.RED}✗ Error: {e}{Colors.ENDC}")
            return False

    def test_battle_empty_inventory(self) -> bool:
        """Test that battling with empty inventory fails"""
        print(f"\n{Colors.BOLD}Testing: Battle with Empty Inventory{Colors.ENDC}")

        # Start fresh session
        self.test_start_session(seed=100)

        try:
            payload = {
                "player_id": self.player_id,
                "round_number": 1,
                "seed": 42
            }

            response = requests.post(f"{BASE_URL}/battle/simulate", json=payload)
            if response.status_code == 400:
                print(f"{Colors.GREEN}✓ Correctly rejected empty inventory{Colors.ENDC}")
                error = response.json().get('detail', '')
                print(f"  Error: {error}")
                return True
            else:
                print(f"{Colors.RED}✗ Should have rejected empty inventory{Colors.ENDC}")
                return False
        except Exception as e:
            print(f"{Colors.RED}✗ Error: {e}{Colors.ENDC}")
            return False

    def test_battle_with_items(self) -> bool:
        """Test battle simulation with items"""
        print(f"\n{Colors.BOLD}Testing: Battle with Items{Colors.ENDC}")

        # Make sure we have items
        if not self.test_purchase_to_grid():
            return False

        try:
            payload = {
                "player_id": self.player_id,
                "round_number": 1,
                "seed": 42,
                "test_ai_difficulty": 1
            }

            response = requests.post(f"{BASE_URL}/battle/simulate", json=payload)
            if response.status_code == 200:
                data = response.json()
                result = data.get("battle_result", {})
                update = data.get("session_update", {})
                winner = result.get("winner", 0)

                print(f"{Colors.GREEN}✓ Battle completed{Colors.ENDC}")
                print(f"  Winner: {'Player' if winner == 1 else 'AI'}")
                print(f"  Round: {update.get('round', 1)}")
                print(f"  Gold earned: {update.get('gold_earned', 0)}")
                print(f"  Lives: {update.get('lives', 0)}")
                print(f"  Wins: {update.get('wins', 0)}")
                print(f"  Losses: {update.get('losses', 0)}")

                return True
            else:
                print(f"{Colors.RED}✗ Failed: {response.status_code}{Colors.ENDC}")
                print(f"  Response: {response.text}")
                return False
        except Exception as e:
            print(f"{Colors.RED}✗ Error: {e}{Colors.ENDC}")
            return False

    def test_sell_item(self) -> bool:
        """Test selling an item"""
        print(f"\n{Colors.BOLD}Testing: Sell Item{Colors.ENDC}")

        # Get current inventory
        self.test_get_session()
        grid_items = self.session.get("inventory_grid", [])

        if not grid_items:
            print(f"{Colors.YELLOW}⚠ No items to sell{Colors.ENDC}")
            return False

        item_to_sell = grid_items[0]

        try:
            payload = {
                "player_id": self.player_id,
                "item_id": item_to_sell["id"],
                "from_storage": False
            }

            response = requests.post(f"{BASE_URL}/sell/item", json=payload)
            if response.status_code == 200:
                data = response.json()
                print(f"{Colors.GREEN}✓ Item sold{Colors.ENDC}")
                print(f"  Gold gained: {data.get('gold_gained', 0)}")
                print(f"  Total gold: {data.get('gold', 0)}")
                return True
            else:
                print(f"{Colors.RED}✗ Failed: {response.status_code}{Colors.ENDC}")
                return False
        except Exception as e:
            print(f"{Colors.RED}✗ Error: {e}{Colors.ENDC}")
            return False

    def test_full_round_cycle(self) -> bool:
        """Test a complete round cycle"""
        print(f"\n{Colors.BOLD}Testing: Full Round Cycle{Colors.ENDC}")

        # Start fresh
        if not self.test_start_session(seed=200):
            return False

        print("  Phase 1: Purchase items...")
        # Purchase multiple items
        positions = [[2, 3], [3, 3], [4, 3]]
        purchases = 0

        for i, item in enumerate(self.shop[:3]):
            if item and purchases < 3:
                payload = {
                    "player_id": self.player_id,
                    "item_id": item["id"],
                    "placement": positions[purchases]
                }
                response = requests.post(f"{BASE_URL}/purchase/item", json=payload)
                if response.status_code == 200:
                    purchases += 1
                    print(f"    Purchased {item.get('name')} at {positions[purchases-1]}")

        print(f"  Phase 2: Battle (purchased {purchases} items)...")
        payload = {
            "player_id": self.player_id,
            "round_number": 1,
            "seed": 42,
            "test_ai_difficulty": 1
        }

        response = requests.post(f"{BASE_URL}/battle/simulate", json=payload)
        if response.status_code == 200:
            data = response.json()
            winner = data.get("battle_result", {}).get("winner", 0)
            update = data.get("session_update", {})

            print(f"  Phase 3: Results")
            print(f"    Winner: {'Player' if winner == 1 else 'AI'}")
            print(f"    New round: {update.get('round', 1)}")
            print(f"    Gold: {update.get('gold', 0)}")

            print(f"{Colors.GREEN}✓ Full round cycle completed{Colors.ENDC}")
            return True
        else:
            print(f"{Colors.RED}✗ Battle failed{Colors.ENDC}")
            return False

    def test_victory_condition(self) -> bool:
        """Test reaching victory by winning round 10"""
        print(f"\n{Colors.BOLD}Testing: Victory Condition (10 rounds){Colors.ENDC}")

        # Start fresh
        if not self.test_start_session(seed=300):
            return False

        for round_num in range(1, 11):
            print(f"  Round {round_num}...")

            # Get current session
            self.test_get_session()

            # Purchase items
            positions = [[2, 3], [3, 3], [4, 3], [5, 3], [2, 4], [3, 4]]
            purchases = 0
            max_purchases = min(3 + round_num // 2, 6)  # Scale with round

            for item in self.session.get("current_shop", []):
                if item and purchases < max_purchases:
                    payload = {
                        "player_id": self.player_id,
                        "item_id": item["id"],
                        "placement": positions[purchases]
                    }
                    response = requests.post(f"{BASE_URL}/purchase/item", json=payload)
                    if response.status_code == 200:
                        purchases += 1

            # Battle with easy AI
            payload = {
                "player_id": self.player_id,
                "round_number": round_num,
                "seed": 42 + round_num,
                "test_ai_difficulty": 1
            }

            response = requests.post(f"{BASE_URL}/battle/simulate", json=payload)
            if response.status_code == 200:
                data = response.json()
                update = data.get("session_update", {})

                if update.get("victory", False):
                    print(f"{Colors.GREEN}✓ Victory achieved at round {round_num}!{Colors.ENDC}")
                    return True

                if update.get("game_over", False):
                    print(f"{Colors.RED}✗ Game over before victory{Colors.ENDC}")
                    return False

        print(f"{Colors.YELLOW}⚠ Did not achieve victory in 10 rounds{Colors.ENDC}")
        return False

    def run_all_tests(self) -> Tuple[int, int]:
        """Run all integration tests"""
        print(f"\n{Colors.BOLD}{'='*50}{Colors.ENDC}")
        print(f"{Colors.BOLD}SENTRY AUTOBATTLER INTEGRATION TESTS{Colors.ENDC}")
        print(f"{Colors.BOLD}{'='*50}{Colors.ENDC}")

        tests = [
            ("Start Session", self.test_start_session),
            ("Get Session", self.test_get_session),
            ("Purchase to Grid", self.test_purchase_to_grid),
            ("Purchase to Storage", self.test_purchase_to_storage),
            ("Invalid Placement", self.test_invalid_placement),
            ("Shop Refresh", self.test_shop_refresh),
            ("Sell Item", self.test_sell_item),
            ("Battle Empty Inventory", self.test_battle_empty_inventory),
            ("Battle with Items", self.test_battle_with_items),
            ("Full Round Cycle", self.test_full_round_cycle),
            # ("Victory Condition", self.test_victory_condition),  # Long test
        ]

        passed = 0
        failed = 0

        for name, test_func in tests:
            try:
                if test_func():
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"{Colors.RED}✗ Test crashed: {e}{Colors.ENDC}")
                failed += 1

        return passed, failed

    def run_client_tests(self) -> bool:
        """Run Godot client tests"""
        print(f"\n{Colors.BOLD}Running Client Tests...{Colors.ENDC}")

        try:
            # Run Godot tests in headless mode
            result = subprocess.run(
                ["godot", "--headless", "--script", "tests/test_server_integration.gd"],
                cwd="client",
                capture_output=True,
                text=True,
                timeout=30
            )

            print(result.stdout)
            if result.stderr:
                print(f"{Colors.YELLOW}Warnings: {result.stderr}{Colors.ENDC}")

            return result.returncode == 0
        except FileNotFoundError:
            print(f"{Colors.YELLOW}⚠ Godot not found in PATH{Colors.ENDC}")
            print("  Install Godot or add it to PATH to run client tests")
            return False
        except subprocess.TimeoutExpired:
            print(f"{Colors.RED}✗ Client tests timed out{Colors.ENDC}")
            return False
        except Exception as e:
            print(f"{Colors.RED}✗ Error running client tests: {e}{Colors.ENDC}")
            return False


def main():
    """Main test runner"""
    tester = ServerIntegrationTest()

    # Check if server is already running
    server_was_running = False
    try:
        response = requests.get(f"{BASE_URL}/docs", timeout=1)
        if response.status_code == 200:
            server_was_running = True
            print(f"{Colors.BLUE}Using existing server at {BASE_URL}{Colors.ENDC}")
    except:
        # Start server
        if not tester.start_server():
            print(f"{Colors.RED}Failed to start server{Colors.ENDC}")
            return 1

    try:
        # Run server tests
        passed, failed = tester.run_all_tests()

        # Run client tests if available
        # tester.run_client_tests()

        # Print summary
        print(f"\n{Colors.BOLD}{'='*50}{Colors.ENDC}")
        print(f"{Colors.BOLD}TEST SUMMARY{Colors.ENDC}")
        print(f"{Colors.BOLD}{'='*50}{Colors.ENDC}")
        print(f"{Colors.GREEN}Passed: {passed}{Colors.ENDC}")
        print(f"{Colors.RED}Failed: {failed}{Colors.ENDC}")

        if failed == 0:
            print(f"\n{Colors.GREEN}{Colors.BOLD}✅ ALL TESTS PASSED!{Colors.ENDC}")
            return 0
        else:
            print(f"\n{Colors.RED}{Colors.BOLD}❌ SOME TESTS FAILED{Colors.ENDC}")
            return 1

    finally:
        # Stop server if we started it
        if not server_was_running:
            tester.stop_server()


if __name__ == "__main__":
    exit(main())
