#!/bin/bash
# Run tests with a real Python server
# Usage: ./run_tests.sh [test_name_pattern]
# Example: ./run_tests.sh test_shop_purchase

# --unit runs the unit tests only, which need no server. Everything goes
# through this script so that the checks at the bottom -- a script that errored,
# a script that never loaded -- are run whatever anyone typed. A raw godot
# command skips them, and a run with a broken test file looks green.
UNIT_ONLY=0
if [ "${1:-}" = "--unit" ] || [ "${1:-}" = "-u" ]; then
    UNIT_ONLY=1
    shift
fi

# Get test filter from command line argument
TEST_FILTER="${1:-}"

# Configuration
TEST_SERVER_PORT=8081
SERVER_DIR="../server"
SERVER_LOG="test_server.log"
SERVER_PID_FILE="test_server.pid"
TEST_DB_NAME="ctrl_alt_defeat_client_test"
# Seconds to let the whole run take before killing it. See the note below.
RUN_TIMEOUT="${RUN_TIMEOUT:-600}"
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
# Run all tests in one command - GUT will find all test directories.
#
# 45s per test is not because anything is slow: the slowest UI test takes 3
# seconds. It is so that a test's own wait, which gives up after 25 and says
# what it was waiting for, gets to report before GUT cuts in with a generic
# timeout.
WHERE="-gdir=res://test"
if [ "$UNIT_ONLY" = "1" ]; then
    WHERE="-gdir=res://test/unit -ginclude_subdirs=false"
fi

(
    godot --headless --script addons/gut/gut_cmdln.gd \
        $WHERE \
        -gexit \
        -glog=3 \
        -gtest_timeout=45 \
        $FILTER_ARG 2>&1 | tee test_output.tmp
) &
TEST_PID=$!

# Wait for the whole run. GUT fails any single test that runs over
# -gtest_timeout above, so this is only the backstop for a test that hangs
# without ever awaiting, which nothing inside the process can catch.
#
# This used to be 10 seconds, which killed every run before it finished and is
# most of why nobody ran this script.
SECONDS=0
while [ $SECONDS -lt $RUN_TIMEOUT ]; do
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
    echo -e "${RED}❌ Tests timed out after ${RUN_TIMEOUT} seconds${NC}"
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

# GUT's own exit code counts failed assertions and nothing else. A test that
# errors part way through is reported as "did not assert" and counted Risky; a
# whole file that will not parse is not counted at all, and the run simply has
# fewer tests in it. Both of those are a green suite that tested less than it
# says. So the output is read for them here.
if grep -q "\[Failed\]:\|FAILED:" test_output.tmp; then
    echo -e "${RED}Detected test failures in output${NC}"
    if [ $TEST_EXIT_CODE -eq 0 ]; then
        TEST_EXIT_CODE=1
    fi
fi

# A script error. Parse errors are printed under this banner too, so this is
# also what catches a test file that never loaded.
if grep -q "SCRIPT ERROR:" test_output.tmp; then
    echo -e "${RED}A test script errored. GUT counts these as Risky, not"
    echo -e "failed, so the run would otherwise pass having tested less:${NC}"
    grep -A 1 "SCRIPT ERROR:" test_output.tmp | head -20
    TEST_EXIT_CODE=1
fi

# And a file that was found but never ran. GUT says how many scripts it ran;
# anything in a suite directory that is missing from that count did not load.
#
# The suites only. test/utils holds helper classes and test/integration two
# more, all named test_* and none of them extending GutTest, so GUT ignores
# them on purpose and says so.
SUITES="test/unit test/ui test/smoke"
if [ "$UNIT_ONLY" = "1" ]; then
    SUITES="test/unit"
fi
FOUND=$(find $SUITES -maxdepth 1 -name 'test_*.gd' 2>/dev/null | wc -l | tr -d ' ')
RAN=$(grep -oE "^Scripts +[0-9]+" test_output.tmp | grep -oE "[0-9]+" | head -1)
if [ -n "$RAN" ] && [ -n "$FOUND" ] && [ "$RAN" -lt "$FOUND" ]; then
    echo -e "${RED}$RAN test scripts ran and $FOUND are on disk."
    echo -e "A script that does not load is a script that cannot fail.${NC}"
    TEST_EXIT_CODE=1
fi

# And a run that ran nothing at all. A filter that matches no test method
# leaves GUT with nothing to do, and it says so and exits 0 -- so a mistyped
# name reported a green suite that had not run a single test.
if grep -q "Nothing was run" test_output.tmp; then
    echo -e "${RED}No test ran. A run that tested nothing is not a pass;"
    echo -e "-gunit_test_name matches a test method, not a file name.${NC}"
    TEST_EXIT_CODE=1
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
