#!/bin/bash
# Run tests with a real Python server
# Usage: ./run_tests.sh [test_name_pattern]
# Example: ./run_tests.sh test_shop_purchase

# Get test filter from command line argument
TEST_FILTER="${1:-}"

# Configuration
TEST_SERVER_PORT=8081
SERVER_DIR="../server"
SERVER_LOG="test_server.log"
SERVER_PID_FILE="test_server.pid"
TEST_DB_NAME="ctrl_alt_defeat_client_test"
# Use default host (localhost:5432) unless specified
TEST_DB_HOST="${TEST_DB_HOST:-localhost:5432}"

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

# Start the Python server on test port with test database
echo "Starting Python server on port $TEST_SERVER_PORT..."
echo "Using test database: $TEST_DB_NAME on $TEST_DB_HOST"
cd "$SERVER_DIR"
# Set TEST_MODE environment variable for test-only endpoints
TEST_MODE=true python main.py --port "$TEST_SERVER_PORT" --db-host "$TEST_DB_HOST" --db-name "$TEST_DB_NAME" > "../client/$SERVER_LOG" 2>&1 &
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

# Show filter if provided
if [ -n "$TEST_FILTER" ]; then
    echo "Running tests matching: $TEST_FILTER"
else
    echo "Running all tests"
fi

# Build filter argument if provided
FILTER_ARG=""
if [ -n "$TEST_FILTER" ]; then
    FILTER_ARG="-gunit_test_name=$TEST_FILTER"
fi

# Run all test suites, passing filter
echo ""
echo "Running All Tests..."
echo "--------------------"
# Run all tests in one command - GUT will find all test directories
# Use background process with timeout to prevent hanging tests
(
    godot --headless --script addons/gut/gut_cmdln.gd \
        -gdir=res://test \
        -gexit \
        -glog=3 \
        $FILTER_ARG 2>&1 | tee test_output.tmp
) &
TEST_PID=$!

# Wait for up to 10 seconds
SECONDS=0
while [ $SECONDS -lt 10 ]; do
    if ! kill -0 $TEST_PID 2>/dev/null; then
        # Process finished
        wait $TEST_PID
        TEST_EXIT_CODE=$?
        break
    fi
    sleep 0.1
done

# If still running after 10 seconds, kill it
if kill -0 $TEST_PID 2>/dev/null; then
    echo -e "${RED}❌ Tests timed out after 10 seconds${NC}"
    kill -TERM $TEST_PID 2>/dev/null
    wait $TEST_PID 2>/dev/null
    TEST_EXIT_CODE=124
else
    # Get the exit code if we didn't already
    if [ -z "$TEST_EXIT_CODE" ]; then
        wait $TEST_PID
        TEST_EXIT_CODE=$?
    fi
fi

# Also check for failures in output as backup
if grep -q "\[Failed\]:\|SCRIPT ERROR:\|FAILED:" test_output.tmp; then
    echo "Detected test failures or errors in output"
    if [ $TEST_EXIT_CODE -eq 0 ]; then
        TEST_EXIT_CODE=1
    fi
fi

# Clean up temp file
rm -f test_output.tmp

# Exit code is already set from the single test run

echo ""
echo "==============================="
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed!${NC}"
else
    echo -e "${RED}❌ Some tests failed (exit code: $TEST_EXIT_CODE)${NC}"
fi

# Cleanup will happen automatically via trap
exit $TEST_EXIT_CODE
