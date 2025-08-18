#!/bin/bash

echo "======================================"
echo "   SENTRY AUTOBATTLER TEST SUITE"
echo "======================================"
echo ""

# Check if server is running
echo "1. Checking server status..."
if lsof -i :8000 | grep -q LISTEN; then
    echo "✓ Server is running on port 8000"
else
    echo "✗ Server not running. Starting server..."
    cd server && python main.py &
    SERVER_PID=$!
    sleep 3
    echo "Server started with PID: $SERVER_PID"
fi

echo ""
echo "2. Running Python integration tests..."
echo "--------------------------------------"
python test_integration.py
PYTHON_RESULT=$?

echo ""
echo "3. Godot tests information:"
echo "--------------------------------------"
echo "To run Godot tests:"
echo "  1. Open Godot 4.3"
echo "  2. Open the project from 'client/' directory"
echo "  3. Run the scene: tests/TestRunner.tscn"
echo ""
echo "Or from command line (if Godot is in PATH):"
echo "  godot --path client/ --script tests/TestRunner.gd"
echo ""

echo "======================================"
echo "   TEST SUMMARY"
echo "======================================"

if [ $PYTHON_RESULT -eq 0 ]; then
    echo "✅ Python integration tests: PASSED"
else
    echo "❌ Python integration tests: FAILED"
fi

echo ""
echo "Test suite complete!"

# Return appropriate exit code
exit $PYTHON_RESULT
