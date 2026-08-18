"""
Configuration loader for items and containers from JSON files
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from grid_system import ItemShape, parse_map
from item_effects import (
    DEBUFFS,
    AttackEffect,
    BattleStartTrigger,
    BlockEffect,
    BuffEffect,
    ConsumeEffect,
    CpuDrainEffect,
    DamageTakenTrigger,
    DebuffEffect,
    HealEffect,
    ItemSpec,
    OnAttackedTrigger,
    OnHitTrigger,
    PassiveTrigger,
    PreventDamageEffect,
    StatModEffect,
    TimerTrigger,
)

logger = logging.getLogger(__name__)


class CatalogueError(Exception):
    """The item catalogue could not be read."""


class ConfigLoader:
    """Loads item and container configurations from JSON files"""

    # The catalogue sits next to this module, so it is found from wherever the
    # process happens to be running. It used to be resolved against the working
    # directory, which meant importing this from anywhere but `server/` built
    # an empty catalogue and printed a warning -- and the trainer carries an
    # `os.chdir` to work around it, having been bitten through multiprocessing.
    DATA_DIR = Path(__file__).parent / "data"

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = Path(data_dir) if data_dir else self.DATA_DIR
        self.containers: dict[str, ItemSpec] = {}
        self.items = {}

    def load_all(self):
        """Load all configurations"""
        self.load_containers()
        self.load_items()
        # Add containers to items catalog with special markers
        for container_id, container_info in self.containers.items():
            # Add to items with a special marker to indicate it's a container
            self.items[container_id] = container_info

    def load_containers(self, filename: str = "containers.json") -> dict[str, ItemSpec]:
        """Load container configurations from JSON"""
        # Look for containers in items directory first, then data directory
        filepath = self.data_dir / "items" / filename
        if not filepath.exists():
            filepath = self.data_dir / filename
        if not filepath.exists():
            raise CatalogueError(
                f"no containers file at {filepath}. Every item stands on a "
                f"container, so a game without them cannot be played."
            )

        try:
            data = json.loads(filepath.read_text())
        except json.JSONDecodeError as bad_json:
            raise CatalogueError(f"{filename} is not valid JSON: {bad_json}") from None

        containers = {}
        for container_id, config in data.get("containers", {}).items():
            try:
                containers[container_id] = self._create_container_spec(
                    container_id, config
                )
            except Exception as bad_container:
                raise CatalogueError(f"{filename}: {bad_container}") from None

        self.containers = containers
        return containers

    def load_items(self):
        """Load item configurations from split JSON files"""
        items = {}

        # Load from split category files in data/items/
        items_dir = self.data_dir / "items"
        if not items_dir.exists() or not items_dir.is_dir():
            raise CatalogueError(f"no items directory at {items_dir}")

        # Deliberately not sorted. The catalogue's insertion order decides
        # what a seeded shop offers, so sorting here silently reshuffles every
        # shop in the game. That the order comes from the filesystem at all is
        # a real problem, but it is not this one -- see BACKLOG.md.
        for category_file in items_dir.glob("*.json"):
            # Containers are loaded separately, by load_containers
            if category_file.name == "containers.json":
                continue

            try:
                category_data = json.loads(category_file.read_text())
            except json.JSONDecodeError as bad_json:
                raise CatalogueError(
                    f"{category_file.name} is not valid JSON: {bad_json}"
                ) from None

            # Both shapes appear: {"items": {...}} and {"category", "items"}
            for item_id, config in category_data.get("items", {}).items():
                try:
                    items[item_id] = self._create_item_spec(item_id, config)
                except Exception as bad_item:
                    raise CatalogueError(
                        f"{category_file.name}: {bad_item}"
                    ) from None

        if not items:
            raise CatalogueError(f"no items in any file under {items_dir}")

        self.items = items
        return items

    def _create_container_spec(
        self, container_id: str, config: Dict[str, Any]
    ) -> ItemSpec:
        """Create a container specification from config"""
        shape = self._parse_shape(config["map"], config["name"])

        # Parse effects
        effects = []
        triggers = []
        for effect_config in config.get("effects", []):
            effect = self._parse_effect(effect_config, container_id)
            if effect:
                effects.append(effect)

        # Create trigger if there are effects
        if effects:
            triggers = [PassiveTrigger(effects=effects)]

        # Create ItemSpec for the container
        spec = ItemSpec(
            id=container_id,
            name=config["name"],
            category="container",
            cost=config["cost"],
            player_class=config["class"],
            slug=config["slug"],
            shape=shape,
            triggers=triggers,
            rarity=config["rarity"],
        )

        return spec

    def _create_item_spec(self, item_id: str, config: Dict[str, Any]) -> ItemSpec:
        """Create an item specification from config"""
        # Parse shape
        shape = self._parse_shape(config["map"], config["name"])

        # Parse triggers
        triggers = []
        for trigger_config in config.get("triggers", []):
            trigger = self._parse_trigger(trigger_config, item_id)
            if trigger:
                triggers.append(trigger)

        return ItemSpec(
            id=item_id,
            name=config["name"],
            category=config["category"],
            cost=config["cost"],
            player_class=config["class"],
            slug=config["slug"],
            shape=shape,
            triggers=triggers,
            rarity=config["rarity"],
            color=config["color"],
            pattern=config["pattern"],
            in_shop=config.get("in_shop", True),
        )

    def _parse_shape(self, item_map: list, name: str) -> ItemShape:
        """The squares an item covers, from its map"""
        return parse_map(item_map, name)

    def _parse_trigger(self, config: Dict[str, Any], item_id: str) -> Optional[Any]:
        """Parse a trigger configuration"""
        trigger_type = config.get("type")
        effects = []

        # Parse effects
        for effect_config in config.get("effects", []):
            effect = self._parse_effect(effect_config, item_id)
            if effect:
                effects.append(effect)

        # Preventing damage is the one effect that cannot apply itself: it
        # has to hand a number back so the attack can be reduced by it, and
        # only the on_attacked handler asks. Anywhere else it would load
        # cleanly and do nothing, which is the failure this catches.
        if trigger_type != "on_attacked" and any(
            isinstance(e, PreventDamageEffect) for e in effects
        ):
            raise ValueError(
                f"{item_id}: prevent_damage only works in an on_attacked "
                f"trigger, not a {trigger_type!r} one. There is no attack to "
                f"prevent anywhere else."
            )

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
        elif trigger_type == "on_hit":
            # `chance` is a second roll, taken only after accuracy has passed.
            if "chance" not in config:
                raise ValueError(
                    f"{item_id}: an on_hit trigger has to state its `chance`. "
                    f"Write 1.0 if the effect always happens."
                )
            return OnHitTrigger(chance=config["chance"], effects=effects)
        elif trigger_type == "on_attacked":
            if "chance" not in config:
                raise ValueError(
                    f"{item_id}: an on_attacked trigger has to state its "
                    f"`chance`. Every shield in the source game rolls 0.3."
                )
            return OnAttackedTrigger(chance=config["chance"], effects=effects)
        elif trigger_type == "passive":
            return PassiveTrigger(effects=effects)

        return None

    def _parse_effect(self, config: Dict[str, Any], item_id: str) -> Optional[Any]:
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
        elif effect_type == "prevent_damage":
            if "value" not in config:
                raise ValueError(f"{item_id}: prevent_damage needs a `value`")
            return PreventDamageEffect(amount=config["value"])
        elif effect_type == "cpu_drain":
            if "value" not in config:
                raise ValueError(f"{item_id}: cpu_drain needs a `value`")
            return CpuDrainEffect(
                amount=config["value"],
                target_type=config.get("target", "attacker"),
            )
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
        elif effect_type == "debuff":
            name = config.get("debuff_name")
            if name not in DEBUFFS:
                raise ValueError(
                    f"{item_id}: `{name}` is not a debuff. "
                    f"Section 3.2 has three: {', '.join(sorted(DEBUFFS))}."
                )
            return DebuffEffect(
                debuff_name=name,
                value=config.get("value", 1),
                target_type=config.get("target", "enemy"),
            )
        elif effect_type == "block":
            return BlockEffect(block_amount=config.get("value", 5))
        elif effect_type == "consume":
            return ConsumeEffect()

        return None

    def get_container(self, container_id: str) -> ItemSpec:
        """Get a container by ID"""
        return self.containers[container_id]

    def get_item(self, item_id: str) -> ItemSpec:
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
config_loader.load_all()
