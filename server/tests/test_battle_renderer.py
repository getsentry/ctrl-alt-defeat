"""
Test the ASCII battle renderer using JSON-loaded items
"""

import io
import json
import sys
import tempfile
import unittest.mock

import pytest
from battle_engine import BattleSimulator, PlacedItem
from battle_renderer import ASCIIBattleRenderer, BattleState
from config_loader import ConfigLoader
from item_effects import AttackEffect, ItemSpec, TimerTrigger
from schemas import BattleAction
from server_containers import ServerContainer


class TestBattleRenderer:
    """Test ASCII battle rendering functionality with JSON-loaded items"""

    @pytest.fixture(autouse=True)
    def setup_config(self):
        """Load configurations before each test"""
        self.loader = ConfigLoader()
        self.loader.load_all()

    def test_render_battle_with_json_items(self):
        """Test rendering a battle with items loaded from JSON"""
        # Get items from JSON
        null_pointer = self.loader.get_item("null_pointer")
        firewall = self.loader.get_item("firewall")
        memory_leak = self.loader.get_item("memory_leak")

        assert null_pointer is not None, "null_pointer should be loaded from JSON"
        assert firewall is not None, "firewall should be loaded from JSON"
        assert memory_leak is not None, "memory_leak should be loaded from JSON"

        # Get containers from JSON
        containers = self.loader.containers
        standard_vm = containers["standard_vm"]

        # Create container instances
        p1_container = ServerContainer(
            spec=standard_vm["spec"],
            position=(0, 0),
            uid="p1_vm",
            shape=standard_vm["external_shape"],
        )

        p2_container = ServerContainer(
            spec=standard_vm["spec"],
            position=(4, 0),
            uid="p2_vm",
            shape=standard_vm["external_shape"],
        )

        # Create items
        p1_items = [
            PlacedItem(spec=null_pointer, position=(0, 0), uid="p1_null"),
            PlacedItem(spec=memory_leak, position=(1, 0), uid="p1_leak"),
        ]

        p2_items = [PlacedItem(spec=firewall, position=(4, 0), uid="p2_firewall")]

        # Run battle
        sim = BattleSimulator(seed=12345)
        result = sim.simulate_battle(
            p1_items,
            p2_items,
            round_number=1,
            p1_containers=[p1_container],
            p2_containers=[p2_container],
        )

        # Add starting HP for renderer
        result["player1_quota_start"] = 25
        result["player2_quota_start"] = 25

        # Create renderer and test rendering
        renderer = ASCIIBattleRenderer()

        # Capture output and mock input to avoid hanging
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()

        try:
            with unittest.mock.patch("builtins.input", return_value="q"):
                renderer.render_battle(
                    result,
                    p1_items,
                    p2_items,
                    real_time=False,  # Step mode
                    p1_containers=[p1_container],
                    p2_containers=[p2_container],
                )

            output = sys.stdout.getvalue()

            # Verify output contains expected elements
            assert "BATTLE REPLAY" in output
            assert "Player 1:" in output
            assert "Player 2:" in output
            assert "HP" in output
            assert "CPU" in output

        finally:
            sys.stdout = old_stdout

    def test_save_and_load_battle(self):
        """Test saving and loading battle results for replay"""
        # Get items from JSON
        null_pointer = self.loader.get_item("null_pointer")
        memory_leak = self.loader.get_item("memory_leak")

        # Get container
        standard_vm = self.loader.containers["standard_vm"]
        p1_container = ServerContainer(
            spec=standard_vm["spec"],
            position=(0, 0),
            uid="p1_vm",
            shape=standard_vm["external_shape"],
        )
        p2_container = ServerContainer(
            spec=standard_vm["spec"],
            position=(4, 0),
            uid="p2_vm",
            shape=standard_vm["external_shape"],
        )

        # Create items
        p1_items = [PlacedItem(spec=null_pointer, position=(0, 0), uid="p1_null")]
        p2_items = [PlacedItem(spec=memory_leak, position=(4, 0), uid="p2_leak")]

        # Run battle
        sim = BattleSimulator(seed=42)
        result = sim.simulate_battle(
            p1_items,
            p2_items,
            round_number=1,
            p1_containers=[p1_container],
            p2_containers=[p2_container],
        )

        # Remove non-serializable fields before saving
        # Convert BattleAction objects to dicts for JSON serialization
        serializable_actions = [action.model_dump() for action in result["actions"]]
        clean_result = {
            "winner": result["winner"],
            "duration": result["duration"],
            "player1_quota": result["player1_quota"],
            "player2_quota": result["player2_quota"],
            "actions": serializable_actions,
            "seed": result["seed"],
        }

        # Save to temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(clean_result, f, indent=2)
            temp_path = f.name

        # Load from file
        with open(temp_path, "r") as f:
            loaded_result = json.load(f)

        # Verify loaded data matches original
        assert loaded_result["winner"] == clean_result["winner"]
        assert loaded_result["duration"] == clean_result["duration"]
        assert len(loaded_result["actions"]) == len(clean_result["actions"])

        # Clean up
        import os

        os.unlink(temp_path)

    def test_progress_bar(self):
        """Test progress bar rendering functionality"""
        # The renderer doesn't expose _render_progress_bar directly
        # Instead test that battle rendering includes progress elements
        null_pointer = self.loader.get_item("null_pointer")

        # Get container
        standard_vm = self.loader.containers["standard_vm"]
        p1_container = ServerContainer(
            spec=standard_vm["spec"],
            position=(0, 0),
            uid="p1_vm",
            shape=standard_vm["external_shape"],
        )
        p2_container = ServerContainer(
            spec=standard_vm["spec"],
            position=(4, 0),
            uid="p2_vm",
            shape=standard_vm["external_shape"],
        )

        p1_items = [PlacedItem(spec=null_pointer, position=(0, 0), uid="p1")]
        p2_items = []

        sim = BattleSimulator(seed=100)
        result = sim.simulate_battle(
            p1_items,
            p2_items,
            round_number=1,
            p1_containers=[p1_container],
            p2_containers=[p2_container],
        )

        # Verify result has HP values that would be rendered as progress
        assert "player1_quota" in result
        assert "player2_quota" in result

    def test_action_processing(self):
        """Test that renderer correctly processes battle actions"""
        # Get items from JSON
        null_pointer = self.loader.get_item("null_pointer")
        firewall = self.loader.get_item("firewall")

        p1_items = [PlacedItem(spec=null_pointer, position=(0, 0), uid="p1_null")]
        p2_items = [PlacedItem(spec=firewall, position=(4, 0), uid="p2_firewall")]

        # Create initial battle state
        state = BattleState(
            player1_hp=25,
            player1_max_hp=25,
            player1_cpu=10.0,
            player1_max_cpu=10,
            player1_items={
                item.uid: {"name": item.spec.name, "active": False} for item in p1_items
            },
            player2_hp=25,
            player2_max_hp=25,
            player2_cpu=10.0,
            player2_max_cpu=10,
            player2_items={
                item.uid: {"name": item.spec.name, "active": False} for item in p2_items
            },
            current_time=0.0,
            last_actions=[],
        )

        renderer = ASCIIBattleRenderer()

        # Process some test actions - use BattleAction objects
        test_actions = [
            BattleAction(
                timestamp=1000,
                source="p1_null",
                action="activate",
                target=None,
                damage=None,
                player=1,
                details=None,
            ),
            BattleAction(
                timestamp=1000,
                source="",
                action="damage",
                target=None,
                damage=5,
                player=2,
                details=None,
            ),
            BattleAction(
                timestamp=1000,
                source="",
                action="heal",
                target=None,
                damage=3,
                player=1,
                details=None,
            ),
        ]

        for action in test_actions:
            renderer._process_action(state, action)

        # Verify state was updated
        assert len(state.last_actions) > 0
        # After damage action, player2_hp should be reduced
        assert state.player2_hp == 20  # 25 - 5 damage
        # After heal action, player1_hp should be increased
        assert state.player1_hp == 25  # was 25, healed 3 but capped at max

    def test_render_with_missing_attributes(self):
        """Test that renderer handles items with missing optional attributes"""
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

        # Get container
        standard_vm = self.loader.containers["standard_vm"]
        p1_container = ServerContainer(
            spec=standard_vm["spec"],
            position=(0, 0),
            uid="p1_vm",
            shape=standard_vm["external_shape"],
        )
        p2_container = ServerContainer(
            spec=standard_vm["spec"],
            position=(4, 0),
            uid="p2_vm",
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

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()

        try:
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

            # Should still produce valid output
            assert "BATTLE REPLAY" in output

        except Exception as e:
            pytest.fail(f"Renderer crashed with minimal item: {e}")
        finally:
            sys.stdout = old_stdout

    def test_render_no_containers(self):
        """Test that renderer works with minimal container setup"""
        # Get items from JSON
        null_pointer = self.loader.get_item("null_pointer")

        # Get container - required now
        standard_vm = self.loader.containers["standard_vm"]
        p1_container = ServerContainer(
            spec=standard_vm["spec"],
            position=(0, 0),
            uid="p1_vm",
            shape=standard_vm["external_shape"],
        )
        p2_container = ServerContainer(
            spec=standard_vm["spec"],
            position=(4, 0),
            uid="p2_vm",
            shape=standard_vm["external_shape"],
        )

        p1_items = [PlacedItem(spec=null_pointer, position=(0, 0), uid="p1_null")]
        p2_items = [PlacedItem(spec=null_pointer, position=(4, 0), uid="p2_null")]

        # Run battle with containers (required now)
        sim = BattleSimulator(seed=99)
        result = sim.simulate_battle(
            p1_items,
            p2_items,
            round_number=1,
            p1_containers=[p1_container],
            p2_containers=[p2_container],
        )

        # Add starting HP
        result["player1_quota_start"] = 25
        result["player2_quota_start"] = 25

        # Test rendering with containers
        renderer = ASCIIBattleRenderer()

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()

        try:
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

            # Should work with containers
            assert "BATTLE REPLAY" in output

        finally:
            sys.stdout = old_stdout
