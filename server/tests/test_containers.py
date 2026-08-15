"""
Test the server container system
"""

from battle_engine import ITEM_CATALOG, BattleSimulator, PlacedItem
from containers import Container, PlacementValidator
from grid_system import SHAPES


class TestContainers:
    """Test server container functionality"""

    def test_container_placement(self):
        """Test that containers can be placed and provide grid space"""
        validator = PlacementValidator()

        # Create a standard VM at position (1, 1)
        standard_vm = Container.of("standard_vm", (1, 1), "vm1")

        # Should be able to place it
        assert validator.add_container(standard_vm)

        # Should cover four squares (standard VM is 2x2)
        assert len(standard_vm.covered_squares()) == 4

        # Check that (1,1) is available (top-left of rack's internal space)
        assert (1, 1) in validator.available_squares

    def test_container_overlap(self):
        """Test that containers cannot overlap each other"""
        validator = PlacementValidator()

        # Place first VM
        vm1 = Container.of("standard_vm", (1, 1), "vm1")
        assert validator.add_container(vm1)

        # Try to place overlapping VM
        vm2 = Container.of("standard_vm", (2, 2), "vm2")
        assert not validator.add_container(vm2)  # Should fail

        # Try non-overlapping VM
        vm3 = Container.of("standard_vm", (4, 1), "vm3")
        assert validator.add_container(vm3)  # Should succeed

    def test_the_grid_is_nine_wide_and_seven_tall(self):
        """The validator uses the real grid, which is wider than it is tall"""
        validator = PlacementValidator()

        # A 2x2 at (7, 0) ends on column 8, the last one.
        assert validator.add_container(Container.of("standard_vm", (7, 0), "vm_right"))

        # Row 7 does not exist, so a 2x2 at (0, 6) hangs off the bottom.
        assert not validator.add_container(
            Container.of("standard_vm", (0, 6), "vm_low")
        )

    def test_item_must_be_on_server(self):
        """Test that items must be placed on server-provided squares"""
        validator = PlacementValidator()

        # No containers yet, so no available squares
        assert len(validator.available_squares) == 0

        # Try to place item - should fail
        assert not validator.validate_item_placement((0, 0), SHAPES["1x1"])

        # Add a container
        validator.add_container(Container.of("standard_vm", (1, 1), "vm1"))

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

        # Add a container orchestrator
        validator.add_container(
            Container.of("container_orchestrator", (1, 1), "container1")
        )

        # Place first item
        assert validator.place_item((1, 1), SHAPES["1x1"])

        # Try to place overlapping item
        assert not validator.place_item((1, 1), SHAPES["1x1"])  # Same position

        # Place non-overlapping item
        assert validator.place_item((2, 1), SHAPES["1x1"])

    def test_multi_square_items_on_servers(self):
        """Test that multi-square items work with servers"""
        validator = PlacementValidator()

        # Add a container orchestrator (3x2, 6 slots)
        validator.add_container(
            Container.of("container_orchestrator", (1, 1), "container1")
        )

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

        # Place two adjacent VMs
        vm1 = Container.of("standard_vm", (0, 0), "vm1")
        vm2 = Container.of("standard_vm", (2, 0), "vm2")  # Adjacent to vm1

        validator.add_container(vm1)
        validator.add_container(vm2)

        # Place a 3x1 item that spans both VMs
        # This item would occupy squares from both containers
        assert validator.validate_item_placement((1, 0), SHAPES["3x1"])

        # Get containers for this item
        containers_touched = validator.get_containers_for_item((1, 0), SHAPES["3x1"])
        assert len(containers_touched) == 2  # Item spans both containers

    def test_non_rectangular_container_covers_only_its_shape(self):
        """A container offers the squares of its shape, and no others"""
        validator = PlacementValidator()

        # An L shape covers (0,0), (0,1) and (1,1) of its 2x2 bounding box
        validator.add_container(
            Container(
                id="l1",
                slug="l_rack",
                type="l_rack",
                position=(1, 1),
                shape=SHAPES["L_shape"].squares,
            )
        )

        assert validator.validate_item_placement((1, 1), SHAPES["1x1"])
        assert validator.validate_item_placement((1, 2), SHAPES["1x1"])
        assert validator.validate_item_placement((2, 2), SHAPES["1x1"])

        # The fourth square of the bounding box is not part of the shape
        assert not validator.validate_item_placement((2, 1), SHAPES["1x1"])

    def test_battle_with_containers(self):
        """Test that battle engine validates with containers"""
        sim = BattleSimulator(seed=12345)

        # Create a container
        vm1 = Container.of("standard_vm", (1, 1), "p1_vm")

        # Create items placed in the VM
        p1_items = [
            PlacedItem(
                spec=ITEM_CATALOG["null_blade"],
                position=(1, 1),  # Inside VM
                uid="item1",
            ),
            PlacedItem(
                spec=ITEM_CATALOG["core_dumper"],
                position=(2, 1),  # Inside VM
                uid="item2",
            ),
        ]

        p2_items = [
            PlacedItem(
                spec=ITEM_CATALOG["error_monitoring"],
                position=(1, 1),  # Would need its own VM
                uid="item3",
            )
        ]

        # Should pass validation with containers
        # (In real usage, p2 would also need a container)
        vm2 = Container.of("standard_vm", (1, 1), "p2_vm")

        # Run battle with container validation
        result = sim.simulate_battle(
            p1_items,
            p2_items,
            round_number=1,
            p1_containers=[vm1],
            p2_containers=[vm2],
        )

        assert result["winner"] in [1, 2]
