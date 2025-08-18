"""Benchmark battle simulation speed"""
import time
from server.battle_engine import BattleSimulator
from server.item_effects import create_example_items
from server.server_containers import ServerContainer

def run_benchmark():
    # Create simulator
    simulator = BattleSimulator()

    # Create simple test setup
    items = create_example_items()
    container = ServerContainer(
        position=(0, 0),
        width=7,
        height=9
    )

    # Simple item placement
    placed_items = []
    item_specs = [items["null_pointer"], items["memory_leak"], items["error_monitoring"]]
    for i, spec in enumerate(item_specs):
        placed_items.append(type('PlacedItem', (), {
            'spec': spec,
            'position': (i, 0),
            'uid': f'item_{i}',
            'shape': None,
            'rotation': None,
            'current_cooldown': 0.0,
            'memory_leak_stacks': 0,
            'damage_mult': 1.0,
            'accuracy_bonus': 0.0,
            'speed_mult': 1.0,
            'cpu_discount': 0
        })())

    # Benchmark
    start = time.time()
    battles_run = 0

    while time.time() - start < 10:  # Run for 10 seconds
        simulator.simulate_battle(
            p1_items=placed_items,
            p2_items=placed_items,
            round_number=1,
            p1_containers=[container],
            p2_containers=[container]
        )
        battles_run += 1

    elapsed = time.time() - start
    battles_per_second = battles_run / elapsed

    print(f"Battles run: {battles_run}")
    print(f"Time elapsed: {elapsed:.2f} seconds")
    print(f"Battles per second: {battles_per_second:.2f}")
    print(f"\nEstimated time for 100,000 battles: {100000 / battles_per_second / 60:.2f} minutes")
    print(f"Estimated time for 1,000,000 battles: {1000000 / battles_per_second / 60:.2f} minutes")

if __name__ == "__main__":
    run_benchmark()
