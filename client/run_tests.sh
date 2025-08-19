#!/bin/bash
# Run all client tests

echo "Running Godot Client Tests..."
echo "=============================="

# Check if Godot is available
if ! command -v godot &> /dev/null; then
    echo "Error: Godot is not installed or not in PATH"
    exit 1
fi

# Run unit tests
echo ""
echo "Running Unit Tests..."
echo "--------------------"
godot --headless --script addons/gut/gut_cmdln.gd \
    -gdir=res://test/unit \
    -gexit \
    -glog=1

UNIT_EXIT_CODE=$?

# Run integration tests
echo ""
echo "Running Integration Tests..."
echo "---------------------------"
godot --headless --script addons/gut/gut_cmdln.gd \
    -gdir=res://test/integration \
    -gexit \
    -glog=1

INTEGRATION_EXIT_CODE=$?

# Determine overall exit code
if [ $UNIT_EXIT_CODE -ne 0 ] || [ $INTEGRATION_EXIT_CODE -ne 0 ]; then
    EXIT_CODE=1
else
    EXIT_CODE=0
fi

echo ""
echo "=============================="
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ All tests passed!"
else
    echo "❌ Some tests failed (exit code: $EXIT_CODE)"
fi

exit $EXIT_CODE
