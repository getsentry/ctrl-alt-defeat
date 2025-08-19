#!/bin/bash
# Run all client tests

echo "Running Godot Client Tests..."
echo "=============================="

# Check if Godot is available
if ! command -v godot &> /dev/null; then
    echo "Error: Godot is not installed or not in PATH"
    exit 1
fi

# Run tests in headless mode
godot --headless --script res://test/run_all_tests.gd

# Capture exit code
EXIT_CODE=$?

echo ""
echo "=============================="
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ All tests passed!"
else
    echo "❌ Some tests failed (exit code: $EXIT_CODE)"
fi

exit $EXIT_CODE
