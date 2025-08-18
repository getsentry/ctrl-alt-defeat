"""
Configuration loader for items and containers from JSON files
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from grid_system import SHAPES, ItemShape
from item_effects import (
    AttackEffect,
    BattleStartTrigger,
    BlockEffect,
    BuffEffect,
    ConsumeEffect,
    DamageTakenTrigger,
    HealEffect,
    ItemSpec,
    PassiveTrigger,
    StatModEffect,
    TimerTrigger,
)
from shield_effect import OnAttackedTrigger, ShieldBlockEffect


class ConfigLoader:
    """Loads item and container configurations from JSON files"""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.containers = {}
        self.items = {}

    def load_all(self):
        """Load all configurations"""
        self.load_containers()
        self.load_items()

    def load_containers(self, filename: str = "containers.json"):
        """Load container configurations from JSON"""
        filepath = self.data_dir / filename
        if not filepath.exists():
            print(f"Warning: {filepath} not found")
            return {}

        with open(filepath, "r") as f:
            data = json.load(f)

        containers = {}
        for container_id, config in data.get("containers", {}).items():
            containers[container_id] = self._create_container_spec(container_id, config)

        self.containers = containers
        return containers

    def load_items(self, filename: str = "items.json"):
        """Load item configurations from JSON"""
        items = {}

        # Try to load from split category files first
        items_dir = self.data_dir / "items"
        if items_dir.exists() and items_dir.is_dir():
            for category_file in items_dir.glob("*.json"):
                try:
                    with open(category_file, "r") as f:
                        category_data = json.load(f)

                    # Handle both formats: {"items": {...}} and {"category": "...", "items": {...}}
                    category_items = category_data.get("items", {})
                    for item_id, config in category_items.items():
                        items[item_id] = self._create_item_spec(item_id, config)

                    print(
                        f"Loaded {len(category_items)} items from {category_file.name}"
                    )
                except Exception as e:
                    print(f"Warning: Failed to load {category_file}: {e}")

        # Fallback to single items.json file
        if not items:
            filepath = self.data_dir / filename
            if filepath.exists():
                with open(filepath, "r") as f:
                    data = json.load(f)

                for category_name, category_items in data.get("items", {}).items():
                    for item_id, config in category_items.items():
                        items[item_id] = self._create_item_spec(item_id, config)

        self.items = items
        return items

    def _create_container_spec(self, container_id: str, config: Dict[str, Any]) -> Dict:
        """Create a container specification from config"""
        # Parse shape
        shape = self._parse_shape(config.get("shape", "2x2"))
        internal_size = tuple(config.get("internal_size", [2, 2]))

        # Parse effects
        effects = []
        triggers = []
        for effect_config in config.get("effects", []):
            effect = self._parse_effect(effect_config)
            if effect:
                effects.append(effect)

        # Create trigger if there are effects
        if effects:
            triggers = [PassiveTrigger(effects=effects)]

        # Create ItemSpec for the container
        spec = ItemSpec(
            id=container_id,
            name=config.get("name", "Unknown Container"),
            category="infrastructure",
            shape=shape,
            triggers=triggers,
            rarity=config.get("rarity", "common"),
        )

        return {
            "spec": spec,
            "internal_size": internal_size,
            "external_shape": shape,
            "description": config.get("description", ""),
            "cost": config.get("cost", 1),
        }

    def _create_item_spec(self, item_id: str, config: Dict[str, Any]) -> ItemSpec:
        """Create an item specification from config"""
        # Parse shape
        shape = self._parse_shape(config.get("shape", "1x1"))

        # Parse triggers
        triggers = []
        for trigger_config in config.get("triggers", []):
            trigger = self._parse_trigger(trigger_config)
            if trigger:
                triggers.append(trigger)

        return ItemSpec(
            id=item_id,
            name=config.get("name", "Unknown Item"),
            category=config.get("category", "problem"),
            shape=shape,
            triggers=triggers,
            rarity=config.get("rarity", "common"),
        )

    def _parse_shape(self, shape_str: str) -> Optional[ItemShape]:
        """Parse a shape string like '2x2' or '3x1'"""
        if shape_str == "variable":
            # Special case for variable shapes
            return SHAPES.get("2x2")  # Default to 2x2

        # Check if it's a predefined shape
        if shape_str in SHAPES:
            return SHAPES[shape_str]

        # Parse custom shape
        if "x" in shape_str:
            try:
                width, height = map(int, shape_str.split("x"))
                squares = []
                for y in range(height):
                    for x in range(width):
                        squares.append((x, y))
                return ItemShape(squares, shape_str)
            except Exception:
                pass

        # Default to 1x1
        return SHAPES.get("1x1")

    def _parse_trigger(self, config: Dict[str, Any]) -> Optional[Any]:
        """Parse a trigger configuration"""
        trigger_type = config.get("type")
        effects = []

        # Parse effects
        for effect_config in config.get("effects", []):
            effect = self._parse_effect(effect_config)
            if effect:
                effects.append(effect)

        if trigger_type == "timer":
            return TimerTrigger(
                cooldown=config.get("cooldown", 1.0),
                cpu_cost=config.get("cpu_cost", 1),
                effects=effects,
            )
        elif trigger_type == "battle_start":
            return BattleStartTrigger(effects=effects)
        elif trigger_type == "damage_taken":
            return DamageTakenTrigger(
                threshold=config.get("threshold", 0),
                cooldown=config.get("cooldown", 0),
                cpu_cost=config.get("cpu_cost", 0),
                effects=effects,
            )
        elif trigger_type == "on_attacked":
            return OnAttackedTrigger(effects=effects)
        elif trigger_type == "passive":
            return PassiveTrigger(effects=effects)

        return None

    def _parse_effect(self, config: Dict[str, Any]) -> Optional[Any]:
        """Parse an effect configuration"""
        effect_type = config.get("type")

        if effect_type == "attack":
            effect = AttackEffect(
                min_damage=config.get("min_damage", 1),
                max_damage=config.get("max_damage", 1),
                accuracy=config.get("accuracy", 1.0),
                crit_chance=config.get("crit_chance", 0),
            )
            # Store additional properties as attributes
            if config.get("pierce"):
                effect.pierce = True
            if config.get("hits", 1) > 1:
                effect.hits = config.get("hits", 1)
            if config.get("special"):
                effect.special = config.get("special")
            return effect
        elif effect_type == "heal":
            return HealEffect(
                min_heal=config.get("min_heal", 1), max_heal=config.get("max_heal", 1)
            )
        elif effect_type == "shield_block":
            effect = ShieldBlockEffect(
                block_chance=config.get("block_chance", 0.3),
                block_amount=config.get("block_amount", 5),
                cpu_steal=config.get("cpu_steal", 0),
            )
            # Store additional properties as attributes
            if config.get("reflect_damage"):
                effect.reflect_damage = config.get("reflect_damage", 0)
            return effect
        elif effect_type == "stat_mod":
            return StatModEffect(
                stat_name=config.get("stat", "max_cpu"), value=config.get("value", 1)
            )
        elif effect_type == "buff":
            return BuffEffect(
                buff_name=config.get("stat", "speed"),
                value=config.get("value", 0.1),
                target_type=config.get("target", "self"),
            )
        elif effect_type == "block":
            return BlockEffect(block_amount=config.get("value", 5))
        elif effect_type == "consume":
            return ConsumeEffect()

        return None

    def get_container(self, container_id: str) -> Optional[Dict]:
        """Get a container by ID"""
        return self.containers.get(container_id)

    def get_item(self, item_id: str) -> Optional[ItemSpec]:
        """Get an item by ID"""
        return self.items.get(item_id)

    def list_containers(self) -> List[str]:
        """List all available container IDs"""
        return list(self.containers.keys())

    def list_items(self) -> List[str]:
        """List all available item IDs"""
        return list(self.items.keys())


# Global instance
config_loader = ConfigLoader()


def load_configurations():
    """Load all configurations from JSON files"""
    config_loader.load_all()
    return config_loader


def create_server_containers_from_config():
    """Create server containers from configuration"""
    if not config_loader.containers:
        config_loader.load_containers()
    return config_loader.containers


def create_items_from_config():
    """Create items from configuration"""
    if not config_loader.items:
        config_loader.load_items()
    return config_loader.items


if __name__ == "__main__":
    # Demo the configuration loader
    print("Loading configurations from JSON files...\n")

    loader = ConfigLoader()
    loader.load_all()

    print(f"Loaded {len(loader.containers)} containers:")
    for container_id in loader.list_containers():
        container = loader.get_container(container_id)
        print(f"  - {container['spec'].name}: {container.get('description', '')}")

    print(f"\nLoaded {len(loader.items)} items:")
    for item_id in loader.list_items():
        item = loader.get_item(item_id)
        print(f"  - {item.name} ({item.category})")

    print("\n✅ Configuration loading complete!")
