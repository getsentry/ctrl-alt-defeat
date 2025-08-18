"""
Demo battle with server containers and multi-square items
"""

from battle_engine import BattleSimulator, PlacedItem
from battle_renderer import ASCIIBattleRenderer
from grid_system import SHAPES
from item_effects import create_example_items
from server_containers import ServerContainer, create_server_containers


def demo_container_battle():
    """Demo a battle with containers and multi-square items"""

    print("=== CONTAINER BATTLE DEMO ===")
    print("Demonstrating server racks and multi-square items\n")

    # Get items and containers
    items = create_example_items()
    containers = create_server_containers()

    # Player 1 setup - aggressive build with a mini rack
    p1_rack = ServerContainer(
        spec=containers["mini_rack"]["spec"],
        position=(1, 1),  # Place rack at (1,1) in main grid
        uid="p1_rack",
        internal_grid_size=containers["mini_rack"]["internal_size"],
        shape=containers["mini_rack"]["external_shape"],
    )

    # Player 1 items - placed ON the rack squares
    # The mini rack occupies (1,1), (2,1), (1,2), (2,2)
    p1_items = [
        PlacedItem(
            spec=items["null_pointer"],
            position=(1, 1),  # Top-left of rack
            uid="p1_null",
            shape=SHAPES["1x1"],
        ),
        PlacedItem(
            spec=items["memory_leak"],
            position=(2, 1),  # Top-right of rack
            uid="p1_leak",
            shape=SHAPES["1x1"],
        ),
        PlacedItem(
            spec=items["sql_injection"],
            position=(1, 2),  # Bottom-left of rack
            uid="p1_sql",
            shape=SHAPES["1x1"],  # Keep it simple for now
        ),
    ]

    # Player 2 setup - defensive build with a standard rack
    p2_rack = ServerContainer(
        spec=containers["standard_rack"]["spec"],
        position=(4, 1),  # Place rack at (4,1) - no overlap with P1
        uid="p2_rack",
        internal_grid_size=containers["standard_rack"]["internal_size"],
        shape=containers["standard_rack"]["external_shape"],
    )

    # Player 2 items - defensive with multi-square items
    # The standard rack occupies (4,1), (5,1), (4,2), (5,2), (4,3), (5,3)
    p2_items = [
        PlacedItem(
            spec=items["error_monitoring"],
            position=(4, 1),  # Top-left of rack
            uid="p2_monitor",
            shape=SHAPES["1x1"],
        ),
        PlacedItem(
            spec=items["redis_cache"],
            position=(5, 1),  # Top-right of rack
            uid="p2_cache",
            shape=SHAPES["1x1"],
        ),
        PlacedItem(
            spec=items["health_potion"],
            position=(4, 2),  # Middle-left of rack
            uid="p2_potion",
            shape=SHAPES["1x1"],
        ),
    ]

    print("Player 1 Setup:")
    print(f"  - Mini Server Rack at {p1_rack.position} (2x2 squares)")
    print("  - Null Pointer at (1,1)")
    print("  - Memory Leak at (2,1)")
    print("  - SQL Injection at (1,2)")

    print("\nPlayer 2 Setup:")
    print(f"  - Standard Server Rack at {p2_rack.position} (2x3 squares)")
    print("  - Error Monitoring at (4,1)")
    print("  - Redis Cache at (5,1)")
    print("  - Health Potion at (4,2)")

    # Run the battle
    print("\n" + "=" * 50)
    print("Running battle simulation...")

    sim = BattleSimulator(seed=98765)
    result = sim.simulate_battle(
        p1_items,
        p2_items,
        round_number=3,  # Round 3 has 35 HP
        validate_placement=True,
        p1_containers=[p1_rack],
        p2_containers=[p2_rack],
    )

    print("Battle completed!")
    print(f"  Winner: Player {result['winner']}")
    print(f"  Duration: {result['duration']}s")
    print(f"  Final HP: P1={result['player1_quota']} P2={result['player2_quota']}")
    print(f"  Total actions: {len(result['actions'])}")

    # Set starting HP for renderer
    result["player1_quota_start"] = 35
    result["player2_quota_start"] = 35

    # Render the battle
    print("\n" + "=" * 50)
    print("Starting battle replay...")
    print("The grid will show:")
    print("  ▓ = Server Rack (provides space)")
    print("  · = Empty space (no server)")
    print("  Letters = Items placed on servers")
    print("\nItems will light up with colors when they activate!")
    print("\nPress Enter to start...")
    input()

    renderer = ASCIIBattleRenderer()
    renderer.render_battle(
        result,
        p1_items,
        p2_items,
        real_time=True,
        speed=2.0,  # 2x speed for demo
        p1_containers=[p1_rack],
        p2_containers=[p2_rack],
    )

    return result


if __name__ == "__main__":
    # Run the demo
    demo_container_battle()
