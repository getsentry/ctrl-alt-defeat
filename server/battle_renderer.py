"""
ASCII Battle Renderer - Replay battles from logs in real-time
Renders the battle grid and shows actions as they happen
"""

import os
import time
from dataclasses import dataclass
from typing import Dict, List

from grid_system import Rotation
from schemas import BattleAction
from server_containers import ServerContainer


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
                action_time = action.timestamp / 1000.0

                if action_time <= current_real_time:
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
                and current_real_time > actions[-1].timestamp / 1000.0 + 1
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
            state.current_time = action.timestamp / 1000.0
            self._render_frame(state)

            print(
                f"\nAction {i+1}/{len(actions)} - Press Enter for next, 'q' to quit: ",
                end="",
            )
            user_input = input()
            if user_input.lower() == "q":
                break

    def _process_action(self, state: BattleState, action: BattleAction):
        """Update state based on action"""
        action_code = action.action
        timestamp = action.timestamp / 1000.0
        player = action.player
        item_uid = action.source
        value = action.damage

        # Clear previous active items (they fade after one frame)
        state.active_items.clear()

        # Build action description
        desc = f"[{timestamp:.1f}s] {action_code}"

        if player is not None:
            desc += f" P{player}"
        if item_uid and item_uid != "system":
            item_name = self._get_item_name(state, item_uid)
            desc += f" {item_name}"
        if value is not None:
            desc += f" ({value})"

        # Update state and set item colors based on action type
        if action_code == "damage":
            damage = value or 0
            if player == 1:
                state.player1_hp -= damage
            else:
                state.player2_hp -= damage
            desc = Colors.colorize(f"💥 {desc}", Colors.BRIGHT_RED)
            if item_uid:
                state.active_items[item_uid] = Colors.BRIGHT_RED

        elif action_code == "heal":
            heal = value or 0
            if player == 1:
                state.player1_hp = min(state.player1_max_hp, state.player1_hp + heal)
            else:
                state.player2_hp = min(state.player2_max_hp, state.player2_hp + heal)
            desc = Colors.colorize(f"💚 {desc}", Colors.BRIGHT_GREEN)
            if item_uid:
                state.active_items[item_uid] = Colors.BRIGHT_GREEN

        elif action_code == "block":
            desc = Colors.colorize(f"🛡️ {desc}", Colors.BRIGHT_CYAN)
            if item_uid:
                state.active_items[item_uid] = Colors.BRIGHT_CYAN

        elif action_code == "cpu_fail":
            desc = Colors.colorize(f"⚠️ {desc}", Colors.YELLOW)
            if item_uid:
                state.active_items[item_uid] = Colors.YELLOW

        elif action_code == "activate":
            desc = Colors.colorize(f"⚡ {desc}", Colors.BRIGHT_YELLOW)
            if item_uid:
                state.active_items[item_uid] = Colors.BRIGHT_YELLOW

        elif action_code == "critical_hit":
            desc = Colors.colorize(f"💥 CRIT! {desc}", Colors.BRIGHT_MAGENTA)
            if item_uid:
                state.active_items[item_uid] = Colors.BRIGHT_MAGENTA

        elif action_code == "miss":
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
    # Example usage with real items from ITEM_CATALOG
    from copy import deepcopy

    from battle_engine import ITEM_CATALOG, BattleSimulator, PlacedItem
    from server_containers import create_server_containers

    # Get container specs
    containers = create_server_containers()

    # Create larger containers for both players (2x2 each)
    p1_containers = [
        ServerContainer(
            spec=containers["standard_vm"]["spec"],
            position=(0, 2),
            uid="p1_rack1",
            shape=containers["standard_vm"]["external_shape"],
        ),
        ServerContainer(
            spec=containers["standard_vm"]["spec"],
            position=(2, 2),
            uid="p1_rack2",
            shape=containers["standard_vm"]["external_shape"],
        ),
    ]

    p2_containers = [
        ServerContainer(
            spec=containers["standard_vm"]["spec"],
            position=(4, 2),
            uid="p2_rack1",
            shape=containers["standard_vm"]["external_shape"],
        ),
        ServerContainer(
            spec=containers["standard_vm"]["spec"],
            position=(4, 4),
            uid="p2_rack2",
            shape=containers["standard_vm"]["external_shape"],
        ),
    ]

    # Create diverse items from real ITEM_CATALOG for Player 1
    p1_items = [
        # Offensive items
        PlacedItem(
            spec=deepcopy(ITEM_CATALOG["memory_leak"]),  # Problem: 3-5 damage
            position=(0, 2),  # On p1's first container
            uid="p1_leak",
        ),
        PlacedItem(
            spec=deepcopy(ITEM_CATALOG["null_pointer"]),  # Problem: 4-7 damage
            position=(1, 2),
            uid="p1_null",
        ),
        # Defensive item
        PlacedItem(
            spec=deepcopy(ITEM_CATALOG["firewall"]),  # Defense: firewall
            position=(0, 3),
            uid="p1_firewall",
            rotation=Rotation.CLOCKWISE_90,  # Rotate to horizontal
        ),
        # Support item
        PlacedItem(
            spec=deepcopy(ITEM_CATALOG["error_monitoring"]),  # Monitor: +10% accuracy
            position=(3, 3),
            uid="p1_monitor",
        ),
        # Additional offensive items on second container
        PlacedItem(
            spec=deepcopy(ITEM_CATALOG["infinite_loop"]),  # Problem: 2-4 damage, fast
            position=(2, 2),
            uid="p1_loop",
        ),
        PlacedItem(
            spec=deepcopy(
                ITEM_CATALOG["race_condition"]
            ),  # Problem: high damage variance
            position=(2, 3),
            uid="p1_race",
        ),
    ]

    # Create diverse items from real ITEM_CATALOG for Player 2
    p2_items = [
        # Offensive items on first container
        PlacedItem(
            spec=deepcopy(
                ITEM_CATALOG["race_condition"]
            ),  # Problem: race condition (1x1)
            position=(4, 2),  # On p2's first container
            uid="p2_race",
        ),
        PlacedItem(
            spec=deepcopy(
                ITEM_CATALOG["zero_day_exploit"]
            ),  # Problem: Zero-day exploit
            position=(5, 2),
            uid="p2_zero_day",
        ),
        PlacedItem(
            spec=deepcopy(
                ITEM_CATALOG["quantum_firewall"]
            ),  # Defense: quantum firewall (1x1)
            position=(4, 3),
            uid="p2_quantum_firewall",
        ),
        PlacedItem(
            spec=deepcopy(
                ITEM_CATALOG["error_monitoring"]
            ),  # Monitor: +10% accuracy (1x1)
            position=(5, 3),
            uid="p2_monitor",
        ),
        # Items on second container
        PlacedItem(
            spec=deepcopy(
                ITEM_CATALOG["rate_limiter"]
            ),  # Defense: rate limiter (2x1 horizontal)
            position=(4, 4),
            uid="p2_rate_limiter",
        ),
        PlacedItem(
            spec=deepcopy(
                ITEM_CATALOG["cpu_booster"]
            ),  # Infrastructure: CPU boost (1x1)
            position=(4, 5),
            uid="p2_cpu_booster",
        ),
        PlacedItem(
            spec=deepcopy(
                ITEM_CATALOG["load_balancer"]
            ),  # Infrastructure: load balancer (1x1)
            position=(5, 5),
            uid="p2_load_balancer",
        ),
    ]

    # Run battle WITH containers
    sim = BattleSimulator(seed=12345)
    result = sim.simulate_battle(
        p1_items,
        p2_items,
        round_number=1,
        p1_containers=p1_containers,
        p2_containers=p2_containers,
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
            p1_containers=p1_containers,
            p2_containers=p2_containers,
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
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )
