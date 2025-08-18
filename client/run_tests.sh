#!/bin/bash

echo "Running Autobattler Tests..."
echo ""

# Run the test runner scene which will execute all tests
godot --headless scenes/TestRunner.tscn --quit

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ All tests passed!"
    exit 0
else
    echo ""
    echo "❌ Some tests failed!"
    exit 1
fi
