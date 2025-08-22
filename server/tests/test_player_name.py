"""Test that player_name from request is used in session creation"""

import pytest
from httpx import ASGITransport, AsyncClient
from main import app


@pytest.mark.asyncio
async def test_player_name_used_from_request():
    """Test that the player_name from StartSessionRequest is actually used"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # First authenticate as guest
        auth_response = await client.post("/auth/guest")
        assert auth_response.status_code == 200
        auth_data = auth_response.json()
        token = auth_data["access_token"]

        # Start session with a custom player name
        custom_name = "TestPlayer123"
        headers = {"Authorization": f"Bearer {token}"}
        start_response = await client.post(
            "/session/start", json={"player_name": custom_name}, headers=headers
        )

        assert start_response.status_code == 200
        session_data = start_response.json()

        # Verify the session uses our custom player name
        assert session_data["session"]["player_name"] == custom_name
        assert session_data["player_name"] == custom_name


@pytest.mark.asyncio
async def test_player_name_defaults_to_user_display_name():
    """Test that player_name defaults to user display name if not provided"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # First authenticate as guest
        auth_response = await client.post("/auth/guest")
        assert auth_response.status_code == 200
        auth_data = auth_response.json()
        token = auth_data["access_token"]

        # Start session without providing player_name
        headers = {"Authorization": f"Bearer {token}"}
        start_response = await client.post(
            "/session/start",
            json={"player_name": None},  # Explicitly null player_name
            headers=headers,
        )

        assert start_response.status_code == 200
        session_data = start_response.json()

        # Should default to Player_ since no name was provided
        assert session_data["session"]["player_name"].startswith("Player_")
        assert session_data["player_name"].startswith("Player_")
