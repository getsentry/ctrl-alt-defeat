"""
Common utilities for tests
"""
from config_loader import config_loader
from server_containers import ServerContainer


def get_test_containers():
    """Get standard test containers for both players"""
    vm = config_loader.get_container("standard_vm")

    # Player 1 gets a standard VM at (0,0) - 2x2 container
    p1_container = ServerContainer(
        spec=vm,
        position=(0, 0),
        uid="p1_test_vm",
    )

    # Player 2 gets a standard VM at (4,0) - 2x2 container
    p2_container = ServerContainer(
        spec=vm,
        position=(4, 0),
        uid="p2_test_vm",
    )

    return [p1_container], [p2_container]


def get_large_test_containers():
    """Get larger test containers for tests that need more space"""
    orchestrator = config_loader.get_container("container_orchestrator")

    # Player 1 gets a container orchestrator at (0,0) - 3x2 container (6 slots)
    p1_container = ServerContainer(
        spec=orchestrator,
        position=(0, 0),
        uid="p1_test_orchestrator",
    )

    # Player 2 gets a container orchestrator at (3,0)
    p2_container = ServerContainer(
        spec=orchestrator,
        position=(3, 0),
        uid="p2_test_orchestrator",
    )

    return [p1_container], [p2_container]


def get_battle_containers():
    """Get containers that cover all positions used in battles and AI"""
    vm = config_loader.get_container("standard_vm")

    def make_container(position, uid):
        return ServerContainer(
            spec=vm,
            position=position,
            uid=uid,
        )

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
