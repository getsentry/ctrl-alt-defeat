"""
Test the battle_renderer.py main block to ensure it doesn't break
"""

import subprocess
import sys

import pytest


class TestBattleRendererMain:
    """Test that the battle_renderer.py script can be run directly"""

    def test_renderer_main_block_runs(self):
        """Test that python battle_renderer.py doesn't crash"""
        # Test with option 2 (step-by-step) and immediate quit
        process = subprocess.Popen(
            [sys.executable, "battle_renderer.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Send "2" for step-by-step mode, then "q" to quit
        stdout, stderr = process.communicate(input="2\nq\n", timeout=5)

        # Check that it didn't crash
        assert (
            process.returncode == 0
        ), f"battle_renderer.py crashed with error:\n{stderr}"

        # Check for expected output
        assert "Choose playback mode:" in stdout
        assert "BATTLE REPLAY" in stdout
        assert "Player 1:" in stdout
        assert "Player 2:" in stdout

        # Should not have KeyError or TypeError
        assert "KeyError" not in stderr
        assert "TypeError" not in stderr
        assert "mini_rack" not in stderr  # Old container name shouldn't appear

    def test_renderer_realtime_mode(self):
        """Test that real-time mode starts without crashing"""
        # Test with option 1 (real-time) with high speed to finish quickly
        process = subprocess.Popen(
            [sys.executable, "battle_renderer.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            # Send "1" for real-time, "10.0" for 10x speed (should finish quickly)
            stdout, stderr = process.communicate(input="1\n10.0\n", timeout=10)

            # Check that it didn't crash
            assert (
                process.returncode == 0
            ), f"battle_renderer.py crashed with error:\n{stderr}"

            # Check for battle completion
            assert "BATTLE ENDED" in stdout or "Winner" in stdout

            # Should not have errors
            assert "KeyError" not in stderr
            assert "TypeError" not in stderr

        except subprocess.TimeoutExpired:
            process.kill()
            pytest.fail("Real-time mode took too long to complete")

    def test_renderer_imports_and_containers(self):
        """Test that the renderer uses correct container names and imports"""
        with open("battle_renderer.py", "r") as f:
            content = f.read()

        # Check that we're not using old container names
        assert (
            '"mini_rack"' not in content or 'containers["mini_rack"]' not in content
        ), "battle_renderer.py still references old 'mini_rack' container"

        # Check that we're using the correct container name
        assert (
            'containers["standard_vm"]' in content or '"standard_vm"' in content
        ), "battle_renderer.py should use 'standard_vm' container"

        # Check that necessary imports are present
        assert "from server_containers import" in content
        assert "from battle_engine import" in content

    def test_renderer_with_json_config(self):
        """Test that renderer works with JSON-loaded configuration"""
        # Create a test script that uses the renderer with JSON config
        test_script = """
import sys
from battle_engine import BattleSimulator, PlacedItem
from battle_renderer import ASCIIBattleRenderer
from config_loader import ConfigLoader
from server_containers import ServerContainer

# Load config
loader = ConfigLoader()
loader.load_all()

# Get items from JSON
null_pointer = loader.get_item("null_pointer")
firewall = loader.get_item("firewall")

# Get containers from JSON
containers = loader.containers
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
p1_items = [PlacedItem(spec=null_pointer, position=(0, 0), uid="p1_null")]
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

# Try to render (but exit immediately)
renderer = ASCIIBattleRenderer()
import unittest.mock
with unittest.mock.patch('builtins.input', return_value='q'):
    renderer.render_battle(
        result,
        p1_items,
        p2_items,
        real_time=False,
        p1_containers=[p1_container],
        p2_containers=[p2_container],
    )

print("SUCCESS: Renderer works with JSON config")
sys.exit(0)
"""

        # Write and run the test script
        with open("test_renderer_json_temp.py", "w") as f:
            f.write(test_script)

        try:
            process = subprocess.run(
                [sys.executable, "test_renderer_json_temp.py"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            assert process.returncode == 0, f"Script failed:\n{process.stderr}"
            assert "SUCCESS" in process.stdout

        finally:
            # Clean up
            import os

            if os.path.exists("test_renderer_json_temp.py"):
                os.remove("test_renderer_json_temp.py")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
