#!/bin/bash

# Run integration tests for Sentry Autobattler

set -e  # Exit on error

echo "=========================================="
echo "SENTRY AUTOBATTLER INTEGRATION TESTS"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed${NC}"
    exit 1
fi

# Check if server directory exists
if [ ! -d "server" ]; then
    echo -e "${RED}❌ Server directory not found${NC}"
    echo "Please run this script from the project root"
    exit 1
fi

# Check if client directory exists
if [ ! -d "client" ]; then
    echo -e "${YELLOW}⚠ Client directory not found - skipping client tests${NC}"
    CLIENT_TESTS=false
else
    CLIENT_TESTS=true
fi

# Set test mode
export TEST_MODE=true

echo ""
echo "1. Running Server Unit Tests..."
echo "--------------------------------"
cd server
python -m pytest tests/ -v --tb=short -q
SERVER_UNIT_RESULT=$?
cd ..

if [ $SERVER_UNIT_RESULT -eq 0 ]; then
    echo -e "${GREEN}✅ Server unit tests passed${NC}"
else
    echo -e "${RED}❌ Server unit tests failed${NC}"
fi

echo ""
echo "2. Running Integration Tests..."
echo "--------------------------------"
python server_integration_test.py
INTEGRATION_RESULT=$?

if [ $INTEGRATION_RESULT -eq 0 ]; then
    echo -e "${GREEN}✅ Integration tests passed${NC}"
else
    echo -e "${RED}❌ Integration tests failed${NC}"
fi

# Run client tests if Godot is available
if [ "$CLIENT_TESTS" = true ]; then
    if command -v godot &> /dev/null; then
        echo ""
        echo "3. Running Client Tests..."
        echo "--------------------------------"
        cd client
        godot --headless --script tests/test_server_integration.gd --quit-after 100
        CLIENT_RESULT=$?
        cd ..

        if [ $CLIENT_RESULT -eq 0 ]; then
            echo -e "${GREEN}✅ Client tests passed${NC}"
        else
            echo -e "${RED}❌ Client tests failed${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ Godot not found - skipping client tests${NC}"
        echo "Install Godot to run client integration tests"
        CLIENT_RESULT=0
    fi
else
    CLIENT_RESULT=0
fi

echo ""
echo "=========================================="
echo "FINAL RESULTS"
echo "=========================================="

TOTAL_FAILURES=$((SERVER_UNIT_RESULT + INTEGRATION_RESULT + CLIENT_RESULT))

if [ $TOTAL_FAILURES -eq 0 ]; then
    echo -e "${GREEN}✅ ALL TESTS PASSED!${NC}"
    exit 0
else
    echo -e "${RED}❌ SOME TESTS FAILED${NC}"
    echo ""
    [ $SERVER_UNIT_RESULT -ne 0 ] && echo -e "${RED}  - Server unit tests failed${NC}"
    [ $INTEGRATION_RESULT -ne 0 ] && echo -e "${RED}  - Integration tests failed${NC}"
    [ $CLIENT_RESULT -ne 0 ] && echo -e "${RED}  - Client tests failed${NC}"
    exit 1
fi
