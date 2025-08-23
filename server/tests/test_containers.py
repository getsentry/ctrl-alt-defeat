"""
Test the server container system
"""

from battle_engine import BattleSimulator, PlacedItem
from config_loader import config_loader
from grid_system import SHAPES
from item_effects import create_example_items
from server_containers import PlacementValidator, ServerContainer


class TestServerContainers:
    """Test server container functionality"""

    def test_container_placement(self):
        """Test that containers can be placed and provide grid space"""
        validator = PlacementValidator(main_grid_size=(7, 9))
        vm = config_loader.get_container("standard_vm")

        # Create a standard VM at position (1, 1)
        standard_vm = ServerContainer(
            spec=vm,
            position=(1, 1),
            uid="vm1",
        )

        # Should be able to place it
        assert validator.add_container(standard_vm)

        # Should provide internal squares (standard VM is 2x2)
        internal_squares = standard_vm.get_internal_squares()
        assert len(internal_squares) == 4  # 2x2 = 4 squares

        # Check that (1,1) is available (top-left of rack's internal space)
        assert (1, 1) in validator.available_squares

    def test_container_overlap(self):
        """Test that containers cannot overlap each other"""
        validator = PlacementValidator()
        vm = config_loader.get_container("standard_vm")
        # Place first VM
        vm1 = ServerContainer(
            spec=vm,
            position=(1, 1),
            uid="vm1",
        )
        assert validator.add_container(vm1)

        # Try to place overlapping VM
        vm2 = ServerContainer(
            spec=vm,
            position=(2, 2),  # This would overlap with vm1
            uid="vm2",
        )
        assert not validator.add_container(vm2)  # Should fail

        # Try non-overlapping VM
        vm3 = ServerContainer(
            spec=vm,
            position=(4, 1),  # No overlap
            uid="vm3",
        )
        assert validator.add_container(vm3)  # Should succeed

    def test_item_must_be_on_server(self):
        """Test that items must be placed on server-provided squares"""
        validator = PlacementValidator()

        # No containers yet, so no available squares
        assert len(validator.available_squares) == 0

        # Try to place item - should fail
        assert not validator.validate_item_placement((0, 0), SHAPES["1x1"])

        # Add a container
        vm = config_loader.get_container("standard_vm")
        vm = ServerContainer(
            spec=vm,
            position=(1, 1),
            uid="vm1",
        )
        validator.add_container(vm)

        # Now we have available squares
        assert len(validator.available_squares) > 0

        # Can place item inside the rack (rack is at (1,1) and is 2x2)
        assert validator.validate_item_placement((1, 1), SHAPES["1x1"])
        assert validator.validate_item_placement((2, 1), SHAPES["1x1"])
        assert validator.validate_item_placement((1, 2), SHAPES["1x1"])
        assert validator.validate_item_placement((2, 2), SHAPES["1x1"])

        # Cannot place item outside the rack
        assert not validator.validate_item_placement((0, 0), SHAPES["1x1"])
        assert not validator.validate_item_placement((3, 1), SHAPES["1x1"])

    def test_items_cannot_overlap(self):
        """Test that items cannot overlap each other"""
        validator = PlacementValidator()
        vm = config_loader.get_container("container_orchestrator")

        # Add a container orchestrator
        container = ServerContainer(
            spec=vm,
            position=(1, 1),
            uid="container1",
        )
        validator.add_container(container)

        # Place first item
        assert validator.place_item((1, 1), SHAPES["1x1"])

        # Try to place overlapping item
        assert not validator.place_item((1, 1), SHAPES["1x1"])  # Same position

        # Place non-overlapping item
        assert validator.place_item((2, 1), SHAPES["1x1"])

    def test_multi_square_items_on_servers(self):
        """Test that multi-square items work with servers"""
        validator = PlacementValidator()
        vm = config_loader.get_container("container_orchestrator")
        # Add a container orchestrator (3x2, 6 slots)
        container = ServerContainer(
            spec=vm,
            position=(1, 1),
            uid="container1",
        )
        validator.add_container(container)

        # Place a 2x2 item
        assert validator.validate_item_placement((1, 1), SHAPES["2x2"])
        assert validator.place_item((1, 1), SHAPES["2x2"])

        # Try to place overlapping 2x2 item
        assert not validator.validate_item_placement(
            (2, 2), SHAPES["2x2"]
        )  # Would overlap

        # Place non-overlapping item
        # Container orchestrator is at (1,1) and is 3x2, so it covers (1,1) to (3,2)
        # Item at (1,1) occupies (1,1), (2,1), (1,2), (2,2)
        # So we can place at (3,1) which is still inside the container
        assert validator.validate_item_placement((3, 1), SHAPES["1x1"])

    def test_item_spanning_containers(self):
        """Test that items can span multiple containers"""
        validator = PlacementValidator()
        vm = config_loader.get_container("standard_vm")

        # Place two adjacent VMs
        vm1 = ServerContainer(
            spec=vm,
            position=(0, 0),
            uid="vm1",
        )
        vm2 = ServerContainer(
            spec=vm,
            position=(2, 0),  # Adjacent to vm1
            uid="vm2",
        )

        validator.add_container(vm1)
        validator.add_container(vm2)

        # Place a 3x1 item that spans both VMs
        # This item would occupy squares from both containers
        assert validator.validate_item_placement((1, 0), SHAPES["3x1"])

        # Get containers for this item
        containers_touched = validator.get_containers_for_item((1, 0), SHAPES["3x1"])
        assert len(containers_touched) == 2  # Item spans both containers

    def test_battle_with_containers(self):
        """Test that battle engine validates with containers"""
        sim = BattleSimulator(seed=12345)
        items = create_example_items()
        vm = config_loader.get_container("standard_vm")

        # Create a container
        vm1 = ServerContainer(
            spec=vm,
            position=(1, 1),
            uid="p1_vm",
        )

        # Create items placed in the VM
        p1_items = [
            PlacedItem(
                spec=items["null_blade"],
                position=(1, 1),  # Inside VM
                uid="item1",
            ),
            PlacedItem(
                spec=items["core_dumper"],
                position=(2, 1),  # Inside VM
                uid="item2",
            ),
        ]

        p2_items = [
            PlacedItem(
                spec=items["error_monitoring"],
                position=(1, 1),  # Would need its own VM
                uid="item3",
            )
        ]

        # Should pass validation with containers
        # (In real usage, p2 would also need a container)
        vm2 = ServerContainer(
            spec=vm,
            position=(1, 1),
            uid="p2_vm",
        )

        # Run battle with container validation
        result = sim.simulate_battle(
            p1_items,
            p2_items,
            round_number=1,
            p1_containers=[vm1],
            p2_containers=[vm2],
        )

        assert result["winner"] in [1, 2]


if __name__ == "__main__":
    # Run tests
    test = TestServerContainers()

    print("Testing container placement...")
    test.test_container_placement()
    print("✓ Container placement works")

    print("\nTesting container overlap...")
    test.test_container_overlap()
    print("✓ Containers cannot overlap")

    print("\nTesting items must be on servers...")
    test.test_item_must_be_on_server()
    print("✓ Items must be placed on servers")

    print("\nTesting items cannot overlap...")
    test.test_items_cannot_overlap()
    print("✓ Items cannot overlap each other")

    print("\nTesting multi-square items...")
    test.test_multi_square_items_on_servers()
    print("✓ Multi-square items work correctly")

    print("\nTesting items spanning containers...")
    test.test_item_spanning_containers()
    print("✓ Items can span multiple containers")

    print("\nTesting battle with containers...")
    test.test_battle_with_containers()
    print("✓ Battle engine validates with containers")

    print("\n✅ All container tests passed!")
