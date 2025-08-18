"""
Common utilities for tests
"""

from server_containers import ServerContainer, create_server_containers


def get_test_containers():
    """Get standard test containers for both players"""
    containers = create_server_containers()

    # Player 1 gets a standard VM at (0,0) - 2x2 container
    p1_container = ServerContainer(
        spec=containers["standard_vm"]["spec"],
        position=(0, 0),
        uid="p1_test_vm",
        internal_grid_size=containers["standard_vm"]["internal_size"],
        shape=containers["standard_vm"]["external_shape"],
    )

    # Player 2 gets a standard VM at (4,0) - 2x2 container
    p2_container = ServerContainer(
        spec=containers["standard_vm"]["spec"],
        position=(4, 0),
        uid="p2_test_vm",
        internal_grid_size=containers["standard_vm"]["internal_size"],
        shape=containers["standard_vm"]["external_shape"],
    )

    return [p1_container], [p2_container]


def get_large_test_containers():
    """Get larger test containers for tests that need more space"""
    containers = create_server_containers()

    # Player 1 gets a container orchestrator at (0,0) - 3x2 container (6 slots)
    p1_container = ServerContainer(
        spec=containers["container_orchestrator"]["spec"],
        position=(0, 0),
        uid="p1_test_orchestrator",
        internal_grid_size=containers["container_orchestrator"]["internal_size"],
        shape=containers["container_orchestrator"]["external_shape"],
    )

    # Player 2 gets a container orchestrator at (3,0)
    p2_container = ServerContainer(
        spec=containers["container_orchestrator"]["spec"],
        position=(3, 0),
        uid="p2_test_orchestrator",
        internal_grid_size=containers["container_orchestrator"]["internal_size"],
        shape=containers["container_orchestrator"]["external_shape"],
    )

    return [p1_container], [p2_container]
