#!/bin/bash
# Play the game against a local server, with a shop that offers items which
# combine. For looking at GDD 5.3 by hand: the arcs, the glow, the progress
# label and the merge after a battle.
#
# Usage: ./run_demo.sh [seed]
#
# The seed fixes what the shop offers in round one. 12724 was chosen by
# searching the seeds for a shop that offers, all at once:
#
#   Hotfix Ampoule (4g) + API Token (2g)      -> Duct Tape Fix, a whole recipe,
#                                                and an item the shop sells too
#   Pointer Rifle (2g) + Schrodinger's Die (2g) -> two of the three parts of a
#                                                Flux Rifle, so a progress label
#
# All four cost 10 of the 13 gold a run starts with, so one run shows the arcs,
# the glow, the label and the merge without selling anything.

SEED="${1:-12724}"
PORT="${DEMO_PORT:-8090}"
SERVER_DIR="../server"
SERVER_LOG="demo_server.log"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

cleanup() {
    if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
        echo -e "\n${YELLOW}Stopping the demo server...${NC}"
        kill "$SERVER_PID" 2>/dev/null
    fi
}
trap cleanup EXIT INT TERM

if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    echo -e "${RED}Something is already listening on port $PORT.${NC}"
    echo "Set DEMO_PORT to another one, or stop what is there."
    exit 1
fi

echo -e "${YELLOW}Starting a server on port $PORT...${NC}"
# TEST_MODE, because only a test-mode server accepts a seed for the shop.
(cd "$SERVER_DIR" && TEST_MODE=true python main.py --port "$PORT") \
    > "$SERVER_LOG" 2>&1 &
SERVER_PID=$!

for _ in $(seq 1 30); do
    if curl -s "http://localhost:$PORT/health" > /dev/null 2>&1; then
        break
    fi
    sleep 1
done

if ! curl -s "http://localhost:$PORT/health" > /dev/null 2>&1; then
    echo -e "${RED}The server did not start. Last of $SERVER_LOG:${NC}"
    tail -20 "$SERVER_LOG"
    exit 1
fi

echo -e "${GREEN}Server is up.${NC}"
echo ""
echo "  Shop, round one (seed $SEED):"
echo "    Hotfix Ampoule 4g + API Token 2g      -> Duct Tape Fix, a whole recipe"
echo "    Pointer Rifle 2g + Schrodinger's Die 2g  -> two thirds of a Flux Rifle"
echo "    All four cost 10 of the 13 a run starts with."
echo ""
echo "  Hover or drag an item to see what it goes with, anywhere on screen."
echo "  Stand two that combine next to each other for the orange glow, then"
echo "  press Enter to fight and watch them merge as the shop comes back."
echo ""

BATTLE_SERVER_URL="http://localhost:$PORT" BATTLE_TEST_SEED="$SEED" \
    godot --path .
