#!/bin/bash

echo "Running Autobattler Tests with GUT..."
echo ""

# Run GUT tests using the command line interface
godot --headless -s addons/gut/gut_cmdln.gd -gdir=res://test -gexit

# Check exit code
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "✅ All tests passed!"
    exit 0
else
    echo ""
    echo "❌ Some tests failed! (Exit code: $EXIT_CODE)"
    exit 1
fi
