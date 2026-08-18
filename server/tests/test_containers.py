"""
Test the server container system
"""

from battle_engine import ITEM_CATALOG, BattleItem, BattleSimulator
from containers import Container, PlacementValidator
from grid_system import Rotation, parse_map
from items import Item, PlacedItem


# The shapes these tests place, built the way the catalogue builds them.
ONE = parse_map(["#"], "one square")
TWO_BY_TWO = parse_map(["##", "##"], "two by two")
THREE_WIDE = parse_map(["###"], "three wide")
AN_L = parse_map(["#.", "##"], "an L")


class TestAContainerIsAnItem:
    """A container is a placed item whose squares are for other items."""

    def test_it_is_a_placed_item(self):
        assert isinstance(Container.of("standard_vm", (1, 1), "vm1"), PlacedItem)

    def test_it_says_it_is_a_container(self):
        # The same answer the shop's offer gives, so nothing drawing it or
        # laying it out has to know which of the two it was handed.
        assert Container.of("standard_vm", (1, 1), "vm1").is_container

    def test_it_has_the_name_the_shop_sold_it_under(self):
        # The name is what a tooltip shows, so a placed container needs one
        # just as much as the offer the player bought did.
        offer = Item.of("standard_vm", "vm1")
        placed = Container.of("standard_vm", (1, 1), "vm1")
        assert placed.name == offer.name == "Standard VM"
        assert placed.item_type == offer.item_type

    def test_it_carries_no_look_of_its_own(self):
        # A container is the ground the items sit on, so it takes no palette
        # colour and no pattern.
        placed = Container.of("standard_vm", (1, 1), "vm1")
        assert placed.color == ""
        assert placed.pattern == ""

    def test_an_item_bought_and_placed_matches_it(self):
        """The shop sells a container as an Item. Placing it must not change
        what it is, only where it is."""
        offer = Item.of("standard_vm", "vm1")
        placed = Container.of("standard_vm", (1, 1), "vm1")
        assert placed.item_fields() == offer.item_fields()


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
        assert not validator.validate_item_placement((0, 0), ONE)

        # Add a container
        validator.add_container(Container.of("standard_vm", (1, 1), "vm1"))

        # Now we have available squares
        assert len(validator.available_squares) > 0

        # Can place item inside the rack (rack is at (1,1) and is 2x2)
        assert validator.validate_item_placement((1, 1), ONE)
        assert validator.validate_item_placement((2, 1), ONE)
        assert validator.validate_item_placement((1, 2), ONE)
        assert validator.validate_item_placement((2, 2), ONE)

        # Cannot place item outside the rack
        assert not validator.validate_item_placement((0, 0), ONE)
        assert not validator.validate_item_placement((3, 1), ONE)

    def test_items_cannot_overlap(self):
        """Test that items cannot overlap each other"""
        validator = PlacementValidator()

        # Add a container orchestrator
        validator.add_container(
            Container.of("container_orchestrator", (1, 1), "container1")
        )

        # Place first item
        assert validator.place_item((1, 1), ONE)

        # Try to place overlapping item
        assert not validator.place_item((1, 1), ONE)  # Same position

        # Place non-overlapping item
        assert validator.place_item((2, 1), ONE)

    def test_multi_square_items_on_servers(self):
        """Test that multi-square items work with servers"""
        validator = PlacementValidator()

        # Add a container orchestrator (3x2, 6 slots)
        validator.add_container(
            Container.of("container_orchestrator", (1, 1), "container1")
        )

        # Place a 2x2 item
        assert validator.validate_item_placement((1, 1), TWO_BY_TWO)
        assert validator.place_item((1, 1), TWO_BY_TWO)

        # Try to place overlapping 2x2 item
        assert not validator.validate_item_placement(
            (2, 2), TWO_BY_TWO
        )  # Would overlap

        # Place non-overlapping item
        # Container orchestrator is at (1,1) and is 3x2, so it covers (1,1) to (3,2)
        # Item at (1,1) occupies (1,1), (2,1), (1,2), (2,2)
        # So we can place at (3,1) which is still inside the container
        assert validator.validate_item_placement((3, 1), ONE)

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
        assert validator.validate_item_placement((1, 0), THREE_WIDE)

        # Get containers for this item
        containers_touched = validator.get_containers_for_item((1, 0), THREE_WIDE)
        assert len(containers_touched) == 2  # Item spans both containers

    def test_non_rectangular_container_covers_only_its_shape(self):
        """A container offers the squares of its shape, and no others"""
        validator = PlacementValidator()

        # An L shape covers (0,0), (0,1) and (1,1) of its 2x2 bounding box.
        # No catalogue container is an L yet, so this is one that has been bent
        # into the shape the test is about.
        validator.add_container(
            Container.of("standard_vm", (1, 1), "l1").model_copy(
                update={"shape": AN_L.squares}
            )
        )

        assert validator.validate_item_placement((1, 1), ONE)
        assert validator.validate_item_placement((1, 2), ONE)
        assert validator.validate_item_placement((2, 2), ONE)

        # The fourth square of the bounding box is not part of the shape
        assert not validator.validate_item_placement((2, 1), ONE)

    def test_battle_with_containers(self):
        """Test that battle engine validates with containers"""
        sim = BattleSimulator(seed=12345)

        # A blade covers two squares and a Core Dumper is a four square L, so
        # they want more room than one 2x2 VM.
        vm1 = Container.of("mesh_network_hub", (1, 1), "p1_hub")

        p1_items = [
            BattleItem(
                spec=ITEM_CATALOG["null_blade"],
                position=(1, 1),
                uid="item1",
            ),
            BattleItem(
                spec=ITEM_CATALOG["core_dumper"],
                position=(2, 1),
                uid="item2",
            ),
        ]

        p2_items = [
            BattleItem(
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


class TestATurnedContainerCoversItsTurnedSquares:
    """
    A container covers different squares once it is turned, so everything that
    asks which squares it holds has to ask it, never its shape.
    """

    def test_a_turn_moves_the_squares_it_covers(self):
        # memory_cache is one wide and three tall, as its Stamina Sack is.
        upright = Container.of("memory_cache", (2, 3), "c1")
        assert sorted(upright.covered_squares()) == [(2, 3), (2, 4), (2, 5)]

        turned = upright.model_copy(update={"rotation": Rotation.CLOCKWISE_90})
        assert sorted(turned.covered_squares()) == [(2, 3), (3, 3), (4, 3)]

    def test_the_validator_sees_the_turn(self):
        validator = PlacementValidator()
        # Upright it stands in one column, so column 7 holds it. Turned it lies
        # three wide and reaches column 9, which the grid does not have.
        turned = Container.of("memory_cache", (7, 3), "c1").model_copy(
            update={"rotation": Rotation.CLOCKWISE_90}
        )
        assert not validator.add_container(turned), "It hangs off the right"
        assert validator.add_container(
            Container.of("memory_cache", (7, 3), "c2")
        ), "Upright it fits in the column"

    def test_two_containers_can_share_a_row_once_one_is_turned(self):
        validator = PlacementValidator()
        assert validator.add_container(Container.of("memory_cache", (2, 3), "flat"))

        # Turned, it stands in a single column and clears the flat one.
        turned = Container.of("memory_cache", (6, 2), "tall").model_copy(
            update={"rotation": Rotation.CLOCKWISE_90}
        )
        assert validator.add_container(turned)
