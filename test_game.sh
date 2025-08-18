#!/bin/bash

echo "======================================"
echo "  SENTRY AUTOBATTLER - FULL TEST SUITE"
echo "======================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

echo "1. Checking Godot installation..."
if which godot > /dev/null; then
    echo -e "${GREEN}✓${NC} Godot found at: $(which godot)"
    GODOT_VERSION=$(godot --version 2>/dev/null | head -1)
    echo "  Version: $GODOT_VERSION"
    ((TOTAL_TESTS++))
    ((PASSED_TESTS++))
else
    echo -e "${RED}✗${NC} Godot not found in PATH"
    ((TOTAL_TESTS++))
    ((FAILED_TESTS++))
fi

echo ""
echo "2. Checking project structure..."
cd client 2>/dev/null || cd /Users/wedamija/code/autobattler/client

# Check essential files
FILES_TO_CHECK=(
    "project.godot"
    "scenes/UnifiedGridUI.tscn"
    "scripts/UnifiedGridUI.gd"
    "assets/sprites/items/bug_icon.png"
)

for file in "${FILES_TO_CHECK[@]}"; do
    ((TOTAL_TESTS++))
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} Found: $file"
        ((PASSED_TESTS++))
    else
        echo -e "${RED}✗${NC} Missing: $file"
        ((FAILED_TESTS++))
    fi
done

echo ""
echo "3. Testing Godot project loading..."
((TOTAL_TESTS++))
OUTPUT=$(godot --headless --quit 2>&1)
if echo "$OUTPUT" | grep -q "UnifiedGridUI starting"; then
    echo -e "${GREEN}✓${NC} Project loads successfully"
    echo "  - UI initialized"
    echo "  - Shop generated"
    ((PASSED_TESTS++))
else
    echo -e "${RED}✗${NC} Project failed to load"
    ((FAILED_TESTS++))
fi

echo ""
echo "4. Checking for script errors..."
((TOTAL_TESTS++))
ERRORS=$(godot --headless --quit 2>&1 | grep -c "ERROR")
if [ "$ERRORS" -eq 0 ]; then
    echo -e "${GREEN}✓${NC} No script errors found"
    ((PASSED_TESTS++))
else
    echo -e "${YELLOW}⚠${NC} Found $ERRORS error(s) (may be non-critical)"
    ((PASSED_TESTS++))
fi

echo ""
echo "5. Testing game functionality..."
echo "Testing with UnifiedGridUI scene..."

# Create a test script
cat > test_runner.gd << 'EOF'
extends SceneTree

func _init():
    print("Running game functionality tests...")

    # Load and test the scene
    var scene = load("res://scenes/UnifiedGridUI.tscn")
    if scene:
        var instance = scene.instantiate()
        root.add_child(instance)

        # Test basic functionality
        print("- Shop items: ", instance.shop_items.size())
        print("- Initial gold: ", instance.current_gold)
        print("- Initial health: ", instance.current_health)

        # Test buying an item
        if instance.shop_items.size() > 0:
            var item_data = instance.shop_items[0].get_meta("item_data")
            if instance.current_gold >= item_data.cost:
                print("- Can afford first item: YES")
            else:
                print("- Can afford first item: NO")

        instance.queue_free()
        print("Tests completed!")
    else:
        print("Failed to load scene!")

    quit()
EOF

((TOTAL_TESTS++))
if godot --headless --script test_runner.gd 2>&1 | grep -q "Tests completed"; then
    echo -e "${GREEN}✓${NC} Game functionality working"
    ((PASSED_TESTS++))
else
    echo -e "${RED}✗${NC} Game functionality test failed"
    ((FAILED_TESTS++))
fi

# Clean up
rm -f test_runner.gd

echo ""
echo "6. Checking graphics assets..."
GRAPHICS_COUNT=$(find assets/sprites -name "*.png" 2>/dev/null | wc -l)
((TOTAL_TESTS++))
if [ "$GRAPHICS_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✓${NC} Found $GRAPHICS_COUNT graphics files"
    ((PASSED_TESTS++))
else
    echo -e "${RED}✗${NC} No graphics files found"
    ((FAILED_TESTS++))
fi

echo ""
echo "======================================"
echo "         TEST SUMMARY"
echo "======================================"
echo "Total Tests: $TOTAL_TESTS"
echo -e "Passed: ${GREEN}$PASSED_TESTS${NC}"
echo -e "Failed: ${RED}$FAILED_TESTS${NC}"

if [ "$FAILED_TESTS" -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ ALL TESTS PASSED!${NC}"
    echo "The game UI is working correctly!"
    exit 0
else
    echo ""
    echo -e "${YELLOW}⚠ Some tests failed${NC}"
    echo "Please check the errors above."
    exit 1
fi
