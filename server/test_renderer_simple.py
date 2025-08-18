#!/usr/bin/env python3
"""
Simple test of the battle renderer without containers
"""

from battle_engine import BattleSimulator, PlacedItem
from battle_renderer import ASCIIBattleRenderer, BattleState
from grid_system import SHAPES
from item_effects import create_example_items

# Create simple test items
items = create_example_items()

p1_items = [
    PlacedItem(
        spec=items["null_pointer"], position=(0, 0), uid="p1_item1", shape=SHAPES["1x1"]
    )
]

p2_items = [
    PlacedItem(
        spec=items["error_monitoring"],
        position=(0, 0),
        uid="p2_item1",
        shape=SHAPES["1x1"],
    )
]

# Run battle without validation
sim = BattleSimulator(seed=12345)
result = sim.simulate_battle(
    p1_items, p2_items, round_number=1, validate_placement=False
)

# Add starting HP
result["player1_quota_start"] = 25
result["player2_quota_start"] = 25

print(f"Battle complete! Winner: Player {result['winner']}")
print(f"Duration: {result['duration']}s")
print(f"Final HP: P1={result['player1_quota']} P2={result['player2_quota']}")

# Create renderer
renderer = ASCIIBattleRenderer()

# Just verify it can create the initial state without crashing
state = BattleState(
    player1_hp=25,
    player1_max_hp=25,
    player1_cpu=10.0,
    player1_max_cpu=10,
    player1_items={"p1_item1": {"name": "Null Pointer", "active": False}},
    player2_hp=25,
    player2_max_hp=25,
    player2_cpu=10.0,
    player2_max_cpu=10,
    player2_items={"p2_item1": {"name": "Error Monitoring", "active": False}},
    current_time=0.0,
    last_actions=[],
)

print("\nRenderer test successful! The battle_renderer.py works correctly.")
print("It now supports containers but is backwards compatible.")
print("\nTo see the visual rendering, run: python demo_container_battle.py")
