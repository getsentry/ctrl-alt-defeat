"""
Common utilities for tests
"""

from server_containers import ServerContainer, create_server_containers


def get_test_containers():
    """Get standard test containers for both players"""
    containers = create_server_containers()

    # Player 1 gets a mini rack at (0,0)
    p1_container = ServerContainer(
        spec=containers["mini_rack"]["spec"],
        position=(0, 0),
        uid="p1_test_rack",
        internal_grid_size=containers["mini_rack"]["internal_size"],
        shape=containers["mini_rack"]["external_shape"],
    )

    # Player 2 gets a mini rack at (4,0)
    p2_container = ServerContainer(
        spec=containers["mini_rack"]["spec"],
        position=(4, 0),
        uid="p2_test_rack",
        internal_grid_size=containers["mini_rack"]["internal_size"],
        shape=containers["mini_rack"]["external_shape"],
    )

    return [p1_container], [p2_container]


def get_large_test_containers():
    """Get larger test containers for tests that need more space"""
    containers = create_server_containers()

    # Player 1 gets a standard rack at (0,0) - 2x3 external
    p1_container = ServerContainer(
        spec=containers["standard_rack"]["spec"],
        position=(0, 0),
        uid="p1_test_rack",
        internal_grid_size=containers["standard_rack"]["internal_size"],
        shape=containers["standard_rack"]["external_shape"],
    )

    # Player 2 gets a standard rack at (3,0)
    p2_container = ServerContainer(
        spec=containers["standard_rack"]["spec"],
        position=(3, 0),
        uid="p2_test_rack",
        internal_grid_size=containers["standard_rack"]["internal_size"],
        shape=containers["standard_rack"]["external_shape"],
    )

    return [p1_container], [p2_container]
