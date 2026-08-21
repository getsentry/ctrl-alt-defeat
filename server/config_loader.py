"""
Configuration loader for items and containers from JSON files
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from grid_system import ItemShape, parse_map
from item_effects import (
    BUFFS,
    DEBUFFS,
    MODIFIER_TARGETS,
    MODIFIERS,
    PLAYER_MODIFIERS,
    UNBUILT_EFFECTS,
    UNBUILT_TRIGGERS,
    WEAPON_KINDS,
    AfterTrigger,
    AttackEffect,
    AuraTrigger,
    BattleStartTrigger,
    BlockEffect,
    BuffEffect,
    ChanceEffect,
    ChoiceEffect,
    CleanseEffect,
    ConditionEffect,
    ConsumeEffect,
    ConvertHealthEffect,
    CostEffect,
    CounterTrigger,
    CpuDrainEffect,
    DebuffEffect,
    DestroyBlockEffect,
    EffectDamageEffect,
    ExtraAttackEffect,
    FatigueStartTrigger,
    GainDamageEffect,
    GoldEffect,
    HealEffect,
    HealthThresholdTrigger,
    InflictFatigueEffect,
    ItemSpec,
    LimitEffect,
    MaxHealthEffect,
    ModifyEffect,
    ModifyPerEffect,
    ModifyPerStatusEffect,
    NextAttackEffect,
    OnAttackedTrigger,
    OnAttackTrigger,
    OnHitTrigger,
    OnMissTrigger,
    OnStunTrigger,
    OutOfStaminaTrigger,
    PassiveTrigger,
    PerCountEffect,
    PlayerModifyEffect,
    PreventDamageEffect,
    RandomStatusEffect,
    Recipe,
    ReflectEffect,
    ResistEffect,
    SaleChanceEffect,
    ShopEnteredTrigger,
    StaminaEffect,
    StatModEffect,
    StatusChangeTrigger,
    StunEffect,
    TimerTrigger,
    TriggerItemEffect,
    WhenAffordableTrigger,
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
        # What loaded as a declared gap, as {name: [item ids]}. Empty means
        # every item in the catalogue does everything it says.
        self.unbuilt: Dict[str, List[str]] = {}

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
                    raise CatalogueError(f"{category_file.name}: {bad_item}") from None

        if not items:
            raise CatalogueError(f"no items in any file under {items_dir}")

        self.items = items
        return items

    def _create_container_spec(
        self, container_id: str, config: Dict[str, Any]
    ) -> ItemSpec:
        """Create a container specification from config"""
        shape = self._parse_shape(config["map"], config["name"])

        # Read the same way an item's are. A container used to write a bare
        # list of effects that were wrapped in a passive trigger here, which
        # meant a container could only ever be passive -- and one of them says
        # "Start of battle". A container is bought from the same shop and
        # built from the same catalogue, so it says when its clauses happen
        # the same way everything else does.
        triggers = []
        for trigger_config in config.get("triggers", []):
            trigger = self._parse_trigger(trigger_config, container_id)
            if trigger:
                triggers.append(trigger)

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
            # A container is craftable like anything else: two of the ten are.
            recipe=self._parse_recipes(config.get("recipe", []), container_id),
            recipe_only=bool(config.get("recipe_only", False)),
            shop_needs=config.get("shop_needs", ""),
            # Read the same way an item's is. It was not read at all, so every
            # container was offered in the shop whatever its own file said --
            # three Unique bags the source game gives out as treasure among
            # them.
            in_shop=config.get("in_shop", True) and not config.get("recipe_only"),
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
            # `recipe_only` is the stronger statement, so an item cannot say
            # it is craft-only and be offered anyway.
            in_shop=config.get("in_shop", True) and not config.get("recipe_only"),
            # One comma-separated string in the catalogue, a set here.
            kinds=frozenset(
                tag.strip()
                for tag in config.get("icontype", "").split(",")
                if tag.strip()
            ),
            recipe=self._parse_recipes(config.get("recipe", []), item_id),
            recipe_only=bool(config.get("recipe_only", False)),
            shop_needs=config.get("shop_needs", ""),
        )

    def _parse_recipes(self, configs: List[Dict[str, Any]], item_id: str) -> tuple:
        """The ways an item can be made.

        A recipe with no ingredients could never be completed and is more
        likely a typo than an item you get for free, so it is refused.
        """
        recipes = []
        for recipe in configs:
            ingredients = tuple(recipe.get("ingredients", ()))
            if not ingredients:
                raise CatalogueError(f"{item_id}: a recipe with no ingredients")
            recipes.append(Recipe(ingredients, tuple(recipe.get("catalysts", ()))))
        return tuple(recipes)

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
        elif trigger_type == "health_threshold":
            if "threshold" not in config:
                raise ValueError(
                    f"{item_id}: a health_threshold trigger has to state its "
                    f"`threshold`, as a fraction of maximum health."
                )
            return HealthThresholdTrigger(
                threshold=config["threshold"], effects=effects
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
            if "answers_to" not in config:
                raise ValueError(
                    f"{item_id}: an on_attacked trigger has to say what it "
                    f"`answers_to`. Every shield in the source game is written "
                    f'"On attacked (Melee)".'
                )
            answers_to = frozenset(config["answers_to"])
            unknown = answers_to - WEAPON_KINDS
            if unknown:
                raise ValueError(
                    f"{item_id}: {sorted(unknown)} is not a way of attacking. "
                    f"There are {len(WEAPON_KINDS)}: "
                    f"{', '.join(sorted(WEAPON_KINDS))}."
                )
            return OnAttackedTrigger(
                chance=config["chance"], effects=effects, answers_to=answers_to
            )
        elif trigger_type == "use":
            costs = config.get("costs")
            if not costs:
                raise ValueError(
                    f"{item_id}: a `use` trigger needs `costs`, as buff to "
                    f"stacks. It is what it waits for."
                )
            unknown = set(costs) - BUFFS
            if unknown:
                raise ValueError(
                    f"{item_id}: {sorted(unknown)} cannot be spent. Section "
                    f"3.1 has seven buffs: {', '.join(sorted(BUFFS))}."
                )
            return WhenAffordableTrigger(costs=dict(costs), effects=effects)
        elif trigger_type == "status_gained":
            if "whose" not in config:
                raise ValueError(
                    f"{item_id}: a status_gained trigger has to say `whose` "
                    f"gains it watches, `self` or `enemy`."
                )
            status = config.get("status", "")
            if status and status not in BUFFS | DEBUFFS:
                raise ValueError(f"{item_id}: `{status}` is not a buff or a debuff.")
            if not status and "kind" not in config:
                raise ValueError(
                    f"{item_id}: a status_gained trigger with no `status` has "
                    f"to say its `kind`, `buff` or `debuff`."
                )
            return StatusChangeTrigger(
                status=status,
                kind=config.get("kind", "buff"),
                whose=config["whose"],
                effects=effects,
            )
        elif trigger_type == "counter":
            for needed in ("counting", "amount", "whose", "counts"):
                if needed not in config:
                    raise ValueError(
                        f"{item_id}: a counter trigger needs a `{needed}`. "
                        f'`counts` is "held" for what a player has now or '
                        f'"gained" for everything that ever arrived.'
                    )
            counting = config["counting"]
            if counting not in BUFFS | DEBUFFS | {
                "block",
                "effect_damage",
                "health",
                "buffs",
                "debuffs",
            }:
                raise ValueError(
                    f"{item_id}: `{counting}` is not a total anything counts."
                )
            if config["counts"] not in ("held", "gained"):
                raise ValueError(
                    f"{item_id}: a counter counts what is `held` or what was "
                    f"`gained`, not `{config['counts']}`."
                )
            where = config.get("where", "")
            if where:
                if where not in MODIFIER_TARGETS:
                    raise ValueError(
                        f"{item_id}: a counter narrowed to a zone names one "
                        f"of {sorted(MODIFIER_TARGETS)}, not `{where}`."
                    )
                if counting != "block":
                    raise ValueError(
                        f"{item_id}: only `block` can be narrowed to a zone, "
                        f"because only Block is counted per item that gave it."
                    )
                # A zone answers for itself: what the items in it handed over
                # is the owner's, and it only ever goes up. Letting the other
                # two fields say otherwise would let a catalogue entry state
                # something nothing reads.
                if config["whose"] != "self" or config["counts"] != "gained":
                    raise ValueError(
                        f"{item_id}: a counter narrowed to a zone counts what "
                        f"that zone `gained` for `self`, so it cannot also say "
                        f'whose={config["whose"]!r} counts={config["counts"]!r}.'
                    )
            return CounterTrigger(
                counting=counting,
                amount=config["amount"],
                whose=config["whose"],
                counts=config["counts"],
                where=where,
                effects=effects,
            )
        elif trigger_type == "on_stun":
            return OnStunTrigger(effects=effects)
        elif trigger_type == "out_of_stamina":
            return OutOfStaminaTrigger(effects=effects)
        elif trigger_type == "on_miss":
            if "whose" not in config:
                raise ValueError(
                    f"{item_id}: an on_miss trigger has to say `whose` miss "
                    f'it answers. "On miss" is `self` and "Opponent '
                    f'misses attack" is `enemy`.'
                )
            return OnMissTrigger(whose=config["whose"], effects=effects)
        elif trigger_type == "shop_entered":
            return ShopEnteredTrigger(effects=effects)
        elif trigger_type == "aura":
            for needed in ("zone", "counting", "after", "on"):
                if needed not in config:
                    raise ValueError(
                        f"{item_id}: an aura trigger has to state its " f"`{needed}`."
                    )
            if config["zone"] not in ("star", "diamond"):
                raise ValueError(
                    f"{item_id}: an aura watches a `star` or a `diamond`, "
                    f"not `{config['zone']}`."
                )
            counting = config["counting"]
            if counting != "any" and (
                not isinstance(counting, dict)
                or len(counting) != 1
                or set(counting) - {"any", "all"}
                or not next(iter(counting.values()))
            ):
                raise ValueError(
                    f'{item_id}: `counting` is "any" for every item, or one '
                    f'of {{"any": [...]}} and {{"all": [...]}}.'
                )
            if config["after"] < 1:
                raise ValueError(
                    f"{item_id}: an aura fires after at least one activation."
                )
            if config["on"] not in AuraTrigger.WATCHES:
                raise ValueError(
                    f"{item_id}: an aura watches an item that "
                    f"{', '.join(sorted(AuraTrigger.WATCHES))}, not "
                    f"`{config['on']}`."
                )
            return AuraTrigger(
                zone=config["zone"],
                counting=counting,
                after=config["after"],
                on=config["on"],
                effects=effects,
            )
        elif trigger_type == "after":
            if "delay" not in config:
                raise ValueError(
                    f"{item_id}: an after trigger has to state its `delay`, "
                    f"in seconds."
                )
            return AfterTrigger(delay=config["delay"], effects=effects)
        elif trigger_type == "on_attack":
            if "chance" not in config:
                raise ValueError(
                    f"{item_id}: an on_attack trigger has to state its "
                    f"`chance`. Write 1.0 if it always happens."
                )
            return OnAttackTrigger(chance=config["chance"], effects=effects)
        elif trigger_type == "passive":
            return PassiveTrigger(effects=effects)
        elif trigger_type == "fatigue_start":
            return FatigueStartTrigger(effects=effects)

        if trigger_type in UNBUILT_TRIGGERS:
            self.unbuilt.setdefault(trigger_type, []).append(item_id)
            return None
        raise ValueError(
            f"{item_id}: `{trigger_type}` is not a trigger. Add it to "
            f"UNBUILT_TRIGGERS if it is real and simply not built yet."
        )

    @staticmethod
    def _per_status(config, item_id: str):
        """An amount that grows with what somebody holds.

        Written {status: rate} for the owner's own stacks, or
        {status: [rate, "enemy"]} for the opponent's, since both appear:
        "Deals +1 damage per Vampirism and +0.4 per Cold of your opponent".
        """
        rates, whose = {}, {}
        for status, worth in (config or {}).items():
            if status not in BUFFS | DEBUFFS:
                raise ValueError(
                    f"{item_id}: `{status}` is not a buff or a debuff, so "
                    f"there is nothing to count."
                )
            if isinstance(worth, list):
                rate, side = worth
                if side not in ("self", "enemy"):
                    raise ValueError(
                        f"{item_id}: `{side}` is not whose stacks to count."
                    )
            else:
                rate, side = worth, "self"
            rates[status], whose[status] = rate, side
        return rates, whose

    def _behind(self, config, item_id: str, what: str, key: str = "effects"):
        """The effects a wrapper holds.

        A wrapper with nothing behind it is a clause that lost its point in
        transcription, not a clause that does nothing, so it stops the load.
        """
        behind = [
            e
            for e in (self._parse_effect(sub, item_id) for sub in config.get(key, []))
            if e
        ]
        if not behind:
            raise ValueError(f"{item_id}: {what} needs something behind it.")
        return behind

    @staticmethod
    def _counting(config, item_id: str):
        """The `counting` field, read the same way wherever it appears.

        Required, like every other catalogue value: "any" for every item is a
        thing the catalogue says, not a thing it leaves out.
        """
        if "counting" not in config:
            raise ValueError(
                f'{item_id}: this needs a `counting`. Write "any" if it '
                f'means every item, or "free" for the empty squares.'
            )
        counting = config["counting"]
        # "any" is every item; "free" is the squares no item stands on, which
        # is the only thing counted that is not an item at all.
        if counting in ("any", "free"):
            return counting
        if (
            not isinstance(counting, dict)
            or len(counting) != 1
            or (set(counting) - {"any", "all"})
        ):
            raise ValueError(
                f'{item_id}: `counting` is "any" for every item, or '
                f'one of {{"any": [...]}} and {{"all": [...]}}.'
            )
        if not next(iter(counting.values())):
            raise ValueError(
                f'{item_id}: `counting` lists nothing. Write "any" if it '
                f"means every item."
            )
        return counting

    def _parse_effect(self, config: Dict[str, Any], item_id: str) -> Optional[Any]:
        """Parse an effect configuration"""
        effect_type = config.get("type")

        if effect_type == "attack":
            for needed in ("min_damage", "max_damage", "accuracy", "crit_chance"):
                if needed not in config:
                    raise ValueError(
                        f"{item_id}: an attack needs a `{needed}`. Write "
                        f'`"crit_chance": 0` unless the item says otherwise: '
                        f"nothing crits until something grants it."
                    )
            effect = AttackEffect(
                min_damage=config["min_damage"],
                max_damage=config["max_damage"],
                accuracy=config["accuracy"],
                crit_chance=config["crit_chance"],
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
            if "target" not in config:
                raise ValueError(f"{item_id}: cpu_drain needs a `target`")
            return CpuDrainEffect(amount=config["value"], target_type=config["target"])
        elif effect_type == "stat_mod":
            return StatModEffect(
                stat_name=config.get("stat", "max_cpu"), value=config.get("value", 1)
            )
        elif effect_type == "buff":
            name = config.get("buff_name") or config.get("stat")
            if name in MODIFIERS:
                raise ValueError(
                    f"{item_id}: `{name}` changes a number on an item, so it "
                    f"is a `modify` effect rather than a `buff`."
                )
            if name not in BUFFS:
                raise ValueError(
                    f"{item_id}: `{name}` is not a buff. Section 3.1 has "
                    f"seven: {', '.join(sorted(BUFFS))}."
                )
            if "value" not in config:
                raise ValueError(f"{item_id}: a buff needs a `value`")
            if "target" not in config:
                raise ValueError(f"{item_id}: a buff needs a `target`")
            return BuffEffect(
                buff_name=name,
                value=config["value"],
                target_type=config["target"],
                duration=config.get("duration", -1),
            )
        elif effect_type == "modify":
            stat = config.get("stat")
            if stat not in MODIFIERS:
                raise ValueError(
                    f"{item_id}: `{stat}` is not something an item modifier "
                    f"can change. There are {len(MODIFIERS)}: "
                    f"{', '.join(sorted(MODIFIERS))}."
                )
            for needed in ("value", "target", "cap", "duration"):
                if needed not in config:
                    raise ValueError(
                        f"{item_id}: a modify needs a `{needed}`. Write "
                        f'`"cap": null` for a modifier with no limit, and '
                        f'`"duration": -1` for one that lasts the battle.'
                    )
            if config["target"] not in MODIFIER_TARGETS:
                raise ValueError(
                    f"{item_id}: `{config['target']}` is not somewhere a "
                    f"modifier can reach. There are {len(MODIFIER_TARGETS)}: "
                    f"{', '.join(sorted(MODIFIER_TARGETS))}."
                )
            if config["cap"] is not None and config["duration"] > 0:
                raise ValueError(
                    f"{item_id}: a modify cannot have both a `cap` and a "
                    f"`duration`. Taking a lent modifier back does not know "
                    f"which grant it undid, so the limit would say it was "
                    f"spent when it was not."
                )
            return ModifyEffect(
                stat=stat,
                value=config["value"],
                target_type=config["target"],
                counting=self._counting(config, item_id),
                cap=config["cap"],
                duration=config["duration"],
            )
        elif effect_type == "modify_per":
            stat = config.get("stat")
            if stat not in MODIFIERS:
                raise ValueError(
                    f"{item_id}: `{stat}` is not something a modifier can "
                    f"change. There are {len(MODIFIERS)}: "
                    f"{', '.join(sorted(MODIFIERS))}."
                )
            for needed in ("value", "zone"):
                if needed not in config:
                    raise ValueError(f"{item_id}: a modify_per needs a `{needed}`")
            if config["zone"] not in ("star", "diamond"):
                raise ValueError(
                    f"{item_id}: a modify_per counts a `star` or a `diamond`, "
                    f"not `{config['zone']}`."
                )
            counting = self._counting(config, item_id)
            return ModifyPerEffect(
                stat=stat,
                value=config["value"],
                zone=config["zone"],
                counting=counting,
            )
        elif effect_type == "effect_damage":
            for needed in ("value", "lifesteal", "per_status"):
                if needed not in config:
                    raise ValueError(
                        f"{item_id}: effect_damage needs a `{needed}`. Write 0 "
                        f"for lifesteal if it heals nothing, and {{}} for "
                        f"per_status if the amount depends on nothing."
                    )
            per_status, whose = self._per_status(config["per_status"], item_id)
            return EffectDamageEffect(
                amount=config["value"],
                lifesteal=config["lifesteal"],
                per_status=per_status,
                whose=whose,
            )
        elif effect_type == "max_health":
            if "value" not in config and "share" not in config:
                raise ValueError(
                    f"{item_id}: max_health needs a `value`, a `share` of the "
                    f"maximum the battle opened on, or both."
                )
            return MaxHealthEffect(
                amount=config.get("value", 0),
                share=config.get("share", 0.0),
            )
        elif effect_type == "modify_per_status":
            for needed in ("stat", "value", "status", "whose"):
                if needed not in config:
                    raise ValueError(f"{item_id}: modify_per_status needs a `{needed}`")
            if config["stat"] not in MODIFIERS:
                raise ValueError(
                    f"{item_id}: `{config['stat']}` is not something a "
                    f"modifier can change."
                )
            status = config["status"]
            # `buffs` and `debuffs` count every stack of every kind: "Deals
            # +0.5 damage for each debuff of your opponent".
            if status not in BUFFS | DEBUFFS | {"buffs", "debuffs"}:
                raise ValueError(f"{item_id}: `{status}` is not a status to count.")
            if config["whose"] not in ("self", "enemy"):
                raise ValueError(f"{item_id}: `whose` is `self` or `enemy`.")
            target = config.get("target", "self")
            if target not in MODIFIER_TARGETS:
                raise ValueError(
                    f"{item_id}: `{target}` is not somewhere a scaled "
                    f"modifier reaches. There are {len(MODIFIER_TARGETS)}: "
                    f"{', '.join(sorted(MODIFIER_TARGETS))}."
                )
            return ModifyPerStatusEffect(
                stat=config["stat"],
                value=config["value"],
                status=status,
                whose=config["whose"],
                target_type=target,
                cap=config.get("cap"),
            )
        elif effect_type == "chance":
            if "chance" not in config:
                raise ValueError(f"{item_id}: a chance effect needs a `chance`")
            return ChanceEffect(
                chance=config["chance"],
                effects=self._behind(config, item_id, "a chance effect"),
            )
        elif effect_type == "gain_damage":
            for needed in ("amount", "target"):
                if needed not in config:
                    raise ValueError(f"{item_id}: a gain_damage needs an `{needed}`")
            if config["target"] not in MODIFIER_TARGETS | {"self", "enemy"}:
                raise ValueError(
                    f"{item_id}: `{config['target']}` is not somewhere gained "
                    f"damage can land."
                )
            return GainDamageEffect(
                amount=config["amount"],
                target_type=config["target"],
                counting=self._counting(config, item_id),
            )
        elif effect_type == "per_count":
            if "where" not in config:
                raise ValueError(
                    f"{item_id}: a per_count needs a `where` to count in. "
                    f"There are {len(MODIFIER_TARGETS)}: "
                    f"{', '.join(sorted(MODIFIER_TARGETS))}."
                )
            if config["where"] not in MODIFIER_TARGETS:
                raise ValueError(
                    f"{item_id}: `{config['where']}` is not somewhere a "
                    f"per_count can count."
                )
            return PerCountEffect(
                where=config["where"],
                counting=self._counting(config, item_id),
                effects=self._behind(config, item_id, "a per_count"),
            )
        elif effect_type == "cost":
            costs = config.get("costs")
            if not costs and not config.get("from_pool"):
                raise ValueError(
                    f"{item_id}: a cost effect needs `costs`, as buff to "
                    f"stacks, or a `from_pool` of `one` or `all`."
                )
            if config.get("from_pool") not in (None, "", "one", "all"):
                raise ValueError(
                    f"{item_id}: a cost spends `one` of the pool or `all` of "
                    f"it, not `{config['from_pool']}`."
                )
            unknown = set(costs) - BUFFS
            if unknown:
                raise ValueError(
                    f"{item_id}: {sorted(unknown)} cannot be spent. Section "
                    f"3.1 has seven buffs: {', '.join(sorted(BUFFS))}."
                )
            if any(n <= 0 for n in costs.values()):
                raise ValueError(
                    f"{item_id}: a cost of nothing is not a cost. Drop the "
                    f"wrapper instead."
                )
            return CostEffect(
                costs=dict(costs),
                effects=self._behind(config, item_id, "a cost effect"),
                from_pool=config.get("from_pool", ""),
            )
        elif effect_type == "condition":
            for needed in ("subject", "whose", "test"):
                if needed not in config:
                    raise ValueError(f"{item_id}: a condition needs a `{needed}`")
            if config["subject"] not in ("status", "buffs", "debuffs", "health"):
                raise ValueError(
                    f"{item_id}: a condition reads a `status`, all your "
                    f"`buffs` or all your `debuffs`, or your `health`. "
                    f"`{config['subject']}` is none of them."
                )
            if config["whose"] not in ("self", "enemy"):
                raise ValueError(
                    f"{item_id}: a condition reads `self` or `enemy`, not "
                    f"`{config['whose']}`."
                )
            if config["test"] not in ("at_least", "above", "below", "none"):
                raise ValueError(
                    f"{item_id}: `{config['test']}` is not a way of judging a "
                    f"condition. There are four: at_least, above, below, none."
                )
            status = config.get("status", "")
            if config["subject"] == "status":
                if not status:
                    raise ValueError(
                        f"{item_id}: a condition on a status has to say which."
                    )
                if status not in BUFFS | DEBUFFS:
                    raise ValueError(
                        f"{item_id}: `{status}` is not a buff or a debuff."
                    )
            if config["test"] != "none" and "amount" not in config:
                raise ValueError(
                    f"{item_id}: a condition needs an `amount` to judge "
                    f"against, unless it tests for `none`."
                )
            return ConditionEffect(
                subject=config["subject"],
                whose=config["whose"],
                status=status,
                test=config["test"],
                amount=config.get("amount", 0),
                effects=self._behind(config, item_id, "a condition"),
                otherwise=[
                    e
                    for e in (
                        self._parse_effect(sub, item_id)
                        for sub in config.get("otherwise", [])
                    )
                    if e
                ],
            )
        elif effect_type == "stun":
            for needed in ("duration", "target"):
                if needed not in config:
                    raise ValueError(f"{item_id}: a stun needs a `{needed}`")
            if config["target"] not in ("self", "enemy"):
                raise ValueError(
                    f"{item_id}: a stun lands on `self` or `enemy`, not "
                    f"`{config['target']}`."
                )
            return StunEffect(duration=config["duration"], target_type=config["target"])
        elif effect_type == "player_modify":
            for needed in ("stat", "value", "target", "duration"):
                if needed not in config:
                    raise ValueError(
                        f"{item_id}: a player_modify needs a `{needed}`. "
                        f"Write -1 for a duration that lasts the battle."
                    )
            if config["stat"] not in PLAYER_MODIFIERS:
                raise ValueError(
                    f"{item_id}: `{config['stat']}` is not something a "
                    f"modifier on a player can change. There are "
                    f"{len(PLAYER_MODIFIERS)}: "
                    f"{', '.join(sorted(PLAYER_MODIFIERS))}."
                )
            if config["target"] not in ("self", "enemy", "both"):
                raise ValueError(
                    f"{item_id}: a player_modify lands on `self`, `enemy` or "
                    f"`both`, not `{config['target']}`."
                )
            return PlayerModifyEffect(
                stat=config["stat"],
                value=config["value"],
                target_type=config["target"],
                duration=config["duration"],
            )
        elif effect_type == "reflect":
            for needed in ("count", "target"):
                if needed not in config:
                    raise ValueError(f"{item_id}: a reflect needs a `{needed}`")
            return ReflectEffect(count=config["count"], target_type=config["target"])
        elif effect_type == "resist":
            for needed in ("count", "chance", "target"):
                if needed not in config:
                    raise ValueError(
                        f"{item_id}: a resist needs a `{needed}`. Write 0 for "
                        f"whichever of `count` and `chance` it does not grant."
                    )
            if (
                not config["count"]
                and not config["chance"]
                and not config.get("per_status")
            ):
                raise ValueError(
                    f"{item_id}: a resist that grants neither charges nor a "
                    f"chance refuses nothing."
                )
            against = config.get("against", "debuff")
            if against not in ("debuff", "critical", "stun", "removal"):
                raise ValueError(
                    f"{item_id}: a resist refuses a `debuff`, a `critical`, a "
                    f"`stun` or a `removal`, not `{against}`."
                )
            only = tuple(config.get("only", ()))
            # Against a removal, `only` says which pool is protected -- "35%
            # chance to protect your buffs from removal" -- because a cleanse
            # takes from one or the other. Against a debuff it names the
            # debuffs refused.
            if against == "removal":
                allowed, what = {"buff", "debuff"}, "a pool to protect"
            else:
                allowed, what = DEBUFFS, "a debuff to resist"
            unknown = set(only) - allowed
            if unknown:
                raise ValueError(f"{item_id}: {sorted(unknown)} is not {what}.")
            per_status = config.get("per_status", {})
            unknown = set(per_status) - (BUFFS | DEBUFFS)
            if unknown:
                raise ValueError(
                    f"{item_id}: {sorted(unknown)} is not a status to count."
                )
            return ResistEffect(
                count=config["count"],
                chance=config["chance"],
                target_type=config["target"],
                against=against,
                only=only,
                per_status=dict(per_status),
            )
        elif effect_type == "random_status":
            for needed in ("kind", "count", "target"):
                if needed not in config:
                    raise ValueError(f"{item_id}: a random_status needs a `{needed}`")
            if config["kind"] not in ("buff", "debuff"):
                raise ValueError(
                    f"{item_id}: a random_status hands out a `buff` or a "
                    f"`debuff`, not `{config['kind']}`."
                )
            if config.get("pick", "random") not in ("random", "most", "least"):
                raise ValueError(
                    f"{item_id}: a random_status picks at `random`, or the "
                    f"kind held `most` or `least`, not `{config['pick']}`."
                )
            among = tuple(config.get("among", ()))
            unknown = set(among) - (BUFFS | DEBUFFS)
            if unknown:
                raise ValueError(
                    f"{item_id}: {sorted(unknown)} is not a buff or a debuff."
                )
            return RandomStatusEffect(
                kind=config["kind"],
                count=config["count"],
                target_type=config["target"],
                pick=config.get("pick", "random"),
                among=among,
            )
        elif effect_type == "limit":
            if "times" not in config:
                raise ValueError(
                    f'{item_id}: a limit needs `times`. Write 1 for "(once)".'
                )
            if config["times"] < 1:
                raise ValueError(
                    f"{item_id}: a limit of {config['times']} never happens. "
                    f"Drop the clause instead of writing it down as never."
                )
            return LimitEffect(
                times=config["times"],
                effects=self._behind(config, item_id, "a limit"),
            )
        elif effect_type == "stamina":
            for needed in ("amount", "target"):
                if needed not in config:
                    raise ValueError(f"{item_id}: a stamina needs an `{needed}`")
            return StaminaEffect(amount=config["amount"], target_type=config["target"])
        elif effect_type == "extra_attack":
            return ExtraAttackEffect()
        elif effect_type == "trigger_item":
            for needed in ("where", "how_many", "pick"):
                if needed not in config:
                    raise ValueError(
                        f"{item_id}: a trigger_item needs a `{needed}`. Write "
                        f"0 for `how_many` to trigger every one that counts."
                    )
            if config["where"] not in MODIFIER_TARGETS:
                raise ValueError(
                    f"{item_id}: `{config['where']}` is not somewhere a "
                    f"trigger_item can reach."
                )
            if config["pick"] not in ("all", "random"):
                raise ValueError(
                    f"{item_id}: a trigger_item takes them `all` or picks one "
                    f"at `random`, not `{config['pick']}`."
                )
            return TriggerItemEffect(
                where=config["where"],
                counting=self._counting(config, item_id),
                how_many=config["how_many"],
                pick=config["pick"],
            )
        elif effect_type == "gold":
            if "amount" not in config:
                raise ValueError(f"{item_id}: a gold effect needs an `amount`")
            return GoldEffect(amount=config["amount"])
        elif effect_type == "sale_chance":
            if "amount" not in config:
                raise ValueError(f"{item_id}: a sale_chance needs an `amount`")
            return SaleChanceEffect(amount=config["amount"])
        elif effect_type == "choice":
            choices = []
            for one in config.get("choices", []):
                behind = [
                    e for e in (self._parse_effect(sub, item_id) for sub in one) if e
                ]
                if not behind:
                    raise ValueError(
                        f"{item_id}: a choice with nothing behind it is not an "
                        f"alternative."
                    )
                choices.append(behind)
            if len(choices) < 2:
                raise ValueError(
                    f"{item_id}: a choice needs at least two `choices` to "
                    f"choose between."
                )
            return ChoiceEffect(choices=choices)
        elif effect_type == "destroy_block":
            for needed in ("amount", "target"):
                if needed not in config:
                    raise ValueError(f"{item_id}: a destroy_block needs an `{needed}`")
            return DestroyBlockEffect(
                amount=config["amount"], target_type=config["target"]
            )
        elif effect_type == "next_attack":
            for needed in ("damage", "ignores_block"):
                if needed not in config:
                    raise ValueError(
                        f"{item_id}: a next_attack needs a `{needed}`. Write 0 "
                        f"for damage and false for ignores_block."
                    )
            return NextAttackEffect(
                damage=config["damage"], ignores_block=bool(config["ignores_block"])
            )
        elif effect_type == "cleanse":
            if "count" not in config:
                raise ValueError(
                    f"{item_id}: a cleanse has to state its `count`, the "
                    f"number of statuses it takes off."
                )
            named = ", ".join(sorted(BUFFS | DEBUFFS))
            if "removes" not in config:
                raise ValueError(
                    f"{item_id}: a cleanse has to state what it `removes`. "
                    f"Write `debuff` or `buff` for any of that kind, or name "
                    f"one of: {named}."
                )
            removes = config["removes"]
            # A buff can be named as well as a debuff. "Remove 1 Luck from
            # your opponent" is the same mechanic as cleansing a Poison, and
            # a name says which pool it draws from by itself.
            if removes not in ("debuff", "buff") and removes not in BUFFS | DEBUFFS:
                raise ValueError(
                    f"{item_id}: `{removes}` is not something to cleanse. "
                    f"Write `debuff` or `buff` for any of that kind, or name "
                    f"one of: {named}."
                )
            if "target" not in config:
                raise ValueError(
                    f"{item_id}: a cleanse has to state its `target`, `self` "
                    f"or `enemy`."
                )
            return CleanseEffect(
                count=config["count"],
                removes=removes,
                target_type=config["target"],
                keep=bool(config.get("keep", False)),
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
                duration=config.get("duration", -1),
                unstackable=bool(config.get("unstackable", False)),
            )
        elif effect_type == "inflict_fatigue":
            if "target" not in config:
                raise ValueError(f"{item_id}: inflict_fatigue needs a `target`")
            return InflictFatigueEffect(target_type=config["target"])
        elif effect_type == "block":
            if "value" not in config and "of_missing_health" not in config:
                raise ValueError(
                    f"{item_id}: a block needs a `value`, a share "
                    f"`of_missing_health`, or both."
                )
            return BlockEffect(
                block_amount=config.get("value", 0),
                share_of_missing_health=config.get("of_missing_health", 0.0),
            )
        elif effect_type == "convert_health":
            for needed in ("health", "block"):
                if needed not in config:
                    raise ValueError(
                        f"{item_id}: a convert_health needs a `{needed}`: it "
                        f"names a price in health and what it buys."
                    )
            return ConvertHealthEffect(health=config["health"], block=config["block"])
        elif effect_type == "consume":
            return ConsumeEffect()

        if effect_type in UNBUILT_EFFECTS:
            self.unbuilt.setdefault(effect_type, []).append(item_id)
            return None
        raise ValueError(
            f"{item_id}: `{effect_type}` is not an effect. Add it to "
            f"UNBUILT_EFFECTS if it is real and simply not built yet."
        )

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
