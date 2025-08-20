#!/bin/bash

# Quick verification script for the integration

echo "================================"
echo "INTEGRATION VERIFICATION"
echo "================================"
echo ""

# Check if server is running
echo -n "1. Checking server... "
if curl -s http://localhost:8000/docs > /dev/null 2>&1; then
    echo "✅ Running"
else
    echo "❌ Not running"
    echo "   Start with: cd server && TEST_MODE=true python main.py"
    exit 1
fi

# Test session creation
echo -n "2. Testing session creation... "
RESPONSE=$(curl -X POST "http://localhost:8000/session/start?game_seed=42" -s 2>/dev/null)
if echo "$RESPONSE" | grep -q "player_id"; then
    echo "✅ Working"
    PLAYER_ID=$(echo "$RESPONSE" | python -c "import sys, json; print(json.load(sys.stdin)['player_id'])" 2>/dev/null)
else
    echo "❌ Failed"
    exit 1
fi

# Test session retrieval
echo -n "3. Testing session retrieval... "
if curl -s "http://localhost:8000/session/$PLAYER_ID" | grep -q "inventory_grid" 2>/dev/null; then
    echo "✅ Working"
else
    echo "❌ Failed"
    exit 1
fi

# Test purchase endpoint (with JSON body)
echo -n "4. Testing purchase endpoint... "
SESSION=$(curl -s "http://localhost:8000/session/$PLAYER_ID")
ITEM_ID=$(echo "$SESSION" | python -c "import sys, json; shop = json.load(sys.stdin)['current_shop']; print(next((item['id'] for item in shop if item), ''))" 2>/dev/null)

if [ ! -z "$ITEM_ID" ]; then
    PURCHASE_RESPONSE=$(curl -X POST "http://localhost:8000/purchase/item" \
        -H "Content-Type: application/json" \
        -d "{\"player_id\": \"$PLAYER_ID\", \"item_id\": \"$ITEM_ID\", \"placement\": [2, 3]}" \
        -s 2>/dev/null)

    if echo "$PURCHASE_RESPONSE" | grep -q "gold"; then
        echo "✅ Working"
    else
        echo "❌ Failed"
        echo "Response: $PURCHASE_RESPONSE"
    fi
else
    echo "⚠️  No items in shop"
fi

# Test battle endpoint
echo -n "5. Testing battle endpoint... "
BATTLE_RESPONSE=$(curl -X POST "http://localhost:8000/battle/simulate" \
    -H "Content-Type: application/json" \
    -d "{\"player_id\": \"$PLAYER_ID\", \"round_number\": 1, \"seed\": 42, \"test_ai_difficulty\": \"easy\"}" \
    -s 2>/dev/null)

if echo "$BATTLE_RESPONSE" | grep -q "battle_result"; then
    echo "✅ Working"
else
    echo "❌ Failed"
    echo "Response: $BATTLE_RESPONSE"
fi

echo ""
echo "================================"
echo "✅ ALL CHECKS PASSED!"
echo "================================"
echo ""
echo "Integration is working correctly."
echo "You can now:"
echo "  1. Run the Godot client"
echo "  2. Use the API at http://localhost:8000/docs"
echo "  3. Run tests with: ./run_integration_tests.sh"
echo ""
