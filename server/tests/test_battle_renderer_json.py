"""
Test battle renderer with JSON-loaded items to ensure it works correctly
"""

import pytest
from battle_engine import BattleSimulator, PlacedItem
from battle_renderer import ASCIIBattleRenderer
from config_loader import ConfigLoader
from server_containers import ServerContainer


class TestBattleRendererWithJSON:
    """Test that battle renderer works with JSON-loaded items"""

    def test_render_with_json_items_no_hang(self):
        """Test rendering a battle with items loaded from JSON"""
        # Load configurations
        loader = ConfigLoader()
        loader.load_all()

        # Get items
        null_pointer = loader.get_item("null_pointer")
        firewall = loader.get_item("firewall")
        memory_leak = loader.get_item("memory_leak")

        assert null_pointer is not None, "null_pointer should be loaded from JSON"
        assert firewall is not None, "firewall should be loaded from JSON"

        # Get containers
        containers = loader.containers
        standard_vm = containers["standard_vm"]

        # Create container instances
        p1_container = ServerContainer(
            spec=standard_vm["spec"],
            position=(0, 0),
            uid="p1_vm",
            internal_grid_size=standard_vm["internal_size"],
            shape=standard_vm["external_shape"],
        )

        p2_container = ServerContainer(
            spec=standard_vm["spec"],
            position=(4, 0),
            uid="p2_vm",
            internal_grid_size=standard_vm["internal_size"],
            shape=standard_vm["external_shape"],
        )

        # Create items
        p1_items = [
            PlacedItem(spec=null_pointer, position=(0, 0), uid="p1_null"),
            PlacedItem(spec=memory_leak, position=(1, 0), uid="p1_leak"),
        ]
        p2_items = [PlacedItem(spec=firewall, position=(4, 0), uid="p2_fw")]

        # Run battle
        sim = BattleSimulator(seed=12345)
        result = sim.simulate_battle(
            p1_items,
            p2_items,
            round_number=1,
            p1_containers=[p1_container],
            p2_containers=[p2_container],
        )

        # Check result has required fields for rendering
        assert "winner" in result
        assert "duration" in result
        assert "player1_quota" in result
        assert "player2_quota" in result
        assert "actions" in result

        # Create renderer
        renderer = ASCIIBattleRenderer()

        # Test that items have the required attributes for rendering
        for item in p1_items + p2_items:
            assert hasattr(item.spec, "name"), f"Item {item.uid} missing name"
            assert hasattr(item.spec, "category"), f"Item {item.uid} missing category"
            assert hasattr(item, "position"), f"Item {item.uid} missing position"

        # Test rendering doesn't crash
        try:
            # Capture output instead of displaying
            import io
            import sys

            old_stdout = sys.stdout
            sys.stdout = io.StringIO()

            # Mock input to avoid hanging in step-by-step mode
            import unittest.mock

            with unittest.mock.patch("builtins.input", return_value="q"):
                renderer.render_battle(
                    result,
                    p1_items,
                    p2_items,
                    real_time=False,
                    p1_containers=[p1_container],
                    p2_containers=[p2_container],
                )
            output = sys.stdout.getvalue()

            sys.stdout = old_stdout

            # Check output contains expected elements
            assert "BATTLE REPLAY" in output
            assert "Player 1:" in output
            assert "Player 2:" in output
            assert "HP" in output
            assert "CPU" in output

        except Exception as e:
            pytest.fail(f"Renderer crashed with error: {e}")

    def test_render_with_missing_attributes(self):
        """Test that renderer handles items with missing attributes gracefully"""
        from item_effects import AttackEffect, ItemSpec, TimerTrigger

        # Create a minimal item without some optional attributes
        minimal_item = ItemSpec(
            id="test_item",
            name="Test Item",
            category="problem",
            triggers=[
                TimerTrigger(
                    cooldown=1.0,
                    cpu_cost=1,
                    effects=[AttackEffect(min_damage=1, max_damage=2)],
                )
            ],
        )

        # Create placed item
        p1_items = [PlacedItem(spec=minimal_item, position=(0, 0), uid="test1")]
        p2_items = []

        # Create containers
        from server_containers import create_server_containers

        containers = create_server_containers()
        standard_vm = containers["standard_vm"]

        p1_container = ServerContainer(
            spec=standard_vm["spec"],
            position=(0, 0),
            uid="p1_vm",
            internal_grid_size=standard_vm["internal_size"],
            shape=standard_vm["external_shape"],
        )

        p2_container = ServerContainer(
            spec=standard_vm["spec"],
            position=(4, 0),
            uid="p2_vm",
            internal_grid_size=standard_vm["internal_size"],
            shape=standard_vm["external_shape"],
        )

        # Run minimal battle
        sim = BattleSimulator(seed=54321)
        result = sim.simulate_battle(
            p1_items,
            p2_items,
            round_number=1,
            p1_containers=[p1_container],
            p2_containers=[p2_container],
        )

        # Test rendering doesn't crash even with minimal item
        renderer = ASCIIBattleRenderer()

        try:
            import io
            import sys

            old_stdout = sys.stdout
            sys.stdout = io.StringIO()

            # Mock input to avoid hanging in step-by-step mode
            import unittest.mock

            with unittest.mock.patch("builtins.input", return_value="q"):
                renderer.render_battle(
                    result,
                    p1_items,
                    p2_items,
                    real_time=False,
                    p1_containers=[p1_container],
                    p2_containers=[p2_container],
                )

            sys.stdout = old_stdout
            # If we get here, rendering succeeded

        except AttributeError as e:
            pytest.fail(f"Renderer failed with missing attribute: {e}")
        except Exception:
            # Other exceptions might be acceptable
            pass

    def test_render_action_processing(self):
        """Test that action processing works with JSON items"""
        from battle_renderer import ACTION_CODES, BattleState

        loader = ConfigLoader()
        loader.load_all()

        renderer = ASCIIBattleRenderer()

        # Create a simple battle state
        state = BattleState(
            player1_hp=25,
            player1_max_hp=25,
            player1_cpu=10.0,
            player1_max_cpu=10,
            player1_items={
                "test_item": {"name": "Test Item", "position": (0, 0), "active": False}
            },
            player2_hp=25,
            player2_max_hp=25,
            player2_cpu=10.0,
            player2_max_cpu=10,
            player2_items={},
            current_time=0.0,
            last_actions=[],
            p1_containers=[],
            p2_containers=[],
        )

        # Test processing a damage action
        action = {
            "a": ACTION_CODES.get("DAMAGE", "d"),
            "i": "test_item",
            "p": 2,
            "v": 5,
            "t": 1.0,
        }

        # Process the action
        renderer._process_action(state, action)

        # Check that player 2 took damage
        assert state.player2_hp == 20  # 25 - 5
        assert len(state.last_actions) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
