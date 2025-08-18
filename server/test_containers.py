"""
Test the server container system
"""

from battle_engine import BattleSimulator, PlacedItem
from grid_system import SHAPES
from item_effects import create_example_items
from server_containers import (
    PlacementValidator,
    ServerContainer,
    create_server_containers,
)


class TestServerContainers:
    """Test server container functionality"""

    def test_container_placement(self):
        """Test that containers can be placed and provide grid space"""
        validator = PlacementValidator(main_grid_size=(7, 9))
        containers = create_server_containers()

        # Create a mini rack at position (1, 1)
        mini_rack = ServerContainer(
            spec=containers["mini_rack"]["spec"],
            position=(1, 1),
            uid="rack1",
            internal_grid_size=containers["mini_rack"]["internal_size"],
            shape=containers["mini_rack"]["external_shape"],
        )

        # Should be able to place it
        assert validator.add_container(mini_rack)

        # Should provide internal squares
        internal_squares = mini_rack.get_internal_squares()
        assert len(internal_squares) == 12  # 3x4 internal grid

        # Check that (1,1) is available (top-left of rack's internal space)
        assert (1, 1) in validator.available_squares

    def test_container_overlap(self):
        """Test that containers cannot overlap each other"""
        validator = PlacementValidator()
        containers = create_server_containers()

        # Place first rack
        rack1 = ServerContainer(
            spec=containers["mini_rack"]["spec"],
            position=(1, 1),
            uid="rack1",
            internal_grid_size=(3, 4),
            shape=SHAPES["2x2"],
        )
        assert validator.add_container(rack1)

        # Try to place overlapping rack
        rack2 = ServerContainer(
            spec=containers["mini_rack"]["spec"],
            position=(2, 2),  # This would overlap with rack1
            uid="rack2",
            internal_grid_size=(3, 4),
            shape=SHAPES["2x2"],
        )
        assert not validator.add_container(rack2)  # Should fail

        # Try non-overlapping rack
        rack3 = ServerContainer(
            spec=containers["mini_rack"]["spec"],
            position=(4, 1),  # No overlap
            uid="rack3",
            internal_grid_size=(3, 4),
            shape=SHAPES["2x2"],
        )
        assert validator.add_container(rack3)  # Should succeed

    def test_item_must_be_on_server(self):
        """Test that items must be placed on server-provided squares"""
        validator = PlacementValidator()

        # No containers yet, so no available squares
        assert len(validator.available_squares) == 0

        # Try to place item - should fail
        assert not validator.validate_item_placement((0, 0), SHAPES["1x1"])

        # Add a container
        containers = create_server_containers()
        rack = ServerContainer(
            spec=containers["mini_rack"]["spec"],
            position=(1, 1),
            uid="rack1",
            internal_grid_size=(3, 4),
            shape=SHAPES["2x2"],
        )
        validator.add_container(rack)

        # Now we have available squares
        assert len(validator.available_squares) > 0

        # Can place item inside the rack
        assert validator.validate_item_placement((1, 1), SHAPES["1x1"])

        # Cannot place item outside the rack
        assert not validator.validate_item_placement((0, 0), SHAPES["1x1"])

    def test_items_cannot_overlap(self):
        """Test that items cannot overlap each other"""
        validator = PlacementValidator()
        containers = create_server_containers()

        # Add a large rack
        rack = ServerContainer(
            spec=containers["standard_rack"]["spec"],
            position=(1, 1),
            uid="rack1",
            internal_grid_size=(4, 5),
            shape=SHAPES["2x3"],
        )
        validator.add_container(rack)

        # Place first item
        assert validator.place_item((1, 1), SHAPES["1x1"])

        # Try to place overlapping item
        assert not validator.place_item((1, 1), SHAPES["1x1"])  # Same position

        # Place non-overlapping item
        assert validator.place_item((2, 1), SHAPES["1x1"])

    def test_multi_square_items_on_servers(self):
        """Test that multi-square items work with servers"""
        validator = PlacementValidator()
        containers = create_server_containers()

        # Add a large rack
        rack = ServerContainer(
            spec=containers["enterprise_rack"]["spec"],
            position=(1, 1),
            uid="rack1",
            internal_grid_size=(5, 6),
            shape=SHAPES["3x3"],
        )
        validator.add_container(rack)

        # Place a 2x2 item
        assert validator.validate_item_placement((1, 1), SHAPES["2x2"])
        assert validator.place_item((1, 1), SHAPES["2x2"])

        # Try to place overlapping 2x2 item
        assert not validator.validate_item_placement(
            (2, 2), SHAPES["2x2"]
        )  # Would overlap

        # Place non-overlapping item
        assert validator.validate_item_placement((3, 3), SHAPES["2x2"])

    def test_item_spanning_containers(self):
        """Test that items can span multiple containers"""
        validator = PlacementValidator()
        containers = create_server_containers()

        # Place two adjacent racks
        rack1 = ServerContainer(
            spec=containers["mini_rack"]["spec"],
            position=(0, 0),
            uid="rack1",
            internal_grid_size=(3, 4),
            shape=SHAPES["2x2"],
        )
        rack2 = ServerContainer(
            spec=containers["mini_rack"]["spec"],
            position=(2, 0),  # Adjacent to rack1
            uid="rack2",
            internal_grid_size=(3, 4),
            shape=SHAPES["2x2"],
        )

        validator.add_container(rack1)
        validator.add_container(rack2)

        # Place a 3x1 item that spans both racks
        # This item would occupy squares from both containers
        assert validator.validate_item_placement((1, 0), SHAPES["3x1"])

        # Get containers for this item
        containers_touched = validator.get_containers_for_item((1, 0), SHAPES["3x1"])
        assert len(containers_touched) == 2  # Item spans both containers

    def test_battle_with_containers(self):
        """Test that battle engine validates with containers"""
        sim = BattleSimulator(seed=12345)
        items = create_example_items()
        containers = create_server_containers()

        # Create a container
        rack = ServerContainer(
            spec=containers["mini_rack"]["spec"],
            position=(1, 1),
            uid="p1_rack",
            internal_grid_size=(3, 4),
            shape=SHAPES["2x2"],
        )

        # Create items placed in the rack
        p1_items = [
            PlacedItem(
                spec=items["null_pointer"],
                position=(1, 1),  # Inside rack
                uid="item1",
                shape=SHAPES["1x1"],
            ),
            PlacedItem(
                spec=items["memory_leak"],
                position=(2, 1),  # Inside rack
                uid="item2",
                shape=SHAPES["1x1"],
            ),
        ]

        p2_items = [
            PlacedItem(
                spec=items["error_monitoring"],
                position=(1, 1),  # Would need its own rack
                uid="item3",
                shape=SHAPES["1x1"],
            )
        ]

        # Should pass validation with containers
        # (In real usage, p2 would also need a container)
        rack2 = ServerContainer(
            spec=containers["mini_rack"]["spec"],
            position=(1, 1),
            uid="p2_rack",
            internal_grid_size=(3, 4),
            shape=SHAPES["2x2"],
        )

        # Run battle with container validation
        result = sim.simulate_battle(
            p1_items,
            p2_items,
            round_number=1,
            validate_placement=True,
            p1_containers=[rack],
            p2_containers=[rack2],
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
