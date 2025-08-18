#!/bin/bash

echo "================================"
echo "   UNIFIED GRID UI TESTS"
echo "================================"

# Run Godot tests
godot --headless --script tests/test_unified_grid_ui.gd --quit 2>&1 | grep -v "^Godot Engine"

# Check if UI loads
echo ""
echo "Testing UI Loading..."
OUTPUT=$(godot --headless --quit 2>&1)
if echo "$OUTPUT" | grep -q "UnifiedGridUI starting"; then
    echo "✅ UI loads successfully"
else
    echo "❌ UI failed to load"
    exit 1
fi

echo ""
echo "================================"
echo "        TESTS COMPLETE"
echo "================================"
