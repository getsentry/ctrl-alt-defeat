#!/usr/bin/env python3
"""
Test script for the battle renderer with many real items
Shows a comprehensive battle with diverse items from the catalog
"""

import random
from copy import deepcopy

from battle_engine import ITEM_CATALOG, BattleSimulator, PlacedItem
from battle_renderer import ASCIIBattleRenderer, ServerContainer
from server_containers import create_server_containers


def main():
    # Get container specs
    containers = create_server_containers()

    # Create 3 containers for each player (3x 2x2 VM racks)
    p1_containers = [
        ServerContainer(
            spec=containers["standard_vm"]["spec"],
            position=(0, 1),
            uid="p1_rack1",
            internal_grid_size=containers["standard_vm"]["internal_size"],
            shape=containers["standard_vm"]["external_shape"],
        ),
        ServerContainer(
            spec=containers["standard_vm"]["spec"],
            position=(2, 1),
            uid="p1_rack2",
            internal_grid_size=containers["standard_vm"]["internal_size"],
            shape=containers["standard_vm"]["external_shape"],
        ),
        ServerContainer(
            spec=containers["standard_vm"]["spec"],
            position=(0, 3),
            uid="p1_rack3",
            internal_grid_size=containers["standard_vm"]["internal_size"],
            shape=containers["standard_vm"]["external_shape"],
        ),
    ]

    p2_containers = [
        ServerContainer(
            spec=containers["standard_vm"]["spec"],
            position=(4, 1),
            uid="p2_rack1",
            internal_grid_size=containers["standard_vm"]["internal_size"],
            shape=containers["standard_vm"]["external_shape"],
        ),
        ServerContainer(
            spec=containers["standard_vm"]["spec"],
            position=(4, 3),
            uid="p2_rack2",
            internal_grid_size=containers["standard_vm"]["internal_size"],
            shape=containers["standard_vm"]["external_shape"],
        ),
        ServerContainer(
            spec=containers["standard_vm"]["spec"],
            position=(4, 5),
            uid="p2_rack3",
            internal_grid_size=containers["standard_vm"]["internal_size"],
            shape=containers["standard_vm"]["external_shape"],
        ),
    ]

    # Create a diverse set of items for Player 1
    p1_items = [
        # Rack 1 - Offensive focus
        PlacedItem(
            spec=deepcopy(ITEM_CATALOG["null_pointer"]),
            position=(0, 1),
            uid="p1_null1",
        ),
        PlacedItem(
            spec=deepcopy(ITEM_CATALOG["memory_leak"]),
            position=(1, 1),
            uid="p1_leak1",
        ),
        PlacedItem(
            spec=deepcopy(ITEM_CATALOG["race_condition"]),
            position=(0, 2),
            uid="p1_race1",
        ),
        PlacedItem(
            spec=deepcopy(ITEM_CATALOG["infinite_loop"]),
            position=(1, 2),
            uid="p1_loop1",
        ),
        # Rack 2 - Mixed offense and defense
        PlacedItem(
            spec=deepcopy(ITEM_CATALOG["sql_injection"]),
            position=(2, 1),
            uid="p1_sql1",
        ),
        PlacedItem(
            spec=deepcopy(ITEM_CATALOG["firewall"]),
            position=(3, 1),
            uid="p1_firewall1",
        ),
        PlacedItem(
            spec=deepcopy(ITEM_CATALOG["error_monitoring"]),
            position=(2, 2),
            uid="p1_monitor1",
        ),
        PlacedItem(
            spec=deepcopy(ITEM_CATALOG["rate_limiter"]),
            position=(3, 2),
            uid="p1_rate1",
        ),
        # Rack 3 - Support and infrastructure
        PlacedItem(
            spec=deepcopy(ITEM_CATALOG["cpu_booster"]),
            position=(0, 3),
            uid="p1_cpu1",
        ),
        PlacedItem(
            spec=deepcopy(ITEM_CATALOG["auto_scaler"]),
            position=(1, 3),
            uid="p1_scaler1",
        ),
        PlacedItem(
            spec=deepcopy(ITEM_CATALOG["health_check"]),
            position=(0, 4),
            uid="p1_health1",
        ),
        PlacedItem(
            spec=deepcopy(ITEM_CATALOG["backup_system"]),
            position=(1, 4),
            uid="p1_backup1",
        ),
    ]

    # Create a diverse set of items for Player 2
    p2_items = [
        # Rack 1 - Heavy offense
        PlacedItem(
            spec=deepcopy(ITEM_CATALOG["ddos_attack"]),
            position=(4, 1),
            uid="p2_ddos1",
        ),
        PlacedItem(
            spec=deepcopy(ITEM_CATALOG["zero_day_exploit"]),
            position=(5, 1),
            uid="p2_zero1",
        ),
        PlacedItem(
            spec=deepcopy(ITEM_CATALOG["null_pointer"]),
            position=(4, 2),
            uid="p2_null1",
        ),
        PlacedItem(
            spec=deepcopy(ITEM_CATALOG["memory_leak"]),
            position=(5, 2),
            uid="p2_leak1",
        ),
        # Rack 2 - Heavy defense
        PlacedItem(
            spec=deepcopy(ITEM_CATALOG["quantum_firewall"]),
            position=(4, 3),
            uid="p2_quantum1",
        ),
        PlacedItem(
            spec=deepcopy(ITEM_CATALOG["encryption_layer"]),
            position=(5, 3),
            uid="p2_encrypt1",
        ),
        PlacedItem(
            spec=deepcopy(ITEM_CATALOG["firewall"]),
            position=(4, 4),
            uid="p2_firewall1",
        ),
        PlacedItem(
            spec=deepcopy(ITEM_CATALOG["rate_limiter"]),
            position=(5, 4),
            uid="p2_rate1",
        ),
        # Rack 3 - Infrastructure support
        PlacedItem(
            spec=deepcopy(ITEM_CATALOG["load_balancer_module"]),
            position=(4, 5),
            uid="p2_balancer1",
        ),
        PlacedItem(
            spec=deepcopy(ITEM_CATALOG["cpu_booster"]),
            position=(5, 5),
            uid="p2_cpu1",
        ),
        PlacedItem(
            spec=deepcopy(ITEM_CATALOG["auto_scaler"]),
            position=(4, 6),
            uid="p2_scaler1",
        ),
        PlacedItem(
            spec=deepcopy(ITEM_CATALOG["health_check"]),
            position=(5, 6),
            uid="p2_health1",
        ),
    ]

    print("=" * 80)
    print("EPIC BATTLE SIMULATOR - 12v12 Items!")
    print("=" * 80)
    print("\nPlayer 1 Loadout:")
    print("-" * 40)
    for item in p1_items[:6]:
        print(f"  • {item.spec.name:20} [{item.spec.category}]")
    print(f"  ... and {len(p1_items) - 6} more items")

    print("\nPlayer 2 Loadout:")
    print("-" * 40)
    for item in p2_items[:6]:
        print(f"  • {item.spec.name:20} [{item.spec.category}]")
    print(f"  ... and {len(p2_items) - 6} more items")

    print("\n" + "=" * 80)

    # Ask for seed
    print("\nEnter battle seed (or press Enter for random): ", end="")
    seed_input = input()
    if seed_input:
        seed = int(seed_input)
    else:
        seed = random.randint(1, 999999)

    print(f"\nUsing seed: {seed}")

    # Run the battle simulation
    print("\nSimulating battle...")
    sim = BattleSimulator(seed=seed)
    result = sim.simulate_battle(
        p1_items,
        p2_items,
        round_number=5,  # Mid-game round for balanced quotas
        p1_containers=p1_containers,
        p2_containers=p2_containers,
    )

    # Add starting quotas for renderer
    result["player1_quota_start"] = 35  # Round 5 quota
    result["player2_quota_start"] = 35

    # Create renderer
    renderer = ASCIIBattleRenderer()

    # Ask for playback mode
    print("\nChoose playback mode:")
    print("1. Real-time playback")
    print("2. Step-by-step")
    print("3. Fast forward (5x speed)")
    print("4. Slow motion (0.25x speed)")
    choice = input("Enter choice (1-4): ")

    if choice == "2":
        renderer.render_battle(
            result,
            p1_items,
            p2_items,
            real_time=False,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )
    elif choice == "3":
        renderer.render_battle(
            result,
            p1_items,
            p2_items,
            real_time=True,
            speed=5.0,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )
    elif choice == "4":
        renderer.render_battle(
            result,
            p1_items,
            p2_items,
            real_time=True,
            speed=0.25,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )
    else:
        renderer.render_battle(
            result,
            p1_items,
            p2_items,
            real_time=True,
            speed=1.0,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

    # Show battle stats
    print("\n" + "=" * 80)
    print("BATTLE STATISTICS")
    print("=" * 80)
    print(f"Duration: {result.get('duration', 0):.1f} seconds")
    print(f"Total actions: {len(result.get('actions', []))}")
    print(f"Winner: Player {result.get('winner', 0)}")
    print(
        f"Final quotas: P1={result.get('player1_quota', 0)}, P2={result.get('player2_quota', 0)}"
    )
    print(f"Seed used: {result.get('seed', seed)}")

    # Count action types
    action_counts = {}
    for action in result.get("actions", []):
        action_type = action.get("a", "unknown")
        action_counts[action_type] = action_counts.get(action_type, 0) + 1

    print("\nAction breakdown:")
    for action_type, count in sorted(
        action_counts.items(), key=lambda x: x[1], reverse=True
    ):
        print(f"  {action_type}: {count}")


if __name__ == "__main__":
    main()
