#!/usr/bin/env python3
"""
Test that JSON configuration system works correctly
"""

from battle_engine import BattleItem, BattleSimulator
from config_loader import ConfigLoader
from containers import Container


def test_json_config():
    """Test that we can load and use items from JSON"""

    print("Testing JSON Configuration System")
    print("=" * 50)

    # Load configurations
    loader = ConfigLoader()
    loader.load_all()

    print(f"\n✅ Loaded {len(loader.containers)} containers from JSON")
    print(f"✅ Loaded {len(loader.items)} items from JSON")

    # Test that we can create a battle with JSON-loaded items
    sim = BattleSimulator(seed=12345)

    # Get some items from JSON config
    null_blade = loader.get_item("null_blade")
    core_dumper = loader.get_item("core_dumper")
    loader.get_item("firewall")  # Verify it exists
    health_check = loader.get_item("health_check")

    # Create container instances from JSON config
    p1_container = Container.of("standard_vm", (0, 0), "p1_vm")
    p2_container = Container.of("edge_node", (4, 0), "p2_edge")

    # Create items
    p1_items = [
        BattleItem(spec=null_blade, position=(0, 0), uid="p1_null"),
        BattleItem(spec=core_dumper, position=(1, 0), uid="p1_leak"),
    ]

    # Place items that fit within the edge_node container (2x1 horizontal at 4,0)
    # Use smaller items that fit in the available squares
    p2_items = [
        BattleItem(spec=core_dumper, position=(4, 0), uid="p2_null2"),  # 1x1 item
        BattleItem(spec=health_check, position=(5, 0), uid="p2_health"),  # 1x1 item
    ]

    # Run battle
    print("\n🎮 Running test battle with JSON-loaded items...")
    result = sim.simulate_battle(
        p1_items,
        p2_items,
        round_number=1,
        p1_containers=[p1_container],
        p2_containers=[p2_container],
    )

    print(f"✅ Battle completed! Winner: Player {result['winner']}")
    print(f"   Duration: {result['duration']:.1f}s")
    print(f"   Total actions: {len(result['actions'])}")

    # Test some specific items
    print("\n📋 Testing specific items from JSON:")

    # Test a problem item
    ddos = loader.get_item("denier_of_service")
    if ddos:
        print(f"✅ DDoS Attack: {ddos.name} ({ddos.rarity})")
        print(f"   Shape: {ddos.shape.name if ddos.shape else 'None'}")
        print(f"   Triggers: {len(ddos.triggers)}")

    # Test a defense item
    quantum_fw = loader.get_item("quantum_firewall")
    if quantum_fw:
        print(f"✅ Quantum Firewall: {quantum_fw.name} ({quantum_fw.rarity})")
        print(f"   Category: {quantum_fw.category}")
        print(f"   Triggers: {len(quantum_fw.triggers)}")

    # Test a container
    orchestrator = loader.get_container("container_orchestrator")
    if orchestrator:
        print(f"\n✅ Container Orchestrator: {orchestrator.name}")
        print(f"   Shape: {orchestrator.shape.name if orchestrator.shape else 'None'}")
        print(f"   Cost: {orchestrator.cost}")

    print("\n" + "=" * 50)
    print("✨ JSON Configuration System Test Complete!")
    print("\nThe system successfully:")
    print("  • Loaded items and containers from JSON files")
    print("  • Created battle-ready items from configurations")
    print("  • Ran a complete battle simulation")
    print("\nYou can now easily add/modify items by editing:")
    print("  • data/items/*.json (category-specific item files)")
    print("  • data/containers.json")


if __name__ == "__main__":
    test_json_config()


class TestShopVisibility:
    """An item can exist without the shop offering it"""

    def test_items_are_offered_unless_told_otherwise(self):
        from config_loader import config_loader

        spec = config_loader.items["null_blade"]
        assert spec.in_shop is True

    def test_the_shop_skips_an_item_that_is_not_offered(self):
        # Items arrive from Backpack Battles with numbers and no behaviour.
        # They have to be able to sit in the catalogue without a player
        # being able to buy one.
        from unittest.mock import patch

        from battle_engine import ITEM_CATALOG
        from main import generate_shop_items

        hidden = "null_blade"
        original = ITEM_CATALOG[hidden]
        with patch.dict(ITEM_CATALOG, {hidden: original.__class__(
            **{**original.__dict__, "in_shop": False}
        )}):
            offered = set()
            for seed in range(120):
                offered |= {i.item_type for i in generate_shop_items(1, seed) if i}
        assert hidden not in offered, "a hidden item should never reach the shop"
        assert len(offered) > 5, "the rest of the catalogue should still be offered"
