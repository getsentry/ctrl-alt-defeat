"""
ASCII Battle Renderer - Replay battles from logs in real-time
Renders the battle grid and shows actions as they happen
"""

import os
import time
from dataclasses import dataclass
from typing import Dict, List

from battle_engine import ACTION_CODES
from server_containers import ServerContainer

# Reverse action codes for display
ACTION_NAMES = {v: k for k, v in ACTION_CODES.items()}


# ANSI color codes for terminal output
class Colors:
    """ANSI color codes for terminal highlighting"""

    RESET = "\033[0m"
    BOLD = "\033[1m"

    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright foreground colors
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"

    # Background colors
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"

    @staticmethod
    def colorize(text: str, color: str) -> str:
        """Apply color to text"""
        return f"{color}{text}{Colors.RESET}"


@dataclass
class BattleState:
    """Track the current state of the battle for rendering"""

    player1_hp: int
    player1_max_hp: int
    player1_cpu: float
    player1_max_cpu: int
    player1_items: Dict[str, dict]  # uid -> item info

    player2_hp: int
    player2_max_hp: int
    player2_cpu: float
    player2_max_cpu: int
    player2_items: Dict[str, dict]

    current_time: float
    last_actions: List[str]  # Recent actions to display
    active_items: Dict[str, str] = None  # uid -> action color
    p1_containers: List = None  # Server containers for P1
    p2_containers: List = None  # Server containers for P2

    def __post_init__(self):
        if self.active_items is None:
            self.active_items = {}
        if self.p1_containers is None:
            self.p1_containers = []
        if self.p2_containers is None:
            self.p2_containers = []


class ASCIIBattleRenderer:
    """Render battle replays in ASCII art"""

    def __init__(self, width: int = 80, height: int = 30):
        self.width = width
        self.height = height
        self.clear_screen = "cls" if os.name == "nt" else "clear"

    def render_battle(
        self,
        battle_result: Dict,
        p1_items: List,
        p2_items: List,
        real_time: bool = True,
        speed: float = 1.0,
        p1_containers: List = None,
        p2_containers: List = None,
    ):
        """
        Render a battle replay from results

        Args:
            battle_result: Result dict from BattleSimulator.simulate_battle
            p1_items: Player 1's items
            p2_items: Player 2's items
            real_time: If True, play in real-time. If False, step through
            speed: Playback speed multiplier (2.0 = 2x speed)
        """
        # Initialize battle state
        state = BattleState(
            player1_hp=battle_result.get("player1_quota_start", 25),
            player1_max_hp=battle_result.get("player1_quota_start", 25),
            player1_cpu=10.0,
            player1_max_cpu=10,
            player1_items={
                item.uid: {
                    "name": item.spec.name,
                    "position": item.position,
                    "active": False,
                }
                for item in p1_items
            },
            player2_hp=battle_result.get("player2_quota_start", 25),
            player2_max_hp=battle_result.get("player2_quota_start", 25),
            player2_cpu=10.0,
            player2_max_cpu=10,
            player2_items={
                item.uid: {
                    "name": item.spec.name,
                    "position": item.position,
                    "active": False,
                }
                for item in p2_items
            },
            current_time=0.0,
            last_actions=[],
            p1_containers=p1_containers or [],
            p2_containers=p2_containers or [],
        )

        # Store containers in state for rendering
        state.p1_containers = p1_containers or []
        state.p2_containers = p2_containers or []

        actions = battle_result.get("actions", [])

        if real_time:
            self._render_real_time(state, actions, speed)
        else:
            self._render_step_by_step(state, actions)

    def _render_real_time(self, state: BattleState, actions: List[Dict], speed: float):
        """Render the battle in real-time"""
        start_time = time.time()
        action_index = 0

        while action_index < len(actions) or state.current_time < 60:
            current_real_time = (time.time() - start_time) * speed

            # Process all actions up to current time
            while action_index < len(actions):
                action = actions[action_index]
                if action["t"] <= current_real_time:
                    self._process_action(state, action)
                    action_index += 1
                else:
                    break

            state.current_time = current_real_time

            # Render current state
            self._render_frame(state)

            # Small delay for smooth animation
            time.sleep(0.05 / speed)

            # Check if battle is over
            if (
                action_index >= len(actions)
                and current_real_time > actions[-1]["t"] + 1
            ):
                break

        # Show final state
        print("\n" + "=" * self.width)
        print(f"BATTLE ENDED - Winner: Player {state.player1_hp > 0 and 1 or 2}")
        print("=" * self.width)

    def _render_step_by_step(self, state: BattleState, actions: List[Dict]):
        """Render the battle step by step with user input"""
        for i, action in enumerate(actions):
            self._process_action(state, action)
            state.current_time = action["t"]
            self._render_frame(state)

            print(
                f"\nAction {i+1}/{len(actions)} - Press Enter for next, 'q' to quit: ",
                end="",
            )
            user_input = input()
            if user_input.lower() == "q":
                break

    def _process_action(self, state: BattleState, action: Dict):
        """Update state based on action"""
        action_type = ACTION_NAMES.get(action["a"], action["a"])

        # Clear previous active items (they fade after one frame)
        state.active_items.clear()

        # Build action description
        desc = f"[{action['t']:.1f}s] {action_type}"

        item_uid = action.get("i")
        if "p" in action:
            desc += f" P{action['p']}"
        if item_uid:
            item_name = self._get_item_name(state, item_uid)
            desc += f" {item_name}"
        if "v" in action:
            desc += f" ({action['v']})"

        # Update state and set item colors based on action type
        if action["a"] == ACTION_CODES["DAMAGE"]:
            if action["p"] == 1:
                state.player1_hp -= action.get("v", 0)
            else:
                state.player2_hp -= action.get("v", 0)
            desc = Colors.colorize(f"💥 {desc}", Colors.BRIGHT_RED)
            if item_uid:
                state.active_items[item_uid] = Colors.BRIGHT_RED

        elif action["a"] == ACTION_CODES["HEAL"]:
            if action["p"] == 1:
                state.player1_hp = min(
                    state.player1_max_hp, state.player1_hp + action.get("v", 0)
                )
            else:
                state.player2_hp = min(
                    state.player2_max_hp, state.player2_hp + action.get("v", 0)
                )
            desc = Colors.colorize(f"💚 {desc}", Colors.BRIGHT_GREEN)
            if item_uid:
                state.active_items[item_uid] = Colors.BRIGHT_GREEN

        elif action["a"] == ACTION_CODES["BLOCK"]:
            desc = Colors.colorize(f"🛡️ {desc}", Colors.BRIGHT_CYAN)
            if item_uid:
                state.active_items[item_uid] = Colors.BRIGHT_CYAN

        elif action["a"] == ACTION_CODES["CPU_FAIL"]:
            desc = Colors.colorize(f"⚠️ {desc}", Colors.YELLOW)
            if item_uid:
                state.active_items[item_uid] = Colors.YELLOW

        elif action["a"] == ACTION_CODES["ACTIVATE"]:
            desc = Colors.colorize(f"⚡ {desc}", Colors.BRIGHT_YELLOW)
            if item_uid:
                state.active_items[item_uid] = Colors.BRIGHT_YELLOW

        elif action["a"] == ACTION_CODES["CRIT"]:
            desc = Colors.colorize(f"💥 CRIT! {desc}", Colors.BRIGHT_MAGENTA)
            if item_uid:
                state.active_items[item_uid] = Colors.BRIGHT_MAGENTA

        elif action["a"] == ACTION_CODES["MISS"]:
            desc = Colors.colorize(f"✗ {desc}", Colors.WHITE)
            if item_uid:
                state.active_items[item_uid] = Colors.WHITE

        # Add to recent actions (keep last 5)
        state.last_actions.append(desc)
        if len(state.last_actions) > 5:
            state.last_actions.pop(0)

    def _get_item_name(self, state: BattleState, uid: str) -> str:
        """Get item name from uid"""
        if uid in state.player1_items:
            return state.player1_items[uid]["name"]
        elif uid in state.player2_items:
            return state.player2_items[uid]["name"]
        return uid

    def _render_frame(self, state: BattleState):
        """Render a single frame of the battle"""
        os.system(self.clear_screen)

        print("=" * self.width)
        print(f"{'BATTLE REPLAY':^{self.width}}")
        print(f"{'Time: ' + f'{state.current_time:.1f}s':^{self.width}}")
        print("=" * self.width)

        # Player stats
        self._render_player_stats(state)

        print("-" * self.width)

        # Items grid (simplified)
        self._render_items_grid(state)

        print("-" * self.width)

        # Recent actions
        print("Recent Actions:")
        for action in state.last_actions:
            print(f"  {action}")

        print("=" * self.width)

    def _render_player_stats(self, state: BattleState):
        """Render player health and CPU bars"""
        # Player 1
        hp_bar1 = self._make_bar(state.player1_hp, state.player1_max_hp, 20, "█", "░")
        cpu_bar1 = self._make_bar(
            int(state.player1_cpu), state.player1_max_cpu, 10, "▓", "░"
        )

        # Player 2
        hp_bar2 = self._make_bar(state.player2_hp, state.player2_max_hp, 20, "█", "░")
        cpu_bar2 = self._make_bar(
            int(state.player2_cpu), state.player2_max_cpu, 10, "▓", "░"
        )

        # Display
        p1_text = f"Player 1: HP {hp_bar1} {state.player1_hp:3}/{state.player1_max_hp}"
        p2_text = f"Player 2: HP {hp_bar2} {state.player2_hp:3}/{state.player2_max_hp}"

        print(f"{p1_text:<39} | {p2_text:>39}")

        p1_cpu = (
            f"         CPU {cpu_bar1} {state.player1_cpu:.0f}/{state.player1_max_cpu}"
        )
        p2_cpu = (
            f"         CPU {cpu_bar2} {state.player2_cpu:.0f}/{state.player2_max_cpu}"
        )

        print(f"{p1_cpu:<39} | {p2_cpu:>39}")

    def _make_bar(
        self,
        current: int,
        maximum: int,
        length: int,
        filled: str = "█",
        empty: str = "░",
    ) -> str:
        """Create a progress bar"""
        if maximum <= 0:
            return empty * length

        filled_length = int(length * current / maximum)
        return filled * filled_length + empty * (length - filled_length)

    def _render_items_grid(self, state: BattleState):
        """Render item grids with visual representation"""
        # Create visual grids for both players
        self._render_visual_grid(state)

    def _render_visual_grid(self, state: BattleState):
        """Render visual grid representation with containers and colored active items"""
        # Create 7x9 main grid
        grid_width, grid_height = 7, 9

        print("\n" + "─" * 50)
        print(Colors.colorize("PLAYER 1 GRID (with Server Racks):", Colors.BOLD))

        # Build grid
        p1_grid = [[" " for _ in range(grid_width)] for _ in range(grid_height)]
        p1_colors = [[None for _ in range(grid_width)] for _ in range(grid_height)]
        p1_types = [
            [None for _ in range(grid_width)] for _ in range(grid_height)
        ]  # Track what's in each cell

        # First, render containers (servers) - they provide the space
        if hasattr(state, "p1_containers"):
            for container in state.p1_containers:
                if hasattr(container, "get_occupied_squares"):
                    for x, y in container.get_occupied_squares():
                        if 0 <= x < grid_width and 0 <= y < grid_height:
                            p1_grid[y][x] = "▓"  # Server rack character
                            p1_types[y][x] = "container"
                            p1_colors[y][x] = Colors.GREEN  # Servers are green

        # Then render items on top of containers
        # Items should have position data - use it if available
        for uid, item_info in state.player1_items.items():
            # Try to get position from item info
            if hasattr(item_info, "position"):
                x, y = item_info.position
            elif "position" in item_info:
                x, y = item_info["position"]
            else:
                # Fallback to default positions if no position data
                default_positions = [(0, 0), (1, 0), (0, 1), (1, 1)]
                idx = list(state.player1_items.keys()).index(uid)
                if idx < len(default_positions):
                    x, y = default_positions[idx]
                else:
                    continue

            if 0 <= x < grid_width and 0 <= y < grid_height:
                # Just render the item - validation already happened in battle engine
                char = (
                    item_info["name"][0].upper()
                    if isinstance(item_info, dict)
                    else item_info.name[0].upper()
                )
                p1_grid[y][x] = char
                p1_types[y][x] = "item"
                # Apply color if item is active
                if uid in state.active_items:
                    p1_colors[y][x] = state.active_items[uid]
                else:
                    p1_colors[y][x] = Colors.WHITE

        # Print grid with legend
        print("  " + "".join(str(i) for i in range(grid_width)))
        for y in range(grid_height):
            row_str = f"{y} "
            for x in range(grid_width):
                cell = p1_grid[y][x]
                color = p1_colors[y][x]
                cell_type = p1_types[y][x]

                if cell_type == "container" and p1_grid[y][x] == "▓":
                    # Empty server space
                    cell_str = Colors.colorize("▓", Colors.GREEN)
                elif cell_type == "item":
                    # Item on a server
                    if color:
                        cell_str = Colors.colorize(f"{cell}", color + Colors.BOLD)
                    else:
                        cell_str = f"{cell}"
                else:
                    # Empty space (no server)
                    cell_str = "·"
                row_str += cell_str + " "
            print(row_str)

        print("\nLegend: ▓=Server Rack  ·=Empty  Letters=Items")

        print("\n" + "─" * 50)
        print(Colors.colorize("PLAYER 2 GRID (with Server Racks):", Colors.BOLD))

        # Build grid
        p2_grid = [[" " for _ in range(grid_width)] for _ in range(grid_height)]
        p2_colors = [[None for _ in range(grid_width)] for _ in range(grid_height)]
        p2_types = [[None for _ in range(grid_width)] for _ in range(grid_height)]

        # First, render containers (servers)
        if hasattr(state, "p2_containers"):
            for container in state.p2_containers:
                if hasattr(container, "get_occupied_squares"):
                    for x, y in container.get_occupied_squares():
                        if 0 <= x < grid_width and 0 <= y < grid_height:
                            p2_grid[y][x] = "▓"
                            p2_types[y][x] = "container"
                            p2_colors[y][x] = Colors.GREEN

        # Then render items on containers
        for uid, item_info in state.player2_items.items():
            # Try to get position from item info
            if hasattr(item_info, "position"):
                x, y = item_info.position
            elif "position" in item_info:
                x, y = item_info["position"]
            else:
                # Fallback to default positions if no position data
                default_positions = [(4, 0), (5, 0), (4, 1), (5, 1)]
                idx = list(state.player2_items.keys()).index(uid)
                if idx < len(default_positions):
                    x, y = default_positions[idx]
                else:
                    continue

            if 0 <= x < grid_width and 0 <= y < grid_height:
                # Just render the item - validation already happened in battle engine
                char = (
                    item_info["name"][0].upper()
                    if isinstance(item_info, dict)
                    else item_info.name[0].upper()
                )
                p2_grid[y][x] = char
                p2_types[y][x] = "item"
                # Apply color if item is active
                if uid in state.active_items:
                    p2_colors[y][x] = state.active_items[uid]
                else:
                    p2_colors[y][x] = Colors.WHITE

        # Print grid
        print("  " + "".join(str(i) for i in range(grid_width)))
        for y in range(grid_height):
            row_str = f"{y} "
            for x in range(grid_width):
                cell = p2_grid[y][x]
                color = p2_colors[y][x]
                cell_type = p2_types[y][x]

                if cell_type == "container" and p2_grid[y][x] == "▓":
                    # Empty server space
                    cell_str = Colors.colorize("▓", Colors.GREEN)
                elif cell_type == "item":
                    # Item on a server
                    if color:
                        cell_str = Colors.colorize(f"{cell}", color + Colors.BOLD)
                    else:
                        cell_str = f"{cell}"
                else:
                    # Empty space (no server)
                    cell_str = "·"
                row_str += cell_str + " "
            print(row_str)


def replay_battle_from_file(filename: str, speed: float = 1.0):
    """Load and replay a battle from a saved JSON file"""
    import json

    with open(filename, "r") as f:
        data = json.load(f)

    renderer = ASCIIBattleRenderer()
    renderer.render_battle(
        data["result"],
        data.get("p1_items", []),
        data.get("p2_items", []),
        real_time=True,
        speed=speed,
    )


if __name__ == "__main__":
    # Example usage
    from battle_engine import BattleSimulator, PlacedItem
    from item_effects import AttackEffect, ItemSpec, TimerTrigger
    from server_containers import create_server_containers

    # Get container specs
    containers = create_server_containers()

    # Create containers for both players
    p1_container = ServerContainer(
        spec=containers["mini_rack"]["spec"],
        position=(0, 0),
        uid="p1_rack",
        internal_grid_size=containers["mini_rack"]["internal_size"],
        shape=containers["mini_rack"]["external_shape"],
    )

    p2_container = ServerContainer(
        spec=containers["mini_rack"]["spec"],
        position=(4, 0),
        uid="p2_rack",
        internal_grid_size=containers["mini_rack"]["internal_size"],
        shape=containers["mini_rack"]["external_shape"],
    )

    # Create simple test items - placed ON the containers
    p1_items = [
        PlacedItem(
            spec=ItemSpec(
                id="test1",
                name="Bug Attacker",
                category="problem",
                triggers=[
                    TimerTrigger(
                        cooldown=2.0,
                        cpu_cost=3,
                        effects=[
                            AttackEffect(min_damage=5, max_damage=8, accuracy=0.9)
                        ],
                    )
                ],
            ),
            position=(0, 0),  # On p1's container
            uid="p1_item1",
        )
    ]

    p2_items = [
        PlacedItem(
            spec=ItemSpec(
                id="test2",
                name="Shield Defender",
                category="problem",
                triggers=[
                    TimerTrigger(
                        cooldown=3.0,
                        cpu_cost=2,
                        effects=[
                            AttackEffect(min_damage=4, max_damage=6, accuracy=0.95)
                        ],
                    )
                ],
            ),
            position=(4, 0),  # On p2's container
            uid="p2_item1",
        )
    ]

    # Run battle WITH containers
    sim = BattleSimulator(seed=12345)
    result = sim.simulate_battle(
        p1_items,
        p2_items,
        round_number=1,
        validate_placement=True,  # Enable validation
        p1_containers=[p1_container],
        p2_containers=[p2_container],
    )

    # Add starting HP to result for renderer
    result["player1_quota_start"] = 25
    result["player2_quota_start"] = 25

    # Render the battle
    renderer = ASCIIBattleRenderer()

    print("Choose playback mode:")
    print("1. Real-time playback")
    print("2. Step-by-step")
    choice = input("Enter choice (1 or 2): ")

    if choice == "2":
        renderer.render_battle(
            result,
            p1_items,
            p2_items,
            real_time=False,
            p1_containers=[p1_container],
            p2_containers=[p2_container],
        )
    else:
        print("Enter playback speed (1.0 = normal, 2.0 = 2x speed, 0.5 = half speed): ")
        speed = float(input() or "1.0")
        renderer.render_battle(
            result,
            p1_items,
            p2_items,
            real_time=True,
            speed=speed,
            p1_containers=[p1_container],
            p2_containers=[p2_container],
        )
