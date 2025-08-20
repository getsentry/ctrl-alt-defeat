# Sentry Autobattler API Client Guide

## Authentication Flow

### Quick Start (Guest Play)
1. Call `/auth/guest` to create a guest account and get a JWT token
2. Use the token in all subsequent API calls via `Authorization: Bearer <token>` header
3. Call `/session/start` to begin a game session

### Registered Account Flow
1. Call `/auth/register` to create an account OR `/auth/login` to login
2. Use the returned token in all API calls
3. Call `/session/start` to begin a game session

## API Endpoints

### Authentication Endpoints

#### `POST /auth/guest`
Create a guest account for instant play.

**Request:** No body required

**Response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user_id": 123,
  "username": "Guest_a1b2c3d4_1234"
}
```

**Client Usage:**
```javascript
// Store the token for all future requests
const response = await fetch('http://localhost:8000/auth/guest', {
  method: 'POST'
});
const data = await response.json();
localStorage.setItem('auth_token', data.access_token);
localStorage.setItem('user_id', data.user_id);
```

#### `POST /auth/register`
Register a permanent account.

**Request:**
```json
{
  "username": "player123",
  "password": "securepassword",
  "email": "player@example.com",  // optional
  "display_name": "Player 123"     // optional
}
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

#### `POST /auth/login`
Login to existing account.

**Request:**
```json
{
  "username": "player123",
  "password": "securepassword"
}
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

#### `GET /auth/me`
Get current user information.

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "user_id": 123,
  "username": "player123",
  "display_name": "Player 123",
  "account_type": "registered",
  "total_games": 42,
  "wins": 20,
  "losses": 22,
  "rank": 1050
}
```

#### `POST /auth/upgrade-guest`
Convert a guest account to permanent account.

**Headers:** `Authorization: Bearer <token>`

**Request:**
```json
{
  "username": "newusername",
  "password": "securepassword",
  "email": "player@example.com",  // optional
  "display_name": "Player Name"    // optional
}
```

### Game Session Endpoints

#### `POST /session/start`
Start a new game session. **Requires authentication.**

**Headers:** `Authorization: Bearer <token>`

**Request:**
```json
{
  "player_name": "Player Name",
  "seed": 12345  // Optional, only in TEST_MODE
}
```

**Response:**
```json
{
  "player_id": "123",  // This is your user_id as string
  "session": {
    "player_id": "123",
    "player_name": "Player Name",
    "round": 1,
    "gold": 12,
    "lives": 5,
    // ... other session data
  },
  "item_catalog": {
    // ... item definitions
  }
}
```

#### `GET /session/{player_id}`
Get current session state.

**Headers:** `Authorization: Bearer <token>` (optional but recommended)

#### `POST /shop/refresh`
Refresh shop items (costs 1 gold).

**Headers:** `Authorization: Bearer <token>` (optional but recommended)

**Request:**
```json
{
  "player_id": "123"
}
```

#### `POST /battle/simulate`
Run a battle simulation.

**Headers:** `Authorization: Bearer <token>` (optional but recommended)

**Request:**
```json
{
  "player_id": "123",
  "round_number": 1
}
```

## Client Implementation Example (Godot)

```gdscript
# BattleServerAPI.gd

var auth_token: String = ""
var user_id: int = 0

func start_guest_session():
    # Step 1: Get guest account
    var url = BASE_URL + "/auth/guest"
    var headers = ["Content-Type: application/json"]

    http_request.request(url, headers, HTTPClient.METHOD_POST, "")
    var result = await http_request.request_completed

    if result[1] == 200:
        var json = JSON.new()
        json.parse(result[3].get_string_from_utf8())
        var data = json.data

        # Store auth info
        auth_token = data["access_token"]
        user_id = data["user_id"]

        # Step 2: Start game session
        await start_game_session()

func start_game_session():
    var url = BASE_URL + "/session/start"
    var headers = [
        "Content-Type: application/json",
        "Authorization: Bearer " + auth_token
    ]

    var body = JSON.stringify({
        "player_name": "Player"
    })

    http_request.request(url, headers, HTTPClient.METHOD_POST, body)
    var result = await http_request.request_completed

    if result[1] == 200:
        # Parse and use session data
        var json = JSON.new()
        json.parse(result[3].get_string_from_utf8())
        return json.data

# For all other API calls, include the auth header
func make_api_call(endpoint: String, method: int, body_dict: Dictionary = {}):
    var url = BASE_URL + endpoint
    var headers = [
        "Content-Type: application/json",
        "Authorization: Bearer " + auth_token
    ]

    var body = JSON.stringify(body_dict) if body_dict else ""
    http_request.request(url, headers, method, body)
    return await http_request.request_completed
```

## Important Notes

1. **Token Storage**: Store the JWT token securely on the client and include it in all API requests
2. **Token Expiration**: Tokens expire after 90 days. When expired, create a new guest account or login again
3. **User ID**: The `player_id` in game sessions is the user's ID. Use this for all game-related API calls
4. **Guest to Registered**: Guest accounts can be upgraded to registered accounts without losing progress
5. **Error Handling**: Always check for 401 Unauthorized responses and re-authenticate if needed

## Migration from Old API

If you're currently using the API without authentication:

1. Add a call to `/auth/guest` at app startup
2. Store the returned token
3. Add `Authorization: Bearer <token>` header to all API calls
4. `/session/start` now REQUIRES authentication - no guest creation logic
5. The `player_id` returned is now always the user's ID
