"""
Common utilities for tests
"""
from containers import Container


def get_test_containers():
    """A quiet rack for each player: four plain VMs, four squares by four.

    One 3x3 bag used to stand here. Every bag in the catalogue carries a
    clause now and that one amplifies its owner's healing by 12%, which every
    healing test would otherwise have to allow for. Four standard_vm cover the
    same ground and further, and say nothing at all.
    """
    return (
        [
            Container.of("standard_vm", (0, 0), "p1_test_rack_a"),
            Container.of("standard_vm", (2, 0), "p1_test_rack_b"),
            Container.of("standard_vm", (0, 2), "p1_test_rack_c"),
            Container.of("standard_vm", (2, 2), "p1_test_rack_d"),
        ],
        [
            Container.of("standard_vm", (4, 0), "p2_test_rack_a"),
            Container.of("standard_vm", (6, 0), "p2_test_rack_b"),
            Container.of("standard_vm", (4, 2), "p2_test_rack_c"),
            Container.of("standard_vm", (6, 2), "p2_test_rack_d"),
        ],
    )


def get_large_test_containers():
    """Eight squares each, four wide and two deep, and nothing to say.

    A Holdall used to stand here, six squares of it. It gives its owner Block
    for every Neutral item inside now, which is not something a test about
    anything else wants happening behind it.
    """
    return (
        [
            Container.of("standard_vm", (0, 0), "p1_test_large_a"),
            Container.of("standard_vm", (2, 0), "p1_test_large_b"),
        ],
        [
            Container.of("standard_vm", (3, 0), "p2_test_large_a"),
            Container.of("standard_vm", (5, 0), "p2_test_large_b"),
        ],
    )


def get_battle_containers():
    """Get containers that cover all positions used in battles and AI"""

    def make_container(position, container_id):
        return Container.of("standard_vm", position, container_id)

    # P1 needs containers at multiple positions for tests
    # Tests use (0,0), (1,0), (0,1), (1,1), (2,1), (1,2)
    # So we need a 3x3 area covered
    p1_containers = [
        make_container((0, 0), "p1_vm1"),
        make_container((2, 0), "p1_vm2"),
        make_container((0, 2), "p1_vm3"),
    ]

    # P2 needs containers for AI positions
    # AI uses (1,3), (2,3), (4,3), (5,3), (1,4), (2,4), (4,4), (5,4)
    # Also tests use (4,0), (5,0), (4,1), (5,1), (4,2)
    p2_containers = [
        make_container((4, 0), "p2_vm1"),
        make_container((4, 2), "p2_vm2"),
        make_container((1, 3), "p2_vm3"),
        make_container((3, 3), "p2_vm4"),
        make_container((5, 3), "p2_vm5"),
    ]

    return p1_containers, p2_containers
