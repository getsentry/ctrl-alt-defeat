"""Tests for auth_endpoints.py"""

import os
import uuid

os.environ["TEST_MODE"] = "true"

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402
from name_generator import MAX_NAME_LENGTH, name_error  # noqa: E402


def fresh_name(prefix: str = "Name") -> str:
    """A name no earlier test run has claimed.

    These tests share one database with every run before them, and a name is
    kept for good, so a fixed name works once and then fails.
    """
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def new_guest(client):
    """A fresh guest account. Returns its token and its name."""
    response = client.post("/auth/guest")
    assert response.status_code == 200
    body = response.json()
    return body["access_token"], body["username"]


def as_guest(client):
    """Headers for a fresh guest account, and the name it was given."""
    token, name = new_guest(client)
    return {"Authorization": f"Bearer {token}"}, name


class TestGuestNames:
    def test_a_guest_is_given_a_legal_name(self):
        with TestClient(app) as client:
            _, name = new_guest(client)
            assert name_error(name) is None

    def test_an_empty_json_body_is_accepted(self):
        """The client posts an empty body, not no body. Both must work."""
        with TestClient(app) as client:
            response = client.post(
                "/auth/guest", content="", headers={"Content-Type": "application/json"}
            )
            assert response.status_code == 200
            assert name_error(response.json()["username"]) is None

    def test_guests_are_not_all_called_the_same_thing(self):
        """A generated name has to be a name, not a placeholder."""
        with TestClient(app) as client:
            names = {new_guest(client)[1] for _ in range(8)}
            assert len(names) > 1


class TestChangeName:
    def test_a_name_can_be_changed(self):
        with TestClient(app) as client:
            headers, _ = as_guest(client)

            wanted = fresh_name("Walker")
            response = client.post("/auth/name", json={"name": wanted}, headers=headers)
            assert response.status_code == 200
            assert response.json()["username"] == wanted

            me = client.get("/auth/me", headers=headers)
            assert me.json()["username"] == wanted

    def test_the_new_token_carries_the_new_name(self):
        """The name is in the token, so a stale token would show the old one."""
        with TestClient(app) as client:
            headers, _ = as_guest(client)

            wanted = fresh_name("Token")
            response = client.post("/auth/name", json={"name": wanted}, headers=headers)
            fresh = {"Authorization": f"Bearer {response.json()['access_token']}"}

            assert client.get("/auth/me", headers=fresh).json()["username"] == wanted

    def test_surrounding_spaces_are_trimmed(self):
        with TestClient(app) as client:
            headers, _ = as_guest(client)
            wanted = fresh_name("Trim")
            response = client.post(
                "/auth/name", json={"name": f"  {wanted}  "}, headers=headers
            )
            assert response.status_code == 200
            assert response.json()["username"] == wanted

    def test_keeping_your_own_name_is_not_a_conflict(self):
        with TestClient(app) as client:
            headers, name = as_guest(client)
            response = client.post("/auth/name", json={"name": name}, headers=headers)
            assert response.status_code == 200

    def test_a_taken_name_is_refused(self):
        with TestClient(app) as client:
            wanted = fresh_name("Only")
            first, _ = as_guest(client)
            client.post("/auth/name", json={"name": wanted}, headers=first)

            second, _ = as_guest(client)
            response = client.post("/auth/name", json={"name": wanted}, headers=second)
            assert response.status_code == 409
            assert "taken" in response.json()["detail"]

    def test_letter_case_does_not_make_a_name_free(self):
        """`Dan` and `dan` on one leaderboard read as one player."""
        with TestClient(app) as client:
            wanted = fresh_name("Case")
            first, _ = as_guest(client)
            client.post("/auth/name", json={"name": wanted}, headers=first)

            second, _ = as_guest(client)
            response = client.post(
                "/auth/name", json={"name": wanted.lower()}, headers=second
            )
            assert response.status_code == 409

    def test_an_illegal_name_is_refused_with_a_reason(self):
        with TestClient(app) as client:
            headers, _ = as_guest(client)
            for bad in ["ab", "has a space", "x" * (MAX_NAME_LENGTH + 1)]:
                response = client.post(
                    "/auth/name", json={"name": bad}, headers=headers
                )
                assert response.status_code == 400, bad
                assert response.json()["detail"], bad

    def test_a_name_change_needs_a_token(self):
        with TestClient(app) as client:
            assert client.post("/auth/name", json={"name": "NoToken"}).status_code in (
                401,
                403,
            )


class TestLogin:
    def test_letter_case_does_not_matter_when_signing_in(self):
        """A player types the name they read off the screen."""
        with TestClient(app) as client:
            headers, _ = as_guest(client)
            wanted = fresh_name("Mixed")
            client.post(
                "/auth/upgrade-guest",
                json={"username": wanted, "password": "secret"},
                headers=headers,
            )

            response = client.post(
                "/auth/login",
                json={"username": wanted.lower(), "password": "secret"},
            )
            assert response.status_code == 200

    def test_a_guest_cannot_take_a_name_that_is_taken(self):
        with TestClient(app) as client:
            wanted = fresh_name("Mine")
            first, _ = as_guest(client)
            client.post(
                "/auth/upgrade-guest",
                json={"username": wanted, "password": "secret"},
                headers=first,
            )

            second, _ = as_guest(client)
            response = client.post(
                "/auth/upgrade-guest",
                json={"username": wanted.lower(), "password": "secret"},
                headers=second,
            )
            # 409, the same as /auth/name gives. A taken name is a conflict
            # wherever it is met; this endpoint used to be the odd one out.
            assert response.status_code == 409, response.text
            assert response.json()["detail"] == "That name is taken."


class TestPasswords:
    def test_a_password_round_trips(self):
        """bcrypt is called directly. A broken driver here 500s every sign-in."""
        with TestClient(app) as client:
            headers, _ = as_guest(client)
            wanted = fresh_name("Round")

            upgrade = client.post(
                "/auth/upgrade-guest",
                json={"username": wanted, "password": "correct horse"},
                headers=headers,
            )
            assert upgrade.status_code == 200

            assert (
                client.post(
                    "/auth/login",
                    json={"username": wanted, "password": "correct horse"},
                ).status_code
                == 200
            )
            assert (
                client.post(
                    "/auth/login",
                    json={"username": wanted, "password": "wrong horse"},
                ).status_code
                == 401
            )

    def test_a_short_password_is_refused_with_a_reason(self):
        with TestClient(app) as client:
            headers, _ = as_guest(client)
            response = client.post(
                "/auth/upgrade-guest",
                json={"username": fresh_name("Short"), "password": "ab"},
                headers=headers,
            )
            assert response.status_code == 400
            assert response.json()["detail"]

    def test_a_password_over_the_bcrypt_limit_is_refused_not_crashed(self):
        """bcrypt refuses more than 72 bytes. That must not reach the player."""
        with TestClient(app) as client:
            headers, _ = as_guest(client)
            response = client.post(
                "/auth/upgrade-guest",
                json={"username": fresh_name("Long"), "password": "x" * 100},
                headers=headers,
            )
            assert response.status_code == 400


class TestCheckingAName:
    """`GET /auth/name/available`, for a field that checks while it is typed."""

    def test_a_free_name_is_free(self):
        with TestClient(app) as client:
            headers, _ = as_guest(client)
            answer = client.get(
                "/auth/name/available", params={"name": fresh_name()}, headers=headers
            )
            assert answer.status_code == 200, answer.text
            assert answer.json() == {"available": True, "detail": None}

    def test_a_taken_name_is_not(self):
        with TestClient(app) as client:
            taken = fresh_name("Taken")
            first, _ = as_guest(client)
            client.post("/auth/name", json={"name": taken}, headers=first)

            second, _ = as_guest(client)
            answer = client.get(
                "/auth/name/available", params={"name": taken}, headers=second
            ).json()

            assert answer["available"] is False
            assert answer["detail"] == "That name is taken."

    def test_letter_case_does_not_free_a_name(self):
        with TestClient(app) as client:
            taken = fresh_name("Case")
            first, _ = as_guest(client)
            client.post("/auth/name", json={"name": taken}, headers=first)

            second, _ = as_guest(client)
            answer = client.get(
                "/auth/name/available", params={"name": taken.lower()}, headers=second
            ).json()

            assert answer["available"] is False

    def test_your_own_name_is_not_taken_from_you(self):
        """Renaming yourself to what you are already called is not a conflict."""
        with TestClient(app) as client:
            headers, mine = as_guest(client)

            answer = client.get(
                "/auth/name/available", params={"name": mine}, headers=headers
            ).json()

            assert answer["available"] is True

    def test_a_name_that_breaks_the_rules_says_which_rule(self):
        with TestClient(app) as client:
            headers, _ = as_guest(client)

            answer = client.get(
                "/auth/name/available",
                params={"name": "no spaces here"},
                headers=headers,
            ).json()

            assert answer["available"] is False
            assert answer["detail"] == name_error("no spaces here")

    def test_the_rules_are_checked_before_the_database(self):
        """Too short is answered without asking whether anyone holds it."""
        with TestClient(app) as client:
            headers, _ = as_guest(client)

            answer = client.get(
                "/auth/name/available", params={"name": "ab"}, headers=headers
            ).json()

            assert answer["available"] is False
            assert answer["detail"] != "That name is taken."

    def test_it_needs_an_account_to_ask_from(self):
        with TestClient(app) as client:
            answer = client.get("/auth/name/available", params={"name": "Whoever"})
            assert answer.status_code == 403
