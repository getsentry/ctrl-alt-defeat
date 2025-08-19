#!/bin/bash
# Run tests with a real Python server

# Configuration
TEST_SERVER_PORT=8081
SERVER_DIR="../server"
SERVER_LOG="test_server.log"
SERVER_PID_FILE="test_server.pid"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Starting test environment...${NC}"
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

# Start the Python server on test port
echo "Starting Python server on port $TEST_SERVER_PORT..."
cd "$SERVER_DIR"
python main.py --port "$TEST_SERVER_PORT" > "../client/$SERVER_LOG" 2>&1 &
SERVER_PID=$!
cd ../client

# Save PID for cleanup
echo $SERVER_PID > "$SERVER_PID_FILE"

# Wait for server to be ready
echo "Waiting for server to start..."
MAX_ATTEMPTS=30
ATTEMPT=0
while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if curl -s "http://localhost:$TEST_SERVER_PORT/health" > /dev/null 2>&1; then
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
echo "Running Godot Client Tests..."
echo "==============================="

# Export server URL for tests to use
export BATTLE_SERVER_URL="http://localhost:$TEST_SERVER_PORT"
echo "Test server URL: $BATTLE_SERVER_URL"

# Run the actual tests
./run_tests.sh

# Capture test exit code
TEST_EXIT_CODE=$?

echo ""
echo "==============================="
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed!${NC}"
else
    echo -e "${RED}❌ Some tests failed (exit code: $TEST_EXIT_CODE)${NC}"
fi

# Cleanup will happen automatically via trap
exit $TEST_EXIT_CODE
