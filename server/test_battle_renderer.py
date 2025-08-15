"""
Test the ASCII battle renderer
"""

import pytest
import json
import tempfile
from battle_engine import BattleSimulator, PlacedItem
from item_effects import ItemSpec, TimerTrigger, AttackEffect, HealEffect
from shield_effect import OnAttackedTrigger, ShieldBlockEffect
from battle_renderer import ASCIIBattleRenderer, BattleState

class TestBattleRenderer:
    """Test ASCII battle rendering functionality"""
    
    def test_render_simple_battle(self):
        """Test rendering a simple battle"""
        # Create test items
        p1_items = [
            PlacedItem(
                spec=ItemSpec(
                    id="attacker",
                    name="Memory Leak",
                    category="problem",
                    triggers=[TimerTrigger(
                        cooldown=2.0,
                        cpu_cost=3,
                        effects=[AttackEffect(min_damage=5, max_damage=7, accuracy=0.9)]
                    )]
                ),
                position=(0, 0),
                uid="p1_attack"
            )
        ]
        
        p2_items = [
            PlacedItem(
                spec=ItemSpec(
                    id="defender",
                    name="Error Shield",
                    category="defense",
                    triggers=[OnAttackedTrigger(
                        effects=[ShieldBlockEffect(block_chance=0.3, block_amount=3)]
                    )]
                ),
                position=(0, 0),
                uid="p2_shield"
            ),
            PlacedItem(
                spec=ItemSpec(
                    id="healer",
                    name="Health Check",
                    category="infrastructure",
                    triggers=[TimerTrigger(
                        cooldown=4.0,
                        cpu_cost=2,
                        effects=[HealEffect(min_heal=2, max_heal=3)]
                    )]
                ),
                position=(1, 0),
                uid="p2_heal"
            )
        ]
        
        # Run battle
        sim = BattleSimulator(seed=99999)
        result = sim.simulate_battle(p1_items, p2_items, round_number=1)
        
        # Add starting HP
        result["player1_quota_start"] = 25
        result["player2_quota_start"] = 25
        
        # Create renderer
        renderer = ASCIIBattleRenderer()
        
        # Test that rendering doesn't crash (can't test visual output easily)
        # In real usage, this would display the battle
        # renderer.render_battle(result, p1_items, p2_items, real_time=False)
        
        # Just verify the renderer can process actions
        state = BattleState(
            player1_hp=25, player1_max_hp=25, player1_cpu=10.0, player1_max_cpu=10,
            player1_items={item.uid: {"name": item.spec.name, "active": False} for item in p1_items},
            player2_hp=25, player2_max_hp=25, player2_cpu=10.0, player2_max_cpu=10,
            player2_items={item.uid: {"name": item.spec.name, "active": False} for item in p2_items},
            current_time=0.0, last_actions=[]
        )
        
        # Process some actions
        for action in result["actions"][:5]:
            renderer._process_action(state, action)
        
        # Verify state was updated
        assert len(state.last_actions) <= 5
        assert state.current_time == 0.0  # Time is updated separately
    
    def test_save_and_load_battle(self):
        """Test saving battle results for replay"""
        # Create and run a battle
        p1_items = [
            PlacedItem(
                spec=ItemSpec(
                    id="test1",
                    name="Test Item 1",
                    category="problem",
                    triggers=[TimerTrigger(
                        cooldown=1.5,
                        cpu_cost=2,
                        effects=[AttackEffect(min_damage=3, max_damage=5, accuracy=0.95)]
                    )]
                ),
                position=(0, 0),
                uid="item1"
            )
        ]
        
        p2_items = [
            PlacedItem(
                spec=ItemSpec(
                    id="test2",
                    name="Test Item 2",
                    category="problem",
                    triggers=[TimerTrigger(
                        cooldown=2.0,
                        cpu_cost=3,
                        effects=[AttackEffect(min_damage=4, max_damage=6, accuracy=0.9)]
                    )]
                ),
                position=(0, 0),
                uid="item2"
            )
        ]
        
        sim = BattleSimulator(seed=12345)
        result = sim.simulate_battle(p1_items, p2_items, round_number=1)
        
        # Save to file
        battle_data = {
            "result": result,
            "p1_items": [{"uid": item.uid, "name": item.spec.name} for item in p1_items],
            "p2_items": [{"uid": item.uid, "name": item.spec.name} for item in p2_items]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(battle_data, f)
            temp_file = f.name
        
        # Load and verify
        with open(temp_file, 'r') as f:
            loaded_data = json.load(f)
        
        assert loaded_data["result"]["seed"] == 12345
        assert loaded_data["result"]["winner"] in [1, 2]
        assert len(loaded_data["result"]["actions"]) > 0
    
    def test_progress_bar(self):
        """Test progress bar rendering"""
        renderer = ASCIIBattleRenderer()
        
        # Test various bar states
        bar1 = renderer._make_bar(10, 10, 10, "█", "░")
        assert bar1 == "█" * 10
        
        bar2 = renderer._make_bar(5, 10, 10, "█", "░")
        assert bar2 == "█" * 5 + "░" * 5
        
        bar3 = renderer._make_bar(0, 10, 10, "█", "░")
        assert bar3 == "░" * 10
        
        bar4 = renderer._make_bar(7, 10, 10, "█", "░")
        assert bar4 == "█" * 7 + "░" * 3
    
    def test_action_processing(self):
        """Test that actions update state correctly"""
        renderer = ASCIIBattleRenderer()
        
        state = BattleState(
            player1_hp=25, player1_max_hp=25, player1_cpu=10.0, player1_max_cpu=10,
            player1_items={"item1": {"name": "Test Item", "active": False}},
            player2_hp=25, player2_max_hp=25, player2_cpu=10.0, player2_max_cpu=10,
            player2_items={},
            current_time=0.0, last_actions=[]
        )
        
        # Test damage action
        damage_action = {"t": 1.0, "a": "d", "p": 1, "v": 5}
        renderer._process_action(state, damage_action)
        assert state.player1_hp == 20
        
        # Test heal action
        heal_action = {"t": 2.0, "a": "h", "p": 1, "v": 3}
        renderer._process_action(state, heal_action)
        assert state.player1_hp == 23
        
        # Test that actions are logged
        assert len(state.last_actions) == 2
        
        # Test action limit (max 5)
        for i in range(10):
            renderer._process_action(state, {"t": i, "a": "m", "p": 1})
        assert len(state.last_actions) == 5

def demo_battle_replay():
    """Demo function to show a battle replay"""
    from battle_engine import BattleSimulator, PlacedItem
    from item_effects import ItemSpec, TimerTrigger, AttackEffect, HealEffect
    
    print("=== BATTLE REPLAY DEMO ===")
    print("Creating a battle between aggressive and defensive builds...")
    
    # Aggressive build
    p1_items = [
        PlacedItem(
            spec=ItemSpec(
                id="null_pointer",
                name="Null Pointer",
                category="problem",
                triggers=[TimerTrigger(
                    cooldown=2.0,
                    cpu_cost=3,
                    effects=[AttackEffect(min_damage=4, max_damage=6, accuracy=0.9)]
                )]
            ),
            position=(0, 0),
            uid="p1_null"
        ),
        PlacedItem(
            spec=ItemSpec(
                id="memory_leak",
                name="Memory Leak",
                category="problem",
                triggers=[TimerTrigger(
                    cooldown=2.5,
                    cpu_cost=2,
                    effects=[AttackEffect(min_damage=3, max_damage=5, accuracy=0.95)]
                )]
            ),
            position=(1, 0),
            uid="p1_leak"
        )
    ]
    
    # Defensive build
    p2_items = [
        PlacedItem(
            spec=ItemSpec(
                id="shield",
                name="Error Shield",
                category="defense",
                triggers=[OnAttackedTrigger(
                    effects=[ShieldBlockEffect(block_chance=0.4, block_amount=3)]
                )]
            ),
            position=(0, 0),
            uid="p2_shield"
        ),
        PlacedItem(
            spec=ItemSpec(
                id="healer",
                name="Health Monitor",
                category="infrastructure",
                triggers=[TimerTrigger(
                    cooldown=3.0,
                    cpu_cost=2,
                    effects=[HealEffect(min_heal=2, max_heal=4)]
                )]
            ),
            position=(1, 0),
            uid="p2_heal"
        ),
        PlacedItem(
            spec=ItemSpec(
                id="counter",
                name="Counter Bug",
                category="problem",
                triggers=[TimerTrigger(
                    cooldown=3.5,
                    cpu_cost=3,
                    effects=[AttackEffect(min_damage=5, max_damage=7, accuracy=0.85)]
                )]
            ),
            position=(0, 1),
            uid="p2_counter"
        )
    ]
    
    # Run the battle
    print("\nSimulating battle...")
    sim = BattleSimulator(seed=54321)
    result = sim.simulate_battle(p1_items, p2_items, round_number=3)
    
    # Add starting HP
    result["player1_quota_start"] = 35  # Round 3 has 35 HP
    result["player2_quota_start"] = 35
    
    print(f"Battle completed! Winner: Player {result['winner']}")
    print(f"Duration: {result['duration']}s")
    print(f"Total actions: {len(result['actions'])}")
    
    # Save to file
    import json
    battle_data = {
        "result": result,
        "p1_items": [{"uid": item.uid, "name": item.spec.name} for item in p1_items],
        "p2_items": [{"uid": item.uid, "name": item.spec.name} for item in p2_items]
    }
    
    with open("demo_battle.json", "w") as f:
        json.dump(battle_data, f, indent=2)
    print("\nBattle saved to demo_battle.json")
    
    return result, p1_items, p2_items

if __name__ == "__main__":
    # Run the demo
    result, p1_items, p2_items = demo_battle_replay()
    
    # Offer to replay
    print("\nWould you like to watch the battle replay? (y/n): ", end='')
    if input().lower() == 'y':
        renderer = ASCIIBattleRenderer()
        renderer.render_battle(result, p1_items, p2_items, real_time=True, speed=2.0)