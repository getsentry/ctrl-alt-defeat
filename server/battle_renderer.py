"""
ASCII Battle Renderer - Replay battles from logs in real-time
Renders the battle grid and shows actions as they happen
"""

import time
import os
import sys
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from battle_engine import ACTION_CODES

# Try to import grid system for better visualization
try:
    from grid_system import InventoryGrid, GridItem, Container, SHAPES, Rotation
    GRID_AVAILABLE = True
except ImportError:
    GRID_AVAILABLE = False

# Reverse action codes for display
ACTION_NAMES = {v: k for k, v in ACTION_CODES.items()}

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
    
class ASCIIBattleRenderer:
    """Render battle replays in ASCII art"""
    
    def __init__(self, width: int = 80, height: int = 30):
        self.width = width
        self.height = height
        self.clear_screen = 'cls' if os.name == 'nt' else 'clear'
        
    def render_battle(self, battle_result: Dict, p1_items: List, p2_items: List, 
                     real_time: bool = True, speed: float = 1.0):
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
            player1_items={item.uid: {"name": item.spec.name, "active": False} for item in p1_items},
            
            player2_hp=battle_result.get("player2_quota_start", 25),
            player2_max_hp=battle_result.get("player2_quota_start", 25),
            player2_cpu=10.0,
            player2_max_cpu=10,
            player2_items={item.uid: {"name": item.spec.name, "active": False} for item in p2_items},
            
            current_time=0.0,
            last_actions=[]
        )
        
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
            if action_index >= len(actions) and current_real_time > actions[-1]["t"] + 1:
                break
        
        # Show final state
        print("\n" + "="*self.width)
        print(f"BATTLE ENDED - Winner: Player {state.player1_hp > 0 and 1 or 2}")
        print("="*self.width)
    
    def _render_step_by_step(self, state: BattleState, actions: List[Dict]):
        """Render the battle step by step with user input"""
        for i, action in enumerate(actions):
            self._process_action(state, action)
            state.current_time = action["t"]
            self._render_frame(state)
            
            print(f"\nAction {i+1}/{len(actions)} - Press Enter for next, 'q' to quit: ", end='')
            user_input = input()
            if user_input.lower() == 'q':
                break
    
    def _process_action(self, state: BattleState, action: Dict):
        """Update state based on action"""
        action_type = ACTION_NAMES.get(action["a"], action["a"])
        
        # Build action description
        desc = f"[{action['t']:.1f}s] {action_type}"
        
        if "p" in action:
            desc += f" P{action['p']}"
        if "i" in action:
            item_name = self._get_item_name(state, action["i"])
            desc += f" {item_name}"
        if "v" in action:
            desc += f" ({action['v']})"
        
        # Update state based on action type
        if action["a"] == ACTION_CODES["DAMAGE"]:
            if action["p"] == 1:
                state.player1_hp -= action.get("v", 0)
            else:
                state.player2_hp -= action.get("v", 0)
            desc = f"💥 {desc}"
            
        elif action["a"] == ACTION_CODES["HEAL"]:
            if action["p"] == 1:
                state.player1_hp = min(state.player1_max_hp, state.player1_hp + action.get("v", 0))
            else:
                state.player2_hp = min(state.player2_max_hp, state.player2_hp + action.get("v", 0))
            desc = f"💚 {desc}"
            
        elif action["a"] == ACTION_CODES["BLOCK"]:
            desc = f"🛡️ {desc}"
            
        elif action["a"] == ACTION_CODES["CPU_FAIL"]:
            desc = f"⚠️ {desc}"
            
        elif action["a"] == ACTION_CODES["ACTIVATE"]:
            # Mark item as active briefly
            if action.get("i"):
                if action["p"] == 1 and action["i"] in state.player1_items:
                    state.player1_items[action["i"]]["active"] = True
                elif action["p"] == 2 and action["i"] in state.player2_items:
                    state.player2_items[action["i"]]["active"] = True
            desc = f"⚡ {desc}"
        
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
        
        print("="*self.width)
        print(f"{'BATTLE REPLAY':^{self.width}}")
        print(f"{'Time: ' + f'{state.current_time:.1f}s':^{self.width}}")
        print("="*self.width)
        
        # Player stats
        self._render_player_stats(state)
        
        print("-"*self.width)
        
        # Items grid (simplified)
        self._render_items_grid(state)
        
        print("-"*self.width)
        
        # Recent actions
        print("Recent Actions:")
        for action in state.last_actions:
            print(f"  {action}")
        
        print("="*self.width)
    
    def _render_player_stats(self, state: BattleState):
        """Render player health and CPU bars"""
        # Player 1
        hp_bar1 = self._make_bar(state.player1_hp, state.player1_max_hp, 20, "█", "░")
        cpu_bar1 = self._make_bar(int(state.player1_cpu), state.player1_max_cpu, 10, "▓", "░")
        
        # Player 2
        hp_bar2 = self._make_bar(state.player2_hp, state.player2_max_hp, 20, "█", "░")
        cpu_bar2 = self._make_bar(int(state.player2_cpu), state.player2_max_cpu, 10, "▓", "░")
        
        # Display
        p1_text = f"Player 1: HP {hp_bar1} {state.player1_hp:3}/{state.player1_max_hp}"
        p2_text = f"Player 2: HP {hp_bar2} {state.player2_hp:3}/{state.player2_max_hp}"
        
        print(f"{p1_text:<39} | {p2_text:>39}")
        
        p1_cpu = f"         CPU {cpu_bar1} {state.player1_cpu:.0f}/{state.player1_max_cpu}"
        p2_cpu = f"         CPU {cpu_bar2} {state.player2_cpu:.0f}/{state.player2_max_cpu}"
        
        print(f"{p1_cpu:<39} | {p2_cpu:>39}")
    
    def _make_bar(self, current: int, maximum: int, length: int, 
                  filled: str = "█", empty: str = "░") -> str:
        """Create a progress bar"""
        if maximum <= 0:
            return empty * length
        
        filled_length = int(length * current / maximum)
        return filled * filled_length + empty * (length - filled_length)
    
    def _render_items_grid(self, state: BattleState):
        """Render item grids with visual representation"""
        if GRID_AVAILABLE:
            # Create visual grids for both players
            self._render_visual_grid(state)
        else:
            # Fallback to simple list
            self._render_simple_items(state)
    
    def _render_visual_grid(self, state: BattleState):
        """Render visual grid representation"""
        # Create 7x4 grids for each player (simplified)
        grid_width, grid_height = 7, 4
        
        print("\n" + "─" * 40)
        print("PLAYER 1 GRID:")
        p1_grid = [[" " for _ in range(grid_width)] for _ in range(grid_height)]
        
        # Place items in grid (simplified - just use first letter)
        item_positions = {
            0: (0, 0), 1: (2, 0), 2: (4, 0),  # First row
            3: (0, 2), 4: (2, 2), 5: (4, 2),  # Second row
        }
        
        for i, (uid, item) in enumerate(state.player1_items.items()):
            if i < len(item_positions):
                x, y = item_positions[i]
                if x < grid_width and y < grid_height:
                    char = "⚡" if item.get("active") else item["name"][0].upper()
                    p1_grid[y][x] = char
                    item["active"] = False
        
        # Print grid
        print("  " + "".join(str(i) for i in range(grid_width)))
        for y, row in enumerate(p1_grid):
            print(f"{y} " + "".join(f"[{cell}]" for cell in row))
        
        print("\n" + "─" * 40)
        print("PLAYER 2 GRID:")
        p2_grid = [[" " for _ in range(grid_width)] for _ in range(grid_height)]
        
        for i, (uid, item) in enumerate(state.player2_items.items()):
            if i < len(item_positions):
                x, y = item_positions[i]
                if x < grid_width and y < grid_height:
                    char = "⚡" if item.get("active") else item["name"][0].upper()
                    p2_grid[y][x] = char
                    item["active"] = False
        
        # Print grid
        print("  " + "".join(str(i) for i in range(grid_width)))
        for y, row in enumerate(p2_grid):
            print(f"{y} " + "".join(f"[{cell}]" for cell in row))
    
    def _render_simple_items(self, state: BattleState):
        """Render simple item list (fallback)"""
        print("\nPlayer 1 Items:")
        for uid, item in list(state.player1_items.items())[:3]:  # Show first 3
            active_marker = "⚡" if item.get("active") else " "
            print(f"  {active_marker} {item['name'][:20]:<20}")
            item["active"] = False
        
        print("\nPlayer 2 Items:")
        for uid, item in list(state.player2_items.items())[:3]:  # Show first 3
            active_marker = "⚡" if item.get("active") else " "
            print(f"  {active_marker} {item['name'][:20]:<20}")
            item["active"] = False


def replay_battle_from_file(filename: str, speed: float = 1.0):
    """Load and replay a battle from a saved JSON file"""
    import json
    
    with open(filename, 'r') as f:
        data = json.load(f)
    
    renderer = ASCIIBattleRenderer()
    renderer.render_battle(
        data["result"],
        data.get("p1_items", []),
        data.get("p2_items", []),
        real_time=True,
        speed=speed
    )


if __name__ == "__main__":
    # Example usage
    from battle_engine import BattleSimulator, PlacedItem
    from item_effects import ItemSpec, TimerTrigger, AttackEffect
    
    # Create simple test items
    p1_items = [
        PlacedItem(
            spec=ItemSpec(
                id="test1",
                name="Bug Attacker",
                category="problem",
                triggers=[TimerTrigger(
                    cooldown=2.0,
                    cpu_cost=3,
                    effects=[AttackEffect(min_damage=5, max_damage=8, accuracy=0.9)]
                )]
            ),
            position=(0, 0),
            uid="p1_item1"
        )
    ]
    
    p2_items = [
        PlacedItem(
            spec=ItemSpec(
                id="test2",
                name="Shield Defender",
                category="problem",
                triggers=[TimerTrigger(
                    cooldown=3.0,
                    cpu_cost=2,
                    effects=[AttackEffect(min_damage=4, max_damage=6, accuracy=0.95)]
                )]
            ),
            position=(0, 0),
            uid="p2_item1"
        )
    ]
    
    # Run battle
    sim = BattleSimulator(seed=12345)
    result = sim.simulate_battle(p1_items, p2_items, round_number=1)
    
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
        renderer.render_battle(result, p1_items, p2_items, real_time=False)
    else:
        print("Enter playback speed (1.0 = normal, 2.0 = 2x speed, 0.5 = half speed): ")
        speed = float(input() or "1.0")
        renderer.render_battle(result, p1_items, p2_items, real_time=True, speed=speed)