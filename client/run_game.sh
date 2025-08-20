#!/bin/bash
# Run the game with a real Python server for development

# Configuration
DEV_SERVER_PORT=8082
SERVER_DIR="../server"
SERVER_LOG="dev_server.log"
SERVER_PID_FILE="dev_server.pid"
DEV_DB_NAME="ctrl_alt_defeat_dev"
# Use default host (localhost:5432) unless specified
DEV_DB_HOST="${DEV_DB_HOST:-localhost:5432}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Starting development environment...${NC}"
echo "==============================="

# Function to cleanup server on exit
cleanup() {
    echo -e "\n${YELLOW}Cleaning up...${NC}"

    # Kill server if PID file exists
    if [ -f "$SERVER_PID_FILE" ]; then
        PID=$(cat "$SERVER_PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo "Stopping server (PID: $PID)..."
            kill "$PID"
            sleep 1
            # Force kill if still running
            if kill -0 "$PID" 2>/dev/null; then
                kill -9 "$PID"
            fi
        fi
        rm -f "$SERVER_PID_FILE"
    fi

    # Clean up log file
    if [ -f "$SERVER_LOG" ]; then
        echo "Server log saved to: $SERVER_LOG"
    fi
}

# Set up cleanup on script exit
trap cleanup EXIT INT TERM

# Check if server directory exists
if [ ! -d "$SERVER_DIR" ]; then
    echo -e "${RED}Error: Server directory not found at $SERVER_DIR${NC}"
    exit 1
fi

# Kill any existing server on the dev port
echo "Checking for existing server on port $DEV_SERVER_PORT..."
if lsof -i:$DEV_SERVER_PORT > /dev/null 2>&1; then
    echo "Found existing server on port $DEV_SERVER_PORT, killing it..."
    lsof -ti:$DEV_SERVER_PORT | xargs kill -9 2>/dev/null || true
    sleep 1
fi

# Start the Python server on dev port with dev database
echo "Starting Python server on port $DEV_SERVER_PORT..."
echo "Using development database: $DEV_DB_NAME on $DEV_DB_HOST"
cd "$SERVER_DIR"
python main.py --port "$DEV_SERVER_PORT" --db-host "$DEV_DB_HOST" --db-name "$DEV_DB_NAME" > "../client/$SERVER_LOG" 2>&1 &
SERVER_PID=$!
cd ../client

# Save PID for cleanup
echo $SERVER_PID > "$SERVER_PID_FILE"

# Wait for server to be ready
echo "Waiting for server to start..."
MAX_ATTEMPTS=30
ATTEMPT=0
while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if curl -s "http://localhost:$DEV_SERVER_PORT/health" > /dev/null 2>&1; then
        echo -e "${GREEN}Server is ready!${NC}"
        break
    fi
    sleep 1
    ATTEMPT=$((ATTEMPT + 1))
    echo -n "."
done

if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
    echo -e "\n${RED}Error: Server failed to start. Check $SERVER_LOG for details${NC}"
    tail -20 "$SERVER_LOG"
    exit 1
fi

echo ""
echo "==============================="
echo -e "${GREEN}Development server running on http://localhost:$DEV_SERVER_PORT${NC}"
echo "==============================="

# Export server URL for game to use
export BATTLE_SERVER_URL="http://localhost:$DEV_SERVER_PORT"
echo "Game will connect to: $BATTLE_SERVER_URL"

# Run Godot
echo ""
echo "Starting Godot..."
echo "==============================="
godot

# Cleanup will happen automatically via trap when Godot exits
