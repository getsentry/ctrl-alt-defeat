"""
Common utilities for tests
"""

from server_containers import ServerContainer, create_server_containers


def get_test_containers():
    """Get standard test containers for both players"""
    containers = create_server_containers()
    vm = containers["standard_vm"]

    # Player 1 gets a standard VM at (0,0) - 2x2 container
    p1_container = ServerContainer(
        spec=vm["spec"],
        position=(0, 0),
        uid="p1_test_vm",
        shape=vm["spec"].shape,
    )

    # Player 2 gets a standard VM at (4,0) - 2x2 container
    p2_container = ServerContainer(
        spec=vm["spec"],
        position=(4, 0),
        uid="p2_test_vm",
        shape=vm["spec"].shape,
    )

    return [p1_container], [p2_container]


def get_large_test_containers():
    """Get larger test containers for tests that need more space"""
    containers = create_server_containers()
    orchestrator = containers["container_orchestrator"]

    # Player 1 gets a container orchestrator at (0,0) - 3x2 container (6 slots)
    p1_container = ServerContainer(
        spec=orchestrator["spec"],
        position=(0, 0),
        uid="p1_test_orchestrator",
        shape=orchestrator["spec"].shape,
    )

    # Player 2 gets a container orchestrator at (3,0)
    p2_container = ServerContainer(
        spec=orchestrator["spec"],
        position=(3, 0),
        uid="p2_test_orchestrator",
        shape=orchestrator["spec"].shape,
    )

    return [p1_container], [p2_container]


def get_battle_containers():
    """Get containers that cover all positions used in battles and AI"""
    containers = create_server_containers()
    vm = containers["standard_vm"]

    def make_container(position, uid):
        return ServerContainer(
            spec=vm["spec"],
            position=position,
            uid=uid,
            shape=vm["spec"].shape,
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
