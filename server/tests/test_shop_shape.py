"""Test that shop items include shape data"""

import os

from main import generate_shop_items

os.environ["TEST_MODE"] = "true"


class TestShopShape:
    """Test that shop items include shape information"""

    def test_shop_items_have_shape(self):
        """Test that all shop items include shape data"""
        # Generate shop directly
        shop = generate_shop_items(round_number=1, seed=12345)

        assert len(shop) == 5, "Shop should have 5 items"

        for item in shop:
            if item:  # Shop can have None values for empty slots
                assert isinstance(
                    item.shape, list
                ), f"Shape should be a list for {item.name}"
                assert len(item.shape) > 0, f"{item.name} should cover a square"
                for square in item.shape:
                    assert isinstance(square, tuple), "A shape holds (x, y) pairs"
                    assert len(square) == 2, "Each offset is an (x, y) pair"

    def test_container_shapes(self):
        """Test that containers have appropriate shapes"""
        shop = generate_shop_items(
            round_number=5, seed=999
        )  # Higher round for containers

        # Find a container if any
        containers = [item for item in shop if item and item.is_container]

        if containers:
            for container in containers:
                # Standard VM is 2x2 = 4 squares
                if container.item_type == "standard_vm":
                    assert (
                        len(container.shape) == 4
                    ), "Standard VM should have 4 squares"

    def test_shop_refresh_includes_shape(self, auth_client):
        """Test that refreshed shop also includes shape data"""
        # Create a test session
        response = auth_client.post(
            "/session/start", json={}
        )
        assert response.status_code == 200

        # Refresh shop
        response = auth_client.post("/shop/refresh", json={})
        assert response.status_code == 200

        shop = response.json()["current_shop"]
        for item in shop:
            if item:
                assert (
                    "shape" in item
                ), f"Shape missing after refresh for {item['name']}"

    def test_session_start_shop_has_shapes(self, auth_client):
        """Test that initial shop from session start has shapes"""
        response = auth_client.post(
            "/session/start", json={}
        )
        assert response.status_code == 200

        session = response.json()["session"]
        shop = session["current_shop"]

        for item in shop:
            if item:
                assert "shape" in item, f"Initial shop missing shape for {item['name']}"
